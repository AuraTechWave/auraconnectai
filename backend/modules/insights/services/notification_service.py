# backend/modules/insights/services/notification_service.py

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import asyncio
import aiohttp
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

from ..models.insight_models import (
    Insight,
    InsightNotificationRule,
    NotificationChannel,
    InsightSeverity,
    InsightStatus,
)
from ..schemas.insight_schemas import NotificationRuleCreate, NotificationRuleUpdate

logger = logging.getLogger(__name__)


class InsightNotificationService:
    """Service for sending insight notifications"""

    def __init__(self, db: Session):
        self.db = db

        # These would come from settings/environment
        self.smtp_config = {
            "host": "",  # Will be configured via settings module
            "port": 587,
            "username": "",
            "password": "",
            "use_tls": True,
        }

        self.slack_config = {"webhook_url": "", "default_channel": "#insights"}

        self.frontend_url = "http://localhost:3000"

        # Rate limiting tracking
        self.sent_notifications: Dict[int, List[datetime]] = {}

    async def process_new_insight(self, insight: Insight):
        """Process notifications for a new insight"""

        # Get applicable notification rules
        rules = self._get_applicable_rules(insight)

        for rule in rules:
            # Check rate limits
            if not self._check_rate_limits(
                rule.id, rule.max_per_hour, rule.max_per_day
            ):
                logger.warning(f"Rate limit exceeded for rule {rule.id}")
                continue

            # Send notifications
            if rule.immediate:
                await self._send_immediate_notifications(insight, rule)
            else:
                await self._queue_batch_notification(insight, rule)

    def _get_applicable_rules(self, insight: Insight) -> List[InsightNotificationRule]:
        """Get notification rules that apply to this insight"""

        all_rules = (
            self.db.query(InsightNotificationRule)
            .filter(
                InsightNotificationRule.restaurant_id == insight.restaurant_id,
                InsightNotificationRule.is_active == True,
            )
            .all()
        )

        applicable_rules = []

        for rule in all_rules:
            # Check domain
            if rule.domains and insight.domain not in rule.domains:
                continue

            # Check type
            if rule.types and insight.type not in rule.types:
                continue

            # Check severity
            if rule.min_severity:
                severity_order = {
                    InsightSeverity.INFO: 0,
                    InsightSeverity.LOW: 1,
                    InsightSeverity.MEDIUM: 2,
                    InsightSeverity.HIGH: 3,
                    InsightSeverity.CRITICAL: 4,
                }

                if severity_order.get(insight.severity, 0) < severity_order.get(
                    rule.min_severity, 0
                ):
                    continue

            # Check impact score
            if rule.min_impact_score and (
                not insight.impact_score or insight.impact_score < rule.min_impact_score
            ):
                continue

            # Check estimated value
            if rule.min_estimated_value and (
                not insight.estimated_value
                or insight.estimated_value < rule.min_estimated_value
            ):
                continue

            applicable_rules.append(rule)

        return applicable_rules

    def _check_rate_limits(
        self, rule_id: int, max_per_hour: Optional[int], max_per_day: Optional[int]
    ) -> bool:
        """Check if sending notification would exceed rate limits"""

        now = datetime.utcnow()

        # Get notification history for this rule
        if rule_id not in self.sent_notifications:
            self.sent_notifications[rule_id] = []

        notifications = self.sent_notifications[rule_id]

        # Clean old entries
        day_ago = now - timedelta(days=1)
        notifications = [n for n in notifications if n > day_ago]
        self.sent_notifications[rule_id] = notifications

        # Check hourly limit
        if max_per_hour:
            hour_ago = now - timedelta(hours=1)
            hourly_count = sum(1 for n in notifications if n > hour_ago)
            if hourly_count >= max_per_hour:
                return False

        # Check daily limit
        if max_per_day:
            daily_count = len(notifications)
            if daily_count >= max_per_day:
                return False

        return True

    async def _send_immediate_notifications(
        self, insight: Insight, rule: InsightNotificationRule
    ):
        """Send immediate notifications through configured channels"""

        tasks = []

        for channel in rule.channels:
            recipients = rule.recipients.get(channel, [])

            if channel == NotificationChannel.EMAIL:
                tasks.append(self._send_email_notification(insight, recipients))
            elif channel == NotificationChannel.SLACK:
                tasks.append(self._send_slack_notification(insight, recipients))
            elif channel == NotificationChannel.WEBHOOK:
                tasks.append(self._send_webhook_notification(insight, recipients))
            elif channel == NotificationChannel.SMS:
                tasks.append(self._send_sms_notification(insight, recipients))

        # Send all notifications concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Track successful sends
        for i, result in enumerate(results):
            if not isinstance(result, Exception):
                self.sent_notifications.setdefault(rule.id, []).append(
                    datetime.utcnow()
                )

        # Update insight with notification status
        notification_status = insight.notifications_sent or {}
        for channel in rule.channels:
            notification_status[channel] = datetime.utcnow().isoformat()
        insight.notifications_sent = notification_status

    async def _send_email_notification(self, insight: Insight, recipients: List[str]):
        """Send email notification"""

        if not recipients or not self.smtp_config["host"]:
            return

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[{insight.severity.upper()}] {insight.title}"
            msg["From"] = self.smtp_config["username"]
            msg["To"] = ", ".join(recipients)

            # Create HTML content
            html = self._create_email_html(insight)
            msg.attach(MIMEText(html, "html"))

            # Send email
            with smtplib.SMTP(
                self.smtp_config["host"], self.smtp_config["port"]
            ) as server:
                if self.smtp_config["use_tls"]:
                    server.starttls()
                if self.smtp_config["username"]:
                    server.login(
                        self.smtp_config["username"], self.smtp_config["password"]
                    )
                server.send_message(msg)

            logger.info(
                f"Email sent for insight {insight.id} to {len(recipients)} recipients"
            )

        except Exception as e:
            logger.error(f"Failed to send email for insight {insight.id}: {e}")
            raise

    async def _send_slack_notification(self, insight: Insight, channels: List[str]):
        """Send Slack notification"""

        if not self.slack_config["webhook_url"]:
            return

        # Use provided channels or default
        target_channels = channels or [self.slack_config["default_channel"]]

        # Create Slack message
        message = self._create_slack_message(insight)

        async with aiohttp.ClientSession() as session:
            for channel in target_channels:
                payload = {**message, "channel": channel}

                try:
                    async with session.post(
                        self.slack_config["webhook_url"], json=payload
                    ) as response:
                        if response.status != 200:
                            raise Exception(f"Slack API returned {response.status}")

                    logger.info(
                        f"Slack notification sent for insight {insight.id} to {channel}"
                    )

                except Exception as e:
                    logger.error(f"Failed to send Slack notification: {e}")
                    raise

    async def _send_webhook_notification(self, insight: Insight, webhooks: List[str]):
        """Send webhook notifications"""

        payload = self._create_webhook_payload(insight)

        async with aiohttp.ClientSession() as session:
            for webhook_url in webhooks:
                try:
                    async with session.post(
                        webhook_url,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as response:
                        if response.status >= 400:
                            raise Exception(f"Webhook returned {response.status}")

                    logger.info(
                        f"Webhook sent for insight {insight.id} to {webhook_url}"
                    )

                except Exception as e:
                    logger.error(f"Failed to send webhook to {webhook_url}: {e}")
                    raise

    async def _send_sms_notification(self, insight: Insight, phone_numbers: List[str]):
        """Send SMS notification (placeholder)"""

        # TODO: Implement SMS provider integration (Twilio, etc.)
        logger.info(
            f"SMS notification would be sent for insight {insight.id} to {len(phone_numbers)} numbers"
        )

    def _create_email_html(self, insight: Insight) -> str:
        """Create HTML content for email"""

        severity_colors = {
            InsightSeverity.CRITICAL: "#dc3545",
            InsightSeverity.HIGH: "#fd7e14",
            InsightSeverity.MEDIUM: "#ffc107",
            InsightSeverity.LOW: "#28a745",
            InsightSeverity.INFO: "#17a2b8",
        }

        recommendations_html = ""
        if insight.recommendations:
            recommendations_html = "<h3>Recommendations:</h3><ul>"
            for rec in insight.recommendations:
                recommendations_html += f"<li>{rec}</li>"
            recommendations_html += "</ul>"

        return f"""
        <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto;">
                    <div style="background-color: {severity_colors.get(insight.severity, '#6c757d')}; 
                               color: white; padding: 10px; border-radius: 5px;">
                        <h2 style="margin: 0;">{insight.title}</h2>
                        <p style="margin: 5px 0;">
                            {insight.type.value.title()} | {insight.domain.value.title()} | 
                            Impact Score: {insight.impact_score or 'N/A'}
                        </p>
                    </div>
                    
                    <div style="padding: 20px 0;">
                        <p>{insight.description}</p>
                        
                        {f'<p><strong>Estimated Value:</strong> ${insight.estimated_value:,.2f}</p>' 
                         if insight.estimated_value else ''}
                        
                        {recommendations_html}
                        
                        <div style="margin-top: 20px;">
                            <a href="{self.frontend_url}/insights/{insight.id}" 
                               style="background-color: #007bff; color: white; padding: 10px 20px; 
                                      text-decoration: none; border-radius: 5px;">
                                View Details
                            </a>
                        </div>
                    </div>
                    
                    <div style="border-top: 1px solid #dee2e6; margin-top: 30px; padding-top: 10px; 
                               font-size: 12px; color: #6c757d;">
                        Generated by AuraConnect AI | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
                    </div>
                </div>
            </body>
        </html>
        """

    def _create_slack_message(self, insight: Insight) -> Dict[str, Any]:
        """Create Slack message format"""

        severity_emojis = {
            InsightSeverity.CRITICAL: "🚨",
            InsightSeverity.HIGH: "⚠️",
            InsightSeverity.MEDIUM: "📊",
            InsightSeverity.LOW: "💡",
            InsightSeverity.INFO: "ℹ️",
        }

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{severity_emojis.get(insight.severity, '📌')} {insight.title}",
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": insight.description},
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Type:* {insight.type.value} | *Domain:* {insight.domain.value} | "
                        f"*Severity:* {insight.severity.value}",
                    }
                ],
            },
        ]

        # Add metrics if available
        if insight.impact_score or insight.estimated_value:
            fields = []
            if insight.impact_score:
                fields.append(
                    {
                        "type": "mrkdwn",
                        "text": f"*Impact Score:* {insight.impact_score}/100",
                    }
                )
            if insight.estimated_value:
                fields.append(
                    {
                        "type": "mrkdwn",
                        "text": f"*Est. Value:* ${insight.estimated_value:,.2f}",
                    }
                )

            blocks.append({"type": "section", "fields": fields})

        # Add recommendations
        if insight.recommendations:
            rec_text = "*Recommendations:*\n"
            for i, rec in enumerate(insight.recommendations[:5], 1):
                rec_text += f"{i}. {rec}\n"

            blocks.append(
                {"type": "section", "text": {"type": "mrkdwn", "text": rec_text}}
            )

        # Add action button
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Details"},
                        "url": f"{self.frontend_url}/insights/{insight.id}",
                        "style": "primary",
                    }
                ],
            }
        )

        return {"blocks": blocks}

    def _create_webhook_payload(self, insight: Insight) -> Dict[str, Any]:
        """Create webhook payload"""

        return {
            "event_type": "insight_generated",
            "timestamp": datetime.utcnow().isoformat(),
            "insight": {
                "id": insight.id,
                "restaurant_id": insight.restaurant_id,
                "type": insight.type,
                "severity": insight.severity,
                "domain": insight.domain,
                "status": insight.status,
                "title": insight.title,
                "description": insight.description,
                "impact_score": (
                    float(insight.impact_score) if insight.impact_score else None
                ),
                "estimated_value": (
                    float(insight.estimated_value) if insight.estimated_value else None
                ),
                "recommendations": insight.recommendations,
                "metrics": insight.metrics,
                "generated_at": insight.created_at.isoformat(),
            },
        }

    async def _queue_batch_notification(
        self, insight: Insight, rule: InsightNotificationRule
    ):
        """Queue insight for batch notification"""

        # TODO: Implement batch notification queueing
        # This would typically use a task queue like Celery or a database table
        logger.info(
            f"Insight {insight.id} queued for batch notification via rule {rule.id}"
        )

    async def send_batch_notifications(self, restaurant_id: int):
        """Send batch notifications for queued insights"""

        # TODO: Implement batch notification sending
        # This would be called by a scheduled task
        logger.info(f"Sending batch notifications for restaurant {restaurant_id}")

    # CRUD operations for notification rules

    def create_rule(
        self, rule_data: NotificationRuleCreate, restaurant_id: int
    ) -> InsightNotificationRule:
        """Create a new notification rule"""
        rule = InsightNotificationRule(
            restaurant_id=restaurant_id,
            name=rule_data.name,
            description=rule_data.description,
            domains=rule_data.domains,
            types=rule_data.types,
            min_severity=rule_data.min_severity,
            min_impact_score=rule_data.min_impact_score,
            min_estimated_value=rule_data.min_estimated_value,
            channels=rule_data.channels,
            recipients=rule_data.recipients,
            immediate=rule_data.immediate,
            batch_hours=rule_data.batch_hours,
            max_per_hour=rule_data.max_per_hour,
            max_per_day=rule_data.max_per_day,
        )

        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)

        return rule

    def list_rules(
        self, restaurant_id: int, is_active: Optional[bool] = None
    ) -> List[InsightNotificationRule]:
        """List notification rules"""
        query = self.db.query(InsightNotificationRule).filter(
            InsightNotificationRule.restaurant_id == restaurant_id
        )

        if is_active is not None:
            query = query.filter(InsightNotificationRule.is_active == is_active)

        return query.all()

    def update_rule(
        self, rule_id: int, update_data: NotificationRuleUpdate, restaurant_id: int
    ) -> Optional[InsightNotificationRule]:
        """Update a notification rule"""
        rule = (
            self.db.query(InsightNotificationRule)
            .filter(
                InsightNotificationRule.id == rule_id,
                InsightNotificationRule.restaurant_id == restaurant_id,
            )
            .first()
        )

        if not rule:
            return None

        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(rule, field, value)

        self.db.commit()
        self.db.refresh(rule)

        return rule

    def delete_rule(self, rule_id: int, restaurant_id: int) -> bool:
        """Delete a notification rule"""
        rule = (
            self.db.query(InsightNotificationRule)
            .filter(
                InsightNotificationRule.id == rule_id,
                InsightNotificationRule.restaurant_id == restaurant_id,
            )
            .first()
        )

        if not rule:
            return False

        self.db.delete(rule)
        self.db.commit()

        return True
