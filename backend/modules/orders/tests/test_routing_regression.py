"""
Regression tests for order routing to ensure existing functionality remains intact.
"""

import pytest
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch

from modules.orders.models.order_models import Order, OrderItem, OrderStatus
from modules.orders.services.order_service import create_order_with_fraud_check
from modules.orders.models.routing_models import OrderRoutingRule, RuleStatus
from modules.kds.models import KDSStation, KDSOrderItem
from core.menu_models import MenuItem, MenuCategory


@pytest.fixture
def mock_kds_routing(monkeypatch):
    """Mock KDS routing service."""
    mock_service = Mock()
    mock_service.route_order_to_stations = Mock(
        return_value=[Mock(station_id=1, item_id=1), Mock(station_id=2, item_id=2)]
    )

    def mock_kds_constructor(db):
        return mock_service

    monkeypatch.setattr(
        "modules.kds.services.kds_order_routing_service.KDSOrderRoutingService",
        mock_kds_constructor,
    )
    return mock_service


@pytest.fixture
def sample_menu_items(db_session: Session):
    """Create sample menu items for testing."""
    category = MenuCategory(name="Test Category", description="Test")
    db_session.add(category)
    db_session.flush()

    items = []
    for i in range(3):
        item = MenuItem(
            name=f"Test Item {i+1}",
            category_id=category.id,
            price=Decimal(f"{10 + i}.99"),
            is_available=True,
        )
        items.append(item)

    db_session.add_all(items)
    db_session.commit()
    return items


class TestOrderCreationRegression:
    """Test that order creation still works with routing rules."""

    @pytest.mark.asyncio
    async def test_order_reaches_kds_when_no_rules_exist(
        self, db_session, mock_kds_routing, sample_menu_items
    ):
        """Verify orders reach KDS when no routing rules exist."""
        # Ensure no routing rules exist
        assert db_session.query(OrderRoutingRule).count() == 0

        # Create order
        order_data = {
            "customer_id": 1,
            "table_no": 5,
            "status": OrderStatus.PENDING.value,
            "total_amount": Decimal("29.97"),
            "final_amount": Decimal("29.97"),
        }

        order = await create_order_with_fraud_check(
            db_session, order_data, perform_fraud_validation=False
        )

        # Verify order was created
        assert order.id is not None
        assert order.status == OrderStatus.PENDING.value

        # Verify KDS routing was called
        mock_kds_routing.route_order_to_stations.assert_called_once_with(order.id)

    @pytest.mark.asyncio
    async def test_order_reaches_kds_when_no_rules_match(
        self, db_session, mock_kds_routing, sample_menu_items
    ):
        """Verify fallback to KDS when no routing rules match."""
        # Create a rule that won't match
        rule = OrderRoutingRule(
            name="High Value Only",
            priority=100,
            status=RuleStatus.ACTIVE,
            target_type="staff",
            target_id=1,
            created_by=1,
        )
        db_session.add(rule)
        db_session.commit()

        # Add condition that won't match (order must be > $1000)
        from modules.orders.models.routing_models import (
            RoutingRuleCondition,
            RuleConditionOperator,
        )

        condition = RoutingRuleCondition(
            rule_id=rule.id,
            field_path="order.total",
            operator=RuleConditionOperator.GREATER_THAN,
            value=1000.0,
        )
        db_session.add(condition)
        db_session.commit()

        # Create order with low value
        order_data = {
            "customer_id": 1,
            "table_no": 5,
            "status": OrderStatus.PENDING.value,
            "total_amount": Decimal("29.97"),
            "final_amount": Decimal("29.97"),
        }

        order = await create_order_with_fraud_check(
            db_session, order_data, perform_fraud_validation=False
        )

        # Verify KDS routing was still called (fallback)
        mock_kds_routing.route_order_to_stations.assert_called_once_with(order.id)

    @pytest.mark.asyncio
    async def test_order_creation_continues_if_routing_fails(
        self, db_session, mock_kds_routing, sample_menu_items
    ):
        """Verify order creation doesn't fail if routing errors occur."""
        # Make routing evaluation fail
        with patch(
            "modules.orders.services.routing_rule_service.RoutingRuleService.evaluate_order_routing"
        ) as mock_eval:
            mock_eval.side_effect = Exception("Routing evaluation failed")

            order_data = {
                "customer_id": 1,
                "table_no": 5,
                "status": OrderStatus.PENDING.value,
                "total_amount": Decimal("29.97"),
                "final_amount": Decimal("29.97"),
            }

            # Order creation should still succeed
            order = await create_order_with_fraud_check(
                db_session, order_data, perform_fraud_validation=False
            )

            assert order.id is not None
            assert order.status == OrderStatus.PENDING.value

            # Verify fallback KDS routing was attempted
            mock_kds_routing.route_order_to_stations.assert_called()

    @pytest.mark.asyncio
    async def test_routing_decision_logged(
        self, db_session, mock_kds_routing, sample_menu_items, caplog
    ):
        """Verify routing decisions are properly logged."""
        order_data = {
            "customer_id": 1,
            "table_no": 5,
            "status": OrderStatus.PENDING.value,
            "total_amount": Decimal("29.97"),
            "final_amount": Decimal("29.97"),
        }

        with caplog.at_level("INFO"):
            order = await create_order_with_fraud_check(
                db_session, order_data, perform_fraud_validation=False
            )

        # Check for routing decision log
        assert any("routing decision" in record.message for record in caplog.records)


