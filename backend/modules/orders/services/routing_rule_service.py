"""
Service for managing and evaluating order routing rules.
"""

import logging
import re
import json
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime, time
from decimal import Decimal
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status

from ..models.routing_models import (
    OrderRoutingRule,
    RoutingRuleCondition,
    RoutingRuleAction,
    RoutingRuleLog,
    RouteOverride,
    StaffRoutingCapability,
    TeamRoutingConfig,
    TeamMember,
    RouteTargetType,
    RuleConditionOperator,
    RuleStatus,
)
from ..models.order_models import Order, OrderItem
from ..schemas.routing_schemas import (
    RoutingRuleCreate,
    RoutingRuleUpdate,
    RouteEvaluationRequest,
    RouteEvaluationResult,
    RouteOverrideCreate,
    RoutingRuleTestRequest,
    RoutingRuleTestResult,
    StaffCapabilityCreate,
    TeamRoutingConfigCreate,
    TeamMemberCreate,
)
from ...staff.models import StaffMember
from ...menu.models import MenuItem
from ...customers.models import Customer
from modules.kds.services.kds_order_routing_service import KDSOrderRoutingService

logger = logging.getLogger(__name__)


class RoutingRuleService:
    """Service for managing order routing rules"""

    def __init__(self, db: Session):
        self.db = db
        self.kds_routing = KDSOrderRoutingService(db)
        self._field_extractors = self._initialize_field_extractors()

    # Rule Management
    def create_routing_rule(
        self, rule_data: RoutingRuleCreate, created_by_id: int
    ) -> OrderRoutingRule:
        """Create a new routing rule with conditions and actions"""
        try:
            # Create the rule
            rule = OrderRoutingRule(
                name=rule_data.name,
                description=rule_data.description,
                priority=rule_data.priority,
                status=rule_data.status,
                target_type=rule_data.target_type,
                target_id=rule_data.target_id,
                target_config=rule_data.target_config,
                active_from=rule_data.active_from,
                active_until=rule_data.active_until,
                schedule_config=rule_data.schedule_config,
                created_by=created_by_id,
            )
            self.db.add(rule)
            self.db.flush()

            # Add conditions
            for condition_data in rule_data.conditions:
                condition = RoutingRuleCondition(
                    rule_id=rule.id,
                    field_path=condition_data.field_path,
                    operator=condition_data.operator,
                    value=condition_data.value,
                    condition_group=condition_data.condition_group,
                    is_negated=condition_data.is_negated,
                )
                self.db.add(condition)

            # Add actions
            for action_data in rule_data.actions:
                action = RoutingRuleAction(
                    rule_id=rule.id,
                    action_type=action_data.action_type,
                    action_config=action_data.action_config,
                    execution_order=action_data.execution_order,
                    condition_expression=action_data.condition_expression,
                )
                self.db.add(action)

            self.db.commit()
            self.db.refresh(rule)

            logger.info(
                f"Created routing rule '{rule.name}' with {len(rule_data.conditions)} conditions and {len(rule_data.actions)} actions"
            )
            return rule

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to create routing rule: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create routing rule",
            )

    def update_routing_rule(
        self, rule_id: int, update_data: RoutingRuleUpdate, updated_by_id: int
    ) -> OrderRoutingRule:
        """Update an existing routing rule"""
        rule = (
            self.db.query(OrderRoutingRule)
            .filter(OrderRoutingRule.id == rule_id)
            .first()
        )
        if not rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Routing rule {rule_id} not found",
            )

        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(rule, field, value)

        rule.updated_by = updated_by_id

        self.db.commit()
        self.db.refresh(rule)

        logger.info(f"Updated routing rule {rule_id}")
        return rule

    def get_routing_rule(self, rule_id: int) -> OrderRoutingRule:
        """Get a routing rule with all its conditions and actions"""
        rule = (
            self.db.query(OrderRoutingRule)
            .options(
                joinedload(OrderRoutingRule.conditions),
                joinedload(OrderRoutingRule.actions),
            )
            .filter(OrderRoutingRule.id == rule_id)
            .first()
        )

        if not rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Routing rule {rule_id} not found",
            )

        return rule

    def list_routing_rules(
        self,
        status_filter: Optional[RuleStatus] = None,
        target_type: Optional[RouteTargetType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[OrderRoutingRule]:
        """List routing rules with optional filters"""
        query = self.db.query(OrderRoutingRule).options(
            joinedload(OrderRoutingRule.conditions),
            joinedload(OrderRoutingRule.actions),
        )

        if status_filter:
            query = query.filter(OrderRoutingRule.status == status_filter)

        if target_type:
            query = query.filter(OrderRoutingRule.target_type == target_type)

        return (
            query.order_by(desc(OrderRoutingRule.priority))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def delete_routing_rule(self, rule_id: int) -> None:
        """Delete a routing rule"""
        rule = (
            self.db.query(OrderRoutingRule)
            .filter(OrderRoutingRule.id == rule_id)
            .first()
        )
        if not rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Routing rule {rule_id} not found",
            )

        self.db.delete(rule)
        self.db.commit()

        logger.info(f"Deleted routing rule {rule_id}")

    # Rule Evaluation
    def evaluate_order_routing(
        self, request: RouteEvaluationRequest
    ) -> RouteEvaluationResult:
        """Evaluate routing rules for an order and determine routing"""
        start_time = datetime.utcnow()

        # Get the order with relationships
        order = (
            self.db.query(Order)
            .options(joinedload(Order.order_items), joinedload(Order.customer))
            .filter(Order.id == request.order_id)
            .first()
        )

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order {request.order_id} not found",
            )

        # Check for manual override first
        override = self._check_route_override(order.id)
        if override and not request.force_evaluation:
            return RouteEvaluationResult(
                order_id=order.id,
                evaluated_rules=0,
                matched_rules=[],
                routing_decision={
                    "type": "override",
                    "target_type": override.target_type.value,
                    "target_id": override.target_id,
                    "reason": override.reason,
                },
                evaluation_time_ms=0,
                test_mode=request.test_mode,
            )

        # Get applicable rules
        rules = self._get_applicable_rules(request.include_inactive)

        matched_rules = []
        errors = []

        # Evaluate each rule
        for rule in rules:
            try:
                rule_matched, match_details = self._evaluate_rule(rule, order)

                if rule_matched:
                    matched_rules.append(
                        {
                            "rule_id": rule.id,
                            "rule_name": rule.name,
                            "priority": rule.priority,
                            "match_details": match_details,
                        }
                    )

                    # Log the evaluation
                    if not request.test_mode:
                        self._log_rule_evaluation(
                            rule,
                            order,
                            True,
                            match_details,
                            (datetime.utcnow() - start_time).total_seconds() * 1000,
                        )

                    # Update rule statistics
                    rule.evaluation_count += 1
                    rule.match_count += 1
                    rule.last_matched_at = datetime.utcnow()

                else:
                    rule.evaluation_count += 1

            except Exception as e:
                logger.error(f"Error evaluating rule {rule.id}: {str(e)}")
                errors.append(f"Rule {rule.id}: {str(e)}")

        # Determine final routing decision
        routing_decision = self._determine_routing_decision(
            matched_rules, order, request.test_mode
        )

        # Apply routing if not in test mode
        if not request.test_mode and routing_decision:
            self._apply_routing_decision(order, routing_decision)

        self.db.commit()

        evaluation_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        return RouteEvaluationResult(
            order_id=order.id,
            evaluated_rules=len(rules),
            matched_rules=matched_rules,
            routing_decision=routing_decision,
            evaluation_time_ms=evaluation_time,
            test_mode=request.test_mode,
            errors=errors,
        )

    def _evaluate_rule(
        self, rule: OrderRoutingRule, order: Order
    ) -> Tuple[bool, Dict[str, Any]]:
        """Evaluate a single rule against an order"""
        # Check if rule is currently active
        if not self._is_rule_active(rule):
            return False, {"reason": "Rule not active"}

        # Group conditions by group number
        condition_groups = {}
        for condition in rule.conditions:
            if condition.condition_group not in condition_groups:
                condition_groups[condition.condition_group] = []
            condition_groups[condition.condition_group].append(condition)

        # Evaluate each group (OR between groups, AND within groups)
        group_results = {}
        for group_id, conditions in condition_groups.items():
            group_matched = True
            condition_results = []

            for condition in conditions:
                matched = self._evaluate_condition(condition, order)
                condition_results.append(
                    {
                        "field": condition.field_path,
                        "operator": condition.operator.value,
                        "expected": condition.value,
                        "matched": matched,
                    }
                )

                if not matched:
                    group_matched = False
                    break

            group_results[group_id] = {
                "matched": group_matched,
                "conditions": condition_results,
            }

        # Rule matches if any group matches
        rule_matched = any(result["matched"] for result in group_results.values())

        return rule_matched, {"groups": group_results}

    def _evaluate_condition(
        self, condition: RoutingRuleCondition, order: Order
    ) -> bool:
        """Evaluate a single condition"""
        try:
            # Extract field value
            field_value = self._extract_field_value(condition.field_path, order)

            # Apply operator
            result = self._apply_operator(
                field_value, condition.operator, condition.value
            )

            # Apply negation if needed
            if condition.is_negated:
                result = not result

            return result

        except Exception as e:
            logger.warning(f"Failed to evaluate condition {condition.id}: {str(e)}")
            return False

    def _extract_field_value(self, field_path: str, order: Order) -> Any:
        """Extract field value from order using dot notation"""
        parts = field_path.split(".")

        if parts[0] in self._field_extractors:
            return self._field_extractors[parts[0]](parts[1:], order)

        raise ValueError(f"Unknown field path: {field_path}")

    def _initialize_field_extractors(self) -> Dict[str, Any]:
        """Initialize field extraction functions"""
        return {
            "order": self._extract_order_fields,
            "customer": self._extract_customer_fields,
            "item": self._extract_item_fields,
            "metadata": self._extract_metadata_fields,
            "context": self._extract_context_fields,
        }

    def _extract_order_fields(self, path_parts: List[str], order: Order) -> Any:
        """Extract fields from order object"""
        if not path_parts:
            return None

        field = path_parts[0]

        if field == "type":
            # Determine order type (dine-in, takeout, delivery)
            if order.table_no:
                return "dine_in"
            elif hasattr(order, "delivery_address"):
                return "delivery"
            else:
                return "takeout"
        elif field == "total":
            return float(order.final_amount) if order.final_amount else 0
        elif field == "item_count":
            return sum(item.quantity for item in order.order_items)
        elif field == "status":
            return (
                order.status.value if hasattr(order.status, "value") else order.status
            )
        elif field == "priority":
            return (
                order.priority.value
                if hasattr(order, "priority") and order.priority
                else "normal"
            )
        elif field == "scheduled_time":
            return order.scheduled_fulfillment_time
        else:
            return getattr(order, field, None)

    def _extract_customer_fields(self, path_parts: List[str], order: Order) -> Any:
        """Extract fields from customer object"""
        if not path_parts or not order.customer:
            return None

        field = path_parts[0]

        if field == "vip_status":
            return getattr(order.customer, "vip_status", False)
        elif field == "order_count":
            # Would need to query this
            return (
                self.db.query(Order)
                .filter(Order.customer_id == order.customer_id)
                .count()
            )
        else:
            return getattr(order.customer, field, None)

    def _extract_item_fields(self, path_parts: List[str], order: Order) -> Any:
        """Extract fields from order items"""
        if not path_parts:
            return None

        field = path_parts[0]

        if field == "categories":
            # Get all unique categories from items
            categories = set()
            for item in order.order_items:
                menu_item = (
                    self.db.query(MenuItem)
                    .filter(MenuItem.id == item.menu_item_id)
                    .first()
                )
                if menu_item and hasattr(menu_item, "category") and menu_item.category:
                    categories.add(menu_item.category.name)
            return list(categories)
        elif field == "has_alcohol":
            # Check if any item contains alcohol
            for item in order.order_items:
                menu_item = (
                    self.db.query(MenuItem)
                    .filter(MenuItem.id == item.menu_item_id)
                    .first()
                )
                if (
                    menu_item
                    and hasattr(menu_item, "contains_alcohol")
                    and menu_item.contains_alcohol
                ):
                    return True
            return False
        else:
            # Return list of values from all items
            values = []
            for item in order.order_items:
                if hasattr(item, field):
                    values.append(getattr(item, field))
            return values

    def _extract_metadata_fields(self, path_parts: List[str], order: Order) -> Any:
        """Extract fields from order metadata"""
        # This would extract from JSON metadata if stored
        return None

    def _extract_context_fields(self, path_parts: List[str], order: Order) -> Any:
        """Extract contextual fields"""
        if not path_parts:
            return None

        field = path_parts[0]

        if field == "time_of_day":
            hour = datetime.utcnow().hour
            if 6 <= hour < 11:
                return "breakfast"
            elif 11 <= hour < 15:
                return "lunch"
            elif 15 <= hour < 17:
                return "afternoon"
            elif 17 <= hour < 22:
                return "dinner"
            else:
                return "late_night"
        elif field == "day_of_week":
            return datetime.utcnow().strftime("%A").lower()
        elif field == "is_peak_hour":
            hour = datetime.utcnow().hour
            return 12 <= hour <= 14 or 18 <= hour <= 20
        else:
            return None

    def _apply_operator(
        self, field_value: Any, operator: RuleConditionOperator, expected_value: Any
    ) -> bool:
        """Apply comparison operator"""
        if field_value is None:
            return False

        if operator == RuleConditionOperator.EQUALS:
            return str(field_value).lower() == str(expected_value).lower()
        elif operator == RuleConditionOperator.NOT_EQUALS:
            return str(field_value).lower() != str(expected_value).lower()
        elif operator == RuleConditionOperator.CONTAINS:
            return str(expected_value).lower() in str(field_value).lower()
        elif operator == RuleConditionOperator.NOT_CONTAINS:
            return str(expected_value).lower() not in str(field_value).lower()
        elif operator == RuleConditionOperator.IN:
            if isinstance(expected_value, list):
                return field_value in expected_value
            return False
        elif operator == RuleConditionOperator.NOT_IN:
            if isinstance(expected_value, list):
                return field_value not in expected_value
            return True
        elif operator == RuleConditionOperator.GREATER_THAN:
            try:
                return float(field_value) > float(expected_value)
            except:
                return False
        elif operator == RuleConditionOperator.LESS_THAN:
            try:
                return float(field_value) < float(expected_value)
            except:
                return False
        elif operator == RuleConditionOperator.BETWEEN:
            if isinstance(expected_value, list) and len(expected_value) == 2:
                try:
                    val = float(field_value)
                    return float(expected_value[0]) <= val <= float(expected_value[1])
                except:
                    return False
            return False
        elif operator == RuleConditionOperator.REGEX:
            try:
                return bool(re.match(str(expected_value), str(field_value)))
            except:
                return False

        return False

    def _is_rule_active(self, rule: OrderRoutingRule) -> bool:
        """Check if a rule is currently active"""
        if rule.status != RuleStatus.ACTIVE:
            return False

        now = datetime.utcnow()

        # Check active date range
        if rule.active_from and now < rule.active_from:
            return False
        if rule.active_until and now > rule.active_until:
            return False

        # Check schedule
        if rule.schedule_config:
            return self._check_schedule(rule.schedule_config)

        return True

    def _check_schedule(self, schedule: Dict[str, Any]) -> bool:
        """Check if current time matches schedule"""
        now = datetime.utcnow()

        # Check days
        if "days" in schedule:
            current_day = now.strftime("%A").lower()
            if current_day not in [day.lower() for day in schedule["days"]]:
                return False

        # Check hours
        if "hours" in schedule:
            current_time = now.time()
            start_time = time.fromisoformat(schedule["hours"]["start"])
            end_time = time.fromisoformat(schedule["hours"]["end"])

            if not (start_time <= current_time <= end_time):
                return False

        return True

    def _get_applicable_rules(
        self, include_inactive: bool = False
    ) -> List[OrderRoutingRule]:
        """Get rules that should be evaluated"""
        query = self.db.query(OrderRoutingRule).options(
            joinedload(OrderRoutingRule.conditions),
            joinedload(OrderRoutingRule.actions),
        )

        if not include_inactive:
            query = query.filter(
                OrderRoutingRule.status.in_([RuleStatus.ACTIVE, RuleStatus.TESTING])
            )

        return query.order_by(desc(OrderRoutingRule.priority)).all()

    def _determine_routing_decision(
        self, matched_rules: List[Dict[str, Any]], order: Order, test_mode: bool
    ) -> Dict[str, Any]:
        """Determine final routing decision from matched rules"""
        if not matched_rules:
            # Default routing logic
            return self._get_default_routing(order)

        # Sort by priority (highest first)
        sorted_matches = sorted(
            matched_rules, key=lambda x: x["priority"], reverse=True
        )

        # Check for priority conflicts
        if len(sorted_matches) > 1:
            top_priority = sorted_matches[0]["priority"]
            conflicts = [m for m in sorted_matches if m["priority"] == top_priority]

            if len(conflicts) > 1:
                # Log priority conflict
                conflict_names = [m["rule_name"] for m in conflicts]
                logger.warning(
                    f"Priority conflict detected for order {order.id}. "
                    f"Rules with same priority ({top_priority}): {conflict_names}. "
                    f"Using first rule: {conflicts[0]['rule_name']}"
                )

                # Add conflict info to decision
                decision_base = self._build_routing_decision_from_rule(
                    conflicts[0]["rule_id"]
                )
                decision_base["conflicts"] = {
                    "detected": True,
                    "conflicting_rules": conflict_names,
                    "resolution": "first_rule",
                }
                return decision_base

        # Use highest priority rule
        highest_priority_match = sorted_matches[0]
        rule = (
            self.db.query(OrderRoutingRule)
            .filter(OrderRoutingRule.id == highest_priority_match["rule_id"])
            .first()
        )

        if not rule:
            return self._get_default_routing(order)

        # Build routing decision
        decision = {
            "type": "rule",
            "rule_id": rule.id,
            "rule_name": rule.name,
            "target_type": rule.target_type.value,
            "target_id": rule.target_id,
            "target_config": rule.target_config or {},
            "applied_priority": rule.priority,
        }

        # Execute actions to enhance routing decision
        executed_actions = []
        for action in sorted(rule.actions, key=lambda x: x.execution_order):
            if action.action_type == "route":
                # Update routing target from action config
                if "target_id" in action.action_config:
                    decision["target_id"] = action.action_config["target_id"]
                if "target_config" in action.action_config:
                    decision["target_config"].update(
                        action.action_config["target_config"]
                    )
                executed_actions.append(
                    {"type": "route", "config": action.action_config}
                )
            elif action.action_type == "priority":
                decision["priority_adjustment"] = action.action_config.get(
                    "adjustment", 0
                )
                executed_actions.append(
                    {"type": "priority", "adjustment": decision["priority_adjustment"]}
                )
            elif action.action_type == "split":
                decision["split_config"] = action.action_config
                executed_actions.append(
                    {"type": "split", "config": action.action_config}
                )
            elif action.action_type == "notify":
                # Queue notification
                decision["notifications"] = decision.get("notifications", [])
                decision["notifications"].append(action.action_config)
                executed_actions.append(
                    {"type": "notify", "config": action.action_config}
                )

        decision["executed_actions"] = executed_actions

        return decision

    def _build_routing_decision_from_rule(self, rule_id: int) -> Dict[str, Any]:
        """Build routing decision from a rule ID"""
        rule = (
            self.db.query(OrderRoutingRule)
            .filter(OrderRoutingRule.id == rule_id)
            .first()
        )

        if not rule:
            return self._get_default_routing(None)

        decision = {
            "type": "rule",
            "rule_id": rule.id,
            "rule_name": rule.name,
            "target_type": rule.target_type.value,
            "target_id": rule.target_id,
            "target_config": rule.target_config or {},
            "applied_priority": rule.priority,
        }

        return decision

    def _get_default_routing(self, order: Order) -> Dict[str, Any]:
        """Get default routing when no rules match"""
        # Use existing KDS routing logic as fallback
        try:
            routed_items = self.kds_routing.route_order_to_stations(order.id)
            if routed_items:
                return {
                    "type": "default",
                    "target_type": "station",
                    "target_id": routed_items[0].station_id if routed_items else None,
                    "message": "Default KDS routing applied",
                }
        except:
            pass

        return {
            "type": "default",
            "target_type": "queue",
            "target_id": None,
            "message": "No routing rules matched, sent to default queue",
        }

    def _apply_routing_decision(self, order: Order, decision: Dict[str, Any]) -> None:
        """Apply the routing decision to the order"""
        target_type = decision.get("target_type")
        target_id = decision.get("target_id")

        if target_type == "station":
            # Route to kitchen station
            self.kds_routing.route_order_to_stations(order.id)
        elif target_type == "staff":
            # Assign to specific staff member
            # This would update order assignment
            pass
        elif target_type == "team":
            # Route to team
            self._route_to_team(order, target_id)
        elif target_type == "queue":
            # Add to queue
            # This would add to a work queue
            pass

        # Apply any additional actions
        if "priority_adjustment" in decision:
            # Adjust order priority
            pass

        if "split_config" in decision:
            # Split the order
            pass

    def _route_to_team(self, order: Order, team_id: int) -> None:
        """Route order to a team using team's routing strategy"""
        team = (
            self.db.query(TeamRoutingConfig)
            .filter(TeamRoutingConfig.id == team_id)
            .first()
        )

        if not team or not team.is_active:
            logger.warning(f"Team {team_id} not found or inactive")
            return

        # Get active team members
        members = (
            self.db.query(TeamMember)
            .filter(TeamMember.team_id == team_id, TeamMember.is_active == True)
            .all()
        )

        if not members:
            logger.warning(f"No active members in team {team_id}")
            return

        # Apply routing strategy
        if team.routing_strategy == "round_robin":
            # Simple round-robin assignment
            # In production, would track last assigned
            selected_member = members[0]
        elif team.routing_strategy == "least_loaded":
            # Assign to member with lowest current load
            selected_member = min(members, key=lambda m: m.current_load)
        elif team.routing_strategy == "skill_based":
            # Match based on capabilities
            # Would need to implement skill matching
            selected_member = members[0]
        else:
            selected_member = members[0]

        # Update assignment
        selected_member.current_load += 1
        team.current_load += 1

        logger.info(
            f"Routed order {order.id} to team member {selected_member.staff_id}"
        )

    def _check_route_override(self, order_id: int) -> Optional[RouteOverride]:
        """Check if there's an active override for this order"""
        override = (
            self.db.query(RouteOverride)
            .filter(
                RouteOverride.order_id == order_id,
                or_(
                    RouteOverride.expires_at.is_(None),
                    RouteOverride.expires_at > datetime.utcnow(),
                ),
            )
            .first()
        )

        return override

    def _log_rule_evaluation(
        self,
        rule: OrderRoutingRule,
        order: Order,
        matched: bool,
        match_details: Dict[str, Any],
        evaluation_time_ms: float,
    ) -> None:
        """Log rule evaluation for audit trail"""
        log = RoutingRuleLog(
            rule_id=rule.id,
            order_id=order.id,
            matched=matched,
            evaluation_time_ms=evaluation_time_ms,
            order_context={
                "status": (
                    order.status.value
                    if hasattr(order.status, "value")
                    else order.status
                ),
                "total": float(order.final_amount) if order.final_amount else 0,
                "item_count": len(order.order_items),
            },
            conditions_evaluated=match_details,
        )

        self.db.add(log)

    # Override Management
    def create_route_override(
        self, override_data: RouteOverrideCreate, created_by_id: int
    ) -> RouteOverride:
        """Create a manual route override"""
        # Check if order exists
        order = self.db.query(Order).filter(Order.id == override_data.order_id).first()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order {override_data.order_id} not found",
            )

        # Remove any existing override
        existing = (
            self.db.query(RouteOverride)
            .filter(RouteOverride.order_id == override_data.order_id)
            .first()
        )
        if existing:
            self.db.delete(existing)

        # Create new override
        override = RouteOverride(
            order_id=override_data.order_id,
            override_type=override_data.override_type,
            target_type=override_data.target_type,
            target_id=override_data.target_id,
            reason=override_data.reason,
            overridden_by=created_by_id,
            expires_at=override_data.expires_at,
        )

        self.db.add(override)
        self.db.commit()
        self.db.refresh(override)

        logger.info(f"Created route override for order {override_data.order_id}")
        return override

    # Testing
    def test_routing_rules(
        self, test_request: RoutingRuleTestRequest
    ) -> RoutingRuleTestResult:
        """Test routing rules with mock order data"""
        # Create mock order from test data
        mock_order = self._create_mock_order(test_request.test_order_data)

        if test_request.rule_id:
            # Test specific rule
            rule = self.get_routing_rule(test_request.rule_id)
            matched, match_details = self._evaluate_rule(rule, mock_order)

            # Determine what actions would execute
            would_execute = []
            if matched:
                for action in rule.actions:
                    would_execute.append(
                        {"type": action.action_type, "config": action.action_config}
                    )

            return RoutingRuleTestResult(
                rule_id=rule.id,
                rule_name=rule.name,
                matched=matched,
                conditions_results=match_details.get("groups", {}),
                would_execute_actions=would_execute,
                routing_target=(
                    {"type": rule.target_type.value, "id": rule.target_id}
                    if matched
                    else None
                ),
            )
        else:
            # Test all rules
            rules = self._get_applicable_rules(test_request.include_all_rules)

            for rule in rules:
                matched, match_details = self._evaluate_rule(rule, mock_order)
                if matched:
                    would_execute = []
                    for action in rule.actions:
                        would_execute.append(
                            {"type": action.action_type, "config": action.action_config}
                        )

                    return RoutingRuleTestResult(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        matched=True,
                        conditions_results=match_details.get("groups", {}),
                        would_execute_actions=would_execute,
                        routing_target={
                            "type": rule.target_type.value,
                            "id": rule.target_id,
                        },
                    )

            return RoutingRuleTestResult(
                matched=False,
                conditions_results=[],
                would_execute_actions=[],
                test_notes=["No rules matched the test order data"],
            )

    def _create_mock_order(self, test_data: Dict[str, Any]) -> Order:
        """Create a mock order object from test data"""
        # This creates an in-memory order object for testing
        # without persisting to database
        order = Order()

        # Set basic fields
        order.id = test_data.get("id", 999999)
        order.status = test_data.get("status", "pending")
        order.final_amount = Decimal(str(test_data.get("total", 0)))
        order.table_no = test_data.get("table_no")
        order.created_at = datetime.utcnow()

        # Mock customer
        if "customer" in test_data:
            customer = Customer()
            for key, value in test_data["customer"].items():
                setattr(customer, key, value)
            order.customer = customer
            order.customer_id = customer.id if hasattr(customer, "id") else 1

        # Mock items
        order.order_items = []
        for item_data in test_data.get("items", []):
            item = OrderItem()
            item.menu_item_id = item_data.get("menu_item_id", 1)
            item.quantity = item_data.get("quantity", 1)
            item.price = Decimal(str(item_data.get("price", 0)))
            order.order_items.append(item)

        return order

    # Staff Capability Management
    def create_staff_capability(
        self, capability_data: StaffCapabilityCreate
    ) -> StaffRoutingCapability:
        """Create a staff routing capability"""
        # Check if staff exists
        staff = (
            self.db.query(StaffMember)
            .filter(StaffMember.id == capability_data.staff_id)
            .first()
        )
        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Staff member {capability_data.staff_id} not found",
            )

        capability = StaffRoutingCapability(**capability_data.dict())
        self.db.add(capability)
        self.db.commit()
        self.db.refresh(capability)

        logger.info(
            f"Created capability for staff {capability_data.staff_id}: {capability_data.capability_type}={capability_data.capability_value}"
        )
        return capability

    def get_staff_capabilities(self, staff_id: int) -> List[StaffRoutingCapability]:
        """Get all capabilities for a staff member"""
        return (
            self.db.query(StaffRoutingCapability)
            .filter(StaffRoutingCapability.staff_id == staff_id)
            .all()
        )

    # Team Management
    def create_team(self, team_data: TeamRoutingConfigCreate) -> TeamRoutingConfig:
        """Create a new routing team"""
        team = TeamRoutingConfig(**team_data.dict())
        self.db.add(team)
        self.db.commit()
        self.db.refresh(team)

        logger.info(f"Created routing team '{team.team_name}'")
        return team

    def detect_rule_conflicts(
        self, rule_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Detect potential conflicts between routing rules"""
        conflicts = []

        # Get all active rules
        rules = (
            self.db.query(OrderRoutingRule)
            .filter(OrderRoutingRule.status == RuleStatus.ACTIVE)
            .all()
        )

        if rule_id:
            # Check conflicts for specific rule
            target_rule = next((r for r in rules if r.id == rule_id), None)
            if not target_rule:
                return conflicts

            for other_rule in rules:
                if other_rule.id == rule_id:
                    continue

                conflict = self._check_rule_conflict(target_rule, other_rule)
                if conflict:
                    conflicts.append(conflict)
        else:
            # Check all pairs of rules
            for i, rule1 in enumerate(rules):
                for rule2 in rules[i + 1 :]:
                    conflict = self._check_rule_conflict(rule1, rule2)
                    if conflict:
                        conflicts.append(conflict)

        return conflicts

    def _check_rule_conflict(
        self, rule1: OrderRoutingRule, rule2: OrderRoutingRule
    ) -> Optional[Dict[str, Any]]:
        """Check if two rules potentially conflict"""
        # Same priority is always a potential conflict
        if rule1.priority == rule2.priority:
            return {
                "type": "priority_conflict",
                "rule1_id": rule1.id,
                "rule1_name": rule1.name,
                "rule2_id": rule2.id,
                "rule2_name": rule2.name,
                "priority": rule1.priority,
                "severity": "high",
            }

        # Check for overlapping conditions with different targets
        if (
            rule1.target_type == rule2.target_type
            and rule1.target_id == rule2.target_id
        ):
            return None  # Same target, no conflict

        # Check if conditions could match same orders
        overlap = self._check_condition_overlap(rule1.conditions, rule2.conditions)
        if overlap:
            return {
                "type": "condition_overlap",
                "rule1_id": rule1.id,
                "rule1_name": rule1.name,
                "rule1_priority": rule1.priority,
                "rule2_id": rule2.id,
                "rule2_name": rule2.name,
                "rule2_priority": rule2.priority,
                "overlap_fields": overlap,
                "severity": "medium",
            }

        return None

    def _check_condition_overlap(
        self,
        conditions1: List[RoutingRuleCondition],
        conditions2: List[RoutingRuleCondition],
    ) -> List[str]:
        """Check if two sets of conditions could match the same orders"""
        overlap_fields = []

        # Group conditions by field path
        fields1 = {c.field_path for c in conditions1}
        fields2 = {c.field_path for c in conditions2}

        # Find common fields
        common_fields = fields1.intersection(fields2)

        for field in common_fields:
            # Get conditions for this field from both rules
            conds1 = [c for c in conditions1 if c.field_path == field]
            conds2 = [c for c in conditions2 if c.field_path == field]

            # Check if conditions could match same values
            for c1 in conds1:
                for c2 in conds2:
                    if self._conditions_could_overlap(c1, c2):
                        overlap_fields.append(field)
                        break

        return overlap_fields

    def _conditions_could_overlap(
        self, cond1: RoutingRuleCondition, cond2: RoutingRuleCondition
    ) -> bool:
        """Check if two conditions on the same field could match same values"""
        # This is a simplified check - in production would need more sophisticated logic

        # If operators are opposites, they don't overlap
        opposite_pairs = [
            (RuleConditionOperator.EQUALS, RuleConditionOperator.NOT_EQUALS),
            (RuleConditionOperator.CONTAINS, RuleConditionOperator.NOT_CONTAINS),
            (RuleConditionOperator.IN, RuleConditionOperator.NOT_IN),
        ]

        for op1, op2 in opposite_pairs:
            if (
                cond1.operator == op1
                and cond2.operator == op2
                and cond1.value == cond2.value
            ) or (
                cond1.operator == op2
                and cond2.operator == op1
                and cond1.value == cond2.value
            ):
                return False

        # For now, assume other combinations could overlap
        return True

    def add_team_member(self, member_data: TeamMemberCreate) -> TeamMember:
        """Add a member to a routing team"""
        # Validate team and staff exist
        team = (
            self.db.query(TeamRoutingConfig)
            .filter(TeamRoutingConfig.id == member_data.team_id)
            .first()
        )
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Team {member_data.team_id} not found",
            )

        staff = (
            self.db.query(StaffMember)
            .filter(StaffMember.id == member_data.staff_id)
            .first()
        )
        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Staff member {member_data.staff_id} not found",
            )

        member = TeamMember(**member_data.dict())
        self.db.add(member)
        self.db.commit()
        self.db.refresh(member)

        logger.info(f"Added staff {member_data.staff_id} to team {team.team_name}")
        return member
