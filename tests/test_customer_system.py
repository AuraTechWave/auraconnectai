# tests/test_customer_system.py

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException

from backend.modules.customers.models.customer_models import Customer, CustomerTier, CustomerStatus
from backend.modules.customers.schemas.customer_schemas import CustomerCreate, CustomerUpdate
from backend.modules.customers.services.customer_service import CustomerService, CustomerAuthService
from backend.modules.customers.services.order_history_service import OrderHistoryService
from backend.modules.customers.auth.customer_auth import (
    CustomerAuthService as JWTAuthService, 
    verify_customer_password,
    get_customer_password_hash,
    create_customer_access_token
)


class TestCustomerService:
    """Test cases for CustomerService"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def customer_service(self, mock_db):
        """CustomerService instance with mocked database"""
        return CustomerService(mock_db)
    
    @pytest.fixture
    def sample_customer_data(self):
        """Sample customer creation data"""
        return CustomerCreate(
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            phone="+1234567890",
            password="testpassword123"
        )
    
    @pytest.fixture
    def sample_customer(self):
        """Sample customer model instance"""
        return Customer(
            id=1,
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            phone="+1234567890",
            status=CustomerStatus.ACTIVE,
            tier=CustomerTier.BRONZE,
            loyalty_points=100,
            lifetime_points=500,
            total_orders=5,
            total_spent=250.0,
            average_order_value=50.0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    
    def test_create_customer_success(self, customer_service, mock_db, sample_customer_data, sample_customer):
        """Test successful customer creation"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.return_value = None  # No existing customer
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        with patch('backend.modules.customers.services.customer_service.get_password_hash') as mock_hash:
            mock_hash.return_value = "hashed_password"
            
            # Mock the customer creation
            customer_service._generate_referral_code = Mock(return_value="ABC123")
            customer_service._create_default_preferences = Mock()
            
            # Execute
            result = customer_service.create_customer(sample_customer_data)
            
            # Assertions
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_hash.assert_called_once_with("testpassword123")
    
    def test_create_customer_duplicate_email(self, customer_service, mock_db, sample_customer_data, sample_customer):
        """Test customer creation with duplicate email"""
        # Setup mocks - existing customer found
        mock_db.query.return_value.filter.return_value.first.return_value = sample_customer
        
        # Execute and assert
        with pytest.raises(ValueError, match="already exists"):
            customer_service.create_customer(sample_customer_data)
    
    def test_get_customer_success(self, customer_service, mock_db, sample_customer):
        """Test successful customer retrieval"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = sample_customer
        
        # Execute
        result = customer_service.get_customer(1)
        
        # Assertions
        assert result == sample_customer
        mock_db.query.assert_called_once()
    
    def test_get_customer_not_found(self, customer_service, mock_db):
        """Test customer retrieval when customer doesn't exist"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None
        
        # Execute
        result = customer_service.get_customer(999)
        
        # Assertions
        assert result is None
    
    def test_update_customer_success(self, customer_service, mock_db, sample_customer):
        """Test successful customer update"""
        # Setup mocks
        customer_service.get_customer = Mock(return_value=sample_customer)
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        update_data = CustomerUpdate(first_name="Jane", last_name="Smith")
        
        # Execute
        result = customer_service.update_customer(1, update_data)
        
        # Assertions
        assert result.first_name == "Jane"
        assert result.last_name == "Smith"
        mock_db.commit.assert_called_once()
    
    def test_add_loyalty_points(self, customer_service, mock_db, sample_customer):
        """Test adding loyalty points"""
        # Setup mocks
        customer_service.get_customer = Mock(return_value=sample_customer)
        customer_service._check_tier_upgrade = Mock()
        mock_db.commit = Mock()
        
        initial_points = sample_customer.loyalty_points
        initial_lifetime = sample_customer.lifetime_points
        
        # Execute
        result = customer_service.add_loyalty_points(1, 50, "Order completion")
        
        # Assertions
        assert result.loyalty_points == initial_points + 50
        assert result.lifetime_points == initial_lifetime + 50
        customer_service._check_tier_upgrade.assert_called_once_with(sample_customer)
        mock_db.commit.assert_called_once()
    
    def test_redeem_loyalty_points_success(self, customer_service, mock_db, sample_customer):
        """Test successful loyalty points redemption"""
        # Setup mocks
        customer_service.get_customer = Mock(return_value=sample_customer)
        mock_db.commit = Mock()
        
        initial_points = sample_customer.loyalty_points
        
        # Execute
        result = customer_service.redeem_loyalty_points(1, 50)
        
        # Assertions
        assert result is True
        assert sample_customer.loyalty_points == initial_points - 50
        mock_db.commit.assert_called_once()
    
    def test_redeem_loyalty_points_insufficient(self, customer_service, mock_db, sample_customer):
        """Test loyalty points redemption with insufficient points"""
        # Setup mocks
        sample_customer.loyalty_points = 25  # Less than what we're trying to redeem
        customer_service.get_customer = Mock(return_value=sample_customer)
        
        # Execute and assert
        with pytest.raises(ValueError, match="Insufficient loyalty points"):
            customer_service.redeem_loyalty_points(1, 50)
    
    def test_tier_upgrade_logic(self, customer_service, mock_db, sample_customer):
        """Test loyalty tier upgrade logic"""
        # Setup - customer with enough points for silver
        sample_customer.lifetime_points = 1500
        sample_customer.tier = CustomerTier.BRONZE
        
        with patch('backend.modules.customers.services.customer_service.LoyaltyService') as mock_loyalty_service:
            mock_loyalty_instance = Mock()
            mock_loyalty_service.return_value = mock_loyalty_instance
            mock_loyalty_instance.calculate_tier_for_customer.return_value = "silver"
            
            customer_service._notify_tier_change = Mock()
            
            # Execute
            customer_service._check_tier_upgrade(sample_customer)
            
            # Assertions
            assert sample_customer.tier == CustomerTier.SILVER
            assert sample_customer.tier_updated_at is not None
            customer_service._notify_tier_change.assert_called_once()


