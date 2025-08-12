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
        
    def calculate_order_priority(self, order_id: int, queue_id: int) -> OrderPriorityScore:
        """
        Calculate priority score for an order in a specific queue.
        
        Args:
            order_id: ID of the order
            queue_id: ID of the queue
            
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
        profile = self.db.query(PriorityProfile).options(
            joinedload(PriorityProfile.profile_rules).joinedload(
                PriorityProfileRule.rule
            )
        ).filter(
            PriorityProfile.id == config.profile_id,
            PriorityProfile.is_active == True
        ).first()
        
        if not profile:
            return self._create_default_score(queue_item.id, config.id)
        
        # Calculate priority based on algorithm type
        start_time = time.time()
        
        if profile.algorithm_type == PriorityAlgorithm.FIFO:
            priority_score = self._calculate_fifo_priority(queue_item, config)
        elif profile.algorithm_type == PriorityAlgorithm.WEIGHTED:
            priority_score = self._calculate_weighted_priority(
                queue_item, config, profile
            )
        elif profile.algorithm_type == PriorityAlgorithm.DYNAMIC:
            priority_score = self._calculate_dynamic_priority(
                queue_item, config, profile
            )
        elif profile.algorithm_type == PriorityAlgorithm.FAIR_SHARE:
            priority_score = self._calculate_fair_share_priority(
                queue_item, config, profile
            )
        elif profile.algorithm_type == PriorityAlgorithm.REVENUE_OPTIMIZED:
            priority_score = self._calculate_revenue_optimized_priority(
                queue_item, config, profile
            )
        else:
            priority_score = self._calculate_weighted_priority(
                queue_item, config, profile
            )
        
        # Apply boost if configured
        if config.boost_new_items and self._is_new_item(queue_item, config):
            priority_score = self._apply_boost(priority_score, config, "new_item")
        
        # Save calculation time
        priority_score.calculation_time_ms = int((time.time() - start_time) * 1000)
        priority_score.algorithm_version = "1.0.0"
        
        # Save or update score
        self.db.merge(priority_score)
        self.db.commit()
        
        return priority_score
    
    def rebalance_queue(self, queue_id: int, force: bool = False) -> QueueRebalanceResponse:
        """
        Rebalance queue to ensure fairness while respecting priority.
        
        Args:
            queue_id: ID of the queue to rebalance
            force: Force rebalance even if threshold not met
            
        Returns:
            QueueRebalanceResponse with rebalancing results
        """
        start_time = time.time()
        
        # Get queue configuration
        config = self.db.query(QueuePriorityConfig).filter(
            QueuePriorityConfig.queue_id == queue_id,
            QueuePriorityConfig.is_active == True
        ).first()
        
        if not config or not config.auto_rebalance:
            raise ValidationError("Queue rebalancing not enabled")
        
        # Check if rebalancing is needed
        if not force and not self._should_rebalance(queue_id, config):
            return QueueRebalanceResponse(
                queue_id=queue_id,
                items_rebalanced=0,
                average_position_change=0.0,
                max_position_change=0,
                fairness_before=self._calculate_fairness_index(queue_id),
                fairness_after=self._calculate_fairness_index(queue_id),
                execution_time_ms=int((time.time() - start_time) * 1000),
                dry_run=False
            )
        
        # Get current queue state
        fairness_before = self._calculate_fairness_index(queue_id)
        
        # Get all active items in queue with their priority scores
        queue_items = self.db.query(QueueItem, OrderPriorityScore).join(
            OrderPriorityScore,
            OrderPriorityScore.queue_item_id == QueueItem.id
        ).filter(
            QueueItem.queue_id == queue_id,
            QueueItem.status.in_([
                QueueItemStatus.QUEUED,
                QueueItemStatus.IN_PREPARATION
            ])
        ).order_by(QueueItem.sequence_number).all()
        
        if len(queue_items) < 2:
            # Nothing to rebalance
            return QueueRebalanceResponse(
                queue_id=queue_id,
                items_rebalanced=0,
                average_position_change=0.0,
                max_position_change=0,
                fairness_before=fairness_before,
                fairness_after=fairness_before,
                execution_time_ms=int((time.time() - start_time) * 1000),
                dry_run=False
            )
        
        # Calculate new sequence based on priority scores
        rebalanced_items = self._calculate_rebalanced_sequence(
            queue_items, config
        )
        
        # Apply new sequence
        position_changes = []
        max_change = 0
        
        for new_seq, (queue_item, score), old_seq in rebalanced_items:
            position_change = abs(new_seq - old_seq)
            position_changes.append(position_change)
            max_change = max(max_change, position_change)
            
            # Update sequence number
            queue_item.sequence_number = new_seq
        
        # Update last rebalance time
        config.last_rebalance_time = datetime.utcnow()
        
        # Commit changes
        self.db.commit()
        
        # Calculate metrics
        fairness_after = self._calculate_fairness_index(queue_id)
        avg_position_change = sum(position_changes) / len(position_changes) if position_changes else 0
        
        # Log rebalancing metrics
        self._log_rebalancing_metrics(
            queue_id, len(queue_items), avg_position_change, 
            fairness_before, fairness_after
        )
        
        return QueueRebalanceResponse(
            queue_id=queue_id,
            items_rebalanced=len(position_changes),
            average_position_change=avg_position_change,
            max_position_change=max_change,
            fairness_before=fairness_before,
            fairness_after=fairness_after,
            execution_time_ms=int((time.time() - start_time) * 1000),
            dry_run=False
        )
    
    def _calculate_weighted_priority(
        self, 
        queue_item: QueueItem, 
        config: QueuePriorityConfig,
        profile: PriorityProfile
    ) -> OrderPriorityScore:
        """Calculate priority using weighted scoring across multiple factors"""
        score_components = {}
        total_weight = 0
        weighted_sum = 0
        
        # Get order details
        order = self.db.query(Order).filter(Order.id == queue_item.order_id).first()
        
        # Calculate each component score
        for profile_rule in profile.profile_rules:
            if not profile_rule.is_active or not profile_rule.rule.is_active:
                continue
            
            rule = profile_rule.rule
            weight = profile_rule.weight
            
            # Calculate component score based on type
            if rule.score_type == PriorityScoreType.WAIT_TIME:
                component_score = self._calculate_wait_time_priority(queue_item, rule)
            elif rule.score_type == PriorityScoreType.ORDER_VALUE:
                component_score = self._calculate_order_value_priority(order, rule)
            elif rule.score_type == PriorityScoreType.VIP_STATUS:
                component_score = self._calculate_vip_priority(order, rule)
            elif rule.score_type == PriorityScoreType.DELIVERY_TIME:
                component_score = self._calculate_delivery_time_priority(order, rule)
            elif rule.score_type == PriorityScoreType.PREP_COMPLEXITY:
                component_score = self._calculate_complexity_priority(order, rule)
            else:
                component_score = self._calculate_custom_priority(
                    queue_item, order, rule
                )
            
            # Apply normalization if configured
            if rule.normalize_output:
                component_score = self._normalize_score(
                    component_score, 
                    rule.min_score, 
                    rule.max_score,
                    rule.normalization_method
                )
            
            # Store component details
            score_components[rule.score_type.value] = {
                "value": component_score,
                "score": component_score,
                "weight": weight,
                "weighted_score": component_score * weight
            }
            
            weighted_sum += component_score * weight
            total_weight += weight
        
        # Calculate final score
        if profile.total_weight_normalization and total_weight > 0:
            total_score = weighted_sum / total_weight
        else:
            total_score = weighted_sum
        
        # Apply bounds
        total_score = max(profile.min_total_score, 
                         min(profile.max_total_score, total_score))
        
        # Create or update priority score
        priority_score = self.db.query(OrderPriorityScore).filter(
            OrderPriorityScore.queue_item_id == queue_item.id
        ).first()
        
        if not priority_score:
            priority_score = OrderPriorityScore(
                queue_item_id=queue_item.id,
                config_id=config.id
            )
        
        priority_score.total_score = total_score
        priority_score.base_score = total_score
        priority_score.boost_score = 0
        priority_score.score_components = score_components
        priority_score.calculated_at = datetime.utcnow()
        priority_score.is_boosted = False
        
        return priority_score
    
    def _calculate_wait_time_priority(
        self, 
        queue_item: QueueItem, 
        rule: PriorityRule
    ) -> float:
        """Calculate priority score based on wait time"""
        wait_minutes = (datetime.utcnow() - queue_item.queued_at).total_seconds() / 60
        config = rule.score_config
        
        if config.get('type') == 'linear':
            # Linear increase with wait time
            base = config.get('base_score', 0)
            multiplier = config.get('multiplier', 1)
            score = base + (wait_minutes * multiplier)
        elif config.get('type') == 'exponential':
            # Exponential increase for long waits
            base = config.get('base_score', 0)
            rate = config.get('rate', 0.1)
            score = base + math.exp(wait_minutes * rate)
        elif config.get('type') == 'step':
            # Step function based on thresholds
            thresholds = config.get('thresholds', [])
            score = 0
            for threshold in thresholds:
                if wait_minutes >= threshold['minutes']:
                    score = threshold['score']
        else:
            # Default linear
            score = wait_minutes
        
        return min(rule.max_score, max(rule.min_score, score))
    
    def _calculate_order_value_priority(
        self, 
        order: Order, 
        rule: PriorityRule
    ) -> float:
        """Calculate priority score based on order value"""
        if not order:
            return rule.min_score
            
        order_value = float(order.total_amount or 0)
        config = rule.score_config
        
        if config.get('type') == 'linear':
            # Linear scaling with order value
            min_value = config.get('min_value', 0)
            max_value = config.get('max_value', 1000)
            
            if order_value <= min_value:
                score = rule.min_score
            elif order_value >= max_value:
                score = rule.max_score
            else:
                # Linear interpolation
                ratio = (order_value - min_value) / (max_value - min_value)
                score = rule.min_score + (ratio * (rule.max_score - rule.min_score))
        elif config.get('type') == 'tiered':
            # Tiered scoring based on value ranges
            tiers = config.get('tiers', [])
            score = rule.min_score
            for tier in tiers:
                if order_value >= tier['min_value']:
                    score = tier['score']
        else:
            # Default proportional
            base_value = config.get('base_value', 100)
            score = (order_value / base_value) * rule.max_score
        
        return min(rule.max_score, max(rule.min_score, score))
    
    def _calculate_vip_priority(
        self, 
        order: Order, 
        rule: PriorityRule
    ) -> float:
        """Calculate priority score based on VIP/loyalty status"""
        if not order or not order.customer_id:
            return rule.min_score
        
        # Get customer loyalty information
        customer = self.db.query(Customer).filter(
            Customer.id == order.customer_id
        ).first()
        
        if not customer:
            return rule.min_score
        
        config = rule.score_config
        score = rule.min_score
        
        # Check VIP status
        if hasattr(customer, 'is_vip') and customer.is_vip:
            score = config.get('vip_score', rule.max_score)
        
        # Check loyalty tier
        if hasattr(customer, 'loyalty_tier'):
            tier_scores = config.get('tier_scores', {})
            tier_score = tier_scores.get(customer.loyalty_tier, rule.min_score)
            score = max(score, tier_score)
        
        # Check order frequency
        if hasattr(customer, 'order_count'):
            frequency_threshold = config.get('frequency_threshold', 10)
            if customer.order_count >= frequency_threshold:
                frequency_score = config.get('frequency_score', rule.max_score * 0.7)
                score = max(score, frequency_score)
        
        return min(rule.max_score, max(rule.min_score, score))
    
    def _calculate_delivery_time_priority(
        self, 
        order: Order, 
        rule: PriorityRule
    ) -> float:
        """Calculate priority based on delivery window urgency"""
        if not order or not hasattr(order, 'promised_delivery_time'):
            return rule.min_score
        
        if not order.promised_delivery_time:
            return rule.min_score
        
        # Calculate time until delivery
        time_remaining = (order.promised_delivery_time - datetime.utcnow()).total_seconds() / 60
        config = rule.score_config
        
        if time_remaining <= 0:
            # Already late
            return rule.max_score
        
        if config.get('type') == 'inverse_linear':
            # Higher priority as deadline approaches
            max_minutes = config.get('max_minutes', 120)
            if time_remaining >= max_minutes:
                score = rule.min_score
            else:
                ratio = 1 - (time_remaining / max_minutes)
                score = rule.min_score + (ratio * (rule.max_score - rule.min_score))
        elif config.get('type') == 'threshold':
            # Step function based on urgency thresholds
            thresholds = config.get('thresholds', [])
            score = rule.min_score
            for threshold in thresholds:
                if time_remaining <= threshold['minutes']:
                    score = threshold['score']
                    break
        else:
            # Default inverse proportional
            score = rule.max_score * (60 / max(time_remaining, 1))
        
        return min(rule.max_score, max(rule.min_score, score))
    
    def _calculate_complexity_priority(
        self, 
        order: Order, 
        rule: PriorityRule
    ) -> float:
        """Calculate priority based on order preparation complexity"""
        if not order:
            return rule.min_score
        
        config = rule.score_config
        
        # Calculate complexity factors
        item_count = len(order.items) if hasattr(order, 'items') else 1
        
        # Count modifications/special requests
        modification_count = 0
        if hasattr(order, 'items'):
            for item in order.items:
                if hasattr(item, 'modifiers') and item.modifiers:
                    modification_count += len(item.modifiers)
                if hasattr(item, 'special_instructions') and item.special_instructions:
                    modification_count += 1
        
        # Calculate complexity score
        if config.get('type') == 'weighted':
            item_weight = config.get('item_weight', 1.0)
            mod_weight = config.get('modification_weight', 2.0)
            
            complexity = (item_count * item_weight) + (modification_count * mod_weight)
            max_complexity = config.get('max_complexity', 20)
            
            if complexity >= max_complexity:
                score = rule.max_score
            else:
                ratio = complexity / max_complexity
                score = rule.min_score + (ratio * (rule.max_score - rule.min_score))
        else:
            # Simple additive
            score = rule.min_score + (item_count * 5) + (modification_count * 10)
        
        return min(rule.max_score, max(rule.min_score, score))
    
    def _calculate_custom_priority(
        self, 
        queue_item: QueueItem,
        order: Order,
        rule: PriorityRule
    ) -> float:
        """Calculate priority using custom rule configuration"""
        config = rule.score_config
        score = config.get('default_score', rule.min_score)
        
        # Evaluate conditions if present
        conditions = config.get('conditions', [])
        for condition in conditions:
            if self._evaluate_condition(queue_item, order, condition):
                adjustment = condition.get('adjustment', 0)
                operation = condition.get('operation', 'add')
                
                if operation == 'add':
                    score += adjustment
                elif operation == 'multiply':
                    score *= adjustment
                elif operation == 'set':
                    score = adjustment
        
        return min(rule.max_score, max(rule.min_score, score))
    
    def _evaluate_condition(
        self,
        queue_item: QueueItem,
        order: Order,
        condition: Dict[str, Any]
    ) -> bool:
        """Evaluate a condition for custom scoring"""
        field = condition.get('field')
        operator = condition.get('operator')
        value = condition.get('value')
        
        # Get field value from queue_item or order
        if hasattr(queue_item, field):
            field_value = getattr(queue_item, field)
        elif order and hasattr(order, field):
            field_value = getattr(order, field)
        else:
            return False
        
        # Evaluate based on operator
        if operator == 'eq':
            return field_value == value
        elif operator == 'ne':
            return field_value != value
        elif operator == 'gt':
            return field_value > value
        elif operator == 'gte':
            return field_value >= value
        elif operator == 'lt':
            return field_value < value
        elif operator == 'lte':
            return field_value <= value
        elif operator == 'in':
            return field_value in value
        elif operator == 'not_in':
            return field_value not in value
        
        return False
    
    def _normalize_score(
        self,
        score: float,
        min_score: float,
        max_score: float,
        method: str
    ) -> float:
        """Normalize score using specified method"""
        if method == 'min_max':
            # Min-max normalization to [0, 1] then scale
            if max_score == min_score:
                return min_score
            normalized = (score - min_score) / (max_score - min_score)
            return normalized * 100  # Scale to 0-100
        elif method == 'z_score':
            # Z-score normalization (would need mean/std from historical data)
            # Simplified version
            return score
        elif method == 'percentile':
            # Percentile ranking (would need distribution data)
            # Simplified version
            return score
        else:
            return score
    
    def _calculate_fifo_priority(
        self,
        queue_item: QueueItem,
        config: QueuePriorityConfig
    ) -> OrderPriorityScore:
        """Calculate FIFO priority based on queue time"""
        wait_minutes = (datetime.utcnow() - queue_item.queued_at).total_seconds() / 60
        
        # Simple FIFO: priority increases linearly with wait time
        total_score = wait_minutes
        
        priority_score = self.db.query(OrderPriorityScore).filter(
            OrderPriorityScore.queue_item_id == queue_item.id
        ).first()
        
        if not priority_score:
            priority_score = OrderPriorityScore(
                queue_item_id=queue_item.id,
                config_id=config.id
            )
        
        priority_score.total_score = total_score
        priority_score.base_score = total_score
        priority_score.boost_score = 0
        priority_score.score_components = {
            "wait_time": {
                "value": wait_minutes,
                "score": total_score,
                "weight": 1.0
            }
        }
        priority_score.calculated_at = datetime.utcnow()
        
        return priority_score
    
    def _calculate_dynamic_priority(
        self,
        queue_item: QueueItem,
        config: QueuePriorityConfig,
        profile: PriorityProfile
    ) -> OrderPriorityScore:
        """Calculate dynamic priority that adapts to current conditions"""
        # Start with weighted calculation
        priority_score = self._calculate_weighted_priority(queue_item, config, profile)
        
        # Apply dynamic adjustments based on current queue state
        queue_size = self.db.query(func.count(QueueItem.id)).filter(
            QueueItem.queue_id == queue_item.queue_id,
            QueueItem.status == QueueItemStatus.QUEUED
        ).scalar()
        
        # Adjust based on queue pressure
        if queue_size > 20:
            # High pressure - prioritize quick orders
            order = self.db.query(Order).filter(Order.id == queue_item.order_id).first()
            if order and hasattr(order, 'estimated_prep_time'):
                if order.estimated_prep_time < 10:  # Quick orders
                    priority_score.total_score *= 1.2
        
        # Adjust based on time of day
        current_hour = datetime.utcnow().hour
        if config.peak_hours_config:
            peak_hours = config.peak_hours_config.get('hours', [])
            if current_hour in peak_hours:
                peak_multiplier = config.peak_hours_config.get('multiplier', 1.1)
                priority_score.total_score *= peak_multiplier
        
        return priority_score
    
    def _calculate_fair_share_priority(
        self,
        queue_item: QueueItem,
        config: QueuePriorityConfig,
        profile: PriorityProfile
    ) -> OrderPriorityScore:
        """Calculate priority ensuring fair distribution across customers"""
        # Start with weighted calculation
        priority_score = self._calculate_weighted_priority(queue_item, config, profile)
        
        # Get customer's recent order history in queue
        order = self.db.query(Order).filter(Order.id == queue_item.order_id).first()
        if order and order.customer_id:
            # Count customer's active orders in queue
            customer_queue_count = self.db.query(func.count(QueueItem.id)).join(
                Order
            ).filter(
                QueueItem.queue_id == queue_item.queue_id,
                Order.customer_id == order.customer_id,
                QueueItem.status.in_([
                    QueueItemStatus.QUEUED,
                    QueueItemStatus.IN_PREPARATION
                ])
            ).scalar()
            
            # Reduce priority if customer has multiple orders
            if customer_queue_count > 1:
                fairness_penalty = 1 - (0.1 * (customer_queue_count - 1))
                priority_score.total_score *= max(0.5, fairness_penalty)
        
        return priority_score
    
    def _calculate_revenue_optimized_priority(
        self,
        queue_item: QueueItem,
        config: QueuePriorityConfig,
        profile: PriorityProfile
    ) -> OrderPriorityScore:
        """Calculate priority to maximize revenue potential"""
        # Start with weighted calculation
        priority_score = self._calculate_weighted_priority(queue_item, config, profile)
        
        order = self.db.query(Order).filter(Order.id == queue_item.order_id).first()
        if order:
            # Boost high-value orders
            if float(order.total_amount or 0) > 100:
                priority_score.total_score *= 1.3
            
            # Boost orders from frequent customers
            if order.customer_id:
                customer = self.db.query(Customer).filter(
                    Customer.id == order.customer_id
                ).first()
                if customer and hasattr(customer, 'lifetime_value'):
                    if customer.lifetime_value > 1000:
                        priority_score.total_score *= 1.2
        
        return priority_score
    
    def _create_default_score(
        self,
        queue_item_id: int,
        config_id: Optional[int]
    ) -> OrderPriorityScore:
        """Create a default priority score"""
        return OrderPriorityScore(
            queue_item_id=queue_item_id,
            config_id=config_id,
            total_score=0.0,
            base_score=0.0,
            boost_score=0.0,
            score_components={},
            calculated_at=datetime.utcnow(),
            is_boosted=False
        )
    
    def _is_new_item(
        self,
        queue_item: QueueItem,
        config: QueuePriorityConfig
    ) -> bool:
        """Check if item is considered new for boosting"""
        age_seconds = (datetime.utcnow() - queue_item.queued_at).total_seconds()
        return age_seconds <= config.boost_duration_seconds
    
    def _apply_boost(
        self,
        priority_score: OrderPriorityScore,
        config: QueuePriorityConfig,
        reason: str
    ) -> OrderPriorityScore:
        """Apply temporary boost to priority score"""
        boost_amount = config.queue_overrides.get('boost_amount', 20) if config.queue_overrides else 20
        
        priority_score.boost_score = boost_amount
        priority_score.total_score += boost_amount
        priority_score.is_boosted = True
        priority_score.boost_expires_at = datetime.utcnow() + timedelta(
            seconds=config.boost_duration_seconds
        )
        priority_score.boost_reason = reason
        
        return priority_score
    
    def _should_rebalance(
        self,
        queue_id: int,
        config: QueuePriorityConfig
    ) -> bool:
        """Check if queue needs rebalancing"""
        # Check time since last rebalance
        if config.last_rebalance_time:
            time_since_rebalance = (datetime.utcnow() - config.last_rebalance_time).total_seconds() / 60
            if time_since_rebalance < config.rebalance_interval_minutes:
                return False
        
        # Check fairness threshold
        fairness_index = self._calculate_fairness_index(queue_id)
        return fairness_index < config.rebalance_threshold
    
    def _calculate_fairness_index(self, queue_id: int) -> float:
        """
        Calculate Gini coefficient for queue fairness (0=perfect equality, 1=perfect inequality).
        
        This is a proper implementation of the Gini coefficient for wait time distribution.
        """
        # Get wait times for all active items in queue
        queue_items = self.db.query(QueueItem).filter(
            QueueItem.queue_id == queue_id,
            QueueItem.status.in_([
                QueueItemStatus.QUEUED,
                QueueItemStatus.IN_PREPARATION
            ])
        ).all()
        
        if len(queue_items) < 2:
            return 1.0  # Perfect fairness with 0 or 1 item
        
        # Calculate wait times in minutes
        wait_times = []
        now = datetime.utcnow()
        for item in queue_items:
            wait_time = (now - item.queued_at).total_seconds() / 60
            wait_times.append(wait_time)
        
        # Sort wait times
        wait_times.sort()
        n = len(wait_times)
        
        # Calculate Gini coefficient using the standard formula
        # G = (2 * sum(i * x_i)) / (n * sum(x_i)) - (n + 1) / n
        
        sum_weighted = sum((i + 1) * wait_time for i, wait_time in enumerate(wait_times))
        sum_total = sum(wait_times)
        
        if sum_total == 0:
            return 1.0  # All items have 0 wait time = perfect fairness
        
        gini = (2 * sum_weighted) / (n * sum_total) - (n + 1) / n
        
        # Gini coefficient is between 0 and 1, but we want fairness index
        # where 1 = perfect fairness, 0 = perfect inequality
        fairness_index = 1 - gini
        
        return max(0.0, min(1.0, fairness_index))
    
    def _calculate_rebalanced_sequence(
        self,
        queue_items: List[Tuple[QueueItem, OrderPriorityScore]],
        config: QueuePriorityConfig
    ) -> List[Tuple[int, Tuple[QueueItem, OrderPriorityScore], int]]:
        """
        Calculate new sequence numbers based on priority scores while respecting constraints.
        
        Returns list of (new_sequence, (queue_item, score), old_sequence) tuples.
        """
        # Sort by priority score (descending) and then by current sequence (ascending)
        sorted_items = sorted(
            enumerate(queue_items, 1),
            key=lambda x: (-x[1][1].total_score, x[1][0].sequence_number)
        )
        
        rebalanced = []
        
        for new_seq, (old_seq, (queue_item, score)) in enumerate(sorted_items, 1):
            # Apply max position change constraint
            position_change = abs(new_seq - old_seq)
            
            if position_change > config.max_position_change:
                # Limit the position change
                if new_seq < old_seq:
                    # Moving forward - limit to max allowed
                    adjusted_seq = max(new_seq, old_seq - config.max_position_change)
                else:
                    # Moving backward - limit to max allowed
                    adjusted_seq = min(new_seq, old_seq + config.max_position_change)
            else:
                adjusted_seq = new_seq
            
            rebalanced.append((adjusted_seq, (queue_item, score), old_seq))
        
        # Resolve conflicts from position constraints
        rebalanced = self._resolve_sequence_conflicts(rebalanced)
        
        return rebalanced
    
    def _resolve_sequence_conflicts(
        self,
        rebalanced: List[Tuple[int, Tuple[QueueItem, OrderPriorityScore], int]]
    ) -> List[Tuple[int, Tuple[QueueItem, OrderPriorityScore], int]]:
        """Resolve any sequence number conflicts from position constraints"""
        # Sort by desired sequence
        rebalanced.sort(key=lambda x: x[0])
        
        # Ensure unique sequence numbers
        used_sequences = set()
        resolved = []
        
        for desired_seq, item_data, old_seq in rebalanced:
            # Find next available sequence
            final_seq = desired_seq
            while final_seq in used_sequences:
                final_seq += 1
            
            used_sequences.add(final_seq)
            resolved.append((final_seq, item_data, old_seq))
        
        return resolved
    
    def _log_rebalancing_metrics(
        self,
        queue_id: int,
        items_count: int,
        avg_position_change: float,
        fairness_before: float,
        fairness_after: float
    ):
        """Log metrics for queue rebalancing"""
        current_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        
        # Get or create metrics record
        metrics = self.db.query(PriorityMetrics).filter(
            PriorityMetrics.queue_id == queue_id,
            PriorityMetrics.metric_date == current_hour,
            PriorityMetrics.hour_of_day == current_hour.hour
        ).first()
        
        if not metrics:
            metrics = PriorityMetrics(
                queue_id=queue_id,
                metric_date=current_hour,
                hour_of_day=current_hour.hour,
                rebalance_count=0,
                avg_rebalance_impact=0
            )
            self.db.add(metrics)
        
        # Update rebalancing metrics
        metrics.rebalance_count += 1
        
        # Update average impact (rolling average)
        if metrics.avg_rebalance_impact:
            metrics.avg_rebalance_impact = (
                (metrics.avg_rebalance_impact * (metrics.rebalance_count - 1) + 
                 avg_position_change) / metrics.rebalance_count
            )
        else:
            metrics.avg_rebalance_impact = avg_position_change
        
        # Update fairness metrics
        metrics.gini_coefficient = 1 - fairness_after  # Convert back to Gini
        
        self.db.commit()
    
    def adjust_priority_manually(
        self,
        queue_item_id: int,
        new_score: float,
        adjustment_type: str,
        adjustment_reason: str,
        adjusted_by_id: int,
        duration_seconds: Optional[int] = None
    ) -> PriorityAdjustmentLog:
        """Apply manual priority adjustment to a queue item"""
        # Get current priority score
        priority_score = self.db.query(OrderPriorityScore).filter(
            OrderPriorityScore.queue_item_id == queue_item_id
        ).first()
        
        if not priority_score:
            raise NotFoundError(f"Priority score not found for queue item {queue_item_id}")
        
        # Get queue item for position tracking
        queue_item = self.db.query(QueueItem).filter(
            QueueItem.id == queue_item_id
        ).first()
        
        # Store old values
        old_score = priority_score.total_score
        old_position = queue_item.sequence_number
        
        # Apply adjustment
        if adjustment_type == 'boost':
            priority_score.boost_score = new_score - priority_score.base_score
            priority_score.is_boosted = True
            if duration_seconds:
                priority_score.boost_expires_at = datetime.utcnow() + timedelta(
                    seconds=duration_seconds
                )
            priority_score.boost_reason = adjustment_reason
        else:
            priority_score.base_score = new_score
            priority_score.boost_score = 0
        
        priority_score.total_score = new_score
        priority_score.calculated_at = datetime.utcnow()
        
        # Create adjustment log
        adjustment_log = PriorityAdjustmentLog(
            queue_item_id=queue_item_id,
            old_score=old_score,
            new_score=new_score,
            adjustment_type=adjustment_type,
            adjustment_reason=adjustment_reason,
            old_position=old_position,
            adjusted_by_id=adjusted_by_id
        )
        
        self.db.add(adjustment_log)
        self.db.commit()
        
        # Resequence queue if needed
        self._resequence_queue_after_adjustment(queue_item.queue_id)
        
        # Update new position
        self.db.refresh(queue_item)
        adjustment_log.new_position = queue_item.sequence_number
        self.db.commit()
        
        return adjustment_log
    
    def _resequence_queue_after_adjustment(self, queue_id: int):
        """Resequence queue after manual adjustment"""
        # Get all active items with scores
        items = self.db.query(QueueItem, OrderPriorityScore).join(
            OrderPriorityScore,
            OrderPriorityScore.queue_item_id == QueueItem.id
        ).filter(
            QueueItem.queue_id == queue_id,
            QueueItem.status.in_([
                QueueItemStatus.QUEUED,
                QueueItemStatus.IN_PREPARATION
            ])
        ).order_by(
            OrderPriorityScore.total_score.desc(),
            QueueItem.sequence_number
        ).all()
        
        # Assign new sequence numbers
        for seq, (queue_item, score) in enumerate(items, 1):
            queue_item.sequence_number = seq
        
        self.db.commit()
    
    def get_queue_priority_sequence(self, queue_id: int) -> List[Dict[str, Any]]:
        """Get current priority-based sequence for a queue"""
        items = self.db.query(
            QueueItem, OrderPriorityScore, Order
        ).join(
            OrderPriorityScore,
            OrderPriorityScore.queue_item_id == QueueItem.id
        ).join(
            Order,
            Order.id == QueueItem.order_id
        ).filter(
            QueueItem.queue_id == queue_id,
            QueueItem.status.in_([
                QueueItemStatus.QUEUED,
                QueueItemStatus.IN_PREPARATION
            ])
        ).order_by(
            QueueItem.sequence_number
        ).all()
        
        result = []
        for queue_item, priority_score, order in items:
            result.append({
                "sequence_number": queue_item.sequence_number,
                "queue_item_id": queue_item.id,
                "order_id": order.id,
                "order_number": order.order_number,
                "priority_score": priority_score.total_score,
                "is_boosted": priority_score.is_boosted,
                "status": queue_item.status.value,
                "wait_time_minutes": (datetime.utcnow() - queue_item.queued_at).total_seconds() / 60
            })
        
        return result