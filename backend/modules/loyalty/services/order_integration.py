# backend/modules/loyalty/services/order_integration.py

from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from datetime import datetime
import logging

from .rewards_engine import RewardsEngine
from modules.orders.models.order_models import Order
from modules.customers.models.customer_models import Customer


logger = logging.getLogger(__name__)


class OrderLoyaltyIntegration:
    """Integration service for processing loyalty rewards when orders are completed"""
    
    def __init__(self, db: Session):
        self.db = db
        self.rewards_engine = RewardsEngine(db)
    
    def process_order_completion(self, order_id: int) -> Dict[str, Any]:
        """Process loyalty rewards and points when an order is completed"""
        logger.info(f"Processing loyalty rewards for order {order_id}")
        
        try:
            # Use the rewards engine to process the order
            result = self.rewards_engine.process_order_completion(order_id)
            
            # Send notifications if enabled
            if result.get("success") and result.get("rewards_triggered"):
                self._send_reward_notifications(order_id, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing order loyalty for order {order_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "points_earned": 0,
                "rewards_triggered": [],
                "tier_upgrade": None
            }
    
    def apply_reward_discount(self, order_id: int, reward_code: str) -> Dict[str, Any]:
        """Apply a reward discount to an order during checkout"""
        try:
            # Get the order
            order = self.db.query(Order).filter(Order.id == order_id).first()
            if not order:
                return {"success": False, "error": "Order not found"}
            
            # Redeem the reward
            result = self.rewards_engine.redeem_reward(
                reward_code=reward_code,
                order_id=order_id
            )
            
            if result.get("success"):
                # Here you would typically update the order total
                # This depends on your order system implementation
                logger.info(f"Applied reward discount of ${result['discount_amount']:.2f} to order {order_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error applying reward to order {order_id}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_applicable_rewards(self, customer_id: int, order_total: float) -> Dict[str, Any]:
        """Get rewards that can be applied to an order"""
        try:
            # Get customer's available rewards
            available_rewards = self.rewards_engine.get_customer_available_rewards(customer_id)
            
            # Filter rewards that can be applied to this order
            applicable_rewards = []
            
            for reward in available_rewards:
                template = reward.template
                
                # Check minimum order amount
                if template.min_order_amount and order_total < template.min_order_amount:
                    continue
                
                # Calculate potential discount
                discount_result = self.rewards_engine._calculate_reward_discount(reward, None)
                if discount_result.get("valid", False):
                    applicable_rewards.append({
                        "reward_id": reward.id,
                        "code": reward.code,
                        "title": reward.title,
                        "description": reward.description,
                        "reward_type": reward.reward_type.value,
                        "potential_discount": discount_result.get("discount_amount", 0),
                        "points_cost": reward.points_cost,
                        "expires_in_days": reward.days_until_expiry
                    })
            
            # Sort by potential discount value (highest first)
            applicable_rewards.sort(key=lambda x: x["potential_discount"], reverse=True)
            
            return {
                "success": True,
                "applicable_rewards": applicable_rewards,
                "total_potential_savings": sum(r["potential_discount"] for r in applicable_rewards)
            }
            
        except Exception as e:
            logger.error(f"Error getting applicable rewards for customer {customer_id}: {str(e)}")
            return {"success": False, "error": str(e), "applicable_rewards": []}
    
    def calculate_points_preview(self, customer_id: int, order_total: float) -> Dict[str, Any]:
        """Calculate points that would be earned for an order (preview)"""
        try:
            customer = self.db.query(Customer).filter(Customer.id == customer_id).first()
            if not customer:
                return {"success": False, "error": "Customer not found"}
            
            # Calculate points using the loyalty service
            points_to_earn = self.rewards_engine.loyalty_service.calculate_points_earned(
                action_type="order",
                amount=order_total,
                customer_tier=customer.tier.value.lower()
            )
            
            # Check if this would trigger tier upgrade
            new_lifetime_points = customer.lifetime_points + points_to_earn
            
            # Determine potential tier upgrade
            current_tier = customer.tier.value.lower()
            potential_tier = self.rewards_engine.loyalty_service.calculate_tier_for_customer_points(new_lifetime_points)
            
            tier_upgrade = None
            if potential_tier != current_tier:
                tier_upgrade = {
                    "current_tier": current_tier,
                    "new_tier": potential_tier,
                    "tier_benefits": self.rewards_engine.loyalty_service.get_tier_benefits(potential_tier)
                }
            
            return {
                "success": True,
                "points_to_earn": points_to_earn,
                "current_points": customer.loyalty_points,
                "points_after_order": customer.loyalty_points + points_to_earn,
                "tier_upgrade": tier_upgrade
            }
            
        except Exception as e:
            logger.error(f"Error calculating points preview: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def handle_order_cancellation(self, order_id: int) -> Dict[str, Any]:
        """Handle loyalty points and rewards when an order is cancelled"""
        try:
            # Get the order
            order = self.db.query(Order).filter(Order.id == order_id).first()
            if not order or not order.customer_id:
                return {"success": False, "error": "Order not found or no customer"}
            
            customer = self.db.query(Customer).filter(Customer.id == order.customer_id).first()
            if not customer:
                return {"success": False, "error": "Customer not found"}
            
            # Reverse any points that were awarded for this order
            from ..models.rewards_models import LoyaltyPointsTransaction
            
            order_transactions = self.db.query(LoyaltyPointsTransaction).filter(
                LoyaltyPointsTransaction.customer_id == customer.id,
                LoyaltyPointsTransaction.order_id == order_id,
                LoyaltyPointsTransaction.transaction_type == "earned"
            ).all()
            
            points_reversed = 0
            for transaction in order_transactions:
                # Create reversal transaction
                reversal = LoyaltyPointsTransaction(
                    customer_id=customer.id,
                    transaction_type="adjusted",
                    points_change=-transaction.points_change,
                    points_balance_before=customer.loyalty_points,
                    points_balance_after=customer.loyalty_points - transaction.points_change,
                    reason=f"Order #{order_id} cancelled - points reversed",
                    order_id=order_id,
                    source="system"
                )
                self.db.add(reversal)
                
                # Update customer balance
                customer.loyalty_points -= transaction.points_change
                customer.lifetime_points -= transaction.points_change
                points_reversed += transaction.points_change
            
            # Mark any order-triggered rewards as revoked
            from ..models.rewards_models import CustomerReward, RewardStatus
            
            order_rewards = self.db.query(CustomerReward).filter(
                CustomerReward.customer_id == customer.id,
                CustomerReward.trigger_data.contains({"order_id": order_id}),
                CustomerReward.status == RewardStatus.AVAILABLE
            ).all()
            
            rewards_revoked = 0
            for reward in order_rewards:
                reward.status = RewardStatus.REVOKED
                reward.revoked_at = datetime.utcnow()
                reward.revoked_reason = f"Order #{order_id} cancelled"
                rewards_revoked += 1
            
            self.db.commit()
            
            logger.info(f"Order cancellation processed: {points_reversed} points reversed, {rewards_revoked} rewards revoked")
            
            return {
                "success": True,
                "points_reversed": points_reversed,
                "rewards_revoked": rewards_revoked
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error handling order cancellation for order {order_id}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def handle_partial_refund(self, order_id: int, refund_amount: float) -> Dict[str, Any]:
        """Handle loyalty adjustments for partial refunds"""
        try:
            # Get the order
            order = self.db.query(Order).filter(Order.id == order_id).first()
            if not order or not order.customer_id:
                return {"success": False, "error": "Order not found or no customer"}
            
            customer = self.db.query(Customer).filter(Customer.id == order.customer_id).first()
            if not customer:
                return {"success": False, "error": "Customer not found"}
            
            # Calculate original order total
            original_total = sum(item.price * item.quantity for item in order.order_items)
            
            # Calculate points to reverse based on refund percentage
            refund_percentage = refund_amount / original_total if original_total > 0 else 0
            
            # Get points earned from this order
            from ..models.rewards_models import LoyaltyPointsTransaction
            
            order_transactions = self.db.query(LoyaltyPointsTransaction).filter(
                LoyaltyPointsTransaction.customer_id == customer.id,
                LoyaltyPointsTransaction.order_id == order_id,
                LoyaltyPointsTransaction.transaction_type == "earned"
            ).all()
            
            points_to_reverse = 0
            for transaction in order_transactions:
                points_to_reverse += int(transaction.points_change * refund_percentage)
            
            if points_to_reverse > 0:
                # Create adjustment transaction
                adjustment = LoyaltyPointsTransaction(
                    customer_id=customer.id,
                    transaction_type="adjusted",
                    points_change=-points_to_reverse,
                    points_balance_before=customer.loyalty_points,
                    points_balance_after=customer.loyalty_points - points_to_reverse,
                    reason=f"Partial refund for order #{order_id} - ${refund_amount:.2f}",
                    order_id=order_id,
                    source="system"
                )
                self.db.add(adjustment)
                
                # Update customer balance
                customer.loyalty_points = max(0, customer.loyalty_points - points_to_reverse)
                customer.lifetime_points = max(0, customer.lifetime_points - points_to_reverse)
                customer.total_spent = max(0, customer.total_spent - refund_amount)
            
            self.db.commit()
            
            logger.info(f"Partial refund processed: {points_to_reverse} points adjusted")
            
            return {
                "success": True,
                "points_adjusted": points_to_reverse,
                "refund_amount": refund_amount
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error handling partial refund for order {order_id}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _send_reward_notifications(self, order_id: int, loyalty_result: Dict[str, Any]):
        """Send notifications about earned rewards and points"""
        try:
            # This would integrate with your notification system
            # For now, just log the notifications
            
            if loyalty_result.get("points_earned", 0) > 0:
                logger.info(f"Notification: Customer earned {loyalty_result['points_earned']} points from order {order_id}")
            
            if loyalty_result.get("rewards_triggered"):
                for reward in loyalty_result["rewards_triggered"]:
                    logger.info(f"Notification: Customer received reward '{reward['title']}' from order {order_id}")
            
            if loyalty_result.get("tier_upgrade"):
                tier_info = loyalty_result["tier_upgrade"]
                logger.info(f"Notification: Customer upgraded from {tier_info['old_tier']} to {tier_info['new_tier']}")
            
        except Exception as e:
            logger.warning(f"Error sending reward notifications: {str(e)}")


# Webhook handlers for order system integration
class OrderWebhookHandlers:
    """Webhook handlers for order system events"""
    
    def __init__(self, db: Session):
        self.integration = OrderLoyaltyIntegration(db)
    
    def on_order_completed(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle order completion webhook"""
        order_id = order_data.get("order_id")
        if not order_id:
            return {"success": False, "error": "Missing order_id"}
        
        return self.integration.process_order_completion(order_id)
    
    def on_order_cancelled(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle order cancellation webhook"""
        order_id = order_data.get("order_id")
        if not order_id:
            return {"success": False, "error": "Missing order_id"}
        
        return self.integration.handle_order_cancellation(order_id)
    
    def on_order_refunded(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle order refund webhook"""
        order_id = order_data.get("order_id")
        refund_amount = order_data.get("refund_amount")
        
        if not order_id or refund_amount is None:
            return {"success": False, "error": "Missing order_id or refund_amount"}
        
        # Full refund
        if order_data.get("full_refund", False):
            return self.integration.handle_order_cancellation(order_id)
        else:
            # Partial refund
            return self.integration.handle_partial_refund(order_id, refund_amount)


# Utility functions for menu system integration
def get_order_categories(order: Order) -> list:
    """Get categories from order items (to be implemented based on menu structure)"""
    # This would need to be implemented based on your menu item structure
    # For now, return empty list as placeholder
    return []


def calculate_order_total(order: Order) -> float:
    """Calculate total order amount"""
    total = 0.0
    for item in order.order_items:
        total += float(item.price) * item.quantity
    return total