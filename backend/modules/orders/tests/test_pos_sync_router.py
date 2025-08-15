# backend/modules/orders/tests/test_pos_sync_router.py

"""
Tests for POS sync endpoints.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.orders.models.order_models import Order
from modules.orders.models.sync_models import OrderSyncStatus, SyncStatus
from modules.orders.routers.pos_sync_router import POSSyncRequest, POSSyncResponse


@pytest.fixture
def mock_sync_service():
    """Mock OrderSyncService"""
    with patch(
        "backend.modules.orders.routers.pos_sync_router.OrderSyncService"
    ) as mock:
        service = Mock()
        service.sync_single_order = AsyncMock(return_value=(True, None))
        service.close = AsyncMock()
        mock.return_value = service
        yield mock


@pytest.fixture
def mock_scheduler():
    """Mock order sync scheduler"""
    with patch(
        "backend.modules.orders.routers.pos_sync_router.order_sync_scheduler"
    ) as mock:
        mock.trigger_manual_sync.return_value = True
        mock.get_scheduler_status.return_value = {
            "running": True,
            "next_run": datetime.utcnow().isoformat(),
        }
        yield mock


class TestPOSSyncEndpoint:
    """Test POST /pos/sync endpoint"""

    def test_sync_specific_orders_success(
        self, client: TestClient, db: Session, auth_headers, mock_sync_service
    ):
        """Test syncing specific order IDs"""
        # Create test orders
        orders = []
        for i in range(3):
            order = Order(
                staff_id=1, table_no=f"T{i+1}", status="completed", is_deleted=False
            )
            db.add(order)
            orders.append(order)
        db.commit()

        # Create sync request
        request_data = {
            "terminal_id": "POS-001",
            "order_ids": [o.id for o in orders],
            "sync_all_pending": False,
        }

        response = client.post("/pos/sync", json=request_data, headers=auth_headers)

        assert response.status_code == 202
        data = response.json()

        assert data["status"] == "initiated"
        assert data["terminal_id"] == "POS-001"
        assert data["orders_queued"] == 3
        assert "Sync initiated for 3 orders" in data["message"]

    def test_sync_invalid_order_ids(
        self, client: TestClient, db: Session, auth_headers
    ):
        """Test syncing with invalid order IDs"""
        request_data = {
            "terminal_id": "POS-001",
            "order_ids": [9999, 10000],  # Non-existent IDs
            "sync_all_pending": False,
        }

        response = client.post("/pos/sync", json=request_data, headers=auth_headers)

        assert response.status_code == 404
        data = response.json()

        assert "No valid orders found" in data["detail"]

    def test_sync_all_pending_orders(
        self, client: TestClient, db: Session, auth_headers, mock_scheduler
    ):
        """Test syncing all pending orders"""
        # Create orders with sync status
        for i in range(5):
            order = Order(
                staff_id=1, table_no=f"T{i+1}", status="completed", is_deleted=False
            )
            db.add(order)
            db.flush()

            # Add sync status
            sync_status = OrderSyncStatus(
                order_id=order.id,
                sync_status=SyncStatus.PENDING if i < 3 else SyncStatus.SYNCED,
                sync_direction="local_to_remote",
            )
            db.add(sync_status)

        db.commit()

        request_data = {
            "terminal_id": "POS-002",
            "sync_all_pending": True,
            "include_recent": False,
        }

        response = client.post("/pos/sync", json=request_data, headers=auth_headers)

        assert response.status_code == 202
        data = response.json()

        assert data["status"] == "initiated"
        assert data["terminal_id"] == "POS-002"
        assert "sync_batch_id" in data
        assert mock_scheduler.trigger_manual_sync.called

    def test_sync_include_recent_orders(
        self, client: TestClient, db: Session, auth_headers, mock_scheduler
    ):
        """Test syncing with include_recent flag"""
        # Create recently synced order
        order = Order(staff_id=1, table_no="T1", status="completed", is_deleted=False)
        db.add(order)
        db.flush()

        sync_status = OrderSyncStatus(
            order_id=order.id,
            sync_status=SyncStatus.SYNCED,
            sync_direction="local_to_remote",
            synced_at=datetime.utcnow(),
        )
        db.add(sync_status)
        db.commit()

        request_data = {"sync_all_pending": True, "include_recent": True}

        response = client.post("/pos/sync", json=request_data, headers=auth_headers)

        assert response.status_code == 202
        data = response.json()

        assert data["status"] in ["initiated", "completed"]
        assert data["details"]["include_recent"] is True

    def test_sync_no_pending_orders(
        self, client: TestClient, db: Session, auth_headers
    ):
        """Test sync when no pending orders exist"""
        # Create all synced orders
        for i in range(3):
            order = Order(
                staff_id=1, table_no=f"T{i+1}", status="completed", is_deleted=False
            )
            db.add(order)
            db.flush()

            sync_status = OrderSyncStatus(
                order_id=order.id,
                sync_status=SyncStatus.SYNCED,
                sync_direction="local_to_remote",
                synced_at=datetime.utcnow(),
            )
            db.add(sync_status)

        db.commit()

        request_data = {"sync_all_pending": True, "include_recent": False}

        response = client.post("/pos/sync", json=request_data, headers=auth_headers)

        assert response.status_code == 202
        data = response.json()

        assert data["status"] == "completed"
        assert data["orders_queued"] == 0
        assert "No pending orders to sync" in data["message"]


class TestPOSSyncStatusEndpoint:
    """Test GET /pos/sync/status endpoint"""

    def test_get_sync_status(self, client: TestClient, db: Session, auth_headers):
        """Test getting sync status overview"""
        # Create orders with various sync statuses
        statuses = [
            SyncStatus.PENDING,
            SyncStatus.PENDING,
            SyncStatus.SYNCED,
            SyncStatus.FAILED,
            SyncStatus.RETRY,
        ]

        for i, status in enumerate(statuses):
            order = Order(
                staff_id=1, table_no=f"T{i+1}", status="completed", is_deleted=False
            )
            db.add(order)
            db.flush()

            sync_status = OrderSyncStatus(
                order_id=order.id, sync_status=status, sync_direction="local_to_remote"
            )
            db.add(sync_status)

        db.commit()

        response = client.get("/pos/sync/status", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert "sync_status_counts" in data
        assert data["sync_status_counts"]["pending"] == 2
        assert data["sync_status_counts"]["synced"] == 1
        assert data["sync_status_counts"]["failed"] == 1
        assert data["sync_status_counts"]["retry"] == 1

        assert "unsynced_orders" in data
        assert "pending_conflicts" in data
        assert "scheduler" in data
        assert "configuration" in data

    def test_get_sync_status_with_terminal_id(self, client: TestClient, auth_headers):
        """Test getting sync status with specific terminal ID"""
        response = client.get(
            "/pos/sync/status?terminal_id=POS-123", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert data["configuration"]["terminal_id"] == "POS-123"


class TestPOSSyncRequestValidation:
    """Test request validation"""

    def test_empty_request(self, client: TestClient, auth_headers):
        """Test with empty request body"""
        response = client.post("/pos/sync", json={}, headers=auth_headers)

        assert response.status_code == 202
        data = response.json()

        # Should default to sync_all_pending=True
        assert data["status"] in ["initiated", "completed"]

    def test_invalid_order_ids_type(self, client: TestClient, auth_headers):
        """Test with invalid order_ids type"""
        request_data = {
            "order_ids": "not-a-list",  # Should be a list
            "sync_all_pending": False,
        }

        response = client.post("/pos/sync", json=request_data, headers=auth_headers)

        assert response.status_code == 422  # Validation error

    def test_conflicting_options(self, client: TestClient, auth_headers):
        """Test with both order_ids and sync_all_pending"""
        request_data = {
            "order_ids": [1, 2, 3],
            "sync_all_pending": True,  # Should be ignored when order_ids provided
        }

        response = client.post("/pos/sync", json=request_data, headers=auth_headers)

        assert response.status_code in [202, 404]  # 202 if orders exist, 404 if not
        data = response.json()

        # Should process specific orders, not all pending
        if response.status_code == 202:
            assert "order_ids" in data.get("details", {})

    def test_empty_order_ids_array(self, client: TestClient, auth_headers):
        """Test with empty order_ids array"""
        request_data = {"order_ids": [], "sync_all_pending": False}

        response = client.post("/pos/sync", json=request_data, headers=auth_headers)

        assert response.status_code == 400
        data = response.json()
        assert "order_ids cannot be empty" in data["detail"]

    def test_scheduler_failure(
        self, client: TestClient, db: Session, auth_headers, mock_scheduler
    ):
        """Test when scheduler trigger_manual_sync returns False"""
        # Configure mock to return False
        mock_scheduler.trigger_manual_sync.return_value = False

        # Create pending order
        order = Order(staff_id=1, table_no="T1", status="completed", is_deleted=False)
        db.add(order)
        db.flush()

        sync_status = OrderSyncStatus(
            order_id=order.id,
            sync_status=SyncStatus.PENDING,
            sync_direction="local_to_remote",
        )
        db.add(sync_status)
        db.commit()

        request_data = {"sync_all_pending": True}

        response = client.post("/pos/sync", json=request_data, headers=auth_headers)

        assert response.status_code == 503
        data = response.json()
        assert "Sync scheduler is unavailable" in data["detail"]


@pytest.mark.asyncio
async def test_background_sync_processing():
    """Test background sync task processing"""
    from modules.orders.routers.pos_sync_router import _process_sync_batch

    with patch("backend.modules.orders.routers.pos_sync_router.get_db") as mock_get_db:
        mock_db = Mock()
        mock_get_db.return_value = iter([mock_db])

        with patch(
            "backend.modules.orders.routers.pos_sync_router.OrderSyncService"
        ) as mock_service:
            service = Mock()
            service.sync_single_order = AsyncMock(return_value=(True, None))
            service.close = AsyncMock()
            mock_service.return_value = service

            await _process_sync_batch([1, 2, 3], "POS-001")

            assert service.sync_single_order.call_count == 3
            assert service.close.called
            assert mock_db.close.called
