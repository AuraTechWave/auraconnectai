# backend/core/notification_service.py

from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime

from .notification_adapter import (
    NotificationAdapter, NotificationMessage, NotificationPriority,
    LoggingAdapter, EmailAdapter, SlackAdapter, SMSAdapter, CompositeAdapter
)
from .config import settings


logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for sending notifications to users and roles
    
    Uses adapter pattern to support multiple notification channels
    """
    
    def __init__(self, db: Session, adapter: Optional[NotificationAdapter] = None):
        self.db = db
        self._adapter = adapter or self._create_default_adapter()
    
    def _create_default_adapter(self) -> NotificationAdapter:
        """
        Create default notification adapter based on configuration
        
        Returns composite adapter with all configured channels
        """
        adapters = []
        
        # Always include logging adapter
        adapters.append(LoggingAdapter())
        
        # Add other adapters based on configuration
        if hasattr(settings, 'SMTP_ENABLED') and settings.SMTP_ENABLED:
            adapters.append(EmailAdapter(smtp_config={
                'host': getattr(settings, 'SMTP_HOST', ''),
                'port': getattr(settings, 'SMTP_PORT', 587),
                'username': getattr(settings, 'SMTP_USERNAME', ''),
                'password': getattr(settings, 'SMTP_PASSWORD', ''),
            }))
        
        if hasattr(settings, 'SLACK_WEBHOOK_URL') and settings.SLACK_WEBHOOK_URL:
            adapters.append(SlackAdapter(
                webhook_url=settings.SLACK_WEBHOOK_URL,
                bot_token=getattr(settings, 'SLACK_BOT_TOKEN', None)
            ))
        
        if hasattr(settings, 'TWILIO_ENABLED') and settings.TWILIO_ENABLED:
            adapters.append(SMSAdapter(twilio_config={
                'account_sid': getattr(settings, 'TWILIO_ACCOUNT_SID', ''),
                'auth_token': getattr(settings, 'TWILIO_AUTH_TOKEN', ''),
                'from_number': getattr(settings, 'TWILIO_FROM_NUMBER', ''),
            }))
        
        # Return composite adapter with all configured channels
        return CompositeAdapter(adapters, require_all=False)
    
    def set_adapter(self, adapter: NotificationAdapter):
        """Set a custom notification adapter"""
        self._adapter = adapter
    
    async def send_role_notification(
        self,
        role: str,
        subject: str,
        message: str,
        priority: str = "normal",
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Send notification to all users with a specific role
        
        Args:
            role: Role name to send notification to
            subject: Notification subject
            message: Notification message
            priority: Priority level (low, normal, high, urgent)
            metadata: Additional metadata
        
        Returns:
            Success status
        """
        try:
            notification = NotificationMessage(
                subject=subject,
                message=message,
                priority=NotificationPriority(priority),
                metadata={
                    "role": role,
                    **(metadata or {})
                }
            )
            
            return await self._adapter.send_to_role(role, notification)
            
        except Exception as e:
            logger.error(f"Failed to send role notification: {str(e)}")
            return False
    
    async def send_user_notification(
        self,
        user_id: int,
        subject: str,
        message: str,
        priority: str = "normal",
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Send notification to a specific user
        
        Args:
            user_id: User ID to send notification to
            subject: Notification subject
            message: Notification message
            priority: Priority level (low, normal, high, urgent)
            metadata: Additional metadata
        
        Returns:
            Success status
        """
        try:
            notification = NotificationMessage(
                subject=subject,
                message=message,
                priority=NotificationPriority(priority),
                metadata={
                    "user_id": user_id,
                    **(metadata or {})
                }
            )
            
            return await self._adapter.send_to_user(user_id, notification)
            
        except Exception as e:
            logger.error(f"Failed to send user notification: {str(e)}")
            return False
    
    async def send_critical_alert(
        self,
        alert_type: str,
        message: str,
        affected_resources: List[Dict],
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Send critical system alert
        
        Args:
            alert_type: Type of alert (inventory_failure, system_error, etc.)
            message: Alert message
            affected_resources: List of affected resources
            metadata: Additional metadata
        
        Returns:
            Success status
        """
        try:
            notification_metadata = {
                "alert_type": alert_type,
                "affected_resources": affected_resources,
                **(metadata or {})
            }
            
            # Send to admins with urgent priority
            admin_notification = NotificationMessage(
                subject=f"CRITICAL ALERT: {alert_type}",
                message=message,
                priority=NotificationPriority.URGENT,
                metadata=notification_metadata
            )
            
            admin_result = await self._adapter.send_to_role("admin", admin_notification)
            
            # Send to managers with high priority
            manager_notification = NotificationMessage(
                subject=f"Critical Alert: {alert_type}",
                message=message,
                priority=NotificationPriority.HIGH,
                metadata=notification_metadata
            )
            
            manager_result = await self._adapter.send_to_role("manager", manager_notification)
            
            return admin_result and manager_result
            
        except Exception as e:
            logger.error(f"Failed to send critical alert: {str(e)}")
            return False
    
    async def send_batch_notifications(
        self,
        notifications: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Send multiple notifications in batch
        
        Args:
            notifications: List of notification configurations
                Each dict should contain:
                - type: "user" or "role"
                - target: user_id (for user) or role name (for role)
                - subject: Notification subject
                - message: Notification message
                - priority: Priority level (optional)
                - metadata: Additional metadata (optional)
        
        Returns:
            Dict with results for each notification
        """
        results = {
            "total": len(notifications),
            "successful": 0,
            "failed": 0,
            "details": []
        }
        
        for i, notif_config in enumerate(notifications):
            try:
                notif_type = notif_config.get("type")
                target = notif_config.get("target")
                
                if notif_type == "user":
                    success = await self.send_user_notification(
                        user_id=target,
                        subject=notif_config.get("subject", ""),
                        message=notif_config.get("message", ""),
                        priority=notif_config.get("priority", "normal"),
                        metadata=notif_config.get("metadata")
                    )
                elif notif_type == "role":
                    success = await self.send_role_notification(
                        role=target,
                        subject=notif_config.get("subject", ""),
                        message=notif_config.get("message", ""),
                        priority=notif_config.get("priority", "normal"),
                        metadata=notif_config.get("metadata")
                    )
                else:
                    success = False
                    logger.error(f"Unknown notification type: {notif_type}")
                
                if success:
                    results["successful"] += 1
                else:
                    results["failed"] += 1
                
                results["details"].append({
                    "index": i,
                    "type": notif_type,
                    "target": target,
                    "success": success
                })
                
            except Exception as e:
                results["failed"] += 1
                results["details"].append({
                    "index": i,
                    "success": False,
                    "error": str(e)
                })
                logger.error(f"Error processing batch notification {i}: {str(e)}")
        
        return results