"""
Tests for order split payment math and integrity.
"""

import pytest
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session

from modules.orders.models.order_models import (
    Order,
    OrderItem,
    OrderStatus,
    OrderSplit,
    SplitPayment,
)
from modules.orders.schemas.order_split_schemas import (
    TicketSplitRequest,
    DeliverySplitRequest,
    PaymentSplitRequest,
    PaymentSplitDetail,
    MergeSplitsRequest,
)
from modules.orders.services.order_split_service import OrderSplitService


@pytest.fixture
def split_service(db_session: Session):
    """Create order split service instance."""
    return OrderSplitService(db_session)


@pytest.fixture
def sample_order_with_items(db_session: Session):
    """Create a sample order with multiple items."""
    order = Order(
        customer_id=1,
        table_no=5,
        status=OrderStatus.PENDING.value,
        total_amount=Decimal("150.00"),
        tax_amount=Decimal("12.00"),
        tip_amount=Decimal("22.50"),
        final_amount=Decimal("184.50"),  # 150 + 12 + 22.50
        created_at=datetime.utcnow(),
    )
    db_session.add(order)
    db_session.flush()

    # Add items
    items = [
        OrderItem(
            order_id=order.id,
            menu_item_id=1,
            quantity=2,
            price=Decimal("25.00"),
            subtotal=Decimal("50.00"),
        ),
        OrderItem(
            order_id=order.id,
            menu_item_id=2,
            quantity=1,
            price=Decimal("50.00"),
            subtotal=Decimal("50.00"),
        ),
        OrderItem(
            order_id=order.id,
            menu_item_id=3,
            quantity=3,
            price=Decimal("16.67"),
            subtotal=Decimal("50.00"),  # 50.01 rounded to 50.00
        ),
    ]
    db_session.add_all(items)
    db_session.commit()

    return order


class TestPaymentSplitMath:
    """Test payment split calculations and validation."""

    def test_payment_split_total_must_equal_order_total(
        self, split_service, db_session, sample_order_with_items
    ):
        """Test that sum of payment splits must equal order total."""
        order = sample_order_with_items

        # Try to create splits that don't sum to order total
        invalid_request = PaymentSplitRequest(
            splits=[
                PaymentSplitDetail(
                    name="Person 1",
                    amount=Decimal("100.00"),  # Should be 92.25
                    tip_amount=Decimal("10.00"),
                ),
                PaymentSplitDetail(
                    name="Person 2",
                    amount=Decimal("50.00"),  # Should be 92.25
                    tip_amount=Decimal("12.50"),
                ),
                # Total: 150 + 22.50 = 172.50 (should be 184.50)
            ]
        )

        with pytest.raises(ValueError) as exc_info:
            split_service.split_payment(order.id, invalid_request)

        assert "must equal order total" in str(exc_info.value).lower()

    def test_payment_split_with_exact_amounts(
        self, split_service, db_session, sample_order_with_items
    ):
        """Test payment split with exact amounts."""
        order = sample_order_with_items

        # Create valid splits
        request = PaymentSplitRequest(
            splits=[
                PaymentSplitDetail(
                    name="Person 1",
                    amount=Decimal("92.25"),  # Half of 184.50
                    tip_amount=Decimal("11.25"),  # Half of 22.50
                ),
                PaymentSplitDetail(
                    name="Person 2",
                    amount=Decimal("92.25"),
                    tip_amount=Decimal("11.25"),
                ),
            ]
        )

        result = split_service.split_payment(order.id, request)

        assert len(result["split_orders"]) == 2

        # Verify totals
        total_amount = sum(
            Decimal(str(s["final_amount"])) for s in result["split_orders"]
        )
        assert total_amount == order.final_amount

        # Check split payments
        split_payments = (
            db_session.query(SplitPayment)
            .filter(SplitPayment.parent_order_id == order.id)
            .all()
        )

        assert len(split_payments) == 2
        payment_total = sum(p.amount for p in split_payments)
        assert payment_total == order.final_amount

    def test_payment_split_with_rounding(self, split_service, db_session):
        """Test payment splits handle decimal rounding correctly."""
        # Create order with amount that doesn't divide evenly
        order = Order(
            customer_id=1,
            status=OrderStatus.PENDING.value,
            total_amount=Decimal("100.00"),
            tax_amount=Decimal("8.33"),  # Doesn't divide evenly by 3
            final_amount=Decimal("108.33"),
        )
        db_session.add(order)
        db_session.commit()

        # Split 3 ways
        request = PaymentSplitRequest(
            splits=[
                PaymentSplitDetail(
                    name="Person 1", amount=Decimal("36.11")  # 108.33 / 3 = 36.11
                ),
                PaymentSplitDetail(name="Person 2", amount=Decimal("36.11")),
                PaymentSplitDetail(name="Person 3", amount=Decimal("36.11")),
            ]
        )

        result = split_service.split_payment(order.id, request)

        # Verify sum still equals original
        total = sum(Decimal(str(s["final_amount"])) for s in result["split_orders"])
        assert total == Decimal("108.33")

    def test_payment_split_updates_statuses(
        self, split_service, db_session, sample_order_with_items
    ):
        """Test that payment splits update order statuses correctly."""
        order = sample_order_with_items

        request = PaymentSplitRequest(
            splits=[
                PaymentSplitDetail(
                    name="Person 1",
                    amount=Decimal("100.00"),
                    tip_amount=Decimal("12.00"),
                ),
                PaymentSplitDetail(
                    name="Person 2",
                    amount=Decimal("84.50"),
                    tip_amount=Decimal("10.50"),
                ),
            ]
        )

        result = split_service.split_payment(order.id, request)

        # Parent order should be split
        db_session.refresh(order)
        assert order.status == OrderStatus.SPLIT.value

        # Split orders should be pending_payment
        for split_info in result["split_orders"]:
            split_order = db_session.query(Order).get(split_info["id"])
            assert split_order.status == OrderStatus.PENDING_PAYMENT.value


