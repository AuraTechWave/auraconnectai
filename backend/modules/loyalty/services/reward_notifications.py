# backend/modules/loyalty/services/reward_notifications.py

from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging
from enum import Enum

from modules.customers.models.customer_models import Customer, CustomerNotification
from ..models.rewards_models import CustomerReward, RewardTemplate
from modules.customers.models.loyalty_config import LoyaltyTierConfig


logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Types of reward notifications"""

    REWARD_EARNED = "reward_earned"
    REWARD_EXPIRING = "reward_expiring"
    POINTS_EARNED = "points_earned"
    TIER_UPGRADE = "tier_upgrade"
    MILESTONE_ACHIEVED = "milestone_achieved"
    CAMPAIGN_REWARD = "campaign_reward"


class NotificationChannel(str, Enum):
    """Notification delivery channels"""

    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"


class RewardNotificationService:
    """Service for sending reward-related notifications to customers"""

    def __init__(self, db: Session):
        self.db = db

    def notify_reward_earned(
        self,
        customer_id: int,
        reward: CustomerReward,
        trigger_context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Notify customer about a newly earned reward"""
        try:
            customer = (
                self.db.query(Customer).filter(Customer.id == customer_id).first()
            )
            if not customer:
                logger.error(
                    f"Customer {customer_id} not found for reward notification"
                )
                return False

            # Check customer's communication preferences
            if not self._should_send_notification(
                customer, NotificationType.REWARD_EARNED
            ):
                logger.info(
                    f"Skipping reward notification for customer {customer_id} due to preferences"
                )
                return True

            # Create notification content
            subject = f"🎉 You've earned a new reward: {reward.title}!"
            content = self._build_reward_earned_content(reward, trigger_context)

            # Send through preferred channels
            channels = self._get_preferred_channels(
                customer, NotificationType.REWARD_EARNED
            )

            success = True
            for channel in channels:
                try:
                    notification_sent = self._send_notification(
                        customer=customer,
                        channel=channel,
                        notification_type=NotificationType.REWARD_EARNED,
                        subject=subject,
                        content=content,
                        metadata={
                            "reward_id": reward.id,
                            "reward_code": reward.code,
                            "reward_type": reward.reward_type.value,
                        },
                    )

                    if not notification_sent:
                        success = False

                except Exception as e:
                    logger.error(
                        f"Failed to send reward notification via {channel}: {str(e)}"
                    )
                    success = False

            return success

        except Exception as e:
            logger.error(f"Error sending reward earned notification: {str(e)}")
            return False

    def notify_points_earned(
        self,
        customer_id: int,
        points_earned: int,
        reason: str,
        order_id: Optional[int] = None,
    ) -> bool:
        """Notify customer about points earned"""
        try:
            customer = (
                self.db.query(Customer).filter(Customer.id == customer_id).first()
            )
            if not customer:
                return False

            if not self._should_send_notification(
                customer, NotificationType.POINTS_EARNED
            ):
                return True

            # Only send points notifications for significant amounts or milestones
            if points_earned < 50 and customer.loyalty_points % 500 != 0:
                return True

            subject = f"💎 You earned {points_earned} loyalty points!"
            content = self._build_points_earned_content(
                customer, points_earned, reason, order_id
            )

            channels = self._get_preferred_channels(
                customer, NotificationType.POINTS_EARNED
            )

            success = True
            for channel in channels:
                try:
                    self._send_notification(
                        customer=customer,
                        channel=channel,
                        notification_type=NotificationType.POINTS_EARNED,
                        subject=subject,
                        content=content,
                        metadata={
                            "points_earned": points_earned,
                            "total_points": customer.loyalty_points,
                            "order_id": order_id,
                            "reason": reason,
                        },
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to send points notification via {channel}: {str(e)}"
                    )
                    success = False

            return success

        except Exception as e:
            logger.error(f"Error sending points earned notification: {str(e)}")
            return False

    def notify_tier_upgrade(
        self,
        customer_id: int,
        old_tier: str,
        new_tier: str,
        tier_benefits: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Notify customer about tier upgrade"""
        try:
            customer = (
                self.db.query(Customer).filter(Customer.id == customer_id).first()
            )
            if not customer:
                return False

            if not self._should_send_notification(
                customer, NotificationType.TIER_UPGRADE
            ):
                return True

            subject = (
                f"🌟 Congratulations! You've been upgraded to {new_tier.title()} tier!"
            )
            content = self._build_tier_upgrade_content(
                customer, old_tier, new_tier, tier_benefits
            )

            # Tier upgrades are important, send via all channels
            channels = [NotificationChannel.EMAIL, NotificationChannel.IN_APP]
            if (
                customer.communication_preferences
                and customer.communication_preferences.get("sms", False)
            ):
                channels.append(NotificationChannel.SMS)

            success = True
            for channel in channels:
                try:
                    self._send_notification(
                        customer=customer,
                        channel=channel,
                        notification_type=NotificationType.TIER_UPGRADE,
                        subject=subject,
                        content=content,
                        metadata={
                            "old_tier": old_tier,
                            "new_tier": new_tier,
                            "tier_benefits": tier_benefits,
                        },
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to send tier upgrade notification via {channel}: {str(e)}"
                    )
                    success = False

            return success

        except Exception as e:
            logger.error(f"Error sending tier upgrade notification: {str(e)}")
            return False

    def notify_rewards_expiring(self, days_ahead: int = 7) -> Dict[str, Any]:
        """Send notifications for rewards expiring soon"""
        try:
            cutoff_date = datetime.utcnow() + timedelta(days=days_ahead)

            # Get rewards expiring soon
            expiring_rewards = (
                self.db.query(CustomerReward)
                .filter(
                    CustomerReward.status == "available",
                    CustomerReward.valid_until <= cutoff_date,
                    CustomerReward.valid_until > datetime.utcnow(),
                )
                .all()
            )

            # Group by customer
            customer_rewards = {}
            for reward in expiring_rewards:
                if reward.customer_id not in customer_rewards:
                    customer_rewards[reward.customer_id] = []
                customer_rewards[reward.customer_id].append(reward)

            notifications_sent = 0
            failures = 0

            for customer_id, rewards in customer_rewards.items():
                try:
                    customer = (
                        self.db.query(Customer)
                        .filter(Customer.id == customer_id)
                        .first()
                    )
                    if not customer:
                        continue

                    if not self._should_send_notification(
                        customer, NotificationType.REWARD_EXPIRING
                    ):
                        continue

                    # Create notification for expiring rewards
                    subject = f"⏰ {len(rewards)} reward(s) expiring soon!"
                    content = self._build_expiring_rewards_content(
                        customer, rewards, days_ahead
                    )

                    channels = self._get_preferred_channels(
                        customer, NotificationType.REWARD_EXPIRING
                    )

                    for channel in channels:
                        self._send_notification(
                            customer=customer,
                            channel=channel,
                            notification_type=NotificationType.REWARD_EXPIRING,
                            subject=subject,
                            content=content,
                            metadata={
                                "expiring_rewards_count": len(rewards),
                                "days_until_expiry": days_ahead,
                                "reward_codes": [r.code for r in rewards],
                            },
                        )

                    notifications_sent += 1

                except Exception as e:
                    logger.error(
                        f"Failed to send expiring rewards notification to customer {customer_id}: {str(e)}"
                    )
                    failures += 1

            logger.info(
                f"Expiring rewards notifications: {notifications_sent} sent, {failures} failed"
            )

            return {
                "success": True,
                "notifications_sent": notifications_sent,
                "failures": failures,
                "customers_notified": len(customer_rewards),
            }

        except Exception as e:
            logger.error(f"Error sending expiring rewards notifications: {str(e)}")
            return {"success": False, "error": str(e)}

    def notify_milestone_achieved(
        self,
        customer_id: int,
        milestone_type: str,
        milestone_value: Any,
        rewards_triggered: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """Notify customer about achieving a milestone"""
        try:
            customer = (
                self.db.query(Customer).filter(Customer.id == customer_id).first()
            )
            if not customer:
                return False

            if not self._should_send_notification(
                customer, NotificationType.MILESTONE_ACHIEVED
            ):
                return True

            subject = f"🏆 Milestone Achieved: {self._format_milestone_title(milestone_type, milestone_value)}"
            content = self._build_milestone_content(
                customer, milestone_type, milestone_value, rewards_triggered
            )

            channels = self._get_preferred_channels(
                customer, NotificationType.MILESTONE_ACHIEVED
            )

            success = True
            for channel in channels:
                try:
                    self._send_notification(
                        customer=customer,
                        channel=channel,
                        notification_type=NotificationType.MILESTONE_ACHIEVED,
                        subject=subject,
                        content=content,
                        metadata={
                            "milestone_type": milestone_type,
                            "milestone_value": milestone_value,
                            "rewards_triggered": rewards_triggered,
                        },
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to send milestone notification via {channel}: {str(e)}"
                    )
                    success = False

            return success

        except Exception as e:
            logger.error(f"Error sending milestone notification: {str(e)}")
            return False

    def send_birthday_rewards(self) -> Dict[str, Any]:
        """Send birthday rewards and notifications"""
        try:
            from datetime import date

            today = date.today()

            # Find customers with birthdays today
            birthday_customers = (
                self.db.query(Customer)
                .filter(
                    Customer.date_of_birth.isnot(None), Customer.deleted_at.is_(None)
                )
                .all()
            )

            birthday_customers = [
                c
                for c in birthday_customers
                if c.date_of_birth
                and c.date_of_birth.month == today.month
                and c.date_of_birth.day == today.day
            ]

            notifications_sent = 0
            rewards_issued = 0

            # Get birthday reward template
            birthday_template = (
                self.db.query(RewardTemplate)
                .filter(
                    RewardTemplate.trigger_type == "birthday",
                    RewardTemplate.is_active == True,
                )
                .first()
            )

            for customer in birthday_customers:
                try:
                    # Issue birthday reward if template exists
                    if birthday_template:
                        from .rewards_engine import RewardsEngine

                        rewards_engine = RewardsEngine(self.db)

                        try:
                            reward = rewards_engine.issue_reward_to_customer(
                                customer_id=customer.id,
                                template_id=birthday_template.id,
                                custom_data={"birthday": True},
                            )
                            rewards_issued += 1

                            # Send birthday notification with reward
                            self._send_birthday_notification_with_reward(
                                customer, reward
                            )

                        except Exception as e:
                            # Still send birthday notification even if reward fails
                            logger.warning(
                                f"Failed to issue birthday reward to customer {customer.id}: {str(e)}"
                            )
                            self._send_birthday_notification(customer)
                    else:
                        # Send birthday notification without reward
                        self._send_birthday_notification(customer)

                    notifications_sent += 1

                except Exception as e:
                    logger.error(
                        f"Failed to process birthday for customer {customer.id}: {str(e)}"
                    )

            logger.info(
                f"Birthday processing: {notifications_sent} notifications sent, {rewards_issued} rewards issued"
            )

            return {
                "success": True,
                "notifications_sent": notifications_sent,
                "rewards_issued": rewards_issued,
                "birthday_customers": len(birthday_customers),
            }

        except Exception as e:
            logger.error(f"Error processing birthday rewards: {str(e)}")
            return {"success": False, "error": str(e)}

    # Private helper methods

    def _should_send_notification(
        self, customer: Customer, notification_type: NotificationType
    ) -> bool:
        """Check if customer wants to receive this type of notification"""
        if (
            not customer.marketing_opt_in
            and notification_type != NotificationType.TIER_UPGRADE
        ):
            return False

        prefs = customer.communication_preferences or {}

        # Check specific preferences
        type_prefs = {
            NotificationType.REWARD_EARNED: prefs.get("rewards", True),
            NotificationType.POINTS_EARNED: prefs.get("points", True),
            NotificationType.TIER_UPGRADE: True,  # Always send tier upgrades
            NotificationType.REWARD_EXPIRING: prefs.get("expiring_rewards", True),
            NotificationType.MILESTONE_ACHIEVED: prefs.get("milestones", True),
            NotificationType.CAMPAIGN_REWARD: prefs.get("campaigns", True),
        }

        return type_prefs.get(notification_type, True)

    def _get_preferred_channels(
        self, customer: Customer, notification_type: NotificationType
    ) -> List[NotificationChannel]:
        """Get customer's preferred notification channels for this type"""
        channels = [NotificationChannel.IN_APP]  # Always include in-app

        prefs = customer.communication_preferences or {}

        if prefs.get("email", True) and customer.email_verified:
            channels.append(NotificationChannel.EMAIL)

        if prefs.get("sms", False) and customer.phone_verified:
            channels.append(NotificationChannel.SMS)

        # Important notifications go via all available channels
        if notification_type == NotificationType.TIER_UPGRADE:
            if customer.email_verified and NotificationChannel.EMAIL not in channels:
                channels.append(NotificationChannel.EMAIL)

        return channels

    def _send_notification(
        self,
        customer: Customer,
        channel: NotificationChannel,
        notification_type: NotificationType,
        subject: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send notification via specific channel"""
        try:
            # Create notification record
            notification = CustomerNotification(
                customer_id=customer.id,
                type=notification_type.value,
                channel=channel.value,
                subject=subject,
                content=content,
                metadata=metadata or {},
            )

            self.db.add(notification)
            self.db.commit()

            # Here you would integrate with actual notification services
            # For now, just log the notification
            logger.info(
                f"Notification sent to customer {customer.id} via {channel.value}: {subject}"
            )

            # Mark as sent
            notification.status = "sent"
            notification.sent_at = datetime.utcnow()
            self.db.commit()

            return True

        except Exception as e:
            logger.error(f"Failed to send notification via {channel.value}: {str(e)}")
            return False

    def _build_reward_earned_content(
        self, reward: CustomerReward, trigger_context: Optional[Dict[str, Any]]
    ) -> str:
        """Build content for reward earned notification"""
        content = f"Great news, {reward.customer.first_name}!\n\n"
        content += f"You've earned a new reward: **{reward.title}**\n\n"

        if reward.description:
            content += f"{reward.description}\n\n"

        content += f"**Reward Code:** {reward.code}\n"
        content += f"**Valid Until:** {reward.valid_until.strftime('%B %d, %Y')}\n\n"

        if reward.points_cost and reward.points_cost > 0:
            content += f"This reward costs {reward.points_cost} points to redeem.\n"

        if trigger_context and trigger_context.get("order_id"):
            content += f"\nThis reward was earned from your recent order (#{trigger_context['order_id']}).\n"

        content += "\nUse this reward on your next order to save money!"

        return content

    def _build_points_earned_content(
        self,
        customer: Customer,
        points_earned: int,
        reason: str,
        order_id: Optional[int],
    ) -> str:
        """Build content for points earned notification"""
        content = f"Hi {customer.first_name}!\n\n"
        content += f"You've earned **{points_earned} loyalty points**!\n\n"
        content += f"**Reason:** {reason}\n"
        content += f"**Your Current Balance:** {customer.loyalty_points} points\n"
        content += f"**Lifetime Points:** {customer.lifetime_points} points\n\n"

        if order_id:
            content += f"These points were earned from order #{order_id}.\n\n"

        # Add tier progress
        content += self._get_tier_progress_text(customer)

        return content

    def _build_tier_upgrade_content(
        self,
        customer: Customer,
        old_tier: str,
        new_tier: str,
        tier_benefits: Optional[Dict[str, Any]],
    ) -> str:
        """Build content for tier upgrade notification"""
        content = f"🎉 Congratulations, {customer.first_name}!\n\n"
        content += f"You've been upgraded from **{old_tier.title()}** to **{new_tier.title()}** tier!\n\n"

        if tier_benefits:
            content += "**Your new benefits include:**\n"
            for benefit, value in tier_benefits.items():
                if benefit == "point_multiplier":
                    content += f"• {value}x points on all purchases\n"
                elif benefit == "free_delivery":
                    content += "• Free delivery on all orders\n"
                elif benefit == "birthday_bonus":
                    content += f"• {value} bonus points on your birthday\n"
                elif benefit == "priority_support":
                    content += "• Priority customer support\n"

        content += f"\nYour current balance: {customer.loyalty_points} points\n"
        content += "Thank you for your loyalty!"

        return content

    def _build_expiring_rewards_content(
        self, customer: Customer, rewards: List[CustomerReward], days_ahead: int
    ) -> str:
        """Build content for expiring rewards notification"""
        content = f"Hi {customer.first_name}!\n\n"

        if len(rewards) == 1:
            reward = rewards[0]
            content += f"Your reward **{reward.title}** (code: {reward.code}) is expiring in {days_ahead} days.\n\n"
        else:
            content += f"You have {len(rewards)} rewards expiring in the next {days_ahead} days:\n\n"
            for reward in rewards:
                content += f"• **{reward.title}** (code: {reward.code}) - expires {reward.valid_until.strftime('%B %d')}\n"

        content += "\nDon't let these rewards go to waste! Use them on your next order."

        return content

    def _build_milestone_content(
        self,
        customer: Customer,
        milestone_type: str,
        milestone_value: Any,
        rewards_triggered: Optional[List[Dict[str, Any]]],
    ) -> str:
        """Build content for milestone achievement notification"""
        content = f"🏆 Amazing, {customer.first_name}!\n\n"
        content += f"You've reached a special milestone: {self._format_milestone_title(milestone_type, milestone_value)}\n\n"

        if rewards_triggered:
            content += "As a reward for this achievement, you've earned:\n"
            for reward in rewards_triggered:
                content += f"• **{reward['title']}** (code: {reward.get('reward_code', 'N/A')})\n"
            content += "\n"

        content += "Thank you for being such a loyal customer!"

        return content

    def _format_milestone_title(self, milestone_type: str, milestone_value: Any) -> str:
        """Format milestone title for display"""
        if milestone_type == "total_orders":
            return f"{milestone_value} orders placed"
        elif milestone_type == "total_spent":
            return f"${milestone_value} total spent"
        elif milestone_type == "lifetime_points":
            return f"{milestone_value} lifetime points earned"
        else:
            return f"{milestone_type}: {milestone_value}"

    def _get_tier_progress_text(self, customer: Customer) -> str:
        """Get text showing progress to next tier"""
        tier_points_map = {
            "bronze": 0,
            "silver": 1000,
            "gold": 2500,
            "platinum": 5000,
            "vip": 10000,
        }
        current_tier_points = tier_points_map.get(customer.tier.value.lower(), 0)

        next_tier = None
        next_tier_points = None

        for tier, points in tier_points_map.items():
            if points > customer.lifetime_points:
                next_tier = tier
                next_tier_points = points
                break

        if next_tier:
            points_needed = next_tier_points - customer.lifetime_points
            return f"You need {points_needed} more points to reach {next_tier.title()} tier!"
        else:
            return "You've reached the highest tier - VIP! 🌟"

    def _send_birthday_notification(self, customer: Customer):
        """Send birthday notification without reward"""
        subject = f"🎂 Happy Birthday, {customer.first_name}!"
        content = f"Happy Birthday, {customer.first_name}!\n\n"
        content += (
            "We hope you have a wonderful day filled with joy and celebration.\n\n"
        )
        content += "Thank you for being a valued customer!"

        self._send_notification(
            customer=customer,
            channel=NotificationChannel.EMAIL,
            notification_type=NotificationType.MILESTONE_ACHIEVED,
            subject=subject,
            content=content,
            metadata={"birthday": True},
        )

    def _send_birthday_notification_with_reward(
        self, customer: Customer, reward: CustomerReward
    ):
        """Send birthday notification with reward"""
        subject = f"🎂🎁 Happy Birthday, {customer.first_name}! You've got a gift!"
        content = f"Happy Birthday, {customer.first_name}!\n\n"
        content += (
            "To celebrate your special day, we've got a birthday gift for you:\n\n"
        )
        content += f"**{reward.title}**\n"
        content += f"**Reward Code:** {reward.code}\n"
        content += f"**Valid Until:** {reward.valid_until.strftime('%B %d, %Y')}\n\n"
        content += "Enjoy your special day and your birthday treat!"

        self._send_notification(
            customer=customer,
            channel=NotificationChannel.EMAIL,
            notification_type=NotificationType.MILESTONE_ACHIEVED,
            subject=subject,
            content=content,
            metadata={"birthday": True, "reward_id": reward.id},
        )
