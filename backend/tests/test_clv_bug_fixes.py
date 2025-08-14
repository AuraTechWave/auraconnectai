"""
Unit tests specifically for the CLV bug fixes.

Tests the two specific bugs:
1. Refund metrics only updating when points are reversed
2. CLV calculation overwriting refund adjustments
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from decimal import Decimal


class TestCLVBugFixes:
    """Test the specific CLV bug fixes"""
    
    def test_bug1_refund_updates_without_points(self):
        """
        Bug 1: Test that lifetime_value and total_spent are updated
        even when no loyalty points need to be reversed.
        """
        # Import the class we're testing
        from modules.loyalty.services.order_integration import OrderLoyaltyIntegration
        
        # Create mock database session
        mock_db = Mock()
        
        # Create mock customer with initial values
        mock_customer = Mock()
        mock_customer.id = 1
        mock_customer.total_spent = 100.0
        mock_customer.lifetime_value = 100.0
        mock_customer.loyalty_points = 0  # No points to reverse
        mock_customer.lifetime_points = 0
        
        # Create mock order
        mock_order = Mock()
        mock_order.id = 123
        mock_order.customer_id = 1
        mock_order.order_items = []
        
        # Mock query chain
        mock_db.query().filter().first.side_effect = [mock_order, mock_customer]
        
        # Mock empty points transactions (no points to reverse)
        mock_db.query().filter().all.return_value = []
        
        # Create service and test
        service = OrderLoyaltyIntegration(mock_db)
        result = service.handle_partial_refund(order_id=123, refund_amount=30.0)
        
        # Verify the bug fix: only lifetime_value should be updated, NOT total_spent
        # even though no points were reversed
        assert mock_customer.total_spent == 100.0  # Should remain unchanged
        assert mock_customer.lifetime_value == 70.0  # 100 - 30
        assert result["success"] is True
        assert result["points_adjusted"] == 0
        
        # Verify commit was called
        mock_db.commit.assert_called_once()
    
    def test_bug2_clv_preserves_refund_adjustments(self):
        """
        Bug 2: Test that update_customer_order_stats preserves
        refund adjustments instead of overwriting lifetime_value.
        """
        from modules.customers.services.order_history_service import OrderHistoryService
        
        # Create mock database session
        mock_db = Mock()
        
        # Create mock customer with refund adjustments
        # total_spent: 150 (from orders)
        # lifetime_value: 120 (after $30 in refunds)
        mock_customer = Mock()
        mock_customer.id = 1
        mock_customer.total_spent = 150.0
        mock_customer.lifetime_value = 120.0  # $30 less due to refunds
        mock_customer.total_orders = 0
        
        # Mock the query for customer
        mock_db.query().filter().first.return_value = mock_customer
        
        # Mock order statistics query
        # This simulates recalculating from completed orders
        mock_stats = Mock()
        mock_stats.total_orders = 3
        mock_stats.total_spent = 180.0  # New total from orders
        mock_stats.first_order_date = Mock()
        mock_stats.last_order_date = Mock()
        
        # Setup the complex query chain for statistics
        mock_db.query().filter().first.return_value = mock_stats
        
        # Create service and test
        service = OrderHistoryService(mock_db)
        result = service.update_customer_order_stats(customer_id=1)
        
        # Verify the bug fix: lifetime_value should preserve the $30 refund adjustment
        # Refund adjustment was: 120 - 150 = -30
        # New lifetime_value should be: 180 + (-30) = 150
        assert mock_customer.total_spent == 180.0  # Updated from orders
        assert mock_customer.lifetime_value == 150.0  # Preserves $30 refund
        assert mock_customer.total_orders == 3
        
        # Verify commit was called
        mock_db.commit.assert_called_once()
    
    def test_refund_never_goes_negative(self):
        """Test that CLV and total_spent never go below zero"""
        from modules.loyalty.services.order_integration import OrderLoyaltyIntegration
        
        mock_db = Mock()
        
        # Customer with small balance
        mock_customer = Mock()
        mock_customer.id = 1
        mock_customer.total_spent = 20.0
        mock_customer.lifetime_value = 20.0
        mock_customer.loyalty_points = 10
        mock_customer.lifetime_points = 10
        
        mock_order = Mock()
        mock_order.id = 123
        mock_order.customer_id = 1
        mock_order.order_items = []
        
        mock_db.query().filter().first.side_effect = [mock_order, mock_customer]
        mock_db.query().filter().all.return_value = []
        
        service = OrderLoyaltyIntegration(mock_db)
        # Try to refund more than the current values
        result = service.handle_partial_refund(order_id=123, refund_amount=50.0)
        
        # Only lifetime_value should be affected, and clamped to zero
        assert mock_customer.total_spent == 20.0  # Should remain unchanged
        assert mock_customer.lifetime_value == 0.0  # Clamped to zero
        assert result["success"] is True
    
    def test_clv_calculation_with_multiple_refunds(self):
        """Test CLV calculation correctly handles multiple refunds"""
        from modules.customers.services.order_history_service import OrderHistoryService
        
        mock_db = Mock()
        
        # Customer with multiple refunds applied
        # Original orders total: 500
        # Refunds applied: 75 + 25 = 100
        # Current state: total_spent=500, lifetime_value=400
        mock_customer = Mock()
        mock_customer.id = 1
        mock_customer.total_spent = 500.0
        mock_customer.lifetime_value = 400.0
        mock_customer.total_orders = 5
        
        mock_db.query().filter().first.return_value = mock_customer
        
        # New order stats (e.g., after a new order)
        mock_stats = Mock()
        mock_stats.total_orders = 6
        mock_stats.total_spent = 600.0  # Added a $100 order
        mock_stats.first_order_date = Mock()
        mock_stats.last_order_date = Mock()
        
        mock_db.query().filter().first.return_value = mock_stats
        
        service = OrderHistoryService(mock_db)
        result = service.update_customer_order_stats(customer_id=1)
        
        # Should preserve the $100 in total refunds
        # Refund adjustment: 400 - 500 = -100
        # New lifetime_value: 600 + (-100) = 500
        assert mock_customer.total_spent == 600.0
        assert mock_customer.lifetime_value == 500.0
        assert mock_customer.average_order_value == 100.0  # 600 / 6
    
    def test_null_lifetime_value_handling(self):
        """Test handling of customers with null lifetime_value"""
        from modules.loyalty.services.order_integration import OrderLoyaltyIntegration
        
        mock_db = Mock()
        
        # Customer with null lifetime_value (existing customer)
        mock_customer = Mock()
        mock_customer.id = 1
        mock_customer.total_spent = 150.0
        mock_customer.lifetime_value = None  # Null value
        mock_customer.loyalty_points = 100
        
        mock_order = Mock()
        mock_order.id = 123
        mock_order.customer_id = 1
        mock_order.order_items = []
        
        mock_db.query().filter().first.side_effect = [mock_order, mock_customer]
        mock_db.query().filter().all.return_value = []
        
        service = OrderLoyaltyIntegration(mock_db)
        result = service.handle_partial_refund(order_id=123, refund_amount=30.0)
        
        # Should initialize lifetime_value from total_spent, then apply refund
        assert mock_customer.total_spent == 150.0  # Unchanged
        assert mock_customer.lifetime_value == 120.0  # 150 - 30
        assert result["success"] is True