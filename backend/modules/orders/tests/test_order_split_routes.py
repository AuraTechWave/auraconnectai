"""
Tests for order splitting API routes.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from datetime import datetime
from decimal import Decimal

from app.main import app
from ..schemas.order_split_schemas import (
    SplitType,
    PaymentStatus,
    SplitValidationResponse,
    OrderSplitResponse,
    SplitOrderSummary,
)
from ..enums.order_enums import OrderStatus


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Mock authentication headers"""
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def mock_current_user():
    """Mock authenticated user"""
    user = Mock()
    user.id = 1
    user.email = "test@example.com"
    user.role = "admin"
    return user


class TestOrderSplitValidation:
    """Test order split validation endpoints"""

    @patch("modules.orders.routes.order_split_routes.get_current_user")
    @patch("modules.orders.routes.order_split_routes.get_db")
    @patch("modules.orders.routes.order_split_routes.OrderSplitService")
    def test_validate_split_success(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        auth_headers,
        mock_current_user,
    ):
        """Test successful split validation"""
        # Setup
        mock_get_user.return_value = mock_current_user
        mock_db = Mock()
        mock_get_db.return_value = mock_db

        mock_service = Mock()
        mock_validation = SplitValidationResponse(
            can_split=True,
            reason=None,
            splittable_items=[{"item_id": 1, "quantity": 2, "unit_price": 25.00}],
            warnings=[],
            estimated_totals={
                "subtotal": Decimal("50.00"),
                "tax_amount": Decimal("5.00"),
                "total_amount": Decimal("55.00"),
            },
        )
        mock_service.validate_split_request.return_value = mock_validation
        mock_service_class.return_value = mock_service

        # Request data
        split_data = {
            "split_type": "ticket",
            "items": [{"item_id": 1, "quantity": 2}],
            "split_reason": "Customer request",
        }

        # Test
        response = client.post(
            "/api/v1/orders/1/split/validate", json=split_data, headers=auth_headers
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["can_split"] is True
        assert len(data["splittable_items"]) == 1
        assert float(data["estimated_totals"]["total_amount"]) == 55.00


class TestOrderSplitting:
    """Test order splitting endpoints"""

    @patch("modules.orders.routes.order_split_routes.get_current_user")
    @patch("modules.orders.routes.order_split_routes.get_db")
    @patch("modules.orders.routes.order_split_routes.OrderSplitService")
    def test_split_order_ticket(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        auth_headers,
        mock_current_user,
    ):
        """Test splitting order by ticket"""
        # Setup
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value = Mock()

        mock_service = Mock()
        mock_response = OrderSplitResponse(
            success=True,
            message="Order split successfully into 2 orders",
            parent_order_id=1,
            split_order_ids=[2, 3],
            split_details=[
                {"split_order_id": 2, "group_name": "Ticket 1"},
                {"split_order_id": 3, "group_name": "Ticket 2"},
            ],
        )
        mock_service.split_order.return_value = mock_response
        mock_service_class.return_value = mock_service

        # Request data
        split_data = {
            "split_type": "ticket",
            "items": [{"item_id": 1, "quantity": 1}, {"item_id": 2, "quantity": 1}],
            "split_reason": "Kitchen ticket split",
        }

        # Test
        response = client.post(
            "/api/v1/orders/1/split", json=split_data, headers=auth_headers
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["split_order_ids"]) == 2
        assert data["parent_order_id"] == 1

    @patch("modules.orders.routes.order_split_routes.get_current_user")
    @patch("modules.orders.routes.order_split_routes.get_db")
    @patch("modules.orders.routes.order_split_routes.OrderSplitService")
    def test_split_order_delivery(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        auth_headers,
        mock_current_user,
    ):
        """Test splitting order for delivery"""
        # Setup
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value = Mock()

        mock_service = Mock()
        mock_response = OrderSplitResponse(
            success=True,
            message="Order split for delivery",
            parent_order_id=1,
            split_order_ids=[2],
            split_details=[{"split_order_id": 2, "delivery_type": "separate"}],
        )
        mock_service.split_order.return_value = mock_response
        mock_service_class.return_value = mock_service

        # Request data
        split_data = {
            "split_type": "delivery",
            "items": [{"item_id": 1, "quantity": 2}],
            "split_reason": "Separate delivery requested",
            "customer_id": 2,
            "scheduled_time": "2024-01-20T14:00:00",
        }

        # Test
        response = client.post(
            "/api/v1/orders/1/split", json=split_data, headers=auth_headers
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["split_order_ids"]) == 1


class TestPaymentSplitting:
    """Test payment splitting endpoints"""

    @patch("modules.orders.routes.order_split_routes.get_current_user")
    @patch("modules.orders.routes.order_split_routes.get_db")
    @patch("modules.orders.routes.order_split_routes.OrderSplitService")
    def test_split_payment(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        auth_headers,
        mock_current_user,
    ):
        """Test splitting order payment"""
        # Setup
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value = Mock()

        mock_service = Mock()
        mock_response = OrderSplitResponse(
            success=True,
            message="Payment split into 2 parts",
            parent_order_id=1,
            split_order_ids=[2, 3],
            split_details=[
                {"split_order_id": 2, "amount": 55.00},
                {"split_order_id": 3, "amount": 55.00},
            ],
        )
        mock_service.split_order_for_payment.return_value = mock_response
        mock_service_class.return_value = mock_service

        # Request data
        payment_data = {
            "splits": [
                {"amount": 55.00, "customer_id": 1, "payment_method": "card"},
                {"amount": 55.00, "customer_id": 2, "payment_method": "cash"},
            ]
        }

        # Test
        response = client.post(
            "/api/v1/orders/1/split/payment", json=payment_data, headers=auth_headers
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["split_order_ids"]) == 2

    @patch("modules.orders.routes.order_split_routes.get_current_user")
    @patch("modules.orders.routes.order_split_routes.get_db")
    @patch("modules.orders.routes.order_split_routes.OrderSplitService")
    def test_update_split_payment(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        auth_headers,
        mock_current_user,
    ):
        """Test updating split payment status"""
        # Setup
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value = Mock()

        mock_service = Mock()
        mock_payment = Mock()
        mock_payment.id = 1
        mock_payment.amount = Decimal("55.00")
        mock_payment.payment_status = "paid"
        mock_payment.payment_reference = "REF123"
        mock_service.update_split_payment.return_value = mock_payment
        mock_service_class.return_value = mock_service

        # Test
        response = client.put(
            "/api/v1/orders/splits/payment/1?payment_status=paid&payment_reference=REF123",
            headers=auth_headers,
        )

        # Verify
        assert response.status_code == 200
        mock_service.update_split_payment.assert_called_once_with(
            1, PaymentStatus.PAID, "REF123", None
        )


class TestSplitManagement:
    """Test split order management endpoints"""

    @patch("modules.orders.routes.order_split_routes.get_current_user")
    @patch("modules.orders.routes.order_split_routes.get_db")
    @patch("modules.orders.routes.order_split_routes.OrderSplitService")
    def test_get_order_splits(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        auth_headers,
        mock_current_user,
    ):
        """Test getting order split summary"""
        # Setup
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value = Mock()

        mock_service = Mock()
        mock_summary = SplitOrderSummary(
            parent_order_id=1,
            total_splits=2,
            split_orders=[],
            payment_splits=[],
            total_amount=Decimal("110.00"),
            paid_amount=Decimal("55.00"),
            pending_amount=Decimal("55.00"),
        )
        mock_service.get_split_summary.return_value = mock_summary
        mock_service_class.return_value = mock_service

        # Test
        response = client.get("/api/v1/orders/1/splits", headers=auth_headers)

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["parent_order_id"] == 1
        assert data["total_splits"] == 2
        assert float(data["paid_amount"]) == 55.00

    @patch("modules.orders.routes.order_split_routes.get_current_user")
    @patch("modules.orders.routes.order_split_routes.get_db")
    @patch("modules.orders.routes.order_split_routes.OrderSplitService")
    def test_merge_split_orders(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        auth_headers,
        mock_current_user,
    ):
        """Test merging split orders"""
        # Setup
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value = Mock()

        mock_service = Mock()
        mock_response = OrderSplitResponse(
            success=True,
            message="Successfully merged 2 orders",
            parent_order_id=1,
            split_order_ids=[1],
            split_details=[{"merged_order_id": 1}],
        )
        mock_service.merge_split_orders.return_value = mock_response
        mock_service_class.return_value = mock_service

        # Request data
        merge_data = {
            "split_order_ids": [2, 3],
            "merge_reason": "Customer changed mind",
            "keep_original": True,
        }

        # Test
        response = client.post(
            "/api/v1/orders/splits/merge", json=merge_data, headers=auth_headers
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "merged" in data["message"]


class TestTableSplits:
    """Test table-level split operations"""

    @patch("modules.orders.routes.order_split_routes.get_current_user")
    @patch("modules.orders.routes.order_split_routes.get_db")
    @patch("modules.orders.routes.order_split_routes.OrderSplitService")
    def test_get_table_splits(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        auth_headers,
        mock_current_user,
    ):
        """Test getting all splits for a table"""
        # Setup
        mock_get_user.return_value = mock_current_user

        # Mock database queries
        mock_db = Mock()
        mock_order = Mock()
        mock_order.id = 1

        mock_split = Mock()
        mock_split.parent_order_id = 1

        # Configure query chain
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_order]
        mock_db.query.return_value.filter.return_value.first.return_value = mock_split

        mock_get_db.return_value = mock_db

        # Mock service
        mock_service = Mock()
        mock_summary = SplitOrderSummary(
            parent_order_id=1,
            total_splits=1,
            split_orders=[],
            payment_splits=[],
            total_amount=Decimal("110.00"),
            paid_amount=Decimal("0.00"),
            pending_amount=Decimal("110.00"),
        )
        mock_service.get_split_summary.return_value = mock_summary
        mock_service_class.return_value = mock_service

        # Test
        response = client.get("/api/v1/orders/splits/by-table/5", headers=auth_headers)

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestTrackingEndpoints:
    """Test split order tracking endpoints"""

    @patch("modules.orders.routes.order_split_routes.get_current_user")
    @patch("modules.orders.routes.order_split_routes.get_db")
    @patch("modules.orders.routes.order_split_routes.OrderSplitService")
    def test_get_split_tracking(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        auth_headers,
        mock_current_user,
    ):
        """Test getting split order tracking"""
        # Setup
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value = Mock()

        mock_service = Mock()
        mock_tracking = {
            "parent_order": {"id": 1, "status": "pending", "total_amount": 110.00},
            "splits_by_type": {"ticket": [], "delivery": [], "payment": []},
            "status_summary": {"total_splits": 2, "pending": 1, "in_progress": 1},
            "payment_summary": {
                "total_amount": 110.00,
                "paid_amount": 55.00,
                "pending_amount": 55.00,
            },
        }
        mock_service.get_split_tracking.return_value = mock_tracking
        mock_service_class.return_value = mock_service

        # Test
        response = client.get("/api/v1/orders/1/splits/tracking", headers=auth_headers)

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["parent_order"]["id"] == 1
        assert data["status_summary"]["total_splits"] == 2

    @patch("modules.orders.routes.order_split_routes.get_current_user")
    @patch("modules.orders.routes.order_split_routes.get_db")
    @patch("modules.orders.routes.order_split_routes.OrderSplitService")
    def test_update_split_status(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        auth_headers,
        mock_current_user,
    ):
        """Test updating split order status"""
        # Setup
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value = Mock()

        mock_service = Mock()
        mock_result = {
            "split_order_id": 2,
            "parent_order_id": 1,
            "old_status": "pending",
            "new_status": "in_progress",
            "updated_at": datetime.utcnow().isoformat(),
        }
        mock_service.update_split_status.return_value = mock_result
        mock_service_class.return_value = mock_service

        # Test
        response = client.put(
            "/api/v1/orders/splits/2/status?new_status=in_progress&notes=Starting",
            headers=auth_headers,
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["old_status"] == "pending"
        assert data["new_status"] == "in_progress"


if __name__ == "__main__":
    pytest.main([__file__])