class TestMergeSplits:
    """Test merging split orders back together."""

    def test_merge_restores_correct_totals(
        self, split_service, db_session, sample_order_with_items
    ):
        """Test that merging splits restores original totals."""
        order = sample_order_with_items
        original_total = order.final_amount

        # First split the order
        split_request = TicketSplitRequest(
            splits=[
                {"name": "Kitchen 1", "item_ids": [1]},
                {"name": "Kitchen 2", "item_ids": [2, 3]},
            ]
        )
        split_result = split_service.split_by_ticket(order.id, split_request)
        split_ids = [s["id"] for s in split_result["split_orders"]]

        # Now merge them back
        merge_request = MergeSplitsRequest(
            split_order_ids=split_ids, merge_reason="Customer changed mind"
        )
        merge_result = split_service.merge_splits(order.id, merge_request)

        # Verify totals restored
        merged_order = db_session.query(Order).get(merge_result["merged_order"]["id"])
        assert merged_order.final_amount == original_total
        assert merged_order.status == OrderStatus.PENDING.value

        # Verify split orders are cancelled
        for split_id in split_ids:
            split_order = db_session.query(Order).get(split_id)
            assert split_order.status == OrderStatus.CANCELLED.value

    def test_cannot_merge_paid_splits(
        self, split_service, db_session, sample_order_with_items
    ):
        """Test that paid splits cannot be merged."""
        order = sample_order_with_items

        # Create payment splits
        split_request = PaymentSplitRequest(
            splits=[
                PaymentSplitDetail(
                    name="Person 1",
                    amount=Decimal("92.25"),
                    tip_amount=Decimal("11.25"),
                ),
                PaymentSplitDetail(
                    name="Person 2",
                    amount=Decimal("92.25"),
                    tip_amount=Decimal("11.25"),
                ),
            ]
        )
        split_result = split_service.split_payment(order.id, split_request)
        split_ids = [s["id"] for s in split_result["split_orders"]]

        # Mark one as paid
        paid_order = db_session.query(Order).get(split_ids[0])
        paid_order.status = OrderStatus.COMPLETED.value
        db_session.commit()

        # Try to merge
        merge_request = MergeSplitsRequest(
            split_order_ids=split_ids, merge_reason="Trying to merge paid order"
        )

        with pytest.raises(ValueError) as exc_info:
            split_service.merge_splits(order.id, merge_request)

        assert "cannot be merged" in str(exc_info.value).lower()


