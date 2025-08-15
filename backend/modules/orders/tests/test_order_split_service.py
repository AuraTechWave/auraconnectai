"""
Comprehensive tests for order splitting functionality.
"""

import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from ..models.order_models import Order, OrderItem, OrderSplit, SplitPayment
from ..schemas.order_split_schemas import (
    OrderSplitRequest,
    OrderItemSplitRequest,
    SplitType,
    PaymentSplitRequest,
    PaymentStatus,
    MergeSplitRequest,
)
from ..services.order_split_service import OrderSplitService
from ..enums.order_enums import OrderStatus
from fastapi import HTTPException


@pytest.fixture
def mock_db():
    """Create a mock database session"""
    db = Mock(spec=Session)
    db.query.return_value = db
    db.filter.return_value = db
    db.first.return_value = None
    db.all.return_value = []
    db.options.return_value = db
    return db


@pytest.fixture
def mock_webhook_service():
    """Create a mock webhook service"""
    service = Mock()
    service.trigger_webhook = Mock()
    return service


@pytest.fixture
def sample_order():
    """Create a sample order for testing"""
    order = Mock(spec=Order)
    order.id = 1
    order.staff_id = 1
    order.customer_id = 1
    order.table_no = 5
    order.status = OrderStatus.PENDING
    order.category_id = 1
    order.subtotal = Decimal("100.00")
    order.tax_amount = Decimal("10.00")
    order.total_amount = Decimal("110.00")
    order.final_amount = Decimal("110.00")
    order.discount_amount = Decimal("0.00")
    order.external_id = "EXT123"
    order.created_at = datetime.utcnow()

    # Add order items
    item1 = Mock(spec=OrderItem)
    item1.id = 1
    item1.menu_item_id = 101
    item1.quantity = 2
    item1.price = Decimal("25.00")
    item1.notes = "No onions"

    item2 = Mock(spec=OrderItem)
    item2.id = 2
    item2.menu_item_id = 102
    item2.quantity = 1
    item2.price = Decimal("50.00")
    item2.notes = None

    order.order_items = [item1, item2]
    return order


class TestOrderSplitValidation:
    """Test order split validation"""

    def test_validate_split_request_success(self, mock_db, sample_order):
        """Test successful split validation"""
        # Setup
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = (
            sample_order
        )
        service = OrderSplitService(mock_db)

        # Create split request
        split_request = OrderSplitRequest(
            split_type=SplitType.TICKET,
            items=[
                OrderItemSplitRequest(item_id=1, quantity=1),
                OrderItemSplitRequest(item_id=2, quantity=1),
            ],
            split_reason="Customer request",
        )

        # Mock item split count
        with patch.object(service, "_get_item_split_count", return_value=0):
            result = service.validate_split_request(1, split_request)

        # Verify
        assert result.can_split is True
        assert len(result.splittable_items) == 2
        assert result.estimated_totals["subtotal"] == Decimal("75.00")
        assert result.estimated_totals["tax_amount"] == Decimal("7.50")
        assert result.estimated_totals["total_amount"] == Decimal("82.50")

    def test_validate_split_request_order_not_found(self, mock_db):
        """Test validation when order not found"""
        # Setup
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = (
            None
        )
        service = OrderSplitService(mock_db)

        split_request = OrderSplitRequest(
            split_type=SplitType.TICKET,
            items=[OrderItemSplitRequest(item_id=1, quantity=1)],
            split_reason="Test",
        )

        # Test
        with pytest.raises(HTTPException) as exc_info:
            service.validate_split_request(999, split_request)

        assert exc_info.value.status_code == 404
        assert "Order 999 not found" in str(exc_info.value.detail)

    def test_validate_split_completed_order(self, mock_db, sample_order):
        """Test validation prevents splitting completed orders"""
        # Setup
        sample_order.status = OrderStatus.COMPLETED
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = (
            sample_order
        )
        service = OrderSplitService(mock_db)

        split_request = OrderSplitRequest(
            split_type=SplitType.TICKET,
            items=[OrderItemSplitRequest(item_id=1, quantity=1)],
            split_reason="Test",
        )

        # Test
        result = service.validate_split_request(1, split_request)

        # Verify
        assert result.can_split is False
        assert "Cannot split order with status" in result.reason


