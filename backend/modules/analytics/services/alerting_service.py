# backend/modules/analytics/services/alerting_service.py

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc

from ..models.analytics_models import (
    AlertRule, SalesAnalyticsSnapshot, SalesMetric, AggregationPeriod
)
from ..schemas.analytics_schemas import SalesFilterRequest
from .sales_report_service import SalesReportService

logger = logging.getLogger(__name__)


class AlertingService:
    """Service for managing and evaluating sales analytics alerts"""
    
    def __init__(self, db: Session):
        self.db = db
        self.sales_service = SalesReportService(db)
    
    def create_alert_rule(
        self,
        name: str,
        description: str,
        metric_name: str,
        condition_type: str,
        threshold_value: Decimal,
        evaluation_period: str,
        notification_channels: List[str],
        notification_recipients: List[str],
        created_by: int,
        comparison_period: Optional[str] = None,
        entity_filters: Optional[Dict[str, Any]] = None
    ) -> AlertRule:
        """Create a new alert rule"""
        
        try:
            alert_rule = AlertRule(
                name=name,
                description=description,
                metric_name=metric_name,
                condition_type=condition_type,
                threshold_value=threshold_value,
                evaluation_period=evaluation_period,
                comparison_period=comparison_period,
                notification_channels=notification_channels,
                notification_recipients=notification_recipients,
                created_by=created_by,
                is_active=True,
                trigger_count=0
            )
            
            # Add entity filters to metadata if provided
            if entity_filters:
                alert_rule.metadata = {"entity_filters": entity_filters}
            
            self.db.add(alert_rule)
            self.db.commit()
            
            logger.info(f"Created alert rule: {name}")
            return alert_rule
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating alert rule: {e}")
            raise
    
    def get_alert_rules(
        self,
        include_inactive: bool = False,
        created_by: Optional[int] = None
    ) -> List[AlertRule]:
        """Get all alert rules with optional filters"""
        
        query = self.db.query(AlertRule)
        
        if not include_inactive:
            query = query.filter(AlertRule.is_active == True)
        
        if created_by:
            query = query.filter(AlertRule.created_by == created_by)
        
        return query.order_by(desc(AlertRule.created_at)).all()
    
    def update_alert_rule(
        self,
        rule_id: int,
        updates: Dict[str, Any]
    ) -> AlertRule:
        """Update an existing alert rule"""
        
        rule = self.db.query(AlertRule).filter(AlertRule.id == rule_id).first()
        if not rule:
            raise ValueError(f"Alert rule {rule_id} not found")
        
        # Update allowed fields
        allowed_fields = [
            'name', 'description', 'threshold_value', 'is_active',
            'notification_channels', 'notification_recipients'
        ]
        
        for field, value in updates.items():
            if field in allowed_fields and hasattr(rule, field):
                setattr(rule, field, value)
        
        self.db.commit()
        
        logger.info(f"Updated alert rule: {rule.name}")
        return rule
    
    def delete_alert_rule(self, rule_id: int) -> bool:
        """Delete an alert rule"""
        
        rule = self.db.query(AlertRule).filter(AlertRule.id == rule_id).first()
        if not rule:
            return False
        
        self.db.delete(rule)
        self.db.commit()
        
        logger.info(f"Deleted alert rule: {rule.name}")
        return True
    
    async def evaluate_all_alerts(self) -> Dict[str, Any]:
        """Evaluate all active alert rules"""
        
        active_rules = self.get_alert_rules(include_inactive=False)
        
        results = {
            "total_rules": len(active_rules),
            "triggered_alerts": [],
            "evaluation_errors": [],
            "evaluation_time": datetime.now()
        }
        
        for rule in active_rules:
            try:
                triggered = await self.evaluate_alert_rule(rule)
                if triggered:
                    results["triggered_alerts"].append({
                        "rule_id": rule.id,
                        "rule_name": rule.name,
                        "triggered_at": datetime.now(),
                        "metric_name": rule.metric_name,
                        "threshold": float(rule.threshold_value)
                    })
                    
            except Exception as e:
                logger.error(f"Error evaluating alert rule {rule.name}: {e}")
                results["evaluation_errors"].append({
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "error": str(e)
                })
        
        return results
    
    async def evaluate_alert_rule(self, rule: AlertRule) -> bool:
        """Evaluate a single alert rule"""
        
        try:
            # Check throttling
            if self._should_throttle_alert(rule):
                return False
            
            # Get current metric value
            current_value = await self._get_metric_value(rule)
            if current_value is None:
                return False
            
            # Get comparison value if needed
            comparison_value = None
            if rule.comparison_period:
                comparison_value = await self._get_comparison_value(rule)
            
            # Evaluate condition
            should_trigger = self._evaluate_condition(
                rule, current_value, comparison_value
            )
            
            if should_trigger:
                # Trigger alert
                await self._trigger_alert(rule, current_value, comparison_value)
                
                # Update rule statistics
                rule.last_triggered_at = datetime.now()
                rule.trigger_count += 1
                self.db.commit()
                
                logger.info(f"Alert triggered: {rule.name} (value: {current_value})")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error evaluating alert rule {rule.name}: {e}")
            return False
    
    async def test_alert_rule(
        self,
        rule: AlertRule,
        test_value: Optional[float] = None
    ) -> Dict[str, Any]:
        """Test an alert rule without triggering notifications"""
        
        try:
            # Use test value or get actual current value
            if test_value is not None:
                current_value = test_value
            else:
                current_value = await self._get_metric_value(rule)
            
            if current_value is None:
                return {
                    "success": False,
                    "error": "Could not retrieve metric value"
                }
            
            # Get comparison value if needed
            comparison_value = None
            if rule.comparison_period:
                comparison_value = await self._get_comparison_value(rule)
            
            # Evaluate condition
            would_trigger = self._evaluate_condition(
                rule, current_value, comparison_value
            )
            
            return {
                "success": True,
                "rule_name": rule.name,
                "current_value": current_value,
                "comparison_value": comparison_value,
                "threshold": float(rule.threshold_value),
                "condition_type": rule.condition_type,
                "would_trigger": would_trigger,
                "evaluation_time": datetime.now()
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_alert_history(
        self,
        rule_id: Optional[int] = None,
        days_back: int = 30
    ) -> List[Dict[str, Any]]:
        """Get alert trigger history"""
        
        # This would typically query a separate alert_history table
        # For now, we'll return rule statistics
        
        query = self.db.query(AlertRule)
        
        if rule_id:
            query = query.filter(AlertRule.id == rule_id)
        
        cutoff_date = datetime.now() - timedelta(days=days_back)
        rules = query.filter(
            AlertRule.last_triggered_at >= cutoff_date
        ).all()
        
        history = []
        for rule in rules:
            if rule.last_triggered_at:
                history.append({
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "metric_name": rule.metric_name,
                    "last_triggered": rule.last_triggered_at,
                    "trigger_count": rule.trigger_count,
                    "threshold": float(rule.threshold_value),
                    "condition_type": rule.condition_type
                })
        
        return sorted(history, key=lambda x: x["last_triggered"], reverse=True)
    
    # Private helper methods
    
    async def _get_metric_value(self, rule: AlertRule) -> Optional[float]:
        """Get current metric value based on rule configuration"""
        
        try:
            # Parse evaluation period
            period_days = self._parse_period_days(rule.evaluation_period)
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=period_days)
            
            # Create filters for metric calculation
            filters = SalesFilterRequest(
                date_from=start_date,
                date_to=end_date,
                period_type=AggregationPeriod.DAILY
            )
            
            # Add entity filters if specified
            if rule.metadata and "entity_filters" in rule.metadata:
                entity_filters = rule.metadata["entity_filters"]
                if "staff_ids" in entity_filters:
                    filters.staff_ids = entity_filters["staff_ids"]
                if "category_ids" in entity_filters:
                    filters.category_ids = entity_filters["category_ids"]
            
            # Get metric value based on metric name
            if rule.metric_name == "daily_revenue":
                summary = self.sales_service.generate_sales_summary(filters)
                return float(summary.total_revenue)
                
            elif rule.metric_name == "daily_orders":
                summary = self.sales_service.generate_sales_summary(filters)
                return float(summary.total_orders)
                
            elif rule.metric_name == "average_order_value":
                summary = self.sales_service.generate_sales_summary(filters)
                return float(summary.average_order_value)
                
            elif rule.metric_name == "customer_count":
                summary = self.sales_service.generate_sales_summary(filters)
                return float(summary.unique_customers)
                
            elif rule.metric_name == "revenue_growth":
                summary = self.sales_service.generate_sales_summary(filters)
                return float(summary.revenue_growth) if summary.revenue_growth else 0.0
                
            else:
                # Try to get from SalesMetric table
                metric = self.db.query(SalesMetric).filter(
                    and_(
                        SalesMetric.metric_name == rule.metric_name,
                        SalesMetric.metric_date >= start_date
                    )
                ).order_by(desc(SalesMetric.created_at)).first()
                
                if metric:
                    return float(metric.value_numeric) if metric.value_numeric else float(metric.value_integer or 0)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting metric value for {rule.metric_name}: {e}")
            return None
    
    async def _get_comparison_value(self, rule: AlertRule) -> Optional[float]:
        """Get comparison metric value for relative alerts"""
        
        try:
            # Parse comparison period
            comparison_days = self._parse_period_days(rule.comparison_period)
            evaluation_days = self._parse_period_days(rule.evaluation_period)
            
            # Calculate comparison period dates
            current_end = datetime.now().date()
            current_start = current_end - timedelta(days=evaluation_days)
            
            comparison_end = current_start - timedelta(days=1)
            comparison_start = comparison_end - timedelta(days=comparison_days)
            
            # Create filters for comparison period
            filters = SalesFilterRequest(
                date_from=comparison_start,
                date_to=comparison_end,
                period_type=AggregationPeriod.DAILY
            )
            
            # Get comparison metric value (similar to _get_metric_value)
            if rule.metric_name == "daily_revenue":
                summary = self.sales_service.generate_sales_summary(filters)
                return float(summary.total_revenue)
                
            elif rule.metric_name == "daily_orders":
                summary = self.sales_service.generate_sales_summary(filters)
                return float(summary.total_orders)
                
            # Add other metrics as needed
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting comparison value: {e}")
            return None
    
    def _evaluate_condition(
        self,
        rule: AlertRule,
        current_value: float,
        comparison_value: Optional[float] = None
    ) -> bool:
        """Evaluate if alert condition is met"""
        
        threshold = float(rule.threshold_value)
        
        if rule.condition_type == "above":
            return current_value > threshold
            
        elif rule.condition_type == "below":
            return current_value < threshold
            
        elif rule.condition_type == "equals":
            return abs(current_value - threshold) < 0.01  # Small tolerance for floats
            
        elif rule.condition_type == "change" and comparison_value is not None:
            if comparison_value == 0:
                return False  # Avoid division by zero
            
            change_percentage = abs((current_value - comparison_value) / comparison_value) * 100
            return change_percentage > threshold
            
        elif rule.condition_type == "increase" and comparison_value is not None:
            if comparison_value == 0:
                return current_value > 0
            
            increase_percentage = ((current_value - comparison_value) / comparison_value) * 100
            return increase_percentage > threshold
            
        elif rule.condition_type == "decrease" and comparison_value is not None:
            if comparison_value == 0:
                return False
            
            decrease_percentage = ((comparison_value - current_value) / comparison_value) * 100
            return decrease_percentage > threshold
        
        return False
    
    def _should_throttle_alert(self, rule: AlertRule) -> bool:
        """Check if alert should be throttled to avoid spam"""
        
        if rule.last_triggered_at is None:
            return False
        
        # Throttle based on evaluation period
        period_minutes = self._parse_period_minutes(rule.evaluation_period)
        throttle_minutes = max(period_minutes, 60)  # At least 1 hour
        
        time_since_last = datetime.now() - rule.last_triggered_at
        return time_since_last.total_seconds() < (throttle_minutes * 60)
    
    async def _trigger_alert(
        self,
        rule: AlertRule,
        current_value: float,
        comparison_value: Optional[float] = None
    ):
        """Trigger alert notifications"""
        
        # Prepare alert data
        alert_data = {
            "rule_name": rule.name,
            "rule_description": rule.description,
            "metric_name": rule.metric_name,
            "current_value": current_value,
            "threshold": float(rule.threshold_value),
            "condition_type": rule.condition_type,
            "triggered_at": datetime.now(),
            "comparison_value": comparison_value
        }
        
        # Send notifications through configured channels
        for channel in rule.notification_channels:
            try:
                if channel == "email":
                    await self._send_email_alert(rule, alert_data)
                elif channel == "slack":
                    await self._send_slack_alert(rule, alert_data)
                elif channel == "webhook":
                    await self._send_webhook_alert(rule, alert_data)
                elif channel == "sms":
                    await self._send_sms_alert(rule, alert_data)
                    
            except Exception as e:
                logger.error(f"Error sending {channel} alert: {e}")
    
    async def _send_email_alert(self, rule: AlertRule, alert_data: Dict[str, Any]):
        """Send email alert notification"""
        
        # This would integrate with an email service
        logger.info(f"EMAIL ALERT: {rule.name} - {alert_data['current_value']}")
        
        # Example email content
        subject = f"🚨 Analytics Alert: {rule.name}"
        body = f"""
        Alert: {rule.name}
        
        Description: {rule.description}
        Metric: {rule.metric_name}
        Current Value: {alert_data['current_value']}
        Threshold: {alert_data['threshold']}
        Condition: {rule.condition_type}
        
        Triggered at: {alert_data['triggered_at']}
        """
        
        # Send to recipients
        for recipient in rule.notification_recipients:
            # await email_service.send_email(recipient, subject, body)
            pass
    
    async def _send_slack_alert(self, rule: AlertRule, alert_data: Dict[str, Any]):
        """Send Slack alert notification"""
        
        logger.info(f"SLACK ALERT: {rule.name} - {alert_data['current_value']}")
        
        # This would integrate with Slack API
        slack_message = {
            "text": f"🚨 Analytics Alert: {rule.name}",
            "attachments": [
                {
                    "color": "danger",
                    "fields": [
                        {"title": "Metric", "value": rule.metric_name, "short": True},
                        {"title": "Current Value", "value": str(alert_data['current_value']), "short": True},
                        {"title": "Threshold", "value": str(alert_data['threshold']), "short": True},
                        {"title": "Condition", "value": rule.condition_type, "short": True},
                    ]
                }
            ]
        }
        
        # Send to Slack channels/users
        # await slack_service.send_message(slack_message)
    
    async def _send_webhook_alert(self, rule: AlertRule, alert_data: Dict[str, Any]):
        """Send webhook alert notification"""
        
        logger.info(f"WEBHOOK ALERT: {rule.name} - {alert_data['current_value']}")
        
        # This would send HTTP POST to configured webhook URLs
        webhook_payload = {
            "alert_type": "analytics_alert",
            "rule_id": rule.id,
            "rule_name": rule.name,
            "metric_name": rule.metric_name,
            "current_value": alert_data['current_value'],
            "threshold": alert_data['threshold'],
            "condition_type": rule.condition_type,
            "triggered_at": alert_data['triggered_at'].isoformat()
        }
        
        # Send to webhook URLs
        # await webhook_service.send_webhook(webhook_payload)
    
    async def _send_sms_alert(self, rule: AlertRule, alert_data: Dict[str, Any]):
        """Send SMS alert notification"""
        
        logger.info(f"SMS ALERT: {rule.name} - {alert_data['current_value']}")
        
        # This would integrate with SMS service (Twilio, etc.)
        sms_message = f"🚨 {rule.name}: {rule.metric_name} is {alert_data['current_value']} (threshold: {alert_data['threshold']})"
        
        # Send to phone numbers
        for recipient in rule.notification_recipients:
            if recipient.startswith('+') or recipient.isdigit():
                # await sms_service.send_sms(recipient, sms_message)
                pass
    
    def _parse_period_days(self, period: str) -> int:
        """Parse period string to number of days"""
        
        period_mapping = {
            "hourly": 1,
            "daily": 1,
            "weekly": 7,
            "monthly": 30,
            "quarterly": 90
        }
        
        return period_mapping.get(period, 1)
    
    def _parse_period_minutes(self, period: str) -> int:
        """Parse period string to number of minutes"""
        
        period_mapping = {
            "hourly": 60,
            "daily": 60,  # Minimum 1 hour throttle
            "weekly": 360,  # 6 hours
            "monthly": 1440,  # 24 hours
            "quarterly": 4320  # 3 days
        }
        
        return period_mapping.get(period, 60)


# Service factory function
def create_alerting_service(db: Session) -> AlertingService:
    """Create an alerting service instance"""
    return AlertingService(db)