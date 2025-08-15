# backend/modules/orders/routers/sync/conflict_router.py

"""
Sync conflict management endpoints.

Handles conflict resolution and related operations.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict
from datetime import datetime
import logging

from core.database import get_db
from core.auth import get_current_user
from modules.staff.models.staff_models import StaffMember
from modules.orders.models.sync_models import SyncConflict, OrderSyncStatus, SyncStatus
from modules.orders.schemas.sync_schemas import (
    SyncConflictResponse,
    ConflictResolutionRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["sync-conflicts"])


@router.get("/conflicts", response_model=List[SyncConflictResponse])
async def get_sync_conflicts(
    status: str = Query("pending", description="Conflict resolution status"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user),
) -> List[SyncConflictResponse]:
    """
    Get unresolved sync conflicts.

    Returns list of conflicts that need manual resolution.
    """
    conflicts = (
        db.query(SyncConflict)
        .filter(SyncConflict.resolution_status == status)
        .order_by(SyncConflict.detected_at.desc())
        .limit(limit)
        .all()
    )

    return [SyncConflictResponse.from_orm(conflict) for conflict in conflicts]


@router.post("/conflicts/{conflict_id}/resolve")
async def resolve_conflict(
    conflict_id: int,
    resolution: ConflictResolutionRequest,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user),
) -> Dict[str, str]:
    """
    Resolve a sync conflict.

    Allows manual resolution of sync conflicts by choosing
    which version to keep or merging changes.
    """
    conflict = db.query(SyncConflict).filter(SyncConflict.id == conflict_id).first()

    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict not found")

    if conflict.resolution_status != "pending":
        raise HTTPException(status_code=400, detail="Conflict already resolved")

    # Apply resolution
    conflict.resolution_method = resolution.resolution_method
    conflict.resolved_at = datetime.utcnow()
    conflict.resolved_by = current_user.id
    conflict.resolution_notes = resolution.notes
    conflict.resolution_status = "resolved"

    # Update sync status based on resolution
    sync_status = (
        db.query(OrderSyncStatus)
        .filter(OrderSyncStatus.order_id == conflict.order_id)
        .first()
    )

    if sync_status:
        if resolution.resolution_method in ["local_wins", "merge"]:
            # Retry sync with resolved data
            sync_status.sync_status = SyncStatus.RETRY
            sync_status.next_retry_at = datetime.utcnow()
            sync_status.conflict_data = None
        elif resolution.resolution_method == "remote_wins":
            # Mark as synced since we're accepting remote version
            sync_status.sync_status = SyncStatus.SYNCED
            sync_status.synced_at = datetime.utcnow()

    # Store final data
    if resolution.final_data:
        conflict.final_data = resolution.final_data

    db.commit()

    return {"status": "resolved", "conflict_id": conflict_id}
