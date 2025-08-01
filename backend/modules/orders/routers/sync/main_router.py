# backend/modules/orders/routers/sync/main_router.py

"""
Main sync router with core sync operations.

Handles manual sync triggers, batch operations, and retry functionality.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from core.database import get_db
from core.auth import get_current_user
from modules.staff.models.staff_models import StaffMember
from modules.orders.services.sync_service import OrderSyncService
from modules.orders.models.sync_models import (
    SyncBatch, OrderSyncStatus, SyncStatus
)
from modules.orders.tasks.sync_tasks import order_sync_scheduler
from modules.orders.schemas.sync_schemas import (
    SyncBatchResponse, ManualSyncRequest
)

from .status_router import router as status_router
from .config_router import router as config_router
from .conflict_router import router as conflict_router

logger = logging.getLogger(__name__)

# Create main router and include sub-routers
router = APIRouter(prefix="/sync", tags=["order-sync"])
router.include_router(status_router)
router.include_router(config_router)
router.include_router(conflict_router)


@router.get("/batches", response_model=List[SyncBatchResponse])
async def get_sync_batches(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> List[SyncBatchResponse]:
    """
    Get sync batch history.
    
    Returns list of recent sync batches with their results.
    """
    query = db.query(SyncBatch).order_by(SyncBatch.started_at.desc())
    
    if status:
        # Filter by completion status
        if status == "completed":
            query = query.filter(SyncBatch.completed_at.isnot(None))
        elif status == "running":
            query = query.filter(SyncBatch.completed_at.is_(None))
    
    batches = query.offset(offset).limit(limit).all()
    
    return [SyncBatchResponse.from_orm(batch) for batch in batches]


@router.post("/manual")
async def trigger_manual_sync(
    request: ManualSyncRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Trigger a manual synchronization.
    
    Can sync all pending orders or specific order IDs.
    """
    if request.order_ids:
        # Sync specific orders
        sync_service = OrderSyncService(db)
        results = {}
        
        for order_id in request.order_ids:
            try:
                success, error = await sync_service.sync_single_order(order_id)
                results[order_id] = {
                    "success": success,
                    "error": error
                }
            except ValueError as e:
                results[order_id] = {
                    "success": False,
                    "error": f"Invalid order ID {order_id}: {str(e)}"
                }
            except Exception as e:
                logger.error(f"Unexpected error syncing order {order_id}: {e}", exc_info=True)
                results[order_id] = {
                    "success": False,
                    "error": f"Internal error: {str(e)}"
                }
        
        await sync_service.close()
        
        return {
            "type": "specific_orders",
            "results": results,
            "total": len(request.order_ids),
            "successful": sum(1 for r in results.values() if r["success"])
        }
    else:
        # Trigger full sync
        if order_sync_scheduler.trigger_manual_sync():
            return {
                "type": "full_sync",
                "status": "scheduled",
                "message": "Manual sync has been scheduled and will run immediately"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to trigger manual sync"
            )


@router.post("/retry-failed")
async def retry_failed_syncs(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Retry all failed sync attempts.
    
    Resets failed orders to retry status for next sync run.
    """
    # Update failed orders to retry
    updated = db.query(OrderSyncStatus).filter(
        OrderSyncStatus.sync_status == SyncStatus.FAILED
    ).limit(limit).update({
        "sync_status": SyncStatus.RETRY,
        "next_retry_at": datetime.utcnow()
    })
    
    db.commit()
    
    # Trigger immediate sync if any were updated
    if updated > 0:
        order_sync_scheduler.trigger_manual_sync()
    
    return {
        "status": "scheduled",
        "orders_scheduled": updated,
        "message": f"{updated} failed orders scheduled for retry"
    }