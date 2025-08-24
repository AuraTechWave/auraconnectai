# backend/modules/email/routers/email_router.py

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import get_current_user
from core.permissions import check_permission
from modules.auth.models.user_models import User
from modules.email.services.email_service import EmailService
from modules.email.services.template_service import EmailTemplateService
from modules.email.services.unsubscribe_service import UnsubscribeService
from modules.email.services.sendgrid_service import SendGridService
from modules.email.services.ses_service import SESService
from modules.email.schemas.email_schemas import (
    EmailSendRequest,
    EmailBulkSendRequest,
    EmailMessageResponse,
    EmailTemplateCreate,
    EmailTemplateUpdate,
    EmailTemplateResponse,
    EmailStatusUpdate,
    EmailUnsubscribeRequest,
    EmailStatistics
)
from modules.email.models.email_models import (
    EmailStatus, EmailTemplateCategory, EmailProvider
)

router = APIRouter(prefix="/api/v1/email", tags=["email"])


@router.post("/send", response_model=EmailMessageResponse)
async def send_email(
    request: EmailSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send a single email"""
    check_permission(current_user, "email:send")
    
    email_service = EmailService(db)
    
    try:
        message = await email_service.send_email(request, current_user.id)
        return EmailMessageResponse.model_validate(message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")


@router.post("/send-bulk", response_model=List[EmailMessageResponse])
async def send_bulk_email(
    request: EmailBulkSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send bulk emails"""
    check_permission(current_user, "email:send_bulk")
    
    email_service = EmailService(db)
    
    try:
        messages = await email_service.send_bulk_email(request, current_user.id)
        return [EmailMessageResponse.model_validate(msg) for msg in messages]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send bulk emails: {str(e)}")


@router.get("/messages", response_model=List[EmailMessageResponse])
async def get_email_history(
    customer_id: Optional[int] = Query(None),
    email_address: Optional[str] = Query(None),
    status: Optional[EmailStatus] = Query(None),
    category: Optional[EmailTemplateCategory] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get email message history"""
    check_permission(current_user, "email:read")
    
    email_service = EmailService(db)
    
    messages = email_service.get_message_history(
        customer_id=customer_id,
        email_address=email_address,
        start_date=start_date,
        end_date=end_date,
        status=status,
        category=category,
        limit=limit,
        offset=offset
    )
    
    return [EmailMessageResponse.model_validate(msg) for msg in messages]


@router.get("/messages/{message_id}", response_model=EmailMessageResponse)
async def get_email_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific email message"""
    check_permission(current_user, "email:read")
    
    message = db.query(EmailMessage).filter(EmailMessage.id == message_id).first()
    
    if not message:
        raise HTTPException(status_code=404, detail="Email message not found")
    
    return EmailMessageResponse.model_validate(message)


@router.get("/statistics", response_model=EmailStatistics)
async def get_email_statistics(
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    category: Optional[EmailTemplateCategory] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get email statistics for a date range"""
    check_permission(current_user, "email:analytics")
    
    email_service = EmailService(db)
    
    stats = email_service.get_email_statistics(start_date, end_date, category)
    
    return EmailStatistics(**stats)


# Template endpoints
@router.post("/templates", response_model=EmailTemplateResponse)
async def create_template(
    template: EmailTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new email template"""
    check_permission(current_user, "email:template_manage")
    
    template_service = EmailTemplateService(db)
    
    try:
        created_template = template_service.create_template(template, current_user.id)
        return EmailTemplateResponse.model_validate(created_template)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/templates", response_model=List[EmailTemplateResponse])
async def list_templates(
    category: Optional[EmailTemplateCategory] = Query(None),
    is_active: Optional[bool] = Query(None),
    is_transactional: Optional[bool] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List email templates"""
    check_permission(current_user, "email:template_read")
    
    template_service = EmailTemplateService(db)
    
    templates = template_service.list_templates(
        category=category,
        is_active=is_active,
        is_transactional=is_transactional,
        limit=limit,
        offset=offset
    )
    
    return [EmailTemplateResponse.model_validate(t) for t in templates]


@router.get("/templates/{template_id}", response_model=EmailTemplateResponse)
async def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific email template"""
    check_permission(current_user, "email:template_read")
    
    template_service = EmailTemplateService(db)
    template = template_service.get_template(template_id)
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return EmailTemplateResponse.model_validate(template)


@router.put("/templates/{template_id}", response_model=EmailTemplateResponse)
async def update_template(
    template_id: int,
    template_update: EmailTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an email template"""
    check_permission(current_user, "email:template_manage")
    
    template_service = EmailTemplateService(db)
    
    try:
        updated_template = template_service.update_template(
            template_id, template_update, current_user.id
        )
        return EmailTemplateResponse.model_validate(updated_template)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete (deactivate) an email template"""
    check_permission(current_user, "email:template_manage")
    
    template_service = EmailTemplateService(db)
    
    if not template_service.delete_template(template_id):
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {"message": "Template deactivated successfully"}


# Unsubscribe endpoints
@router.post("/unsubscribe")
async def unsubscribe(
    request: EmailUnsubscribeRequest,
    db: Session = Depends(get_db)
):
    """Process unsubscribe request"""
    unsubscribe_service = UnsubscribeService(db)
    
    try:
        unsubscribe_service.unsubscribe(request)
        return {"message": "Successfully unsubscribed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to unsubscribe: {str(e)}")


@router.get("/unsubscribe")
async def unsubscribe_via_link(
    email: str = Query(...),
    token: str = Query(...),
    categories: Optional[List[EmailTemplateCategory]] = Query(None),
    db: Session = Depends(get_db)
):
    """Process unsubscribe via email link"""
    unsubscribe_service = UnsubscribeService(db)
    
    if not unsubscribe_service.process_unsubscribe_link(email, token, categories):
        raise HTTPException(status_code=400, detail="Invalid unsubscribe link")
    
    # Return a simple HTML page
    return {
        "message": "You have been successfully unsubscribed",
        "email": email,
        "categories": [cat.value for cat in categories] if categories else ["all"]
    }


@router.post("/resubscribe")
async def resubscribe(
    email: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Resubscribe an email address"""
    check_permission(current_user, "email:unsubscribe_manage")
    
    unsubscribe_service = UnsubscribeService(db)
    
    if not unsubscribe_service.resubscribe(email):
        raise HTTPException(status_code=404, detail="No unsubscribe record found")
    
    return {"message": "Successfully resubscribed"}


# Webhook endpoints
@router.post("/webhooks/sendgrid")
async def sendgrid_webhook(
    events: List[Dict[str, Any]],
    db: Session = Depends(get_db)
):
    """Process SendGrid webhook events"""
    sendgrid_service = SendGridService()
    email_service = EmailService(db)
    
    # TODO: Verify webhook signature
    
    for event in events:
        parsed_event = sendgrid_service.parse_webhook_event(event)
        
        if parsed_event.get('provider_message_id'):
            email_service.update_message_status(
                provider_message_id=parsed_event['provider_message_id'],
                status=parsed_event['status'],
                delivered_at=parsed_event.get('timestamp') if parsed_event['event_type'] == 'delivered' else None,
                opened_at=parsed_event.get('timestamp') if parsed_event['event_type'] == 'open' else None,
                clicked_at=parsed_event.get('timestamp') if parsed_event['event_type'] == 'click' else None,
                bounced_at=parsed_event.get('timestamp') if parsed_event['event_type'] == 'bounce' else None,
                complained_at=parsed_event.get('timestamp') if parsed_event['event_type'] == 'spamreport' else None,
                error_message=parsed_event.get('reason')
            )
    
    return {"status": "ok"}


@router.post("/webhooks/ses")
async def ses_webhook(
    message: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """Process AWS SES webhook events (via SNS)"""
    ses_service = SESService()
    email_service = EmailService(db)
    
    # Handle SNS subscription confirmation
    if message.get('Type') == 'SubscriptionConfirmation':
        # TODO: Confirm SNS subscription
        return {"status": "subscription confirmation needed"}
    
    # Parse and process event
    parsed_event = ses_service.parse_webhook_event(message)
    
    if parsed_event.get('provider_message_id'):
        email_service.update_message_status(
            provider_message_id=parsed_event['provider_message_id'],
            status=parsed_event['status'],
            delivered_at=parsed_event.get('delivered_at'),
            opened_at=parsed_event.get('timestamp') if parsed_event['event_type'] == 'open' else None,
            clicked_at=parsed_event.get('timestamp') if parsed_event['event_type'] == 'click' else None,
            bounced_at=parsed_event.get('timestamp') if parsed_event['event_type'] == 'bounce' else None,
            complained_at=parsed_event.get('timestamp') if parsed_event['event_type'] == 'complaint' else None,
            error_message=parsed_event.get('diagnostic_code')
        )
    
    return {"status": "ok"}


# Health check
@router.get("/health")
async def email_health_check(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check email service health"""
    check_permission(current_user, "email:analytics")
    
    from modules.email.services.tracking_service import EmailTrackingService
    tracking_service = EmailTrackingService(db)
    
    health_score = tracking_service.get_email_health_score()
    
    return health_score