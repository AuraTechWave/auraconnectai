# backend/tests/modules/loyalty/test_loyalty_service.py

"""
Comprehensive tests for loyalty service.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch, MagicMock, call
from decimal import Decimal

from modules.loyalty.services.loyalty_service import LoyaltyService
from modules.loyalty.models.rewards_models import (
    RewardTemplate, CustomerReward, RewardCampaign,
    RewardRedemption, LoyaltyPointsTransaction,
    RewardType, RewardStatus, TriggerType
)
from modules.loyalty.schemas.loyalty_schemas import (
    PointsTransactionCreate, PointsAdjustment, PointsTransfer,
    RewardTemplateCreate, RewardTemplateUpdate,
    ManualRewardIssuance, BulkRewardIssuance,
    RewardRedemptionRequest, RewardValidationRequest,
    OrderCompletionReward
)
from modules.customers.models import Customer
from core.error_handling import NotFoundError, APIValidationError, ConflictError


@pytest.fixture
def db_session():
    """Mock database session"""
    session = Mock(spec=Session)
    session.query = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.refresh = Mock()
    session.flush = Mock()
    return session


@pytest.fixture
def loyalty_service(db_session):
    """Create LoyaltyService instance"""
    return LoyaltyService(db_session)


@pytest.fixture
def sample_customer():
    """Sample customer for testing"""
    customer = Mock(spec=Customer)
    customer.id = 1
    customer.email = "customer@example.com"
    customer.created_at = datetime.utcnow()
    return customer


@pytest.fixture
def sample_reward_template():
    """Sample reward template"""
    return RewardTemplate(
        id=1,
        name="10% Off",
        description="10% discount on next order",
        reward_type=RewardType.PERCENTAGE_DISCOUNT,
        percentage=10,
        points_cost=100,
        is_active=True,
        valid_days=30
    )


@pytest.fixture
def sample_customer_reward():
    """Sample customer reward"""
    return CustomerReward(
        id=1,
        customer_id=1,
        template_id=1,
        reward_type=RewardType.PERCENTAGE_DISCOUNT,
        title="10% Off",
        percentage=10,
        code="REWARD123",
        status=RewardStatus.AVAILABLE,
        valid_from=datetime.utcnow(),
        valid_until=datetime.utcnow() + timedelta(days=30)
    )


class TestPointsManagement:
    """Tests for points management"""
    
    def test_add_points_success(self, loyalty_service, db_session, sample_customer):
        """Test successful points addition"""
        transaction_data = PointsTransactionCreate(
            customer_id=1,
            transaction_type="earned",
            points_change=100,
            reason="Order completion",
            order_id=123,
            source="order"
        )
        
        # Mock customer lookup
        db_session.query.return_value.filter.return_value.first.return_value = sample_customer
        
        # Mock current balance
        db_session.query.return_value.filter.return_value.scalar.return_value = 500
        
        # Add points
        result = loyalty_service.add_points(transaction_data)
        
        # Verify
        db_session.add.assert_called_once()
        db_session.commit.assert_called_once()
        assert result.points_change == 100
        assert result.points_balance_before == 500
        assert result.points_balance_after == 600
    
    def test_add_points_insufficient_balance(self, loyalty_service, db_session, sample_customer):
        """Test points redemption with insufficient balance"""
        transaction_data = PointsTransactionCreate(
            customer_id=1,
            transaction_type="redeemed",
            points_change=-200,
            reason="Reward redemption"
        )
        
        # Mock customer lookup
        db_session.query.return_value.filter.return_value.first.return_value = sample_customer
        
        # Mock insufficient balance
        db_session.query.return_value.filter.return_value.scalar.return_value = 100
        
        # Should raise error
        with pytest.raises(APIValidationError) as exc_info:
            loyalty_service.add_points(transaction_data)
        
        assert "Insufficient points balance" in str(exc_info.value)
    
    def test_adjust_points_manual(self, loyalty_service, db_session, sample_customer):
        """Test manual points adjustment"""
        adjustment = PointsAdjustment(
            customer_id=1,
            points=50,
            reason="Customer service compensation",
            notify_customer=True
        )
        
        # Mock customer and balance
        db_session.query.return_value.filter.return_value.first.return_value = sample_customer
        db_session.query.return_value.filter.return_value.scalar.return_value = 100
        
        # Adjust points
        result = loyalty_service.adjust_points(adjustment, staff_id=1)
        
        # Verify
        assert result.points_change == 50
        assert result.transaction_type == "adjusted"
        assert result.source == "manual"
    
    def test_transfer_points_success(self, loyalty_service, db_session):
        """Test successful points transfer"""
        transfer = PointsTransfer(
            from_customer_id=1,
            to_customer_id=2,
            points=100,
            reason="Family transfer"
        )
        
        # Mock customers
        from_customer = Mock(id=1)
        to_customer = Mock(id=2)
        
        db_session.query.return_value.filter.return_value.first.side_effect = [
            from_customer,  # From customer exists
            to_customer,    # To customer exists
            from_customer,  # For debit transaction
            to_customer     # For credit transaction
        ]
        
        # Mock balances
        db_session.query.return_value.filter.return_value.scalar.side_effect = [
            200,  # From customer balance (sufficient)
            200,  # Balance check for debit
            100,  # New balance after debit
            50,   # To customer initial balance
            150   # To customer new balance
        ]
        
        # Transfer points
        debit, credit = loyalty_service.transfer_points(transfer, staff_id=1)
        
        # Verify transactions
        assert debit.points_change == -100
        assert credit.points_change == 100
        assert db_session.add.call_count == 2
    
    def test_transfer_points_insufficient_balance(self, loyalty_service, db_session):
        """Test points transfer with insufficient balance"""
        transfer = PointsTransfer(
            from_customer_id=1,
            to_customer_id=2,
            points=100,
            reason="Transfer"
        )
        
        # Mock customers
        from_customer = Mock(id=1)
        to_customer = Mock(id=2)
        
        db_session.query.return_value.filter.return_value.first.side_effect = [
            from_customer,
            to_customer
        ]
        
        # Mock insufficient balance
        db_session.query.return_value.filter.return_value.scalar.return_value = 50
        
        # Should raise error
        with pytest.raises(APIValidationError) as exc_info:
            loyalty_service.transfer_points(transfer, staff_id=1)
        
        assert "Insufficient points for transfer" in str(exc_info.value)


class TestRewardTemplates:
    """Tests for reward template management"""
    
    def test_create_reward_template_success(self, loyalty_service, db_session):
        """Test successful reward template creation"""
        template_data = RewardTemplateCreate(
            name="20% Off",
            description="20% discount on any order",
            reward_type=RewardType.PERCENTAGE_DISCOUNT,
            percentage=20,
            points_cost=200,
            min_order_amount=50.0,
            valid_days=30
        )
        
        # Mock no existing template
        db_session.query.return_value.filter.return_value.first.return_value = None
        
        # Create template
        result = loyalty_service.create_reward_template(template_data)
        
        # Verify
        db_session.add.assert_called_once()
        db_session.commit.assert_called_once()
        assert result.name == "20% Off"
        assert result.percentage == 20
    
    def test_create_reward_template_duplicate_name(self, loyalty_service, db_session):
        """Test creating template with duplicate name"""
        template_data = RewardTemplateCreate(
            name="Existing Template",
            description="Test",
            reward_type=RewardType.FIXED_DISCOUNT,
            value=10.0
        )
        
        # Mock existing template
        existing = Mock(name="Existing Template")
        db_session.query.return_value.filter.return_value.first.return_value = existing
        
        # Should raise error
        with pytest.raises(ConflictError):
            loyalty_service.create_reward_template(template_data)
    
    def test_update_reward_template(self, loyalty_service, db_session, sample_reward_template):
        """Test updating reward template"""
        update_data = RewardTemplateUpdate(
            description="Updated description",
            points_cost=150,
            is_featured=True
        )
        
        # Mock template lookup
        db_session.query.return_value.filter.return_value.first.return_value = sample_reward_template
        
        # Update template
        result = loyalty_service.update_reward_template(1, update_data)
        
        # Verify
        assert result.description == "Updated description"
        assert result.points_cost == 150
        assert result.is_featured == True
        db_session.commit.assert_called_once()
    
    def test_get_available_templates_with_filters(self, loyalty_service, db_session):
        """Test getting available templates with filters"""
        # Mock templates
        templates = [
            Mock(
                id=1,
                name="Template 1",
                reward_type=RewardType.PERCENTAGE_DISCOUNT,
                points_cost=100,
                eligible_tiers=[],
                priority=1
            ),
            Mock(
                id=2,
                name="Template 2",
                reward_type=RewardType.FIXED_DISCOUNT,
                points_cost=200,
                eligible_tiers=["gold"],
                priority=2
            )
        ]
        
        # Mock query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.all.return_value = templates
        db_session.query.return_value = mock_query
        
        # Get templates
        result = loyalty_service.get_available_templates(
            customer_id=1,
            reward_type=RewardType.PERCENTAGE_DISCOUNT,
            points_balance=150
        )
        
        # Verify ordering
        assert len(result) == 2


class TestRewardIssuance:
    """Tests for reward issuance"""
    
    def test_issue_reward_success(self, loyalty_service, db_session, sample_customer, sample_reward_template):
        """Test successful reward issuance"""
        # Mock lookups
        db_session.query.return_value.filter.return_value.first.side_effect = [
            sample_customer,        # Customer exists
            sample_reward_template, # Template exists
            None                    # No existing reward count
        ]
        
        # Mock reward count
        db_session.query.return_value.filter.return_value.count.return_value = 0
        
        # Issue reward
        result = loyalty_service.issue_reward(
            customer_id=1,
            template_id=1,
            issued_by=1
        )
        
        # Verify
        db_session.add.assert_called()
        assert result.customer_id == 1
        assert result.template_id == 1
        assert result.status == RewardStatus.AVAILABLE
        assert len(result.code) == 8  # Generated code
    
    def test_issue_reward_usage_limit_exceeded(self, loyalty_service, db_session, sample_customer, sample_reward_template):
        """Test reward issuance when usage limit exceeded"""
        # Set usage limit
        sample_reward_template.max_uses_per_customer = 1
        
        # Mock lookups
        db_session.query.return_value.filter.return_value.first.side_effect = [
            sample_customer,
            sample_reward_template
        ]
        
        # Mock existing reward count
        db_session.query.return_value.filter.return_value.count.return_value = 1
        
        # Should raise error
        with pytest.raises(APIValidationError) as exc_info:
            loyalty_service.issue_reward(1, 1)
        
        assert "maximum uses" in str(exc_info.value)
    
    def test_issue_manual_reward(self, loyalty_service, db_session, sample_customer, sample_reward_template):
        """Test manual reward issuance"""
        issuance = ManualRewardIssuance(
            customer_id=1,
            template_id=1,
            reason="Customer appreciation",
            valid_days_override=60,
            notify_customer=True
        )
        
        # Mock lookups
        db_session.query.return_value.filter.return_value.first.side_effect = [
            sample_customer,
            sample_reward_template,
            None
        ]
        db_session.query.return_value.filter.return_value.count.return_value = 0
        
        # Issue reward
        result = loyalty_service.issue_manual_reward(issuance, staff_id=1)
        
        # Verify
        assert result.issued_by == 1
        assert "manual" in result.trigger_data
    
    def test_issue_bulk_rewards(self, loyalty_service, db_session, sample_customer, sample_reward_template):
        """Test bulk reward issuance"""
        bulk_issuance = BulkRewardIssuance(
            template_id=1,
            customer_ids=[1, 2, 3],
            reason="Holiday promotion",
            notify_customers=True
        )
        
        # Mock customers and template
        customers = [Mock(id=i) for i in [1, 2, 3]]
        
        # Configure mocks for each issuance
        db_session.query.return_value.filter.return_value.first.side_effect = [
            customers[0], sample_reward_template, None,  # Customer 1
            customers[1], sample_reward_template, None,  # Customer 2
            customers[2], sample_reward_template, None   # Customer 3
        ]
        db_session.query.return_value.filter.return_value.count.return_value = 0
        
        # Issue rewards
        results = loyalty_service.issue_bulk_rewards(bulk_issuance, staff_id=1)
        
        # Verify
        assert len(results) == 3
        assert all(r.template_id == 1 for r in results)


class TestRewardValidationAndRedemption:
    """Tests for reward validation and redemption"""
    
    def test_validate_reward_valid(self, loyalty_service, db_session, sample_customer_reward):
        """Test validating valid reward"""
        validation_request = RewardValidationRequest(
            reward_code="REWARD123",
            order_amount=100.0
        )
        
        # Mock reward lookup
        db_session.query.return_value.filter.return_value.first.return_value = sample_customer_reward
        
        # Mock template
        sample_customer_reward.template = Mock(
            min_order_amount=50.0,
            max_discount_amount=None,
            terms_and_conditions="Valid on orders over $50"
        )
        
        # Validate
        result = loyalty_service.validate_reward(validation_request)
        
        # Verify
        assert result["is_valid"] == True
        assert result["discount_amount"] == 10.0  # 10% of $100
        assert len(result["validation_errors"]) == 0
    
    def test_validate_reward_expired(self, loyalty_service, db_session, sample_customer_reward):
        """Test validating expired reward"""
        validation_request = RewardValidationRequest(
            reward_code="REWARD123",
            order_amount=100.0
        )
        
        # Set reward as expired
        sample_customer_reward.valid_until = datetime.utcnow() - timedelta(days=1)
        
        # Mock reward lookup
        db_session.query.return_value.filter.return_value.first.return_value = sample_customer_reward
        
        # Validate
        result = loyalty_service.validate_reward(validation_request)
        
        # Verify
        assert result["is_valid"] == False
        assert "expired" in result["validation_errors"][0]
    
    def test_validate_reward_minimum_order_not_met(self, loyalty_service, db_session, sample_customer_reward):
        """Test validating reward with minimum order requirement not met"""
        validation_request = RewardValidationRequest(
            reward_code="REWARD123",
            order_amount=30.0
        )
        
        # Mock reward and template
        sample_customer_reward.template = Mock(
            min_order_amount=50.0,
            max_discount_amount=None
        )
        
        db_session.query.return_value.filter.return_value.first.return_value = sample_customer_reward
        
        # Validate
        result = loyalty_service.validate_reward(validation_request)
        
        # Verify
        assert result["is_valid"] == False
        assert "Minimum order amount" in result["validation_errors"][0]
    
    def test_redeem_reward_success(self, loyalty_service, db_session, sample_customer_reward):
        """Test successful reward redemption"""
        redemption_request = RewardRedemptionRequest(
            reward_code="REWARD123",
            order_id=123,
            order_amount=100.0
        )
        
        # Mock reward and template
        sample_customer_reward.template = Mock(
            min_order_amount=0,
            max_discount_amount=None,
            total_redeemed=5
        )
        
        # Mock reward lookup with lock
        mock_query = Mock()
        mock_query.filter.return_value.with_for_update.return_value.first.return_value = sample_customer_reward
        db_session.query.return_value = mock_query
        
        # Mock validation
        with patch.object(loyalty_service, 'validate_reward') as mock_validate:
            mock_validate.return_value = {
                "is_valid": True,
                "discount_amount": 10.0
            }
            
            # Redeem
            result = loyalty_service.redeem_reward(redemption_request)
        
        # Verify
        assert result["success"] == True
        assert result["discount_amount"] == 10.0
        assert sample_customer_reward.status == RewardStatus.REDEEMED
        assert sample_customer_reward.order_id == 123
        db_session.add.assert_called_once()  # Redemption record
        db_session.commit.assert_called_once()
    
    def test_redeem_reward_validation_failed(self, loyalty_service, db_session):
        """Test redemption with validation failure"""
        redemption_request = RewardRedemptionRequest(
            reward_code="INVALID",
            order_id=123,
            order_amount=100.0
        )
        
        # Mock validation failure
        with patch.object(loyalty_service, 'validate_reward') as mock_validate:
            mock_validate.return_value = {
                "is_valid": False,
                "validation_errors": ["Invalid reward code"]
            }
            
            # Redeem
            result = loyalty_service.redeem_reward(redemption_request)
        
        # Verify
        assert result["success"] == False
        assert "Invalid reward code" in result["message"]


class TestOrderIntegration:
    """Tests for order integration"""
    
    def test_process_order_completion(self, loyalty_service, db_session):
        """Test processing order completion"""
        order_data = OrderCompletionReward(
            customer_id=1,
            order_id=123,
            order_amount=100.0,
            items_purchased=["item1", "item2"]
        )
        
        # Mock customer
        db_session.query.return_value.filter.return_value.first.return_value = Mock(id=1)
        
        # Mock points balance checks
        db_session.query.return_value.filter.return_value.scalar.side_effect = [
            0,    # Initial balance
            100,  # After earning points
            100   # For tier calculation
        ]
        
        # Mock triggered rewards check
        db_session.query.return_value.filter.return_value.all.return_value = []
        
        # Process order
        result = loyalty_service.process_order_completion(order_data)
        
        # Verify
        assert result["points_earned"] == 100  # $100 * 1 point per dollar
        assert "current_tier" in result["tier_progress"]
        db_session.add.assert_called()  # Points transaction
    
    def test_process_order_with_triggered_rewards(self, loyalty_service, db_session):
        """Test order processing that triggers rewards"""
        order_data = OrderCompletionReward(
            customer_id=1,
            order_id=123,
            order_amount=200.0
        )
        
        # Mock triggered reward templates
        triggered_template = Mock(
            id=1,
            trigger_type=TriggerType.ORDER_COMPLETE,
            trigger_conditions={"min_order_amount": 150}
        )
        
        # Configure mocks
        db_session.query.return_value.filter.return_value.first.side_effect = [
            Mock(id=1),  # Customer exists
            Mock(id=1),  # For reward issuance
            triggered_template,  # Template lookup
            None  # No existing reward
        ]
        
        db_session.query.return_value.filter.return_value.scalar.side_effect = [
            0,    # Initial balance
            200,  # After earning points
            200   # For tier calculation
        ]
        
        db_session.query.return_value.filter.return_value.all.return_value = [triggered_template]
        db_session.query.return_value.filter.return_value.count.return_value = 0
        
        # Process order
        result = loyalty_service.process_order_completion(order_data)
        
        # Verify
        assert result["points_earned"] == 200
        assert len(result["rewards_triggered"]) == 1


class TestHelperMethods:
    """Tests for helper methods"""
    
    def test_get_customer_points_balance(self, loyalty_service, db_session):
        """Test getting customer points balance"""
        # Mock balance query
        db_session.query.return_value.filter.return_value.scalar.return_value = 500
        
        balance = loyalty_service._get_customer_points_balance(1)
        
        assert balance == 500
    
    def test_get_customer_tier_calculation(self, loyalty_service, db_session):
        """Test customer tier calculation"""
        # Mock lifetime points
        db_session.query.return_value.filter.return_value.scalar.side_effect = [
            2500,  # Lifetime earned (Silver tier)
            2500   # For tier calculation
        ]
        
        tier_info = loyalty_service._calculate_customer_tier(1, 500)
        
        assert tier_info["current_tier"] == "silver"
        assert tier_info["points_to_next_tier"] == 2500  # 5000 - 2500
        assert "benefits" in tier_info
    
    def test_calculate_discount_percentage(self, loyalty_service):
        """Test discount calculation for percentage rewards"""
        reward = Mock(
            reward_type=RewardType.PERCENTAGE_DISCOUNT,
            percentage=20,
            template=Mock(max_discount_amount=None)
        )
        
        discount = loyalty_service._calculate_discount(reward, 100.0)
        
        assert discount == 20.0  # 20% of $100
    
    def test_calculate_discount_with_max_limit(self, loyalty_service):
        """Test discount calculation with maximum limit"""
        reward = Mock(
            reward_type=RewardType.PERCENTAGE_DISCOUNT,
            percentage=50,
            template=Mock(max_discount_amount=25.0)
        )
        
        discount = loyalty_service._calculate_discount(reward, 100.0)
        
        assert discount == 25.0  # Limited by max_discount_amount
    
    def test_generate_reward_code_uniqueness(self, loyalty_service, db_session):
        """Test reward code generation ensures uniqueness"""
        # First call finds existing code, second doesn't
        db_session.query.return_value.filter.return_value.first.side_effect = [
            Mock(code="ABCD1234"),  # First code exists
            None                     # Second code is unique
        ]
        
        code = loyalty_service._generate_reward_code()
        
        # Should have queried twice
        assert db_session.query.call_count == 2
        assert len(code) == 8
        assert code.isupper()


class TestValidation:
    """Tests for validation methods"""
    
    def test_validate_reward_template_percentage_discount(self, loyalty_service):
        """Test validation for percentage discount template"""
        # Valid percentage discount
        template = RewardTemplateCreate(
            name="20% Off",
            description="Test",
            reward_type=RewardType.PERCENTAGE_DISCOUNT,
            percentage=20
        )
        
        # Should not raise
        loyalty_service._validate_reward_template(template)
        
        # Invalid - no percentage
        template.percentage = None
        with pytest.raises(APIValidationError):
            loyalty_service._validate_reward_template(template)
    
    def test_validate_reward_template_fixed_discount(self, loyalty_service):
        """Test validation for fixed discount template"""
        # Valid fixed discount
        template = RewardTemplateCreate(
            name="$10 Off",
            description="Test",
            reward_type=RewardType.FIXED_DISCOUNT,
            value=10.0
        )
        
        # Should not raise
        loyalty_service._validate_reward_template(template)
        
        # Invalid - no value
        template.value = None
        with pytest.raises(APIValidationError):
            loyalty_service._validate_reward_template(template)
    
    def test_validate_reward_template_free_item(self, loyalty_service):
        """Test validation for free item template"""
        # Valid free item
        template = RewardTemplateCreate(
            name="Free Coffee",
            description="Test",
            reward_type=RewardType.FREE_ITEM,
            item_id=123
        )
        
        # Should not raise
        loyalty_service._validate_reward_template(template)
        
        # Invalid - no item_id
        template.item_id = None
        with pytest.raises(APIValidationError):
            loyalty_service._validate_reward_template(template)


if __name__ == "__main__":
    pytest.main([__file__])