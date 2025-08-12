"""
Order prioritization service implementing various priority algorithms.
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
import math
import json
from decimal import Decimal

from ..models.priority_models import (
    PriorityRule, PriorityProfile, PriorityProfileRule,
    QueuePriorityConfig, OrderPriorityScore, PriorityAdjustmentLog,
    PriorityAlgorithmType, PriorityScoreType
)
from ..models.order_models import Order, OrderPriority
from ..models.queue_models import QueueItem, OrderQueue, QueueItemStatus
from ...customers.models.customer_models import Customer, CustomerTier
from ...menu.models.menu_models import MenuItem


class PriorityService:
    """Service for calculating and managing order priorities"""
    
    def __init__(self, db: Session):
        self.db = db
        self._algorithm_handlers = {
            PriorityAlgorithmType.PREPARATION_TIME: self._calculate_prep_time_priority,
            PriorityAlgorithmType.DELIVERY_WINDOW: self._calculate_delivery_window_priority,
            PriorityAlgorithmType.VIP_STATUS: self._calculate_vip_priority,
            PriorityAlgorithmType.ORDER_VALUE: self._calculate_order_value_priority,
            PriorityAlgorithmType.WAIT_TIME: self._calculate_wait_time_priority,
            PriorityAlgorithmType.ITEM_COMPLEXITY: self._calculate_complexity_priority,
        }
    
    def calculate_order_priority(
        self,
        order_id: int,
        queue_id: int,
        profile_override: Optional[int] = None
    ) -> OrderPriorityScore:
        """Calculate priority score for an order in a specific queue"""
        
        # Get order and queue
        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        queue = self.db.query(OrderQueue).filter(OrderQueue.id == queue_id).first()
        if not queue:
            raise ValueError(f"Queue {queue_id} not found")
        
        # Get priority profile
        profile = self._get_priority_profile(queue_id, profile_override)
        if not profile:
            # Use default scoring if no profile
            return self._create_default_priority_score(order, queue)
        
        # Calculate component scores
        component_scores = {}
        total_weight = 0
        
        for profile_rule in profile.profile_rules:
            if not profile_rule.rule.is_active:
                continue
            
            # Check if rule conditions are met
            if not self._check_rule_conditions(profile_rule.rule, order, queue):
                continue
            
            # Calculate score for this rule
            try:
                score = self._calculate_rule_score(profile_rule.rule, order, queue)
                
                # Apply weight override if specified
                weight = profile_rule.weight_override or profile_rule.rule.weight
                
                # Apply thresholds
                if profile_rule.min_threshold and score < profile_rule.min_threshold:
                    score = 0
                elif profile_rule.max_threshold and score > profile_rule.max_threshold:
                    score = profile_rule.max_threshold
                
                component_scores[profile_rule.rule.algorithm_type.value] = {
                    "score": score,
                    "weight": weight,
                    "weighted_score": score * weight
                }
                total_weight += weight
                
            except Exception as e:
                # Use fallback score if calculation fails
                if profile_rule.is_required:
                    raise ValueError(f"Required rule {profile_rule.rule.name} failed: {str(e)}")
                
                component_scores[profile_rule.rule.algorithm_type.value] = {
                    "score": profile_rule.fallback_score,
                    "weight": weight,
                    "weighted_score": profile_rule.fallback_score * weight,
                    "error": str(e)
                }
                total_weight += weight
        
        # Calculate total score
        total_score = sum(c["weighted_score"] for c in component_scores.values())
        
        # Normalize if requested
        if profile.normalize_scores and total_weight > 0:
            if profile.normalization_method == "min_max":
                # Min-max normalization to 0-100
                normalized_score = (total_score / total_weight) * 100
            else:
                normalized_score = total_score
        else:
            normalized_score = total_score
        
        # Apply queue-specific boosts
        config = self.db.query(QueuePriorityConfig).filter(
            QueuePriorityConfig.queue_id == queue_id
        ).first()
        
        if config:
            # VIP boost
            if order.customer_id:
                customer = self.db.query(Customer).filter(
                    Customer.id == order.customer_id
                ).first()
                if customer and customer.tier in [CustomerTier.VIP, CustomerTier.PLATINUM]:
                    total_score += config.priority_boost_vip
                    normalized_score += config.priority_boost_vip
            
            # Delay boost
            if order.scheduled_fulfillment_time:
                now = datetime.utcnow()
                if now > order.scheduled_fulfillment_time:
                    total_score += config.priority_boost_delayed
                    normalized_score += config.priority_boost_delayed
            
            # Large party boost
            if hasattr(order, 'party_size') and order.party_size > 6:
                total_score += config.priority_boost_large_party
                normalized_score += config.priority_boost_large_party
            
            # Peak hours multiplier
            if config.peak_hours and self._is_peak_hour(config.peak_hours):
                total_score *= config.peak_multiplier
                normalized_score *= config.peak_multiplier
        
        # Determine priority tier
        priority_tier = self._determine_priority_tier(normalized_score)
        
        # Create or update priority score record
        priority_score = self.db.query(OrderPriorityScore).filter(
            and_(
                OrderPriorityScore.order_id == order_id,
                OrderPriorityScore.queue_id == queue_id
            )
        ).first()
        
        if not priority_score:
            priority_score = OrderPriorityScore(
                order_id=order_id,
                queue_id=queue_id
            )
            self.db.add(priority_score)
        
        priority_score.total_score = total_score
        priority_score.normalized_score = normalized_score
        priority_score.score_components = component_scores
        priority_score.profile_used = profile.name
        priority_score.calculated_at = datetime.utcnow()
        priority_score.factors_applied = {
            "profile_id": profile.id,
            "total_weight": total_weight,
            "boosts_applied": {
                "vip": config.priority_boost_vip if config else 0,
                "delayed": config.priority_boost_delayed if config else 0,
                "large_party": config.priority_boost_large_party if config else 0
            }
        }
        priority_score.priority_tier = priority_tier
        
        self.db.commit()
        
        return priority_score
    
    def _calculate_prep_time_priority(self, rule: PriorityRule, order: Order, queue: OrderQueue) -> float:
        """Calculate priority based on preparation time"""
        params = rule.parameters or {}
        base_minutes = params.get("base_minutes", 15)
        penalty_per_minute = params.get("penalty_per_minute", 2)
        
        # Get estimated prep time
        prep_time = self._estimate_prep_time(order)
        
        # Calculate score based on how prep time compares to base
        if prep_time <= base_minutes:
            # Bonus for quick items
            score = rule.max_score
        else:
            # Penalty for longer prep times
            overtime = prep_time - base_minutes
            score = rule.max_score - (overtime * penalty_per_minute)
            score = max(score, rule.min_score)
        
        return self._apply_score_function(score, rule)
    
    def _calculate_delivery_window_priority(self, rule: PriorityRule, order: Order, queue: OrderQueue) -> float:
        """Calculate priority based on delivery window"""
        params = rule.parameters or {}
        grace_minutes = params.get("grace_minutes", 10)
        critical_minutes = params.get("critical_minutes", 30)
        
        if not order.scheduled_fulfillment_time:
            return rule.min_score
        
        now = datetime.utcnow()
        time_until_due = (order.scheduled_fulfillment_time - now).total_seconds() / 60
        
        if time_until_due <= 0:
            # Already late
            score = rule.max_score
        elif time_until_due <= grace_minutes:
            # Within grace period - highest priority
            score = rule.max_score * 0.9
        elif time_until_due <= critical_minutes:
            # Approaching deadline
            ratio = 1 - (time_until_due - grace_minutes) / (critical_minutes - grace_minutes)
            score = rule.min_score + (rule.max_score - rule.min_score) * ratio
        else:
            # Plenty of time
            score = rule.min_score
        
        return self._apply_score_function(score, rule)
    
    def _calculate_vip_priority(self, rule: PriorityRule, order: Order, queue: OrderQueue) -> float:
        """Calculate priority based on VIP status"""
        params = rule.parameters or {}
        tier_scores = params.get("tier_scores", {
            "bronze": 10,
            "silver": 20,
            "gold": 30,
            "platinum": 50,
            "vip": 100
        })
        
        if not order.customer_id:
            return rule.min_score
        
        customer = self.db.query(Customer).filter(Customer.id == order.customer_id).first()
        if not customer:
            return rule.min_score
        
        # Get score for customer tier
        tier_value = customer.tier.value if hasattr(customer.tier, 'value') else str(customer.tier).lower()
        base_score = tier_scores.get(tier_value, rule.min_score)
        
        # Additional factors for VIP customers
        if hasattr(customer, 'lifetime_value'):
            # Bonus based on lifetime value
            ltv_bonus = min(float(customer.lifetime_value) / 1000, 20)  # Max 20 point bonus
            base_score += ltv_bonus
        
        # Normalize to rule's score range
        score = rule.min_score + (base_score / 100) * (rule.max_score - rule.min_score)
        
        return self._apply_score_function(score, rule)
    
    def _calculate_order_value_priority(self, rule: PriorityRule, order: Order, queue: OrderQueue) -> float:
        """Calculate priority based on order value"""
        params = rule.parameters or {}
        min_value = params.get("min_value", 0)
        max_value = params.get("max_value", 200)
        
        # Get order total
        order_total = float(order.total_amount or 0)
        
        # Normalize to score range
        if order_total <= min_value:
            score = rule.min_score
        elif order_total >= max_value:
            score = rule.max_score
        else:
            ratio = (order_total - min_value) / (max_value - min_value)
            score = rule.min_score + ratio * (rule.max_score - rule.min_score)
        
        return self._apply_score_function(score, rule)
    
    def _calculate_wait_time_priority(self, rule: PriorityRule, order: Order, queue: OrderQueue) -> float:
        """Calculate priority based on wait time"""
        params = rule.parameters or {}
        base_wait_minutes = params.get("base_wait_minutes", 5)
        max_wait_minutes = params.get("max_wait_minutes", 30)
        
        # Get queue item to check wait time
        queue_item = self.db.query(QueueItem).filter(
            and_(
                QueueItem.order_id == order.id,
                QueueItem.queue_id == queue.id
            )
        ).first()
        
        if not queue_item or not queue_item.queued_at:
            return rule.min_score
        
        # Calculate wait time
        wait_time = (datetime.utcnow() - queue_item.queued_at).total_seconds() / 60
        
        if wait_time <= base_wait_minutes:
            score = rule.min_score
        elif wait_time >= max_wait_minutes:
            score = rule.max_score
        else:
            ratio = (wait_time - base_wait_minutes) / (max_wait_minutes - base_wait_minutes)
            score = rule.min_score + ratio * (rule.max_score - rule.min_score)
        
        return self._apply_score_function(score, rule)
    
    def _calculate_complexity_priority(self, rule: PriorityRule, order: Order, queue: OrderQueue) -> float:
        """Calculate priority based on order complexity"""
        params = rule.parameters or {}
        item_weights = params.get("item_weights", {})
        complexity_threshold = params.get("complexity_threshold", 10)
        
        # Calculate complexity score
        complexity = 0
        
        for item in order.order_items:
            # Get menu item details
            menu_item = self.db.query(MenuItem).filter(
                MenuItem.id == item.menu_item_id
            ).first()
            
            if menu_item:
                # Check item category for complexity
                category_weight = item_weights.get(menu_item.category_id, 1)
                complexity += item.quantity * category_weight
                
                # Add modifier complexity
                if item.special_instructions:
                    complexity += len(item.special_instructions) * 0.5
        
        # Invert complexity for priority (simpler orders get higher priority)
        if complexity <= complexity_threshold:
            score = rule.max_score
        else:
            # More complex orders get lower priority
            score = rule.max_score - (complexity - complexity_threshold) * 2
            score = max(score, rule.min_score)
        
        return self._apply_score_function(score, rule)
    
    def _apply_score_function(self, base_score: float, rule: PriorityRule) -> float:
        """Apply scoring function to base score"""
        if rule.score_type == PriorityScoreType.LINEAR:
            return base_score
        elif rule.score_type == PriorityScoreType.EXPONENTIAL:
            # Exponential scaling
            normalized = (base_score - rule.min_score) / (rule.max_score - rule.min_score)
            return rule.min_score + (math.exp(normalized) - 1) / (math.e - 1) * (rule.max_score - rule.min_score)
        elif rule.score_type == PriorityScoreType.LOGARITHMIC:
            # Logarithmic scaling
            normalized = (base_score - rule.min_score) / (rule.max_score - rule.min_score)
            if normalized > 0:
                return rule.min_score + math.log(1 + normalized * 9) / math.log(10) * (rule.max_score - rule.min_score)
            return rule.min_score
        elif rule.score_type == PriorityScoreType.STEP:
            # Step function
            steps = rule.parameters.get("steps", [25, 50, 75])
            for i, threshold in enumerate(steps):
                if base_score <= threshold:
                    return rule.min_score + (i / len(steps)) * (rule.max_score - rule.min_score)
            return rule.max_score
        elif rule.score_type == PriorityScoreType.CUSTOM and rule.score_function:
            # Custom function (evaluate safely)
            try:
                # Create safe namespace for evaluation
                namespace = {
                    "score": base_score,
                    "min": rule.min_score,
                    "max": rule.max_score,
                    "math": math
                }
                return eval(rule.score_function, {"__builtins__": {}}, namespace)
            except:
                return base_score
        
        return base_score
    
    def _get_priority_profile(self, queue_id: int, profile_override: Optional[int] = None) -> Optional[PriorityProfile]:
        """Get priority profile for queue"""
        if profile_override:
            return self.db.query(PriorityProfile).filter(
                and_(
                    PriorityProfile.id == profile_override,
                    PriorityProfile.is_active == True
                )
            ).first()
        
        # Get queue configuration
        config = self.db.query(QueuePriorityConfig).filter(
            QueuePriorityConfig.queue_id == queue_id
        ).first()
        
        if config and config.priority_profile:
            return config.priority_profile
        
        # Get default profile
        return self.db.query(PriorityProfile).filter(
            and_(
                PriorityProfile.is_default == True,
                PriorityProfile.is_active == True
            )
        ).first()
    
    def _check_rule_conditions(self, rule: PriorityRule, order: Order, queue: OrderQueue) -> bool:
        """Check if rule conditions are met"""
        conditions = rule.conditions or {}
        
        # Check order type
        if "order_type" in conditions:
            if order.category_id not in conditions["order_type"]:
                return False
        
        # Check minimum order value
        if "min_order_value" in conditions:
            if float(order.total_amount or 0) < conditions["min_order_value"]:
                return False
        
        # Check queue type
        if "queue_types" in conditions:
            if queue.queue_type.value not in conditions["queue_types"]:
                return False
        
        # Check time of day
        if "time_ranges" in conditions:
            current_hour = datetime.utcnow().hour
            in_range = False
            for time_range in conditions["time_ranges"]:
                start_hour = time_range.get("start_hour", 0)
                end_hour = time_range.get("end_hour", 24)
                if start_hour <= current_hour < end_hour:
                    in_range = True
                    break
            if not in_range:
                return False
        
        return True
    
    def _create_default_priority_score(self, order: Order, queue: OrderQueue) -> OrderPriorityScore:
        """Create default priority score when no profile is configured"""
        # Simple FIFO with basic priority consideration
        base_score = 50.0
        
        # Add points for high priority orders
        if order.priority == OrderPriority.HIGH:
            base_score += 20
        elif order.priority == OrderPriority.URGENT:
            base_score += 30
        
        priority_score = OrderPriorityScore(
            order_id=order.id,
            queue_id=queue.id,
            total_score=base_score,
            normalized_score=base_score,
            score_components={"default": {"score": base_score, "weight": 1, "weighted_score": base_score}},
            profile_used="default",
            calculated_at=datetime.utcnow(),
            priority_tier=self._determine_priority_tier(base_score)
        )
        
        self.db.add(priority_score)
        self.db.commit()
        
        return priority_score
    
    def _estimate_prep_time(self, order: Order) -> float:
        """Estimate preparation time for an order"""
        total_time = 0
        
        for item in order.order_items:
            # Get menu item
            menu_item = self.db.query(MenuItem).filter(
                MenuItem.id == item.menu_item_id
            ).first()
            
            if menu_item:
                # Use item's prep time if available
                item_time = getattr(menu_item, 'prep_time_minutes', 10)
                total_time += item_time * item.quantity
        
        return total_time
    
    def _determine_priority_tier(self, score: float) -> str:
        """Determine priority tier based on score"""
        if score >= 80:
            return "critical"
        elif score >= 60:
            return "high"
        elif score >= 40:
            return "medium"
        else:
            return "low"
    
    def _is_peak_hour(self, peak_hours: List[Dict]) -> bool:
        """Check if current time is during peak hours"""
        now = datetime.utcnow()
        current_hour = now.hour
        current_day = now.weekday()  # 0 = Monday
        
        for peak in peak_hours:
            # Check day of week
            if "days" in peak and current_day not in peak["days"]:
                continue
            
            # Check hour range
            start_hour = peak.get("start_hour", 0)
            end_hour = peak.get("end_hour", 24)
            
            if start_hour <= current_hour < end_hour:
                return True
        
        return False
    
    def rebalance_queue(self, queue_id: int) -> Dict[str, Any]:
        """Rebalance queue based on current priorities"""
        # Get queue configuration
        config = self.db.query(QueuePriorityConfig).filter(
            QueuePriorityConfig.queue_id == queue_id
        ).first()
        
        if not config or not config.rebalance_enabled:
            return {"rebalanced": False, "reason": "Rebalancing disabled"}
        
        # Get all active queue items
        queue_items = self.db.query(QueueItem).filter(
            and_(
                QueueItem.queue_id == queue_id,
                QueueItem.status.in_([QueueItemStatus.QUEUED, QueueItemStatus.ON_HOLD])
            )
        ).order_by(QueueItem.sequence_number).all()
        
        if len(queue_items) < 2:
            return {"rebalanced": False, "reason": "Not enough items to rebalance"}
        
        # Recalculate priorities for all items
        priority_scores = []
        for item in queue_items:
            try:
                score = self.calculate_order_priority(item.order_id, queue_id)
                priority_scores.append((item, score.total_score))
            except Exception as e:
                # Use current sequence as fallback
                priority_scores.append((item, 0))
        
        # Sort by priority score (descending)
        priority_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Track changes
        changes = []
        
        # Reassign sequence numbers based on priority
        for new_sequence, (item, score) in enumerate(priority_scores, 1):
            if item.sequence_number != new_sequence:
                # Limit position changes
                if config.max_position_change:
                    max_change = config.max_position_change
                    if abs(item.sequence_number - new_sequence) > max_change:
                        # Limit the change
                        if new_sequence < item.sequence_number:
                            new_sequence = item.sequence_number - max_change
                        else:
                            new_sequence = item.sequence_number + max_change
                
                changes.append({
                    "order_id": item.order_id,
                    "old_sequence": item.sequence_number,
                    "new_sequence": new_sequence,
                    "priority_score": score
                })
                
                item.sequence_number = new_sequence
        
        self.db.commit()
        
        return {
            "rebalanced": True,
            "items_reordered": len(changes),
            "changes": changes
        }
    
    def adjust_priority_manual(
        self,
        order_id: int,
        queue_id: int,
        new_priority: float,
        reason: str,
        user_id: int
    ) -> PriorityAdjustmentLog:
        """Manually adjust order priority"""
        # Get current priority
        priority_score = self.db.query(OrderPriorityScore).filter(
            and_(
                OrderPriorityScore.order_id == order_id,
                OrderPriorityScore.queue_id == queue_id
            )
        ).first()
        
        if not priority_score:
            raise ValueError("No priority score found for order")
        
        # Get queue item
        queue_item = self.db.query(QueueItem).filter(
            and_(
                QueueItem.order_id == order_id,
                QueueItem.queue_id == queue_id
            )
        ).first()
        
        if not queue_item:
            raise ValueError("Order not in queue")
        
        # Create adjustment log
        adjustment = PriorityAdjustmentLog(
            order_id=order_id,
            queue_item_id=queue_item.id,
            old_priority=priority_score.total_score,
            new_priority=new_priority,
            old_sequence=queue_item.sequence_number,
            adjustment_reason=reason,
            adjusted_by_id=user_id
        )
        
        # Update priority score
        old_score = priority_score.total_score
        priority_score.total_score = new_priority
        priority_score.normalized_score = new_priority
        priority_score.score_components["manual_adjustment"] = {
            "score": new_priority - old_score,
            "weight": 1,
            "weighted_score": new_priority - old_score
        }
        
        # Rebalance queue to apply new priority
        rebalance_result = self.rebalance_queue(queue_id)
        
        # Update adjustment log with new sequence
        queue_item.refresh_from_db(self.db)
        adjustment.new_sequence = queue_item.sequence_number
        adjustment.affected_orders = rebalance_result.get("changes", [])
        
        self.db.add(adjustment)
        self.db.commit()
        
        return adjustment