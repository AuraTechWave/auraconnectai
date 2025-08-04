# backend/modules/orders/services/pricing_rule_service.py

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, time
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload
import logging
import json
import time as time_module
from collections import defaultdict

from core.database import get_db
from ..models.pricing_rule_models import (
    PricingRule, PricingRuleApplication, PricingRuleMetrics,
    RuleType, RuleStatus, ConflictResolution
)
from ..models.order_models import Order, OrderItem
from ..schemas.pricing_rule_schemas import (
    PricingRuleDebugInfo, RuleEvaluationResult, 
    DebugTraceEntry, ConflictInfo
)
from ..metrics.pricing_rule_metrics import pricing_metrics_collector
from ..utils.audit_logger import AuditLogger, audit_action

logger = logging.getLogger(__name__)


class PricingRuleService:
    """Service for managing and applying pricing rules"""
    
    def __init__(self):
        self.debug_mode = False
        self.debug_traces: List[DebugTraceEntry] = []
        self.metrics_collector = defaultdict(int)
        self.audit_logger = AuditLogger("pricing_rules")
    
    async def evaluate_rules_for_order(
        self,
        db: AsyncSession,
        order: Order,
        debug: bool = False
    ) -> Tuple[List[PricingRuleApplication], Optional[PricingRuleDebugInfo]]:
        """
        Evaluate all applicable pricing rules for an order
        
        Args:
            db: Database session
            order: Order to evaluate
            debug: Enable debug mode for rule tracing
            
        Returns:
            Tuple of (applications, debug_info)
        """
        self.debug_mode = debug
        self.debug_traces = []
        applications = []
        start_time = time_module.time()
        
        try:
            # Get all potentially applicable rules
            rules = await self._get_applicable_rules(db, order)
            
            if self.debug_mode:
                self._add_debug_trace(
                    "RULES_FETCHED",
                    f"Found {len(rules)} potentially applicable rules",
                    {"rule_count": len(rules), "rule_ids": [r.id for r in rules]}
                )
            
            # Evaluate each rule
            evaluation_results = []
            for rule in rules:
                result = await self._evaluate_rule(db, rule, order)
                evaluation_results.append(result)
                
                # Track metrics
                pricing_metrics_collector.record_rule_evaluated(
                    order.restaurant_id, rule.rule_type.value
                )
                
                if result.applicable:
                    pricing_metrics_collector.record_rule_applied(
                        order.restaurant_id,
                        rule.rule_type.value,
                        rule.rule_id,
                        float(result.discount_amount)
                    )
                else:
                    pricing_metrics_collector.record_rule_skipped(
                        order.restaurant_id,
                        result.skip_reason or "unknown"
                    )
                
                if self.debug_mode:
                    self._add_debug_trace(
                        "RULE_EVALUATED",
                        f"Rule {rule.name} evaluated",
                        {
                            "rule_id": rule.id,
                            "applicable": result.applicable,
                            "conditions_met": result.conditions_met,
                            "reason": result.skip_reason
                        }
                    )
            
            # Filter applicable rules
            applicable_results = [r for r in evaluation_results if r.applicable]
            
            # Resolve conflicts
            final_results = await self._resolve_conflicts(applicable_results, order)
            
            # Apply rules and create applications
            for result in final_results:
                application = await self._apply_rule(db, result, order)
                if application:
                    applications.append(application)
                    self.metrics_collector['rules_applied'] += 1
            
            # Update metrics
            await self._update_metrics(db, applications)
            
            # Record final metrics
            evaluation_duration = time_module.time() - start_time
            pricing_metrics_collector.record_evaluation_time(
                order.restaurant_id, evaluation_duration
            )
            pricing_metrics_collector.record_rules_per_order(
                order.restaurant_id, len(applications)
            )
            
            # Prepare debug info if requested
            debug_info = None
            if self.debug_mode:
                debug_info = PricingRuleDebugInfo(
                    order_id=order.id,
                    rules_evaluated=len(rules),
                    rules_applied=len(applications),
                    total_discount=sum(app.discount_amount for app in applications),
                    evaluation_results=evaluation_results,
                    debug_traces=self.debug_traces,
                    metrics=dict(self.metrics_collector),
                    total_evaluation_time_ms=evaluation_duration * 1000
                )
            
            return applications, debug_info
            
        except Exception as e:
            logger.error(f"Error evaluating pricing rules: {str(e)}")
            pricing_metrics_collector.record_error(
                order.restaurant_id, type(e).__name__
            )
            if self.debug_mode:
                self._add_debug_trace("ERROR", str(e), {"exception": type(e).__name__})
            raise
    
    async def _get_applicable_rules(
        self, 
        db: AsyncSession, 
        order: Order
    ) -> List[PricingRule]:
        """Get all potentially applicable rules for an order"""
        
        # Base query for active rules
        query = select(PricingRule).where(
            and_(
                PricingRule.restaurant_id == order.restaurant_id,
                PricingRule.status == RuleStatus.ACTIVE,
                PricingRule.valid_from <= datetime.utcnow()
            )
        )
        
        # Add validity check
        query = query.where(
            or_(
                PricingRule.valid_until.is_(None),
                PricingRule.valid_until > datetime.utcnow()
            )
        )
        
        # Order by priority
        query = query.order_by(PricingRule.priority)
        
        result = await db.execute(query)
        rules = result.scalars().all()
        
        return [rule for rule in rules if rule.is_valid()]
    
    async def _evaluate_rule(
        self,
        db: AsyncSession,
        rule: PricingRule,
        order: Order
    ) -> RuleEvaluationResult:
        """Evaluate if a rule applies to an order"""
        
        result = RuleEvaluationResult(
            rule_id=rule.id,
            rule_name=rule.name,
            rule_type=rule.rule_type,
            priority=rule.priority,
            conditions_met={},
            applicable=True
        )
        
        try:
            # Check time conditions
            if 'time' in rule.conditions:
                time_valid = await self._check_time_conditions(
                    rule.conditions['time']
                )
                result.conditions_met['time'] = time_valid
                if not time_valid:
                    result.applicable = False
                    result.skip_reason = "Time conditions not met"
                    return result
            
            # Check item conditions
            if 'items' in rule.conditions:
                items_valid = await self._check_item_conditions(
                    db, rule.conditions['items'], order
                )
                result.conditions_met['items'] = items_valid
                if not items_valid:
                    result.applicable = False
                    result.skip_reason = "Item conditions not met"
                    return result
            
            # Check customer conditions
            if 'customer' in rule.conditions:
                customer_valid = await self._check_customer_conditions(
                    db, rule.conditions['customer'], order
                )
                result.conditions_met['customer'] = customer_valid
                if not customer_valid:
                    result.applicable = False
                    result.skip_reason = "Customer conditions not met"
                    return result
            
            # Check order conditions
            if 'order' in rule.conditions:
                order_valid = await self._check_order_conditions(
                    rule.conditions['order'], order
                )
                result.conditions_met['order'] = order_valid
                if not order_valid:
                    result.applicable = False
                    result.skip_reason = "Order conditions not met"
                    return result
            
            # Check minimum order amount
            if rule.min_order_amount:
                if order.total_amount < rule.min_order_amount:
                    result.applicable = False
                    result.skip_reason = f"Order amount {order.total_amount} below minimum {rule.min_order_amount}"
                    return result
            
            # Check usage limits
            if rule.max_uses_total and rule.current_uses >= rule.max_uses_total:
                result.applicable = False
                result.skip_reason = "Rule usage limit reached"
                return result
            
            # Calculate potential discount
            result.discount_amount = await self._calculate_discount(
                rule, order
            )
            
        except Exception as e:
            logger.error(f"Error evaluating rule {rule.id}: {str(e)}")
            result.applicable = False
            result.skip_reason = f"Evaluation error: {str(e)}"
        
        return result
    
    async def _check_time_conditions(
        self, 
        time_conditions: Dict[str, Any]
    ) -> bool:
        """Check if current time meets rule conditions"""
        now = datetime.utcnow()
        
        # Check days of week
        if 'days_of_week' in time_conditions:
            if now.weekday() not in time_conditions['days_of_week']:
                return False
        
        # Check time range
        if 'start_time' in time_conditions and 'end_time' in time_conditions:
            current_time = now.time()
            start_time = time.fromisoformat(time_conditions['start_time'])
            end_time = time.fromisoformat(time_conditions['end_time'])
            
            if start_time <= end_time:
                if not (start_time <= current_time <= end_time):
                    return False
            else:  # Handles overnight ranges
                if not (current_time >= start_time or current_time <= end_time):
                    return False
        
        return True
    
    async def _check_item_conditions(
        self,
        db: AsyncSession,
        item_conditions: Dict[str, Any],
        order: Order
    ) -> bool:
        """Check if order items meet rule conditions"""
        
        order_item_ids = [item.menu_item_id for item in order.items]
        
        # Check specific items
        if 'menu_item_ids' in item_conditions:
            required_items = set(item_conditions['menu_item_ids'])
            if not required_items.intersection(order_item_ids):
                return False
        
        # Check excluded items
        if 'exclude_item_ids' in item_conditions:
            excluded_items = set(item_conditions['exclude_item_ids'])
            if excluded_items.intersection(order_item_ids):
                return False
        
        # Check categories (would need to join with menu items)
        if 'category_ids' in item_conditions:
            # This would require loading menu items and checking categories
            # Simplified for now
            pass
        
        return True
    
    async def _check_customer_conditions(
        self,
        db: AsyncSession,
        customer_conditions: Dict[str, Any],
        order: Order
    ) -> bool:
        """Check if customer meets rule conditions"""
        
        if not order.customer_id:
            return False
        
        # Check loyalty tier
        if 'loyalty_tier' in customer_conditions:
            # Would need to check customer's loyalty status
            pass
        
        # Check minimum orders
        if 'min_orders' in customer_conditions:
            # Would need to count customer's previous orders
            pass
        
        # Check tags
        if 'tags' in customer_conditions:
            # Would need to check customer tags
            pass
        
        return True
    
    async def _check_order_conditions(
        self,
        order_conditions: Dict[str, Any],
        order: Order
    ) -> bool:
        """Check if order meets rule conditions"""
        
        # Check minimum items
        if 'min_items' in order_conditions:
            if len(order.items) < order_conditions['min_items']:
                return False
        
        # Check payment methods
        if 'payment_methods' in order_conditions:
            # Would need to check order's payment method
            pass
        
        # Check order types
        if 'order_types' in order_conditions:
            if order.order_type not in order_conditions['order_types']:
                return False
        
        return True
    
    async def _calculate_discount(
        self,
        rule: PricingRule,
        order: Order
    ) -> Decimal:
        """Calculate discount amount for a rule"""
        
        base_amount = order.subtotal
        discount = Decimal('0')
        
        if rule.rule_type == RuleType.PERCENTAGE_DISCOUNT:
            discount = base_amount * (rule.discount_value / 100)
            if rule.max_discount_amount:
                discount = min(discount, rule.max_discount_amount)
        
        elif rule.rule_type == RuleType.FIXED_DISCOUNT:
            discount = min(rule.discount_value, base_amount)
        
        elif rule.rule_type == RuleType.BUNDLE_DISCOUNT:
            # Complex calculation based on bundle items
            pass
        
        elif rule.rule_type == RuleType.BOGO:
            # Calculate based on item pairs
            pass
        
        # Add other rule type calculations...
        
        return discount
    
    async def _resolve_conflicts(
        self,
        results: List[RuleEvaluationResult],
        order: Order
    ) -> List[RuleEvaluationResult]:
        """Resolve conflicts between multiple applicable rules"""
        
        if len(results) <= 1:
            return results
        
        # Group by stackability
        stackable = [r for r in results if r.rule.stackable]
        non_stackable = [r for r in results if not r.rule.stackable]
        
        final_results = []
        
        # Handle non-stackable rules based on conflict resolution
        if non_stackable:
            if order.restaurant.default_conflict_resolution == ConflictResolution.HIGHEST_DISCOUNT:
                # Sort by discount amount descending
                non_stackable.sort(key=lambda x: x.discount_amount, reverse=True)
                final_results.append(non_stackable[0])
                
                # Track conflicts
                for skipped in non_stackable[1:]:
                    self.metrics_collector['conflicts_skipped'] += 1
                    if self.debug_mode:
                        self._add_debug_trace(
                            "CONFLICT_SKIPPED",
                            f"Rule {skipped.rule_name} skipped due to conflict",
                            {
                                "rule_id": skipped.rule_id,
                                "discount": float(skipped.discount_amount),
                                "reason": "Lower discount than selected rule"
                            }
                        )
            
            elif order.restaurant.default_conflict_resolution == ConflictResolution.PRIORITY_BASED:
                # Already sorted by priority from query
                final_results.append(non_stackable[0])
            
            elif order.restaurant.default_conflict_resolution == ConflictResolution.FIRST_MATCH:
                final_results.append(non_stackable[0])
        
        # Add stackable rules
        for rule in stackable:
            # Check if it can stack with selected rules
            can_stack = True
            for selected in final_results:
                if selected.rule_id in rule.rule.excluded_rule_ids:
                    can_stack = False
                    break
            
            if can_stack:
                final_results.append(rule)
                self.metrics_collector['stacking_count'] += 1
            else:
                self.metrics_collector['conflicts_skipped'] += 1
        
        return final_results
    
    async def _apply_rule(
        self,
        db: AsyncSession,
        result: RuleEvaluationResult,
        order: Order
    ) -> Optional[PricingRuleApplication]:
        """Apply a pricing rule to an order"""
        
        try:
            application = PricingRuleApplication(
                rule_id=result.rule_id,
                order_id=order.id,
                customer_id=order.customer_id,
                discount_amount=result.discount_amount,
                original_amount=order.total_amount,
                final_amount=order.total_amount - result.discount_amount,
                applied_by='system',
                conditions_met=result.conditions_met,
                application_metadata={
                    'debug_mode': self.debug_mode,
                    'evaluation_time': datetime.utcnow().isoformat()
                }
            )
            
            db.add(application)
            
            # Update rule usage count
            rule = await db.get(PricingRule, result.rule_id)
            rule.current_uses += 1
            
            # Update order discount
            order.discount_amount = (order.discount_amount or 0) + result.discount_amount
            order.total_amount = order.subtotal - order.discount_amount
            
            await db.commit()
            
            return application
            
        except Exception as e:
            logger.error(f"Error applying rule {result.rule_id}: {str(e)}")
            await db.rollback()
            return None
    
    async def _update_metrics(
        self,
        db: AsyncSession,
        applications: List[PricingRuleApplication]
    ):
        """Update metrics for applied rules"""
        
        if not applications:
            return
        
        # Group by rule
        rule_metrics = defaultdict(lambda: {
            'count': 0,
            'discount': Decimal('0'),
            'customers': set()
        })
        
        for app in applications:
            metrics = rule_metrics[app.rule_id]
            metrics['count'] += 1
            metrics['discount'] += app.discount_amount
            if app.customer_id:
                metrics['customers'].add(app.customer_id)
        
        # Update metrics records
        today = datetime.utcnow().date()
        
        for rule_id, metrics in rule_metrics.items():
            # Get or create metric record
            result = await db.execute(
                select(PricingRuleMetrics).where(
                    and_(
                        PricingRuleMetrics.rule_id == rule_id,
                        func.date(PricingRuleMetrics.date) == today
                    )
                )
            )
            metric = result.scalar_one_or_none()
            
            if not metric:
                metric = PricingRuleMetrics(
                    rule_id=rule_id,
                    date=datetime.utcnow()
                )
                db.add(metric)
            
            # Update metrics
            metric.applications_count += metrics['count']
            metric.total_discount_amount += metrics['discount']
            metric.unique_customers = len(metrics['customers'])
            metric.conflicts_skipped += self.metrics_collector.get('conflicts_skipped', 0)
            metric.stacking_count += self.metrics_collector.get('stacking_count', 0)
        
        await db.commit()
    
    def _add_debug_trace(
        self,
        event_type: str,
        message: str,
        data: Dict[str, Any] = None
    ):
        """Add a debug trace entry"""
        
        if self.debug_mode:
            self.debug_traces.append(DebugTraceEntry(
                timestamp=datetime.utcnow(),
                event_type=event_type,
                message=message,
                data=data or {}
            ))
    
    # Audit logging methods
    
    async def create_pricing_rule_with_audit(
        self,
        db: AsyncSession,
        rule_data: Dict[str, Any],
        user_id: int,
        ip_address: Optional[str] = None
    ) -> PricingRule:
        """Create a pricing rule with audit logging"""
        
        try:
            # Create the rule (this would be implemented in the actual service)
            rule = PricingRule(**rule_data)
            db.add(rule)
            await db.flush()
            
            # Audit log the creation
            self.audit_logger.log_action(
                action="create_pricing_rule",
                user_id=user_id,
                resource_type="pricing_rule",
                resource_id=rule.id,
                details={
                    "rule_name": rule.name,
                    "rule_type": rule.rule_type.value,
                    "restaurant_id": rule.restaurant_id,
                    "discount_value": float(rule.discount_value) if rule.discount_value else None,
                    "priority": rule.priority.value,
                    "stackable": rule.stackable,
                    "conditions": rule.conditions
                },
                ip_address=ip_address
            )
            
            await db.commit()
            return rule
            
        except Exception as e:
            await db.rollback()
            self.audit_logger.log_action(
                action="create_pricing_rule",
                user_id=user_id,
                resource_type="pricing_rule",
                resource_id=None,
                details={"error": str(e), "rule_data": rule_data},
                result="failure",
                ip_address=ip_address
            )
            raise
    
    async def update_pricing_rule_with_audit(
        self,
        db: AsyncSession,
        rule_id: int,
        update_data: Dict[str, Any],
        user_id: int,
        ip_address: Optional[str] = None
    ) -> PricingRule:
        """Update a pricing rule with audit logging"""
        
        try:
            # Get the existing rule
            rule = await db.get(PricingRule, rule_id)
            if not rule:
                raise ValueError(f"Pricing rule {rule_id} not found")
            
            # Capture old values for audit
            old_values = {
                "name": rule.name,
                "rule_type": rule.rule_type.value,
                "discount_value": float(rule.discount_value) if rule.discount_value else None,
                "priority": rule.priority.value,
                "stackable": rule.stackable,
                "conditions": rule.conditions,
                "status": rule.status.value
            }
            
            # Apply updates
            for field, value in update_data.items():
                if hasattr(rule, field):
                    setattr(rule, field, value)
            
            rule.updated_at = datetime.utcnow()
            
            # Capture new values
            new_values = {
                "name": rule.name,
                "rule_type": rule.rule_type.value,
                "discount_value": float(rule.discount_value) if rule.discount_value else None,
                "priority": rule.priority.value,
                "stackable": rule.stackable,
                "conditions": rule.conditions,
                "status": rule.status.value
            }
            
            # Find changed fields
            changed_fields = {}
            for field in old_values:
                if old_values[field] != new_values[field]:
                    changed_fields[field] = {
                        "old": old_values[field],
                        "new": new_values[field]
                    }
            
            # Audit log the update
            self.audit_logger.log_action(
                action="update_pricing_rule",
                user_id=user_id,
                resource_type="pricing_rule",
                resource_id=rule_id,
                details={
                    "rule_name": rule.name,
                    "changed_fields": changed_fields,
                    "update_data": update_data
                },
                ip_address=ip_address
            )
            
            await db.commit()
            return rule
            
        except Exception as e:
            await db.rollback()
            self.audit_logger.log_action(
                action="update_pricing_rule",
                user_id=user_id,
                resource_type="pricing_rule",
                resource_id=rule_id,
                details={"error": str(e), "update_data": update_data},
                result="failure",
                ip_address=ip_address
            )
            raise
    
    async def delete_pricing_rule_with_audit(
        self,
        db: AsyncSession,
        rule_id: int,
        user_id: int,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """Delete a pricing rule with audit logging"""
        
        try:
            # Get the rule for audit details
            rule = await db.get(PricingRule, rule_id)
            if not rule:
                raise ValueError(f"Pricing rule {rule_id} not found")
            
            rule_details = {
                "rule_name": rule.name,
                "rule_type": rule.rule_type.value,
                "restaurant_id": rule.restaurant_id,
                "discount_value": float(rule.discount_value) if rule.discount_value else None,
                "deletion_reason": reason
            }
            
            # Delete the rule
            await db.delete(rule)
            
            # Audit log the deletion
            self.audit_logger.log_action(
                action="delete_pricing_rule",
                user_id=user_id,
                resource_type="pricing_rule",
                resource_id=rule_id,
                details=rule_details,
                ip_address=ip_address
            )
            
            await db.commit()
            
        except Exception as e:
            await db.rollback()
            self.audit_logger.log_action(
                action="delete_pricing_rule",
                user_id=user_id,
                resource_type="pricing_rule",
                resource_id=rule_id,
                details={"error": str(e), "reason": reason},
                result="failure",
                ip_address=ip_address
            )
            raise
    
    async def activate_rule_with_audit(
        self,
        db: AsyncSession,
        rule_id: int,
        user_id: int,
        ip_address: Optional[str] = None
    ):
        """Activate a pricing rule with audit logging"""
        
        try:
            rule = await db.get(PricingRule, rule_id)
            if not rule:
                raise ValueError(f"Pricing rule {rule_id} not found")
            
            old_status = rule.status
            rule.status = RuleStatus.ACTIVE
            rule.updated_at = datetime.utcnow()
            
            self.audit_logger.log_action(
                action="activate_pricing_rule",
                user_id=user_id,
                resource_type="pricing_rule",
                resource_id=rule_id,
                details={
                    "rule_name": rule.name,
                    "old_status": old_status.value,
                    "new_status": "ACTIVE"
                },
                ip_address=ip_address
            )
            
            await db.commit()
            
        except Exception as e:
            await db.rollback()
            self.audit_logger.log_action(
                action="activate_pricing_rule",
                user_id=user_id,
                resource_type="pricing_rule",
                resource_id=rule_id,
                details={"error": str(e)},
                result="failure",
                ip_address=ip_address
            )
            raise
    
    async def deactivate_rule_with_audit(
        self,
        db: AsyncSession,
        rule_id: int,
        user_id: int,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """Deactivate a pricing rule with audit logging"""
        
        try:
            rule = await db.get(PricingRule, rule_id)
            if not rule:
                raise ValueError(f"Pricing rule {rule_id} not found")
            
            old_status = rule.status
            rule.status = RuleStatus.INACTIVE
            rule.updated_at = datetime.utcnow()
            
            self.audit_logger.log_action(
                action="deactivate_pricing_rule",
                user_id=user_id,
                resource_type="pricing_rule",
                resource_id=rule_id,
                details={
                    "rule_name": rule.name,
                    "old_status": old_status.value,
                    "new_status": "INACTIVE",
                    "reason": reason
                },
                ip_address=ip_address
            )
            
            await db.commit()
            
        except Exception as e:
            await db.rollback()
            self.audit_logger.log_action(
                action="deactivate_pricing_rule",
                user_id=user_id,
                resource_type="pricing_rule",
                resource_id=rule_id,
                details={"error": str(e), "reason": reason},
                result="failure",
                ip_address=ip_address
            )
            raise


# Create singleton instance
pricing_rule_service = PricingRuleService()