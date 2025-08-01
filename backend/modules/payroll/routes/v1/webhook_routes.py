# backend/modules/payroll/routes/v1/webhook_routes.py

"""
Webhook management endpoints for payroll events.

Provides endpoints for managing webhook subscriptions and
handling payroll event notifications.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import uuid
import httpx
import hmac
import hashlib
import json

from core.database import get_db
from core.auth import require_payroll_write, get_current_user, User
from ...models.payroll_configuration import PayrollWebhookSubscription
from ...schemas.webhook_schemas import (
    WebhookSubscriptionRequest,
    WebhookSubscriptionResponse,
    WebhookEventType,
    WebhookTestRequest,
    WebhookTestResponse,
    WebhookEventLog
)
from ...schemas.error_schemas import ErrorResponse, PayrollErrorCodes

router = APIRouter()


async def send_webhook_notification(
    webhook_url: str,
    event_type: str,
    payload: dict,
    secret_key: str
):
    """
    Send webhook notification to subscribed URL.
    """
    # Generate signature
    payload_json = json.dumps(payload, sort_keys=True)
    signature = hmac.new(
        secret_key.encode(),
        payload_json.encode(),
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature,
        "X-Webhook-Timestamp": datetime.utcnow().isoformat(),
        "X-Webhook-Event": event_type
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                webhook_url,
                json=payload,
                headers=headers,
                timeout=30.0
            )
            return response.status_code, response.text
        except Exception as e:
            return None, str(e)


@router.post("/subscribe", response_model=WebhookSubscriptionResponse)
async def create_webhook_subscription(
    subscription: WebhookSubscriptionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Create a new webhook subscription for payroll events.
    
    ## Request Body
    - **webhook_url**: URL to receive webhook notifications
    - **event_types**: List of event types to subscribe to
    - **active**: Whether the subscription is active
    - **description**: Optional description
    
    ## Response
    Returns created webhook subscription with secret key.
    
    ## Event Types
    - payroll.started
    - payroll.completed
    - payroll.failed
    - payment.processed
    - payment.failed
    - tax_rule.updated
    - employee.payroll_updated
    """
    try:
        # Validate URL format
        if not subscription.webhook_url.startswith(('http://', 'https://')):
            raise HTTPException(
                status_code=422,
                detail=ErrorResponse(
                    error="ValidationError",
                    message="Webhook URL must start with http:// or https://",
                    code=PayrollErrorCodes.INVALID_DATA_FORMAT
                ).dict()
            )
        
        # Check for duplicate subscription
        existing = db.query(PayrollWebhookSubscription).filter(
            PayrollWebhookSubscription.webhook_url == subscription.webhook_url,
            PayrollWebhookSubscription.is_active == True
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=409,
                detail=ErrorResponse(
                    error="DuplicateError",
                    message="Active webhook subscription already exists for this URL",
                    code=PayrollErrorCodes.DUPLICATE_RECORD
                ).dict()
            )
        
        # Generate secret key
        secret_key = str(uuid.uuid4())
        
        # Create subscription
        webhook_sub = PayrollWebhookSubscription(
            webhook_url=subscription.webhook_url,
            event_types=subscription.event_types,
            secret_key=secret_key,
            description=subscription.description,
            is_active=subscription.active,
            created_by_user_id=current_user.id,
            tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None
        )
        
        db.add(webhook_sub)
        db.commit()
        db.refresh(webhook_sub)
        
        return WebhookSubscriptionResponse(
            id=webhook_sub.id,
            webhook_url=webhook_sub.webhook_url,
            event_types=webhook_sub.event_types,
            secret_key=webhook_sub.secret_key,
            active=webhook_sub.is_active,
            description=webhook_sub.description,
            created_at=webhook_sub.created_at,
            last_triggered_at=webhook_sub.last_triggered_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="WebhookError",
                message=f"Failed to create webhook subscription: {str(e)}",
                code=PayrollErrorCodes.DATABASE_ERROR
            ).dict()
        )


