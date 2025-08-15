# backend/modules/promotions/services/automation_service.py

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import Optional, List, Dict, Any, Callable, Tuple
from datetime import datetime, timedelta
import logging
import json

from ..models.promotion_models import Promotion, PromotionStatus, PromotionRule
from ..services.promotion_service import PromotionService
from modules.customers.models.customer_models import Customer
from modules.orders.models.order_models import Order

logger = logging.getLogger(__name__)


class PromotionAutomationService:
    """Service for automating promotion triggers and rules"""

    def __init__(self, db: Session):
        self.db = db
        self.promotion_service = PromotionService(db)
        self.trigger_handlers = self._initialize_trigger_handlers()

    def _initialize_trigger_handlers(self) -> Dict[str, Callable]:
        """Initialize trigger handler functions"""
        return {
            "customer_lifecycle": self._handle_customer_lifecycle_trigger,
            "purchase_behavior": self._handle_purchase_behavior_trigger,
            "cart_abandonment": self._handle_cart_abandonment_trigger,
            "loyalty_milestone": self._handle_loyalty_milestone_trigger,
            "inventory_level": self._handle_inventory_level_trigger,
            "weather_condition": self._handle_weather_condition_trigger,
            "competitor_price": self._handle_competitor_price_trigger,
            "seasonal_event": self._handle_seasonal_event_trigger,
        }

    def create_automated_promotion(
        self,
        name: str,
        trigger_type: str,
        trigger_conditions: Dict[str, Any],
        promotion_config: Dict[str, Any],
        automation_options: Dict[str, Any],
    ) -> Promotion:
        """
        Create an automated promotion with trigger conditions

        Args:
            name: Promotion name
            trigger_type: Type of trigger (customer_lifecycle, purchase_behavior, etc.)
            trigger_conditions: Conditions for the trigger
            promotion_config: Configuration for the promotion when triggered
            automation_options: Additional automation options

        Returns:
            Created automated promotion
        """
        try:
            # Create base promotion
            from ..schemas.promotion_schemas import PromotionCreate

            promotion_data = PromotionCreate(
                name=name,
                description=f"Automated promotion triggered by {trigger_type}",
                **promotion_config,
            )

            promotion = self.promotion_service.create_promotion(promotion_data)

            # Set as draft initially (will be activated by triggers)
            promotion.status = PromotionStatus.DRAFT

            # Store automation metadata
            if not promotion.metadata:
                promotion.metadata = {}

            promotion.metadata["automation"] = {
                "trigger_type": trigger_type,
                "trigger_conditions": trigger_conditions,
                "automation_options": automation_options,
                "created_at": datetime.utcnow().isoformat(),
                "last_triggered": None,
                "trigger_count": 0,
            }

            # Create automation rule
            rule = PromotionRule(
                promotion_id=promotion.id,
                rule_type="automation_trigger",
                condition_type=trigger_type,
                condition_value=trigger_conditions,
                action_type="activate_promotion",
                action_value={
                    "duration_hours": automation_options.get("duration_hours", 24)
                },
                is_active=True,
            )
            self.db.add(rule)

            self.db.commit()
            self.db.refresh(promotion)

            logger.info(
                f"Created automated promotion: {name} with trigger {trigger_type}"
            )
            return promotion

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating automated promotion: {str(e)}")
            raise

    async def process_triggers(
        self, trigger_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process automation triggers and activate relevant promotions"""

        try:
            results = {
                "triggers_processed": 0,
                "promotions_activated": [],
                "errors": [],
            }

            # Get automation rules to process
            query = self.db.query(PromotionRule).filter(
                PromotionRule.rule_type == "automation_trigger",
                PromotionRule.is_active == True,
            )

            if trigger_type:
                query = query.filter(PromotionRule.condition_type == trigger_type)

            rules = query.all()

            for rule in rules:
                try:
                    results["triggers_processed"] += 1

                    # Get the trigger handler
                    handler = self.trigger_handlers.get(rule.condition_type)
                    if not handler:
                        logger.warning(
                            f"No handler for trigger type: {rule.condition_type}"
                        )
                        continue

                    # Check if trigger conditions are met
                    should_trigger, trigger_data = handler(rule.condition_value)

                    if should_trigger:
                        # Activate the promotion
                        promotion = rule.promotion
                        if promotion and promotion.status == PromotionStatus.DRAFT:
                            activated = await self._activate_triggered_promotion(
                                promotion, rule, trigger_data
                            )

                            if activated:
                                results["promotions_activated"].append(
                                    {
                                        "promotion_id": promotion.id,
                                        "promotion_name": promotion.name,
                                        "trigger_type": rule.condition_type,
                                        "trigger_data": trigger_data,
                                    }
                                )

                except Exception as e:
                    logger.error(f"Error processing rule {rule.id}: {str(e)}")
                    results["errors"].append({"rule_id": rule.id, "error": str(e)})

            self.db.commit()

            return results

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error processing automation triggers: {str(e)}")
            raise

    async def _activate_triggered_promotion(
        self, promotion: Promotion, rule: PromotionRule, trigger_data: Dict[str, Any]
    ) -> bool:
        """Activate a triggered promotion"""

        try:
            # Check if promotion can be activated
            metadata = promotion.metadata or {}
            automation = metadata.get("automation", {})

            # Check cooldown period
            last_triggered = automation.get("last_triggered")
            if last_triggered:
                cooldown_hours = automation.get("automation_options", {}).get(
                    "cooldown_hours", 0
                )
                if cooldown_hours > 0:
                    last_triggered_dt = datetime.fromisoformat(last_triggered)
                    if datetime.utcnow() - last_triggered_dt < timedelta(
                        hours=cooldown_hours
                    ):
                        logger.info(f"Promotion {promotion.id} in cooldown period")
                        return False

            # Check max trigger count
            max_triggers = automation.get("automation_options", {}).get("max_triggers")
            if max_triggers and automation.get("trigger_count", 0) >= max_triggers:
                logger.info(f"Promotion {promotion.id} reached max triggers")
                return False

            # Activate the promotion
            promotion.status = PromotionStatus.ACTIVE

            # Set duration if specified
            duration_hours = rule.action_value.get("duration_hours", 24)
            if duration_hours:
                promotion.end_date = datetime.utcnow() + timedelta(hours=duration_hours)

            # Update automation metadata
            automation["last_triggered"] = datetime.utcnow().isoformat()
            automation["trigger_count"] = automation.get("trigger_count", 0) + 1
            automation["last_trigger_data"] = trigger_data

            promotion.metadata["automation"] = automation

            logger.info(f"Activated triggered promotion: {promotion.name}")
            return True

        except Exception as e:
            logger.error(f"Error activating triggered promotion: {str(e)}")
            return False

    def _handle_customer_lifecycle_trigger(
        self, conditions: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Handle customer lifecycle triggers"""

        event_type = conditions.get(
            "event_type"
        )  # signup, first_purchase, birthday, etc.

        if event_type == "signup":
            # Check for new signups in the last hour
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            new_customers = (
                self.db.query(Customer).filter(Customer.created_at >= hour_ago).count()
            )

            if new_customers > 0:
                return True, {"new_customers": new_customers}

        elif event_type == "birthday":
            # Check for customers with birthdays today
            today = datetime.utcnow().date()
            birthday_customers = (
                self.db.query(Customer)
                .filter(
                    func.extract("month", Customer.date_of_birth) == today.month,
                    func.extract("day", Customer.date_of_birth) == today.day,
                )
                .count()
            )

            if birthday_customers > 0:
                return True, {"birthday_customers": birthday_customers}

        elif event_type == "win_back":
            # Check for inactive customers
            days_inactive = conditions.get("days_inactive", 30)
            cutoff_date = datetime.utcnow() - timedelta(days=days_inactive)

            inactive_customers = (
                self.db.query(Customer)
                .filter(Customer.last_order_date < cutoff_date)
                .count()
            )

            if inactive_customers > 0:
                return True, {"inactive_customers": inactive_customers}

        return False, {}

    def _handle_purchase_behavior_trigger(
        self, conditions: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Handle purchase behavior triggers"""

        behavior_type = conditions.get("behavior_type")

        if behavior_type == "high_value_purchase":
            # Check for recent high-value orders
            threshold = conditions.get("order_threshold", 100)
            hour_ago = datetime.utcnow() - timedelta(hours=1)

            high_value_orders = (
                self.db.query(Order)
                .filter(Order.created_at >= hour_ago, Order.total_amount >= threshold)
                .count()
            )

            if high_value_orders > 0:
                return True, {"high_value_orders": high_value_orders}

        elif behavior_type == "category_purchase":
            # Check for purchases in specific categories
            category_ids = conditions.get("category_ids", [])
            hour_ago = datetime.utcnow() - timedelta(hours=1)

            category_orders = (
                self.db.query(Order)
                .filter(
                    Order.created_at >= hour_ago, Order.category_id.in_(category_ids)
                )
                .count()
            )

            if category_orders > 0:
                return True, {"category_orders": category_orders}

        return False, {}

    def _handle_cart_abandonment_trigger(
        self, conditions: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Handle cart abandonment triggers"""

        # This would integrate with cart/session tracking
        # For now, return a placeholder
        abandonment_threshold_hours = conditions.get("hours_since_abandonment", 2)

        # Placeholder logic - would check actual cart data
        abandoned_carts = 0  # Would query actual cart data

        if abandoned_carts > 0:
            return True, {"abandoned_carts": abandoned_carts}

        return False, {}

    def _handle_loyalty_milestone_trigger(
        self, conditions: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Handle loyalty milestone triggers"""

        milestone_type = conditions.get("milestone_type")

        if milestone_type == "points_threshold":
            # Check for customers reaching points threshold
            points_threshold = conditions.get("points_threshold", 1000)

            # This would integrate with loyalty system
            customers_reached = 0  # Would query actual loyalty data

            if customers_reached > 0:
                return True, {"customers_reached_milestone": customers_reached}

        elif milestone_type == "tier_upgrade":
            # Check for recent tier upgrades
            hour_ago = datetime.utcnow() - timedelta(hours=1)

            # Placeholder - would check actual tier changes
            tier_upgrades = 0

            if tier_upgrades > 0:
                return True, {"tier_upgrades": tier_upgrades}

        return False, {}

    def _handle_inventory_level_trigger(
        self, conditions: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Handle inventory level triggers"""

        trigger_type = conditions.get("trigger_type")

        if trigger_type == "low_stock":
            # Check for low stock items
            threshold_percentage = conditions.get("threshold_percentage", 20)

            # This would integrate with inventory system
            low_stock_items = 0  # Would query actual inventory

            if low_stock_items > 0:
                return True, {"low_stock_items": low_stock_items}

        elif trigger_type == "overstock":
            # Check for overstock items
            threshold_percentage = conditions.get("threshold_percentage", 150)

            overstock_items = 0  # Would query actual inventory

            if overstock_items > 0:
                return True, {"overstock_items": overstock_items}

        return False, {}

    def _handle_weather_condition_trigger(
        self, conditions: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Handle weather-based triggers"""

        # This would integrate with weather API
        weather_type = conditions.get("weather_type")

        # Placeholder logic
        if weather_type == "temperature":
            temp_threshold = conditions.get("temperature_threshold")
            comparison = conditions.get("comparison", "above")

            # Would check actual weather data
            current_temp = 75  # Placeholder

            if comparison == "above" and current_temp > temp_threshold:
                return True, {"current_temperature": current_temp}
            elif comparison == "below" and current_temp < temp_threshold:
                return True, {"current_temperature": current_temp}

        return False, {}

    def _handle_competitor_price_trigger(
        self, conditions: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Handle competitor price triggers"""

        # This would integrate with price monitoring
        price_difference_threshold = conditions.get("price_difference_percentage", 10)

        # Placeholder logic
        items_with_price_difference = 0  # Would check actual competitor prices

        if items_with_price_difference > 0:
            return True, {"items_with_price_difference": items_with_price_difference}

        return False, {}

    def _handle_seasonal_event_trigger(
        self, conditions: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Handle seasonal event triggers"""

        event_type = conditions.get("event_type")
        days_before = conditions.get("days_before", 0)

        # Define seasonal events
        seasonal_events = {
            "black_friday": datetime(datetime.utcnow().year, 11, 29),
            "cyber_monday": datetime(datetime.utcnow().year, 12, 2),
            "christmas": datetime(datetime.utcnow().year, 12, 25),
            "new_year": datetime(datetime.utcnow().year + 1, 1, 1),
            "valentines": datetime(datetime.utcnow().year, 2, 14),
            "summer_start": datetime(datetime.utcnow().year, 6, 21),
            "back_to_school": datetime(datetime.utcnow().year, 8, 15),
        }

        if event_type in seasonal_events:
            event_date = seasonal_events[event_type]
            trigger_date = event_date - timedelta(days=days_before)

            if datetime.utcnow().date() == trigger_date.date():
                return True, {
                    "event_type": event_type,
                    "event_date": event_date.isoformat(),
                }

        return False, {}

    def create_customer_segment_promotion(
        self, segment_criteria: Dict[str, Any], promotion_config: Dict[str, Any]
    ) -> Promotion:
        """Create a promotion targeted at specific customer segments"""

        try:
            # Define the segment
            segment_name = segment_criteria.get("name", "Custom Segment")

            # Create promotion with segment targeting
            from ..schemas.promotion_schemas import PromotionCreate

            promotion_data = PromotionCreate(
                name=f"{segment_name} - Targeted Promotion",
                description=f"Promotion for {segment_name} customers",
                target_customer_segments=[segment_name],
                **promotion_config,
            )

            promotion = self.promotion_service.create_promotion(promotion_data)

            # Store segment criteria
            if not promotion.metadata:
                promotion.metadata = {}

            promotion.metadata["segment_targeting"] = {
                "segment_criteria": segment_criteria,
                "created_at": datetime.utcnow().isoformat(),
            }

            self.db.commit()
            self.db.refresh(promotion)

            logger.info(f"Created customer segment promotion for: {segment_name}")
            return promotion

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating customer segment promotion: {str(e)}")
            raise

    def evaluate_customer_segment(
        self, customer_id: int, segment_criteria: Dict[str, Any]
    ) -> bool:
        """Evaluate if a customer belongs to a segment"""

        try:
            customer = (
                self.db.query(Customer).filter(Customer.id == customer_id).first()
            )

            if not customer:
                return False

            # Evaluate criteria
            criteria_type = segment_criteria.get("type")

            if criteria_type == "purchase_frequency":
                min_orders = segment_criteria.get("min_orders", 0)
                time_period_days = segment_criteria.get("time_period_days", 30)

                cutoff_date = datetime.utcnow() - timedelta(days=time_period_days)
                order_count = (
                    self.db.query(Order)
                    .filter(
                        Order.customer_id == customer_id,
                        Order.created_at >= cutoff_date,
                    )
                    .count()
                )

                return order_count >= min_orders

            elif criteria_type == "total_spent":
                min_amount = segment_criteria.get("min_amount", 0)
                time_period_days = segment_criteria.get("time_period_days", 365)

                cutoff_date = datetime.utcnow() - timedelta(days=time_period_days)
                total_spent = (
                    self.db.query(func.sum(Order.total_amount))
                    .filter(
                        Order.customer_id == customer_id,
                        Order.created_at >= cutoff_date,
                    )
                    .scalar()
                    or 0
                )

                return total_spent >= min_amount

            elif criteria_type == "customer_attributes":
                attributes = segment_criteria.get("attributes", {})

                for attr, value in attributes.items():
                    if hasattr(customer, attr):
                        if getattr(customer, attr) != value:
                            return False
                    else:
                        return False

                return True

            return False

        except Exception as e:
            logger.error(f"Error evaluating customer segment: {str(e)}")
            return False

    def get_automation_performance(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get performance metrics for automated promotions"""

        try:
            if not end_date:
                end_date = datetime.utcnow()
            if not start_date:
                start_date = end_date - timedelta(days=30)

            # Get automated promotions
            automated_promotions = (
                self.db.query(Promotion)
                .filter(Promotion.metadata["automation"].isnot(None))
                .all()
            )

            metrics = {
                "total_automated_promotions": len(automated_promotions),
                "trigger_type_breakdown": {},
                "performance_by_trigger": {},
                "total_triggers": 0,
                "total_revenue_generated": 0,
            }

            for promotion in automated_promotions:
                automation = promotion.metadata.get("automation", {})
                trigger_type = automation.get("trigger_type")
                trigger_count = automation.get("trigger_count", 0)

                if trigger_type not in metrics["trigger_type_breakdown"]:
                    metrics["trigger_type_breakdown"][trigger_type] = 0
                metrics["trigger_type_breakdown"][trigger_type] += 1

                metrics["total_triggers"] += trigger_count

                # Calculate revenue for this promotion
                from ..models.promotion_models import PromotionUsage

                revenue = (
                    self.db.query(func.sum(PromotionUsage.final_order_amount))
                    .filter(
                        PromotionUsage.promotion_id == promotion.id,
                        PromotionUsage.created_at >= start_date,
                        PromotionUsage.created_at <= end_date,
                    )
                    .scalar()
                    or 0
                )

                if trigger_type not in metrics["performance_by_trigger"]:
                    metrics["performance_by_trigger"][trigger_type] = {
                        "count": 0,
                        "total_triggers": 0,
                        "total_revenue": 0,
                    }

                metrics["performance_by_trigger"][trigger_type]["count"] += 1
                metrics["performance_by_trigger"][trigger_type][
                    "total_triggers"
                ] += trigger_count
                metrics["performance_by_trigger"][trigger_type][
                    "total_revenue"
                ] += float(revenue)

                metrics["total_revenue_generated"] += float(revenue)

            return metrics

        except Exception as e:
            logger.error(f"Error getting automation performance: {str(e)}")
            raise