class TestPriorityConflicts:
    """Test priority conflict detection and resolution."""

    def test_priority_conflict_detection(self, db_session):
        """Test that priority conflicts are properly detected."""
        from modules.orders.services.routing_rule_service import RoutingRuleService
        from modules.orders.models.routing_models import RoutingRuleAction

        service = RoutingRuleService(db_session)

        # Create two rules with same priority
        rule1 = OrderRoutingRule(
            name="Rule 1",
            priority=50,
            status=RuleStatus.ACTIVE,
            target_type="station",
            target_id=1,
            created_by=1,
        )
        rule2 = OrderRoutingRule(
            name="Rule 2",
            priority=50,  # Same priority
            status=RuleStatus.ACTIVE,
            target_type="station",
            target_id=2,
            created_by=1,
        )
        db_session.add_all([rule1, rule2])
        db_session.commit()

        # Add minimal actions
        for rule in [rule1, rule2]:
            action = RoutingRuleAction(
                rule_id=rule.id,
                action_type="route",
                action_config={},
                execution_order=0,
            )
            db_session.add(action)
        db_session.commit()

        # Detect conflicts
        conflicts = service.detect_rule_conflicts()

        # Should find priority conflict
        priority_conflicts = [c for c in conflicts if c["type"] == "priority_conflict"]
        assert len(priority_conflicts) == 1
        assert priority_conflicts[0]["priority"] == 50
        assert priority_conflicts[0]["severity"] == "high"

    def test_first_rule_wins_behavior(self, db_session):
        """Test that first rule wins when priorities conflict."""
        from modules.orders.services.routing_rule_service import RoutingRuleService
        from modules.orders.schemas.routing_schemas import RouteEvaluationRequest
        from modules.orders.models.routing_models import (
            RoutingRuleCondition,
            RoutingRuleAction,
            RuleConditionOperator,
        )

        service = RoutingRuleService(db_session)

        # Create order
        order = Order(
            customer_id=1,
            table_no=5,
            status=OrderStatus.PENDING.value,
            total_amount=Decimal("50.00"),
            final_amount=Decimal("50.00"),
        )
        db_session.add(order)
        db_session.flush()

        # Create two conflicting rules
        rules = []
        for i in range(2):
            rule = OrderRoutingRule(
                name=f"Conflicting Rule {i+1}",
                priority=100,  # Same priority
                status=RuleStatus.ACTIVE,
                target_type="station",
                target_id=i + 1,
                created_by=1,
            )
            db_session.add(rule)
            db_session.flush()

            # Add matching condition
            condition = RoutingRuleCondition(
                rule_id=rule.id,
                field_path="order.total",
                operator=RuleConditionOperator.GREATER_THAN,
                value=10.0,
            )
            action = RoutingRuleAction(
                rule_id=rule.id,
                action_type="route",
                action_config={},
                execution_order=0,
            )
            db_session.add_all([condition, action])
            rules.append(rule)

        db_session.commit()

        # Evaluate routing
        request = RouteEvaluationRequest(order_id=order.id, test_mode=True)
        result = service.evaluate_order_routing(request)

        # Should use first rule (by ID)
        assert result.routing_decision["rule_id"] == min(r.id for r in rules)
        assert "conflicts" in result.routing_decision
        assert result.routing_decision["conflicts"]["detected"] == True
        assert len(result.routing_decision["conflicts"]["conflicting_rules"]) == 2


