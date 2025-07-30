# backend/modules/orders/routers/external_pos_webhook_router.py

"""
Router for handling incoming webhooks from external POS systems.

Supports webhooks from Square, Stripe, Toast, and other payment providers
for payment updates on orders paid externally.
"""

from fastapi import APIRouter, Request, Response, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import logging
import json
import uuid
from datetime import datetime

from backend.core.database import get_db
from backend.core.config import settings
from backend.modules.orders.services.webhook_auth_service import WebhookAuthService
from backend.modules.orders.services.external_pos_webhook_service import ExternalPOSWebhookService
from backend.modules.orders.models.external_pos_models import (
    ExternalPOSWebhookEvent, ExternalPOSProvider
)
from backend.modules.orders.enums.external_pos_enums import (
    WebhookProcessingStatus, ExternalPOSProvider as POSProviderEnum
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/external-pos", tags=["External POS Webhooks"])


@router.post("/{provider_code}/events")
async def receive_external_pos_webhook(
    provider_code: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Receive webhook events from external POS providers.
    
    This endpoint handles incoming webhooks for payment updates from:
    - Square
    - Stripe
    - Toast
    - Clover
    - Other configured providers
    """
    event_id = str(uuid.uuid4())
    
    try:
        # Get request data
        body = await request.body()
        headers = dict(request.headers)
        
        # Log incoming webhook
        logger.info(
            f"Received webhook from {provider_code}",
            extra={
                "event_id": event_id,
                "provider": provider_code,
                "headers": {k: v for k, v in headers.items() if not k.lower().startswith('authorization')}
            }
        )
        
        # Verify provider exists and is active
        provider = db.query(ExternalPOSProvider).filter(
            ExternalPOSProvider.provider_code == provider_code,
            ExternalPOSProvider.is_active == True
        ).first()
        
        if not provider:
            logger.warning(f"Unknown provider: {provider_code}")
            raise HTTPException(
                status_code=404,
                detail=f"Provider {provider_code} not found or inactive"
            )
        
        # Parse body
        try:
            body_json = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON body from {provider_code}")
            raise HTTPException(
                status_code=400,
                detail="Invalid JSON in request body"
            )
        
        # Create webhook event record
        webhook_event = ExternalPOSWebhookEvent(
            event_id=uuid.UUID(event_id),
            provider_id=provider.id,
            event_type=_extract_event_type(provider_code, body_json),
            event_timestamp=_extract_event_timestamp(provider_code, body_json),
            request_headers=headers,
            request_body=body_json,
            request_signature=_extract_signature(headers, provider_code),
            processing_status=WebhookProcessingStatus.PENDING
        )
        
        db.add(webhook_event)
        db.commit()
        db.refresh(webhook_event)
        
        # Verify webhook authenticity
        auth_service = WebhookAuthService(db)
        is_valid, error_msg, verification_details = await auth_service.verify_webhook_request(
            provider_code=provider_code,
            headers=headers,
            body=body,
            request_signature=webhook_event.request_signature
        )
        
        webhook_event.is_verified = is_valid
        webhook_event.verification_details = verification_details
        
        if not is_valid:
            webhook_event.processing_status = WebhookProcessingStatus.FAILED
            webhook_event.last_error = f"Authentication failed: {error_msg}"
            db.commit()
            
            logger.warning(
                f"Webhook authentication failed for {provider_code}: {error_msg}",
                extra={"event_id": event_id}
            )
            
            # Still return 200 to prevent retries from provider
            return {
                "status": "received",
                "event_id": event_id,
                "message": "Authentication failed"
            }
        
        # Process webhook asynchronously
        background_tasks.add_task(
            _process_webhook_async,
            webhook_event_id=webhook_event.id,
            provider_code=provider_code
        )
        
        # Return success immediately
        return {
            "status": "accepted",
            "event_id": event_id,
            "message": "Webhook received and queued for processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error receiving webhook from {provider_code}: {str(e)}",
            extra={"event_id": event_id},
            exc_info=True
        )
        # Return 200 to prevent retries, but log the error
        return {
            "status": "error",
            "event_id": event_id,
            "message": "Internal error occurred"
        }


@router.get("/{provider_code}/status")
async def get_provider_webhook_status(
    provider_code: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get webhook configuration status for a provider"""
    provider = db.query(ExternalPOSProvider).filter(
        ExternalPOSProvider.provider_code == provider_code
    ).first()
    
    if not provider:
        raise HTTPException(
            status_code=404,
            detail=f"Provider {provider_code} not found"
        )
    
    # Get recent webhook stats
    recent_webhooks = db.query(ExternalPOSWebhookEvent).filter(
        ExternalPOSWebhookEvent.provider_id == provider.id
    ).order_by(
        ExternalPOSWebhookEvent.created_at.desc()
    ).limit(10).all()
    
    return {
        "provider": {
            "code": provider.provider_code,
            "name": provider.provider_name,
            "is_active": provider.is_active,
            "webhook_endpoint": f"/api/webhooks/external-pos/{provider.provider_code}/events"
        },
        "recent_webhooks": [
            {
                "event_id": str(webhook.event_id),
                "event_type": webhook.event_type,
                "status": webhook.processing_status,
                "is_verified": webhook.is_verified,
                "created_at": webhook.created_at.isoformat()
            }
            for webhook in recent_webhooks
        ]
    }


@router.post("/{provider_code}/test")
async def test_webhook_endpoint(
    provider_code: str,
    test_data: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Test webhook endpoint with sample data"""
    provider = db.query(ExternalPOSProvider).filter(
        ExternalPOSProvider.provider_code == provider_code
    ).first()
    
    if not provider:
        raise HTTPException(
            status_code=404,
            detail=f"Provider {provider_code} not found"
        )
    
    # Generate test webhook data
    if not test_data:
        test_data = _generate_test_webhook_data(provider_code)
    
    # Generate authentication headers
    auth_service = WebhookAuthService(db)
    auth_headers = auth_service.generate_test_signature(
        provider_code=provider_code,
        body=test_data
    )
    
    if not auth_headers:
        raise HTTPException(
            status_code=400,
            detail="Could not generate test authentication"
        )
    
    return {
        "status": "test_data_generated",
        "webhook_url": f"{settings.BASE_URL}/api/webhooks/external-pos/{provider_code}/events",
        "headers": auth_headers,
        "body": test_data,
        "instructions": "Send a POST request to the webhook_url with the provided headers and body"
    }


# Utility functions

def _extract_event_type(provider_code: str, body: Dict[str, Any]) -> str:
    """Extract event type from webhook payload based on provider"""
    if provider_code == POSProviderEnum.SQUARE:
        return body.get("type", "unknown")
    elif provider_code == POSProviderEnum.STRIPE:
        return body.get("type", "unknown")
    elif provider_code == POSProviderEnum.TOAST:
        return body.get("eventType", "unknown")
    else:
        # Generic fallback
        return body.get("event_type") or body.get("type") or "unknown"


def _extract_event_timestamp(provider_code: str, body: Dict[str, Any]) -> datetime:
    """Extract event timestamp from webhook payload"""
    timestamp_str = None
    
    if provider_code == POSProviderEnum.SQUARE:
        timestamp_str = body.get("created_at")
    elif provider_code == POSProviderEnum.STRIPE:
        # Stripe uses Unix timestamp
        timestamp_int = body.get("created")
        if timestamp_int:
            return datetime.fromtimestamp(timestamp_int)
    elif provider_code == POSProviderEnum.TOAST:
        timestamp_str = body.get("timestamp")
    else:
        timestamp_str = body.get("timestamp") or body.get("created_at")
    
    if timestamp_str:
        try:
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except:
            pass
    
    # Fallback to current time
    return datetime.utcnow()


def _extract_signature(headers: Dict[str, str], provider_code: str) -> Optional[str]:
    """Extract signature from headers based on provider"""
    if provider_code == POSProviderEnum.SQUARE:
        return headers.get("x-square-signature", "")
    elif provider_code == POSProviderEnum.STRIPE:
        return headers.get("stripe-signature", "")
    elif provider_code == POSProviderEnum.TOAST:
        return headers.get("x-toast-signature", "")
    else:
        # Try common signature headers
        return (
            headers.get("x-webhook-signature") or
            headers.get("x-signature") or
            headers.get("x-hub-signature-256") or
            ""
        )


async def _process_webhook_async(webhook_event_id: int, provider_code: str):
    """Process webhook asynchronously"""
    db = next(get_db())
    try:
        service = ExternalPOSWebhookService(db)
        await service.process_webhook_event(webhook_event_id)
    except Exception as e:
        logger.error(
            f"Error processing webhook {webhook_event_id}: {str(e)}",
            exc_info=True
        )
    finally:
        db.close()


def _generate_test_webhook_data(provider_code: str) -> Dict[str, Any]:
    """Generate test webhook data for different providers"""
    if provider_code == POSProviderEnum.SQUARE:
        return {
            "merchant_id": "TEST_MERCHANT",
            "type": "payment.updated",
            "event_id": str(uuid.uuid4()),
            "created_at": datetime.utcnow().isoformat() + "Z",
            "data": {
                "type": "payment",
                "id": "TEST_PAYMENT_ID",
                "object": {
                    "payment": {
                        "id": "TEST_PAYMENT_ID",
                        "amount_money": {
                            "amount": 1000,
                            "currency": "USD"
                        },
                        "status": "COMPLETED",
                        "order_id": "TEST_ORDER_ID"
                    }
                }
            }
        }
    elif provider_code == POSProviderEnum.STRIPE:
        return {
            "id": f"evt_{uuid.uuid4().hex[:24]}",
            "object": "event",
            "api_version": "2023-10-16",
            "created": int(datetime.utcnow().timestamp()),
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": f"pi_{uuid.uuid4().hex[:24]}",
                    "object": "payment_intent",
                    "amount": 1000,
                    "currency": "usd",
                    "status": "succeeded",
                    "metadata": {
                        "order_id": "TEST_ORDER_123"
                    }
                }
            }
        }
    else:
        # Generic test data
        return {
            "event_id": str(uuid.uuid4()),
            "event_type": "payment.completed",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "payment_id": "TEST_PAYMENT_ID",
                "order_id": "TEST_ORDER_123",
                "amount": 10.00,
                "currency": "USD",
                "status": "completed"
            }
        }