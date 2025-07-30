# backend/modules/orders/routers/webhook/events_router.py

"""
Router for receiving webhook events from external POS systems.
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
from backend.modules.orders.utils.security_utils import mask_headers, mask_sensitive_dict
from backend.modules.orders.enums.external_pos_enums import (
    WebhookProcessingStatus, ExternalPOSProvider as POSProviderEnum,
    SquareEventType, StripeEventType, ToastEventType, CloverEventType,
    ExternalPOSEventType, PROVIDER_EVENT_MAPPING
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/external-pos", tags=["External POS Webhooks"])


@router.post("/{provider_code}/events")
async def receive_webhook_event(
    provider_code: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
) -> Response:
    """
    Receive webhook events from external POS systems.
    
    This endpoint receives webhook events from various POS providers like
    Square, Stripe, Toast, etc. It verifies the webhook signature and
    processes payment updates asynchronously.
    """
    
    # Get provider configuration
    provider = db.query(ExternalPOSProvider).filter(
        ExternalPOSProvider.provider_code == provider_code,
        ExternalPOSProvider.is_active == True
    ).first()
    
    if not provider:
        logger.warning(f"Webhook received for unknown/inactive provider: {provider_code}")
        raise HTTPException(
            status_code=404,
            detail=f"Provider {provider_code} not found or inactive"
        )
    
    # Extract request data
    body = await request.body()
    headers = dict(request.headers)
    
    # Generate unique event ID
    event_id = headers.get("x-webhook-event-id") or str(uuid.uuid4())
    
    logger.info(
        f"Received webhook from {provider_code}",
        extra={
            "provider": provider_code,
            "event_id": event_id,
            "headers": mask_headers(headers)
        }
    )
    
    try:
        # Parse request body
        try:
            body_json = json.loads(body.decode())
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from {provider_code} webhook")
            raise HTTPException(
                status_code=400,
                detail="Invalid JSON in request body"
            )
        
        # Create webhook event record with masked headers for storage
        webhook_event = ExternalPOSWebhookEvent(
            event_id=uuid.UUID(event_id),
            provider_id=provider.id,
            event_type=_extract_event_type(provider_code, body_json),
            event_timestamp=_extract_event_timestamp(provider_code, body_json),
            request_headers=mask_headers(headers),  # Store masked headers for security
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
            
            # Return 401 for auth failures
            raise HTTPException(
                status_code=401,
                detail=f"Webhook authentication failed: {error_msg}"
            )
        
        # Process webhook asynchronously
        background_tasks.add_task(
            process_webhook_async,
            webhook_event_id=webhook_event.id
        )
        
        # Return success immediately
        return Response(
            content=json.dumps({"status": "accepted", "event_id": str(event_id)}),
            status_code=200,
            media_type="application/json"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error processing webhook from {provider_code}: {str(e)}",
            extra={
                "event_id": event_id,
                "provider": provider_code
            },
            exc_info=True
        )
        
        # Return 500 for unexpected errors
        raise HTTPException(
            status_code=500,
            detail="Internal server error processing webhook"
        )


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
    ).limit(settings.WEBHOOK_RECENT_EVENTS_LIMIT).all()
    
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
    
    # Generate test signature
    auth_service = WebhookAuthService(db)
    test_headers = auth_service.generate_test_signature(
        provider_code=provider_code,
        body=test_data
    )
    
    if not test_headers:
        return {
            "error": "Could not generate test signature",
            "provider": provider_code
        }
    
    return {
        "message": "Test webhook data generated",
        "provider": provider_code,
        "test_endpoint": f"/api/webhooks/external-pos/{provider_code}/events",
        "test_headers": test_headers,
        "test_body": test_data
    }


# Helper functions
async def process_webhook_async(webhook_event_id: int):
    """Process webhook asynchronously"""
    db = next(get_db())
    try:
        service = ExternalPOSWebhookService(db)
        await service.process_webhook_event(webhook_event_id)
    except Exception as e:
        logger.error(
            f"Error in async webhook processing: {str(e)}",
            extra={"webhook_event_id": webhook_event_id},
            exc_info=True
        )
    finally:
        db.close()


def _extract_event_type(provider_code: str, body: Dict[str, Any]) -> str:
    """Extract event type from webhook body based on provider"""
    if provider_code == POSProviderEnum.SQUARE:
        raw_type = body.get("type", "unknown")
        # Map to generic event type if mapping exists
        if provider_code in PROVIDER_EVENT_MAPPING:
            for provider_event, generic_event in PROVIDER_EVENT_MAPPING[provider_code].items():
                if provider_event.value == raw_type:
                    return generic_event.value
        return raw_type
    elif provider_code == POSProviderEnum.STRIPE:
        raw_type = body.get("type", "unknown")
        if provider_code in PROVIDER_EVENT_MAPPING:
            for provider_event, generic_event in PROVIDER_EVENT_MAPPING[provider_code].items():
                if provider_event.value == raw_type:
                    return generic_event.value
        return raw_type
    else:
        return body.get("event_type", body.get("type", "unknown"))


def _extract_event_timestamp(provider_code: str, body: Dict[str, Any]) -> datetime:
    """Extract event timestamp from webhook body based on provider"""
    if provider_code == POSProviderEnum.SQUARE:
        timestamp_str = body.get("created_at", "")
        if timestamp_str:
            return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    elif provider_code == POSProviderEnum.STRIPE:
        timestamp = body.get("created", 0)
        if timestamp:
            return datetime.fromtimestamp(timestamp)
    else:
        timestamp_str = body.get("timestamp", body.get("created_at", ""))
        if timestamp_str:
            try:
                return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except:
                pass
    
    return datetime.utcnow()


def _extract_signature(headers: Dict[str, str], provider_code: str) -> Optional[str]:
    """Extract webhook signature from headers based on provider"""
    if provider_code == POSProviderEnum.SQUARE:
        return headers.get("x-square-signature", "")
    elif provider_code == POSProviderEnum.STRIPE:
        return headers.get("stripe-signature", "")
    else:
        # Try common signature headers
        for header in ["x-webhook-signature", "x-signature", "x-hub-signature"]:
            if header in headers:
                return headers[header]
    return None


def _generate_test_webhook_data(provider_code: str) -> Dict[str, Any]:
    """Generate test webhook data for different providers"""
    if provider_code == POSProviderEnum.SQUARE:
        return {
            "merchant_id": "TEST_MERCHANT",
            "type": SquareEventType.PAYMENT_UPDATED.value,
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
            "type": StripeEventType.PAYMENT_INTENT_SUCCEEDED.value,
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
            "event_type": ToastEventType.PAYMENT_COMPLETED.value,
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "payment_id": "TEST_PAYMENT_ID",
                "order_id": "TEST_ORDER_123",
                "amount": 10.00,
                "currency": "USD",
                "status": "completed"
            }
        }