class TestTeamRoutingEdgeCases:
    """Test team routing edge cases."""

    def test_no_active_team_members(self, db_session):
        """Test routing to team with no active members."""
        from modules.orders.services.routing_rule_service import RoutingRuleService
        from modules.orders.models.routing_models import TeamRoutingConfig

        service = RoutingRuleService(db_session)

        # Create team with no members
        team = TeamRoutingConfig(
            team_name="Empty Team", routing_strategy="round_robin", is_active=True
        )
        db_session.add(team)
        db_session.commit()

        # Create order
        order = Order(
            customer_id=1,
            status=OrderStatus.PENDING.value,
            total_amount=Decimal("50.00"),
            final_amount=Decimal("50.00"),
        )
        db_session.add(order)
        db_session.commit()

        # Try to route to empty team
        service._route_to_team(order, team.id)

        # Should handle gracefully (check logs for warning)
        # Order should remain unassigned

    def test_load_balancing_strategies(self, db_session, sample_staff):
        """Test different team load balancing strategies."""
        from modules.orders.services.routing_rule_service import RoutingRuleService
        from modules.orders.models.routing_models import TeamRoutingConfig, TeamMember

        service = RoutingRuleService(db_session)
        staff1, staff2 = sample_staff

        # Create team with least_loaded strategy
        team = TeamRoutingConfig(
            team_name="Load Balanced Team",
            routing_strategy="least_loaded",
            is_active=True,
        )
        db_session.add(team)
        db_session.flush()

        # Add members with different loads
        member1 = TeamMember(
            team_id=team.id,
            staff_id=staff1.id,
            is_active=True,
            current_load=5,  # Higher load
        )
        member2 = TeamMember(
            team_id=team.id,
            staff_id=staff2.id,
            is_active=True,
            current_load=2,  # Lower load
        )
        db_session.add_all([member1, member2])
        db_session.commit()

        # Create order
        order = Order(
            customer_id=1,
            status=OrderStatus.PENDING.value,
            total_amount=Decimal("50.00"),
            final_amount=Decimal("50.00"),
        )
        db_session.add(order)
        db_session.commit()

        # Route to team
        service._route_to_team(order, team.id)

        # Should route to member with lower load
        db_session.refresh(member2)
        assert member2.current_load == 3  # Load increased by 1

    def test_inactive_team_members_excluded(self, db_session, sample_staff):
        """Test that inactive team members are excluded from routing."""
        from modules.orders.services.routing_rule_service import RoutingRuleService
        from modules.orders.models.routing_models import TeamRoutingConfig, TeamMember

        service = RoutingRuleService(db_session)
        staff1, staff2 = sample_staff

        # Create team
        team = TeamRoutingConfig(
            team_name="Mixed Team", routing_strategy="round_robin", is_active=True
        )
        db_session.add(team)
        db_session.flush()

        # Add one active and one inactive member
        member1 = TeamMember(
            team_id=team.id, staff_id=staff1.id, is_active=True, current_load=0
        )
        member2 = TeamMember(
            team_id=team.id,
            staff_id=staff2.id,
            is_active=False,  # Inactive
            current_load=0,
        )
        db_session.add_all([member1, member2])
        db_session.commit()

        # Create order
        order = Order(
            customer_id=1,
            status=OrderStatus.PENDING.value,
            total_amount=Decimal("50.00"),
            final_amount=Decimal("50.00"),
        )
        db_session.add(order)
        db_session.commit()

        # Route to team
        service._route_to_team(order, team.id)

        # Should only route to active member
        db_session.refresh(member1)
        db_session.refresh(member2)
        assert member1.current_load == 1
        assert member2.current_load == 0  # Unchanged


