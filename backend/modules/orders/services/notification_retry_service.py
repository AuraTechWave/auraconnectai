# backend/modules/orders/services/notification_retry_service.py

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from core.database import get_db
from ..models.notification_config_models import (
    NotificationChannelConfig,
    NotificationRetryQueue,
    NotificationRetryStrategy,
    NotificationChannelStatus,
)
from ..models.order_tracking_models import OrderNotification, NotificationChannel
from core.notification_adapter import NotificationMessage, NotificationPriority


logger = logging.getLogger(__name__)


class NotificationRetryService:
    """Service for handling notification retries with configurable strategies"""

    def __init__(self, db: Session):
        self.db = db
        self._retry_tasks = {}

    async def queue_for_retry(
        self,
        notification: OrderNotification,
        error_message: str,
        channel_config: NotificationChannelConfig,
    ) -> NotificationRetryQueue:
        """
        Queue a failed notification for retry

        Args:
            notification: The failed notification
            error_message: Error message from the failure
            channel_config: Channel configuration

        Returns:
            Created retry queue entry
        """
        # Check if already in retry queue
        existing = (
            self.db.query(NotificationRetryQueue)
            .filter(
                and_(
                    NotificationRetryQueue.notification_id == notification.id,
                    NotificationRetryQueue.channel_name == notification.channel.value,
                    NotificationRetryQueue.is_abandoned == False,
                )
            )
            .first()
        )

        if existing:
            # Update existing retry entry
            existing.retry_count += 1
            existing.last_error = error_message
            existing.error_count += 1
            existing.last_retry_at = datetime.utcnow()

            # Calculate next retry time
            next_retry = self._calculate_next_retry(
                existing.retry_count, channel_config
            )

            if next_retry and existing.retry_count <= channel_config.max_retry_attempts:
                existing.next_retry_at = next_retry
            else:
                # Max retries exceeded, abandon
                existing.is_abandoned = True
                existing.abandoned_reason = (
                    f"Max retries ({channel_config.max_retry_attempts}) exceeded"
                )

            retry_entry = existing
        else:
            # Create new retry entry
            next_retry = self._calculate_next_retry(1, channel_config)

            retry_entry = NotificationRetryQueue(
                notification_id=notification.id,
                channel_name=notification.channel.value,
                retry_count=1,
                next_retry_at=next_retry,
                last_error=error_message,
                error_count=1,
                recipient=notification.recipient,
                subject=notification.subject,
                message=notification.message,
                metadata=notification.metadata,
            )
            self.db.add(retry_entry)

        # Update notification record
        notification.failed_at = datetime.utcnow()
        notification.error_message = error_message
        notification.retry_count = retry_entry.retry_count

        self.db.commit()
        return retry_entry

    def _calculate_next_retry(
        self, retry_count: int, config: NotificationChannelConfig
    ) -> Optional[datetime]:
        """
        Calculate next retry time based on strategy

        Args:
            retry_count: Current retry attempt number
            config: Channel configuration

        Returns:
            Next retry datetime or None if no retry
        """
        if retry_count > config.max_retry_attempts:
            return None

        strategy = config.retry_strategy
        base_delay = config.initial_retry_delay_seconds

        if strategy == NotificationRetryStrategy.EXPONENTIAL_BACKOFF:
            # Exponential backoff: delay * (multiplier ^ (retry_count - 1))
            delay = base_delay * (config.retry_backoff_multiplier ** (retry_count - 1))

        elif strategy == NotificationRetryStrategy.LINEAR_BACKOFF:
            # Linear backoff: delay * retry_count
            delay = base_delay * retry_count

        elif strategy == NotificationRetryStrategy.FIXED_DELAY:
            # Fixed delay
            delay = base_delay

        else:  # NO_RETRY
            return None

        # Cap at max delay
        delay = min(delay, config.max_retry_delay_seconds)

        return datetime.utcnow() + timedelta(seconds=delay)

    async def process_retry_queue(self, batch_size: int = 100):
        """
        Process pending retries in the queue

        Args:
            batch_size: Number of retries to process at once
        """
        # Get pending retries
        pending_retries = (
            self.db.query(NotificationRetryQueue)
            .filter(
                and_(
                    NotificationRetryQueue.next_retry_at <= datetime.utcnow(),
                    NotificationRetryQueue.is_abandoned == False,
                )
            )
            .limit(batch_size)
            .all()
        )

        if not pending_retries:
            return

        logger.info(f"Processing {len(pending_retries)} notification retries")

        # Group by channel for batch processing
        retries_by_channel = {}
        for retry in pending_retries:
            if retry.channel_name not in retries_by_channel:
                retries_by_channel[retry.channel_name] = []
            retries_by_channel[retry.channel_name].append(retry)

        # Process each channel
        for channel_name, channel_retries in retries_by_channel.items():
            await self._process_channel_retries(channel_name, channel_retries)

    async def _process_channel_retries(
        self, channel_name: str, retries: List[NotificationRetryQueue]
    ):
        """Process retries for a specific channel"""
        # Get channel config
        config = (
            self.db.query(NotificationChannelConfig)
            .filter(NotificationChannelConfig.channel_name == channel_name)
            .first()
        )

        if not config or not config.is_enabled:
            logger.warning(
                f"Channel {channel_name} not found or disabled, abandoning retries"
            )
            for retry in retries:
                retry.is_abandoned = True
                retry.abandoned_reason = "Channel disabled or not found"
            self.db.commit()
            return

        # Get adapter for channel
        adapter = self._get_adapter_for_channel(config)
        if not adapter:
            logger.error(f"No adapter found for channel {channel_name}")
            return

        # Process each retry
        for retry in retries:
            try:
                # Recreate notification message
                message = NotificationMessage(
                    subject=retry.subject,
                    message=retry.message,
                    metadata=retry.metadata,
                )

                # Attempt to send
                success = await self._send_with_adapter(
                    adapter, retry.recipient, message, config
                )

                if success:
                    # Success - remove from retry queue
                    self.db.delete(retry)

                    # Update original notification
                    notification = (
                        self.db.query(OrderNotification)
                        .filter(OrderNotification.id == retry.notification_id)
                        .first()
                    )

                    if notification:
                        notification.delivered_at = datetime.utcnow()
                        notification.retry_count = retry.retry_count
                else:
                    # Failed again - update retry
                    await self.queue_for_retry(
                        notification=self.db.query(OrderNotification)
                        .filter(OrderNotification.id == retry.notification_id)
                        .first(),
                        error_message="Retry failed",
                        channel_config=config,
                    )

            except Exception as e:
                logger.error(f"Error processing retry {retry.id}: {e}")
                retry.last_error = str(e)
                retry.error_count += 1

        self.db.commit()

    def _get_adapter_for_channel(self, config: NotificationChannelConfig):
        """Get the appropriate adapter for a channel configuration"""
        # This would be expanded to return actual adapters
        # For now, return a mock adapter
        from core.notification_adapter import LoggingAdapter

        return LoggingAdapter()

    async def _send_with_adapter(
        self,
        adapter,
        recipient: str,
        message: NotificationMessage,
        config: NotificationChannelConfig,
    ) -> bool:
        """Send notification with adapter and handle rate limiting"""
        # Check rate limits
        if not self._check_rate_limit(config):
            logger.warning(f"Rate limit exceeded for channel {config.channel_name}")
            return False

        try:
            # This would use the actual adapter methods based on channel type
            # For now, just log
            logger.info(
                f"Retrying notification to {recipient} via {config.channel_name}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return False

    def _check_rate_limit(self, config: NotificationChannelConfig) -> bool:
        """Check if sending is within rate limits"""
        if not any(
            [
                config.rate_limit_per_minute,
                config.rate_limit_per_hour,
                config.rate_limit_per_day,
            ]
        ):
            return True

        # Implementation would check NotificationChannelStats
        # For now, always allow
        return True

    async def cleanup_old_retries(self, days_to_keep: int = 7):
        """Clean up old abandoned retries"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

        deleted = (
            self.db.query(NotificationRetryQueue)
            .filter(
                or_(
                    NotificationRetryQueue.is_abandoned == True,
                    NotificationRetryQueue.created_at < cutoff_date,
                )
            )
            .delete()
        )

        self.db.commit()
        logger.info(f"Cleaned up {deleted} old retry entries")

    def get_retry_stats(self, channel_name: Optional[str] = None) -> Dict[str, Any]:
        """Get retry queue statistics"""
        query = self.db.query(NotificationRetryQueue)

        if channel_name:
            query = query.filter(NotificationRetryQueue.channel_name == channel_name)

        total = query.count()
        pending = query.filter(
            and_(
                NotificationRetryQueue.is_abandoned == False,
                NotificationRetryQueue.next_retry_at > datetime.utcnow(),
            )
        ).count()

        abandoned = query.filter(NotificationRetryQueue.is_abandoned == True).count()

        return {
            "total": total,
            "pending": pending,
            "abandoned": abandoned,
            "active": total - abandoned,
        }


class NotificationHealthChecker:
    """Service for checking health of notification channels"""

    def __init__(self, db: Session):
        self.db = db

    async def check_all_channels(self):
        """Check health of all notification channels"""
        channels = (
            self.db.query(NotificationChannelConfig)
            .filter(NotificationChannelConfig.is_enabled == True)
            .all()
        )

        for channel in channels:
            await self.check_channel_health(channel)

    async def check_channel_health(self, channel: NotificationChannelConfig):
        """Check health of a specific channel"""
        try:
            # Get adapter
            adapter = self._get_adapter_for_channel(channel)

            # Check if available
            is_available = await adapter.is_available()

            if is_available:
                channel.health_check_status = "healthy"
                channel.health_check_message = "Channel is operational"
                channel.consecutive_failures = 0
            else:
                channel.consecutive_failures += 1
                channel.health_check_status = "unhealthy"
                channel.health_check_message = "Channel is not available"

                # Auto-disable if too many failures
                if (
                    channel.auto_disable_after_failures
                    and channel.consecutive_failures
                    >= channel.auto_disable_after_failures
                ):
                    channel.is_enabled = False
                    channel.status = NotificationChannelStatus.FAILED
                    logger.error(
                        f"Auto-disabled channel {channel.channel_name} after {channel.consecutive_failures} failures"
                    )

            channel.last_health_check = datetime.utcnow()
            self.db.commit()

        except Exception as e:
            logger.error(f"Health check failed for channel {channel.channel_name}: {e}")
            channel.consecutive_failures += 1
            channel.health_check_status = "error"
            channel.health_check_message = str(e)
            channel.last_health_check = datetime.utcnow()
            self.db.commit()

    def _get_adapter_for_channel(self, channel: NotificationChannelConfig):
        """Get adapter for channel"""
        # This would return actual adapters based on config
        from core.notification_adapter import LoggingAdapter

        return LoggingAdapter()


# Background task to process retry queue
async def process_notification_retries():
    """Background task to process notification retry queue"""
    while True:
        try:
            async with get_db() as db:
                retry_service = NotificationRetryService(db)
                await retry_service.process_retry_queue()

                # Also run cleanup occasionally
                import random

                if random.random() < 0.01:  # 1% chance
                    await retry_service.cleanup_old_retries()

            # Wait before next batch
            await asyncio.sleep(60)  # Check every minute

        except Exception as e:
            logger.error(f"Error in retry processor: {e}")
            await asyncio.sleep(300)  # Wait 5 minutes on error


# Background task for health checks
async def check_notification_health():
    """Background task to check notification channel health"""
    while True:
        try:
            async with get_db() as db:
                health_checker = NotificationHealthChecker(db)
                await health_checker.check_all_channels()

            # Wait 5 minutes between health checks
            await asyncio.sleep(300)

        except Exception as e:
            logger.error(f"Error in health checker: {e}")
            await asyncio.sleep(600)  # Wait 10 minutes on error