class TestOrderSplitting:
    """Test order splitting operations"""

    @patch("modules.orders.services.order_split_service.WebhookService")
    def test_split_order_by_ticket(self, mock_webhook_class, mock_db, sample_order):
        """Test splitting order by ticket"""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = sample_order
        mock_webhook_service = Mock()
        mock_webhook_class.return_value = mock_webhook_service

        service = OrderSplitService(mock_db)
        service.webhook_service = mock_webhook_service

        split_request = OrderSplitRequest(
            split_type=SplitType.TICKET,
            items=[
                OrderItemSplitRequest(item_id=1, quantity=1),
                OrderItemSplitRequest(item_id=2, quantity=1),
            ],
            split_reason="Kitchen ticket split",
        )

        # Mock validation
        with patch.object(service, "validate_split_request") as mock_validate:
            mock_validate.return_value.can_split = True

            # Mock split implementation
            with patch.object(service, "_split_by_ticket") as mock_split:
                mock_split.return_value = {
                    "split_order_ids": [2, 3],
                    "details": [
                        {"split_order_id": 2, "group_name": "Ticket 1"},
                        {"split_order_id": 3, "group_name": "Ticket 2"},
                    ],
                }

                # Test
                result = service.split_order(1, split_request, 1)

        # Verify
        assert result.success is True
        assert len(result.split_order_ids) == 2
        assert result.parent_order_id == 1
        mock_webhook_service.trigger_webhook.call_count == 2

    @patch("modules.orders.services.order_split_service.WebhookService")
    def test_split_order_by_delivery(self, mock_webhook_class, mock_db, sample_order):
        """Test splitting order for delivery"""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = sample_order
        service = OrderSplitService(mock_db)

        split_request = OrderSplitRequest(
            split_type=SplitType.DELIVERY,
            items=[OrderItemSplitRequest(item_id=1, quantity=2)],
            split_reason="Separate delivery",
            customer_id=2,
            scheduled_time=datetime.utcnow(),
        )

        # Mock validation and split
        with patch.object(service, "validate_split_request") as mock_validate:
            mock_validate.return_value.can_split = True

            with patch.object(service, "_split_by_delivery") as mock_split:
                mock_split.return_value = {
                    "split_order_ids": [2],
                    "details": [{"split_order_id": 2, "delivery_type": "separate"}],
                }

                result = service.split_order(1, split_request, 1)

        assert result.success is True
        assert len(result.split_order_ids) == 1


class TestPaymentSplitting:
    """Test payment splitting functionality"""

    @patch("modules.orders.services.order_split_service.WebhookService")
    def test_split_order_for_payment(self, mock_webhook_class, mock_db, sample_order):
        """Test splitting order for payment"""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = sample_order
        service = OrderSplitService(mock_db)

        payment_request = PaymentSplitRequest(
            splits=[
                {"amount": 55.00, "customer_id": 1, "payment_method": "card"},
                {"amount": 55.00, "customer_id": 2, "payment_method": "cash"},
            ]
        )

        # Test
        result = service.split_order_for_payment(1, payment_request, 1)

        # Verify
        assert result.success is True
        assert len(result.split_order_ids) == 2
        assert result.message == "Payment split into 2 parts"

    def test_split_payment_amount_mismatch(self, mock_db, sample_order):
        """Test payment split with amount mismatch"""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = sample_order
        service = OrderSplitService(mock_db)

        payment_request = PaymentSplitRequest(
            splits=[
                {"amount": 50.00, "customer_id": 1},
                {"amount": 40.00, "customer_id": 2},  # Total 90, but order is 110
            ]
        )

        # Test
        with pytest.raises(HTTPException) as exc_info:
            service.split_order_for_payment(1, payment_request, 1)

        assert exc_info.value.status_code == 400
        assert "do not match order total" in str(exc_info.value.detail)


class TestSplitTracking:
    """Test split order tracking"""

    def test_get_split_summary(self, mock_db, sample_order):
        """Test getting split summary"""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = sample_order

        # Mock splits
        split1 = Mock(spec=OrderSplit)
        split1.id = 1
        split1.parent_order_id = 1
        split1.split_order_id = 2
        split1.split_type = SplitType.PAYMENT.value
        split1.created_at = datetime.utcnow()

        # Mock payment
        payment1 = Mock(spec=SplitPayment)
        payment1.amount = Decimal("55.00")
        payment1.payment_status = PaymentStatus.PAID.value

        mock_db.query.return_value.filter.return_value.all.side_effect = [
            [split1],  # splits query
            [payment1],  # payments query
        ]

        service = OrderSplitService(mock_db)
        result = service.get_split_summary(1)

        # Verify
        assert result.parent_order_id == 1
        assert result.total_splits == 1
        assert result.paid_amount == Decimal("55.00")

    def test_update_split_payment(self, mock_db):
        """Test updating split payment status"""
        # Setup
        payment = Mock(spec=SplitPayment)
        payment.id = 1
        payment.parent_order_id = 1
        payment.split_order_id = 2
        payment.amount = Decimal("55.00")
        payment.payment_status = PaymentStatus.PENDING.value

        mock_db.query.return_value.filter.return_value.first.return_value = payment

        service = OrderSplitService(mock_db)
        service.webhook_service = Mock()

        # Test
        result = service.update_split_payment(1, PaymentStatus.PAID, "REF123", "card")

        # Verify
        assert payment.payment_status == PaymentStatus.PAID.value
        assert payment.payment_reference == "REF123"
        assert payment.payment_method == "card"
        mock_db.commit.assert_called_once()