class TestSplitStatusTransitions:
    """Test status transitions are properly audited."""

    def test_split_creates_audit_records(
        self, split_service, db_session, sample_order_with_items
    ):
        """Test that splits create proper audit records."""
        order = sample_order_with_items

        # Create split
        request = TicketSplitRequest(
            splits=[
                {"name": "Split 1", "item_ids": [1]},
                {"name": "Split 2", "item_ids": [2, 3]},
            ]
        )

        result = split_service.split_by_ticket(order.id, request)

        # Check OrderSplit records created
        splits = (
            db_session.query(OrderSplit)
            .filter(OrderSplit.parent_order_id == order.id)
            .all()
        )

        assert len(splits) == 2
        for split in splits:
            assert split.split_type == "ticket"
            assert split.created_at is not None

    def test_payment_tracking_accuracy(
        self, split_service, db_session, sample_order_with_items
    ):
        """Test payment tracking for splits."""
        order = sample_order_with_items

        # Create payment split
        request = PaymentSplitRequest(
            splits=[
                PaymentSplitDetail(
                    name="Card Payment",
                    amount=Decimal("100.00"),
                    tip_amount=Decimal("15.00"),
                    payment_method="credit_card",
                ),
                PaymentSplitDetail(
                    name="Cash Payment",
                    amount=Decimal("84.50"),
                    tip_amount=Decimal("7.50"),
                    payment_method="cash",
                ),
            ]
        )

        result = split_service.split_payment(order.id, request)

        # Verify payment tracking
        payments = (
            db_session.query(SplitPayment)
            .filter(SplitPayment.parent_order_id == order.id)
            .all()
        )

        assert len(payments) == 2

        # Check payment methods recorded
        payment_methods = {p.payment_method for p in payments}
        assert "credit_card" in payment_methods
        assert "cash" in payment_methods

        # Verify amounts
        total_paid = sum(p.amount for p in payments)
        assert total_paid == order.final_amount


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_split_order_with_zero_items(self, split_service, db_session):
        """Test handling of orders with no items."""
        order = Order(
            customer_id=1,
            status=OrderStatus.PENDING.value,
            total_amount=Decimal("0.00"),
            final_amount=Decimal("0.00"),
        )
        db_session.add(order)
        db_session.commit()

        request = TicketSplitRequest(splits=[{"name": "Empty split", "item_ids": []}])

        with pytest.raises(ValueError):
            split_service.split_by_ticket(order.id, request)

    def test_decimal_precision_maintained(self, split_service, db_session):
        """Test that decimal precision is maintained throughout splits."""
        # Create order with precise decimals
        order = Order(
            customer_id=1,
            status=OrderStatus.PENDING.value,
            total_amount=Decimal("123.45"),
            tax_amount=Decimal("9.88"),
            tip_amount=Decimal("18.52"),
            final_amount=Decimal("151.85"),
        )
        db_session.add(order)
        db_session.commit()

        # Split with precise amounts
        request = PaymentSplitRequest(
            splits=[
                PaymentSplitDetail(
                    name="Exact Third 1",
                    amount=Decimal("50.62"),  # 151.85 / 3 = 50.6166...
                    tip_amount=Decimal("6.17"),
                ),
                PaymentSplitDetail(
                    name="Exact Third 2",
                    amount=Decimal("50.62"),
                    tip_amount=Decimal("6.17"),
                ),
                PaymentSplitDetail(
                    name="Exact Third 3",
                    amount=Decimal("50.61"),  # Handle rounding
                    tip_amount=Decimal("6.18"),
                ),
            ]
        )

        result = split_service.split_payment(order.id, request)

        # Verify precision maintained
        total = Decimal("0.00")
        for split_info in result["split_orders"]:
            split_order = db_session.query(Order).get(split_info["id"])
            total += split_order.final_amount

        assert total == order.final_amount
