# backend/modules/orders/routers/sync_router.py

"""
API endpoints for order synchronization management.

Provides endpoints for monitoring sync status, triggering manual syncs,
and managing sync conflicts.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from backend.core.database import get_db
from backend.core.auth import get_current_user
from backend.modules.staff.models import StaffMember
from backend.modules.orders.services.sync_service import OrderSyncService
from backend.modules.orders.models.sync_models import (
    SyncBatch, SyncConflict, SyncConfiguration,
    OrderSyncStatus, SyncStatus, SyncLog
)
from backend.modules.orders.models.order_models import Order
from backend.modules.orders.tasks.sync_tasks import order_sync_scheduler
from backend.modules.orders.schemas.sync_schemas import (
    SyncStatusResponse, SyncBatchResponse, SyncConflictResponse,
    SyncConfigurationUpdate, ManualSyncRequest, ConflictResolutionRequest,
    SyncMetricsResponse, SyncHealthCheckResponse
)

router = APIRouter(prefix="/sync", tags=["order-sync"])


@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status(
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> SyncStatusResponse:
    """
    Get current synchronization status overview.
    
    Returns summary of sync status including pending orders,
    recent batches, and any conflicts.
    """
    sync_service = OrderSyncService(db)
    
    try:
        status = await sync_service.get_sync_status()
        
        # Add scheduler status
        scheduler_status = order_sync_scheduler.get_job_status()
        status["scheduler"] = scheduler_status
        
        # Add configuration
        config = {
            "sync_enabled": SyncConfiguration.get_config(db, "sync_enabled", True),
            "sync_interval_minutes": SyncConfiguration.get_config(db, "sync_interval_minutes", 10),
            "conflict_resolution_mode": SyncConfiguration.get_config(db, "conflict_resolution_mode", "manual")
        }
        status["configuration"] = config
        
        return SyncStatusResponse(**status)
        
    finally:
        await sync_service.close()


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


@router.get("/conflicts", response_model=List[SyncConflictResponse])
async def get_sync_conflicts(
    status: str = Query("pending", description="Conflict resolution status"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> List[SyncConflictResponse]:
    """
    Get unresolved sync conflicts.
    
    Returns list of conflicts that need manual resolution.
    """
    conflicts = db.query(SyncConflict).filter(
        SyncConflict.resolution_status == status
    ).order_by(
        SyncConflict.detected_at.desc()
    ).limit(limit).all()
    
    return [SyncConflictResponse.from_orm(conflict) for conflict in conflicts]


@router.post("/conflicts/{conflict_id}/resolve")
async def resolve_conflict(
    conflict_id: int,
    resolution: ConflictResolutionRequest,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Resolve a sync conflict.
    
    Allows manual resolution of sync conflicts by choosing
    which version to keep or merging changes.
    """
    conflict = db.query(SyncConflict).filter(
        SyncConflict.id == conflict_id
    ).first()
    
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
    sync_status = db.query(OrderSyncStatus).filter(
        OrderSyncStatus.order_id == conflict.order_id
    ).first()
    
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
            except Exception as e:
                results[order_id] = {
                    "success": False,
                    "error": str(e)
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


@router.put("/configuration")
async def update_sync_configuration(
    config: SyncConfigurationUpdate,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Update sync configuration.
    
    Allows enabling/disabling sync and changing sync interval.
    """
    # Require admin permission
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=403,
            detail="Only administrators can modify sync configuration"
        )
    
    updated = []
    
    # Update sync enabled
    if config.sync_enabled is not None:
        sync_config = db.query(SyncConfiguration).filter(
            SyncConfiguration.config_key == "sync_enabled"
        ).first()
        
        if sync_config:
            sync_config.config_value = config.sync_enabled
        else:
            sync_config = SyncConfiguration(
                config_key="sync_enabled",
                config_value=config.sync_enabled,
                description="Enable or disable automatic order synchronization"
            )
            db.add(sync_config)
        
        sync_config.updated_by = current_user.id
        updated.append("sync_enabled")
    
    # Update sync interval
    if config.sync_interval_minutes is not None:
        if config.sync_interval_minutes < 1 or config.sync_interval_minutes > 1440:
            raise HTTPException(
                status_code=400,
                detail="Sync interval must be between 1 and 1440 minutes"
            )
        
        sync_config = db.query(SyncConfiguration).filter(
            SyncConfiguration.config_key == "sync_interval_minutes"
        ).first()
        
        if sync_config:
            sync_config.config_value = config.sync_interval_minutes
        else:
            sync_config = SyncConfiguration(
                config_key="sync_interval_minutes",
                config_value=config.sync_interval_minutes,
                description="Interval in minutes between automatic sync runs"
            )
            db.add(sync_config)
        
        sync_config.updated_by = current_user.id
        updated.append("sync_interval_minutes")
        
        # Update scheduler
        order_sync_scheduler.update_sync_interval(config.sync_interval_minutes)
    
    # Update conflict resolution mode
    if config.conflict_resolution_mode is not None:
        if config.conflict_resolution_mode not in ["auto", "manual"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid conflict resolution mode"
            )
        
        sync_config = db.query(SyncConfiguration).filter(
            SyncConfiguration.config_key == "conflict_resolution_mode"
        ).first()
        
        if sync_config:
            sync_config.config_value = config.conflict_resolution_mode
        else:
            sync_config = SyncConfiguration(
                config_key="conflict_resolution_mode",
                config_value=config.conflict_resolution_mode,
                description="How to handle sync conflicts (auto or manual)"
            )
            db.add(sync_config)
        
        sync_config.updated_by = current_user.id
        updated.append("conflict_resolution_mode")
    
    db.commit()
    
    return {
        "status": "updated",
        "updated_fields": updated
    }


@router.get("/orders/{order_id}/sync-status")
async def get_order_sync_status(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get sync status for a specific order.
    
    Returns detailed sync information for a single order.
    """
    sync_status = db.query(OrderSyncStatus).filter(
        OrderSyncStatus.order_id == order_id
    ).first()
    
    if not sync_status:
        # Check if order exists
        from backend.modules.orders.models.order_models import Order
        order = db.query(Order).filter(Order.id == order_id).first()
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        return {
            "order_id": order_id,
            "sync_status": "never_synced",
            "is_synced": order.is_synced,
            "last_sync_at": order.last_sync_at.isoformat() if order.last_sync_at else None
        }
    
    # Get sync logs for this order
    from backend.modules.orders.models.sync_models import SyncLog
    recent_logs = db.query(SyncLog).filter(
        SyncLog.order_id == order_id
    ).order_by(
        SyncLog.started_at.desc()
    ).limit(5).all()
    
    return {
        "order_id": order_id,
        "sync_status": sync_status.sync_status.value,
        "last_attempt_at": sync_status.last_attempt_at.isoformat() if sync_status.last_attempt_at else None,
        "synced_at": sync_status.synced_at.isoformat() if sync_status.synced_at else None,
        "attempt_count": sync_status.attempt_count,
        "last_error": sync_status.last_error,
        "next_retry_at": sync_status.next_retry_at.isoformat() if sync_status.next_retry_at else None,
        "remote_id": sync_status.remote_id,
        "recent_logs": [
            {
                "started_at": log.started_at.isoformat(),
                "status": log.status,
                "duration_ms": log.duration_ms,
                "error_message": log.error_message
            }
            for log in recent_logs
        ]
    }


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


@router.get("/metrics", response_model=SyncMetricsResponse)
async def get_sync_metrics(
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> SyncMetricsResponse:
    """
    Get synchronization metrics and statistics.
    
    Returns metrics for monitoring sync performance and health.
    """
    from sqlalchemy import func, and_
    from datetime import date
    
    today = date.today()
    
    # Get today's sync statistics
    today_stats = db.query(
        func.count(SyncLog.id).filter(SyncLog.status == "success").label("successful"),
        func.count(SyncLog.id).filter(SyncLog.status == "failed").label("failed"),
        func.avg(SyncLog.duration_ms).filter(SyncLog.status == "success").label("avg_duration")
    ).filter(
        func.date(SyncLog.started_at) == today
    ).first()
    
    # Get pending orders count
    pending_orders = db.query(Order).filter(
        Order.is_synced == False
    ).count()
    
    # Get retry queue size
    retry_queue = db.query(OrderSyncStatus).filter(
        OrderSyncStatus.sync_status == SyncStatus.RETRY
    ).count()
    
    # Calculate success rate
    total_today = (today_stats.successful or 0) + (today_stats.failed or 0)
    success_rate = (today_stats.successful / total_today * 100) if total_today > 0 else 0
    
    # Get conflict rate
    total_syncs = db.query(SyncLog).filter(
        func.date(SyncLog.started_at) == today
    ).count()
    
    conflicts_today = db.query(SyncConflict).filter(
        func.date(SyncConflict.detected_at) == today
    ).count()
    
    conflict_rate = (conflicts_today / total_syncs * 100) if total_syncs > 0 else 0
    
    # Get last successful batch
    last_batch = db.query(SyncBatch).filter(
        SyncBatch.successful_syncs > 0
    ).order_by(
        SyncBatch.completed_at.desc()
    ).first()
    
    # Get next scheduled sync
    scheduler_status = order_sync_scheduler.get_job_status()
    next_sync = None
    for job in scheduler_status.get("jobs", []):
        if job["id"] == "order_sync_job" and job["next_run_time"]:
            next_sync = datetime.fromisoformat(job["next_run_time"])
            break
    
    return SyncMetricsResponse(
        total_synced_today=today_stats.successful or 0,
        total_failed_today=today_stats.failed or 0,
        average_sync_time_ms=float(today_stats.avg_duration or 0),
        sync_success_rate=float(success_rate),
        pending_orders=pending_orders,
        retry_queue_size=retry_queue,
        conflict_rate=float(conflict_rate),
        last_successful_batch=last_batch.completed_at if last_batch else None,
        next_scheduled_sync=next_sync
    )


@router.get("/health", response_model=SyncHealthCheckResponse)
async def get_sync_health(
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> SyncHealthCheckResponse:
    """
    Perform sync system health check.
    
    Analyzes sync system health and provides recommendations.
    """
    issues = []
    recommendations = []
    metrics = {}
    
    # Check scheduler status
    scheduler_status = order_sync_scheduler.get_job_status()
    if not scheduler_status["scheduler_running"]:
        issues.append("Sync scheduler is not running")
        recommendations.append("Restart the sync scheduler")
    
    # Check for high failure rate
    recent_batches = db.query(SyncBatch).filter(
        SyncBatch.completed_at.isnot(None)
    ).order_by(
        SyncBatch.started_at.desc()
    ).limit(5).all()
    
    if recent_batches:
        total_success = sum(b.successful_syncs for b in recent_batches)
        total_failed = sum(b.failed_syncs for b in recent_batches)
        
        if total_failed > total_success:
            issues.append("High sync failure rate detected")
            recommendations.append("Check network connectivity and API credentials")
        
        metrics["recent_success_rate"] = (
            total_success / (total_success + total_failed) * 100
            if (total_success + total_failed) > 0 else 0
        )
    
    # Check for stale syncs
    stale_syncs = db.query(OrderSyncStatus).filter(
        OrderSyncStatus.sync_status == SyncStatus.IN_PROGRESS,
        OrderSyncStatus.last_attempt_at < datetime.utcnow() - timedelta(hours=1)
    ).count()
    
    if stale_syncs > 0:
        issues.append(f"{stale_syncs} syncs stuck in progress")
        recommendations.append("Reset stuck syncs to retry status")
    
    # Check for old unresolved conflicts
    old_conflicts = db.query(SyncConflict).filter(
        SyncConflict.resolution_status == "pending",
        SyncConflict.detected_at < datetime.utcnow() - timedelta(days=7)
    ).count()
    
    if old_conflicts > 0:
        issues.append(f"{old_conflicts} unresolved conflicts older than 7 days")
        recommendations.append("Review and resolve old conflicts")
    
    # Determine overall health status
    if len(issues) == 0:
        status = "healthy"
    elif len(issues) <= 2:
        status = "warning"
    else:
        status = "critical"
    
    metrics["scheduler_running"] = scheduler_status["scheduler_running"]
    metrics["pending_syncs"] = db.query(Order).filter(Order.is_synced == False).count()
    metrics["active_conflicts"] = db.query(SyncConflict).filter(
        SyncConflict.resolution_status == "pending"
    ).count()
    
    return SyncHealthCheckResponse(
        status=status,
        issues=issues,
        last_check=datetime.utcnow(),
        metrics=metrics,
        recommendations=recommendations
    )