class TestOrderHistoryService:
    """Test cases for OrderHistoryService"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def order_history_service(self, mock_db):
        """OrderHistoryService instance with mocked database"""
        return OrderHistoryService(mock_db)
    
    def test_get_customer_orders(self, order_history_service, mock_db):
        """Test getting customer orders"""
        # Setup mock orders
        mock_orders = [Mock(id=1, status="completed"), Mock(id=2, status="pending")]
        mock_db.query.return_value.filter.return_value.count.return_value = 2
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = mock_orders
        
        # Execute
        orders, total = order_history_service.get_customer_orders(1)
        
        # Assertions
        assert len(orders) == 2
        assert total == 2
        mock_db.query.assert_called()
    
    def test_get_order_analytics(self, order_history_service, mock_db):
        """Test order analytics calculation"""
        # Setup mock orders
        mock_orders = [
            Mock(
                created_at=datetime.utcnow() - timedelta(days=30),
                status="completed",
                order_items=[Mock(price=25.0, quantity=2)]
            ),
            Mock(
                created_at=datetime.utcnow() - timedelta(days=15),
                status="completed", 
                order_items=[Mock(price=30.0, quantity=1)]
            )
        ]
        
        mock_db.query.return_value.filter.return_value.all.return_value = mock_orders
        
        # Execute
        analytics = order_history_service.get_order_analytics(1)
        
        # Assertions
        assert analytics["total_orders"] == 2
        assert analytics["total_spent"] == 80.0  # (25*2) + (30*1)
        assert analytics["average_order_value"] == 40.0
        assert "preferred_order_times" in analytics
        assert "monthly_spending" in analytics
    
    def test_update_customer_order_stats(self, order_history_service, mock_db):
        """Test updating customer order statistics"""
        # Setup mocks
        mock_customer = Mock(id=1, total_orders=0, total_spent=0.0)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_customer
        
        # Mock the order stats query
        mock_stats = Mock(
            total_orders=5,
            total_spent=250.0,
            first_order_date=datetime.utcnow() - timedelta(days=30),
            last_order_date=datetime.utcnow()
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_stats
        
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Execute
        result = order_history_service.update_customer_order_stats(1)
        
        # Assertions
        assert mock_customer.total_orders == 5
        assert mock_customer.total_spent == 250.0
        assert mock_customer.average_order_value == 50.0
        mock_db.commit.assert_called_once()


class TestCustomerAuthentication:
    """Test cases for customer authentication"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def auth_service(self, mock_db):
        """CustomerAuthService instance with mocked database"""
        return JWTAuthService(mock_db)
    
    @pytest.fixture
    def sample_customer(self):
        """Sample customer for authentication tests"""
        return Customer(
            id=1,
            email="test@example.com",
            password_hash=get_customer_password_hash("testpassword"),
            status=CustomerStatus.ACTIVE,
            tier=CustomerTier.BRONZE,
            first_name="Test",
            last_name="User",
            loyalty_points=100
        )
    
    def test_password_hashing(self):
        """Test password hashing and verification"""
        password = "testpassword123"
        hashed = get_customer_password_hash(password)
        
        # Assertions
        assert hashed != password  # Should be hashed
        assert verify_customer_password(password, hashed) is True
        assert verify_customer_password("wrongpassword", hashed) is False
    
    def test_jwt_token_creation(self, sample_customer):
        """Test JWT token creation"""
        token_data = {
            "customer_id": sample_customer.id,
            "email": sample_customer.email,
            "tier": sample_customer.tier.value
        }
        
        token = create_customer_access_token(token_data)
        
        # Assertions
        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are typically long
    
    def test_authenticate_customer_success(self, auth_service, mock_db, sample_customer):
        """Test successful customer authentication"""
        # Setup mocks
        auth_service.customer_service.get_customer_by_email = Mock(return_value=sample_customer)
        mock_db.commit = Mock()
        
        # Execute
        result = auth_service.authenticate_customer("test@example.com", "testpassword")
        
        # Assertions
        assert result == sample_customer
        assert sample_customer.last_login is not None
        assert sample_customer.login_count > 0
        mock_db.commit.assert_called_once()
    
    def test_authenticate_customer_invalid_password(self, auth_service, mock_db, sample_customer):
        """Test customer authentication with invalid password"""
        # Setup mocks
        auth_service.customer_service.get_customer_by_email = Mock(return_value=sample_customer)
        
        # Execute
        result = auth_service.authenticate_customer("test@example.com", "wrongpassword")
        
        # Assertions
        assert result is None
    
    def test_authenticate_customer_not_found(self, auth_service, mock_db):
        """Test customer authentication when customer doesn't exist"""
        # Setup mocks
        auth_service.customer_service.get_customer_by_email = Mock(return_value=None)
        
        # Execute
        result = auth_service.authenticate_customer("nonexistent@example.com", "password")
        
        # Assertions
        assert result is None
    
    def test_create_access_token(self, auth_service, sample_customer):
        """Test access token creation"""
        # Execute
        token_response = auth_service.create_access_token(sample_customer)
        
        # Assertions
        assert "access_token" in token_response
        assert "token_type" in token_response
        assert "expires_in" in token_response
        assert "customer" in token_response
        assert token_response["token_type"] == "bearer"
        assert token_response["customer"]["id"] == sample_customer.id
    
    def test_change_password_success(self, auth_service, mock_db, sample_customer):
        """Test successful password change"""
        # Setup mocks
        auth_service.customer_service.get_customer = Mock(return_value=sample_customer)
        mock_db.commit = Mock()
        
        # Execute
        result = auth_service.change_password(1, "testpassword", "newpassword123")
        
        # Assertions
        assert result is True
        assert verify_customer_password("newpassword123", sample_customer.password_hash)
        mock_db.commit.assert_called_once()
    
    def test_change_password_invalid_current(self, auth_service, mock_db, sample_customer):
        """Test password change with invalid current password"""
        # Setup mocks
        auth_service.customer_service.get_customer = Mock(return_value=sample_customer)
        
        # Execute and assert
        with pytest.raises(ValueError, match="Invalid current password"):
            auth_service.change_password(1, "wrongpassword", "newpassword123")


