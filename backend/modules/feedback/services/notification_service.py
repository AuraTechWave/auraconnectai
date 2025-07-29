# backend/modules/feedback/services/notification_service.py

import asyncio
import logging
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from dataclasses import dataclass
from enum import Enum
import json
import httpx
from jinja2 import Template

from backend.modules.feedback.models.feedback_models import (
    Review, Feedback, ReviewInvitation, ReviewStatus, FeedbackStatus,
    FeedbackPriority
)
from backend.core.config import settings

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Types of notifications"""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"
    WEBHOOK = "webhook"


class NotificationPriority(str, Enum):
    """Notification priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class NotificationTemplate:
    """Notification template configuration"""
    template_id: str
    subject: str
    content: str
    notification_types: List[NotificationType]
    priority: NotificationPriority
    variables: List[str]


@dataclass
class NotificationRequest:
    """Notification request data"""
    recipient_id: Optional[int]
    recipient_email: Optional[str]
    recipient_phone: Optional[str]
    template_id: str
    variables: Dict[str, Any]
    notification_types: List[NotificationType]
    priority: NotificationPriority
    scheduled_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class EmailBackend:
    """Email notification backend using SMTP"""
    
    def __init__(self):
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME', '')
        self.smtp_password = os.getenv('SMTP_PASSWORD', '')
        self.from_email = os.getenv('FROM_EMAIL', 'noreply@auraconnect.ai')
        self.from_name = os.getenv('FROM_NAME', 'AuraConnect')
    
    async def send_email(self, to_email: str, subject: str, html_content: str, 
                        text_content: Optional[str] = None) -> Dict[str, Any]:
        """Send email using SMTP"""
        try:
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = f"{self.from_name} <{self.from_email}>"
            message['To'] = to_email
            
            # Add text part
            if text_content:
                text_part = MIMEText(text_content, 'plain')
                message.attach(text_part)
            
            # Add HTML part
            html_part = MIMEText(html_content, 'html')
            message.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                server.send_message(message)
            
            return {
                "success": True,
                "message_id": f"email_{datetime.utcnow().timestamp()}",
                "provider": "smtp"
            }
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return {
                "success": False,
                "error": str(e),
                "provider": "smtp"
            }


class SMSBackend:
    """SMS notification backend using Twilio"""
    
    def __init__(self):
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID', '')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN', '')
        self.from_phone = os.getenv('TWILIO_FROM_PHONE', '')
        self.api_url = "https://api.twilio.com/2010-04-01/Accounts/{}/Messages.json"
    
    async def send_sms(self, to_phone: str, message: str) -> Dict[str, Any]:
        """Send SMS using Twilio API"""
        if not all([self.account_sid, self.auth_token, self.from_phone]):
            logger.warning("Twilio credentials not configured, skipping SMS")
            return {"success": False, "error": "SMS not configured"}
        
        try:
            url = self.api_url.format(self.account_sid)
            auth = (self.account_sid, self.auth_token)
            data = {
                'From': self.from_phone,
                'To': to_phone,
                'Body': message
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, auth=auth, data=data)
                response.raise_for_status()
                
                result = response.json()
                return {
                    "success": True,
                    "message_id": result.get('sid'),
                    "provider": "twilio"
                }
                
        except Exception as e:
            logger.error(f"Failed to send SMS to {to_phone}: {e}")
            return {
                "success": False,
                "error": str(e),
                "provider": "twilio"
            }


