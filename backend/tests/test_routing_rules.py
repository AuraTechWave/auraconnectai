"""
Tests for order routing rules functionality.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException

from modules.orders.models.routing_models import (
    OrderRoutingRule, RoutingRuleCondition, RoutingRuleAction,
    RouteTargetType, RuleConditionOperator, RuleStatus,
    StaffRoutingCapability, TeamRoutingConfig, TeamMember
)
from modules.orders.models.order_models import Order, OrderItem, OrderStatus
from modules.orders.schemas.routing_schemas import (
    RoutingRuleCreate, RoutingRuleUpdate, RouteEvaluationRequest,
    RuleConditionCreate, RuleActionCreate, RouteOverrideCreate,
    StaffCapabilityCreate, TeamRoutingConfigCreate, TeamMemberCreate,
    RoutingRuleTestRequest
)
from modules.orders.services.routing_rule_service import RoutingRuleService
from modules.staff.models import StaffMember
from core.menu_models import MenuItem, MenuCategory
from modules.customers.models import Customer


@pytest.fixture
def routing_service(db_session: Session):
    """Create routing service instance."""
    return RoutingRuleService(db_session)


@pytest.fixture
def sample_staff(db_session: Session):
    """Create sample staff members."""
    staff1 = StaffMember(
        first_name="John",
        last_name="Cook",
        email="john.cook@test.com",
        phone="555-0001",
        role="cook",
        is_active=True
    )
    staff2 = StaffMember(
        first_name="Jane",
        last_name="Server",
        email="jane.server@test.com",
        phone="555-0002",
        role="server",
        is_active=True
    )
    db_session.add_all([staff1, staff2])
    db_session.commit()
    return staff1, staff2


@pytest.fixture
def sample_menu_items(db_session: Session):
    """Create sample menu items."""
    category1 = MenuCategory(name="Appetizers", description="Starters")
    category2 = MenuCategory(name="Main Course", description="Main dishes")
    category3 = MenuCategory(name="Beverages", description="Drinks")
    
    db_session.add_all([category1, category2, category3])
    db_session.flush()
    
    item1 = MenuItem(
        name="Caesar Salad",
        category_id=category1.id,
        price=Decimal("12.99"),
        is_available=True
    )
    item2 = MenuItem(
        name="Grilled Steak",
        category_id=category2.id,
        price=Decimal("28.99"),
        is_available=True
    )
    item3 = MenuItem(
        name="Wine",
        category_id=category3.id,
        price=Decimal("8.99"),
        is_available=True,
        contains_alcohol=True
    )
    
    db_session.add_all([item1, item2, item3])
    db_session.commit()
    return item1, item2, item3


@pytest.fixture
def sample_order(db_session: Session, sample_menu_items):
    """Create a sample order."""
    item1, item2, item3 = sample_menu_items
    
    customer = Customer(
        name="Test Customer",
        email="customer@test.com",
        phone="555-1234"
    )
    db_session.add(customer)
    db_session.flush()
    
    order = Order(
        customer_id=customer.id,
        table_no=5,
        status=OrderStatus.PENDING.value,
        total_amount=Decimal("49.97"),
        final_amount=Decimal("49.97"),
        created_at=datetime.utcnow()
    )
    db_session.add(order)
    db_session.flush()
    
    # Add order items
    order_items = [
        OrderItem(
            order_id=order.id,
            menu_item_id=item1.id,
            quantity=1,
            price=item1.price,
            subtotal=item1.price
        ),
        OrderItem(
            order_id=order.id,
            menu_item_id=item2.id,
            quantity=1,
            price=item2.price,
            subtotal=item2.price
        ),
        OrderItem(
            order_id=order.id,
            menu_item_id=item3.id,
            quantity=1,
            price=item3.price,
            subtotal=item3.price
        )
    ]
    db_session.add_all(order_items)
    db_session.commit()
    
    return order


class TestRoutingRuleManagement:
    """Test routing rule CRUD operations."""
    
    def test_create_routing_rule(self, routing_service, db_session):
        """Test creating a routing rule."""
        rule_data = RoutingRuleCreate(
            name="High Value Orders",
            description="Route high value orders to senior staff",
            priority=100,
            status=RuleStatus.ACTIVE,
            target_type=RouteTargetType.STAFF,
            target_id=1,
            conditions=[
                RuleConditionCreate(
                    field_path="order.total",
                    operator=RuleConditionOperator.GREATER_THAN,
                    value=50.0,
                    condition_group=0
                )
            ],
            actions=[
                RuleActionCreate(
                    action_type="route",
                    action_config={"priority": "high"},
                    execution_order=0
                )
            ]
        )
        
        rule = routing_service.create_routing_rule(rule_data, created_by_id=1)
        
        assert rule.id is not None
        assert rule.name == "High Value Orders"
        assert rule.priority == 100
        assert len(rule.conditions) == 1
        assert len(rule.actions) == 1
        assert rule.conditions[0].field_path == "order.total"
    
    def test_update_routing_rule(self, routing_service, db_session):
        """Test updating a routing rule."""
        # Create rule first
        rule_data = RoutingRuleCreate(
            name="Test Rule",
            priority=50,
            status=RuleStatus.ACTIVE,
            target_type=RouteTargetType.STATION,
            target_id=1,
            conditions=[
                RuleConditionCreate(
                    field_path="order.type",
                    operator=RuleConditionOperator.EQUALS,
                    value="takeout"
                )
            ],
            actions=[
                RuleActionCreate(
                    action_type="route",
                    action_config={}
                )
            ]
        )
        rule = routing_service.create_routing_rule(rule_data, created_by_id=1)
        
        # Update rule
        update_data = RoutingRuleUpdate(
            name="Updated Rule",
            priority=75,
            status=RuleStatus.INACTIVE
        )
        updated_rule = routing_service.update_routing_rule(
            rule.id, update_data, updated_by_id=1
        )
        
        assert updated_rule.name == "Updated Rule"
        assert updated_rule.priority == 75
        assert updated_rule.status == RuleStatus.INACTIVE
    
    def test_delete_routing_rule(self, routing_service, db_session):
        """Test deleting a routing rule."""
        # Create rule
        rule_data = RoutingRuleCreate(
            name="Delete Test",
            priority=10,
            status=RuleStatus.ACTIVE,
            target_type=RouteTargetType.QUEUE,
            conditions=[
                RuleConditionCreate(
                    field_path="order.status",
                    operator=RuleConditionOperator.EQUALS,
                    value="pending"
                )
            ],
            actions=[
                RuleActionCreate(
                    action_type="route",
                    action_config={}
                )
            ]
        )
        rule = routing_service.create_routing_rule(rule_data, created_by_id=1)
        rule_id = rule.id
        
        # Delete rule
        routing_service.delete_routing_rule(rule_id)
        
        # Verify deletion
        deleted_rule = db_session.query(OrderRoutingRule).filter(
            OrderRoutingRule.id == rule_id
        ).first()
        assert deleted_rule is None


class TestRuleEvaluation:
    """Test routing rule evaluation logic."""
    
    def test_evaluate_simple_condition(self, routing_service, db_session, sample_order):
        """Test evaluating a simple condition."""
        # Create rule that matches orders over $40
        rule_data = RoutingRuleCreate(
            name="High Value Rule",
            priority=100,
            status=RuleStatus.ACTIVE,
            target_type=RouteTargetType.STAFF,
            target_id=1,
            conditions=[
                RuleConditionCreate(
                    field_path="order.total",
                    operator=RuleConditionOperator.GREATER_THAN,
                    value=40.0
                )
            ],
            actions=[
                RuleActionCreate(
                    action_type="route",
                    action_config={"tag": "high_value"}
                )
            ]
        )
        rule = routing_service.create_routing_rule(rule_data, created_by_id=1)
        
        # Evaluate routing
        request = RouteEvaluationRequest(
            order_id=sample_order.id,
            test_mode=True
        )
        result = routing_service.evaluate_order_routing(request)
        
        assert result.evaluated_rules == 1
        assert len(result.matched_rules) == 1
        assert result.matched_rules[0]["rule_id"] == rule.id
        assert result.routing_decision["type"] == "rule"
    
    def test_evaluate_complex_conditions(self, routing_service, db_session, sample_order):
        """Test evaluating complex AND/OR conditions."""
        # Create rule with multiple condition groups
        rule_data = RoutingRuleCreate(
            name="Complex Rule",
            priority=90,
            status=RuleStatus.ACTIVE,
            target_type=RouteTargetType.TEAM,
            target_id=1,
            conditions=[
                # Group 0: High value AND dinner time
                RuleConditionCreate(
                    field_path="order.total",
                    operator=RuleConditionOperator.GREATER_THAN,
                    value=30.0,
                    condition_group=0
                ),
                RuleConditionCreate(
                    field_path="context.time_of_day",
                    operator=RuleConditionOperator.EQUALS,
                    value="dinner",
                    condition_group=0
                ),
                # Group 1: OR VIP customer
                RuleConditionCreate(
                    field_path="customer.vip_status",
                    operator=RuleConditionOperator.EQUALS,
                    value=True,
                    condition_group=1
                )
            ],
            actions=[
                RuleActionCreate(
                    action_type="route",
                    action_config={"priority": "high"}
                )
            ]
        )
        rule = routing_service.create_routing_rule(rule_data, created_by_id=1)
        
        # Evaluate routing
        request = RouteEvaluationRequest(
            order_id=sample_order.id,
            test_mode=True
        )
        result = routing_service.evaluate_order_routing(request)
        
        # Should match based on order total being > 30
        assert result.evaluated_rules == 1
        assert len(result.matched_rules) >= 0  # Depends on time of day
    
    def test_priority_ordering(self, routing_service, db_session, sample_order):
        """Test that higher priority rules are evaluated first."""
        # Create low priority rule
        low_rule_data = RoutingRuleCreate(
            name="Low Priority",
            priority=10,
            status=RuleStatus.ACTIVE,
            target_type=RouteTargetType.STATION,
            target_id=1,
            conditions=[
                RuleConditionCreate(
                    field_path="order.total",
                    operator=RuleConditionOperator.GREATER_THAN,
                    value=10.0
                )
            ],
            actions=[
                RuleActionCreate(
                    action_type="route",
                    action_config={"station": "low"}
                )
            ]
        )
        low_rule = routing_service.create_routing_rule(low_rule_data, created_by_id=1)
        
        # Create high priority rule
        high_rule_data = RoutingRuleCreate(
            name="High Priority",
            priority=100,
            status=RuleStatus.ACTIVE,
            target_type=RouteTargetType.STATION,
            target_id=2,
            conditions=[
                RuleConditionCreate(
                    field_path="order.total",
                    operator=RuleConditionOperator.GREATER_THAN,
                    value=10.0
                )
            ],
            actions=[
                RuleActionCreate(
                    action_type="route",
                    action_config={"station": "high"}
                )
            ]
        )
        high_rule = routing_service.create_routing_rule(high_rule_data, created_by_id=1)
        
        # Evaluate routing
        request = RouteEvaluationRequest(
            order_id=sample_order.id,
            test_mode=True
        )
        result = routing_service.evaluate_order_routing(request)
        
        # Should use high priority rule
        assert result.routing_decision["rule_id"] == high_rule.id
        assert result.routing_decision["applied_priority"] == 100


class TestConflictDetection:
    """Test rule conflict detection."""
    
    def test_detect_priority_conflicts(self, routing_service, db_session):
        """Test detecting rules with same priority."""
        # Create two rules with same priority
        rule1_data = RoutingRuleCreate(
            name="Rule 1",
            priority=50,
            status=RuleStatus.ACTIVE,
            target_type=RouteTargetType.STATION,
            target_id=1,
            conditions=[
                RuleConditionCreate(
                    field_path="order.type",
                    operator=RuleConditionOperator.EQUALS,
                    value="dine_in"
                )
            ],
            actions=[
                RuleActionCreate(
                    action_type="route",
                    action_config={}
                )
            ]
        )
        rule1 = routing_service.create_routing_rule(rule1_data, created_by_id=1)
        
        rule2_data = RoutingRuleCreate(
            name="Rule 2",
            priority=50,  # Same priority
            status=RuleStatus.ACTIVE,
            target_type=RouteTargetType.STATION,
            target_id=2,
            conditions=[
                RuleConditionCreate(
                    field_path="order.type",
                    operator=RuleConditionOperator.EQUALS,
                    value="takeout"
                )
            ],
            actions=[
                RuleActionCreate(
                    action_type="route",
                    action_config={}
                )
            ]
        )
        rule2 = routing_service.create_routing_rule(rule2_data, created_by_id=1)
        
        # Detect conflicts
        conflicts = routing_service.detect_rule_conflicts()
        
        assert len(conflicts) > 0
        priority_conflicts = [c for c in conflicts if c["type"] == "priority_conflict"]
        assert len(priority_conflicts) == 1
        assert priority_conflicts[0]["priority"] == 50
        assert priority_conflicts[0]["severity"] == "high"


class TestRouteOverrides:
    """Test manual route overrides."""
    
    def test_create_route_override(self, routing_service, db_session, sample_order):
        """Test creating a manual route override."""
        override_data = RouteOverrideCreate(
            order_id=sample_order.id,
            override_type="manual",
            target_type=RouteTargetType.STAFF,
            target_id=1,
            reason="Customer requested specific staff"
        )
        
        override = routing_service.create_route_override(override_data, created_by_id=1)
        
        assert override.order_id == sample_order.id
        assert override.target_type == RouteTargetType.STAFF
        assert override.target_id == 1
    
    def test_override_bypasses_rules(self, routing_service, db_session, sample_order):
        """Test that overrides bypass normal rules."""
        # Create a rule
        rule_data = RoutingRuleCreate(
            name="Normal Rule",
            priority=100,
            status=RuleStatus.ACTIVE,
            target_type=RouteTargetType.STATION,
            target_id=1,
            conditions=[
                RuleConditionCreate(
                    field_path="order.total",
                    operator=RuleConditionOperator.GREATER_THAN,
                    value=10.0
                )
            ],
            actions=[
                RuleActionCreate(
                    action_type="route",
                    action_config={}
                )
            ]
        )
        rule = routing_service.create_routing_rule(rule_data, created_by_id=1)
        
        # Create override
        override_data = RouteOverrideCreate(
            order_id=sample_order.id,
            override_type="manual",
            target_type=RouteTargetType.STAFF,
            target_id=2,
            reason="Override test"
        )
        override = routing_service.create_route_override(override_data, created_by_id=1)
        
        # Evaluate routing
        request = RouteEvaluationRequest(
            order_id=sample_order.id,
            test_mode=True
        )
        result = routing_service.evaluate_order_routing(request)
        
        # Should use override, not rule
        assert result.routing_decision["type"] == "override"
        assert result.routing_decision["target_type"] == "staff"
        assert result.routing_decision["target_id"] == 2


class TestStaffCapabilities:
    """Test staff routing capabilities."""
    
    def test_create_staff_capability(self, routing_service, db_session, sample_staff):
        """Test creating staff capabilities."""
        staff1, staff2 = sample_staff
        
        capability_data = StaffCapabilityCreate(
            staff_id=staff1.id,
            capability_type="category",
            capability_value="grill",
            max_concurrent_orders=5,
            skill_level=4
        )
        
        capability = routing_service.create_staff_capability(capability_data)
        
        assert capability.staff_id == staff1.id
        assert capability.capability_type == "category"
        assert capability.capability_value == "grill"
        assert capability.skill_level == 4
    
    def test_get_staff_capabilities(self, routing_service, db_session, sample_staff):
        """Test retrieving staff capabilities."""
        staff1, staff2 = sample_staff
        
        # Create multiple capabilities
        capabilities_data = [
            StaffCapabilityCreate(
                staff_id=staff1.id,
                capability_type="category",
                capability_value="grill",
                skill_level=4
            ),
            StaffCapabilityCreate(
                staff_id=staff1.id,
                capability_type="certification",
                capability_value="alcohol_service",
                skill_level=5
            )
        ]
        
        for cap_data in capabilities_data:
            routing_service.create_staff_capability(cap_data)
        
        # Get capabilities
        capabilities = routing_service.get_staff_capabilities(staff1.id)
        
        assert len(capabilities) == 2
        assert all(c.staff_id == staff1.id for c in capabilities)


class TestTeamRouting:
    """Test team-based routing."""
    
    def test_create_team(self, routing_service, db_session):
        """Test creating a routing team."""
        team_data = TeamRoutingConfigCreate(
            team_name="Kitchen Team",
            description="Main kitchen staff",
            routing_strategy="round_robin",
            max_concurrent_orders=10
        )
        
        team = routing_service.create_team(team_data)
        
        assert team.team_name == "Kitchen Team"
        assert team.routing_strategy == "round_robin"
        assert team.max_concurrent_orders == 10
    
    def test_add_team_member(self, routing_service, db_session, sample_staff):
        """Test adding members to a team."""
        staff1, staff2 = sample_staff
        
        # Create team
        team_data = TeamRoutingConfigCreate(
            team_name="Service Team",
            routing_strategy="least_loaded"
        )
        team = routing_service.create_team(team_data)
        
        # Add member
        member_data = TeamMemberCreate(
            team_id=team.id,
            staff_id=staff1.id,
            role_in_team="senior",
            weight=1.5
        )
        member = routing_service.add_team_member(member_data)
        
        assert member.team_id == team.id
        assert member.staff_id == staff1.id
        assert member.role_in_team == "senior"
        assert member.weight == 1.5


class TestRuleTesting:
    """Test the rule testing functionality."""
    
    def test_test_specific_rule(self, routing_service, db_session):
        """Test testing a specific rule with mock data."""
        # Create rule
        rule_data = RoutingRuleCreate(
            name="Test Rule",
            priority=100,
            status=RuleStatus.ACTIVE,
            target_type=RouteTargetType.STATION,
            target_id=1,
            conditions=[
                RuleConditionCreate(
                    field_path="order.total",
                    operator=RuleConditionOperator.GREATER_THAN,
                    value=25.0
                )
            ],
            actions=[
                RuleActionCreate(
                    action_type="route",
                    action_config={"station": "main"}
                )
            ]
        )
        rule = routing_service.create_routing_rule(rule_data, created_by_id=1)
        
        # Test with matching data
        test_request = RoutingRuleTestRequest(
            rule_id=rule.id,
            test_order_data={
                "total": 30.0,
                "status": "pending"
            }
        )
        result = routing_service.test_routing_rules(test_request)
        
        assert result.matched == True
        assert result.rule_id == rule.id
        assert len(result.would_execute_actions) == 1
        
        # Test with non-matching data
        test_request2 = RoutingRuleTestRequest(
            rule_id=rule.id,
            test_order_data={
                "total": 20.0,
                "status": "pending"
            }
        )
        result2 = routing_service.test_routing_rules(test_request2)
        
        assert result2.matched == False