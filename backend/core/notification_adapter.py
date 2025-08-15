# backend/core/notification_adapter.py

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging
from datetime import datetime


logger = logging.getLogger(__name__)


class NotificationPriority(str, Enum):
    """Notification priority levels"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class NotificationMessage:
    """Standard notification message structure"""

    subject: str
    message: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class NotificationAdapter(ABC):
    """
    Abstract base class for notification adapters

    Implement this interface to add new notification channels
    (Email, Slack, SMS, Push notifications, etc.)
    """

    @abstractmethod
    async def send_to_user(self, user_id: int, message: NotificationMessage) -> bool:
        """Send notification to a specific user"""
        pass

    @abstractmethod
    async def send_to_role(self, role: str, message: NotificationMessage) -> bool:
        """Send notification to all users with a specific role"""
        pass

    @abstractmethod
    async def send_broadcast(
        self, message: NotificationMessage, user_ids: Optional[List[int]] = None
    ) -> bool:
        """Send broadcast notification to multiple users"""
        pass

    @abstractmethod
    def get_adapter_name(self) -> str:
        """Return the name of this adapter"""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the adapter is currently available"""
        pass


class LoggingAdapter(NotificationAdapter):
    """
    Default logging adapter for notifications

    This adapter logs all notifications and can be used for
    development/testing or as a fallback
    """

    def __init__(self, log_level: int = logging.INFO):
        self.log_level = log_level

    async def send_to_user(self, user_id: int, message: NotificationMessage) -> bool:
        logger.log(
            self.log_level,
            f"[NOTIFICATION] To User {user_id} - {message.subject}: {message.message}",
            extra={
                "notification_type": "user",
                "user_id": user_id,
                "subject": message.subject,
                "priority": message.priority.value,
                "timestamp": message.timestamp.isoformat(),
                "metadata": message.metadata,
            },
        )
        return True

    async def send_to_role(self, role: str, message: NotificationMessage) -> bool:
        logger.log(
            self.log_level,
            f"[NOTIFICATION] To Role '{role}' - {message.subject}: {message.message}",
            extra={
                "notification_type": "role",
                "role": role,
                "subject": message.subject,
                "priority": message.priority.value,
                "timestamp": message.timestamp.isoformat(),
                "metadata": message.metadata,
            },
        )
        return True

    async def send_broadcast(
        self, message: NotificationMessage, user_ids: Optional[List[int]] = None
    ) -> bool:
        target = f"Users {user_ids}" if user_ids else "All Users"
        logger.log(
            self.log_level,
            f"[NOTIFICATION] Broadcast to {target} - {message.subject}: {message.message}",
            extra={
                "notification_type": "broadcast",
                "user_ids": user_ids,
                "subject": message.subject,
                "priority": message.priority.value,
                "timestamp": message.timestamp.isoformat(),
                "metadata": message.metadata,
            },
        )
        return True

    def get_adapter_name(self) -> str:
        return "logging"

    async def is_available(self) -> bool:
        return True


class EmailAdapter(NotificationAdapter):
    """
    Email notification adapter (placeholder for implementation)
    """

    def __init__(self, smtp_config: Dict[str, Any]):
        self.smtp_config = smtp_config
        # TODO: Initialize email client

    async def send_to_user(self, user_id: int, message: NotificationMessage) -> bool:
        # TODO: Implement email sending to user
        # 1. Look up user email from database
        # 2. Format email with template
        # 3. Send via SMTP/email service
        logger.info(f"Email adapter: Would send to user {user_id}")
        return True

    async def send_to_role(self, role: str, message: NotificationMessage) -> bool:
        # TODO: Implement email sending to role
        # 1. Look up all users with role
        # 2. Get their emails
        # 3. Send batch emails
        logger.info(f"Email adapter: Would send to role {role}")
        return True

    async def send_broadcast(
        self, message: NotificationMessage, user_ids: Optional[List[int]] = None
    ) -> bool:
        # TODO: Implement broadcast email
        logger.info(f"Email adapter: Would broadcast to {len(user_ids or [])} users")
        return True

    def get_adapter_name(self) -> str:
        return "email"

    async def is_available(self) -> bool:
        # TODO: Check SMTP connection
        return False


