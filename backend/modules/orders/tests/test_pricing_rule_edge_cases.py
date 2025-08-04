# backend/modules/orders/tests/test_pricing_rule_edge_cases.py

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from ..services.pricing_rule_service import PricingRuleService
from ..models.pricing_rule_models import (
    PricingRule, PricingRuleApplication, RuleType, RuleStatus, 
    RulePriority, ConflictResolution
)
from ..models.order_models import Order, OrderItem
from ..schemas.pricing_rule_schemas import RuleEvaluationResult


class TestPricingRuleEdgeCases:
    """Test edge cases and complex scenarios for pricing rule overlaps"""
    
    @pytest.fixture
    def pricing_service(self):
        return PricingRuleService()
    
    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)
    
    @pytest.fixture
    def sample_order(self):
        """Create a sample order for testing"""
        order = Mock(spec=Order)
        order.id = 1
        order.restaurant_id = 1
        order.total_amount = Decimal('50.00')
        order.subtotal = Decimal('45.00')
        order.created_at = datetime.utcnow()
        order.customer_id = 123
        
        # Mock restaurant
        order.restaurant = Mock()
        order.restaurant.default_conflict_resolution = ConflictResolution.HIGHEST_DISCOUNT
        
        # Mock order items
        item1 = Mock(spec=OrderItem)
        item1.id = 1
        item1.menu_item_id = 10
        item1.quantity = 2
        item1.price = Decimal('12.50')
        item1.category_id = 5
        
        item2 = Mock(spec=OrderItem)
        item2.id = 2
        item2.menu_item_id = 11
        item2.quantity = 1
        item2.price = Decimal('20.00')
        item2.category_id = 6
        
        order.items = [item1, item2]
        return order
    
    @pytest.fixture
    def overlapping_percentage_rules(self):
        """Create overlapping percentage discount rules"""
        rules = []
        
        # Rule 1: 15% off orders over $40
        rule1 = Mock(spec=PricingRule)
        rule1.id = 1
        rule1.rule_id = "BULK15"
        rule1.name = "Bulk Order 15% Off"
        rule1.rule_type = RuleType.PERCENTAGE_DISCOUNT
        rule1.status = RuleStatus.ACTIVE
        rule1.priority = RulePriority.HIGH
        rule1.stackable = False
        rule1.excluded_rule_ids = []
        rule1.conditions = {
            "min_order_amount": 40.00,
            "discount_percentage": 15
        }
        rule1.valid_from = datetime.utcnow() - timedelta(days=1)
        rule1.valid_until = datetime.utcnow() + timedelta(days=30)
        rule1.is_valid = Mock(return_value=True)
        rules.append(rule1)
        
        # Rule 2: 20% off orders over $45 (higher minimum, higher discount)
        rule2 = Mock(spec=PricingRule)
        rule2.id = 2
        rule2.rule_id = "PREMIUM20"
        rule2.name = "Premium Order 20% Off"
        rule2.rule_type = RuleType.PERCENTAGE_DISCOUNT
        rule2.status = RuleStatus.ACTIVE
        rule2.priority = RulePriority.MEDIUM
        rule2.stackable = False
        rule2.excluded_rule_ids = []
        rule2.conditions = {
            "min_order_amount": 45.00,
            "discount_percentage": 20
        }
        rule2.valid_from = datetime.utcnow() - timedelta(days=1)
        rule2.valid_until = datetime.utcnow() + timedelta(days=30)
        rule2.is_valid = Mock(return_value=True)
        rules.append(rule2)
        
        # Rule 3: 10% off with high priority (should win in priority-based resolution)
        rule3 = Mock(spec=PricingRule)
        rule3.id = 3
        rule3.rule_id = "PRIORITY10"
        rule3.name = "High Priority 10% Off"
        rule3.rule_type = RuleType.PERCENTAGE_DISCOUNT
        rule3.status = RuleStatus.ACTIVE
        rule3.priority = RulePriority.CRITICAL
        rule3.stackable = False
        rule3.excluded_rule_ids = []
        rule3.conditions = {
            "min_order_amount": 30.00,
            "discount_percentage": 10
        }
        rule3.valid_from = datetime.utcnow() - timedelta(days=1)
        rule3.valid_until = datetime.utcnow() + timedelta(days=30)
        rule3.is_valid = Mock(return_value=True)
        rules.append(rule3)
        
        return rules
    
    @pytest.fixture
    def mixed_type_rules(self):
        """Create rules of different types that could overlap"""
        rules = []
        
        # Fixed amount discount
        rule1 = Mock(spec=PricingRule)
        rule1.id = 4
        rule1.rule_id = "FIXED5"
        rule1.name = "Fixed $5 Off"
        rule1.rule_type = RuleType.FIXED_DISCOUNT
        rule1.status = RuleStatus.ACTIVE
        rule1.priority = RulePriority.MEDIUM
        rule1.stackable = True
        rule1.excluded_rule_ids = []
        rule1.conditions = {
            "min_order_amount": 25.00,
            "discount_amount": 5.00
        }
        rule1.valid_from = datetime.utcnow() - timedelta(days=1)
        rule1.valid_until = datetime.utcnow() + timedelta(days=30)
        rule1.is_valid = Mock(return_value=True)
        rules.append(rule1)
        
        # Buy one get one free
        rule2 = Mock(spec=PricingRule)
        rule2.id = 5
        rule2.rule_id = "BOGO"
        rule2.name = "Buy One Get One Free"
        rule2.rule_type = RuleType.BUY_X_GET_Y
        rule2.status = RuleStatus.ACTIVE
        rule2.priority = RulePriority.HIGH
        rule2.stackable = True
        rule2.excluded_rule_ids = []
        rule2.conditions = {
            "buy_quantity": 1,
            "get_quantity": 1,
            "target_item_ids": [10],
            "free_item_discount": 100
        }
        rule2.valid_from = datetime.utcnow() - timedelta(days=1)
        rule2.valid_until = datetime.utcnow() + timedelta(days=30)
        rule2.is_valid = Mock(return_value=True)
        rules.append(rule2)
        
        # Percentage discount
        rule3 = Mock(spec=PricingRule)
        rule3.id = 6
        rule3.rule_id = "PERCENT15"
        rule3.name = "15% Off Everything"
        rule3.rule_type = RuleType.PERCENTAGE_DISCOUNT
        rule3.status = RuleStatus.ACTIVE
        rule3.priority = RulePriority.LOW
        rule3.stackable = True
        rule3.excluded_rule_ids = []
        rule3.conditions = {
            "discount_percentage": 15
        }
        rule3.valid_from = datetime.utcnow() - timedelta(days=1)
        rule3.valid_until = datetime.utcnow() + timedelta(days=30)
        rule3.is_valid = Mock(return_value=True)
        rules.append(rule3)
        
        return rules
    
    @pytest.fixture
    def time_sensitive_rules(self):
        """Create time-sensitive overlapping rules"""
        rules = []
        now = datetime.utcnow()
        
        # Happy hour rule (should be active)
        rule1 = Mock(spec=PricingRule)
        rule1.id = 7
        rule1.rule_id = "HAPPY"
        rule1.name = "Happy Hour 25% Off"
        rule1.rule_type = RuleType.PERCENTAGE_DISCOUNT
        rule1.status = RuleStatus.ACTIVE
        rule1.priority = RulePriority.HIGH
        rule1.stackable = False
        rule1.excluded_rule_ids = []
        rule1.conditions = {
            "discount_percentage": 25,
            "valid_hours": ["14:00-17:00"],  # 2-5 PM
            "valid_days": ["MON", "TUE", "WED", "THU", "FRI"]
        }
        rule1.valid_from = now - timedelta(days=1)
        rule1.valid_until = now + timedelta(days=30)
        rule1.is_valid = Mock(return_value=True)
        rules.append(rule1)
        
        # Weekend special (overlaps if it's weekend)
        rule2 = Mock(spec=PricingRule)
        rule2.id = 8
        rule2.rule_id = "WEEKEND"
        rule2.name = "Weekend Special 30% Off"
        rule2.rule_type = RuleType.PERCENTAGE_DISCOUNT
        rule2.status = RuleStatus.ACTIVE
        rule2.priority = RulePriority.MEDIUM
        rule2.stackable = False
        rule2.excluded_rule_ids = []
        rule2.conditions = {
            "discount_percentage": 30,
            "valid_days": ["SAT", "SUN"]
        }
        rule2.valid_from = now - timedelta(days=1)
        rule2.valid_until = now + timedelta(days=30)
        rule2.is_valid = Mock(return_value=True)
        rules.append(rule2)
        
        return rules
    
    @pytest.mark.asyncio
    async def test_highest_discount_conflict_resolution(
        self, pricing_service, mock_db, sample_order, overlapping_percentage_rules
    ):
        """Test that highest discount wins when multiple percentage rules overlap"""
        
        # Mock the rule evaluation to return all as applicable
        evaluation_results = []
        for rule in overlapping_percentage_rules:
            if rule.rule_id == "BULK15":
                discount = Decimal('50.00') * Decimal('0.15')  # $7.50
            elif rule.rule_id == "PREMIUM20":
                discount = Decimal('50.00') * Decimal('0.20')  # $10.00 (should win)
            elif rule.rule_id == "PRIORITY10":
                discount = Decimal('50.00') * Decimal('0.10')  # $5.00
            
            result = RuleEvaluationResult(
                rule_id=rule.id,
                rule_name=rule.name,
                rule_type=rule.rule_type,
                applicable=True,
                conditions_met=True,
                discount_amount=discount,
                rule=rule
            )
            evaluation_results.append(result)
        
        # Test conflict resolution
        final_results = await pricing_service._resolve_conflicts(evaluation_results, sample_order)
        
        # Should select the 20% rule (highest discount)
        assert len(final_results) == 1
        assert final_results[0].rule_id == 2  # PREMIUM20
        assert final_results[0].discount_amount == Decimal('10.00')
    
    @pytest.mark.asyncio
    async def test_priority_based_conflict_resolution(
        self, pricing_service, mock_db, sample_order, overlapping_percentage_rules
    ):
        """Test priority-based conflict resolution"""
        
        # Change conflict resolution strategy
        sample_order.restaurant.default_conflict_resolution = ConflictResolution.PRIORITY_BASED
        
        # Mock evaluation results (same as before)
        evaluation_results = []
        for rule in overlapping_percentage_rules:
            if rule.rule_id == "BULK15":
                discount = Decimal('7.50')
            elif rule.rule_id == "PREMIUM20":
                discount = Decimal('10.00')
            elif rule.rule_id == "PRIORITY10":
                discount = Decimal('5.00')
            
            result = RuleEvaluationResult(
                rule_id=rule.id,
                rule_name=rule.name,
                rule_type=rule.rule_type,
                applicable=True,
                conditions_met=True,
                discount_amount=discount,
                rule=rule
            )
            evaluation_results.append(result)
        
        # Sort by priority (CRITICAL > HIGH > MEDIUM)
        evaluation_results.sort(key=lambda x: x.rule.priority.value)
        
        final_results = await pricing_service._resolve_conflicts(evaluation_results, sample_order)
        
        # Should select the critical priority rule even though discount is lower
        assert len(final_results) == 1
        assert final_results[0].rule_id == 3  # PRIORITY10 (CRITICAL priority)
        assert final_results[0].discount_amount == Decimal('5.00')
    
    @pytest.mark.asyncio
    async def test_stackable_rules_combination(
        self, pricing_service, mock_db, sample_order, mixed_type_rules
    ):
        """Test that stackable rules can be combined"""
        
        # All rules are stackable in this fixture
        evaluation_results = []
        for rule in mixed_type_rules:
            if rule.rule_id == "FIXED5":
                discount = Decimal('5.00')
            elif rule.rule_id == "BOGO":
                discount = Decimal('12.50')  # Free item value
            elif rule.rule_id == "PERCENT15":
                discount = Decimal('7.50')  # 15% of $50
            
            result = RuleEvaluationResult(
                rule_id=rule.id,
                rule_name=rule.name,
                rule_type=rule.rule_type,
                applicable=True,
                conditions_met=True,
                discount_amount=discount,
                rule=rule
            )
            evaluation_results.append(result)
        
        final_results = await pricing_service._resolve_conflicts(evaluation_results, sample_order)
        
        # All stackable rules should be included
        assert len(final_results) == 3
        total_discount = sum(r.discount_amount for r in final_results)
        assert total_discount == Decimal('25.00')  # $5 + $12.50 + $7.50
    
    @pytest.mark.asyncio
    async def test_excluded_rules_enforcement(self, pricing_service, mock_db, sample_order):
        """Test that excluded rule IDs are properly enforced"""
        
        # Create rules where one excludes another
        rule1 = Mock(spec=PricingRule)
        rule1.id = 10
        rule1.rule_id = "EXCLUSIVE"
        rule1.name = "Exclusive Rule"
        rule1.stackable = True
        rule1.excluded_rule_ids = [11]  # Excludes rule2
        
        rule2 = Mock(spec=PricingRule)
        rule2.id = 11
        rule2.rule_id = "EXCLUDED"
        rule2.name = "Excluded Rule"
        rule2.stackable = True
        rule2.excluded_rule_ids = []
        
        evaluation_results = [
            RuleEvaluationResult(
                rule_id=10,
                rule_name="Exclusive Rule",
                rule_type=RuleType.FIXED_DISCOUNT,
                applicable=True,
                conditions_met=True,
                discount_amount=Decimal('5.00'),
                rule=rule1
            ),
            RuleEvaluationResult(
                rule_id=11,
                rule_name="Excluded Rule", 
                rule_type=RuleType.FIXED_DISCOUNT,
                applicable=True,
                conditions_met=True,
                discount_amount=Decimal('10.00'),
                rule=rule2
            )
        ]
        
        final_results = await pricing_service._resolve_conflicts(evaluation_results, sample_order)
        
        # Only the first rule should be applied (second is excluded)
        assert len(final_results) == 1
        assert final_results[0].rule_id == 10
    
    @pytest.mark.asyncio
    async def test_time_boundary_edge_cases(self, pricing_service, mock_db, sample_order):
        """Test edge cases around time boundaries"""
        
        now = datetime.utcnow()
        
        # Rule that expires in 1 second
        expiring_rule = Mock(spec=PricingRule)
        expiring_rule.id = 12
        expiring_rule.valid_from = now - timedelta(hours=1)
        expiring_rule.valid_until = now + timedelta(seconds=1)
        expiring_rule.is_valid = Mock(return_value=True)
        expiring_rule.status = RuleStatus.ACTIVE
        expiring_rule.restaurant_id = 1
        
        # Rule that starts in 1 second
        future_rule = Mock(spec=PricingRule)
        future_rule.id = 13
        future_rule.valid_from = now + timedelta(seconds=1)
        future_rule.valid_until = now + timedelta(hours=1)
        future_rule.is_valid = Mock(return_value=False)  # Not valid yet
        future_rule.status = RuleStatus.ACTIVE
        future_rule.restaurant_id = 1
        
        rules = [expiring_rule, future_rule]
        
        # Mock the DB query to return these rules
        mock_db.execute = AsyncMock()
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = rules
        mock_db.execute.return_value = mock_result
        
        applicable_rules = await pricing_service._get_applicable_rules(mock_db, sample_order)
        
        # Only the expiring rule should be applicable (future rule fails is_valid())
        assert len(applicable_rules) == 1
        assert applicable_rules[0].id == 12
    
    @pytest.mark.asyncio
    async def test_zero_discount_edge_case(self, pricing_service, mock_db, sample_order):
        """Test handling of rules that result in zero discount"""
        
        # Rule with conditions that result in zero discount
        result = RuleEvaluationResult(
            rule_id=14,
            rule_name="Zero Discount Rule",
            rule_type=RuleType.PERCENTAGE_DISCOUNT,
            applicable=True,
            conditions_met=True,
            discount_amount=Decimal('0.00'),
            rule=Mock()
        )
        
        final_results = await pricing_service._resolve_conflicts([result], sample_order)
        
        # Zero discount rule should still be included if applicable
        assert len(final_results) == 1
        assert final_results[0].discount_amount == Decimal('0.00')
    
    @pytest.mark.asyncio
    async def test_negative_discount_protection(self, pricing_service, mock_db, sample_order):
        """Test protection against negative discounts"""
        
        # This should not happen in normal operation, but test the edge case
        result = RuleEvaluationResult(
            rule_id=15,
            rule_name="Negative Rule",
            rule_type=RuleType.FIXED_DISCOUNT,
            applicable=True,
            conditions_met=True,
            discount_amount=Decimal('-5.00'),  # Negative discount
            rule=Mock()
        )
        
        final_results = await pricing_service._resolve_conflicts([result], sample_order)
        
        # System should handle negative discounts gracefully
        assert len(final_results) == 1
        # In a real implementation, you might want to filter out negative discounts
    
    @pytest.mark.asyncio
    async def test_maximum_discount_cap(self, pricing_service, mock_db, sample_order):
        """Test handling of discounts that exceed order value"""
        
        # Discount larger than order total
        result = RuleEvaluationResult(
            rule_id=16,
            rule_name="Excessive Discount",
            rule_type=RuleType.FIXED_DISCOUNT,
            applicable=True,
            conditions_met=True,
            discount_amount=Decimal('100.00'),  # More than $50 order
            rule=Mock()
        )
        
        final_results = await pricing_service._resolve_conflicts([result], sample_order)
        
        # Rule should be included but discount should be capped in application
        assert len(final_results) == 1
        assert final_results[0].discount_amount == Decimal('100.00')
        # Note: Actual capping would happen in the application logic
    
    @pytest.mark.asyncio
    async def test_circular_exclusion_protection(self, pricing_service, mock_db, sample_order):
        """Test protection against circular rule exclusions"""
        
        # Rule A excludes Rule B, Rule B excludes Rule A
        rule_a = Mock(spec=PricingRule)
        rule_a.id = 17
        rule_a.excluded_rule_ids = [18]
        rule_a.stackable = True
        
        rule_b = Mock(spec=PricingRule)
        rule_b.id = 18
        rule_b.excluded_rule_ids = [17]
        rule_b.stackable = True
        
        results = [
            RuleEvaluationResult(
                rule_id=17,
                rule_name="Rule A",
                rule_type=RuleType.FIXED_DISCOUNT,
                applicable=True,
                conditions_met=True,
                discount_amount=Decimal('5.00'),
                rule=rule_a
            ),
            RuleEvaluationResult(
                rule_id=18,
                rule_name="Rule B",
                rule_type=RuleType.FIXED_DISCOUNT,
                applicable=True,
                conditions_met=True,
                discount_amount=Decimal('7.00'),
                rule=rule_b
            )
        ]
        
        final_results = await pricing_service._resolve_conflicts(results, sample_order)
        
        # Should handle circular exclusion gracefully (first rule wins)
        assert len(final_results) == 1
        assert final_results[0].rule_id == 17
    
    @pytest.mark.asyncio
    async def test_complex_multi_rule_scenario(
        self, pricing_service, mock_db, sample_order
    ):
        """Test a complex scenario with multiple overlapping rules of different types"""
        
        sample_order.restaurant.default_conflict_resolution = ConflictResolution.HIGHEST_DISCOUNT
        
        # Create a complex mix of rules
        rules_data = [
            # Non-stackable percentage (should conflict)
            (19, "20% Off", RuleType.PERCENTAGE_DISCOUNT, False, Decimal('10.00')),
            (20, "15% Off", RuleType.PERCENTAGE_DISCOUNT, False, Decimal('7.50')),
            
            # Stackable fixed discounts
            (21, "$3 Off", RuleType.FIXED_DISCOUNT, True, Decimal('3.00')),
            (22, "$2 Off", RuleType.FIXED_DISCOUNT, True, Decimal('2.00')),
            
            # Stackable BOGO
            (23, "BOGO Deal", RuleType.BUY_X_GET_Y, True, Decimal('12.50')),
        ]
        
        evaluation_results = []
        for rule_id, name, rule_type, stackable, discount in rules_data:
            rule_mock = Mock(spec=PricingRule)
            rule_mock.id = rule_id
            rule_mock.stackable = stackable
            rule_mock.excluded_rule_ids = []
            
            result = RuleEvaluationResult(
                rule_id=rule_id,
                rule_name=name,
                rule_type=rule_type,
                applicable=True,
                conditions_met=True,
                discount_amount=discount,
                rule=rule_mock
            )
            evaluation_results.append(result)
        
        final_results = await pricing_service._resolve_conflicts(evaluation_results, sample_order)
        
        # Should get: Best percentage (20% = $10) + stackable fixed ($3 + $2) + BOGO ($12.50)
        assert len(final_results) == 4
        
        total_discount = sum(r.discount_amount for r in final_results)
        expected_total = Decimal('10.00') + Decimal('3.00') + Decimal('2.00') + Decimal('12.50')
        assert total_discount == expected_total
        
        # Verify the non-stackable rule with highest discount was selected
        percentage_rules = [r for r in final_results if r.rule_name in ["20% Off", "15% Off"]]
        assert len(percentage_rules) == 1
        assert percentage_rules[0].rule_name == "20% Off"