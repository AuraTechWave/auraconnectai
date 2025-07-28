# tests/test_loyalty_system.py

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.modules.loyalty.services.rewards_engine import RewardsEngine
from backend.modules.loyalty.services.loyalty_service import LoyaltyService
from backend.modules.loyalty.services.order_integration import OrderLoyaltyIntegration
from backend.modules.loyalty.models.rewards_models import (
    RewardTemplate, CustomerReward, RewardStatus, RewardType, TriggerType,
    LoyaltyPointsTransaction, RewardCampaign
)
from backend.modules.customers.models.customer_models import Customer, CustomerTier


class TestRewardsEngine:
    """Test suite for the RewardsEngine service"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def rewards_engine(self, mock_db):
        """Create RewardsEngine instance with mocked DB"""
        return RewardsEngine(mock_db)
    
    @pytest.fixture
    def sample_customer(self):
        """Sample customer for testing"""
        return Customer(
            id=1,
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            tier=CustomerTier.BRONZE,
            loyalty_points=100,
            lifetime_points=500,
            total_orders=5,
            total_spent=250.0
        )
    
    @pytest.fixture
    def sample_reward_template(self):
        """Sample reward template for testing"""
        return RewardTemplate(
            id=1,
            name="test_discount",
            title="Test Discount",
            description="Test discount reward",
            reward_type=RewardType.PERCENTAGE_DISCOUNT,
            percentage=10.0,
            max_discount_amount=15.0,
            min_order_amount=20.0,
            max_uses_per_customer=1,
            valid_days=30,
            trigger_type=TriggerType.MANUAL,
            is_active=True,
            eligible_tiers=["bronze", "silver", "gold", "platinum", "vip"]
        )
    
    def test_create_reward_template(self, rewards_engine, mock_db):
        """Test creating a reward template"""
        template_data = {
            "name": "welcome_discount",
            "title": "Welcome Discount",
            "description": "Welcome new customers",
            "reward_type": "percentage_discount",
            "percentage": 10.0,
            "max_discount_amount": 15.0,
            "min_order_amount": 20.0,
            "max_uses_per_customer": 1,
            "valid_days": 30,
            "trigger_type": "manual",
            "is_active": True,
            "eligible_tiers": ["bronze", "silver", "gold"]
        }
        
        # Mock database operations
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Test template creation
        template = rewards_engine.create_reward_template(template_data)
        
        # Assertions
        assert template.name == "welcome_discount"
        assert template.percentage == 10.0
        assert template.is_active == True
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    
    def test_issue_reward_to_customer(self, rewards_engine, mock_db, sample_customer, sample_reward_template):
        """Test issuing a reward to a customer"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_customer,  # Customer lookup
            sample_reward_template  # Template lookup
        ]
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Test reward issuance
        reward = rewards_engine.issue_reward_to_customer(
            customer_id=1,
            template_id=1,
            issued_by=1
        )
        
        # Assertions
        assert reward.customer_id == 1
        assert reward.template_id == 1
        assert reward.status == RewardStatus.AVAILABLE
        assert len(reward.code) == 10  # Default code length
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    
    def test_redeem_reward_success(self, rewards_engine, mock_db, sample_customer):
        """Test successful reward redemption"""
        # Create mock reward
        reward = CustomerReward(
            id=1,
            customer_id=1,
            template_id=1,
            code="TEST123456",
            status=RewardStatus.AVAILABLE,
            reward_type=RewardType.PERCENTAGE_DISCOUNT,
            percentage=10.0,
            max_discount_amount=15.0,
            valid_from=datetime.utcnow() - timedelta(days=1),
            valid_until=datetime.utcnow() + timedelta(days=30)
        )
        
        # Mock order
        mock_order = Mock()
        mock_order.id = 1
        mock_order.customer_id = 1
        mock_order.total = 100.0
        
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            reward,  # Reward lookup
            mock_order  # Order lookup
        ]
        mock_db.add = Mock()
        mock_db.commit = Mock()
        
        # Test redemption
        result = rewards_engine.redeem_reward(
            reward_code="TEST123456",
            order_id=1
        )
        
        # Assertions
        assert result["success"] == True
        assert result["discount_amount"] == 10.0  # 10% of 100
        assert reward.status == RewardStatus.REDEEMED
        mock_db.commit.assert_called()
    
    def test_redeem_reward_expired(self, rewards_engine, mock_db):
        """Test redemption of expired reward"""
        # Create expired reward
        expired_reward = CustomerReward(
            id=1,
            customer_id=1,
            template_id=1,
            code="EXPIRED123",
            status=RewardStatus.AVAILABLE,
            reward_type=RewardType.PERCENTAGE_DISCOUNT,
            percentage=10.0,
            valid_from=datetime.utcnow() - timedelta(days=35),
            valid_until=datetime.utcnow() - timedelta(days=5)  # Expired
        )
        
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = expired_reward
        
        # Test redemption
        result = rewards_engine.redeem_reward(
            reward_code="EXPIRED123",
            order_id=1
        )
        
        # Assertions
        assert result["success"] == False
        assert "expired" in result["error"].lower()
    
    def test_process_order_completion(self, rewards_engine, mock_db, sample_customer):
        """Test processing order completion for loyalty rewards"""
        # Mock order
        mock_order = Mock()
        mock_order.id = 1
        mock_order.customer_id = 1
        mock_order.total = 50.0
        mock_order.order_items = [
            Mock(price=25.0, quantity=1),
            Mock(price=25.0, quantity=1)
        ]
        
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_order,  # Order lookup
            sample_customer  # Customer lookup
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = []  # No templates
        mock_db.add = Mock()
        mock_db.commit = Mock()
        
        # Mock loyalty service
        with patch.object(rewards_engine, 'loyalty_service') as mock_loyalty:
            mock_loyalty.calculate_points_earned.return_value = 50
            mock_loyalty.award_points.return_value = True
            mock_loyalty.calculate_tier_for_customer_points.return_value = "bronze"
            
            # Test order processing
            result = rewards_engine.process_order_completion(order_id=1)
        
        # Assertions
        assert result["success"] == True
        assert result["points_earned"] == 50
        mock_loyalty.award_points.assert_called_once()
    
    def test_get_customer_available_rewards(self, rewards_engine, mock_db):
        """Test getting available rewards for a customer"""
        # Create sample rewards
        available_rewards = [
            CustomerReward(
                id=1,
                customer_id=1,
                code="REWARD1",
                status=RewardStatus.AVAILABLE,
                valid_from=datetime.utcnow() - timedelta(days=1),
                valid_until=datetime.utcnow() + timedelta(days=30)
            ),
            CustomerReward(
                id=2,
                customer_id=1,
                code="REWARD2",
                status=RewardStatus.AVAILABLE,
                valid_from=datetime.utcnow() - timedelta(days=1),
                valid_until=datetime.utcnow() + timedelta(days=15)
            )
        ]
        
        # Setup mock
        mock_db.query.return_value.filter.return_value.all.return_value = available_rewards
        
        # Test getting rewards
        rewards = rewards_engine.get_customer_available_rewards(customer_id=1)
        
        # Assertions
        assert len(rewards) == 2
        assert all(r.status == RewardStatus.AVAILABLE for r in rewards)
    
    def test_expire_old_rewards(self, rewards_engine, mock_db):
        """Test expiring old rewards"""
        # Create expired rewards
        expired_rewards = [
            CustomerReward(
                id=1,
                customer_id=1,
                status=RewardStatus.AVAILABLE,
                valid_until=datetime.utcnow() - timedelta(days=1)
            ),
            CustomerReward(
                id=2,
                customer_id=2,
                status=RewardStatus.AVAILABLE,
                valid_until=datetime.utcnow() - timedelta(days=5)
            )
        ]
        
        # Setup mock
        mock_db.query.return_value.filter.return_value.all.return_value = expired_rewards
        mock_db.commit = Mock()
        
        # Test expiration
        expired_count = rewards_engine.expire_old_rewards()
        
        # Assertions
        assert expired_count == 2
        assert all(r.status == RewardStatus.EXPIRED for r in expired_rewards)
        mock_db.commit.assert_called_once()