class SlackAdapter(NotificationAdapter):
    """
    Slack notification adapter (placeholder for implementation)
    """

    def __init__(self, webhook_url: str, bot_token: Optional[str] = None):
        self.webhook_url = webhook_url
        self.bot_token = bot_token
        # TODO: Initialize Slack client

    async def send_to_user(self, user_id: int, message: NotificationMessage) -> bool:
        # TODO: Implement Slack DM to user
        # 1. Look up user's Slack ID from database
        # 2. Send DM via Slack API
        logger.info(f"Slack adapter: Would send DM to user {user_id}")
        return True

    async def send_to_role(self, role: str, message: NotificationMessage) -> bool:
        # TODO: Implement Slack channel message
        # 1. Determine channel for role
        # 2. Post to channel
        logger.info(f"Slack adapter: Would post to #{role} channel")
        return True

    async def send_broadcast(
        self, message: NotificationMessage, user_ids: Optional[List[int]] = None
    ) -> bool:
        # TODO: Implement Slack broadcast
        logger.info(f"Slack adapter: Would broadcast message")
        return True

    def get_adapter_name(self) -> str:
        return "slack"

    async def is_available(self) -> bool:
        # TODO: Check Slack webhook/API availability
        return False


class SMSAdapter(NotificationAdapter):
    """
    SMS notification adapter using Twilio (placeholder for implementation)
    """

    def __init__(self, twilio_config: Dict[str, Any]):
        self.twilio_config = twilio_config
        # TODO: Initialize Twilio client

    async def send_to_user(self, user_id: int, message: NotificationMessage) -> bool:
        # TODO: Implement SMS sending
        # Only for HIGH and URGENT priority
        if message.priority not in [
            NotificationPriority.HIGH,
            NotificationPriority.URGENT,
        ]:
            return False

        logger.info(f"SMS adapter: Would send SMS to user {user_id}")
        return True

    async def send_to_role(self, role: str, message: NotificationMessage) -> bool:
        # TODO: Implement SMS to role members
        logger.info(f"SMS adapter: Would send SMS to role {role}")
        return True

    async def send_broadcast(
        self, message: NotificationMessage, user_ids: Optional[List[int]] = None
    ) -> bool:
        # SMS broadcast only for urgent messages
        if message.priority != NotificationPriority.URGENT:
            return False

        logger.info(f"SMS adapter: Would broadcast SMS")
        return True

    def get_adapter_name(self) -> str:
        return "sms"

    async def is_available(self) -> bool:
        # TODO: Check Twilio service status
        return False


class CompositeAdapter(NotificationAdapter):
    """
    Composite adapter that sends notifications through multiple channels
    """

    def __init__(self, adapters: List[NotificationAdapter], require_all: bool = False):
        """
        Args:
            adapters: List of notification adapters to use
            require_all: If True, all adapters must succeed. If False, at least one must succeed.
        """
        self.adapters = adapters
        self.require_all = require_all

    async def send_to_user(self, user_id: int, message: NotificationMessage) -> bool:
        results = []
        for adapter in self.adapters:
            try:
                if await adapter.is_available():
                    result = await adapter.send_to_user(user_id, message)
                    results.append(result)
            except Exception as e:
                logger.error(f"Error in {adapter.get_adapter_name()} adapter: {str(e)}")
                results.append(False)

        return all(results) if self.require_all else any(results)

    async def send_to_role(self, role: str, message: NotificationMessage) -> bool:
        results = []
        for adapter in self.adapters:
            try:
                if await adapter.is_available():
                    result = await adapter.send_to_role(role, message)
                    results.append(result)
            except Exception as e:
                logger.error(f"Error in {adapter.get_adapter_name()} adapter: {str(e)}")
                results.append(False)

        return all(results) if self.require_all else any(results)

    async def send_broadcast(
        self, message: NotificationMessage, user_ids: Optional[List[int]] = None
    ) -> bool:
        results = []
        for adapter in self.adapters:
            try:
                if await adapter.is_available():
                    result = await adapter.send_broadcast(message, user_ids)
                    results.append(result)
            except Exception as e:
                logger.error(f"Error in {adapter.get_adapter_name()} adapter: {str(e)}")
                results.append(False)

        return all(results) if self.require_all else any(results)

    def get_adapter_name(self) -> str:
        adapter_names = [a.get_adapter_name() for a in self.adapters]
        return f"composite({','.join(adapter_names)})"

    async def is_available(self) -> bool:
        availability = []
        for adapter in self.adapters:
            try:
                available = await adapter.is_available()
                availability.append(available)
            except Exception:
                availability.append(False)

        return all(availability) if self.require_all else any(availability)
