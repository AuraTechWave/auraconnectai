# backend/modules/loyalty/services/rewards_engine.py

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import secrets
import string
import logging
from decimal import Decimal

from ..models.rewards_models import (
    RewardTemplate,
    CustomerReward,
    RewardCampaign,
    RewardRedemption,
    LoyaltyPointsTransaction,
    RewardType,
    RewardStatus,
    TriggerType,
)
from modules.customers.models.customer_models import Customer, CustomerTier
from modules.orders.models.order_models import Order
from modules.customers.models.loyalty_config import LoyaltyService


logger = logging.getLogger(__name__)


class RewardsEngine:
    """Core rewards engine for managing loyalty rewards and points"""

    def __init__(self, db: Session):
        self.db = db
        self.loyalty_service = LoyaltyService(db)

    def process_order_completion(self, order_id: int) -> Dict[str, Any]:
        """Process rewards and points when an order is completed"""
        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order or not order.customer_id:
            logger.warning(f"Order {order_id} not found or has no customer")
            return {"success": False, "error": "Order not found or no customer"}

        customer = (
            self.db.query(Customer).filter(Customer.id == order.customer_id).first()
        )
        if not customer:
            logger.warning(f"Customer {order.customer_id} not found")
            return {"success": False, "error": "Customer not found"}

        results = {
            "success": True,
            "points_earned": 0,
            "rewards_triggered": [],
            "tier_upgrade": None,
        }

        try:
            # Calculate and award points for the order
            order_total = self._calculate_order_total(order)
            points_earned = self.loyalty_service.calculate_points_earned(
                action_type="order",
                amount=float(order_total),
                customer_tier=customer.tier.value.lower(),
                order_id=order_id,
                categories=self._get_order_categories(order),
            )

            if points_earned > 0:
                old_tier = customer.tier
                self._award_points(
                    customer, points_earned, f"Order #{order_id}", order_id=order_id
                )
                results["points_earned"] = points_earned

                # Check for tier upgrade
                if customer.tier != old_tier:
                    results["tier_upgrade"] = {
                        "old_tier": old_tier.value,
                        "new_tier": customer.tier.value,
                    }

            # Trigger order completion rewards
            triggered_rewards = self._process_trigger_rewards(
                customer,
                TriggerType.ORDER_COMPLETE,
                {"order_id": order_id, "order_total": float(order_total)},
            )
            results["rewards_triggered"] = triggered_rewards

            # Process milestone rewards if applicable
            milestone_rewards = self._check_milestone_rewards(customer)
            results["rewards_triggered"].extend(milestone_rewards)

            self.db.commit()
            logger.info(
                f"Order completion processed for customer {customer.id}: {points_earned} points, {len(results['rewards_triggered'])} rewards"
            )

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error processing order completion: {str(e)}")
            results = {"success": False, "error": str(e)}

        return results

    def create_reward_template(self, template_data: Dict[str, Any]) -> RewardTemplate:
        """Create a new reward template"""
        template = RewardTemplate(**template_data)
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)

        logger.info(f"Created reward template: {template.name}")
        return template

    def issue_reward_to_customer(
        self,
        customer_id: int,
        template_id: int,
        issued_by: Optional[int] = None,
        custom_data: Optional[Dict[str, Any]] = None,
    ) -> CustomerReward:
        """Manually issue a reward to a customer"""
        template = (
            self.db.query(RewardTemplate)
            .filter(
                and_(RewardTemplate.id == template_id, RewardTemplate.is_active == True)
            )
            .first()
        )

        if not template:
            raise ValueError(f"Active reward template {template_id} not found")

        customer = self.db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")

        # Check eligibility
        if not self._is_customer_eligible(customer, template):
            raise ValueError("Customer is not eligible for this reward")

        # Create reward instance
        reward = self._create_reward_instance(
            customer, template, issued_by, custom_data
        )

        # Update template statistics
        template.total_issued += 1

        self.db.commit()
        logger.info(f"Issued reward {template.name} to customer {customer_id}")

        return reward

    def redeem_reward(
        self, reward_code: str, order_id: int, staff_member_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Redeem a reward against an order"""
        reward = (
            self.db.query(CustomerReward)
            .filter(CustomerReward.code == reward_code)
            .first()
        )

        if not reward:
            return {"success": False, "error": "Invalid reward code"}

        if reward.status != RewardStatus.AVAILABLE:
            return {"success": False, "error": f"Reward is {reward.status.value}"}

        if reward.is_expired:
            reward.status = RewardStatus.EXPIRED
            self.db.commit()
            return {"success": False, "error": "Reward has expired"}

        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"success": False, "error": "Order not found"}

        if order.customer_id != reward.customer_id:
            return {
                "success": False,
                "error": "Reward does not belong to order customer",
            }

        # Calculate discount
        discount_result = self._calculate_reward_discount(reward, order)
        if not discount_result["valid"]:
            return {"success": False, "error": discount_result["error"]}

        # Apply redemption
        try:
            discount_amount = discount_result["discount_amount"]

            # Update reward status
            reward.status = RewardStatus.REDEEMED
            reward.redeemed_at = datetime.utcnow()
            reward.redeemed_amount = discount_amount
            reward.order_id = order_id

            # Create redemption record
            redemption = RewardRedemption(
                reward_id=reward.id,
                customer_id=reward.customer_id,
                order_id=order_id,
                original_order_amount=float(self._calculate_order_total(order)),
                discount_applied=discount_amount,
                final_order_amount=float(self._calculate_order_total(order))
                - discount_amount,
                redemption_method="manual",
                staff_member_id=staff_member_id,
            )
            self.db.add(redemption)

            # Update template statistics
            template = reward.template
            template.total_redeemed += 1

            # Handle points-based rewards
            if reward.points_cost and reward.points_cost > 0:
                self._deduct_points(
                    reward.customer,
                    reward.points_cost,
                    f"Redeemed reward: {reward.title}",
                    reward_id=reward.id,
                )

            self.db.commit()

            logger.info(
                f"Redeemed reward {reward.code} for ${discount_amount:.2f} discount"
            )

            return {
                "success": True,
                "discount_amount": discount_amount,
                "reward_title": reward.title,
                "points_deducted": reward.points_cost or 0,
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error redeeming reward {reward_code}: {str(e)}")
            return {"success": False, "error": "Failed to process redemption"}

    def get_customer_available_rewards(self, customer_id: int) -> List[CustomerReward]:
        """Get all available rewards for a customer"""
        now = datetime.utcnow()

        rewards = (
            self.db.query(CustomerReward)
            .filter(
                and_(
                    CustomerReward.customer_id == customer_id,
                    CustomerReward.status == RewardStatus.AVAILABLE,
                    CustomerReward.valid_from <= now,
                    CustomerReward.valid_until > now,
                )
            )
            .order_by(CustomerReward.valid_until.asc())
            .all()
        )

        return rewards

    def expire_old_rewards(self) -> int:
        """Expire rewards that have passed their expiration date"""
        now = datetime.utcnow()

        expired_count = (
            self.db.query(CustomerReward)
            .filter(
                and_(
                    CustomerReward.status == RewardStatus.AVAILABLE,
                    CustomerReward.valid_until <= now,
                )
            )
            .update({"status": RewardStatus.EXPIRED})
        )

        self.db.commit()

        if expired_count > 0:
            logger.info(f"Expired {expired_count} old rewards")

        return expired_count

    def run_automated_campaigns(self) -> Dict[str, Any]:
        """Run automated reward campaigns"""
        now = datetime.utcnow()

        # Get active automated campaigns
        campaigns = (
            self.db.query(RewardCampaign)
            .filter(
                and_(
                    RewardCampaign.is_active == True,
                    RewardCampaign.is_automated == True,
                    RewardCampaign.start_date <= now,
                    RewardCampaign.end_date > now,
                )
            )
            .all()
        )

        results = {"campaigns_processed": 0, "rewards_distributed": 0, "errors": []}

        for campaign in campaigns:
            try:
                # Find eligible customers
                eligible_customers = self._find_campaign_eligible_customers(campaign)

                rewards_distributed = 0
                for customer in eligible_customers:
                    # Check if customer already received reward from this campaign
                    existing_rewards = (
                        self.db.query(CustomerReward)
                        .filter(
                            and_(
                                CustomerReward.customer_id == customer.id,
                                CustomerReward.template_id == campaign.template_id,
                                CustomerReward.created_at >= campaign.start_date,
                            )
                        )
                        .count()
                    )

                    if existing_rewards < campaign.max_rewards_per_customer:
                        try:
                            self.issue_reward_to_customer(
                                customer.id,
                                campaign.template_id,
                                custom_data={"campaign_id": campaign.id},
                            )
                            rewards_distributed += 1

                            if (
                                campaign.max_rewards_total
                                and campaign.rewards_distributed + rewards_distributed
                                >= campaign.max_rewards_total
                            ):
                                break

                        except Exception as e:
                            logger.warning(
                                f"Failed to issue campaign reward to customer {customer.id}: {str(e)}"
                            )

                # Update campaign statistics
                campaign.rewards_distributed += rewards_distributed
                results["rewards_distributed"] += rewards_distributed
                results["campaigns_processed"] += 1

            except Exception as e:
                error_msg = f"Error processing campaign {campaign.name}: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)

        self.db.commit()
        return results

    def get_reward_analytics(
        self,
        template_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get analytics for reward performance"""
        query = self.db.query(CustomerReward)

        if template_id:
            query = query.filter(CustomerReward.template_id == template_id)

        if start_date:
            query = query.filter(CustomerReward.created_at >= start_date)

        if end_date:
            query = query.filter(CustomerReward.created_at <= end_date)

        # Get basic statistics
        total_issued = query.count()
        redeemed_count = query.filter(
            CustomerReward.status == RewardStatus.REDEEMED
        ).count()
        expired_count = query.filter(
            CustomerReward.status == RewardStatus.EXPIRED
        ).count()

        # Calculate metrics
        redemption_rate = (
            (redeemed_count / total_issued * 100) if total_issued > 0 else 0
        )

        # Get total discount value
        total_discount = (
            self.db.query(func.sum(RewardRedemption.discount_applied))
            .join(CustomerReward)
            .filter(CustomerReward.template_id == template_id)
            .scalar()
            or 0
        )

        return {
            "total_issued": total_issued,
            "total_redeemed": redeemed_count,
            "total_expired": expired_count,
            "redemption_rate": round(redemption_rate, 2),
            "total_discount_value": float(total_discount),
            "average_discount_per_redemption": (
                float(total_discount / redeemed_count) if redeemed_count > 0 else 0
            ),
        }

    # Private helper methods

    def _calculate_order_total(self, order: Order) -> Decimal:
        """Calculate total order amount"""
        total = Decimal("0")
        for item in order.order_items:
            total += Decimal(str(item.price)) * item.quantity
        return total

    def _get_order_categories(self, order: Order) -> List[str]:
        """Get unique categories from order items"""
        # This would need to be implemented based on your menu item structure
        # For now, return empty list
        return []

    def _award_points(
        self,
        customer: Customer,
        points: int,
        reason: str,
        order_id: Optional[int] = None,
        expires_in_days: int = 365,
    ):
        """Award loyalty points to customer"""
        old_balance = customer.loyalty_points
        customer.loyalty_points += points
        customer.lifetime_points += points

        # Create transaction record
        transaction = LoyaltyPointsTransaction(
            customer_id=customer.id,
            transaction_type="earned",
            points_change=points,
            points_balance_before=old_balance,
            points_balance_after=customer.loyalty_points,
            reason=reason,
            order_id=order_id,
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days),
        )
        self.db.add(transaction)

        # Check tier upgrade
        from modules.customers.services.customer_service import CustomerService

        customer_service = CustomerService(self.db)
        customer_service._check_tier_upgrade(customer)

    def _deduct_points(
        self,
        customer: Customer,
        points: int,
        reason: str,
        reward_id: Optional[int] = None,
    ):
        """Deduct loyalty points from customer"""
        if customer.loyalty_points < points:
            raise ValueError("Insufficient loyalty points")

        old_balance = customer.loyalty_points
        customer.loyalty_points -= points

        # Create transaction record
        transaction = LoyaltyPointsTransaction(
            customer_id=customer.id,
            transaction_type="redeemed",
            points_change=-points,
            points_balance_before=old_balance,
            points_balance_after=customer.loyalty_points,
            reason=reason,
            reward_id=reward_id,
        )
        self.db.add(transaction)

    def _process_trigger_rewards(
        self,
        customer: Customer,
        trigger_type: TriggerType,
        trigger_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Process rewards that should be triggered by an event"""
        # Get active templates for this trigger type
        templates = (
            self.db.query(RewardTemplate)
            .filter(
                and_(
                    RewardTemplate.trigger_type == trigger_type,
                    RewardTemplate.is_active == True,
                )
            )
            .all()
        )

        triggered_rewards = []

        for template in templates:
            try:
                # Check if customer is eligible
                if not self._is_customer_eligible(customer, template):
                    continue

                # Check trigger conditions
                if not self._check_trigger_conditions(template, trigger_data):
                    continue

                # Create reward
                reward = self._create_reward_instance(
                    customer, template, trigger_data=trigger_data
                )
                template.total_issued += 1

                triggered_rewards.append(
                    {
                        "reward_id": reward.id,
                        "reward_code": reward.code,
                        "title": reward.title,
                        "type": reward.reward_type.value,
                    }
                )

            except Exception as e:
                logger.warning(
                    f"Failed to process trigger reward {template.name} for customer {customer.id}: {str(e)}"
                )

        return triggered_rewards

    def _check_milestone_rewards(self, customer: Customer) -> List[Dict[str, Any]]:
        """Check and issue milestone-based rewards"""
        milestone_rewards = []

        # Get milestone templates
        templates = (
            self.db.query(RewardTemplate)
            .filter(
                and_(
                    RewardTemplate.trigger_type == TriggerType.MILESTONE,
                    RewardTemplate.is_active == True,
                )
            )
            .all()
        )

        for template in templates:
            try:
                conditions = template.trigger_conditions or {}

                # Check various milestone conditions
                milestone_met = False

                if "total_orders" in conditions:
                    if customer.total_orders >= conditions["total_orders"]:
                        # Check if we already issued this milestone reward
                        existing = (
                            self.db.query(CustomerReward)
                            .filter(
                                and_(
                                    CustomerReward.customer_id == customer.id,
                                    CustomerReward.template_id == template.id,
                                )
                            )
                            .first()
                        )

                        if not existing:
                            milestone_met = True

                if "total_spent" in conditions:
                    if customer.total_spent >= conditions["total_spent"]:
                        existing = (
                            self.db.query(CustomerReward)
                            .filter(
                                and_(
                                    CustomerReward.customer_id == customer.id,
                                    CustomerReward.template_id == template.id,
                                )
                            )
                            .first()
                        )

                        if not existing:
                            milestone_met = True

                if milestone_met:
                    reward = self._create_reward_instance(customer, template)
                    template.total_issued += 1

                    milestone_rewards.append(
                        {
                            "reward_id": reward.id,
                            "reward_code": reward.code,
                            "title": reward.title,
                            "type": reward.reward_type.value,
                            "milestone": conditions,
                        }
                    )

            except Exception as e:
                logger.warning(
                    f"Failed to process milestone reward {template.name} for customer {customer.id}: {str(e)}"
                )

        return milestone_rewards

    def _is_customer_eligible(
        self, customer: Customer, template: RewardTemplate
    ) -> bool:
        """Check if customer is eligible for a reward template"""
        # Check tier eligibility
        if template.eligible_tiers:
            if customer.tier.value.lower() not in template.eligible_tiers:
                return False

        # Check usage limits
        if template.max_uses_per_customer:
            existing_rewards = (
                self.db.query(CustomerReward)
                .filter(
                    and_(
                        CustomerReward.customer_id == customer.id,
                        CustomerReward.template_id == template.id,
                    )
                )
                .count()
            )

            if existing_rewards >= template.max_uses_per_customer:
                return False

        # Additional eligibility checks can be added here
        return True

    def _check_trigger_conditions(
        self, template: RewardTemplate, trigger_data: Dict[str, Any]
    ) -> bool:
        """Check if trigger conditions are met"""
        if not template.trigger_conditions:
            return True

        conditions = template.trigger_conditions

        # Check minimum order amount
        if "min_order_amount" in conditions:
            order_total = trigger_data.get("order_total", 0)
            if order_total < conditions["min_order_amount"]:
                return False

        # Additional condition checks can be added here
        return True

    def _create_reward_instance(
        self,
        customer: Customer,
        template: RewardTemplate,
        issued_by: Optional[int] = None,
        trigger_data: Optional[Dict[str, Any]] = None,
    ) -> CustomerReward:
        """Create a reward instance from template"""
        # Generate unique reward code
        reward_code = self._generate_reward_code()

        # Calculate expiration date
        valid_until = datetime.utcnow() + timedelta(days=template.valid_days)
        if template.valid_until_date and template.valid_until_date < valid_until:
            valid_until = template.valid_until_date

        reward = CustomerReward(
            customer_id=customer.id,
            template_id=template.id,
            reward_type=template.reward_type,
            title=template.title,
            description=template.description,
            value=template.value,
            percentage=template.percentage,
            points_cost=template.points_cost,
            code=reward_code,
            valid_until=valid_until,
            issued_by=issued_by,
            trigger_data=trigger_data,
        )

        self.db.add(reward)
        return reward

    def _generate_reward_code(self) -> str:
        """Generate unique reward code"""
        while True:
            code = "".join(
                secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8)
            )
            existing = (
                self.db.query(CustomerReward)
                .filter(CustomerReward.code == code)
                .first()
            )
            if not existing:
                return code

    def _calculate_reward_discount(
        self, reward: CustomerReward, order: Order
    ) -> Dict[str, Any]:
        """Calculate discount amount for reward redemption"""
        order_total = float(self._calculate_order_total(order))

        # Check minimum order amount
        template = reward.template
        if template.min_order_amount and order_total < template.min_order_amount:
            return {
                "valid": False,
                "error": f"Minimum order amount of ${template.min_order_amount:.2f} required",
            }

        discount_amount = 0.0

        if reward.reward_type == RewardType.FIXED_DISCOUNT:
            discount_amount = float(reward.value) if reward.value else 0.0

        elif reward.reward_type == RewardType.PERCENTAGE_DISCOUNT:
            discount_amount = (
                order_total * (float(reward.percentage) / 100)
                if reward.percentage
                else 0.0
            )

        elif reward.reward_type == RewardType.FREE_DELIVERY:
            # Calculate delivery fee (this would need to be implemented based on your delivery system)
            discount_amount = 5.0  # Default delivery fee

        elif reward.reward_type == RewardType.FREE_ITEM:
            # Calculate item price (this would need menu item lookup)
            discount_amount = float(reward.value) if reward.value else 0.0

        # Apply maximum discount limit
        if template.max_discount_amount:
            discount_amount = min(discount_amount, template.max_discount_amount)

        # Don't allow discount to exceed order total
        discount_amount = min(discount_amount, order_total)

        return {"valid": True, "discount_amount": discount_amount}

    def _find_campaign_eligible_customers(
        self, campaign: RewardCampaign
    ) -> List[Customer]:
        """Find customers eligible for a campaign"""
        query = self.db.query(Customer).filter(Customer.deleted_at.is_(None))

        # Apply tier filters
        if campaign.target_tiers:
            tier_values = [
                getattr(CustomerTier, tier.upper())
                for tier in campaign.target_tiers
                if hasattr(CustomerTier, tier.upper())
            ]
            query = query.filter(Customer.tier.in_(tier_values))

        # Apply other targeting criteria
        if campaign.target_criteria:
            criteria = campaign.target_criteria

            if "min_total_spent" in criteria:
                query = query.filter(
                    Customer.total_spent >= criteria["min_total_spent"]
                )

            if "min_total_orders" in criteria:
                query = query.filter(
                    Customer.total_orders >= criteria["min_total_orders"]
                )

            if "inactive_days" in criteria:
                cutoff_date = datetime.utcnow() - timedelta(
                    days=criteria["inactive_days"]
                )
                query = query.filter(
                    or_(
                        Customer.last_order_date.is_(None),
                        Customer.last_order_date <= cutoff_date,
                    )
                )

        return query.limit(1000).all()  # Limit to prevent excessive processing