class TestLoyaltyService:
    """Test suite for the LoyaltyService"""
    
    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)
    
    @pytest.fixture
    def loyalty_service(self, mock_db):
        return LoyaltyService(mock_db)
    
    def test_calculate_points_earned(self, loyalty_service):
        """Test points calculation for different actions"""
        # Test order points
        points = loyalty_service.calculate_points_earned(
            action_type="order",
            amount=100.0,
            customer_tier="bronze"
        )
        assert points == 50  # Bronze tier: 0.5x multiplier, 1 point per $1
        
        # Test signup points
        signup_points = loyalty_service.calculate_points_earned(
            action_type="signup",
            customer_tier="bronze"
        )
        assert signup_points == 100  # Default signup bonus
    
    def test_award_points(self, loyalty_service, mock_db):
        """Test awarding points to customer"""
        # Mock customer
        customer = Customer(
            id=1,
            loyalty_points=100,
            lifetime_points=500
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = customer
        mock_db.add = Mock()
        mock_db.commit = Mock()
        
        # Test points award
        result = loyalty_service.award_points(
            customer_id=1,
            points=50,
            reason="Order completion",
            order_id=1
        )
        
        # Assertions
        assert result == True
        assert customer.loyalty_points == 150
        assert customer.lifetime_points == 550
        mock_db.add.assert_called_once()  # Transaction record
        mock_db.commit.assert_called_once()
    
    def test_calculate_tier_for_customer_points(self, loyalty_service):
        """Test tier calculation based on lifetime points"""
        # Test different point levels
        assert loyalty_service.calculate_tier_for_customer_points(500) == "bronze"
        assert loyalty_service.calculate_tier_for_customer_points(1500) == "silver"
        assert loyalty_service.calculate_tier_for_customer_points(3000) == "gold"
        assert loyalty_service.calculate_tier_for_customer_points(7500) == "platinum"
        assert loyalty_service.calculate_tier_for_customer_points(15000) == "vip"


class TestOrderLoyaltyIntegration:
    """Test suite for OrderLoyaltyIntegration"""
    
    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)
    
    @pytest.fixture
    def integration(self, mock_db):
        return OrderLoyaltyIntegration(mock_db)
    
    def test_handle_order_cancellation(self, integration, mock_db):
        """Test handling order cancellation and point reversal"""
        # Mock customer and order
        customer = Customer(id=1, loyalty_points=150, lifetime_points=600)
        mock_order = Mock(id=1, customer_id=1)
        
        # Mock points transaction to reverse
        transaction = LoyaltyPointsTransaction(
            customer_id=1,
            order_id=1,
            transaction_type="earned",
            points_change=50
        )
        
        # Setup mocks
        mock_db.query.return_value.filter.side_effect = [
            Mock(first=Mock(return_value=mock_order)),  # Order query
            Mock(first=Mock(return_value=customer)),     # Customer query
            Mock(all=Mock(return_value=[transaction]))   # Transaction query
        ]
        mock_db.add = Mock()
        mock_db.commit = Mock()
        
        # Test cancellation
        result = integration.handle_order_cancellation(order_id=1)
        
        # Assertions
        assert result["success"] == True
        assert result["points_reversed"] == 50
        assert customer.loyalty_points == 100  # 150 - 50
        mock_db.add.assert_called()  # Reversal transaction added
        mock_db.commit.assert_called_once()
    
    def test_calculate_points_preview(self, integration, mock_db):
        """Test calculating points preview for an order"""
        # Mock customer
        customer = Customer(
            id=1,
            loyalty_points=100,
            lifetime_points=500,
            tier=CustomerTier.BRONZE
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = customer
        
        # Mock loyalty service
        with patch.object(integration.rewards_engine, 'loyalty_service') as mock_loyalty:
            mock_loyalty.calculate_points_earned.return_value = 75
            mock_loyalty.calculate_tier_for_customer_points.return_value = "bronze"
            
            # Test preview calculation
            result = integration.calculate_points_preview(
                customer_id=1,
                order_total=150.0
            )
        
        # Assertions
        assert result["success"] == True
        assert result["points_to_earn"] == 75
        assert result["current_points"] == 100
        assert result["points_after_order"] == 175


class TestRewardAnalytics:
    """Test suite for reward analytics functionality"""
    
    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)
    
    @pytest.fixture
    def rewards_engine(self, mock_db):
        return RewardsEngine(mock_db)
    
    def test_get_reward_analytics(self, rewards_engine, mock_db):
        """Test getting analytics for a reward template"""
        # Mock analytics data
        mock_analytics = Mock()
        mock_analytics.rewards_issued = 100
        mock_analytics.rewards_redeemed = 75
        mock_analytics.rewards_expired = 10
        mock_analytics.total_discount_value = 500.0
        mock_analytics.unique_customers = 60
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_analytics
        
        # Test analytics retrieval
        analytics = rewards_engine.get_reward_analytics(template_id=1)
        
        # Assertions
        assert analytics["rewards_issued"] == 100
        assert analytics["rewards_redeemed"] == 75
        assert analytics["redemption_rate"] == 75.0  # 75/100
        assert analytics["total_discount_value"] == 500.0


