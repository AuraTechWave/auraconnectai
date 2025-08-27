# backend/tests/modules/loyalty/test_loyalty_routes.py

"""
Comprehensive tests for loyalty routes.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta, date
from unittest.mock import Mock, patch, MagicMock

from main import app
from core.rbac_models import RBACUser as User
from modules.loyalty.models.rewards_models import (
    RewardTemplate, CustomerReward, LoyaltyPointsTransaction,
    RewardType, RewardStatus
)
from core.database import get_db


@pytest.fixture
def client():
    """Test client for API requests"""
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Mock database session"""
    db = Mock()
    return db


@pytest.fixture
def auth_headers():
    """Mock authentication headers"""
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def mock_current_user():
    """Mock authenticated user"""
    user = Mock(spec=User)
    user.id = 1
    user.email = "admin@example.com"
    user.role = "admin"
    return user


class TestCustomerLoyaltyRoutes:
    """Test customer loyalty endpoints"""
    
    @patch('modules.loyalty.routes.loyalty_routes.get_current_user')
    @patch('modules.loyalty.routes.loyalty_routes.get_db')
    @patch('modules.loyalty.routes.loyalty_routes.LoyaltyService')
    def test_get_customer_loyalty_stats(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test GET /api/v1/loyalty/customers/{customer_id}/loyalty"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_stats = {
            "customer_id": 1,
            "points_balance": 500,
            "lifetime_points_earned": 1500,
            "lifetime_points_spent": 1000,
            "current_tier": "silver",
            "tier_benefits": ["1.2x points earning", "Birthday bonus"],
            "rewards_earned": 10,
            "rewards_redeemed": 7,
            "member_since": date.today()
        }
        mock_service.get_customer_loyalty.return_value = mock_stats
        mock_service_class.return_value = mock_service
        
        # Make request
        response = client.get(
            "/api/v1/loyalty/customers/1/loyalty",
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["points_balance"] == 500
        assert data["current_tier"] == "silver"
    
    @patch('modules.loyalty.routes.loyalty_routes.get_current_user')
    @patch('modules.loyalty.routes.loyalty_routes.get_db')
    def test_get_points_history(self, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test GET /api/v1/loyalty/customers/{customer_id}/points/history"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        # Mock transactions
        transactions = [
            Mock(
                id=1,
                points_change=100,
                transaction_type="earned",
                reason="Order #123",
                created_at=datetime.utcnow()
            ),
            Mock(
                id=2,
                points_change=-50,
                transaction_type="redeemed",
                reason="Reward redemption",
                created_at=datetime.utcnow()
            )
        ]
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value.all.return_value = transactions
        mock_db.query.return_value = mock_query
        
        # Make request
        response = client.get(
            "/api/v1/loyalty/customers/1/points/history?days=30",
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        assert len(response.json()) == 2
    
    @patch('modules.loyalty.routes.loyalty_routes.get_current_user')
    @patch('modules.loyalty.routes.loyalty_routes.get_db')
    @patch('modules.loyalty.routes.loyalty_routes.LoyaltyService')
    def test_add_customer_points(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/loyalty/customers/{customer_id}/points/add"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_transaction = Mock(
            id=1,
            customer_id=1,
            points_change=100,
            points_balance_after=600,
            transaction_type="earned"
        )
        mock_service.add_points.return_value = mock_transaction
        mock_service_class.return_value = mock_service
        
        # Request data
        transaction_data = {
            "transaction_type": "earned",
            "points_change": 100,
            "reason": "Manual addition",
            "source": "manual"
        }
        
        # Make request
        response = client.post(
            "/api/v1/loyalty/customers/1/points/add",
            json=transaction_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["points_change"] == 100
    
    @patch('modules.loyalty.routes.loyalty_routes.get_current_user')
    @patch('modules.loyalty.routes.loyalty_routes.get_db')
    @patch('modules.loyalty.routes.loyalty_routes.LoyaltyService')
    def test_adjust_points(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/loyalty/points/adjust"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_transaction = Mock(
            id=1,
            points_change=50,
            transaction_type="adjusted"
        )
        mock_service.adjust_points.return_value = mock_transaction
        mock_service_class.return_value = mock_service
        
        # Request data
        adjustment_data = {
            "customer_id": 1,
            "points": 50,
            "reason": "Customer service compensation",
            "notify_customer": True
        }
        
        # Make request
        response = client.post(
            "/api/v1/loyalty/points/adjust",
            json=adjustment_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["points_change"] == 50
    
    @patch('modules.loyalty.routes.loyalty_routes.get_current_user')
    @patch('modules.loyalty.routes.loyalty_routes.get_db')
    @patch('modules.loyalty.routes.loyalty_routes.LoyaltyService')
    def test_transfer_points(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/loyalty/points/transfer"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_debit = Mock(id=1, points_change=-100)
        mock_credit = Mock(id=2, points_change=100)
        mock_service.transfer_points.return_value = (mock_debit, mock_credit)
        mock_service_class.return_value = mock_service
        
        # Request data
        transfer_data = {
            "from_customer_id": 1,
            "to_customer_id": 2,
            "points": 100,
            "reason": "Family transfer"
        }
        
        # Make request
        response = client.post(
            "/api/v1/loyalty/points/transfer",
            json=transfer_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["points_transferred"] == 100


class TestRewardTemplateRoutes:
    """Test reward template endpoints"""
    
    @patch('modules.loyalty.routes.loyalty_routes.get_current_user')
    @patch('modules.loyalty.routes.loyalty_routes.get_db')
    @patch('modules.loyalty.routes.loyalty_routes.LoyaltyService')
    def test_create_reward_template(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/loyalty/templates"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_template = Mock(
            id=1,
            name="10% Off",
            reward_type=RewardType.PERCENTAGE_DISCOUNT,
            percentage=10,
            points_cost=100
        )
        mock_service.create_reward_template.return_value = mock_template
        mock_service_class.return_value = mock_service
        
        # Request data
        template_data = {
            "name": "10% Off",
            "description": "10% discount on next order",
            "reward_type": "percentage_discount",
            "percentage": 10,
            "points_cost": 100,
            "valid_days": 30
        }
        
        # Make request
        response = client.post(
            "/api/v1/loyalty/templates",
            json=template_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 201
        assert response.json()["name"] == "10% Off"
    
    @patch('modules.loyalty.routes.loyalty_routes.get_current_user')
    @patch('modules.loyalty.routes.loyalty_routes.get_db')
    @patch('modules.loyalty.routes.loyalty_routes.LoyaltyService')
    def test_list_reward_templates(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test GET /api/v1/loyalty/templates"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_templates = [
            Mock(id=1, name="10% Off", reward_type=RewardType.PERCENTAGE_DISCOUNT),
            Mock(id=2, name="Free Item", reward_type=RewardType.FREE_ITEM)
        ]
        mock_service.get_available_templates.return_value = mock_templates
        mock_service._get_customer_points_balance.return_value = 500
        mock_service_class.return_value = mock_service
        
        # Make request
        response = client.get(
            "/api/v1/loyalty/templates?customer_id=1&is_active=true",
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        assert len(response.json()) == 2
    
    @patch('modules.loyalty.routes.loyalty_routes.get_current_user')
    @patch('modules.loyalty.routes.loyalty_routes.get_db')
    def test_get_reward_template(self, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test GET /api/v1/loyalty/templates/{template_id}"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_template = Mock(
            id=1,
            name="20% Off",
            description="20% discount",
            reward_type=RewardType.PERCENTAGE_DISCOUNT
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_template
        
        # Make request
        response = client.get("/api/v1/loyalty/templates/1", headers=auth_headers)
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["name"] == "20% Off"
    
    @patch('modules.loyalty.routes.loyalty_routes.get_current_user')
    @patch('modules.loyalty.routes.loyalty_routes.get_db')
    @patch('modules.loyalty.routes.loyalty_routes.LoyaltyService')
    def test_update_reward_template(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test PUT /api/v1/loyalty/templates/{template_id}"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_updated = Mock(
            id=1,
            name="25% Off",
            percentage=25
        )
        mock_service.update_reward_template.return_value = mock_updated
        mock_service_class.return_value = mock_service
        
        # Update data
        update_data = {
            "name": "25% Off",
            "percentage": 25
        }
        
        # Make request
        response = client.put(
            "/api/v1/loyalty/templates/1",
            json=update_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["percentage"] == 25
    
    @patch('modules.loyalty.routes.loyalty_routes.get_current_user')
    @patch('modules.loyalty.routes.loyalty_routes.get_db')
    def test_delete_reward_template(self, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test DELETE /api/v1/loyalty/templates/{template_id}"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_template = Mock(id=1, is_active=True)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_template
        
        # Make request
        response = client.delete("/api/v1/loyalty/templates/1", headers=auth_headers)
        
        # Verify response
        assert response.status_code == 204
        assert mock_template.is_active == False


class TestCustomerRewardRoutes:
    """Test customer reward endpoints"""
    
    @patch('modules.loyalty.routes.loyalty_routes.get_current_user')
    @patch('modules.loyalty.routes.loyalty_routes.get_db')
    @patch('modules.loyalty.routes.loyalty_routes.LoyaltyService')
    def test_get_customer_rewards(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test GET /api/v1/loyalty/customers/{customer_id}/rewards"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_service._get_customer_rewards_stats.return_value = {
            "earned": 15,
            "redeemed": 10
        }
        mock_service_class.return_value = mock_service
        
        # Mock queries
        mock_db.query.return_value.filter.return_value.count.return_value = 5
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
            (RewardType.PERCENTAGE_DISCOUNT, 3),
            (RewardType.FIXED_DISCOUNT, 2)
        ]
        mock_db.query.return_value.filter.return_value.scalar.return_value = 250.50
        
        # Make request
        response = client.get(
            "/api/v1/loyalty/customers/1/rewards",
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["customer_id"] == 1
        assert data["available_rewards"] == 5
        assert data["total_rewards_earned"] == 15
    
    @patch('modules.loyalty.routes.loyalty_routes.get_current_user')
    @patch('modules.loyalty.routes.loyalty_routes.get_db')
    @patch('modules.loyalty.routes.loyalty_routes.LoyaltyService')
    def test_search_rewards(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/loyalty/rewards/search"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_rewards = [
            Mock(id=1, title="10% Off"),
            Mock(id=2, title="Free Coffee")
        ]
        mock_service.search_customer_rewards.return_value = (mock_rewards, 2)
        mock_service_class.return_value = mock_service
        
        # Search params
        search_data = {
            "customer_id": 1,
            "status": "available",
            "page": 1,
            "limit": 10
        }
        
        # Make request
        response = client.post(
            "/api/v1/loyalty/rewards/search",
            json=search_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 2
    
    @patch('modules.loyalty.routes.loyalty_routes.get_current_user')
    @patch('modules.loyalty.routes.loyalty_routes.get_db')
    @patch('modules.loyalty.routes.loyalty_routes.LoyaltyService')
    def test_issue_manual_reward(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/loyalty/rewards/issue/manual"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_reward = Mock(
            id=1,
            customer_id=1,
            code="REWARD123",
            title="10% Off"
        )
        mock_service.issue_manual_reward.return_value = mock_reward
        mock_service_class.return_value = mock_service
        
        # Request data
        issuance_data = {
            "customer_id": 1,
            "template_id": 1,
            "reason": "Customer appreciation",
            "notify_customer": True
        }
        
        # Make request
        response = client.post(
            "/api/v1/loyalty/rewards/issue/manual",
            json=issuance_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["code"] == "REWARD123"
    
    @patch('modules.loyalty.routes.loyalty_routes.get_current_user')
    @patch('modules.loyalty.routes.loyalty_routes.get_db')
    @patch('modules.loyalty.routes.loyalty_routes.LoyaltyService')
    def test_issue_bulk_rewards(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/loyalty/rewards/issue/bulk"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_rewards = [
            Mock(id=1, code="CODE1"),
            Mock(id=2, code="CODE2"),
            Mock(id=3, code="CODE3")
        ]
        mock_service.issue_bulk_rewards.return_value = mock_rewards
        mock_service_class.return_value = mock_service
        
        # Request data
        bulk_data = {
            "template_id": 1,
            "customer_ids": [1, 2, 3],
            "reason": "Holiday promotion",
            "notify_customers": True
        }
        
        # Make request
        response = client.post(
            "/api/v1/loyalty/rewards/issue/bulk",
            json=bulk_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["rewards_issued"] == 3


class TestRewardRedemptionRoutes:
    """Test reward redemption endpoints"""
    
    @patch('modules.loyalty.routes.loyalty_routes.get_current_user')
    @patch('modules.loyalty.routes.loyalty_routes.get_db')
    @patch('modules.loyalty.routes.loyalty_routes.LoyaltyService')
    def test_validate_reward(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/loyalty/rewards/validate"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_validation = {
            "is_valid": True,
            "reward_type": "percentage_discount",
            "discount_amount": 10.00,
            "validation_errors": []
        }
        mock_service.validate_reward.return_value = mock_validation
        mock_service_class.return_value = mock_service
        
        # Request data
        validation_data = {
            "reward_code": "REWARD123",
            "order_amount": 100.00
        }
        
        # Make request
        response = client.post(
            "/api/v1/loyalty/rewards/validate",
            json=validation_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] == True
        assert data["discount_amount"] == 10.00
    
    @patch('modules.loyalty.routes.loyalty_routes.get_current_user')
    @patch('modules.loyalty.routes.loyalty_routes.get_db')
    @patch('modules.loyalty.routes.loyalty_routes.LoyaltyService')
    def test_redeem_reward(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/loyalty/rewards/redeem"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_redemption = {
            "success": True,
            "reward_id": 1,
            "discount_amount": 15.00,
            "final_order_amount": 85.00,
            "message": "Reward redeemed successfully",
            "redemption_id": 1
        }
        mock_service.redeem_reward.return_value = mock_redemption
        mock_service_class.return_value = mock_service
        
        # Request data
        redemption_data = {
            "reward_code": "REWARD123",
            "order_id": 123,
            "order_amount": 100.00
        }
        
        # Make request
        response = client.post(
            "/api/v1/loyalty/rewards/redeem",
            json=redemption_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["discount_amount"] == 15.00


class TestOrderIntegrationRoutes:
    """Test order integration endpoints"""
    
    @patch('modules.loyalty.routes.loyalty_routes.get_current_user')
    @patch('modules.loyalty.routes.loyalty_routes.get_db')
    @patch('modules.loyalty.routes.loyalty_routes.LoyaltyService')
    def test_process_order_completion(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/loyalty/orders/complete"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_result = {
            "points_earned": 100,
            "rewards_triggered": [
                {"reward_id": 1, "title": "10% Off", "code": "CODE123"}
            ],
            "tier_progress": {
                "current_tier": "silver",
                "points_to_next_tier": 500,
                "progress_percentage": 50
            },
            "notifications_sent": True
        }
        mock_service.process_order_completion.return_value = mock_result
        mock_service_class.return_value = mock_service
        
        # Request data
        order_data = {
            "customer_id": 1,
            "order_id": 123,
            "order_amount": 100.00,
            "items_purchased": ["item1", "item2"]
        }
        
        # Make request
        response = client.post(
            "/api/v1/loyalty/orders/complete",
            json=order_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["points_earned"] == 100
        assert len(data["rewards_triggered"]) == 1


class TestCampaignRoutes:
    """Test campaign endpoints"""
    
    @patch('modules.loyalty.routes.loyalty_routes.get_current_user')
    @patch('modules.loyalty.routes.loyalty_routes.get_db')
    def test_create_campaign(self, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/loyalty/campaigns"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        # Mock template exists
        mock_template = Mock(id=1, is_active=True)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_template
        
        # Request data
        campaign_data = {
            "name": "Summer Campaign",
            "description": "Summer rewards campaign",
            "template_id": 1,
            "start_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            "end_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            "is_automated": True
        }
        
        # Make request
        response = client.post(
            "/api/v1/loyalty/campaigns",
            json=campaign_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 201
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    
    @patch('modules.loyalty.routes.loyalty_routes.get_current_user')
    @patch('modules.loyalty.routes.loyalty_routes.get_db')
    def test_list_campaigns(self, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test GET /api/v1/loyalty/campaigns"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        # Mock campaigns
        mock_campaigns = [
            Mock(
                id=1,
                name="Campaign 1",
                is_active=True,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=30)
            ),
            Mock(
                id=2,
                name="Campaign 2",
                is_active=False,
                start_date=datetime.utcnow() - timedelta(days=60),
                end_date=datetime.utcnow() - timedelta(days=30)
            )
        ]
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.all.return_value = mock_campaigns
        mock_db.query.return_value = mock_query
        
        # Make request
        response = client.get(
            "/api/v1/loyalty/campaigns?is_active=true",
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        assert len(response.json()) == 2


class TestAnalyticsRoutes:
    """Test analytics endpoints"""
    
    @patch('modules.loyalty.routes.loyalty_routes.get_current_user')
    @patch('modules.loyalty.routes.loyalty_routes.get_db')
    def test_get_reward_analytics(self, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/loyalty/analytics/rewards"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        # Request data
        analytics_request = {
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=30)).isoformat(),
            "group_by": "reward_type"
        }
        
        # Make request
        response = client.post(
            "/api/v1/loyalty/analytics/rewards",
            json=analytics_request,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert data["summary"]["total_rewards_issued"] == 150
    
    @patch('modules.loyalty.routes.loyalty_routes.get_current_user')
    @patch('modules.loyalty.routes.loyalty_routes.get_db')
    def test_get_program_analytics(self, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test GET /api/v1/loyalty/analytics/program/{program_id}"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        # Make request
        response = client.get(
            f"/api/v1/loyalty/analytics/program/1?start_date={date.today()}&end_date={date.today()}",
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["program_id"] == 1
        assert "member_statistics" in data
        assert "points_statistics" in data
        assert "tier_distribution" in data


def test_loyalty_permissions():
    """Test that routes require proper permissions"""
    client = TestClient(app)
    
    # Test without auth header
    response = client.get("/api/v1/loyalty/customers/1/loyalty")
    assert response.status_code == 401
    
    response = client.post("/api/v1/loyalty/templates", json={})
    assert response.status_code == 401
    
    response = client.post("/api/v1/loyalty/rewards/redeem", json={})
    assert response.status_code == 401


def test_loyalty_error_handling():
    """Test error handling in loyalty routes"""
    client = TestClient(app)
    
    # Test with invalid reward type
    with patch('modules.loyalty.routes.loyalty_routes.get_current_user'):
        with patch('modules.loyalty.routes.loyalty_routes.get_db'):
            response = client.post(
                "/api/v1/loyalty/campaigns",
                json={
                    "name": "Test",
                    "start_date": date.today().isoformat(),
                    "end_date": (date.today() - timedelta(days=1)).isoformat()  # End before start
                },
                headers={"Authorization": "Bearer test"}
            )
            
            # Should return validation error
            assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__])