class TestCustomerSearchAndAnalytics:
    """Test cases for customer search and analytics"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def customer_service(self, mock_db):
        """CustomerService instance with mocked database"""
        return CustomerService(mock_db)
    
    def test_search_customers_with_filters(self, customer_service, mock_db):
        """Test customer search with various filters"""
        from backend.modules.customers.schemas.customer_schemas import CustomerSearchParams
        
        # Setup mock data
        mock_customers = [Mock(id=1, email="test1@example.com"), Mock(id=2, email="test2@example.com")]
        
        # Mock the complex query chain
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query  
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_customers
        
        mock_db.query.return_value = mock_query
        
        # Mock count query
        mock_count_query = Mock()
        mock_count_query.filter.return_value = mock_count_query
        mock_count_query.scalar.return_value = 2
        mock_db.query.return_value = mock_count_query
        
        # Create search params
        search_params = CustomerSearchParams(
            query="test",
            tier=["bronze", "silver"],
            page=1,
            page_size=20
        )
        
        # Execute
        customers, total = customer_service.search_customers(search_params)
        
        # Assertions
        assert len(customers) == 2
        assert total == 2
        mock_db.query.assert_called()
    
    def test_get_customer_analytics_optimization(self, customer_service, mock_db):
        """Test customer analytics with query optimization"""
        # Setup mock customer with joinedload
        mock_customer = Mock(
            id=1,
            total_orders=5,
            total_spent=250.0,
            average_order_value=50.0,
            first_order_date=datetime.utcnow() - timedelta(days=30),
            last_order_date=datetime.utcnow() - timedelta(days=5),
            lifetime_points=1000
        )
        
        # Mock the optimized query
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_customer
        mock_db.query.return_value = mock_query
        
        # Mock analytics queries
        mock_db.query.return_value.join.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        # Execute
        analytics = customer_service.get_customer_analytics(1)
        
        # Assertions
        assert analytics.customer_id == 1
        assert analytics.total_orders == 5
        assert analytics.total_spent == 250.0
        assert analytics.average_order_value == 50.0
        assert analytics.churn_risk_score is not None
        
        # Verify joinedload was used
        mock_query.options.assert_called()


# Integration test markers
@pytest.mark.integration
class TestCustomerIntegration:
    """Integration tests for customer system"""
    
    def test_customer_lifecycle(self):
        """Test complete customer lifecycle"""
        # This would test the full flow from registration to orders to analytics
        # In a real integration test, this would use a test database
        pass
    
    def test_loyalty_program_integration(self):
        """Test loyalty program integration"""
        # Test tier upgrades, points earning, and redemption
        pass


# Performance test markers  
@pytest.mark.performance
class TestCustomerPerformance:
    """Performance tests for customer system"""
    
    def test_search_performance_large_dataset(self):
        """Test search performance with large customer dataset"""
        # Mock large dataset and measure query performance
        pass
    
    def test_analytics_performance(self):
        """Test analytics calculation performance"""
        # Test analytics with large order history
        pass


if __name__ == "__main__":
    pytest.main(["-v", __file__])