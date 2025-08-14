"""
Integration tests for Customer Lifetime Value with refund handling.

This module tests the integration between order processing, refunds,
and CLV calculation to ensure data consistency.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from modules.customers.models.customer_models import Customer, CustomerTier
from modules.orders.models.order_models import Order, OrderItem
from modules.loyalty.services.order_integration import OrderLoyaltyIntegration
from modules.customers.services.order_history_service import OrderHistoryService
from modules.customers.services.customer_service import CustomerService


class TestCLVRefundIntegration:
    """Integration tests for CLV calculation with refunds"""
    
    @pytest.fixture
    def services(self, db: Session):
        """Create all required services"""
        return {
            'loyalty': OrderLoyaltyIntegration(db),
            'order_history': OrderHistoryService(db),
            'customer': CustomerService(db)
        }
    
    @pytest.fixture
    def test_customer(self, db: Session):
        """Create a test customer with initial data"""
        customer = Customer(
            first_name="Jane",
            last_name="Doe",
            email="jane.doe@example.com",
            phone="5551234567",
            tier=CustomerTier.SILVER,
            loyalty_points=100,
            lifetime_points=100,
            total_spent=0.0,
            lifetime_value=0,
            total_orders=0
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)
        return customer
    
    def create_order(self, db: Session, customer_id: int, items_data: list, status: str = "completed"):
        """Helper to create an order with items"""
        order = Order(
            customer_id=customer_id,
            status=status,
            created_at=datetime.utcnow()
        )
        db.add(order)
        db.commit()
        
        total = 0
        for item_data in items_data:
            item = OrderItem(
                order_id=order.id,
                menu_item_id=item_data.get('menu_item_id', 1),
                quantity=item_data['quantity'],
                price=item_data['price']
            )
            db.add(item)
            total += item.quantity * item.price
        
        db.commit()
        db.refresh(order)
        return order, total
    
    def test_clv_consistency_across_services(
        self,
        db: Session,
        test_customer: Customer,
        services: dict
    ):
        """Test that CLV remains consistent across different service operations"""
        # Create first order ($200)
        order1, total1 = self.create_order(
            db, 
            test_customer.id,
            [
                {'quantity': 2, 'price': 50.00},
                {'quantity': 1, 'price': 100.00}
            ]
        )
        
        # Process order and update stats
        services['loyalty'].process_order_completion(order1.id)
        services['order_history'].update_customer_order_stats(test_customer.id)
        
        db.refresh(test_customer)
        assert test_customer.total_spent == 200.0
        assert test_customer.lifetime_value == 200.0
        assert test_customer.total_orders == 1
        
        # Create second order ($150)
        order2, total2 = self.create_order(
            db,
            test_customer.id,
            [
                {'quantity': 3, 'price': 50.00}
            ]
        )
        
        services['loyalty'].process_order_completion(order2.id)
        services['order_history'].update_customer_order_stats(test_customer.id)
        
        db.refresh(test_customer)
        assert test_customer.total_spent == 350.0
        assert test_customer.lifetime_value == 350.0
        assert test_customer.total_orders == 2
        
        # Partial refund on first order ($75)
        services['loyalty'].handle_partial_refund(order1.id, 75.0)
        
        db.refresh(test_customer)
        assert test_customer.total_spent == 275.0
        assert test_customer.lifetime_value == 275.0
        
        # Create third order ($100)
        order3, total3 = self.create_order(
            db,
            test_customer.id,
            [
                {'quantity': 2, 'price': 50.00}
            ]
        )
        
        services['loyalty'].process_order_completion(order3.id)
        services['order_history'].update_customer_order_stats(test_customer.id)
        
        db.refresh(test_customer)
        # Total spent recalculated: $200 + $150 + $100 = $450
        assert test_customer.total_spent == 450.0
        # Lifetime value preserves refund: $450 - $75 = $375
        assert test_customer.lifetime_value == 375.0
        assert test_customer.total_orders == 3
        
        # Another partial refund on second order ($50)
        services['loyalty'].handle_partial_refund(order2.id, 50.0)
        
        db.refresh(test_customer)
        assert test_customer.lifetime_value == 325.0  # $375 - $50
        
        # Final stats update should preserve all refunds
        services['order_history'].update_customer_order_stats(test_customer.id)
        
        db.refresh(test_customer)
        assert test_customer.total_spent == 450.0  # Sum of all orders
        assert test_customer.lifetime_value == 325.0  # $450 - $75 - $50
    
    def test_clv_with_order_status_changes(
        self,
        db: Session,
        test_customer: Customer,
        services: dict
    ):
        """Test CLV calculation when order status changes"""
        # Create order in pending status
        order, total = self.create_order(
            db,
            test_customer.id,
            [{'quantity': 1, 'price': 100.00}],
            status="pending"
        )
        
        # Update stats - pending order shouldn't count
        services['order_history'].update_customer_order_stats(test_customer.id)
        
        db.refresh(test_customer)
        assert test_customer.total_spent == 0.0
        assert test_customer.lifetime_value == 0.0
        assert test_customer.total_orders == 0
        
        # Complete the order
        order.status = "completed"
        db.commit()
        
        services['loyalty'].process_order_completion(order.id)
        services['order_history'].update_customer_order_stats(test_customer.id)
        
        db.refresh(test_customer)
        assert test_customer.total_spent == 100.0
        assert test_customer.lifetime_value == 100.0
        assert test_customer.total_orders == 1
        
        # Partial refund
        services['loyalty'].handle_partial_refund(order.id, 30.0)
        
        db.refresh(test_customer)
        assert test_customer.lifetime_value == 70.0
        
        # Change order to cancelled status (soft delete)
        order.status = "cancelled"
        order.deleted_at = datetime.utcnow()
        db.commit()
        
        # Update stats - cancelled order shouldn't count
        services['order_history'].update_customer_order_stats(test_customer.id)
        
        db.refresh(test_customer)
        assert test_customer.total_spent == 0.0  # No completed orders
        assert test_customer.lifetime_value == -30.0  # Preserves the refund adjustment
    
    def test_clv_calculation_performance(
        self,
        db: Session,
        test_customer: Customer,
        services: dict
    ):
        """Test CLV calculation performance with many orders and refunds"""
        import time
        
        start_time = time.time()
        
        # Create 50 orders
        order_ids = []
        for i in range(50):
            order, _ = self.create_order(
                db,
                test_customer.id,
                [{'quantity': 1, 'price': 10.00 + i}]
            )
            order_ids.append(order.id)
        
        # Process all orders
        for order_id in order_ids:
            services['loyalty'].process_order_completion(order_id)
        
        # Update stats once
        services['order_history'].update_customer_order_stats(test_customer.id)
        
        # Apply refunds to every 5th order
        refund_total = 0
        for i, order_id in enumerate(order_ids):
            if i % 5 == 0:
                refund_amount = 5.0
                services['loyalty'].handle_partial_refund(order_id, refund_amount)
                refund_total += refund_amount
        
        # Final stats update
        services['order_history'].update_customer_order_stats(test_customer.id)
        
        end_time = time.time()
        
        db.refresh(test_customer)
        
        # Verify calculations
        expected_total = sum(10.00 + i for i in range(50))
        assert test_customer.total_spent == expected_total
        assert test_customer.lifetime_value == expected_total - refund_total
        assert test_customer.total_orders == 50
        
        # Performance check
        assert end_time - start_time < 5.0  # Should complete in under 5 seconds
    
    def test_concurrent_refund_handling(
        self,
        db: Session,
        test_customer: Customer,
        services: dict
    ):
        """Test handling of concurrent refunds on the same customer"""
        # Create a large order
        order, total = self.create_order(
            db,
            test_customer.id,
            [{'quantity': 10, 'price': 100.00}]  # $1000 order
        )
        
        services['loyalty'].process_order_completion(order.id)
        services['order_history'].update_customer_order_stats(test_customer.id)
        
        db.refresh(test_customer)
        assert test_customer.lifetime_value == 1000.0
        
        # Simulate concurrent refunds (in practice these would be in separate transactions)
        refunds = [100.0, 150.0, 200.0, 50.0]  # Total: $500
        
        for refund_amount in refunds:
            services['loyalty'].handle_partial_refund(order.id, refund_amount)
        
        db.refresh(test_customer)
        
        # Verify final state
        assert test_customer.lifetime_value == 500.0  # $1000 - $500
        
        # Stats update should preserve all refunds
        services['order_history'].update_customer_order_stats(test_customer.id)
        
        db.refresh(test_customer)
        assert test_customer.total_spent == 1000.0
        assert test_customer.lifetime_value == 500.0