class TestMergeOperations:
    """Test merging split orders"""

    def test_merge_split_orders(self, mock_db):
        """Test merging split orders back together"""
        # Setup mocks
        split1 = Mock(spec=OrderSplit)
        split1.parent_order_id = 1
        split1.split_metadata = {}

        split2 = Mock(spec=OrderSplit)
        split2.parent_order_id = 1
        split2.split_metadata = {}

        mock_db.query.return_value.filter.return_value.all.return_value = [
            split1,
            split2,
        ]

        # Mock orders
        order1 = Mock(spec=Order)
        order1.id = 2
        order1.status = OrderStatus.PENDING
        order1.order_items = []

        order2 = Mock(spec=Order)
        order2.id = 3
        order2.status = OrderStatus.PENDING
        order2.order_items = []

        parent_order = Mock(spec=Order)
        parent_order.id = 1

        def mock_filter_side_effect(*args, **kwargs):
            mock = Mock()
            if args and hasattr(args[0], "left"):
                # Order.id.in_ query
                mock.all.return_value = [order1, order2]
            else:
                # Order.id == query
                mock.first.return_value = parent_order
            return mock

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        service = OrderSplitService(mock_db)

        merge_request = MergeSplitRequest(
            split_order_ids=[2, 3],
            merge_reason="Customer changed mind",
            keep_original=True,
        )

        # Mock recalculate
        with patch.object(service, "_recalculate_order_totals"):
            result = service.merge_split_orders(merge_request, 1)

        # Verify
        assert result.success is True
        assert "Successfully merged 2 orders" in result.message
        assert order1.status == OrderStatus.CANCELLED
        assert order2.status == OrderStatus.CANCELLED

    def test_merge_different_parents(self, mock_db):
        """Test merge fails with different parent orders"""
        # Setup
        split1 = Mock(spec=OrderSplit)
        split1.parent_order_id = 1

        split2 = Mock(spec=OrderSplit)
        split2.parent_order_id = 2  # Different parent

        mock_db.query.return_value.filter.return_value.all.return_value = [
            split1,
            split2,
        ]

        service = OrderSplitService(mock_db)

        merge_request = MergeSplitRequest(
            split_order_ids=[2, 3], merge_reason="Test", keep_original=True
        )

        # Test
        with pytest.raises(HTTPException) as exc_info:
            service.merge_split_orders(merge_request, 1)

        assert exc_info.value.status_code == 400
        assert "different parent orders" in str(exc_info.value.detail)


class TestTrackingFeatures:
    """Test tracking and status management"""

    def test_get_split_tracking(self, mock_db, sample_order):
        """Test comprehensive split tracking"""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = sample_order

        # Mock split with nested order
        split_order = Mock(spec=Order)
        split_order.id = 2
        split_order.status = OrderStatus.IN_PROGRESS

        split = Mock(spec=OrderSplit)
        split.id = 1
        split.split_order_id = 2
        split.split_type = SplitType.TICKET.value
        split.split_order = split_order
        split.created_at = datetime.utcnow()
        split.split_by = 1
        split.split_reason = "Test split"
        split.split_metadata = {"test": "data"}

        mock_db.query.return_value.options.return_value.filter.return_value.all.return_value = [
            split
        ]
        mock_db.query.return_value.filter.return_value.first.return_value = (
            None  # No payment
        )

        service = OrderSplitService(mock_db)
        result = service.get_split_tracking(1)

        # Verify
        assert result["parent_order"]["id"] == 1
        assert result["status_summary"]["total_splits"] == 1
        assert len(result["splits_by_type"][SplitType.TICKET.value]) == 1

    def test_update_split_status(self, mock_db):
        """Test updating split order status"""
        # Setup
        split_order = Mock(spec=Order)
        split_order.id = 2
        split_order.status = OrderStatus.PENDING

        split_record = Mock(spec=OrderSplit)
        split_record.parent_order_id = 1
        split_record.split_metadata = {}

        mock_db.query.return_value.filter.return_value.first.side_effect = [
            split_order,  # First query for order
            split_record,  # Second query for split record
        ]

        service = OrderSplitService(mock_db)
        service.webhook_service = Mock()

        # Test
        result = service.update_split_status(
            2, OrderStatus.IN_PROGRESS, 1, "Starting preparation"
        )

        # Verify
        assert result["old_status"] == OrderStatus.PENDING.value
        assert result["new_status"] == OrderStatus.IN_PROGRESS.value
        assert split_order.status == OrderStatus.IN_PROGRESS
        assert "status_updates" in split_record.split_metadata
        mock_db.commit.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])
