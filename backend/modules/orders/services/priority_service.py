"""
Priority calculation and management service for intelligent order queue prioritization.
"""

import math
import time
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
import json
import logging
from decimal import Decimal

from ..models.priority_models import (
    PriorityRule, PriorityProfile, PriorityProfileRule,
    QueuePriorityConfig, OrderPriorityScore, PriorityAdjustmentLog,
    PriorityMetrics, PriorityAlgorithm, PriorityScoreType
)
from ..models.queue_models import (
    OrderQueue, QueueItem, QueueStatus, QueueItemStatus
)
from ..models.order_models import Order
from ..schemas.priority_schemas import (
    QueueRebalanceResponse, BulkPriorityCalculateResponse
)
from modules.customers.models import Customer
from modules.loyalty.models import LoyaltyProgram
from core.exceptions import ValidationError, NotFoundError

logger = logging.getLogger(__name__)


class PriorityService:
    """Service for managing order priority calculations and queue optimization"""
    
    def __init__(self, db: Session):
        self.db = db
        self._calculation_cache = {}
        self._cache_ttl = 60  # seconds
        
    def calculate_order_priority(self, order_id: int, queue_id: int, profile_override: Optional[int] = None) -> OrderPriorityScore:
        """
        Calculate priority score for an order in a specific queue.
        
        Args:
            order_id: ID of the order
            queue_id: ID of the queue
            profile_override: Optional profile ID to override default
            
        Returns:
            OrderPriorityScore object with calculated scores
        """
        # Get queue item
        queue_item = self.db.query(QueueItem).filter(
            QueueItem.order_id == order_id,
            QueueItem.queue_id == queue_id
        ).first()
        
        if not queue_item:
            raise NotFoundError(f"Order {order_id} not found in queue {queue_id}")
        
        # Get queue priority configuration
        config = self.db.query(QueuePriorityConfig).filter(
            QueuePriorityConfig.queue_id == queue_id,
            QueuePriorityConfig.is_active == True
        ).first()
        
        if not config or not config.priority_enabled:
            # Return default score if priority not enabled
            return self._create_default_score(queue_item.id, config.id if config else None)
        
        # Get the priority profile with rules
        profile_id = profile_override or config.profile_id
        profile = self.db.query(PriorityProfile).options(
            joinedload(PriorityProfile.profile_rules).joinedload(
                PriorityProfileRule.rule
            )
        ).filter(
            PriorityProfile.id == profile_id,
            PriorityProfile.is_active == True
        ).first()
        
        if not profile:
            return self._create_default_score(queue_item.id, config.id)
        
        # Calculate priority based on algorithm type
        start_time = time.time()
        
        # Get order details
        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise NotFoundError(f"Order {order_id} not found")
        
        # Calculate component scores
        score_components = {}
        total_score = 0.0
        total_weight = 0.0
        
        for profile_rule in profile.profile_rules:
            if not profile_rule.is_active:
                continue
                
            rule = profile_rule.rule
            if not rule.is_active:
                continue
            
            # Calculate score for this rule
            try:
                component_score = self._calculate_rule_score(
                    rule, profile_rule, order, queue_item, config
                )
                
                # Apply thresholds
                if profile_rule.min_threshold and component_score < profile_rule.min_threshold:
                    component_score = profile_rule.fallback_score or 0.0
                if profile_rule.max_threshold and component_score > profile_rule.max_threshold:
                    component_score = profile_rule.max_threshold
                
                # Weight the score
                weight = profile_rule.weight_override or profile_rule.weight or rule.default_weight
                weighted_score = component_score * weight
                
                score_components[rule.name] = {
                    "value": component_score,
                    "score": weighted_score,
                    "weight": weight
                }
                
                total_score += weighted_score
                total_weight += weight
                
            except Exception as e:
                logger.warning(f"Error calculating score for rule {rule.name}: {e}")
                if profile_rule.is_required:
                    raise ValidationError(f"Required rule {rule.name} failed: {e}")
                # Use fallback score for non-required rules
                fallback_score = profile_rule.fallback_score or 0.0
                score_components[rule.name] = {
                    "value": 0.0,
                    "score": fallback_score,
                    "weight": profile_rule.weight or 1.0,
                    "error": str(e)
                }
                total_score += fallback_score
                total_weight += profile_rule.weight or 1.0
        
        # Normalize total score if configured
        if profile.normalize_scores and total_weight > 0:
            total_score = self._normalize_score(total_score, profile.normalization_method)
        
        # Apply queue-specific boosts
        boost_score = self._apply_queue_boosts(config, order, queue_item)
        final_score = total_score + boost_score
        
        # Determine priority tier
        priority_tier = self._determine_priority_tier(final_score)
        
        # Calculate suggested sequence
        suggested_sequence = self._calculate_suggested_sequence(queue_id, final_score)
        
        calculation_time_ms = int((time.time() - start_time) * 1000)
        
        # Create or update priority score record
        priority_score = self.db.query(OrderPriorityScore).filter(
            OrderPriorityScore.queue_item_id == queue_item.id
        ).first()
        
        if not priority_score:
            priority_score = OrderPriorityScore(
                queue_item_id=queue_item.id,
                config_id=config.id,
                order_id=order_id,
                queue_id=queue_id
            )
            self.db.add(priority_score)
        
        # Update score data
        priority_score.total_score = final_score
        priority_score.base_score = total_score
        priority_score.boost_score = boost_score
        priority_score.score_components = score_components
        priority_score.calculated_at = datetime.utcnow()
        priority_score.algorithm_version = "1.0"
        priority_score.calculation_time_ms = calculation_time_ms
        priority_score.normalized_score = self._normalize_score(final_score, "min_max")
        priority_score.profile_used = profile.name
        priority_score.factors_applied = list(score_components.keys())
        priority_score.priority_tier = priority_tier
        priority_score.suggested_sequence = suggested_sequence
        
        self.db.commit()
        self.db.refresh(priority_score)
        
        return priority_score
    
    def _calculate_rule_score(self, rule: PriorityRule, profile_rule: PriorityProfileRule, 
                            order: Order, queue_item: QueueItem, config: QueuePriorityConfig) -> float:
        """Calculate score for a specific rule"""
        
        # Get rule configuration
        rule_config = profile_rule.override_config or rule.score_config
        rule_type = rule_config.get("type", "linear")
        
        # Get base value based on rule type
        base_value = self._get_base_value(rule, order, queue_item, config)
        
        # Apply scoring function
        if rule_type == "linear":
            return self._linear_score(base_value, rule_config)
        elif rule_type == "exponential":
            return self._exponential_score(base_value, rule_config)
        elif rule_type == "logarithmic":
            return self._logarithmic_score(base_value, rule_config)
        elif rule_type == "step":
            return self._step_score(base_value, rule_config)
        elif rule_type == "custom":
            return self._custom_score(base_value, rule_config, rule.score_function)
        else:
            return base_value
    
    def _get_base_value(self, rule: PriorityRule, order: Order, queue_item: QueueItem, 
                       config: QueuePriorityConfig) -> float:
        """Get base value for rule calculation"""
        
        # Calculate wait time
        if rule.score_type == PriorityScoreType.WAIT_TIME:
            wait_time = (datetime.utcnow() - queue_item.created_at).total_seconds() / 60
            return wait_time
        
        # Calculate order value
        elif rule.score_type == PriorityScoreType.ORDER_VALUE:
            return float(order.total_amount or 0)
        
        # Check VIP status
        elif rule.score_type == PriorityScoreType.VIP_STATUS:
            customer = self.db.query(Customer).filter(Customer.id == order.customer_id).first()
            if customer and customer.vip_status:
                return 1.0
            return 0.0
        
        # Calculate delivery time pressure
        elif rule.score_type == PriorityScoreType.DELIVERY_TIME:
            if order.estimated_delivery_time:
                time_diff = (order.estimated_delivery_time - datetime.utcnow()).total_seconds() / 60
                return max(0, time_diff)
            return 0.0
        
        # Calculate preparation complexity
        elif rule.score_type == PriorityScoreType.PREP_COMPLEXITY:
            # Count items and their complexity
            complexity_score = 0
            for item in order.items:
                complexity_score += item.quantity * (item.complexity_score or 1)
            return complexity_score
        
        # Calculate customer loyalty
        elif rule.score_type == PriorityScoreType.CUSTOMER_LOYALTY:
            customer = self.db.query(Customer).filter(Customer.id == order.customer_id).first()
            if customer:
                loyalty = self.db.query(LoyaltyProgram).filter(
                    LoyaltyProgram.customer_id == customer.id
                ).first()
                if loyalty:
                    return float(loyalty.points or 0)
            return 0.0
        
        # Check if peak hours
        elif rule.score_type == PriorityScoreType.PEAK_HOURS:
            current_hour = datetime.utcnow().hour
            peak_hours = config.peak_hours or [11, 12, 13, 18, 19, 20]  # Default peak hours
            return 1.0 if current_hour in peak_hours else 0.0
        
        # Calculate group size
        elif rule.score_type == PriorityScoreType.GROUP_SIZE:
            return float(order.party_size or 1)
        
        # Check special needs
        elif rule.score_type == PriorityScoreType.SPECIAL_NEEDS:
            special_notes = order.special_instructions or ""
            special_keywords = ["allergy", "gluten", "dairy", "nut", "vegetarian", "vegan"]
            return sum(1 for keyword in special_keywords if keyword.lower() in special_notes.lower())
        
        # Custom rule
        elif rule.score_type == PriorityScoreType.CUSTOM:
            # Use custom parameters from rule
            params = rule.parameters or {}
            return params.get("base_value", 0.0)
        
        else:
            return 0.0
    
    def _linear_score(self, value: float, config: Dict[str, Any]) -> float:
        """Calculate linear score"""
        base_score = config.get("base_score", 0.0)
        multiplier = config.get("multiplier", 1.0)
        return base_score + (value * multiplier)
    
    def _exponential_score(self, value: float, config: Dict[str, Any]) -> float:
        """Calculate exponential score"""
        base_score = config.get("base_score", 0.0)
        multiplier = config.get("multiplier", 1.0)
        exponent = config.get("exponent", 2.0)
        return base_score + (multiplier * (value ** exponent))
    
    def _logarithmic_score(self, value: float, config: Dict[str, Any]) -> float:
        """Calculate logarithmic score"""
        base_score = config.get("base_score", 0.0)
        multiplier = config.get("multiplier", 1.0)
        if value <= 0:
            return base_score
        return base_score + (multiplier * math.log(value + 1))
    
    def _step_score(self, value: float, config: Dict[str, Any]) -> float:
        """Calculate step function score"""
        steps = config.get("steps", [])
        for threshold, score in steps:
            if value <= threshold:
                return score
        return config.get("default_score", 0.0)
    
    def _custom_score(self, value: float, config: Dict[str, Any], function_code: Optional[str]) -> float:
        """Calculate custom score using provided function"""
        if not function_code:
            return value
        
        # In a real implementation, you'd want to safely evaluate the function
        # For now, return the value as-is
        return value
    
    def _apply_queue_boosts(self, config: QueuePriorityConfig, order: Order, queue_item: QueueItem) -> float:
        """Apply queue-specific priority boosts"""
        boost_score = 0.0
        
        # VIP boost
        customer = self.db.query(Customer).filter(Customer.id == order.customer_id).first()
        if customer and customer.vip_status:
            boost_score += config.priority_boost_vip
        
        # Delayed order boost
        if order.estimated_delivery_time:
            time_diff = (order.estimated_delivery_time - datetime.utcnow()).total_seconds() / 60
            if time_diff < 0:  # Delayed
                boost_score += config.priority_boost_delayed
        
        # Large party boost
        if order.party_size and order.party_size > 4:
            boost_score += config.priority_boost_large_party
        
        # Peak hours multiplier
        current_hour = datetime.utcnow().hour
        peak_hours = config.peak_hours or [11, 12, 13, 18, 19, 20]
        if current_hour in peak_hours:
            boost_score *= config.peak_multiplier
        
        return boost_score
    
    def _normalize_score(self, score: float, method: str) -> float:
        """Normalize score to 0-100 range"""
        if method == "min_max":
            # This is a simplified normalization - in practice you'd use historical data
            return min(100.0, max(0.0, score))
        elif method == "z_score":
            # Would need historical data for proper z-score calculation
            return min(100.0, max(0.0, score))
        elif method == "percentile":
            # Would need historical data for percentile calculation
            return min(100.0, max(0.0, score))
        else:
            return score
    
    def _determine_priority_tier(self, score: float) -> str:
        """Determine priority tier based on score"""
        if score >= 80:
            return "high"
        elif score >= 50:
            return "medium"
        else:
            return "low"
    
    def _calculate_suggested_sequence(self, queue_id: int, score: float) -> int:
        """Calculate suggested sequence position in queue"""
        # Get current queue items ordered by priority score
        queue_items = self.db.query(QueueItem).join(OrderPriorityScore).filter(
            QueueItem.queue_id == queue_id,
            QueueItem.status.in_([QueueItemStatus.QUEUED, QueueItemStatus.IN_PREPARATION])
        ).order_by(OrderPriorityScore.total_score.desc()).all()
        
        # Find position where this score would fit
        for i, item in enumerate(queue_items):
            item_score = self.db.query(OrderPriorityScore).filter(
                OrderPriorityScore.queue_item_id == item.id
            ).first()
            if item_score and score > item_score.total_score:
                return i + 1
        
        return len(queue_items) + 1
    
    def _create_default_score(self, queue_item_id: int, config_id: Optional[int]) -> OrderPriorityScore:
        """Create a default priority score"""
        priority_score = OrderPriorityScore(
            queue_item_id=queue_item_id,
            config_id=config_id,
            total_score=50.0,  # Default middle score
            base_score=50.0,
            boost_score=0.0,
            score_components={},
            calculated_at=datetime.utcnow(),
            priority_tier="medium",
            suggested_sequence=1
        )
        
        if config_id:
            self.db.add(priority_score)
            self.db.commit()
            self.db.refresh(priority_score)
        
        return priority_score
    
    def adjust_priority_manually(self, queue_item_id: int, new_score: float, 
                               adjustment_type: str, adjustment_reason: str,
                               adjusted_by_id: int, duration_seconds: Optional[int] = None) -> PriorityAdjustmentLog:
        """Manually adjust priority for a queue item"""
        
        # Get current priority score
        current_score = self.db.query(OrderPriorityScore).filter(
            OrderPriorityScore.queue_item_id == queue_item_id
        ).first()
        
        if not current_score:
            raise NotFoundError(f"No priority score found for queue item {queue_item_id}")
        
        old_score = current_score.total_score
        old_position = self._get_queue_position(queue_item_id)
        
        # Update priority score
        current_score.total_score = new_score
        current_score.is_boosted = True
        current_score.boost_reason = adjustment_reason
        
        if duration_seconds:
            current_score.boost_expires_at = datetime.utcnow() + timedelta(seconds=duration_seconds)
        
        # Create adjustment log
        adjustment_log = PriorityAdjustmentLog(
            queue_item_id=queue_item_id,
            order_id=current_score.order_id,
            old_score=old_score,
            new_score=new_score,
            old_priority=old_score,
            new_priority=new_score,
            adjustment_type=adjustment_type,
            adjustment_reason=adjustment_reason,
            adjusted_by_id=adjusted_by_id,
            old_position=old_position,
            new_position=self._get_queue_position(queue_item_id)
        )
        
        self.db.add(adjustment_log)
        self.db.commit()
        self.db.refresh(adjustment_log)
        
        return adjustment_log
    
    def _get_queue_position(self, queue_item_id: int) -> int:
        """Get current position of queue item"""
        queue_item = self.db.query(QueueItem).filter(QueueItem.id == queue_item_id).first()
        if not queue_item:
            return 0
        
        # Count items ahead in queue
        position = self.db.query(QueueItem).join(OrderPriorityScore).filter(
            QueueItem.queue_id == queue_item.queue_id,
            QueueItem.status.in_([QueueItemStatus.QUEUED, QueueItemStatus.IN_PREPARATION]),
            OrderPriorityScore.total_score > self.db.query(OrderPriorityScore.total_score).filter(
                OrderPriorityScore.queue_item_id == queue_item_id
            ).scalar()
        ).count()
        
        return position + 1
    
    def rebalance_queue(self, queue_id: int, force: bool = False) -> QueueRebalanceResponse:
        """Rebalance a queue to ensure fairness"""
        
        config = self.db.query(QueuePriorityConfig).filter(
            QueuePriorityConfig.queue_id == queue_id,
            QueuePriorityConfig.is_active == True
        ).first()
        
        if not config or not config.rebalance_enabled:
            raise ValidationError("Queue rebalancing is not enabled")
        
        # Check if rebalancing is needed
        if not force:
            fairness_score = self._calculate_fairness_score(queue_id)
            if fairness_score > config.rebalance_threshold:
                return QueueRebalanceResponse(
                    queue_id=queue_id,
                    items_processed=0,
                    items_moved=0,
                    fairness_improvement=0.0,
                    execution_time_ms=0
                )
        
        start_time = time.time()
        
        # Get queue items with priority scores
        queue_items = self.db.query(QueueItem).join(OrderPriorityScore).filter(
            QueueItem.queue_id == queue_id,
            QueueItem.status.in_([QueueItemStatus.QUEUED, QueueItemStatus.IN_PREPARATION])
        ).order_by(OrderPriorityScore.total_score.desc()).all()
        
        items_moved = 0
        max_moves = config.max_position_change
        
        # Simple rebalancing: move items that are too far from their priority position
        for i, item in enumerate(queue_items):
            current_position = i + 1
            priority_score = self.db.query(OrderPriorityScore).filter(
                OrderPriorityScore.queue_item_id == item.id
            ).first()
            
            if priority_score and priority_score.suggested_sequence:
                suggested_position = priority_score.suggested_sequence
                position_diff = abs(current_position - suggested_position)
                
                if position_diff > max_moves:
                    # Would need to implement actual queue reordering here
                    items_moved += 1
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        fairness_improvement = self._calculate_fairness_score(queue_id)
        
        return QueueRebalanceResponse(
            queue_id=queue_id,
            items_processed=len(queue_items),
            items_moved=items_moved,
            fairness_improvement=fairness_improvement,
            execution_time_ms=execution_time_ms
        )
    
    def _calculate_fairness_score(self, queue_id: int) -> float:
        """Calculate fairness score for queue (lower is more fair)"""
        # This is a simplified Gini coefficient calculation
        scores = self.db.query(OrderPriorityScore.total_score).join(QueueItem).filter(
            QueueItem.queue_id == queue_id,
            QueueItem.status.in_([QueueItemStatus.QUEUED, QueueItemStatus.IN_PREPARATION])
        ).all()
        
        if not scores:
            return 0.0
        
        score_values = [s[0] for s in scores]
        n = len(score_values)
        
        if n == 0:
            return 0.0
        
        # Calculate Gini coefficient
        sorted_scores = sorted(score_values)
        cumsum = 0
        for i, score in enumerate(sorted_scores):
            cumsum += (i + 1) * score
        
        return (2 * cumsum) / (n * sum(sorted_scores)) - (n + 1) / n
    
    def get_queue_priority_sequence(self, queue_id: int) -> List[Dict[str, Any]]:
        """Get current priority-based sequence for a queue"""
        queue_items = self.db.query(QueueItem).join(OrderPriorityScore).filter(
            QueueItem.queue_id == queue_id,
            QueueItem.status.in_([QueueItemStatus.QUEUED, QueueItemStatus.IN_PREPARATION])
        ).order_by(OrderPriorityScore.total_score.desc()).all()
        
        sequence = []
        for i, item in enumerate(queue_items):
            priority_score = self.db.query(OrderPriorityScore).filter(
                OrderPriorityScore.queue_item_id == item.id
            ).first()
            
            sequence.append({
                "position": i + 1,
                "order_id": item.order_id,
                "queue_item_id": item.id,
                "priority_score": priority_score.total_score if priority_score else 0.0,
                "priority_tier": priority_score.priority_tier if priority_score else "medium",
                "wait_time_minutes": (datetime.utcnow() - item.created_at).total_seconds() / 60
            })
        
        return sequence
    
    def _resequence_queue_after_adjustment(self, queue_id: int):
        """Resequence queue after priority adjustments"""
        # This would implement the actual queue reordering logic
        # For now, just log that resequencing is needed
        logger.info(f"Queue {queue_id} needs resequencing after priority adjustments")
    
    def _apply_boost(self, priority_score: OrderPriorityScore, config: QueuePriorityConfig, 
                    boost_reason: str) -> OrderPriorityScore:
        """Apply boost to priority score"""
        priority_score.is_boosted = True
        priority_score.boost_reason = boost_reason
        priority_score.boost_expires_at = datetime.utcnow() + timedelta(seconds=config.boost_duration_seconds)
        
        return priority_score
