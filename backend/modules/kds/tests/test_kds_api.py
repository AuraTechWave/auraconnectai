# backend/modules/kds/tests/test_kds_api.py

"""
Tests for KDS API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json

from modules.kds.models.kds_models import (
    KitchenStation,
    KDSOrderItem,
    StationType,
    StationStatus,
    DisplayStatus,
)
from modules.kds.schemas.kds_schemas import StationCreate
from modules.orders.models.order_models import Order, OrderItem
from modules.staff.models import StaffMember


class TestKDSAPI:
    """Test cases for KDS API endpoints"""

    @pytest.fixture
    def auth_headers(self, client: TestClient):
        """Get authentication headers for API requests"""
        # This should use your actual auth mechanism
        # For now, returning a mock token
        return {"Authorization": "Bearer test-token"}

    def test_create_station(self, client: TestClient, auth_headers: dict):
        """Test creating a kitchen station via API"""
        station_data = {
            "name": "Test Grill Station",
            "station_type": "grill",
            "display_name": "Grill #1",
            "color_code": "#FF6B6B",
            "priority": 10,
            "max_active_items": 20,
            "prep_time_multiplier": 1.0,
            "warning_time_minutes": 5,
            "critical_time_minutes": 10,
            "features": ["printer", "buzzer"],
            "printer_id": "PRINTER_01",
        }

        response = client.post(
            "/api/v1/kds/stations", json=station_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Grill Station"
        assert data["station_type"] == "grill"
        assert data["status"] == "active"
        assert "id" in data
        assert "created_at" in data

    def test_list_stations(self, client: TestClient, db: Session, auth_headers: dict):
        """Test listing kitchen stations"""
        # Create test stations
        stations = [
            KitchenStation(
                name="Grill 1",
                station_type=StationType.GRILL,
                status=StationStatus.ACTIVE,
            ),
            KitchenStation(
                name="Salad 1",
                station_type=StationType.SALAD,
                status=StationStatus.ACTIVE,
            ),
            KitchenStation(
                name="Old Station",
                station_type=StationType.FRY,
                status=StationStatus.INACTIVE,
            ),
        ]
        db.add_all(stations)
        db.commit()

        # List all stations
        response = client.get("/api/v1/kds/stations", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2  # Only active stations by default

        # List including inactive
        response = client.get(
            "/api/v1/kds/stations?include_inactive=true", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

        # Filter by type
        response = client.get(
            "/api/v1/kds/stations?station_type=grill", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Grill 1"

    def test_update_station(self, client: TestClient, db: Session, auth_headers: dict):
        """Test updating a station"""
        # Create station
        station = KitchenStation(
            name="Test Station",
            station_type=StationType.GRILL,
            status=StationStatus.ACTIVE,
        )
        db.add(station)
        db.commit()

        # Update station
        update_data = {
            "name": "Updated Station",
            "status": "busy",
            "priority": 15,
            "color_code": "#4ECDC4",
        }

        response = client.put(
            f"/api/v1/kds/stations/{station.id}", json=update_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Station"
        assert data["status"] == "busy"
        assert data["priority"] == 15
        assert data["color_code"] == "#4ECDC4"

    def test_delete_station(self, client: TestClient, db: Session, auth_headers: dict):
        """Test soft deleting a station"""
        # Create station
        station = KitchenStation(
            name="Station to Delete",
            station_type=StationType.GRILL,
            status=StationStatus.ACTIVE,
        )
        db.add(station)
        db.commit()

        # Delete station
        response = client.delete(
            f"/api/v1/kds/stations/{station.id}", headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Station deleted successfully"

        # Verify station is marked inactive
        db.refresh(station)
        assert station.status == StationStatus.INACTIVE

    def test_create_display(self, client: TestClient, db: Session, auth_headers: dict):
        """Test creating a display for a station"""
        # Create station
        station = KitchenStation(
            name="Test Station",
            station_type=StationType.GRILL,
            status=StationStatus.ACTIVE,
        )
        db.add(station)
        db.commit()

        display_data = {
            "station_id": station.id,
            "display_number": 2,
            "name": "Secondary Display",
            "layout_mode": "list",
            "items_per_page": 10,
            "auto_clear_completed": True,
            "auto_clear_delay_seconds": 60,
        }

        response = client.post(
            "/api/v1/kds/displays", json=display_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["station_id"] == station.id
        assert data["display_number"] == 2
        assert data["name"] == "Secondary Display"

    def test_display_heartbeat(self, client: TestClient, db: Session):
        """Test display heartbeat endpoint (no auth required)"""
        # Create station with display
        from modules.kds.models.kds_models import KitchenDisplay

        station = KitchenStation(
            name="Test Station",
            station_type=StationType.GRILL,
            status=StationStatus.ACTIVE,
        )
        db.add(station)
        db.commit()

        display = KitchenDisplay(
            station_id=station.id, display_number=1, name="Primary Display"
        )
        db.add(display)
        db.commit()

        # Send heartbeat
        response = client.post(f"/api/v1/kds/displays/{display.id}/heartbeat")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data

    def test_create_station_assignment(
        self, client: TestClient, db: Session, auth_headers: dict
    ):
        """Test creating station assignment rules"""
        # Create station
        station = KitchenStation(
            name="Test Station",
            station_type=StationType.GRILL,
            status=StationStatus.ACTIVE,
        )
        db.add(station)
        db.commit()

        assignment_data = {
            "station_id": station.id,
            "category_name": "Entrees",
            "priority": 10,
            "is_primary": True,
            "prep_time_override": 20,
            "conditions": {},
        }

        response = client.post(
            "/api/v1/kds/assignments", json=assignment_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["station_id"] == station.id
        assert data["category_name"] == "Entrees"
        assert data["prep_time_override"] == 20

    def test_get_station_items(
        self, client: TestClient, db: Session, auth_headers: dict
    ):
        """Test getting items for a station"""
        # Create test data
        station = KitchenStation(
            name="Test Station",
            station_type=StationType.GRILL,
            status=StationStatus.ACTIVE,
        )
        db.add(station)

        staff = StaffMember(
            name="Test Staff",
            email="staff@test.com",
            phone="1234567890",
            role="chef",
            is_active=True,
        )
        db.add(staff)
        db.commit()

        # Create order with items
        order = Order(staff_id=staff.id, table_no=5, status="pending")
        db.add(order)
        db.commit()

        order_item = OrderItem(
            order_id=order.id, menu_item_id=1, quantity=2, price=15.99
        )
        db.add(order_item)
        db.commit()

        # Create KDS items
        kds_items = [
            KDSOrderItem(
                order_item_id=order_item.id,
                station_id=station.id,
                display_name="Test Item 1",
                quantity=1,
                status=DisplayStatus.PENDING,
            ),
            KDSOrderItem(
                order_item_id=order_item.id,
                station_id=station.id,
                display_name="Test Item 2",
                quantity=1,
                status=DisplayStatus.IN_PROGRESS,
            ),
        ]
        db.add_all(kds_items)
        db.commit()

        # Get station items
        response = client.get(
            f"/api/v1/kds/stations/{station.id}/items", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert any(item["display_name"] == "Test Item 1" for item in data)
        assert any(item["status"] == "in_progress" for item in data)

    def test_item_lifecycle_endpoints(
        self, client: TestClient, db: Session, auth_headers: dict
    ):
        """Test item status update endpoints"""
        # Create test data
        station = KitchenStation(
            name="Test Station",
            station_type=StationType.GRILL,
            status=StationStatus.ACTIVE,
        )
        db.add(station)

        staff = StaffMember(
            name="Test Staff",
            email="staff@test.com",
            phone="1234567890",
            role="chef",
            is_active=True,
        )
        db.add(staff)
        db.commit()

        # Create order and KDS item
        order = Order(staff_id=staff.id, table_no=5, status="pending")
        db.add(order)
        db.commit()

        order_item = OrderItem(
            order_id=order.id, menu_item_id=1, quantity=1, price=15.99
        )
        db.add(order_item)
        db.commit()

        kds_item = KDSOrderItem(
            order_item_id=order_item.id,
            station_id=station.id,
            display_name="Test Item",
            quantity=1,
            status=DisplayStatus.PENDING,
        )
        db.add(kds_item)
        db.commit()

        # Mock auth to include user ID
        auth_headers["X-User-Id"] = str(staff.id)

        # Test acknowledge
        response = client.post(
            f"/api/v1/kds/items/{kds_item.id}/acknowledge", headers=auth_headers
        )
        assert response.status_code == 200

        # Test start
        response = client.post(
            f"/api/v1/kds/items/{kds_item.id}/start", headers=auth_headers
        )
        assert response.status_code == 200

        # Test complete
        response = client.post(
            f"/api/v1/kds/items/{kds_item.id}/complete", headers=auth_headers
        )
        assert response.status_code == 200

        # Test recall
        response = client.post(
            f"/api/v1/kds/items/{kds_item.id}/recall?reason=Customer%20request",
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_station_summary(self, client: TestClient, db: Session, auth_headers: dict):
        """Test getting station summary statistics"""
        # Create station
        station = KitchenStation(
            name="Test Station",
            station_type=StationType.GRILL,
            status=StationStatus.ACTIVE,
        )
        db.add(station)
        db.commit()

        # Get summary
        response = client.get(
            f"/api/v1/kds/stations/{station.id}/summary", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["station_id"] == station.id
        assert data["station_name"] == "Test Station"
        assert "active_items" in data
        assert "pending_items" in data
        assert "average_wait_time" in data

    def test_route_order_endpoint(
        self, client: TestClient, db: Session, auth_headers: dict
    ):
        """Test routing an order to stations"""
        # Create station
        station = KitchenStation(
            name="Test Station",
            station_type=StationType.GRILL,
            status=StationStatus.ACTIVE,
        )
        db.add(station)

        # Create staff and order
        staff = StaffMember(
            name="Test Staff",
            email="staff@test.com",
            phone="1234567890",
            role="server",
            is_active=True,
        )
        db.add(staff)
        db.commit()

        order = Order(staff_id=staff.id, table_no=5, status="pending")
        db.add(order)
        db.commit()

        # Route order
        response = client.post(
            f"/api/v1/kds/orders/{order.id}/route", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "items_routed" in data

    def test_websocket_connection(self, client: TestClient, db: Session):
        """Test WebSocket connection for real-time updates"""
        # Create station
        station = KitchenStation(
            name="Test Station",
            station_type=StationType.GRILL,
            status=StationStatus.ACTIVE,
        )
        db.add(station)
        db.commit()

        # Test WebSocket connection
        with client.websocket_connect(f"/api/v1/kds/ws/{station.id}") as websocket:
            # Should receive initial data
            data = websocket.receive_json()
            assert data["type"] == "initial_data"
            assert "items" in data["data"]

            # Test heartbeat
            websocket.send_text("ping")
            response = websocket.receive_text()
            assert response == "pong"

    def test_error_handling(self, client: TestClient, auth_headers: dict):
        """Test API error handling"""
        # Test getting non-existent station
        response = client.get("/api/v1/kds/stations/999", headers=auth_headers)
        assert response.status_code == 404
        assert response.json()["detail"] == "Station not found"

        # Test invalid station creation
        invalid_data = {"name": "Test Station", "station_type": "invalid_type"}
        response = client.post(
            "/api/v1/kds/stations", json=invalid_data, headers=auth_headers
        )
        assert response.status_code == 422  # Validation error
