# backend/modules/orders/routers/webhook/monitoring_router.py

"""
Webhook event monitoring and management endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from core.database import get_db
from core.auth import get_current_user
from core.config import settings
from modules.staff.models.staff_models import StaffMember
from modules.orders.models.external_pos_models import (
    ExternalPOSProvider,
    ExternalPOSWebhookEvent,
    ExternalPOSWebhookLog,
    ExternalPOSPaymentUpdate,
)
from modules.orders.schemas.external_pos_schemas import (
    WebhookEventResponse,
    WebhookEventDetailResponse,
    WebhookLogResponse,
)
from modules.orders.enums.external_pos_enums import WebhookProcessingStatus
from modules.orders.services.external_pos_webhook_service import (
    ExternalPOSWebhookService,
)
from modules.orders.tasks.webhook_retry_task import webhook_retry_scheduler

router = APIRouter(
    prefix="/webhooks/external-pos/monitoring",
    tags=["Webhook Monitoring"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/events", response_model=List[WebhookEventResponse])
async def list_webhook_events(
    provider_code: Optional[str] = None,
    status: Optional[WebhookProcessingStatus] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user),
) -> List[WebhookEventResponse]:
    """List webhook events with filtering"""

    check_permission(current_user, "webhooks", "read")

    query = db.query(ExternalPOSWebhookEvent)

    if provider_code:
        query = query.join(ExternalPOSWebhookEvent.provider).filter(
            ExternalPOSProvider.provider_code == provider_code
        )

    if status:
        query = query.filter(ExternalPOSWebhookEvent.processing_status == status)

    if start_date:
        query = query.filter(ExternalPOSWebhookEvent.created_at >= start_date)

    if end_date:
        query = query.filter(ExternalPOSWebhookEvent.created_at <= end_date)

    events = (
        query.order_by(ExternalPOSWebhookEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        WebhookEventResponse(
            id=event.id,
            event_id=str(event.event_id),
            provider_code=event.provider.provider_code,
            event_type=event.event_type,
            event_timestamp=event.event_timestamp,
            processing_status=event.processing_status,
            is_verified=event.is_verified,
            processing_attempts=event.processing_attempts,
            last_error=event.last_error,
            created_at=event.created_at,
            processed_at=event.processed_at,
        )
        for event in events
    ]


@router.get("/events/{event_id}", response_model=WebhookEventDetailResponse)
async def get_webhook_event_detail(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user),
) -> WebhookEventDetailResponse:
    """Get detailed information about a webhook event"""

    check_permission(current_user, "webhooks", "read")

    event = (
        db.query(ExternalPOSWebhookEvent)
        .filter(ExternalPOSWebhookEvent.id == event_id)
        .first()
    )

    if not event:
        raise HTTPException(status_code=404, detail="Webhook event not found")

    # Get payment updates
    payment_updates = (
        db.query(ExternalPOSPaymentUpdate)
        .filter(ExternalPOSPaymentUpdate.webhook_event_id == event_id)
        .all()
    )

    return WebhookEventDetailResponse(
        id=event.id,
        event_id=str(event.event_id),
        provider_code=event.provider.provider_code,
        event_type=event.event_type,
        event_timestamp=event.event_timestamp,
        request_headers=event.request_headers,
        request_body=event.request_body,
        processing_status=event.processing_status,
        is_verified=event.is_verified,
        verification_details=event.verification_details,
        processing_attempts=event.processing_attempts,
        last_error=event.last_error,
        created_at=event.created_at,
        processed_at=event.processed_at,
        payment_updates=payment_updates,
    )


@router.get("/events/{event_id}/logs", response_model=List[WebhookLogResponse])
async def get_webhook_event_logs(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user),
) -> List[WebhookLogResponse]:
    """Get processing logs for a webhook event"""

    check_permission(current_user, "webhooks", "read")

    logs = (
        db.query(ExternalPOSWebhookLog)
        .filter(ExternalPOSWebhookLog.webhook_event_id == event_id)
        .order_by(ExternalPOSWebhookLog.occurred_at.desc())
        .all()
    )

    return [
        WebhookLogResponse(
            id=log.id,
            webhook_event_id=log.webhook_event_id,
            log_level=log.log_level,
            log_type=log.log_type,
            message=log.message,
            details=log.details,
            occurred_at=log.occurred_at,
        )
        for log in logs
    ]


@router.post("/retry-failed")
async def retry_failed_webhooks(
    limit: int = Query(
        settings.WEBHOOK_RECENT_EVENTS_LIMIT, ge=1, le=settings.WEBHOOK_RETRY_API_LIMIT
    ),
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user),
):
    """Manually trigger retry of failed webhooks"""

    check_permission(current_user, "webhooks", "update")

    service = ExternalPOSWebhookService(db)
    processed_count = await service.retry_failed_webhooks(limit=limit)

    return {
        "message": f"Retry initiated for up to {limit} failed webhooks",
        "processed_count": processed_count,
    }


@router.post("/scheduler/trigger")
async def trigger_scheduler(current_user: StaffMember = Depends(get_current_user)):
    """Manually trigger the webhook retry scheduler"""

    check_permission(current_user, "webhooks", "update")

    success = webhook_retry_scheduler.trigger_immediate_retry()

    if success:
        return {"message": "Webhook retry scheduler triggered successfully"}
    else:
        raise HTTPException(
            status_code=500, detail="Failed to trigger webhook retry scheduler"
        )
