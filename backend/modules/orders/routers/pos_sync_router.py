# backend/modules/orders/routers/pos_sync_router.py

"""
POS-specific sync endpoints.

Provides a simplified POST /pos/sync endpoint for POS terminals
to trigger manual synchronization.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from backend.core.database import get_db
from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.modules.staff.models import StaffMember
from backend.modules.orders.services.sync_service import OrderSyncService
from backend.modules.orders.models.sync_models import OrderSyncStatus, SyncStatus
from backend.modules.orders.models.order_models import Order
from backend.modules.orders.tasks.sync_tasks import order_sync_scheduler
from backend.modules.orders.schemas.sync_schemas import (
    ManualSyncRequest, SyncStatusResponse
)
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pos", tags=["pos-sync"])


class POSSyncRequest(BaseModel):
    """Request model for POS sync endpoint"""
    terminal_id: Optional[str] = Field(
        None,
        description="POS terminal identifier"
    )
    order_ids: Optional[List[int]] = Field(
        None,
        description="Specific order IDs to sync"
    )
    sync_all_pending: bool = Field(
        True,
        description="Sync all pending orders if order_ids not provided"
    )
    include_recent: bool = Field(
        False,
        description="Include recently synced orders (last 24 hours)"
    )


class POSSyncResponse(BaseModel):
    """Response model for POS sync endpoint"""
    status: str  # initiated, completed, failed
    terminal_id: Optional[str]
    sync_batch_id: Optional[str]
    orders_queued: int
    orders_synced: int = 0
    orders_failed: int = 0
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: Optional[Dict[str, Any]] = None


@router.post("/sync", response_model=POSSyncResponse)
async def trigger_pos_sync(
    request: POSSyncRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> POSSyncResponse:
    """
    Trigger manual synchronization from POS terminal.
    
    This endpoint allows POS terminals to manually trigger order synchronization
    with the cloud system. It can sync specific orders or all pending orders.
    
    Returns immediately with sync status while processing happens in background.
    """
    terminal_id = request.terminal_id or settings.POS_TERMINAL_ID
    
    logger.info(
        f"POS sync requested from terminal {terminal_id}",
        extra={
            "terminal_id": terminal_id,
            "user_id": current_user.id,
            "order_ids": request.order_ids,
            "sync_all_pending": request.sync_all_pending
        }
    )
    
    try:
        if request.order_ids:
            # Sync specific orders
            return await _sync_specific_orders(
                order_ids=request.order_ids,
                terminal_id=terminal_id,
                background_tasks=background_tasks,
                db=db
            )
        elif request.sync_all_pending:
            # Sync all pending orders
            return await _sync_all_pending_orders(
                include_recent=request.include_recent,
                terminal_id=terminal_id,
                background_tasks=background_tasks,
                db=db
            )
        else:
            return POSSyncResponse(
                status="failed",
                terminal_id=terminal_id,
                orders_queued=0,
                message="No orders specified for sync",
                details={"error": "Either provide order_ids or set sync_all_pending=true"}
            )
            
    except Exception as e:
        logger.error(
            f"Error initiating POS sync: {str(e)}",
            extra={"terminal_id": terminal_id},
            exc_info=True
        )
        
        return POSSyncResponse(
            status="failed",
            terminal_id=terminal_id,
            orders_queued=0,
            message=f"Failed to initiate sync: {str(e)}",
            details={"error": str(e)}
        )


async def _sync_specific_orders(
    order_ids: List[int],
    terminal_id: str,
    background_tasks: BackgroundTasks,
    db: Session
) -> POSSyncResponse:
    """Sync specific order IDs"""
    
    # Validate orders exist and belong to this terminal
    valid_orders = db.query(Order).filter(
        Order.id.in_(order_ids),
        Order.is_deleted == False
    ).all()
    
    if not valid_orders:
        return POSSyncResponse(
            status="failed",
            terminal_id=terminal_id,
            orders_queued=0,
            message="No valid orders found",
            details={"requested_ids": order_ids, "found": 0}
        )
    
    # Create or update sync status for each order
    orders_to_sync = []
    for order in valid_orders:
        sync_status = db.query(OrderSyncStatus).filter(
            OrderSyncStatus.order_id == order.id
        ).first()
        
        if not sync_status:
            sync_status = OrderSyncStatus(
                order_id=order.id,
                sync_status=SyncStatus.PENDING,
                sync_direction="local_to_remote"
            )
            db.add(sync_status)
        else:
            sync_status.sync_status = SyncStatus.PENDING
            sync_status.next_retry_at = datetime.utcnow()
        
        orders_to_sync.append(order.id)
    
    db.commit()
    
    # Queue background sync task
    background_tasks.add_task(
        _process_sync_batch,
        order_ids=orders_to_sync,
        terminal_id=terminal_id
    )
    
    return POSSyncResponse(
        status="initiated",
        terminal_id=terminal_id,
        orders_queued=len(orders_to_sync),
        message=f"Sync initiated for {len(orders_to_sync)} orders",
        details={
            "order_ids": orders_to_sync,
            "invalid_ids": list(set(order_ids) - set(o.id for o in valid_orders))
        }
    )


async def _sync_all_pending_orders(
    include_recent: bool,
    terminal_id: str,
    background_tasks: BackgroundTasks,
    db: Session
) -> POSSyncResponse:
    """Sync all pending orders"""
    
    # Get unsynced orders
    query = db.query(OrderSyncStatus).join(Order).filter(
        Order.is_deleted == False,
        OrderSyncStatus.sync_status.in_([
            SyncStatus.PENDING,
            SyncStatus.FAILED,
            SyncStatus.RETRY
        ])
    )
    
    # Optionally include recently synced orders
    if include_recent:
        recent_cutoff = datetime.utcnow().replace(hour=0, minute=0, second=0)
        query = query.filter(
            db.or_(
                OrderSyncStatus.sync_status != SyncStatus.SYNCED,
                OrderSyncStatus.synced_at >= recent_cutoff
            )
        )
    
    pending_sync_statuses = query.all()
    
    if not pending_sync_statuses:
        # Check for orders without sync status
        orders_without_sync = db.query(Order).outerjoin(OrderSyncStatus).filter(
            Order.is_deleted == False,
            OrderSyncStatus.id.is_(None)
        ).all()
        
        # Create sync status for orders that don't have one
        for order in orders_without_sync:
            sync_status = OrderSyncStatus(
                order_id=order.id,
                sync_status=SyncStatus.PENDING,
                sync_direction="local_to_remote"
            )
            db.add(sync_status)
            pending_sync_statuses.append(sync_status)
        
        db.commit()
    
    order_ids = [s.order_id for s in pending_sync_statuses]
    
    if order_ids:
        # Trigger sync scheduler
        if order_sync_scheduler.trigger_manual_sync():
            return POSSyncResponse(
                status="initiated",
                terminal_id=terminal_id,
                sync_batch_id=f"manual_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                orders_queued=len(order_ids),
                message=f"Sync initiated for {len(order_ids)} pending orders",
                details={
                    "sync_type": "scheduled_batch",
                    "include_recent": include_recent
                }
            )
        else:
            return POSSyncResponse(
                status="failed",
                terminal_id=terminal_id,
                orders_queued=0,
                message="Failed to trigger sync scheduler",
                details={"error": "Scheduler unavailable"}
            )
    else:
        return POSSyncResponse(
            status="completed",
            terminal_id=terminal_id,
            orders_queued=0,
            message="No pending orders to sync",
            details={"checked_recent": include_recent}
        )


async def _process_sync_batch(order_ids: List[int], terminal_id: str):
    """Process sync batch in background"""
    db = next(get_db())
    try:
        sync_service = OrderSyncService(db)
        
        for order_id in order_ids:
            try:
                await sync_service.sync_single_order(order_id)
            except Exception as e:
                logger.error(
                    f"Error syncing order {order_id}: {str(e)}",
                    extra={"terminal_id": terminal_id, "order_id": order_id},
                    exc_info=True
                )
        
        await sync_service.close()
        
    except Exception as e:
        logger.error(
            f"Error in sync batch processing: {str(e)}",
            extra={"terminal_id": terminal_id},
            exc_info=True
        )
    finally:
        db.close()


@router.get("/sync/status", response_model=SyncStatusResponse)
async def get_pos_sync_status(
    terminal_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> SyncStatusResponse:
    """
    Get current sync status for POS terminal.
    
    Returns overview of sync status including pending orders,
    conflicts, and recent sync activity.
    """
    terminal_id = terminal_id or settings.POS_TERMINAL_ID
    
    # Get sync status counts
    status_counts = {}
    for status in SyncStatus:
        count = db.query(OrderSyncStatus).filter(
            OrderSyncStatus.sync_status == status
        ).count()
        status_counts[status.value] = count
    
    # Get unsynced orders count
    unsynced_orders = db.query(Order).outerjoin(OrderSyncStatus).filter(
        Order.is_deleted == False,
        db.or_(
            OrderSyncStatus.id.is_(None),
            OrderSyncStatus.sync_status != SyncStatus.SYNCED
        )
    ).count()
    
    # Get pending conflicts
    from backend.modules.orders.models.sync_models import SyncConflict
    pending_conflicts = db.query(SyncConflict).filter(
        SyncConflict.resolution_status == "pending"
    ).count()
    
    # Get last batch info
    from backend.modules.orders.models.sync_models import SyncBatch
    last_batch = db.query(SyncBatch).order_by(
        SyncBatch.started_at.desc()
    ).first()
    
    last_batch_info = None
    if last_batch:
        last_batch_info = {
            "batch_id": last_batch.batch_id,
            "started_at": last_batch.started_at.isoformat(),
            "completed_at": last_batch.completed_at.isoformat() if last_batch.completed_at else None,
            "total_orders": last_batch.total_orders,
            "successful_syncs": last_batch.successful_syncs,
            "failed_syncs": last_batch.failed_syncs
        }
    
    # Get scheduler status
    scheduler_status = order_sync_scheduler.get_scheduler_status()
    
    return SyncStatusResponse(
        sync_status_counts=status_counts,
        unsynced_orders=unsynced_orders,
        pending_conflicts=pending_conflicts,
        last_batch=last_batch_info,
        scheduler=scheduler_status,
        configuration={
            "sync_enabled": settings.SYNC_ENABLED,
            "sync_interval_minutes": settings.SYNC_INTERVAL_MINUTES,
            "terminal_id": terminal_id,
            "cloud_endpoint": settings.CLOUD_SYNC_ENDPOINT
        }
    )