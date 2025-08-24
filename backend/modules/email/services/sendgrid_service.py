# backend/modules/email/services/sendgrid_service.py

import logging
import base64
from typing import Dict, Any, Optional, List
from datetime import datetime
import sendgrid
from sendgrid.helpers.mail import (
    Mail, Email, To, Content, Attachment, FileContent, FileName, 
    FileType, Disposition, ContentId, Personalization, Cc, Bcc,
    ReplyTo, Subject, HtmlContent, PlainTextContent
)
from python_http_client.exceptions import HTTPError

from core.config import settings
from modules.email.models.email_models import EmailStatus

logger = logging.getLogger(__name__)


class SendGridService:
    """Service for sending emails via SendGrid"""
    
    def __init__(self):
        self.api_key = settings.SENDGRID_API_KEY
        self.from_email = settings.EMAIL_FROM_ADDRESS
        self.from_name = settings.EMAIL_FROM_NAME
        self.sg = sendgrid.SendGridAPIClient(api_key=self.api_key) if self.api_key else None
        self.webhook_secret = settings.SENDGRID_WEBHOOK_SECRET
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: Optional[str] = None,
        text_body: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        to_name: Optional[str] = None,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None,
        reply_to_email: Optional[str] = None,
        template_id: Optional[str] = None,
        template_data: Optional[Dict[str, Any]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send email via SendGrid
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_body: HTML content
            text_body: Plain text content
            from_email: Sender email (overrides default)
            from_name: Sender name (overrides default)
            to_name: Recipient name
            cc_emails: CC recipients
            bcc_emails: BCC recipients
            reply_to_email: Reply-to address
            template_id: SendGrid template ID
            template_data: Template substitution data
            attachments: List of attachment dicts
            tags: Email tags for categorization
            metadata: Custom metadata
        
        Returns:
            Dict with success status and details
        """
        if not self.sg:
            logger.error("SendGrid API client not initialized")
            return {
                'success': False,
                'status': EmailStatus.FAILED,
                'error': 'SendGrid not configured'
            }
        
        try:
            # Create mail object
            from_email_obj = Email(from_email or self.from_email, from_name or self.from_name)
            to_email_obj = To(to_email, to_name)
            
            if template_id:
                # Use dynamic template
                message = Mail(from_email=from_email_obj, to_emails=to_email_obj)
                message.template_id = template_id
                
                if template_data:
                    message.dynamic_template_data = template_data
            else:
                # Use content
                message = Mail(
                    from_email=from_email_obj,
                    to_emails=to_email_obj,
                    subject=subject,
                    html_content=html_body,
                    plain_text_content=text_body
                )
            
            # Add CC recipients
            if cc_emails:
                for cc_email in cc_emails:
                    message.add_cc(Cc(cc_email))
            
            # Add BCC recipients
            if bcc_emails:
                for bcc_email in bcc_emails:
                    message.add_bcc(Bcc(bcc_email))
            
            # Add reply-to
            if reply_to_email:
                message.reply_to = ReplyTo(reply_to_email)
            
            # Add attachments
            if attachments:
                for att in attachments:
                    attachment = Attachment()
                    attachment.file_content = FileContent(att['content_base64'])
                    attachment.file_name = FileName(att['filename'])
                    attachment.file_type = FileType(att['content_type'])
                    attachment.disposition = Disposition('attachment')
                    
                    if att.get('content_id'):
                        attachment.content_id = ContentId(att['content_id'])
                        attachment.disposition = Disposition('inline')
                    
                    message.add_attachment(attachment)
            
            # Add custom headers for tracking
            if tags:
                message.add_header('X-Tags', ','.join(tags))
            
            if metadata:
                for key, value in metadata.items():
                    message.add_header(f'X-Metadata-{key}', str(value))
            
            # Send the email
            response = self.sg.send(message)
            
            # Parse response
            if response.status_code in [200, 201, 202]:
                # Extract message ID from headers
                message_id = None
                if hasattr(response, 'headers') and 'X-Message-Id' in response.headers:
                    message_id = response.headers.get('X-Message-Id')
                
                return {
                    'success': True,
                    'status': EmailStatus.SENT,
                    'provider_message_id': message_id,
                    'provider_response': {
                        'status_code': response.status_code,
                        'headers': dict(response.headers) if hasattr(response, 'headers') else {}
                    },
                    'sent_at': datetime.utcnow()
                }
            else:
                return {
                    'success': False,
                    'status': EmailStatus.FAILED,
                    'error': f'SendGrid returned status code: {response.status_code}',
                    'provider_response': {
                        'status_code': response.status_code,
                        'body': response.body,
                        'headers': dict(response.headers) if hasattr(response, 'headers') else {}
                    }
                }
                
        except HTTPError as e:
            logger.error(f"SendGrid HTTP error: {e.status_code} - {e.body}")
            return {
                'success': False,
                'status': EmailStatus.FAILED,
                'error': f'SendGrid error: {e.status_code}',
                'provider_response': {
                    'status_code': e.status_code,
                    'body': e.body.decode('utf-8') if e.body else None
                }
            }
        except Exception as e:
            logger.error(f"Error sending email via SendGrid: {str(e)}")
            return {
                'success': False,
                'status': EmailStatus.FAILED,
                'error': str(e)
            }
    
    def verify_webhook(self, request_body: bytes, signature: str, timestamp: str) -> bool:
        """
        Verify SendGrid webhook signature
        
        Args:
            request_body: Raw request body
            signature: Signature from header
            timestamp: Timestamp from header
        
        Returns:
            True if signature is valid
        """
        if not self.webhook_secret:
            logger.warning("SendGrid webhook secret not configured")
            return False
        
        try:
            import hmac
            import hashlib
            
            # Construct the signed content
            signed_content = timestamp + request_body.decode('utf-8')
            
            # Calculate expected signature
            expected_signature = hmac.new(
                self.webhook_secret.encode('utf-8'),
                signed_content.encode('utf-8'),
                hashlib.sha256
            ).digest()
            
            # Compare signatures
            provided_signature = base64.b64decode(signature)
            
            return hmac.compare_digest(expected_signature, provided_signature)
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False
    
    def parse_webhook_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse SendGrid webhook event
        
        Args:
            event: Webhook event data
        
        Returns:
            Parsed event data
        """
        event_type = event.get('event', '').lower()
        
        # Map SendGrid events to our status
        status_mapping = {
            'processed': EmailStatus.SENT,
            'delivered': EmailStatus.DELIVERED,
            'bounce': EmailStatus.BOUNCED,
            'deferred': EmailStatus.FAILED,
            'dropped': EmailStatus.FAILED,
            'spamreport': EmailStatus.COMPLAINED,
            'open': EmailStatus.OPENED,
            'click': EmailStatus.CLICKED
        }
        
        status = status_mapping.get(event_type, EmailStatus.SENT)
        
        # Extract relevant data
        return {
            'provider_message_id': event.get('sg_message_id', '').split('.')[0],  # Remove the suffix
            'status': status,
            'event_type': event_type,
            'email': event.get('email'),
            'timestamp': datetime.fromtimestamp(event.get('timestamp', 0)),
            'reason': event.get('reason'),
            'bounce_type': event.get('type') if event_type == 'bounce' else None,
            'url': event.get('url') if event_type == 'click' else None,
            'user_agent': event.get('useragent'),
            'ip': event.get('ip'),
            'metadata': {
                'sg_event_id': event.get('sg_event_id'),
                'category': event.get('category'),
                'smtp_id': event.get('smtp-id')
            }
        }
    
    def create_unsubscribe_link(self, email: str, token: str) -> str:
        """
        Create unsubscribe link
        
        Args:
            email: Email address
            token: Unsubscribe token
        
        Returns:
            Unsubscribe URL
        """
        base_url = settings.APP_URL
        return f"{base_url}/api/v1/email/unsubscribe?email={email}&token={token}"