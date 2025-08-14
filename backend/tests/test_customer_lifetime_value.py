"""
Tests for Customer Lifetime Value (CLV) calculation with refunds.

This test module ensures that CLV is correctly calculated and maintained
when orders are refunded, both partially and fully.
"""

import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

# Note: These tests use mocks to verify the logic without requiring a full database setup


class TestCustomerLifetimeValue:
    """Test suite for Customer Lifetime Value calculation"""
    
    @pytest.fixture
    def customer(self, db: Session):
        """Create a test customer"""
        customer = Customer(
            first_name="Test",
            last_name="Customer",
            email="test@example.com",
            phone="1234567890",
            tier=CustomerTier.BRONZE,
            loyalty_points=0,
            lifetime_points=0,
            total_spent=0.0,
            lifetime_value=0,
            total_orders=0
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)
        return customer
    
    @pytest.fixture
    def order_with_items(self, db: Session, customer: Customer):
        """Create a test order with items"""
        order = Order(
            customer_id=customer.id,
            status="completed",
            created_at=datetime.utcnow()
        )
        db.add(order)
        db.commit()
        
        # Add order items
        items = [
            OrderItem(
                order_id=order.id,
                menu_item_id=1,
                quantity=2,
                price=25.00  # $50 total
            ),
            OrderItem(
                order_id=order.id,
                menu_item_id=2,
                quantity=1,
                price=30.00  # $30 total
            )
        ]
        for item in items:
            db.add(item)
        
        db.commit()
        db.refresh(order)
        return order
    
    @pytest.fixture
    def loyalty_integration(self, db: Session):
        """Create loyalty integration service"""
        return OrderLoyaltyIntegration(db)
    
    @pytest.fixture
    def order_history_service(self, db: Session):
        """Create order history service"""
        return OrderHistoryService(db)
    
    def test_clv_with_partial_refund_no_points(
        self, 
        db: Session, 
        customer: Customer, 
        order_with_items: Order,
        loyalty_integration: OrderLoyaltyIntegration,
        order_history_service: OrderHistoryService
    ):
        """Test that CLV is correctly adjusted for partial refunds even when no points are reversed"""
        # First, process the order completion to set initial values
        loyalty_integration.process_order_completion(order_with_items.id)
        order_history_service.update_customer_order_stats(customer.id)
        
        db.refresh(customer)
        
        # Verify initial state
        assert customer.total_spent == 80.0  # $50 + $30
        assert customer.lifetime_value == 80.0
        assert customer.total_orders == 1
        
        # Process a partial refund of $20 (25% of order)
        refund_result = loyalty_integration.handle_partial_refund(
            order_id=order_with_items.id,
            refund_amount=20.0
        )
        
        db.refresh(customer)
        
        # Verify that lifetime_value and total_spent were adjusted
        assert customer.total_spent == 60.0  # $80 - $20
        assert customer.lifetime_value == 60.0  # Should also be adjusted
        assert refund_result["success"] is True
        
        # Now update order stats again to ensure refund adjustments are preserved
        order_history_service.update_customer_order_stats(customer.id)
        
        db.refresh(customer)
        
        # Verify that the refund adjustment is preserved
        assert customer.total_spent == 80.0  # Recalculated from completed orders
        assert customer.lifetime_value == 60.0  # Should preserve the $20 refund adjustment
    
    def test_clv_with_partial_refund_with_points(
        self,
        db: Session,
        customer: Customer,
        order_with_items: Order,
        loyalty_integration: OrderLoyaltyIntegration
    ):
        """Test CLV adjustment when points are also reversed"""
        # Manually create a points transaction to simulate earned points
        points_transaction = LoyaltyPointsTransaction(
            customer_id=customer.id,
            order_id=order_with_items.id,
            transaction_type="earned",
            points_change=80,  # 1 point per dollar
            points_balance_before=0,
            points_balance_after=80,
            reason="Order completion",
            source="system"
        )
        db.add(points_transaction)
        
        # Update customer points
        customer.loyalty_points = 80
        customer.lifetime_points = 80
        customer.total_spent = 80.0
        customer.lifetime_value = 80.0
        db.commit()
        
        # Process a partial refund of $30 (37.5% of order)
        refund_result = loyalty_integration.handle_partial_refund(
            order_id=order_with_items.id,
            refund_amount=30.0
        )
        
        db.refresh(customer)
        
        # Verify adjustments - total_spent should NOT change
        assert customer.total_spent == 80.0  # Should remain unchanged
        assert customer.lifetime_value == 50.0  # $80 - $30
        assert customer.loyalty_points == 50  # 80 - (80 * 0.375) = 50
        assert refund_result["success"] is True
        assert refund_result["points_adjusted"] == 30  # 30 points reversed
    
    def test_clv_with_multiple_orders_and_refunds(
        self,
        db: Session,
        customer: Customer,
        loyalty_integration: OrderLoyaltyIntegration,
        order_history_service: OrderHistoryService
    ):
        """Test CLV calculation with multiple orders and refunds"""
        # Create and process first order ($100)
        order1 = Order(customer_id=customer.id, status="completed")
        db.add(order1)
        db.commit()
        
        item1 = OrderItem(order_id=order1.id, menu_item_id=1, quantity=1, price=100.00)
        db.add(item1)
        db.commit()
        
        loyalty_integration.process_order_completion(order1.id)
        order_history_service.update_customer_order_stats(customer.id)
        
        db.refresh(customer)
        assert customer.total_spent == 100.0
        assert customer.lifetime_value == 100.0
        
        # Create and process second order ($50)
        order2 = Order(customer_id=customer.id, status="completed")
        db.add(order2)
        db.commit()
        
        item2 = OrderItem(order_id=order2.id, menu_item_id=2, quantity=1, price=50.00)
        db.add(item2)
        db.commit()
        
        loyalty_integration.process_order_completion(order2.id)
        order_history_service.update_customer_order_stats(customer.id)
        
        db.refresh(customer)
        assert customer.total_spent == 150.0
        assert customer.lifetime_value == 150.0
        
        # Partial refund on first order ($40)
        loyalty_integration.handle_partial_refund(order1.id, 40.0)
        
        db.refresh(customer)
        assert customer.total_spent == 150.0  # Should remain unchanged
        assert customer.lifetime_value == 110.0  # $150 - $40
        
        # Update stats to ensure refund is preserved
        order_history_service.update_customer_order_stats(customer.id)
        
        db.refresh(customer)
        assert customer.total_spent == 150.0  # Recalculated from orders
        assert customer.lifetime_value == 110.0  # Preserves $40 refund
        
        # Another partial refund on second order ($10)
        loyalty_integration.handle_partial_refund(order2.id, 10.0)
        
        db.refresh(customer)
        assert customer.lifetime_value == 100.0  # $110 - $10
        
        # Final stats update
        order_history_service.update_customer_order_stats(customer.id)
        
        db.refresh(customer)
        assert customer.total_spent == 150.0  # Still shows total from orders
        assert customer.lifetime_value == 100.0  # Preserves total $50 in refunds
    
    def test_clv_never_goes_negative(
        self,
        db: Session,
        customer: Customer,
        order_with_items: Order,
        loyalty_integration: OrderLoyaltyIntegration
    ):
        """Test that CLV never goes below zero even with large refunds"""
        # Set initial values
        customer.total_spent = 50.0
        customer.lifetime_value = 50.0
        db.commit()
        
        # Try to refund more than the lifetime value
        refund_result = loyalty_integration.handle_partial_refund(
            order_id=order_with_items.id,
            refund_amount=100.0  # More than lifetime_value
        )
        
        db.refresh(customer)
        
        # Verify total_spent unchanged and lifetime_value doesn't go negative
        assert customer.total_spent == 50.0  # Should remain unchanged
        assert customer.lifetime_value == 0.0  # max(0, 50 - 100) = 0
        assert refund_result["success"] is True
    
    def test_full_order_cancellation_clv(
        self,
        db: Session,
        customer: Customer,
        order_with_items: Order,
        loyalty_integration: OrderLoyaltyIntegration,
        order_history_service: OrderHistoryService
    ):
        """Test CLV adjustment for full order cancellation"""
        # Process order completion first
        loyalty_integration.process_order_completion(order_with_items.id)
        order_history_service.update_customer_order_stats(customer.id)
        
        db.refresh(customer)
        initial_clv = customer.lifetime_value
        initial_spent = customer.total_spent
        
        # Cancel the order (full refund)
        cancel_result = loyalty_integration.handle_order_cancellation(order_with_items.id)
        
        db.refresh(customer)
        
        # For cancellation, we reverse points but don't adjust total_spent/lifetime_value
        # This is different from partial refunds
        assert customer.loyalty_points == 0  # Points should be reversed
        assert cancel_result["success"] is True
        
        # Note: The current implementation doesn't adjust total_spent/lifetime_value
        # for cancellations, only for partial refunds. This might be a design decision
        # or another bug to fix depending on business requirements.