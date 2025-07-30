# backend/modules/orders/routers/pos_sync/manual_sync.py

"""
Manual sync endpoints for POS terminals.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import logging

from backend.core.database import get_db
from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.modules.staff.models import StaffMember
from backend.modules.orders.models.sync_models import OrderSyncStatus, SyncStatus
from backend.modules.orders.models.order_models import Order
from backend.modules.orders.tasks.sync_tasks import order_sync_scheduler
from .schemas import POSSyncRequest, POSSyncResponse
from .helpers import process_sync_batch

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/sync", response_model=POSSyncResponse, status_code=status.HTTP_202_ACCEPTED)
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
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either provide order_ids or set sync_all_pending=true"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error initiating POS sync: {str(e)}",
            extra={"terminal_id": terminal_id},
            exc_info=True
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate sync: {str(e)}"
        )


async def _sync_specific_orders(
    order_ids: List[int],
    terminal_id: str,
    background_tasks: BackgroundTasks,
    db: Session
) -> POSSyncResponse:
    """Sync specific order IDs"""
    
    # Handle empty order_ids
    if not order_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="order_ids cannot be empty when provided"
        )
    
    # Validate orders exist and belong to this terminal
    valid_orders = db.query(Order).filter(
        Order.id.in_(order_ids),
        Order.is_deleted == False
    ).all()
    
    if not valid_orders:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No valid orders found for IDs: {order_ids}"
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
        process_sync_batch,
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
    """Sync all pending orders with batching support"""
    
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
        from datetime import timedelta
        recent_cutoff = datetime.utcnow() - timedelta(hours=settings.POS_SYNC_RECENT_HOURS)
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
        if not order_sync_scheduler.trigger_manual_sync():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Sync scheduler is unavailable"
            )
            
        return POSSyncResponse(
            status="initiated",
            terminal_id=terminal_id,
            sync_batch_id=f"{settings.POS_SYNC_BATCH_PREFIX}_{datetime.utcnow().strftime(settings.POS_SYNC_DATE_FORMAT)}",
            orders_queued=len(order_ids),
            message=f"Sync initiated for {len(order_ids)} pending orders",
            details={
                "sync_type": "scheduled_batch",
                "include_recent": include_recent
            }
        )
    else:
        return POSSyncResponse(
            status="completed",
            terminal_id=terminal_id,
            orders_queued=0,
            message="No pending orders to sync",
            details={"checked_recent": include_recent}
        )