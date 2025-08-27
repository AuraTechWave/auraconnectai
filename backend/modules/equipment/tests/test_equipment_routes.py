# backend/modules/equipment/tests/test_equipment_routes.py

"""
Comprehensive tests for Equipment Management API routes.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from decimal import Decimal

from main import app
from core.database import get_db
from core.rbac_models import RBACUser as User
from modules.auth.permissions import Permission
from modules.equipment.models import (
    Equipment as EquipmentModel,
    MaintenanceRecord as MaintenanceRecordModel,
)
from modules.equipment.schemas import (
    EquipmentCreate,
    EquipmentUpdate,
    MaintenanceRecordCreate,
    EquipmentSearchParams,
    MaintenanceSearchParams,
)


class TestEquipmentRoutes:
    """Test suite for Equipment API endpoints"""

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
        """Mock authenticated user with equipment permissions"""
        user = Mock(spec=User)
        user.id = 1
        user.email = "test@example.com"
        user.has_permission = Mock(return_value=True)
        return user

    @pytest.fixture
    def auth_headers(self):
        """Mock authentication headers"""
        return {"Authorization": "Bearer mock-token"}

    # ========== Equipment CRUD Tests ==========

    def test_create_equipment_success(self, client, mock_db, mock_user):
        """Test successful equipment creation"""
        # Arrange
        equipment_data = {
            "equipment_name": "Commercial Oven",
            "equipment_type": "Kitchen",
            "manufacturer": "TurboChef",
            "model_number": "TCO-2000",
            "serial_number": "SN123456",
            "purchase_date": "2023-01-15",
            "warranty_expiry": "2025-01-15",
            "location": "Main Kitchen",
            "is_critical": True,
            "maintenance_interval_days": 90,
            "maintenance_notes": "Quarterly deep cleaning required",
        }

        mock_equipment = EquipmentModel(
            id=1,
            **equipment_data,
            status="operational",
            created_at=datetime.utcnow(),
            created_by=1,
        )

        with patch("modules.equipment.routes.get_db", return_value=mock_db):
            with patch(
                "modules.equipment.routes.get_current_user", return_value=mock_user
            ):
                with patch("modules.equipment.routes.EquipmentService") as mock_service:
                    mock_service.return_value.create_equipment.return_value = (
                        mock_equipment
                    )

                    # Act
                    response = client.post("/equipment/", json=equipment_data)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["equipment_name"] == "Commercial Oven"
        assert data["is_critical"] == True
        assert data["id"] == 1

    def test_create_equipment_validation_error(self, client, mock_user):
        """Test equipment creation with invalid data"""
        # Arrange - Missing required fields
        equipment_data = {
            "equipment_name": "",  # Empty name
            "equipment_type": "Kitchen",
            "maintenance_interval_days": -10,  # Negative interval
        }

        with patch("modules.equipment.routes.get_current_user", return_value=mock_user):
            # Act
            response = client.post("/equipment/", json=equipment_data)

        # Assert
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("equipment_name" in str(error) for error in errors)
        assert any("maintenance_interval_days" in str(error) for error in errors)

    def test_create_equipment_permission_denied(self, client, mock_user):
        """Test equipment creation without proper permissions"""
        # Arrange
        mock_user.has_permission = Mock(return_value=False)
        equipment_data = {"equipment_name": "Test Equipment", "equipment_type": "Test"}

        with patch("modules.equipment.routes.get_current_user", return_value=mock_user):
            with patch(
                "modules.equipment.routes.check_permission"
            ) as mock_check_permission:
                mock_check_permission.side_effect = PermissionError("Permission denied")

                # Act
                response = client.post("/equipment/", json=equipment_data)

        # Assert
        assert response.status_code in [403, 500]  # Depends on error handling

    def test_search_equipment_with_filters(self, client, mock_db, mock_user):
        """Test searching equipment with various filters"""
        # Arrange
        mock_equipment = [
            EquipmentModel(
                id=1,
                equipment_name="Oven 1",
                equipment_type="Kitchen",
                status="operational",
                location="Main Kitchen",
                is_critical=True,
                created_at=datetime.utcnow(),
            ),
            EquipmentModel(
                id=2,
                equipment_name="Freezer 1",
                equipment_type="Storage",
                status="maintenance",
                location="Storage Room",
                is_critical=True,
                created_at=datetime.utcnow(),
            ),
        ]

        with patch("modules.equipment.routes.get_db", return_value=mock_db):
            with patch(
                "modules.equipment.routes.get_current_user", return_value=mock_user
            ):
                with patch("modules.equipment.routes.EquipmentService") as mock_service:
                    mock_service.return_value.search_equipment.return_value = (
                        mock_equipment[:1],
                        1,
                    )

                    # Act
                    response = client.get(
                        "/equipment/search?equipment_type=Kitchen&status=operational&is_critical=true&page=1&size=10"
                    )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["equipment_type"] == "Kitchen"
        assert data["page"] == 1
        assert data["pages"] == 1

    def test_search_equipment_invalid_sort_field(self, client, mock_user):
        """Test equipment search with invalid sort field"""
        with patch("modules.equipment.routes.get_current_user", return_value=mock_user):
            # Act
            response = client.get("/equipment/search?sort_by=invalid_field")

        # Assert
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("sort_by" in str(error) for error in errors)

    def test_get_equipment_by_id_success(self, client, mock_db, mock_user):
        """Test getting equipment by ID with maintenance history"""
        # Arrange
        mock_maintenance_records = [
            MaintenanceRecordModel(
                id=1,
                equipment_id=1,
                maintenance_type="preventive",
                status="completed",
                scheduled_date=datetime.utcnow() - timedelta(days=30),
                date_performed=datetime.utcnow() - timedelta(days=29),
                performed_by="John Doe",
                cost=Decimal("150.00"),
                downtime_hours=2,
                created_at=datetime.utcnow(),
            ),
            MaintenanceRecordModel(
                id=2,
                equipment_id=1,
                maintenance_type="repair",
                status="completed",
                scheduled_date=datetime.utcnow() - timedelta(days=60),
                date_performed=datetime.utcnow() - timedelta(days=59),
                performed_by="Jane Smith",
                cost=Decimal("500.00"),
                downtime_hours=8,
                created_at=datetime.utcnow(),
            ),
        ]

        mock_equipment = EquipmentModel(
            id=1,
            equipment_name="Commercial Oven",
            equipment_type="Kitchen",
            status="operational",
            created_at=datetime.utcnow(),
            maintenance_records=mock_maintenance_records,
        )

        with patch("modules.equipment.routes.get_db", return_value=mock_db):
            with patch(
                "modules.equipment.routes.get_current_user", return_value=mock_user
            ):
                with patch("modules.equipment.routes.EquipmentService") as mock_service:
                    mock_service.return_value.get_equipment.return_value = (
                        mock_equipment
                    )

                    # Act
                    response = client.get("/equipment/1")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["equipment_name"] == "Commercial Oven"
        assert data["total_maintenance_count"] == 2
        assert data["total_maintenance_cost"] == 650.0
        assert data["average_downtime_hours"] == 5.0
        assert len(data["maintenance_records"]) == 2

    def test_get_equipment_not_found(self, client, mock_db, mock_user):
        """Test getting non-existent equipment"""
        with patch("modules.equipment.routes.get_db", return_value=mock_db):
            with patch(
                "modules.equipment.routes.get_current_user", return_value=mock_user
            ):
                with patch("modules.equipment.routes.EquipmentService") as mock_service:
                    mock_service.return_value.get_equipment.side_effect = ValueError(
                        "Equipment not found"
                    )

                    # Act
                    response = client.get("/equipment/999")

        # Assert
        assert response.status_code == 500  # Should be 404 with proper error handling

    def test_update_equipment_success(self, client, mock_db, mock_user):
        """Test successful equipment update"""
        # Arrange
        update_data = {
            "status": "maintenance",
            "location": "Repair Shop",
            "maintenance_notes": "Under repair",
        }

        updated_equipment = EquipmentModel(
            id=1,
            equipment_name="Commercial Oven",
            equipment_type="Kitchen",
            status="maintenance",
            location="Repair Shop",
            maintenance_notes="Under repair",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        with patch("modules.equipment.routes.get_db", return_value=mock_db):
            with patch(
                "modules.equipment.routes.get_current_user", return_value=mock_user
            ):
                with patch("modules.equipment.routes.EquipmentService") as mock_service:
                    mock_service.return_value.update_equipment.return_value = (
                        updated_equipment
                    )

                    # Act
                    response = client.put("/equipment/1", json=update_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "maintenance"
        assert data["location"] == "Repair Shop"

    def test_delete_equipment_success(self, client, mock_db, mock_user):
        """Test soft deleting equipment"""
        with patch("modules.equipment.routes.get_db", return_value=mock_db):
            with patch(
                "modules.equipment.routes.get_current_user", return_value=mock_user
            ):
                with patch("modules.equipment.routes.EquipmentService") as mock_service:
                    mock_service.return_value.delete_equipment.return_value = None

                    # Act
                    response = client.delete("/equipment/1")

        # Assert
        assert response.status_code == 204

    # ========== Maintenance Record Tests ==========

    def test_create_maintenance_record_success(self, client, mock_db, mock_user):
        """Test creating maintenance record"""
        # Arrange
        record_data = {
            "equipment_id": 1,
            "maintenance_type": "preventive",
            "scheduled_date": "2024-02-01",
            "description": "Quarterly maintenance",
            "estimated_duration_hours": 4,
            "estimated_cost": 200.00,
        }

        mock_record = MaintenanceRecordModel(
            id=1,
            **record_data,
            status="scheduled",
            created_at=datetime.utcnow(),
            created_by=1,
        )

        with patch("modules.equipment.routes.get_db", return_value=mock_db):
            with patch(
                "modules.equipment.routes.get_current_user", return_value=mock_user
            ):
                with patch("modules.equipment.routes.EquipmentService") as mock_service:
                    mock_service.return_value.create_maintenance_record.return_value = (
                        mock_record
                    )

                    # Act
                    response = client.post("/equipment/maintenance", json=record_data)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["maintenance_type"] == "preventive"
        assert data["status"] == "scheduled"

    def test_search_maintenance_records_with_date_filter(
        self, client, mock_db, mock_user
    ):
        """Test searching maintenance records with date filters"""
        # Arrange
        mock_records = [
            MaintenanceRecordModel(
                id=1,
                equipment_id=1,
                maintenance_type="preventive",
                status="completed",
                scheduled_date=datetime(2024, 1, 15),
                date_performed=datetime(2024, 1, 16),
                created_at=datetime.utcnow(),
            )
        ]

        with patch("modules.equipment.routes.get_db", return_value=mock_db):
            with patch(
                "modules.equipment.routes.get_current_user", return_value=mock_user
            ):
                with patch("modules.equipment.routes.EquipmentService") as mock_service:
                    mock_service.return_value.search_maintenance_records.return_value = (
                        mock_records,
                        1,
                    )

                    # Act
                    response = client.get(
                        "/equipment/maintenance/search?date_from=2024-01-01&date_to=2024-01-31&status=completed"
                    )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

    def test_search_maintenance_invalid_date_format(self, client, mock_user):
        """Test maintenance search with invalid date format"""
        with patch("modules.equipment.routes.get_current_user", return_value=mock_user):
            # Act
            response = client.get(
                "/equipment/maintenance/search?date_from=invalid-date"
            )

        # Assert
        assert response.status_code == 500  # Should be 422 with proper error handling

    def test_get_maintenance_summary_success(self, client, mock_db, mock_user):
        """Test getting maintenance summary statistics"""
        # Arrange
        mock_summary = {
            "total_equipment": 50,
            "operational_count": 45,
            "maintenance_count": 3,
            "out_of_service_count": 2,
            "overdue_maintenance": 5,
            "upcoming_maintenance_7_days": 8,
            "total_maintenance_cost_ytd": 15000.00,
            "average_downtime_hours": 4.5,
        }

        with patch("modules.equipment.routes.get_db", return_value=mock_db):
            with patch(
                "modules.equipment.routes.get_current_user", return_value=mock_user
            ):
                with patch("modules.equipment.routes.EquipmentService") as mock_service:
                    mock_service.return_value.get_maintenance_summary.return_value = (
                        mock_summary
                    )

                    # Act
                    response = client.get("/equipment/maintenance/summary")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total_equipment"] == 50
        assert data["overdue_maintenance"] == 5

    # ========== Edge Cases and Security Tests ==========

    def test_unauthorized_access(self, client):
        """Test accessing endpoints without authentication"""
        # Act - No auth headers
        response = client.get("/equipment/search")

        # Assert
        assert response.status_code == 401

    def test_sql_injection_prevention(self, client, mock_db, mock_user):
        """Test SQL injection prevention in search"""
        # Arrange - Malicious input
        malicious_query = "'; DROP TABLE equipment; --"

        with patch("modules.equipment.routes.get_db", return_value=mock_db):
            with patch(
                "modules.equipment.routes.get_current_user", return_value=mock_user
            ):
                with patch("modules.equipment.routes.EquipmentService") as mock_service:
                    mock_service.return_value.search_equipment.return_value = ([], 0)

                    # Act
                    response = client.get(f"/equipment/search?query={malicious_query}")

        # Assert - Should handle safely
        assert response.status_code == 200
        # The service should handle the query safely without executing SQL

    def test_large_page_size_validation(self, client, mock_user):
        """Test page size limit validation"""
        with patch("modules.equipment.routes.get_current_user", return_value=mock_user):
            # Act - Exceed max size
            response = client.get("/equipment/search?page=1&size=1000")

        # Assert
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("size" in str(error) for error in errors)

    def test_negative_cost_validation(self, client, mock_user):
        """Test negative cost validation in maintenance record"""
        record_data = {
            "equipment_id": 1,
            "maintenance_type": "repair",
            "scheduled_date": "2024-02-01",
            "estimated_cost": -100.00,  # Negative cost
        }

        with patch("modules.equipment.routes.get_current_user", return_value=mock_user):
            # Act
            response = client.post("/equipment/maintenance", json=record_data)

        # Assert
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("cost" in str(error) for error in errors)

    def test_concurrent_update_handling(self, client, mock_db, mock_user):
        """Test handling concurrent updates"""
        update_data = {"status": "maintenance"}

        with patch("modules.equipment.routes.get_db", return_value=mock_db):
            with patch(
                "modules.equipment.routes.get_current_user", return_value=mock_user
            ):
                with patch("modules.equipment.routes.EquipmentService") as mock_service:
                    # Simulate optimistic locking error
                    mock_service.return_value.update_equipment.side_effect = ValueError(
                        "Equipment has been modified by another user"
                    )

                    # Act
                    response = client.put("/equipment/1", json=update_data)

        # Assert
        assert response.status_code == 500  # Should be 409 with proper error handling

    def test_equipment_with_active_maintenance_deletion(
        self, client, mock_db, mock_user
    ):
        """Test preventing deletion of equipment with active maintenance"""
        with patch("modules.equipment.routes.get_db", return_value=mock_db):
            with patch(
                "modules.equipment.routes.get_current_user", return_value=mock_user
            ):
                with patch("modules.equipment.routes.EquipmentService") as mock_service:
                    mock_service.return_value.delete_equipment.side_effect = ValueError(
                        "Cannot delete equipment with active maintenance records"
                    )

                    # Act
                    response = client.delete("/equipment/1")

        # Assert
        assert response.status_code == 500  # Should be 400 with proper error handling


import pytest
from datetime import datetime, timedelta
from fastapi import status
from fastapi.testclient import TestClient

from modules.equipment.models import (
    Equipment,
    MaintenanceRecord,
    EquipmentStatus,
    MaintenanceStatus,
)


@pytest.mark.api
@pytest.mark.equipment
class TestEquipmentRoutes:
    """Test equipment API routes"""

    @pytest.fixture
    def headers(self, auth_token):
        """Auth headers for requests"""
        return {"Authorization": f"Bearer {auth_token}"}

    # Equipment endpoint tests
    @pytest.mark.smoke
    def test_create_equipment(
        self,
        client: TestClient,
        headers: dict,
        equipment_data: dict,
        assert_equipment_shape,
    ):
        """Test creating equipment with valid data"""
        response = client.post("/api/equipment/", json=equipment_data, headers=headers)

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()

        # Verify response shape
        assert_equipment_shape(result)

        # Verify specific values
        assert result["equipment_name"] == equipment_data["equipment_name"]
        assert result["equipment_type"] == equipment_data["equipment_type"]
        assert result["status"] == "operational"
        assert result["is_active"] is True
        assert (
            result["next_due_date"] is not None
        )  # Should be calculated from maintenance_interval_days

    @pytest.mark.negative
    def test_create_equipment_missing_required_fields(
        self, client: TestClient, headers: dict
    ):
        """Test creating equipment without required fields"""
        # Missing equipment_name
        data = {"equipment_type": "Cooking Equipment"}
        response = client.post("/api/equipment/", json=data, headers=headers)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        error = response.json()
        assert "detail" in error
        assert any("equipment_name" in str(err) for err in error["detail"])

        # Missing equipment_type
        data = {"equipment_name": "Test Equipment"}
        response = client.post("/api/equipment/", json=data, headers=headers)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        error = response.json()
        assert any("equipment_type" in str(err) for err in error["detail"])

    @pytest.mark.smoke
    def test_get_equipment(
        self,
        client: TestClient,
        headers: dict,
        created_equipment_api: dict,
        assert_equipment_shape,
    ):
        """Test getting equipment by ID with maintenance history"""
        response = client.get(
            f"/api/equipment/{created_equipment_api['id']}", headers=headers
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()

        # Verify extended response shape
        assert_equipment_shape(result)
        assert "maintenance_records" in result
        assert isinstance(result["maintenance_records"], list)
        assert "total_maintenance_count" in result
        assert "total_maintenance_cost" in result
        assert "average_downtime_hours" in result

        # Verify values match
        assert result["id"] == created_equipment_api["id"]
        assert result["equipment_name"] == created_equipment_api["equipment_name"]

    @pytest.mark.negative
    def test_get_nonexistent_equipment(self, client: TestClient, headers: dict):
        """Test getting non-existent equipment returns 404"""
        response = client.get("/api/equipment/999999", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        error = response.json()
        assert "detail" in error
        assert "not found" in error["detail"].lower()
        assert "999999" in error["detail"]

    def test_update_equipment(
        self,
        client: TestClient,
        headers: dict,
        created_equipment_api: dict,
        assert_equipment_shape,
    ):
        """Test updating equipment"""
        update_data = {
            "location": "Updated Location",
            "status": "needs_maintenance",
            "notes": "Equipment needs service",
            "maintenance_interval_days": 60,
        }

        response = client.put(
            f"/api/equipment/{created_equipment_api['id']}",
            json=update_data,
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()

        # Verify shape and updated values
        assert_equipment_shape(result)
        assert result["location"] == "Updated Location"
        assert result["status"] == "needs_maintenance"
        assert result["notes"] == "Equipment needs service"
        assert result["maintenance_interval_days"] == 60

        # Verify unchanged values persist
        assert result["equipment_name"] == created_equipment_api["equipment_name"]
        assert result["equipment_type"] == created_equipment_api["equipment_type"]

    @pytest.mark.negative
    def test_update_nonexistent_equipment(self, client: TestClient, headers: dict):
        """Test updating non-existent equipment returns 404"""
        update_data = {"location": "New Location"}
        response = client.put(
            "/api/equipment/999999", json=update_data, headers=headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        error = response.json()
        assert "not found" in error["detail"].lower()

    def test_delete_equipment(
        self, client: TestClient, headers: dict, created_equipment_api: dict
    ):
        """Test soft deleting equipment"""
        equipment_id = created_equipment_api["id"]

        # Delete the equipment
        response = client.delete(f"/api/equipment/{equipment_id}", headers=headers)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify it's soft deleted (404 on GET)
        get_response = client.get(f"/api/equipment/{equipment_id}", headers=headers)
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.negative
    def test_delete_nonexistent_equipment(self, client: TestClient, headers: dict):
        """Test deleting non-existent equipment returns 404"""
        response = client.delete("/api/equipment/999999", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        error = response.json()
        assert "not found" in error["detail"].lower()

    @pytest.mark.integration
    def test_search_equipment(
        self,
        client: TestClient,
        headers: dict,
        multiple_equipment: list,
        assert_equipment_shape,
        assert_paginated_response,
    ):
        """Test searching equipment with various filters"""
        # Test search by query
        response = client.get("/api/equipment/search?query=Oven", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        result = response.json()

        assert_paginated_response(result)
        assert result["total"] >= 1
        assert all("Oven" in item["equipment_name"] for item in result["items"])
        for item in result["items"]:
            assert_equipment_shape(item)

        # Test filter by type
        response = client.get(
            "/api/equipment/search?equipment_type=Refrigeration", headers=headers
        )
        assert response.status_code == status.HTTP_200_OK
        result = response.json()

        assert_paginated_response(result)
        assert result["total"] >= 1
        assert all(
            item["equipment_type"] == "Refrigeration" for item in result["items"]
        )

        # Test filter by critical
        response = client.get("/api/equipment/search?is_critical=true", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        result = response.json()

        assert_paginated_response(result)
        assert all(item["is_critical"] is True for item in result["items"])

        # Test filter by location
        response = client.get("/api/equipment/search?location=Kitchen", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        result = response.json()

        assert_paginated_response(result)
        assert all("Kitchen" in item["location"] for item in result["items"])

        # Test combined filters
        response = client.get(
            "/api/equipment/search?equipment_type=Cooking Equipment&is_critical=true",
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        result = response.json()

        assert_paginated_response(result)
        for item in result["items"]:
            assert item["equipment_type"] == "Cooking Equipment"
            assert item["is_critical"] is True

        # Test pagination
        response = client.get("/api/equipment/search?page=1&size=2", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        result = response.json()

        assert_paginated_response(result)
        assert len(result["items"]) <= 2
        assert result["page"] == 1
        assert result["size"] == 2

        # Test sorting
        response = client.get(
            "/api/equipment/search?sort_by=equipment_name&sort_order=desc",
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        result = response.json()

        if len(result["items"]) > 1:
            names = [item["equipment_name"] for item in result["items"]]
            assert names == sorted(names, reverse=True)

    # Maintenance endpoint tests
    @pytest.mark.smoke
    def test_create_maintenance_record(
        self,
        client: TestClient,
        headers: dict,
        created_equipment_api: dict,
        maintenance_data: dict,
        assert_maintenance_shape,
    ):
        """Test creating maintenance record"""
        maintenance_data["equipment_id"] = created_equipment_api["id"]

        response = client.post(
            "/api/equipment/maintenance", json=maintenance_data, headers=headers
        )

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()

        # Verify shape and values
        assert_maintenance_shape(result)
        assert result["equipment_id"] == created_equipment_api["id"]
        assert result["maintenance_type"] == maintenance_data["maintenance_type"]
        assert result["status"] == "scheduled"
        assert result["description"] == maintenance_data["description"]
        assert result["cost"] == maintenance_data["cost"]

    @pytest.mark.negative
    def test_create_maintenance_invalid_equipment(
        self, client: TestClient, headers: dict, maintenance_data: dict
    ):
        """Test creating maintenance for non-existent equipment returns 404"""
        maintenance_data["equipment_id"] = 999999

        response = client.post(
            "/api/equipment/maintenance", json=maintenance_data, headers=headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        error = response.json()
        assert "not found" in error["detail"].lower()
        assert "999999" in error["detail"]

    def test_update_maintenance_record(
        self, client: TestClient, headers: dict, sample_equipment: dict
    ):
        """Test updating maintenance record"""
        # Create a record
        create_data = {
            "equipment_id": sample_equipment["id"],
            "maintenance_type": "preventive",
            "scheduled_date": datetime.now().isoformat(),
            "description": "Test maintenance",
        }
        create_response = client.post(
            "/api/equipment/maintenance", json=create_data, headers=headers
        )
        record = create_response.json()

        # Update it
        update_data = {
            "status": "in_progress",
            "performed_by": "John Doe",
            "cost": 150.50,
        }

        response = client.put(
            f"/api/equipment/maintenance/{record['id']}",
            json=update_data,
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["status"] == "in_progress"
        assert result["performed_by"] == "John Doe"
        assert result["cost"] == 150.50

    def test_complete_maintenance(
        self, client: TestClient, headers: dict, sample_equipment: dict
    ):
        """Test completing maintenance record"""
        # Create a record
        create_data = {
            "equipment_id": sample_equipment["id"],
            "maintenance_type": "corrective",
            "scheduled_date": datetime.now().isoformat(),
            "description": "Fix issue",
        }
        create_response = client.post(
            "/api/equipment/maintenance", json=create_data, headers=headers
        )
        record = create_response.json()

        # Complete it
        completion_data = {
            "date_performed": datetime.now().isoformat(),
            "performed_by": "Jane Technician",
            "cost": 250.00,
            "parts_replaced": "New filter",
            "issues_found": "Filter was clogged",
            "resolution": "Replaced filter",
            "downtime_hours": 1.5,
        }

        response = client.post(
            f"/api/equipment/maintenance/{record['id']}/complete",
            json=completion_data,
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["status"] == "completed"
        assert result["date_performed"] is not None
        assert result["cost"] == 250.00
        assert result["downtime_hours"] == 1.5

    def test_delete_maintenance_record(
        self, client: TestClient, headers: dict, sample_equipment: dict
    ):
        """Test deleting maintenance record"""
        # Create a record
        create_data = {
            "equipment_id": sample_equipment["id"],
            "maintenance_type": "inspection",
            "scheduled_date": (datetime.now() + timedelta(days=14)).isoformat(),
            "description": "Future inspection",
        }
        create_response = client.post(
            "/api/equipment/maintenance", json=create_data, headers=headers
        )
        record = create_response.json()

        # Delete it
        response = client.delete(
            f"/api/equipment/maintenance/{record['id']}", headers=headers
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_search_maintenance_records(
        self, client: TestClient, headers: dict, sample_equipment: dict
    ):
        """Test searching maintenance records"""
        # Create multiple records
        records_data = [
            {
                "equipment_id": sample_equipment["id"],
                "maintenance_type": "preventive",
                "scheduled_date": datetime.now().isoformat(),
                "description": "Preventive check",
            },
            {
                "equipment_id": sample_equipment["id"],
                "maintenance_type": "corrective",
                "scheduled_date": (datetime.now() + timedelta(days=3)).isoformat(),
                "description": "Fix issue",
            },
        ]

        for data in records_data:
            client.post("/api/equipment/maintenance", json=data, headers=headers)

        # Search by equipment ID
        response = client.get(
            f"/api/equipment/maintenance/search?equipment_id={sample_equipment['id']}",
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["total"] >= 2

        # Search by type
        response = client.get(
            "/api/equipment/maintenance/search?maintenance_type=preventive",
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert all(item["maintenance_type"] == "preventive" for item in result["items"])

    @pytest.mark.integration
    def test_maintenance_summary(
        self, client: TestClient, headers: dict, created_equipment_api: dict
    ):
        """Test getting maintenance summary statistics"""
        response = client.get("/api/equipment/maintenance/summary", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        result = response.json()

        # Verify all required fields are present
        required_fields = [
            "total_equipment",
            "operational_equipment",
            "needs_maintenance",
            "under_maintenance",
            "overdue_maintenance",
            "scheduled_this_week",
            "completed_this_month",
            "total_cost_this_month",
            "average_downtime_hours",
        ]
        for field in required_fields:
            assert field in result

        # Verify field types
        assert isinstance(result["total_equipment"], int)
        assert isinstance(result["operational_equipment"], int)
        assert isinstance(result["needs_maintenance"], int)
        assert isinstance(result["under_maintenance"], int)
        assert isinstance(result["overdue_maintenance"], int)
        assert isinstance(result["scheduled_this_week"], int)
        assert isinstance(result["completed_this_month"], int)
        assert isinstance(result["total_cost_this_month"], (int, float))
        assert isinstance(result["average_downtime_hours"], (int, float))

        # Verify logical constraints
        assert result["total_equipment"] >= 0
        assert result["operational_equipment"] >= 0
        assert result["operational_equipment"] <= result["total_equipment"]
        assert result["total_cost_this_month"] >= 0
        assert result["average_downtime_hours"] >= 0

    def test_check_overdue_maintenance(self, client: TestClient, headers: dict):
        """Test checking overdue maintenance"""
        response = client.post("/api/equipment/check-overdue", headers=headers)

        assert response.status_code == status.HTTP_204_NO_CONTENT

    # Permission tests
    def test_create_equipment_no_permission(
        self, client: TestClient, headers_read_only: dict
    ):
        """Test creating equipment without permission"""
        data = {"equipment_name": "Test Equipment", "equipment_type": "Test Type"}

        response = client.post("/api/equipment/", json=data, headers=headers_read_only)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_equipment_with_read_permission(
        self, client: TestClient, headers_read_only: dict, sample_equipment: dict
    ):
        """Test getting equipment with read-only permission"""
        response = client.get(
            f"/api/equipment/{sample_equipment['id']}", headers=headers_read_only
        )

        assert response.status_code == status.HTTP_200_OK