class TestChurnRiskCalculation:
    """Test churn risk calculation algorithms"""
    
    def test_calculate_churn_risk_high(self):
        """Test high churn risk calculation"""
        customer_data = {
            "days_since_last_order": 45,
            "order_frequency_decline": 0.6,  # 60% decline
            "engagement_score": 0.2,
            "support_tickets": 3
        }
        
        # This would be implemented in the analytics service
        # For now, testing the logic
        risk_score = (
            (customer_data["days_since_last_order"] / 60) * 0.3 +
            customer_data["order_frequency_decline"] * 0.4 +
            (1 - customer_data["engagement_score"]) * 0.2 +
            min(customer_data["support_tickets"] / 5, 1) * 0.1
        )
        
        assert risk_score > 0.7  # High risk threshold
    
    def test_calculate_churn_risk_low(self):
        """Test low churn risk calculation"""
        customer_data = {
            "days_since_last_order": 5,
            "order_frequency_decline": 0.1,  # 10% decline
            "engagement_score": 0.9,
            "support_tickets": 0
        }
        
        risk_score = (
            (customer_data["days_since_last_order"] / 60) * 0.3 +
            customer_data["order_frequency_decline"] * 0.4 +
            (1 - customer_data["engagement_score"]) * 0.2 +
            min(customer_data["support_tickets"] / 5, 1) * 0.1
        )
        
        assert risk_score < 0.3  # Low risk threshold


# Integration test helpers
@pytest.fixture
def test_database():
    """Create test database session"""
    # This would be implemented with your test database setup
    pass


@pytest.fixture
def sample_test_data():
    """Create sample test data for integration tests"""
    return {
        "customers": [
            {"id": 1, "email": "test1@example.com", "tier": "bronze"},
            {"id": 2, "email": "test2@example.com", "tier": "silver"},
        ],
        "reward_templates": [
            {"id": 1, "name": "welcome_discount", "reward_type": "percentage_discount"},
            {"id": 2, "name": "birthday_special", "reward_type": "fixed_discount"},
        ]
    }


# Performance test examples
class TestPerformance:
    """Performance tests for loyalty system"""
    
    def test_bulk_reward_issuance_performance(self):
        """Test performance of bulk reward issuance"""
        # This would test issuing rewards to many customers
        # and ensure it completes within acceptable time limits
        pass
    
    def test_analytics_query_performance(self):
        """Test performance of analytics queries"""
        # This would test complex analytics queries
        # and ensure they complete within acceptable time limits
        pass


if __name__ == "__main__":
    pytest.main([__file__])