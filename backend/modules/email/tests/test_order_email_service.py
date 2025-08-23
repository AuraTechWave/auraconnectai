# backend/modules/email/tests/test_order_email_service.py

"""
Unit tests for order email service
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from decimal import Decimal
from modules.email.services.order_email_service import OrderEmailService
from modules.email.schemas.email_schemas import EmailSendRequest


class TestOrderEmailService:
    """Test order email service functionality"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        db = Mock()
        db.query = Mock()
        return db
    
    @pytest.fixture
    def mock_email_service(self):
        """Mock email service"""
        service = Mock()
        service.send_email = AsyncMock()
        return service
    
    @pytest.fixture
    def order_email_service(self, mock_db, mock_email_service):
        """Create order email service instance"""
        with patch('modules.email.services.order_email_service.EmailService', return_value=mock_email_service):
            return OrderEmailService(mock_db)
    
    @pytest.fixture
    def sample_order(self):
        """Sample order with items"""
        order = Mock()
        order.id = 123
        order.order_number = "ORD-2024-0123"
        order.status = "confirmed"
        order.total_amount = Decimal("45.99")
        order.subtotal = Decimal("39.99")
        order.tax_amount = Decimal("3.00")
        order.tip_amount = Decimal("3.00")
        order.created_at = datetime(2024, 1, 15, 10, 30)
        order.order_type = "pickup"
        order.pickup_time = datetime(2024, 1, 15, 11, 0)
        order.special_instructions = "Extra napkins please"
        
        # Mock user
        order.user = Mock()
        order.user.id = 1
        order.user.email = "customer@example.com"
        order.user.first_name = "John"
        order.user.last_name = "Doe"
        
        # Mock restaurant
        order.restaurant = Mock()
        order.restaurant.id = 1
        order.restaurant.name = "Test Restaurant"
        order.restaurant.address = "123 Main St"
        order.restaurant.phone = "(555) 123-4567"
        
        # Mock items
        item1 = Mock()
        item1.id = 1
        item1.quantity = 2
        item1.price = Decimal("12.99")
        item1.menu_item = Mock()
        item1.menu_item.name = "Burger"
        item1.modifiers = []
        
        item2 = Mock()
        item2.id = 2
        item2.quantity = 1
        item2.price = Decimal("14.01")
        item2.menu_item = Mock()
        item2.menu_item.name = "Pizza"
        
        # Mock modifier
        modifier = Mock()
        modifier.modifier = Mock()
        modifier.modifier.name = "Extra Cheese"
        modifier.price = Decimal("2.00")
        item2.modifiers = [modifier]
        
        order.items = [item1, item2]
        
        # Mock payment
        payment = Mock()
        payment.payment_method = "credit_card"
        payment.last_four = "1234"
        order.payments = [payment]
        
        return order
    
    async def test_send_order_confirmation(self, order_email_service, mock_db, mock_email_service, sample_order):
        """Test sending order confirmation email"""
        # Mock order query
        mock_db.query().filter().first.return_value = sample_order
        
        # Mock successful email send
        mock_email_response = Mock()
        mock_email_response.status = "sent"
        mock_email_service.send_email.return_value = mock_email_response
        
        # Send confirmation
        result = await order_email_service.send_order_confirmation(123)
        
        # Verify
        assert result == True
        mock_email_service.send_email.assert_called_once()
        
        # Check email request
        call_args = mock_email_service.send_email.call_args[0][0]
        assert isinstance(call_args, EmailSendRequest)
        assert call_args.to_email == "customer@example.com"
        assert call_args.template_name == "order_confirmation"
        assert call_args.category == "transactional"
        
        # Check variables
        variables = call_args.variables
        assert variables["order_number"] == "ORD-2024-0123"
        assert variables["customer_name"] == "John Doe"
        assert variables["total"] == "45.99"
        assert variables["order_type"] == "pickup"
        assert len(variables["items"]) == 2
        assert variables["items"][0]["name"] == "Burger"
        assert variables["items"][0]["quantity"] == 2
        assert variables["items"][1]["modifiers"] == ["Extra Cheese (+$2.00)"]
    
    async def test_send_order_confirmation_no_user(self, order_email_service, mock_db):
        """Test order confirmation fails without user"""
        # Mock order without user
        order = Mock()
        order.user = None
        mock_db.query().filter().first.return_value = order
        
        result = await order_email_service.send_order_confirmation(123)
        
        assert result == False
    
    async def test_send_order_ready_notification(self, order_email_service, mock_db, mock_email_service, sample_order):
        """Test sending order ready notification"""
        # Mock order query
        mock_db.query().filter().first.return_value = sample_order
        
        # Mock successful email send
        mock_email_response = Mock()
        mock_email_response.status = "sent"
        mock_email_service.send_email.return_value = mock_email_response
        
        # Send notification
        result = await order_email_service.send_order_ready_notification(123)
        
        # Verify
        assert result == True
        
        # Check email request
        call_args = mock_email_service.send_email.call_args[0][0]
        assert call_args.subject == "Your order is ready for pickup!"
        assert call_args.category == "transactional"
        assert call_args.variables["order_number"] == "ORD-2024-0123"
    
    async def test_send_order_cancelled_notification(self, order_email_service, mock_db, mock_email_service, sample_order):
        """Test sending order cancellation notification"""
        # Update order status
        sample_order.status = "cancelled"
        mock_db.query().filter().first.return_value = sample_order
        
        # Mock successful email send
        mock_email_response = Mock()
        mock_email_response.status = "sent"
        mock_email_service.send_email.return_value = mock_email_response
        
        # Send notification
        result = await order_email_service.send_order_cancelled_notification(
            123, 
            reason="Customer requested cancellation"
        )
        
        # Verify
        assert result == True
        
        # Check email request
        call_args = mock_email_service.send_email.call_args[0][0]
        assert "cancelled" in call_args.subject.lower()
        assert call_args.variables["cancellation_reason"] == "Customer requested cancellation"
    
    async def test_send_order_receipt(self, order_email_service, mock_db, mock_email_service, sample_order):
        """Test sending order receipt"""
        # Mock order query
        mock_db.query().filter().first.return_value = sample_order
        
        # Mock successful email send
        mock_email_response = Mock()
        mock_email_response.status = "sent"
        mock_email_service.send_email.return_value = mock_email_response
        
        # Send receipt
        result = await order_email_service.send_order_receipt(123)
        
        # Verify
        assert result == True
        
        # Check email request
        call_args = mock_email_service.send_email.call_args[0][0]
        assert call_args.template_name == "order_receipt"
        assert call_args.variables["payment_method"] == "Credit Card ending in 1234"
        assert call_args.variables["subtotal"] == "39.99"
        assert call_args.variables["tax"] == "3.00"
        assert call_args.variables["tip"] == "3.00"
    
    async def test_email_service_failure(self, order_email_service, mock_db, mock_email_service, sample_order):
        """Test handling email service failure"""
        # Mock order query
        mock_db.query().filter().first.return_value = sample_order
        
        # Mock email service exception
        mock_email_service.send_email.side_effect = Exception("Email service error")
        
        # Should return False on exception
        result = await order_email_service.send_order_confirmation(123)
        
        assert result == False
    
    def test_format_order_items(self, order_email_service, sample_order):
        """Test formatting order items for email"""
        # Access private method for testing
        items = order_email_service._format_order_items(sample_order.items)
        
        assert len(items) == 2
        assert items[0]["name"] == "Burger"
        assert items[0]["quantity"] == 2
        assert items[0]["price"] == "25.98"
        assert items[0]["modifiers"] == []
        
        assert items[1]["name"] == "Pizza"
        assert items[1]["quantity"] == 1
        assert items[1]["price"] == "14.01"
        assert items[1]["modifiers"] == ["Extra Cheese (+$2.00)"]