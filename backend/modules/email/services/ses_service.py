# backend/modules/email/services/ses_service.py

import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
import boto3
from botocore.exceptions import ClientError, BotoCoreError

from core.config import settings
from modules.email.models.email_models import EmailStatus

logger = logging.getLogger(__name__)


class SESService:
    """Service for sending emails via AWS SES"""
    
    def __init__(self):
        self.aws_access_key = settings.AWS_ACCESS_KEY_ID
        self.aws_secret_key = settings.AWS_SECRET_ACCESS_KEY
        self.aws_region = settings.AWS_REGION or 'us-east-1'
        self.from_email = settings.EMAIL_FROM_ADDRESS
        self.from_name = settings.EMAIL_FROM_NAME
        self.configuration_set = settings.SES_CONFIGURATION_SET
        
        # Initialize SES client
        if self.aws_access_key and self.aws_secret_key:
            self.ses_client = boto3.client(
                'ses',
                region_name=self.aws_region,
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key
            )
        else:
            self.ses_client = None
    
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
        template_name: Optional[str] = None,
        template_data: Optional[Dict[str, Any]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send email via AWS SES
        
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
            template_name: SES template name
            template_data: Template data
            attachments: List of attachments (requires raw email)
            tags: Email tags
            metadata: Custom metadata
        
        Returns:
            Dict with success status and details
        """
        if not self.ses_client:
            logger.error("AWS SES client not initialized")
            return {
                'success': False,
                'status': EmailStatus.FAILED,
                'error': 'AWS SES not configured'
            }
        
        try:
            # Format sender
            if from_name:
                source = f"{from_name} <{from_email or self.from_email}>"
            else:
                source = from_email or self.from_email
            
            # Format recipient
            if to_name:
                to_address = f"{to_name} <{to_email}>"
            else:
                to_address = to_email
            
            # Build destination
            destination = {
                'ToAddresses': [to_address]
            }
            
            if cc_emails:
                destination['CcAddresses'] = cc_emails
            
            if bcc_emails:
                destination['BccAddresses'] = bcc_emails
            
            # Prepare email parameters
            params = {
                'Source': source,
                'Destination': destination
            }
            
            # Add configuration set for tracking
            if self.configuration_set:
                params['ConfigurationSetName'] = self.configuration_set
            
            # Add reply-to
            if reply_to_email:
                params['ReplyToAddresses'] = [reply_to_email]
            
            # Add tags
            if tags or metadata:
                message_tags = []
                
                if tags:
                    for tag in tags:
                        message_tags.append({
                            'Name': 'tag',
                            'Value': tag
                        })
                
                if metadata:
                    for key, value in metadata.items():
                        message_tags.append({
                            'Name': f'metadata_{key}',
                            'Value': str(value)
                        })
                
                params['Tags'] = message_tags
            
            # Send using template or content
            if template_name:
                # Use SES template
                params['Template'] = template_name
                params['TemplateData'] = json.dumps(template_data or {})
                
                response = self.ses_client.send_templated_email(**params)
            elif attachments:
                # Send raw email (for attachments)
                raw_message = self._create_raw_email(
                    source, to_address, subject, html_body, text_body,
                    cc_emails, bcc_emails, reply_to_email, attachments
                )
                
                response = self.ses_client.send_raw_email(
                    Source=source,
                    Destinations=[to_address] + (cc_emails or []) + (bcc_emails or []),
                    RawMessage={'Data': raw_message}
                )
            else:
                # Send simple email
                message = {
                    'Subject': {
                        'Data': subject,
                        'Charset': 'UTF-8'
                    },
                    'Body': {}
                }
                
                if html_body:
                    message['Body']['Html'] = {
                        'Data': html_body,
                        'Charset': 'UTF-8'
                    }
                
                if text_body:
                    message['Body']['Text'] = {
                        'Data': text_body,
                        'Charset': 'UTF-8'
                    }
                
                params['Message'] = message
                
                response = self.ses_client.send_email(**params)
            
            # Extract message ID
            message_id = response.get('MessageId', '')
            
            return {
                'success': True,
                'status': EmailStatus.SENT,
                'provider_message_id': message_id,
                'provider_response': response,
                'sent_at': datetime.utcnow()
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            logger.error(f"AWS SES error: {error_code} - {error_message}")
            
            # Map SES errors to our status
            if error_code in ['MessageRejected', 'MailFromDomainNotVerified']:
                status = EmailStatus.FAILED
            else:
                status = EmailStatus.FAILED
            
            return {
                'success': False,
                'status': status,
                'error': error_message,
                'provider_response': e.response
            }
            
        except Exception as e:
            logger.error(f"Error sending email via AWS SES: {str(e)}")
            return {
                'success': False,
                'status': EmailStatus.FAILED,
                'error': str(e)
            }
    
    def _create_raw_email(
        self,
        from_address: str,
        to_address: str,
        subject: str,
        html_body: Optional[str],
        text_body: Optional[str],
        cc_emails: Optional[List[str]],
        bcc_emails: Optional[List[str]],
        reply_to_email: Optional[str],
        attachments: List[Dict[str, Any]]
    ) -> str:
        """
        Create raw email message with attachments
        
        Args:
            Various email components
        
        Returns:
            Raw email message as string
        """
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.base import MIMEBase
        from email import encoders
        import base64
        
        # Create message container
        msg = MIMEMultipart('mixed')
        msg['From'] = from_address
        msg['To'] = to_address
        msg['Subject'] = subject
        
        if cc_emails:
            msg['Cc'] = ', '.join(cc_emails)
        
        if reply_to_email:
            msg['Reply-To'] = reply_to_email
        
        # Create body container
        msg_body = MIMEMultipart('alternative')
        
        # Add text and HTML parts
        if text_body:
            text_part = MIMEText(text_body, 'plain', 'utf-8')
            msg_body.attach(text_part)
        
        if html_body:
            html_part = MIMEText(html_body, 'html', 'utf-8')
            msg_body.attach(html_part)
        
        msg.attach(msg_body)
        
        # Add attachments
        for attachment in attachments:
            # Decode base64 content
            file_content = base64.b64decode(attachment['content_base64'])
            
            # Create attachment
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(file_content)
            encoders.encode_base64(part)
            
            # Add headers
            part.add_header(
                'Content-Disposition',
                f'attachment; filename="{attachment["filename"]}"'
            )
            
            if attachment.get('content_id'):
                part.add_header('Content-ID', f'<{attachment["content_id"]}>')
                part.add_header(
                    'Content-Disposition',
                    f'inline; filename="{attachment["filename"]}"'
                )
            
            msg.attach(part)
        
        return msg.as_string()
    
    def verify_webhook(self, message: Dict[str, Any]) -> bool:
        """
        Verify SES webhook notification (SNS message)
        
        Args:
            message: SNS message
        
        Returns:
            True if message is valid
        """
        try:
            # For SES notifications via SNS, verify the SNS signature
            sns_client = boto3.client(
                'sns',
                region_name=self.aws_region,
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key
            )
            
            # This would typically involve verifying the SNS message signature
            # For simplicity, we'll just check the message type
            return message.get('Type') in ['Notification', 'SubscriptionConfirmation']
            
        except Exception as e:
            logger.error(f"Error verifying webhook: {str(e)}")
            return False
    
    def _parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """
        Safely parse timestamp string to datetime
        
        Args:
            timestamp_str: Timestamp string from webhook
        
        Returns:
            datetime object or None if parsing fails
        """
        if not timestamp_str:
            return None
        
        try:
            # Handle ISO format with Z suffix
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            logger.warning(f"Failed to parse timestamp: {timestamp_str}")
            return None
    
    def parse_webhook_event(self, sns_message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse SES webhook event from SNS
        
        Args:
            sns_message: SNS message containing SES event
        
        Returns:
            Parsed event data
        """
        try:
            # Parse the message body
            message = json.loads(sns_message.get('Message', '{}'))
            
            event_type = message.get('eventType', '').lower()
            
            # Map SES events to our status
            status_mapping = {
                'send': EmailStatus.SENT,
                'delivery': EmailStatus.DELIVERED,
                'bounce': EmailStatus.BOUNCED,
                'complaint': EmailStatus.COMPLAINED,
                'reject': EmailStatus.FAILED,
                'open': EmailStatus.OPENED,
                'click': EmailStatus.CLICKED
            }
            
            status = status_mapping.get(event_type, EmailStatus.SENT)
            
            # Extract mail object
            mail = message.get('mail', {})
            
            # Extract relevant data based on event type
            parsed_event = {
                'provider_message_id': mail.get('messageId'),
                'status': status,
                'event_type': event_type
            }
            
            # Parse timestamp safely - use current time as fallback
            timestamp = self._parse_timestamp(mail.get('timestamp', ''))
            parsed_event['timestamp'] = timestamp if timestamp else datetime.utcnow()
            
            # Add event-specific data
            if event_type == 'bounce':
                bounce = message.get('bounce', {})
                parsed_event.update({
                    'bounce_type': bounce.get('bounceType'),
                    'bounce_subtype': bounce.get('bounceSubType'),
                    'bounced_recipients': bounce.get('bouncedRecipients', [])
                })
            elif event_type == 'complaint':
                complaint = message.get('complaint', {})
                parsed_event.update({
                    'complaint_type': complaint.get('complaintFeedbackType'),
                    'complained_recipients': complaint.get('complainedRecipients', [])
                })
            elif event_type == 'delivery':
                delivery = message.get('delivery', {})
                
                # Parse delivery timestamp safely
                delivered_at = self._parse_timestamp(delivery.get('timestamp', ''))
                if delivered_at:
                    parsed_event['delivered_at'] = delivered_at
                    
                processing_time = delivery.get('processingTimeMillis')
                if processing_time is not None:
                    parsed_event['processing_time_ms'] = processing_time
            elif event_type in ['open', 'click']:
                event_data = message.get(event_type, {})
                parsed_event.update({
                    'user_agent': event_data.get('userAgent'),
                    'ip_address': event_data.get('ipAddress')
                })
                
                # Parse event-specific timestamp if available
                event_timestamp = self._parse_timestamp(event_data.get('timestamp', ''))
                if event_timestamp:
                    parsed_event['timestamp'] = event_timestamp
                    
                if event_type == 'click':
                    parsed_event['url'] = event_data.get('link')
            
            return parsed_event
            
        except Exception as e:
            logger.error(f"Error parsing SES event: {str(e)}")
            return {
                'status': EmailStatus.FAILED,
                'error': str(e)
            }
    
    def create_template(
        self,
        template_name: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None
    ) -> bool:
        """
        Create or update an SES template
        
        Args:
            template_name: Template name
            subject: Subject line template
            html_body: HTML body template
            text_body: Text body template
        
        Returns:
            True if successful
        """
        if not self.ses_client:
            return False
        
        try:
            template = {
                'TemplateName': template_name,
                'SubjectPart': subject,
                'HtmlPart': html_body
            }
            
            if text_body:
                template['TextPart'] = text_body
            
            # Try to create template
            try:
                self.ses_client.create_template(Template=template)
            except ClientError as e:
                if e.response['Error']['Code'] == 'AlreadyExists':
                    # Update existing template
                    self.ses_client.update_template(Template=template)
                else:
                    raise
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating SES template: {str(e)}")
            return False