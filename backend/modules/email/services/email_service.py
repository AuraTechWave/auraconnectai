# backend/modules/email/services/email_service.py

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from core.config import settings
from modules.email.models.email_models import (
    EmailMessage, EmailTemplate, EmailOptOut, EmailStatus, 
    EmailProvider, EmailDirection, EmailTemplateCategory,
    EmailAttachment, EmailUnsubscribe
)
from modules.email.schemas.email_schemas import (
    EmailSendRequest, EmailBulkSendRequest, EmailAttachmentInfo
)
from modules.email.services.sendgrid_service import SendGridService
from modules.email.services.ses_service import SESService
from modules.email.services.template_service import EmailTemplateService
from modules.email.services.unsubscribe_service import UnsubscribeService
from modules.email.services.tracking_service import EmailTrackingService

logger = logging.getLogger(__name__)


class EmailService:
    """Main service for sending and managing email messages"""
    
    def __init__(self, db: Session):
        self.db = db
        self.template_service = EmailTemplateService(db)
        self.unsubscribe_service = UnsubscribeService(db)
        self.tracking_service = EmailTrackingService(db)
        
        # Initialize providers
        self.sendgrid_service = SendGridService()
        self.ses_service = SESService()
        
        # Default provider
        self.default_provider = EmailProvider(settings.EMAIL_DEFAULT_PROVIDER or "sendgrid")
        
        # Retry settings
        self.max_retry_attempts = 3
        self.retry_delay_minutes = 5
    
    async def send_email(
        self,
        request: EmailSendRequest,
        user_id: Optional[int] = None,
        provider: Optional[EmailProvider] = None
    ) -> EmailMessage:
        """
        Send a single email message
        
        Args:
            request: Email send request data
            user_id: ID of the user sending the message
            provider: Email provider to use (defaults to configured provider)
        
        Returns:
            Created EmailMessage record
        """
        # Check unsubscribe status
        if self.unsubscribe_service.is_unsubscribed(request.to_email):
            logger.warning(f"Cannot send email to {request.to_email} - user unsubscribed")
            raise ValueError("Recipient has unsubscribed from emails")
        
        # Prepare email content
        if request.template_id:
            template_result = self.template_service.render_template(
                request.template_id,
                request.template_variables or {}
            )
            subject = template_result['subject']
            html_body = template_result['html_body']
            text_body = template_result['text_body']
            template = template_result['template']
            
            # Check category-specific unsubscribe
            if self.unsubscribe_service.is_unsubscribed_from_category(
                request.to_email, 
                template.category
            ):
                logger.warning(
                    f"Cannot send {template.category} email to {request.to_email} - "
                    f"user unsubscribed from category"
                )
                raise ValueError(f"Recipient has unsubscribed from {template.category} emails")
        else:
            subject = request.subject
            html_body = request.html_body
            text_body = request.text_body
            template = None
        
        if not subject:
            raise ValueError("Email subject cannot be empty")
        
        if not html_body and not text_body:
            raise ValueError("Email must have either HTML or text content")
        
        # Add unsubscribe link to HTML body
        if html_body and (not template or not template.is_transactional):
            unsubscribe_token = self.unsubscribe_service.generate_token(request.to_email)
            unsubscribe_link = self._get_provider_service(provider).create_unsubscribe_link(
                request.to_email, 
                unsubscribe_token
            )
            html_body = self._add_unsubscribe_link(html_body, unsubscribe_link)
        
        # Create database record
        email_message = EmailMessage(
            provider=provider or self.default_provider,
            direction=EmailDirection.OUTBOUND,
            status=EmailStatus.QUEUED,
            from_email=settings.EMAIL_FROM_ADDRESS,
            from_name=settings.EMAIL_FROM_NAME,
            to_email=request.to_email,
            to_name=request.to_name,
            cc_emails=request.cc_emails,
            bcc_emails=request.bcc_emails,
            reply_to_email=request.reply_to_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            template_id=request.template_id,
            template_variables=request.template_variables,
            customer_id=request.customer_id,
            order_id=request.order_id,
            reservation_id=request.reservation_id,
            tags=request.tags,
            metadata=request.metadata,
            created_by=user_id
        )
        
        self.db.add(email_message)
        self.db.flush()
        
        # Add attachments if provided
        if request.attachments:
            for att_info in request.attachments:
                attachment = EmailAttachment(
                    email_message_id=email_message.id,
                    filename=att_info.filename,
                    content_type=att_info.content_type,
                    content_base64=att_info.content_base64,
                    content_id=att_info.content_id,
                    size_bytes=len(att_info.content_base64) * 3 // 4  # Approximate size
                )
                self.db.add(attachment)
        
        self.db.commit()
        
        # Schedule or send immediately
        if request.schedule_at and request.schedule_at > datetime.utcnow():
            email_message.scheduled_at = request.schedule_at
            self.db.commit()
            logger.info(f"Email scheduled for {request.schedule_at}: ID {email_message.id}")
        else:
            await self._send_message(email_message)
        
        return email_message
    
    async def send_bulk_email(
        self,
        request: EmailBulkSendRequest,
        user_id: Optional[int] = None
    ) -> List[EmailMessage]:
        """
        Send bulk email messages
        
        Args:
            request: Bulk email send request
            user_id: ID of the user sending messages
        
        Returns:
            List of created EmailMessage records
        """
        messages = []
        
        for recipient_request in request.recipients:
            try:
                message = await self.send_email(
                    recipient_request, 
                    user_id, 
                    request.provider
                )
                messages.append(message)
            except Exception as e:
                logger.error(f"Failed to send email to {recipient_request.to_email}: {str(e)}")
                # Continue with other messages
        
        return messages
    
    async def _send_message(self, email_message: EmailMessage) -> None:
        """
        Internal method to send message via provider
        
        Args:
            email_message: Email message to send
        """
        try:
            # Update status to sending
            email_message.status = EmailStatus.SENDING
            self.db.commit()
            
            # Get provider service
            provider_service = self._get_provider_service(email_message.provider)
            
            # Prepare attachments
            attachments = None
            if email_message.attachments:
                attachments = [
                    {
                        'filename': att.filename,
                        'content_type': att.content_type,
                        'content_base64': att.content_base64,
                        'content_id': att.content_id
                    }
                    for att in email_message.attachments
                ]
            
            # Send via provider
            result = provider_service.send_email(
                to_email=email_message.to_email,
                subject=email_message.subject,
                html_body=email_message.html_body,
                text_body=email_message.text_body,
                from_email=email_message.from_email,
                from_name=email_message.from_name,
                to_name=email_message.to_name,
                cc_emails=email_message.cc_emails,
                bcc_emails=email_message.bcc_emails,
                reply_to_email=email_message.reply_to_email,
                template_id=email_message.template.sendgrid_template_id if email_message.template and email_message.provider == EmailProvider.SENDGRID else None,
                template_name=email_message.template.ses_template_name if email_message.template and email_message.provider == EmailProvider.AWS_SES else None,
                template_data=email_message.template_variables,
                attachments=attachments,
                tags=email_message.tags,
                metadata={
                    'message_id': str(email_message.id),
                    **(email_message.metadata or {})
                }
            )
            
            if result['success']:
                email_message.status = result['status']
                email_message.provider_message_id = result['provider_message_id']
                email_message.sent_at = result.get('sent_at', datetime.utcnow())
                email_message.provider_response = result.get('provider_response')
            else:
                email_message.status = EmailStatus.FAILED
                email_message.provider_error = result.get('error')
                email_message.failed_at = datetime.utcnow()
                
                # Schedule retry if applicable
                if email_message.retry_count < self.max_retry_attempts:
                    email_message.retry_count += 1
                    email_message.next_retry_at = datetime.utcnow() + timedelta(
                        minutes=self.retry_delay_minutes * email_message.retry_count
                    )
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error sending email {email_message.id}: {str(e)}")
            email_message.status = EmailStatus.FAILED
            email_message.provider_error = str(e)
            email_message.failed_at = datetime.utcnow()
            self.db.commit()
    
    def _get_provider_service(self, provider: Optional[EmailProvider] = None):
        """Get the appropriate provider service"""
        provider = provider or self.default_provider
        
        if provider == EmailProvider.SENDGRID:
            return self.sendgrid_service
        elif provider == EmailProvider.AWS_SES:
            return self.ses_service
        else:
            raise ValueError(f"Unsupported email provider: {provider}")
    
    def _add_unsubscribe_link(self, html_body: str, unsubscribe_link: str) -> str:
        """Add unsubscribe link to HTML body"""
        # Simple implementation - add to end of body
        unsubscribe_html = f"""
        <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #e0e0e0; text-align: center; font-size: 12px; color: #666;">
            <p>
                Don't want to receive these emails? 
                <a href="{unsubscribe_link}" style="color: #666; text-decoration: underline;">Unsubscribe</a>
            </p>
        </div>
        """
        
        # Insert before closing body tag if present
        if '</body>' in html_body.lower():
            return html_body.replace('</body>', f'{unsubscribe_html}</body>')
        else:
            return html_body + unsubscribe_html
    
    async def retry_failed_messages(self) -> int:
        """
        Retry failed messages that are scheduled for retry
        
        Returns:
            Number of messages retried
        """
        messages_to_retry = self.db.query(EmailMessage).filter(
            and_(
                EmailMessage.status == EmailStatus.FAILED,
                EmailMessage.retry_count < self.max_retry_attempts,
                EmailMessage.next_retry_at <= datetime.utcnow()
            )
        ).all()
        
        count = 0
        for message in messages_to_retry:
            await self._send_message(message)
            count += 1
        
        logger.info(f"Retried {count} failed emails")
        return count
    
    async def process_scheduled_messages(self) -> int:
        """
        Process messages scheduled for sending
        
        Returns:
            Number of messages processed
        """
        scheduled_messages = self.db.query(EmailMessage).filter(
            and_(
                EmailMessage.status == EmailStatus.QUEUED,
                EmailMessage.scheduled_at.isnot(None),
                EmailMessage.scheduled_at <= datetime.utcnow()
            )
        ).all()
        
        count = 0
        for message in scheduled_messages:
            message.scheduled_at = None
            await self._send_message(message)
            count += 1
        
        logger.info(f"Processed {count} scheduled emails")
        return count
    
    def update_message_status(
        self,
        provider_message_id: str,
        status: EmailStatus,
        delivered_at: Optional[datetime] = None,
        opened_at: Optional[datetime] = None,
        clicked_at: Optional[datetime] = None,
        bounced_at: Optional[datetime] = None,
        complained_at: Optional[datetime] = None,
        failed_at: Optional[datetime] = None,
        error_message: Optional[str] = None
    ) -> Optional[EmailMessage]:
        """
        Update message status from webhook callback
        
        Args:
            provider_message_id: Provider's message ID
            status: New status
            Various timestamp fields
            error_message: Error message if failed
        
        Returns:
            Updated EmailMessage or None if not found
        """
        message = self.db.query(EmailMessage).filter(
            EmailMessage.provider_message_id == provider_message_id
        ).first()
        
        if not message:
            logger.warning(f"Email not found for provider ID: {provider_message_id}")
            return None
        
        message.status = status
        
        if delivered_at:
            message.delivered_at = delivered_at
        
        if opened_at and not message.opened_at:  # Only record first open
            message.opened_at = opened_at
        
        if clicked_at and not message.clicked_at:  # Only record first click
            message.clicked_at = clicked_at
        
        if bounced_at:
            message.bounced_at = bounced_at
        
        if complained_at:
            message.complained_at = complained_at
        
        if failed_at:
            message.failed_at = failed_at
        
        if error_message:
            message.provider_error = error_message
        
        self.db.commit()
        logger.info(f"Updated status for email {message.id} to {status}")
        
        return message
    
    def get_message_history(
        self,
        customer_id: Optional[int] = None,
        email_address: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        status: Optional[EmailStatus] = None,
        category: Optional[EmailTemplateCategory] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[EmailMessage]:
        """
        Get email history with filters
        
        Args:
            customer_id: Filter by customer
            email_address: Filter by email address
            start_date: Filter messages after this date
            end_date: Filter messages before this date
            status: Filter by status
            category: Filter by template category
            limit: Maximum number of results
            offset: Pagination offset
        
        Returns:
            List of email messages
        """
        query = self.db.query(EmailMessage)
        
        if customer_id:
            query = query.filter(EmailMessage.customer_id == customer_id)
        
        if email_address:
            query = query.filter(
                or_(
                    EmailMessage.to_email == email_address,
                    EmailMessage.from_email == email_address
                )
            )
        
        if start_date:
            query = query.filter(EmailMessage.created_at >= start_date)
        
        if end_date:
            query = query.filter(EmailMessage.created_at <= end_date)
        
        if status:
            query = query.filter(EmailMessage.status == status)
        
        if category:
            query = query.join(EmailTemplate).filter(
                EmailTemplate.category == category
            )
        
        return query.order_by(EmailMessage.created_at.desc()).offset(offset).limit(limit).all()
    
    def get_email_statistics(
        self,
        start_date: datetime,
        end_date: datetime,
        category: Optional[EmailTemplateCategory] = None
    ) -> Dict[str, Any]:
        """
        Get email statistics for a period
        
        Args:
            start_date: Start of period
            end_date: End of period
            category: Filter by category
        
        Returns:
            Dictionary with statistics
        """
        query = self.db.query(EmailMessage).filter(
            and_(
                EmailMessage.created_at >= start_date,
                EmailMessage.created_at <= end_date
            )
        )
        
        if category:
            query = query.join(EmailTemplate).filter(
                EmailTemplate.category == category
            )
        
        messages = query.all()
        
        total_messages = len(messages)
        sent = sum(1 for m in messages if m.status in [EmailStatus.SENT, EmailStatus.DELIVERED, EmailStatus.OPENED, EmailStatus.CLICKED])
        delivered = sum(1 for m in messages if m.status in [EmailStatus.DELIVERED, EmailStatus.OPENED, EmailStatus.CLICKED])
        opened = sum(1 for m in messages if m.status in [EmailStatus.OPENED, EmailStatus.CLICKED])
        clicked = sum(1 for m in messages if m.status == EmailStatus.CLICKED)
        bounced = sum(1 for m in messages if m.status == EmailStatus.BOUNCED)
        complained = sum(1 for m in messages if m.status == EmailStatus.COMPLAINED)
        failed = sum(1 for m in messages if m.status == EmailStatus.FAILED)
        
        return {
            'total_emails': total_messages,
            'sent': sent,
            'delivered': delivered,
            'opened': opened,
            'clicked': clicked,
            'bounced': bounced,
            'complained': complained,
            'failed': failed,
            'delivery_rate': (delivered / sent * 100) if sent > 0 else 0,
            'open_rate': (opened / delivered * 100) if delivered > 0 else 0,
            'click_rate': (clicked / opened * 100) if opened > 0 else 0,
            'bounce_rate': (bounced / sent * 100) if sent > 0 else 0,
            'complaint_rate': (complained / delivered * 100) if delivered > 0 else 0,
            'by_status': {
                status.value: sum(1 for m in messages if m.status == status)
                for status in EmailStatus
            },
            'by_category': self._get_category_breakdown(messages) if not category else {category.value: total_messages}
        }
    
    def _get_category_breakdown(self, messages: List[EmailMessage]) -> Dict[str, int]:
        """Get breakdown by category"""
        breakdown = {}
        for message in messages:
            if message.template and message.template.category:
                category = message.template.category.value
                breakdown[category] = breakdown.get(category, 0) + 1
            else:
                breakdown['uncategorized'] = breakdown.get('uncategorized', 0) + 1
        return breakdown