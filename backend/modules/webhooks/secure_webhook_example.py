"""
Example of secure webhook implementation with signature validation.

This module demonstrates how to properly implement webhook endpoints
with signature validation and audit logging.
"""

from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import json

from core.webhook_security import webhook_validator, WebhookRequest
from core.audit_logger import audit_logger
from core.auth import get_current_user_optional

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


class SquareWebhookPayload(WebhookRequest):
    """Square webhook payload model."""
    type: str
    event_id: str
    created_at: str
    data: Dict[str, Any]
    
    
class ToastWebhookPayload(WebhookRequest):
    """Toast webhook payload model."""
    eventType: str
    guid: str
    timestamp: str
    eventData: Dict[str, Any]


@router.post("/square")
async def handle_square_webhook(request: Request):
    """
    Handle Square webhook with signature validation.
    
    This endpoint validates the webhook signature before processing.
    """
    # Read body
    body = await request.body()
    
    # Validate signature
    await webhook_validator.validate_signature(
        request=request,
        source="square",
        body=body,
        signature_header="X-Square-Signature",
        timestamp_header="X-Square-Timestamp"
    )
    
    # Parse and validate payload
    try:
        payload = SquareWebhookPayload(**json.loads(body))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {str(e)}")
    
    # Log webhook receipt
    await audit_logger.log_operation_start(
        operation_type="webhook_received",
        client_ip=request.client.host if request.client else "unknown",
        request_id=payload.event_id,
        metadata={
            "source": "square",
            "event_type": payload.type,
            "event_id": payload.event_id
        }
    )
    
    # Process webhook based on type
    try:
        if payload.type == "payment.created":
            await process_square_payment(payload.data)
        elif payload.type == "order.updated":
            await process_square_order_update(payload.data)
        else:
            # Log unhandled webhook type
            await audit_logger.log_operation_complete(
                operation_type="webhook_received",
                request_id=payload.event_id,
                status_code=200,
                duration_ms=0
            )
            return {"status": "ignored", "reason": "Unhandled event type"}
        
        # Log successful processing
        await audit_logger.log_operation_complete(
            operation_type="webhook_received",
            request_id=payload.event_id,
            status_code=200,
            duration_ms=0  # Add actual timing
        )
        
        return {"status": "success"}
        
    except Exception as e:
        # Log failure
        await audit_logger.log_operation_failure(
            operation_type="webhook_received",
            request_id=payload.event_id,
            error=str(e),
            duration_ms=0
        )
        raise HTTPException(status_code=500, detail="Failed to process webhook")


@router.post("/toast")
async def handle_toast_webhook(request: Request):
    """
    Handle Toast webhook with signature validation.
    
    Uses the WebhookRequest helper for validation and parsing.
    """
    # Validate and parse in one step
    payload = await ToastWebhookPayload.validate_and_parse(
        request=request,
        source="toast",
        validator=webhook_validator
    )
    
    # Process webhook
    try:
        if payload.eventType == "ORDER_MODIFIED":
            await process_toast_order(payload.eventData)
        elif payload.eventType == "PAYMENT_UPDATED":
            await process_toast_payment(payload.eventData)
        
        return {"status": "success"}
        
    except Exception as e:
        # Log error
        await audit_logger.log_security_event(
            event_type="webhook_processing_error",
            severity="high",
            description=f"Failed to process Toast webhook: {str(e)}",
            metadata={"event_id": payload.guid, "event_type": payload.eventType}
        )
        raise


@router.post("/configure/{source}")
async def configure_webhook_secret(
    source: str,
    secret: str,
    current_user = Depends(get_current_user_optional)
):
    """
    Configure webhook secret for a specific source.
    
    Requires admin authentication.
    """
    # Check admin permission
    if not current_user or "admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Validate source
    valid_sources = ["square", "toast", "clover", "stripe", "twilio"]
    if source.lower() not in valid_sources:
        raise HTTPException(status_code=400, detail="Invalid webhook source")
    
    # Register secret
    webhook_validator.register_webhook_secret(source, secret)
    
    # Log configuration change
    await audit_logger.log_operation_start(
        operation_type="webhook_config_change",
        user_id=current_user.id,
        metadata={"source": source, "action": "secret_updated"}
    )
    
    return {"status": "success", "source": source}


# Webhook processing functions
async def process_square_payment(data: Dict[str, Any]):
    """Process Square payment webhook."""
    # Implementation would go here
    pass


async def process_square_order_update(data: Dict[str, Any]):
    """Process Square order update webhook."""
    # Implementation would go here
    pass


async def process_toast_order(data: Dict[str, Any]):
    """Process Toast order webhook."""
    # Implementation would go here
    pass


async def process_toast_payment(data: Dict[str, Any]):
    """Process Toast payment webhook."""
    # Implementation would go here
    pass