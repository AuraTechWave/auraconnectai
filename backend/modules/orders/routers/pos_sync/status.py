# backend/modules/orders/routers/pos_sync/status.py

"""
Sync status endpoints for POS terminals.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import Optional

from core.database import get_db
from core.auth import get_current_user
from core.config import settings
from modules.staff.models.staff_models import StaffMember
from modules.orders.models.sync_models import OrderSyncStatus, SyncStatus
from modules.orders.models.order_models import Order
from modules.orders.schemas.sync_schemas import SyncStatusResponse
from modules.orders.tasks.sync_tasks import order_sync_scheduler

router = APIRouter()


@router.get("/sync/status", response_model=SyncStatusResponse, status_code=status.HTTP_200_OK)
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
    from modules.orders.models.sync_models import SyncConflict
    pending_conflicts = db.query(SyncConflict).filter(
        SyncConflict.resolution_status == "pending"
    ).count()
    
    # Get last batch info
    from modules.orders.models.sync_models import SyncBatch
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