class TestAPIContractValidation:
    """Test that API contracts match the documented schemas."""

    def test_routing_rule_create_schema(self):
        """Validate RoutingRuleCreate schema matches documentation."""
        from modules.orders.schemas.routing_schemas import RoutingRuleCreate

        # Test valid payload from documentation
        payload = {
            "name": "High Value Orders",
            "description": "Route orders over $100 to senior staff",
            "priority": 100,
            "status": "active",
            "target_type": "staff",
            "target_id": 123,
            "conditions": [
                {
                    "field_path": "order.total",
                    "operator": "greater_than",
                    "value": 100.0,
                    "condition_group": 0,
                }
            ],
            "actions": [
                {
                    "action_type": "route",
                    "action_config": {"priority": "high"},
                    "execution_order": 0,
                }
            ],
        }

        # Should validate without errors
        rule = RoutingRuleCreate(**payload)
        assert rule.name == "High Value Orders"
        assert rule.priority == 100
        assert len(rule.conditions) == 1
        assert len(rule.actions) == 1

    def test_route_evaluation_request_schema(self):
        """Validate RouteEvaluationRequest schema."""
        from modules.orders.schemas.routing_schemas import RouteEvaluationRequest

        payload = {
            "order_id": 12345,
            "force_evaluation": False,
            "test_mode": False,
            "include_inactive": False,
        }

        request = RouteEvaluationRequest(**payload)
        assert request.order_id == 12345
        assert request.test_mode == False

    def test_team_config_schema(self):
        """Validate TeamRoutingConfigCreate schema."""
        from modules.orders.schemas.routing_schemas import TeamRoutingConfigCreate

        payload = {
            "team_name": "Kitchen Brigade",
            "description": "Main kitchen team",
            "routing_strategy": "least_loaded",
            "max_concurrent_orders": 20,
            "specializations": ["grill", "saute", "salad"],
            "load_balancing_config": {"max_per_member": 5, "rebalance_interval": 300},
        }

        team = TeamRoutingConfigCreate(**payload)
        assert team.team_name == "Kitchen Brigade"
        assert team.routing_strategy == "least_loaded"
        assert len(team.specializations) == 3

    def test_conflict_detection_response(self, client, db_session):
        """Test conflict detection endpoint response format."""
        # This would require setting up FastAPI test client
        # Placeholder for integration test
        pass


class TestRuleTestingEndpoint:
    """Test the rule testing functionality."""

    def test_rule_test_with_mock_data(self, db_session):
        """Test rule evaluation with mock order data."""
        from modules.orders.services.routing_rule_service import RoutingRuleService
        from modules.orders.schemas.routing_schemas import RoutingRuleTestRequest
        from modules.orders.models.routing_models import (
            RoutingRuleCondition,
            RoutingRuleAction,
            RuleConditionOperator,
        )

        service = RoutingRuleService(db_session)

        # Create test rule
        rule = OrderRoutingRule(
            name="Test Rule",
            priority=100,
            status=RuleStatus.ACTIVE,
            target_type="station",
            target_id=1,
            created_by=1,
        )
        db_session.add(rule)
        db_session.flush()

        condition = RoutingRuleCondition(
            rule_id=rule.id,
            field_path="order.total",
            operator=RuleConditionOperator.GREATER_THAN,
            value=50.0,
        )
        action = RoutingRuleAction(
            rule_id=rule.id,
            action_type="route",
            action_config={"station": "main"},
            execution_order=0,
        )
        db_session.add_all([condition, action])
        db_session.commit()

        # Test with matching mock data
        test_request = RoutingRuleTestRequest(
            rule_id=rule.id,
            test_order_data={
                "total": 75.00,
                "status": "pending",
                "table_no": 5,
                "customer": {"vip_status": False},
                "items": [{"menu_item_id": 1, "quantity": 2, "price": 25.00}],
            },
        )

        result = service.test_routing_rules(test_request)

        assert result.matched == True
        assert result.rule_id == rule.id
        assert len(result.would_execute_actions) == 1
        assert result.would_execute_actions[0]["type"] == "route"
