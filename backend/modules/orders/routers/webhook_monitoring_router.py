# backend/modules/orders/routers/webhook_monitoring_router.py

"""
Monitoring and management endpoints for external POS webhooks.

Provides health checks, statistics, and management capabilities.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from backend.core.database import get_db
from backend.core.auth import get_current_user
from backend.modules.staff.models import StaffMember
from backend.modules.orders.models.external_pos_models import (
    ExternalPOSProvider, ExternalPOSWebhookEvent,
    ExternalPOSPaymentUpdate, ExternalPOSWebhookLog
)
from backend.modules.orders.schemas.external_pos_schemas import (
    ExternalPOSProviderResponse, ExternalPOSProviderCreate,
    ExternalPOSProviderUpdate, WebhookEventResponse,
    WebhookEventDetailResponse, WebhookStatistics,
    WebhookHealthStatus, WebhookLogResponse
)
from backend.modules.orders.enums.external_pos_enums import WebhookProcessingStatus
from backend.modules.orders.tasks.webhook_retry_task import webhook_retry_scheduler

router = APIRouter(prefix="/webhooks/external-pos/monitoring", tags=["Webhook Monitoring"])


@router.get("/health", response_model=WebhookHealthStatus)
async def get_webhook_health(
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> WebhookHealthStatus:
    """Get overall health status of the webhook system"""
    # Check provider status
    providers = db.query(ExternalPOSProvider).all()
    provider_status = []
    
    for provider in providers:
        # Get recent webhook stats
        last_24h = datetime.utcnow() - timedelta(hours=24)
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
            "status": "healthy" if failed_count == 0 else "degraded" if failed_count < 5 else "unhealthy"
        })
    
    # Get retry scheduler status
    scheduler_status = webhook_retry_scheduler.get_status()
    
    # Get recent errors
    recent_errors = db.query(ExternalPOSWebhookLog).filter(
        ExternalPOSWebhookLog.log_level == "error",
        ExternalPOSWebhookLog.occurred_at >= datetime.utcnow() - timedelta(hours=1)
    ).order_by(
        ExternalPOSWebhookLog.occurred_at.desc()
    ).limit(10).all()
    
    # Determine overall status
    unhealthy_providers = sum(1 for p in provider_status if p["status"] == "unhealthy")
    if unhealthy_providers > 0 or not scheduler_status["scheduler_running"]:
        overall_status = "unhealthy"
    elif any(p["status"] == "degraded" for p in provider_status):
        overall_status = "degraded"
    else:
        overall_status = "healthy"
    
    # Generate recommendations
    recommendations = []
    if not scheduler_status["scheduler_running"]:
        recommendations.append("Webhook retry scheduler is not running - restart the service")
    if unhealthy_providers > 0:
        recommendations.append("One or more providers have high failure rates - check provider configurations")
    
    return WebhookHealthStatus(
        status=overall_status,
        providers=provider_status,
        retry_scheduler_status=scheduler_status,
        recent_errors=[{
            "message": error.message,
            "details": error.details,
            "occurred_at": error.occurred_at.isoformat()
        } for error in recent_errors],
        recommendations=recommendations
    )


@router.get("/statistics", response_model=List[WebhookStatistics])
async def get_webhook_statistics(
    time_period_hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> List[WebhookStatistics]:
    """Get webhook processing statistics by provider"""
    start_time = datetime.utcnow() - timedelta(hours=time_period_hours)
    
    providers = db.query(ExternalPOSProvider).all()
    statistics = []
    
    for provider in providers:
        # Get event counts by status
        status_counts = db.query(
            ExternalPOSWebhookEvent.processing_status,
            func.count(ExternalPOSWebhookEvent.id)
        ).filter(
            ExternalPOSWebhookEvent.provider_id == provider.id,
            ExternalPOSWebhookEvent.created_at >= start_time
        ).group_by(
            ExternalPOSWebhookEvent.processing_status
        ).all()
        
        status_dict = dict(status_counts)
        total_events = sum(status_dict.values())
        
        # Calculate average processing time
        avg_time = db.query(
            func.avg(
                func.extract('epoch', 
                    ExternalPOSWebhookEvent.processed_at - ExternalPOSWebhookEvent.created_at
                ) * 1000
            )
        ).filter(
            ExternalPOSWebhookEvent.provider_id == provider.id,
            ExternalPOSWebhookEvent.processing_status == WebhookProcessingStatus.PROCESSED,
            ExternalPOSWebhookEvent.created_at >= start_time
        ).scalar()
        
        # Get last event time
        last_event = db.query(ExternalPOSWebhookEvent).filter(
            ExternalPOSWebhookEvent.provider_id == provider.id
        ).order_by(
            ExternalPOSWebhookEvent.created_at.desc()
        ).first()
        
        statistics.append(WebhookStatistics(
            provider_code=provider.provider_code,
            total_events=total_events,
            processed_events=status_dict.get(WebhookProcessingStatus.PROCESSED, 0),
            failed_events=status_dict.get(WebhookProcessingStatus.FAILED, 0),
            pending_events=status_dict.get(WebhookProcessingStatus.PENDING, 0),
            duplicate_events=status_dict.get(WebhookProcessingStatus.DUPLICATE, 0),
            success_rate=(
                status_dict.get(WebhookProcessingStatus.PROCESSED, 0) / total_events * 100
                if total_events > 0 else 0
            ),
            average_processing_time_ms=avg_time,
            last_event_at=last_event.created_at if last_event else None
        ))
    
    return statistics


@router.get("/providers", response_model=List[ExternalPOSProviderResponse])
async def list_providers(
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> List[ExternalPOSProviderResponse]:
    """List all configured external POS providers"""
    query = db.query(ExternalPOSProvider)
    
    if is_active is not None:
        query = query.filter(ExternalPOSProvider.is_active == is_active)
    
    providers = query.all()
    
    return [
        ExternalPOSProviderResponse(
            id=p.id,
            provider_code=p.provider_code,
            provider_name=p.provider_name,
            webhook_endpoint_id=p.webhook_endpoint_id,
            webhook_url=f"/api/webhooks/external-pos/{p.provider_code}/events",
            is_active=p.is_active,
            auth_type=p.auth_type,
            supported_events=p.supported_events,
            rate_limit_per_minute=p.rate_limit_per_minute,
            created_at=p.created_at,
            updated_at=p.updated_at
        )
        for p in providers
    ]


@router.post("/providers", response_model=ExternalPOSProviderResponse)
async def create_provider(
    provider_data: ExternalPOSProviderCreate,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> ExternalPOSProviderResponse:
    """Create a new external POS provider configuration"""
    # Check admin permission
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=403,
            detail="Only administrators can create provider configurations"
        )
    
    # Check if provider code already exists
    existing = db.query(ExternalPOSProvider).filter(
        ExternalPOSProvider.provider_code == provider_data.provider_code
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Provider with code {provider_data.provider_code} already exists"
        )
    
    provider = ExternalPOSProvider(**provider_data.dict())
    db.add(provider)
    db.commit()
    db.refresh(provider)
    
    return ExternalPOSProviderResponse(
        id=provider.id,
        provider_code=provider.provider_code,
        provider_name=provider.provider_name,
        webhook_endpoint_id=provider.webhook_endpoint_id,
        webhook_url=f"/api/webhooks/external-pos/{provider.provider_code}/events",
        is_active=provider.is_active,
        auth_type=provider.auth_type,
        supported_events=provider.supported_events,
        rate_limit_per_minute=provider.rate_limit_per_minute,
        created_at=provider.created_at,
        updated_at=provider.updated_at
    )


@router.put("/providers/{provider_id}", response_model=ExternalPOSProviderResponse)
async def update_provider(
    provider_id: int,
    update_data: ExternalPOSProviderUpdate,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> ExternalPOSProviderResponse:
    """Update an external POS provider configuration"""
    # Check admin permission
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=403,
            detail="Only administrators can update provider configurations"
        )
    
    provider = db.query(ExternalPOSProvider).filter(
        ExternalPOSProvider.id == provider_id
    ).first()
    
    if not provider:
        raise HTTPException(
            status_code=404,
            detail=f"Provider {provider_id} not found"
        )
    
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(provider, field, value)
    
    db.commit()
    db.refresh(provider)
    
    return ExternalPOSProviderResponse(
        id=provider.id,
        provider_code=provider.provider_code,
        provider_name=provider.provider_name,
        webhook_endpoint_id=provider.webhook_endpoint_id,
        webhook_url=f"/api/webhooks/external-pos/{provider.provider_code}/events",
        is_active=provider.is_active,
        auth_type=provider.auth_type,
        supported_events=provider.supported_events,
        rate_limit_per_minute=provider.rate_limit_per_minute,
        created_at=provider.created_at,
        updated_at=provider.updated_at
    )


@router.get("/events", response_model=List[WebhookEventResponse])
async def list_webhook_events(
    provider_code: Optional[str] = None,
    status: Optional[WebhookProcessingStatus] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> List[WebhookEventResponse]:
    """List webhook events with filtering"""
    query = db.query(ExternalPOSWebhookEvent).join(ExternalPOSProvider)
    
    if provider_code:
        query = query.filter(ExternalPOSProvider.provider_code == provider_code)
    
    if status:
        query = query.filter(ExternalPOSWebhookEvent.processing_status == status)
    
    events = query.order_by(
        ExternalPOSWebhookEvent.created_at.desc()
    ).offset(offset).limit(limit).all()
    
    return [
        WebhookEventResponse(
            id=e.id,
            event_id=e.event_id,
            provider_code=e.provider.provider_code,
            event_type=e.event_type,
            event_timestamp=e.event_timestamp,
            processing_status=e.processing_status,
            is_verified=e.is_verified,
            processed_at=e.processed_at,
            processing_attempts=e.processing_attempts,
            last_error=e.last_error,
            created_at=e.created_at
        )
        for e in events
    ]


@router.get("/events/{event_id}", response_model=WebhookEventDetailResponse)
async def get_webhook_event_detail(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> WebhookEventDetailResponse:
    """Get detailed information about a specific webhook event"""
    event = db.query(ExternalPOSWebhookEvent).filter(
        ExternalPOSWebhookEvent.event_id == event_id
    ).first()
    
    if not event:
        raise HTTPException(
            status_code=404,
            detail=f"Webhook event {event_id} not found"
        )
    
    # Get payment updates
    payment_updates = db.query(ExternalPOSPaymentUpdate).filter(
        ExternalPOSPaymentUpdate.webhook_event_id == event.id
    ).all()
    
    return WebhookEventDetailResponse(
        id=event.id,
        event_id=event.event_id,
        provider_code=event.provider.provider_code,
        event_type=event.event_type,
        event_timestamp=event.event_timestamp,
        processing_status=event.processing_status,
        is_verified=event.is_verified,
        processed_at=event.processed_at,
        processing_attempts=event.processing_attempts,
        last_error=event.last_error,
        created_at=event.created_at,
        request_headers=event.request_headers,
        request_body=event.request_body,
        verification_details=event.verification_details,
        payment_updates=payment_updates
    )


@router.get("/events/{event_id}/logs", response_model=List[WebhookLogResponse])
async def get_webhook_event_logs(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> List[WebhookLogResponse]:
    """Get processing logs for a webhook event"""
    event = db.query(ExternalPOSWebhookEvent).filter(
        ExternalPOSWebhookEvent.event_id == event_id
    ).first()
    
    if not event:
        raise HTTPException(
            status_code=404,
            detail=f"Webhook event {event_id} not found"
        )
    
    logs = db.query(ExternalPOSWebhookLog).filter(
        ExternalPOSWebhookLog.webhook_event_id == event.id
    ).order_by(
        ExternalPOSWebhookLog.occurred_at.asc()
    ).all()
    
    return logs


@router.post("/retry-failed")
async def retry_failed_webhooks(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> Dict[str, Any]:
    """Manually trigger retry of failed webhooks"""
    # Check admin permission
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=403,
            detail="Only administrators can trigger webhook retries"
        )
    
    # Trigger immediate retry
    success = webhook_retry_scheduler.trigger_immediate_retry()
    
    if success:
        return {
            "status": "triggered",
            "message": f"Webhook retry triggered for up to {limit} failed events"
        }
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to trigger webhook retry"
        )