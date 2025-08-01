# backend/modules/orders/routers/webhook/health_router.py

"""
Health and statistics endpoints for webhook monitoring.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import datetime, timedelta

from core.database import get_db
from core.auth import get_current_user
from core.config import settings
from modules.staff.models.staff_models import StaffMember
from modules.orders.models.external_pos_models import (
    ExternalPOSProvider, ExternalPOSWebhookEvent
)
from modules.orders.schemas.external_pos_schemas import (
    WebhookStatistics, WebhookHealthStatus
)
from modules.orders.enums.external_pos_enums import WebhookProcessingStatus
from modules.orders.tasks.webhook_retry_task import webhook_retry_scheduler

router = APIRouter(
    prefix="/webhooks/external-pos/health",
    tags=["Webhook Health"],
    dependencies=[Depends(get_current_user)]
)


@router.get("/status", response_model=WebhookHealthStatus)
async def get_webhook_health(
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> WebhookHealthStatus:
    """Get overall webhook system health status"""
    
    # Get provider status
    providers = db.query(ExternalPOSProvider).all()
    provider_status = []
    
    for provider in providers:
        # Get recent webhook stats
        last_24h = datetime.utcnow() - timedelta(hours=settings.WEBHOOK_HEALTH_CHECK_HOURS)
        recent_events = db.query(ExternalPOSWebhookEvent).filter(
            ExternalPOSWebhookEvent.provider_id == provider.id,
            ExternalPOSWebhookEvent.created_at >= last_24h
        ).all()
        
        failed_count = sum(1 for e in recent_events if e.processing_status == WebhookProcessingStatus.FAILED)
        success_count = sum(1 for e in recent_events if e.processing_status == WebhookProcessingStatus.PROCESSED)
        
        provider_status.append({
            "provider_code": provider.provider_code,
            "is_active": provider.is_active,
            "recent_events": len(recent_events),
            "success_rate": (success_count / len(recent_events) * 100) if recent_events else 100,
            "status": "healthy" if failed_count == 0 else "degraded" if failed_count < settings.WEBHOOK_HEALTH_DEGRADED_THRESHOLD else "unhealthy"
        })
    
    # Get retry scheduler status
    scheduler_status = webhook_retry_scheduler.get_status()
    
    # Get recent error logs
    recent_errors = db.query(ExternalPOSWebhookEvent).filter(
        ExternalPOSWebhookEvent.processing_status == WebhookProcessingStatus.FAILED,
        ExternalPOSWebhookEvent.created_at >= datetime.utcnow() - timedelta(hours=1)
    ).order_by(
        ExternalPOSWebhookEvent.created_at.desc()
    ).limit(settings.WEBHOOK_RECENT_EVENTS_LIMIT).all()
    
    return WebhookHealthStatus(
        overall_status="healthy" if all(p["status"] == "healthy" for p in provider_status) else "degraded",
        provider_status=provider_status,
        scheduler_status=scheduler_status,
        recent_errors=[{
            "event_id": str(error.event_id),
            "provider": error.provider.provider_code,
            "error": error.last_error,
            "timestamp": error.created_at.isoformat()
        } for error in recent_errors]
    )


@router.get("/statistics", response_model=List[WebhookStatistics])
async def get_webhook_statistics(
    time_period_hours: int = Query(settings.WEBHOOK_STATS_DEFAULT_HOURS, ge=1, le=settings.WEBHOOK_STATS_MAX_HOURS),
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> List[WebhookStatistics]:
    """Get webhook processing statistics"""
    
    start_time = datetime.utcnow() - timedelta(hours=time_period_hours)
    providers = db.query(ExternalPOSProvider).all()
    statistics = []
    
    for provider in providers:
        # Get event counts by status
        status_counts = db.query(
            ExternalPOSWebhookEvent.processing_status,
            func.count(ExternalPOSWebhookEvent.id).label('count')
        ).filter(
            ExternalPOSWebhookEvent.provider_id == provider.id,
            ExternalPOSWebhookEvent.created_at >= start_time
        ).group_by(
            ExternalPOSWebhookEvent.processing_status
        ).all()
        
        status_dict = {status: count for status, count in status_counts}
        total_events = sum(status_dict.values())
        
        # Calculate average processing time
        avg_processing_time = db.query(
            func.avg(
                func.extract(
                    'epoch',
                    ExternalPOSWebhookEvent.processed_at - ExternalPOSWebhookEvent.created_at
                ) * 1000  # Convert to milliseconds
            )
        ).filter(
            ExternalPOSWebhookEvent.provider_id == provider.id,
            ExternalPOSWebhookEvent.created_at >= start_time,
            ExternalPOSWebhookEvent.processed_at.isnot(None)
        ).scalar() or 0
        
        statistics.append(WebhookStatistics(
            provider_code=provider.provider_code,
            provider_name=provider.provider_name,
            time_period_hours=time_period_hours,
            total_events=total_events,
            successful_events=status_dict.get(WebhookProcessingStatus.PROCESSED, 0),
            failed_events=status_dict.get(WebhookProcessingStatus.FAILED, 0),
            retry_events=status_dict.get(WebhookProcessingStatus.RETRY, 0),
            duplicate_events=status_dict.get(WebhookProcessingStatus.DUPLICATE, 0),
            success_rate=(
                status_dict.get(WebhookProcessingStatus.PROCESSED, 0) / total_events * 100
                if total_events > 0 else 0
            ),
            average_processing_time_ms=avg_processing_time
        ))
    
    return statistics