class PushNotificationBackend:
    """Push notification backend using Firebase Cloud Messaging"""
    
    def __init__(self):
        self.server_key = os.getenv('FCM_SERVER_KEY', '')
        self.api_url = "https://fcm.googleapis.com/fcm/send"
    
    async def send_push(self, device_token: str, title: str, body: str, 
                       data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send push notification using FCM"""
        if not self.server_key:
            logger.warning("FCM server key not configured, skipping push notification")
            return {"success": False, "error": "Push notifications not configured"}
        
        try:
            headers = {
                'Authorization': f'key={self.server_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'to': device_token,
                'notification': {
                    'title': title,
                    'body': body
                }
            }
            
            if data:
                payload['data'] = data
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url, 
                    headers=headers, 
                    json=payload
                )
                response.raise_for_status()
                
                result = response.json()
                return {
                    "success": True,
                    "message_id": result.get('multicast_id'),
                    "provider": "fcm"
                }
                
        except Exception as e:
            logger.error(f"Failed to send push notification to {device_token}: {e}")
            return {
                "success": False,
                "error": str(e),
                "provider": "fcm"
            }


class NotificationService:
    """Service for sending notifications related to reviews and feedback"""
    
    def __init__(self, db: Session):
        self.db = db
        self.templates = self._load_notification_templates()
        self.notification_handlers = self._setup_notification_handlers()
        self.rate_limits = self._load_rate_limits()
        
        # Initialize backend services
        self.email_backend = EmailBackend()
        self.sms_backend = SMSBackend()
        self.push_backend = PushNotificationBackend()
    
    async def send_review_notification(
        self,
        event_type: str,
        review: Review,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send notification for review-related events"""
        
        try:
            template_id = f"review_{event_type}"
            template = self.templates.get(template_id)
            
            if not template:
                logger.warning(f"No template found for review event: {event_type}")
                return {"success": False, "reason": "no_template"}
            
            # Prepare notification variables
            variables = self._prepare_review_variables(review, additional_data)
            
            # Determine recipients based on event type
            recipients = self._get_review_notification_recipients(event_type, review)
            
            # Send notifications to all recipients
            results = []
            for recipient in recipients:
                notification_request = NotificationRequest(
                    recipient_id=recipient.get("id"),
                    recipient_email=recipient.get("email"),
                    recipient_phone=recipient.get("phone"),
                    template_id=template_id,
                    variables=variables,
                    notification_types=template.notification_types,
                    priority=template.priority,
                    metadata={"event_type": event_type, "review_id": review.id}
                )
                
                result = await self._send_notification(notification_request)
                results.append(result)
            
            return {
                "success": True,
                "notifications_sent": len([r for r in results if r.get("success")]),
                "total_recipients": len(recipients),
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Error sending review notification for {event_type}: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_feedback_notification(
        self,
        event_type: str,
        feedback: Feedback,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send notification for feedback-related events"""
        
        try:
            template_id = f"feedback_{event_type}"
            template = self.templates.get(template_id)
            
            if not template:
                logger.warning(f"No template found for feedback event: {event_type}")
                return {"success": False, "reason": "no_template"}
            
            # Prepare notification variables
            variables = self._prepare_feedback_variables(feedback, additional_data)
            
            # Determine recipients based on event type
            recipients = self._get_feedback_notification_recipients(event_type, feedback)
            
            # Send notifications to all recipients
            results = []
            for recipient in recipients:
                notification_request = NotificationRequest(
                    recipient_id=recipient.get("id"),
                    recipient_email=recipient.get("email"),
                    recipient_phone=recipient.get("phone"),
                    template_id=template_id,
                    variables=variables,
                    notification_types=template.notification_types,
                    priority=template.priority,
                    metadata={"event_type": event_type, "feedback_id": feedback.id}
                )
                
                result = await self._send_notification(notification_request)
                results.append(result)
            
            return {
                "success": True,
                "notifications_sent": len([r for r in results if r.get("success")]),
                "total_recipients": len(recipients),
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Error sending feedback notification for {event_type}: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_review_invitation(
        self,
        customer_id: int,
        order_id: Optional[int] = None,
        product_id: Optional[int] = None,
        template_id: Optional[int] = None,
        delivery_method: str = "email"
    ) -> Dict[str, Any]:
        """Send review invitation to customer"""
        
        try:
            # Create review invitation record
            invitation = ReviewInvitation(
                customer_id=customer_id,
                order_id=order_id,
                product_id=product_id,
                template_id=template_id,
                delivery_method=delivery_method,
                sent_at=datetime.utcnow()
            )
            
            self.db.add(invitation)
            self.db.flush()
            
            # Prepare invitation variables
            variables = {
                "customer_id": customer_id,
                "invitation_id": invitation.id,
                "invitation_uuid": str(invitation.uuid),
                "order_id": order_id,
                "product_id": product_id,
                "review_url": f"{settings.FRONTEND_URL}/reviews/create?invitation={invitation.uuid}",
                "expires_at": invitation.expires_at.isoformat() if invitation.expires_at else None
            }
            
            # Get customer info (would integrate with customer service)
            customer_info = self._get_customer_info(customer_id)
            
            # Send invitation
            notification_request = NotificationRequest(
                recipient_id=customer_id,
                recipient_email=customer_info.get("email"),
                recipient_phone=customer_info.get("phone"),
                template_id="review_invitation",
                variables=variables,
                notification_types=[NotificationType(delivery_method)],
                priority=NotificationPriority.NORMAL,
                metadata={"invitation_id": invitation.id}
            )
            
            result = await self._send_notification(notification_request)
            
            if result.get("success"):
                invitation.sent_at = datetime.utcnow()
                self.db.commit()
            
            return {
                "success": result.get("success", False),
                "invitation_id": invitation.id,
                "invitation_uuid": str(invitation.uuid),
                "delivery_method": delivery_method,
                "result": result
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error sending review invitation: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_reminder_notifications(
        self,
        reminder_type: str = "review_invitation",
        max_reminders: int = 100
    ) -> Dict[str, Any]:
        """Send reminder notifications for pending invitations"""
        
        try:
            if reminder_type == "review_invitation":
                return await self._send_review_invitation_reminders(max_reminders)
            elif reminder_type == "feedback_follow_up":
                return await self._send_feedback_follow_up_reminders(max_reminders)
            else:
                return {"success": False, "error": "Unknown reminder type"}
                
        except Exception as e:
            logger.error(f"Error sending reminder notifications: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_staff_alert(
        self,
        alert_type: str,
        message: str,
        data: Dict[str, Any],
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> Dict[str, Any]:
        """Send alert to staff members"""
        
        try:
            # Get staff members who should receive this alert
            staff_recipients = self._get_staff_alert_recipients(alert_type)
            
            variables = {
                "alert_type": alert_type,
                "message": message,
                "data": data,
                "timestamp": datetime.utcnow().isoformat(),
                "dashboard_url": f"{settings.ADMIN_URL}/dashboard"
            }
            
            results = []
            for staff in staff_recipients:
                notification_request = NotificationRequest(
                    recipient_id=staff["id"],
                    recipient_email=staff["email"],
                    template_id="staff_alert",
                    variables=variables,
                    notification_types=[NotificationType.EMAIL, NotificationType.IN_APP],
                    priority=priority,
                    metadata={"alert_type": alert_type}
                )
                
                result = await self._send_notification(notification_request)
                results.append(result)
            
            return {
                "success": True,
                "alerts_sent": len([r for r in results if r.get("success")]),
                "total_staff": len(staff_recipients)
            }
            
        except Exception as e:
            logger.error(f"Error sending staff alert: {e}")
            return {"success": False, "error": str(e)}
    
    async def process_notification_queue(
        self,
        batch_size: int = 50
    ) -> Dict[str, Any]:
        """Process queued notifications in batches"""
        
        try:
            # This would typically read from a queue (Redis, RabbitMQ, etc.)
            # For now, we'll simulate processing pending notifications
            
            processed = 0
            errors = []
            
            # Process in batches to avoid overwhelming external services
            # Implementation would depend on the queue system used
            
            logger.info(f"Processed {processed} notifications from batch")
            
            return {
                "success": True,
                "processed": processed,
                "errors": len(errors),
                "error_details": errors
            }
            
        except Exception as e:
            logger.error(f"Error processing notification queue: {e}")
            return {"success": False, "error": str(e)}
    
    # Private helper methods
    
    async def _send_notification(
        self,
        request: NotificationRequest
    ) -> Dict[str, Any]:
        """Send individual notification"""
        
        try:
            # Check rate limits
            if not self._check_rate_limit(request):
                return {"success": False, "reason": "rate_limited"}
            
            # Get template
            template = self.templates.get(request.template_id)
            if not template:
                return {"success": False, "reason": "template_not_found"}
            
            # Render template with variables
            rendered_content = self._render_template(template, request.variables)
            
            # Send via each notification type
            results = {}
            for notification_type in request.notification_types:
                handler = self.notification_handlers.get(notification_type)
                if handler:
                    result = await handler(request, rendered_content)
                    results[notification_type.value] = result
                else:
                    results[notification_type.value] = {"success": False, "reason": "handler_not_found"}
            
            # Update rate limit counters
            self._update_rate_limit(request)
            
            return {
                "success": any(r.get("success") for r in results.values()),
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return {"success": False, "error": str(e)}
    
    async def _send_review_invitation_reminders(self, max_reminders: int) -> Dict[str, Any]:
        """Send reminders for pending review invitations"""
        
        # Find invitations that need reminders
        reminder_cutoff = datetime.utcnow() - timedelta(days=7)  # 7 days after invitation
        
        invitations = self.db.query(ReviewInvitation).filter(
            and_(
                ReviewInvitation.is_completed == False,
                ReviewInvitation.is_expired == False,
                ReviewInvitation.sent_at <= reminder_cutoff,
                ReviewInvitation.reminder_sent_count < 3,  # Max 3 reminders
                or_(
                    ReviewInvitation.last_reminder_sent.is_(None),
                    ReviewInvitation.last_reminder_sent <= datetime.utcnow() - timedelta(days=3)
                )
            )
        ).limit(max_reminders).all()
        
        results = []
        for invitation in invitations:
            # Get customer info
            customer_info = self._get_customer_info(invitation.customer_id)
            
            variables = {
                "customer_name": customer_info.get("name", "Customer"),
                "invitation_uuid": str(invitation.uuid),
                "review_url": f"{settings.FRONTEND_URL}/reviews/create?invitation={invitation.uuid}",
                "product_name": self._get_product_name(invitation.product_id) if invitation.product_id else "your purchase"
            }
            
            notification_request = NotificationRequest(
                recipient_id=invitation.customer_id,
                recipient_email=customer_info.get("email"),
                template_id="review_invitation_reminder",
                variables=variables,
                notification_types=[NotificationType(invitation.delivery_method)],
                priority=NotificationPriority.LOW
            )
            
            result = await self._send_notification(notification_request)
            
            if result.get("success"):
                invitation.reminder_sent_count += 1
                invitation.last_reminder_sent = datetime.utcnow()
            
            results.append(result)
        
        self.db.commit()
        
        return {
            "success": True,
            "reminders_sent": len([r for r in results if r.get("success")]),
            "total_processed": len(invitations)
        }
    
    async def _send_feedback_follow_up_reminders(self, max_reminders: int) -> Dict[str, Any]:
        """Send follow-up reminders for pending feedback"""
        
        # Find feedback that needs follow-up
        feedback_items = self.db.query(Feedback).filter(
            and_(
                Feedback.follow_up_required == True,
                Feedback.follow_up_date <= datetime.utcnow(),
                Feedback.status.in_([FeedbackStatus.NEW, FeedbackStatus.IN_PROGRESS])
            )
        ).limit(max_reminders).all()
        
        results = []
        for feedback in feedback_items:
            # Send reminder to assigned staff or general support team
            if feedback.assigned_to:
                staff_info = self._get_staff_info(feedback.assigned_to)
                variables = {
                    "staff_name": staff_info.get("name", "Team Member"),
                    "feedback_id": feedback.id,
                    "customer_name": feedback.customer_name or "Customer",
                    "subject": feedback.subject,
                    "created_at": feedback.created_at.strftime("%Y-%m-%d %H:%M"),
                    "dashboard_url": f"{settings.ADMIN_URL}/feedback/{feedback.id}"
                }
                
                notification_request = NotificationRequest(
                    recipient_id=feedback.assigned_to,
                    recipient_email=staff_info.get("email"),
                    template_id="feedback_follow_up_reminder",
                    variables=variables,
                    notification_types=[NotificationType.EMAIL, NotificationType.IN_APP],
                    priority=NotificationPriority.NORMAL
                )
                
                result = await self._send_notification(notification_request)
                results.append(result)
                
                # Update follow-up date
                if result.get("success"):
                    feedback.follow_up_date = datetime.utcnow() + timedelta(days=1)
        
        self.db.commit()
        
        return {
            "success": True,
            "reminders_sent": len([r for r in results if r.get("success")]),
            "total_processed": len(feedback_items)
        }
    
    def _prepare_review_variables(
        self,
        review: Review,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Prepare variables for review notifications"""
        
        variables = {
            "review_id": review.id,
            "review_uuid": str(review.uuid),
            "customer_id": review.customer_id,
            "rating": review.rating,
            "title": review.title or "",
            "content": review.content[:200] + "..." if len(review.content) > 200 else review.content,
            "created_at": review.created_at.strftime("%Y-%m-%d %H:%M"),
            "is_verified": review.is_verified_purchase,
            "review_url": f"{settings.FRONTEND_URL}/reviews/{review.uuid}"
        }
        
        if additional_data:
            variables.update(additional_data)
        
        return variables
    
    def _prepare_feedback_variables(
        self,
        feedback: Feedback,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Prepare variables for feedback notifications"""
        
        variables = {
            "feedback_id": feedback.id,
            "feedback_uuid": str(feedback.uuid),
            "customer_id": feedback.customer_id,
            "customer_name": feedback.customer_name or "Customer",
            "customer_email": feedback.customer_email,
            "subject": feedback.subject,
            "message": feedback.message[:200] + "..." if len(feedback.message) > 200 else feedback.message,
            "feedback_type": feedback.feedback_type.value,
            "priority": feedback.priority.value,
            "status": feedback.status.value,
            "created_at": feedback.created_at.strftime("%Y-%m-%d %H:%M"),
            "feedback_url": f"{settings.ADMIN_URL}/feedback/{feedback.id}"
        }
        
        if additional_data:
            variables.update(additional_data)
        
        return variables
    
    def _get_review_notification_recipients(
        self,
        event_type: str,
        review: Review
    ) -> List[Dict[str, Any]]:
        """Get recipients for review notifications"""
        
        recipients = []
        
        if event_type == "created":
            # Notify customer (confirmation)
            customer_info = self._get_customer_info(review.customer_id)
            if customer_info:
                recipients.append(customer_info)
        
        elif event_type == "approved":
            # Notify customer and potentially product team
            customer_info = self._get_customer_info(review.customer_id)
            if customer_info:
                recipients.append(customer_info)
        
        elif event_type == "flagged":
            # Notify moderation team
            moderators = self._get_moderation_team()
            recipients.extend(moderators)
        
        elif event_type == "business_response":
            # Notify customer about business response
            customer_info = self._get_customer_info(review.customer_id)
            if customer_info:
                recipients.append(customer_info)
        
        return recipients
    
    def _get_feedback_notification_recipients(
        self,
        event_type: str,
        feedback: Feedback
    ) -> List[Dict[str, Any]]:
        """Get recipients for feedback notifications"""
        
        recipients = []
        
        if event_type == "created":
            # Notify customer (confirmation) and support team
            if feedback.customer_id:
                customer_info = self._get_customer_info(feedback.customer_id)
                if customer_info:
                    recipients.append(customer_info)
            
            # Notify support team based on priority
            if feedback.priority in [FeedbackPriority.HIGH, FeedbackPriority.URGENT]:
                support_team = self._get_support_team()
                recipients.extend(support_team)
        
        elif event_type == "assigned":
            # Notify assigned staff member
            if feedback.assigned_to:
                staff_info = self._get_staff_info(feedback.assigned_to)
                if staff_info:
                    recipients.append(staff_info)
        
        elif event_type == "resolved":
            # Notify customer about resolution
            if feedback.customer_id:
                customer_info = self._get_customer_info(feedback.customer_id)
                if customer_info:
                    recipients.append(customer_info)
        
        elif event_type == "escalated":
            # Notify escalation target
            if feedback.escalated_to:
                staff_info = self._get_staff_info(feedback.escalated_to)
                if staff_info:
                    recipients.append(staff_info)
        
        return recipients
    
    def _render_template(
        self,
        template: NotificationTemplate,
        variables: Dict[str, Any]
    ) -> Dict[str, str]:
        """Render notification template with variables"""
        
        try:
            from backend.modules.feedback.templates.email_templates import render_email_template
            
            # Use proper email templates for email notifications
            if template.template_id.startswith('review_') or template.template_id.startswith('feedback_'):
                try:
                    rendered = render_email_template(template.template_id, variables)
                    return rendered
                except ValueError:
                    # Fall back to simple rendering if template not found
                    pass
            
            # Simple template rendering fallback
            rendered_subject = template.subject
            rendered_content = template.content
            
            for key, value in variables.items():
                placeholder = f"{{{key}}}"
                rendered_subject = rendered_subject.replace(placeholder, str(value))
                rendered_content = rendered_content.replace(placeholder, str(value))
            
            return {
                "subject": rendered_subject,
                "content": rendered_content
            }
            
        except Exception as e:
            logger.error(f"Error rendering template: {e}")
            return {
                "subject": "Notification",
                "content": "A notification was generated for you."
            }
    
    def _check_rate_limit(self, request: NotificationRequest) -> bool:
        """Check if notification is within rate limits"""
        
        # Simple rate limiting - in production, use Redis or similar
        # For now, just return True
        return True
    
    def _update_rate_limit(self, request: NotificationRequest) -> None:
        """Update rate limit counters"""
        
        # Update rate limiting counters
        # Implementation depends on rate limiting strategy
        pass
    
    def _get_customer_info(self, customer_id: int) -> Optional[Dict[str, Any]]:
        """Get customer information (would integrate with customer service)"""
        
        # Mock customer info - in production, integrate with customer service
        return {
            "id": customer_id,
            "name": f"Customer {customer_id}",
            "email": f"customer{customer_id}@example.com",
            "phone": "+1234567890"
        }
    
    def _get_staff_info(self, staff_id: int) -> Optional[Dict[str, Any]]:
        """Get staff information"""
        
        # Mock staff info - in production, integrate with user service
        return {
            "id": staff_id,
            "name": f"Staff {staff_id}",
            "email": f"staff{staff_id}@company.com"
        }
    
    def _get_product_name(self, product_id: int) -> str:
        """Get product name"""
        
        # Mock product name - in production, integrate with product service
        return f"Product {product_id}"
    
    def _get_moderation_team(self) -> List[Dict[str, Any]]:
        """Get moderation team members"""
        
        # Mock moderation team
        return [
            {"id": 1001, "name": "Moderator 1", "email": "mod1@company.com"},
            {"id": 1002, "name": "Moderator 2", "email": "mod2@company.com"}
        ]
    
    def _get_support_team(self) -> List[Dict[str, Any]]:
        """Get support team members"""
        
        # Mock support team
        return [
            {"id": 2001, "name": "Support 1", "email": "support1@company.com"},
            {"id": 2002, "name": "Support 2", "email": "support2@company.com"}
        ]
    
    def _get_staff_alert_recipients(self, alert_type: str) -> List[Dict[str, Any]]:
        """Get staff members who should receive specific alert types"""
        
        # Different alert types go to different teams
        if alert_type in ["high_priority_feedback", "escalated_feedback"]:
            return self._get_support_team()
        elif alert_type in ["flagged_review", "spam_detected"]:
            return self._get_moderation_team()
        else:
            # General alerts go to all staff
            return self._get_support_team() + self._get_moderation_team()
    
    def _load_notification_templates(self) -> Dict[str, NotificationTemplate]:
        """Load notification templates"""
        
        templates = {
            "review_created": NotificationTemplate(
                template_id="review_created",
                subject="Thank you for your review!",
                content="Hi {customer_name}, thank you for leaving a review. Your feedback helps other customers make informed decisions.",
                notification_types=[NotificationType.EMAIL],
                priority=NotificationPriority.LOW,
                variables=["customer_name", "review_url"]
            ),
            
            "review_approved": NotificationTemplate(
                template_id="review_approved",
                subject="Your review has been published",
                content="Hi {customer_name}, your review has been approved and is now visible to other customers. Thank you for your feedback!",
                notification_types=[NotificationType.EMAIL],
                priority=NotificationPriority.LOW,
                variables=["customer_name", "review_url"]
            ),
            
            "review_invitation": NotificationTemplate(
                template_id="review_invitation",
                subject="Share your experience - Write a review",
                content="Hi! We'd love to hear about your recent purchase. Your review helps other customers and helps us improve. Click here to write your review: {review_url}",
                notification_types=[NotificationType.EMAIL],
                priority=NotificationPriority.NORMAL,
                variables=["customer_name", "review_url", "product_name"]
            ),
            
            "feedback_created": NotificationTemplate(
                template_id="feedback_created",
                subject="We received your feedback - Reference #{feedback_id}",
                content="Hi {customer_name}, we've received your feedback and will review it shortly. Reference: #{feedback_id}",
                notification_types=[NotificationType.EMAIL],
                priority=NotificationPriority.NORMAL,
                variables=["customer_name", "feedback_id", "subject"]
            ),
            
            "feedback_resolved": NotificationTemplate(
                template_id="feedback_resolved",
                subject="Your feedback has been resolved - #{feedback_id}",
                content="Hi {customer_name}, we've resolved your feedback. Here's what we did: {resolution_notes}",
                notification_types=[NotificationType.EMAIL],
                priority=NotificationPriority.NORMAL,
                variables=["customer_name", "feedback_id", "resolution_notes"]
            ),
            
            "staff_alert": NotificationTemplate(
                template_id="staff_alert",
                subject="Alert: {alert_type}",
                content="Alert: {message}. Please check the dashboard for details: {dashboard_url}",
                notification_types=[NotificationType.EMAIL, NotificationType.IN_APP],
                priority=NotificationPriority.NORMAL,
                variables=["alert_type", "message", "dashboard_url"]
            )
        }
        
        return templates
    
    def _setup_notification_handlers(self) -> Dict[NotificationType, Callable]:
        """Setup handlers for different notification types"""
        
        return {
            NotificationType.EMAIL: self._send_email_notification,
            NotificationType.SMS: self._send_sms_notification,
            NotificationType.PUSH: self._send_push_notification,
            NotificationType.IN_APP: self._send_in_app_notification,
            NotificationType.WEBHOOK: self._send_webhook_notification
        }
    
    def _load_rate_limits(self) -> Dict[str, Any]:
        """Load rate limiting configuration"""
        
        return {
            "email": {"limit": 100, "window": 3600},  # 100 emails per hour
            "sms": {"limit": 10, "window": 3600},     # 10 SMS per hour
            "push": {"limit": 50, "window": 3600},    # 50 push notifications per hour
        }
    
    # Notification handlers (mock implementations)
    
    async def _send_email_notification(
        self,
        request: NotificationRequest,
        rendered_content: Dict[str, str]
    ) -> Dict[str, Any]:
        """Send email notification"""
        
        try:
            if not request.recipient_email:
                return {"success": False, "error": "No recipient email provided"}
            
            # Send email using the email backend
            result = await self.email_backend.send_email(
                to_email=request.recipient_email,
                subject=rendered_content['subject'],
                html_content=rendered_content['content'],
                text_content=rendered_content.get('text_content')
            )
            
            logger.info(f"Email sent to {request.recipient_email}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
            return {"success": False, "error": str(e)}
    
    async def _send_sms_notification(
        self,
        request: NotificationRequest,
        rendered_content: Dict[str, str]
    ) -> Dict[str, Any]:
        """Send SMS notification"""
        
        try:
            if not request.recipient_phone:
                return {"success": False, "error": "No recipient phone provided"}
            
            # Send SMS using the SMS backend
            result = await self.sms_backend.send_sms(
                to_phone=request.recipient_phone,
                message=rendered_content['content']
            )
            
            logger.info(f"SMS sent to {request.recipient_phone}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error sending SMS notification: {e}")
            return {"success": False, "error": str(e)}
    
    async def _send_push_notification(
        self,
        request: NotificationRequest,
        rendered_content: Dict[str, str]
    ) -> Dict[str, Any]:
        """Send push notification"""
        
        try:
            # Get device token for the user (this would come from user preferences/device registration)
            device_token = self._get_user_device_token(request.recipient_id)
            
            if not device_token:
                return {"success": False, "error": "No device token found for user"}
            
            # Send push notification using the push backend
            result = await self.push_backend.send_push(
                device_token=device_token,
                title=rendered_content['subject'],
                body=rendered_content['content'],
                data=request.metadata
            )
            
            logger.info(f"Push notification sent to user {request.recipient_id}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error sending push notification: {e}")
            return {"success": False, "error": str(e)}
    
    async def _send_in_app_notification(
        self,
        request: NotificationRequest,
        rendered_content: Dict[str, str]
    ) -> Dict[str, Any]:
        """Send in-app notification"""
        
        try:
            # Mock in-app notification - in production, store in database or send via WebSocket
            logger.info(f"Sending in-app notification to user {request.recipient_id}")
            
            # Store notification in database for user to see in app
            # Implementation would depend on in-app notification system
            
            return {"success": True, "message_id": f"inapp_{datetime.utcnow().timestamp()}"}
            
        except Exception as e:
            logger.error(f"Error sending in-app notification: {e}")
            return {"success": False, "error": str(e)}
    
    async def _send_webhook_notification(
        self,
        request: NotificationRequest,
        rendered_content: Dict[str, str]
    ) -> Dict[str, Any]:
        """Send webhook notification"""
        
        try:
            # Mock webhook - in production, send HTTP POST to configured webhook URL
            logger.info(f"Sending webhook notification for template {request.template_id}")
            
            webhook_data = {
                "template_id": request.template_id,
                "recipient_id": request.recipient_id,
                "content": rendered_content,
                "metadata": request.metadata,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Would send HTTP POST request here
            
            return {"success": True, "webhook_data": webhook_data}
            
        except Exception as e:
            logger.error(f"Error sending webhook: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_user_device_token(self, user_id: Optional[int]) -> Optional[str]:
        """Get device token for push notifications (mock implementation)"""
        if not user_id:
            return None
        
        # In a real implementation, this would query the user's device registration table
        # For now, return a mock device token for testing
        # return self.db.query(UserDevice).filter(...).first().device_token
        
        return f"mock_device_token_{user_id}"


# Global notification service instance
notification_service = None

def get_notification_service(db: Session) -> NotificationService:
    """Get or create notification service instance"""
    return NotificationService(db)