@router.get("/subscriptions", response_model=List[WebhookSubscriptionResponse])
async def list_webhook_subscriptions(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    List all webhook subscriptions.
    
    ## Query Parameters
    - **active_only**: Only return active subscriptions
    
    ## Response
    Returns list of webhook subscriptions.
    """
    query = db.query(PayrollWebhookSubscription)
    
    if active_only:
        query = query.filter(PayrollWebhookSubscription.is_active == True)
    
    if hasattr(current_user, 'tenant_id'):
        query = query.filter(PayrollWebhookSubscription.tenant_id == current_user.tenant_id)
    
    subscriptions = query.order_by(PayrollWebhookSubscription.created_at.desc()).all()
    
    return [
        WebhookSubscriptionResponse(
            id=sub.id,
            webhook_url=sub.webhook_url,
            event_types=sub.event_types,
            secret_key=sub.secret_key,
            active=sub.is_active,
            description=sub.description,
            created_at=sub.created_at,
            last_triggered_at=sub.last_triggered_at
        )
        for sub in subscriptions
    ]


@router.put("/subscriptions/{subscription_id}")
async def update_webhook_subscription(
    subscription_id: int,
    update_request: WebhookSubscriptionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Update an existing webhook subscription.
    
    ## Path Parameters
    - **subscription_id**: ID of subscription to update
    
    ## Request Body
    Same as create subscription request.
    
    ## Response
    Returns updated webhook subscription.
    """
    subscription = db.query(PayrollWebhookSubscription).filter(
        PayrollWebhookSubscription.id == subscription_id
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="NotFound",
                message=f"Webhook subscription {subscription_id} not found",
                code=PayrollErrorCodes.RECORD_NOT_FOUND
            ).dict()
        )
    
    # Update fields
    subscription.webhook_url = update_request.webhook_url
    subscription.event_types = update_request.event_types
    subscription.is_active = update_request.active
    subscription.description = update_request.description
    subscription.updated_at = datetime.utcnow()
    
    try:
        db.commit()
        return {
            "id": subscription.id,
            "webhook_url": subscription.webhook_url,
            "event_types": subscription.event_types,
            "active": subscription.is_active,
            "updated_at": subscription.updated_at.isoformat()
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="UpdateError",
                message="Failed to update webhook subscription",
                code=PayrollErrorCodes.DATABASE_ERROR
            ).dict()
        )


@router.delete("/subscriptions/{subscription_id}")
async def delete_webhook_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Delete a webhook subscription.
    
    ## Path Parameters
    - **subscription_id**: ID of subscription to delete
    
    ## Response
    Returns confirmation of deletion.
    """
    subscription = db.query(PayrollWebhookSubscription).filter(
        PayrollWebhookSubscription.id == subscription_id
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="NotFound",
                message=f"Webhook subscription {subscription_id} not found",
                code=PayrollErrorCodes.RECORD_NOT_FOUND
            ).dict()
        )
    
    try:
        db.delete(subscription)
        db.commit()
        return {
            "message": "Webhook subscription deleted successfully",
            "subscription_id": subscription_id
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="DeleteError",
                message="Failed to delete webhook subscription",
                code=PayrollErrorCodes.DATABASE_ERROR
            ).dict()
        )


@router.post("/test", response_model=WebhookTestResponse)
async def test_webhook(
    test_request: WebhookTestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Test a webhook subscription with sample data.
    
    ## Request Body
    - **subscription_id**: ID of subscription to test
    - **event_type**: Event type to simulate
    
    ## Response
    Returns test status and queued notification.
    """
    subscription = db.query(PayrollWebhookSubscription).filter(
        PayrollWebhookSubscription.id == test_request.subscription_id
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="NotFound",
                message=f"Webhook subscription {test_request.subscription_id} not found",
                code=PayrollErrorCodes.RECORD_NOT_FOUND
            ).dict()
        )
    
    if test_request.event_type not in subscription.event_types:
        raise HTTPException(
            status_code=422,
            detail=ErrorResponse(
                error="ValidationError",
                message=f"Event type {test_request.event_type} not in subscription",
                code=PayrollErrorCodes.INVALID_DATA_FORMAT
            ).dict()
        )
    
    # Create test payload
    test_payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": test_request.event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "test": True,
        "data": {
            "message": "This is a test webhook notification",
            "subscription_id": subscription.id,
            "triggered_by": current_user.email
        }
    }
    
    # Queue webhook notification
    background_tasks.add_task(
        send_webhook_notification,
        subscription.webhook_url,
        test_request.event_type,
        test_payload,
        subscription.secret_key
    )
    
    return WebhookTestResponse(
        test_id=test_payload["event_id"],
        subscription_id=subscription.id,
        webhook_url=subscription.webhook_url,
        event_type=test_request.event_type,
        status="queued",
        test_payload=test_payload
    )


@router.get("/events/{subscription_id}/logs")
async def get_webhook_event_logs(
    subscription_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Get event logs for a webhook subscription.
    
    ## Path Parameters
    - **subscription_id**: ID of subscription
    
    ## Query Parameters
    - **limit**: Maximum number of logs to return
    
    ## Response
    Returns list of webhook event logs.
    """
    subscription = db.query(PayrollWebhookSubscription).filter(
        PayrollWebhookSubscription.id == subscription_id
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="NotFound",
                message=f"Webhook subscription {subscription_id} not found",
                code=PayrollErrorCodes.RECORD_NOT_FOUND
            ).dict()
        )
    
    # In a real implementation, fetch from webhook_event_logs table
    # For now, return mock data
    return {
        "subscription_id": subscription_id,
        "total_events": 0,
        "successful_events": 0,
        "failed_events": 0,
        "events": []
    }