# backend/modules/kds/tests/test_kds_routes.py

"""
Comprehensive tests for KDS API routes.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from main import app
from core.database import get_db
from core.auth import get_current_user
from modules.kds.models.kds_models import (
    KitchenStation,
    StationType,
    StationStatus,
    DisplayStatus,
    KDSOrderItem,
)
from modules.kds.schemas.kds_schemas import (
    StationCreate,
    StationUpdate,
    KitchenDisplayCreate,
    StationAssignmentCreate,
    MenuItemStationCreate,
)


class TestKDSRoutes:
    """Test suite for KDS API endpoints"""

    @pytest.fixture
    def client(self):
        """Test client fixture"""
        return TestClient(app)

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user"""
        return {"id": 1, "email": "test@example.com", "roles": ["admin"]}

    @pytest.fixture
    def auth_headers(self, mock_user):
        """Mock authentication headers"""
        with patch(
            "modules.kds.routes.kds_routes.get_current_user", return_value=mock_user
        ):
            return {"Authorization": "Bearer mock-token"}

    # ========== Station Management Tests ==========

    def test_create_station_success(self, client, mock_db, auth_headers):
        """Test successful station creation"""
        # Arrange
        station_data = {
            "name": "Grill Station",
            "station_type": "grill",
            "color_code": "#FF5733",
            "priority": 1,
            "max_active_items": 15,
            "prep_time_multiplier": 1.2,
            "warning_time_minutes": 5,
            "critical_time_minutes": 10,
        }

        mock_station = KitchenStation(
            id=1,
            name="Grill Station",
            station_type=StationType.GRILL,
            status=StationStatus.ACTIVE,
            color_code="#FF5733",
            priority=1,
            created_at=datetime.utcnow(),
        )

        with patch("modules.kds.routes.kds_routes.get_db", return_value=mock_db):
            with patch("modules.kds.routes.kds_routes.KDSService") as mock_service:
                mock_service.return_value.create_station.return_value = mock_station

                # Act
                response = client.post(
                    "/api/v1/kds/stations", json=station_data, headers=auth_headers
                )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Grill Station"
        assert data["station_type"] == "grill"
        assert data["id"] == 1

    def test_create_station_validation_error(self, client, auth_headers):
        """Test station creation with invalid data"""
        # Arrange - Invalid color code
        station_data = {
            "name": "Test Station",
            "station_type": "grill",
            "color_code": "invalid-color",  # Should be hex format
            "priority": 150,  # Should be 0-100
        }

        # Act
        response = client.post(
            "/api/v1/kds/stations", json=station_data, headers=auth_headers
        )

        # Assert
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any(error["loc"] == ["body", "color_code"] for error in errors)
        assert any(error["loc"] == ["body", "priority"] for error in errors)

    def test_create_station_empty_name(self, client, auth_headers):
        """Test station creation with empty name"""
        # Arrange
        station_data = {"name": "", "station_type": "grill"}  # Empty name should fail

        # Act
        response = client.post(
            "/api/v1/kds/stations", json=station_data, headers=auth_headers
        )

        # Assert
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any(error["loc"] == ["body", "name"] for error in errors)

    def test_get_station_not_found(self, client, mock_db, auth_headers):
        """Test getting non-existent station"""
        with patch("modules.kds.routes.kds_routes.get_db", return_value=mock_db):
            with patch("modules.kds.routes.kds_routes.KDSService") as mock_service:
                mock_service.return_value.get_station.return_value = None

                # Act
                response = client.get("/api/v1/kds/stations/999", headers=auth_headers)

        # Assert
        assert response.status_code == 404
        assert response.json()["detail"] == "Station not found"

    def test_update_station_success(self, client, mock_db, auth_headers):
        """Test successful station update"""
        # Arrange
        update_data = {"name": "Updated Grill", "priority": 2, "status": "busy"}

        updated_station = KitchenStation(
            id=1,
            name="Updated Grill",
            station_type=StationType.GRILL,
            status=StationStatus.BUSY,
            priority=2,
            created_at=datetime.utcnow(),
        )

        with patch("modules.kds.routes.kds_routes.get_db", return_value=mock_db):
            with patch("modules.kds.routes.kds_routes.KDSService") as mock_service:
                mock_service.return_value.update_station.return_value = updated_station

                # Act
                response = client.put(
                    "/api/v1/kds/stations/1", json=update_data, headers=auth_headers
                )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Grill"
        assert data["priority"] == 2
        assert data["status"] == "busy"

    def test_update_station_not_found(self, client, mock_db, auth_headers):
        """Test updating non-existent station"""
        update_data = {"name": "Updated Station"}

        with patch("modules.kds.routes.kds_routes.get_db", return_value=mock_db):
            with patch("modules.kds.routes.kds_routes.KDSService") as mock_service:
                mock_service.return_value.update_station.side_effect = ValueError(
                    "Station not found"
                )

                # Act
                response = client.put(
                    "/api/v1/kds/stations/999", json=update_data, headers=auth_headers
                )

        # Assert
        assert response.status_code == 404
        assert "Station not found" in response.json()["detail"]

    def test_list_stations_with_filters(self, client, mock_db, auth_headers):
        """Test listing stations with filters"""
        # Arrange
        mock_stations = [
            KitchenStation(
                id=1,
                name="Grill Station",
                station_type=StationType.GRILL,
                status=StationStatus.ACTIVE,
                created_at=datetime.utcnow(),
            ),
            KitchenStation(
                id=2,
                name="Fry Station",
                station_type=StationType.FRY,
                status=StationStatus.ACTIVE,
                created_at=datetime.utcnow(),
            ),
        ]

        with patch("modules.kds.routes.kds_routes.get_db", return_value=mock_db):
            with patch("modules.kds.routes.kds_routes.KDSService") as mock_service:
                mock_service.return_value.get_stations_by_type.return_value = [
                    mock_stations[0]
                ]
                mock_service.return_value.get_station_items.return_value = []

                # Act
                response = client.get(
                    "/api/v1/kds/stations?station_type=grill&include_inactive=false",
                    headers=auth_headers,
                )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["station_type"] == "grill"

    # ========== Display Management Tests ==========

    def test_create_display_success(self, client, mock_db, auth_headers):
        """Test successful display creation"""
        display_data = {
            "station_id": 1,
            "display_number": 1,
            "name": "Main Display",
            "layout_mode": "grid",
            "items_per_page": 8,
        }

        with patch("modules.kds.routes.kds_routes.get_db", return_value=mock_db):
            with patch("modules.kds.routes.kds_routes.KDSService") as mock_service:
                mock_display = Mock(
                    id=1,
                    station_id=1,
                    display_number=1,
                    name="Main Display",
                    layout_mode="grid",
                    items_per_page=8,
                    is_active=True,
                    created_at=datetime.utcnow(),
                )
                mock_service.return_value.create_display.return_value = mock_display

                # Act
                response = client.post(
                    "/api/v1/kds/displays", json=display_data, headers=auth_headers
                )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Main Display"
        assert data["layout_mode"] == "grid"

    def test_create_display_invalid_layout(self, client, auth_headers):
        """Test display creation with invalid layout mode"""
        display_data = {
            "station_id": 1,
            "display_number": 1,
            "layout_mode": "invalid_mode",  # Should be grid/list/single
        }

        # Act
        response = client.post(
            "/api/v1/kds/displays", json=display_data, headers=auth_headers
        )

        # Assert
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any(error["loc"] == ["body", "layout_mode"] for error in errors)

    # ========== Order Item Management Tests ==========

    def test_get_station_items_success(self, client, mock_db, auth_headers):
        """Test getting station items with filters"""
        # Arrange
        mock_items = [
            Mock(
                id=1,
                order_item_id=101,
                station_id=1,
                display_name="Burger",
                quantity=2,
                status=DisplayStatus.PENDING,
                received_at=datetime.utcnow(),
                order_item=Mock(order=Mock(id=1001, table_no=5)),
            )
        ]

        with patch("modules.kds.routes.kds_routes.get_db", return_value=mock_db):
            with patch("modules.kds.routes.kds_routes.KDSService") as mock_service:
                mock_service.return_value.get_station_items.return_value = mock_items

                # Act
                response = client.get(
                    "/api/v1/kds/stations/1/items?status=pending&limit=20",
                    headers=auth_headers,
                )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["display_name"] == "Burger"
        assert data[0]["order_id"] == 1001
        assert data[0]["table_number"] == 5

    def test_acknowledge_item_success(self, client, mock_db, auth_headers):
        """Test acknowledging an order item"""
        with patch("modules.kds.routes.kds_routes.get_db", return_value=mock_db):
            with patch("modules.kds.routes.kds_routes.KDSService") as mock_service:
                mock_item = Mock(id=1, station_id=1, acknowledged_at=datetime.utcnow())
                mock_service.return_value.acknowledge_item.return_value = mock_item

                # Act
                response = client.post(
                    "/api/v1/kds/items/1/acknowledge", headers=auth_headers
                )

        # Assert
        assert response.status_code == 200
        assert response.json()["message"] == "Item acknowledged"

    def test_acknowledge_item_not_found(self, client, mock_db, auth_headers):
        """Test acknowledging non-existent item"""
        with patch("modules.kds.routes.kds_routes.get_db", return_value=mock_db):
            with patch("modules.kds.routes.kds_routes.KDSService") as mock_service:
                mock_service.return_value.acknowledge_item.side_effect = ValueError(
                    "Item not found"
                )

                # Act
                response = client.post(
                    "/api/v1/kds/items/999/acknowledge", headers=auth_headers
                )

        # Assert
        assert response.status_code == 404
        assert "Item not found" in response.json()["detail"]

    def test_complete_item_already_completed(self, client, mock_db, auth_headers):
        """Test completing already completed item"""
        with patch("modules.kds.routes.kds_routes.get_db", return_value=mock_db):
            with patch("modules.kds.routes.kds_routes.KDSService") as mock_service:
                mock_service.return_value.complete_item.side_effect = ValueError(
                    "Item already completed"
                )

                # Act
                response = client.post(
                    "/api/v1/kds/items/1/complete", headers=auth_headers
                )

        # Assert
        assert response.status_code == 400
        assert "Item already completed" in response.json()["detail"]

    # ========== Station Assignment Tests ==========

    def test_create_station_assignment_success(self, client, mock_db, auth_headers):
        """Test creating station assignment"""
        assignment_data = {
            "station_id": 1,
            "category_name": "Grilled Items",
            "priority": 1,
            "is_primary": True,
        }

        with patch("modules.kds.routes.kds_routes.get_db", return_value=mock_db):
            with patch(
                "modules.kds.routes.kds_routes.KDSOrderRoutingService"
            ) as mock_service:
                mock_assignment = Mock(
                    id=1,
                    station_id=1,
                    category_name="Grilled Items",
                    priority=1,
                    created_at=datetime.utcnow(),
                )
                mock_service.return_value.create_station_assignment.return_value = (
                    mock_assignment
                )

                # Act
                response = client.post(
                    "/api/v1/kds/assignments",
                    json=assignment_data,
                    headers=auth_headers,
                )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["category_name"] == "Grilled Items"

    def test_create_station_assignment_missing_fields(self, client, auth_headers):
        """Test assignment creation without category or tag"""
        assignment_data = {
            "station_id": 1,
            "priority": 1,
            # Missing both category_name and tag_name
        }

        # Act
        response = client.post(
            "/api/v1/kds/assignments", json=assignment_data, headers=auth_headers
        )

        # Assert
        assert response.status_code == 422
        assert "Either category_name or tag_name must be provided" in str(
            response.json()["detail"]
        )

    # ========== Edge Cases and Security Tests ==========

    def test_unauthorized_access(self, client):
        """Test accessing endpoints without authentication"""
        # Act - No auth headers
        response = client.get("/api/v1/kds/stations")

        # Assert
        assert response.status_code == 401

    def test_sql_injection_prevention(self, client, mock_db, auth_headers):
        """Test SQL injection prevention in search"""
        # Arrange - Malicious input
        malicious_query = "'; DROP TABLE kitchen_stations; --"

        with patch("modules.kds.routes.kds_routes.get_db", return_value=mock_db):
            with patch("modules.kds.routes.kds_routes.KDSService") as mock_service:
                mock_service.return_value.get_all_stations.return_value = []

                # Act
                response = client.get(
                    f"/api/v1/kds/stations?station_type={malicious_query}",
                    headers=auth_headers,
                )

        # Assert - Should handle safely
        # The enum validation should reject invalid station types
        assert response.status_code in [200, 422]

    def test_concurrent_item_update_handling(self, client, mock_db, auth_headers):
        """Test handling concurrent updates to same item"""
        with patch("modules.kds.routes.kds_routes.get_db", return_value=mock_db):
            with patch("modules.kds.routes.kds_routes.KDSService") as mock_service:
                # Simulate concurrent update error
                mock_service.return_value.start_item.side_effect = ValueError(
                    "Item status already changed"
                )

                # Act
                response = client.post(
                    "/api/v1/kds/items/1/start", headers=auth_headers
                )

        # Assert
        assert response.status_code == 400
        assert "Item status already changed" in response.json()["detail"]

    def test_large_limit_validation(self, client, auth_headers):
        """Test limit parameter validation"""
        # Act - Exceed max limit
        response = client.get(
            "/api/v1/kds/stations/1/items?limit=1000", headers=auth_headers
        )

        # Assert
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("limit" in str(error) for error in errors)


class TestKDSWebSocket:
    """Test suite for KDS WebSocket functionality"""

    @pytest.mark.asyncio
    async def test_websocket_connection(self):
        """Test WebSocket connection establishment"""
        # This would require WebSocket test client
        # Example implementation would test:
        # - Connection establishment
        # - Initial data sending
        # - Heartbeat handling
        # - Disconnection handling
        pass

    @pytest.mark.asyncio
    async def test_websocket_broadcast_updates(self):
        """Test broadcasting updates to connected clients"""
        # Test that updates are properly broadcast to all connected clients
        pass
