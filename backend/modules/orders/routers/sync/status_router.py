# backend/modules/orders/routers/sync/status_router.py

"""
Sync status and monitoring endpoints.

Handles sync status queries, metrics, and health checks.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Dict, Any
from datetime import datetime, timedelta, date
import logging

from core.database import get_db
from core.auth import get_current_user
from modules.staff.models.staff_models import StaffMember
from modules.orders.services.sync_service import OrderSyncService
from modules.orders.models.sync_models import (
    SyncBatch,
    OrderSyncStatus,
    SyncStatus,
    SyncLog,
    SyncConfiguration,
    SyncConflict,
)
from modules.orders.models.order_models import Order
from modules.orders.tasks.sync_tasks import order_sync_scheduler
from modules.orders.schemas.sync_schemas import (
    SyncStatusResponse,
    SyncBatchResponse,
    SyncMetricsResponse,
    SyncHealthCheckResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["sync-status"])


@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status(
    db: Session = Depends(get_db), current_user: StaffMember = Depends(get_current_user)
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
            "sync_interval_minutes": SyncConfiguration.get_config(
                db, "sync_interval_minutes", 10
            ),
            "conflict_resolution_mode": SyncConfiguration.get_config(
                db, "conflict_resolution_mode", "manual"
            ),
        }
        status["configuration"] = config

        return SyncStatusResponse(**status)

    finally:
        await sync_service.close()


@router.get("/orders/{order_id}/sync-status")
async def get_order_sync_status(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get sync status for a specific order.

    Returns detailed sync information for a single order.
    """
    sync_status = (
        db.query(OrderSyncStatus).filter(OrderSyncStatus.order_id == order_id).first()
    )

    if not sync_status:
        # Check if order exists
        order = db.query(Order).filter(Order.id == order_id).first()

        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        return {
            "order_id": order_id,
            "sync_status": "never_synced",
            "is_synced": order.is_synced,
            "last_sync_at": (
                order.last_sync_at.isoformat() if order.last_sync_at else None
            ),
        }

    # Get sync logs for this order
    recent_logs = (
        db.query(SyncLog)
        .filter(SyncLog.order_id == order_id)
        .order_by(SyncLog.started_at.desc())
        .limit(5)
        .all()
    )

    return {
        "order_id": order_id,
        "sync_status": sync_status.sync_status.value,
        "last_attempt_at": (
            sync_status.last_attempt_at.isoformat()
            if sync_status.last_attempt_at
            else None
        ),
        "synced_at": (
            sync_status.synced_at.isoformat() if sync_status.synced_at else None
        ),
        "attempt_count": sync_status.attempt_count,
        "last_error": sync_status.last_error,
        "next_retry_at": (
            sync_status.next_retry_at.isoformat() if sync_status.next_retry_at else None
        ),
        "remote_id": sync_status.remote_id,
        "recent_logs": [
            {
                "started_at": log.started_at.isoformat(),
                "status": log.status,
                "duration_ms": log.duration_ms,
                "error_message": log.error_message,
            }
            for log in recent_logs
        ],
    }


@router.get("/metrics", response_model=SyncMetricsResponse)
async def get_sync_metrics(
    db: Session = Depends(get_db), current_user: StaffMember = Depends(get_current_user)
) -> SyncMetricsResponse:
    """
    Get synchronization metrics and statistics.

    Returns metrics for monitoring sync performance and health.
    """
    today = date.today()

    # Get today's sync statistics
    today_stats = (
        db.query(
            func.count(SyncLog.id)
            .filter(SyncLog.status == "success")
            .label("successful"),
            func.count(SyncLog.id).filter(SyncLog.status == "failed").label("failed"),
            func.avg(SyncLog.duration_ms)
            .filter(SyncLog.status == "success")
            .label("avg_duration"),
        )
        .filter(func.date(SyncLog.started_at) == today)
        .first()
    )

    # Get pending orders count
    pending_orders = db.query(Order).filter(Order.is_synced == False).count()

    # Get retry queue size
    retry_queue = (
        db.query(OrderSyncStatus)
        .filter(OrderSyncStatus.sync_status == SyncStatus.RETRY)
        .count()
    )

    # Calculate success rate
    total_today = (today_stats.successful or 0) + (today_stats.failed or 0)
    success_rate = (
        (today_stats.successful / total_today * 100) if total_today > 0 else 0
    )

    # Get conflict rate
    total_syncs = (
        db.query(SyncLog).filter(func.date(SyncLog.started_at) == today).count()
    )

    conflicts_today = (
        db.query(SyncConflict)
        .filter(func.date(SyncConflict.detected_at) == today)
        .count()
    )

    conflict_rate = (conflicts_today / total_syncs * 100) if total_syncs > 0 else 0

    # Get last successful batch
    last_batch = (
        db.query(SyncBatch)
        .filter(SyncBatch.successful_syncs > 0)
        .order_by(SyncBatch.completed_at.desc())
        .first()
    )

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
        next_scheduled_sync=next_sync,
    )


@router.get("/health", response_model=SyncHealthCheckResponse)
async def get_sync_health(
    db: Session = Depends(get_db), current_user: StaffMember = Depends(get_current_user)
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
    recent_batches = (
        db.query(SyncBatch)
        .filter(SyncBatch.completed_at.isnot(None))
        .order_by(SyncBatch.started_at.desc())
        .limit(5)
        .all()
    )

    if recent_batches:
        total_success = sum(b.successful_syncs for b in recent_batches)
        total_failed = sum(b.failed_syncs for b in recent_batches)

        if total_failed > total_success:
            issues.append("High sync failure rate detected")
            recommendations.append("Check network connectivity and API credentials")

        metrics["recent_success_rate"] = (
            total_success / (total_success + total_failed) * 100
            if (total_success + total_failed) > 0
            else 0
        )

    # Check for stale syncs
    stale_syncs = (
        db.query(OrderSyncStatus)
        .filter(
            OrderSyncStatus.sync_status == SyncStatus.IN_PROGRESS,
            OrderSyncStatus.last_attempt_at < datetime.utcnow() - timedelta(hours=1),
        )
        .count()
    )

    if stale_syncs > 0:
        issues.append(f"{stale_syncs} syncs stuck in progress")
        recommendations.append("Reset stuck syncs to retry status")

    # Check for old unresolved conflicts
    old_conflicts = (
        db.query(SyncConflict)
        .filter(
            SyncConflict.resolution_status == "pending",
            SyncConflict.detected_at < datetime.utcnow() - timedelta(days=7),
        )
        .count()
    )

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
    metrics["active_conflicts"] = (
        db.query(SyncConflict)
        .filter(SyncConflict.resolution_status == "pending")
        .count()
    )

    return SyncHealthCheckResponse(
        status=status,
        issues=issues,
        last_check=datetime.utcnow(),
        metrics=metrics,
        recommendations=recommendations,
    )
