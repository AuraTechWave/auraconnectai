# backend/modules/sms/routers/webhook_router.py

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from typing import Optional
from sqlalchemy.orm import Session
import hmac
import hashlib
import base64
import logging

from core.database import get_db
from modules.sms.services.delivery_tracking_service import DeliveryTrackingService
from modules.sms.services.opt_out_service import OptOutService
from modules.sms.models.sms_models import SMSProvider

router = APIRouter(prefix="/api/v1/sms/webhooks", tags=["SMS Webhooks"])
logger = logging.getLogger(__name__)


@router.post("/twilio/status")
async def twilio_status_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_twilio_signature: Optional[str] = Header(None)
):
    """Handle Twilio status callback webhook"""
    try:
        # Get request body
        body = await request.form()
        webhook_data = dict(body)
        
        # Verify Twilio signature (optional but recommended in production)
        # if not verify_twilio_signature(request, x_twilio_signature):
        #     raise HTTPException(status_code=403, detail="Invalid signature")
        
        delivery_service = DeliveryTrackingService(db)
        result = await delivery_service.handle_webhook(SMSProvider.TWILIO, webhook_data)
        
        return {"success": True}
        
    except Exception as e:
        logger.error(f"Error processing Twilio webhook: {str(e)}")
        # Return 200 to prevent Twilio from retrying
        return {"success": False, "error": str(e)}


@router.post("/twilio/inbound")
async def twilio_inbound_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_twilio_signature: Optional[str] = Header(None)
):
    """Handle inbound SMS from Twilio"""
    try:
        # Get request body
        body = await request.form()
        webhook_data = dict(body)
        
        from_number = webhook_data.get('From')
        message_body = webhook_data.get('Body')
        
        if not from_number or not message_body:
            return {"success": False, "error": "Missing required fields"}
        
        # Process for opt-out/opt-in
        opt_out_service = OptOutService(db)
        result = opt_out_service.process_inbound_message(
            phone_number=from_number,
            message_body=message_body
        )
        
        # If action was taken, send response
        response_message = result.get('message')
        if response_message:
            # In production, you would send this response back via Twilio
            logger.info(f"Would send response to {from_number}: {response_message}")
        
        return {"success": True, "action": result.get('action')}
        
    except Exception as e:
        logger.error(f"Error processing inbound SMS: {str(e)}")
        return {"success": False, "error": str(e)}


@router.post("/aws-sns/status")
async def aws_sns_status_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle AWS SNS delivery status webhook"""
    try:
        webhook_data = await request.json()
        
        # AWS SNS sends notifications in a specific format
        if webhook_data.get('Type') == 'SubscriptionConfirmation':
            # Handle subscription confirmation
            return {"message": "Subscription confirmation received"}
        
        if webhook_data.get('Type') == 'Notification':
            message = webhook_data.get('Message')
            # Process the notification
            # AWS SNS specific processing would go here
            
        return {"success": True}
        
    except Exception as e:
        logger.error(f"Error processing AWS SNS webhook: {str(e)}")
        return {"success": False, "error": str(e)}


def verify_twilio_signature(request: Request, signature: str) -> bool:
    """
    Verify Twilio webhook signature
    
    Note: This is a simplified version. In production, you should:
    1. Get the auth token from secure storage
    2. Construct the full URL including protocol and port
    3. Sort the POST parameters alphabetically
    """
    import os
    
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    if not auth_token or not signature:
        return False
    
    # This is a placeholder - implement proper signature verification
    # based on Twilio's security documentation
    return True


@router.get("/health")
async def webhook_health_check():
    """Health check endpoint for webhook service"""
    return {"status": "healthy", "service": "sms_webhooks"}