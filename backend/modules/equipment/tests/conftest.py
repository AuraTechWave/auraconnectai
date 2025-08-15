# backend/modules/equipment/tests/conftest.py

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.equipment.models import Equipment, MaintenanceRecord
from modules.equipment.schemas import EquipmentCreate, MaintenanceRecordCreate


@pytest.fixture
def equipment_data() -> Dict[str, Any]:
    """Base equipment data for testing"""
    return {
        "equipment_name": "Test Equipment",
        "equipment_type": "Test Type",
        "manufacturer": "Test Manufacturer",
        "model_number": "TEST-001",
        "serial_number": f"SN-{datetime.now().timestamp()}",  # Unique serial
        "location": "Test Location",
        "maintenance_interval_days": 90,
        "is_critical": True,
        "notes": "Test equipment for unit tests",
    }


@pytest.fixture
def equipment_create_data(equipment_data) -> EquipmentCreate:
    """Equipment creation schema"""
    return EquipmentCreate(**equipment_data)


@pytest.fixture
def maintenance_data() -> Dict[str, Any]:
    """Base maintenance record data for testing"""
    return {
        "maintenance_type": "preventive",
        "scheduled_date": (datetime.now() + timedelta(days=7)).isoformat(),
        "description": "Routine maintenance check",
        "performed_by": "Test Technician",
        "cost": 150.00,
    }


@pytest.fixture
def created_equipment_api(
    client: TestClient, headers: dict, equipment_data: dict
) -> dict:
    """Create equipment via API and return response data"""
    response = client.post("/api/equipment/", json=equipment_data, headers=headers)
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def created_maintenance_api(
    client: TestClient,
    headers: dict,
    created_equipment_api: dict,
    maintenance_data: dict,
) -> dict:
    """Create maintenance record via API and return response data"""
    maintenance_data["equipment_id"] = created_equipment_api["id"]
    response = client.post(
        "/api/equipment/maintenance", json=maintenance_data, headers=headers
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def multiple_equipment(client: TestClient, headers: dict) -> list:
    """Create multiple equipment for search/filter testing"""
    equipment_list = [
        {
            "equipment_name": "Industrial Oven A",
            "equipment_type": "Cooking Equipment",
            "manufacturer": "CookTech",
            "location": "Main Kitchen",
            "status": "operational",
            "is_critical": True,
        },
        {
            "equipment_name": "Commercial Freezer B",
            "equipment_type": "Refrigeration",
            "manufacturer": "CoolPro",
            "location": "Storage Room",
            "status": "needs_maintenance",
            "is_critical": True,
        },
        {
            "equipment_name": "Dishwasher Unit C",
            "equipment_type": "Cleaning Equipment",
            "manufacturer": "CleanTech",
            "location": "Main Kitchen",
            "status": "operational",
            "is_critical": False,
        },
    ]

    created = []
    for data in equipment_list:
        response = client.post("/api/equipment/", json=data, headers=headers)
        assert response.status_code == 201
        created.append(response.json())

    return created


@pytest.fixture
def assert_equipment_shape():
    """Factory fixture for asserting equipment response shape"""

    def _assert(equipment: dict):
        """Assert equipment has correct shape and required fields"""
        # Required fields
        assert "id" in equipment
        assert isinstance(equipment["id"], int)

        assert "equipment_name" in equipment
        assert isinstance(equipment["equipment_name"], str)

        assert "equipment_type" in equipment
        assert isinstance(equipment["equipment_type"], str)

        assert "status" in equipment
        assert equipment["status"] in [
            "operational",
            "needs_maintenance",
            "under_maintenance",
            "out_of_service",
            "retired",
        ]

        assert "is_active" in equipment
        assert isinstance(equipment["is_active"], bool)

        assert "is_critical" in equipment
        assert isinstance(equipment["is_critical"], bool)

        # Optional fields that should be present
        optional_fields = [
            "manufacturer",
            "model_number",
            "serial_number",
            "location",
            "notes",
            "maintenance_interval_days",
            "last_maintenance_date",
            "next_due_date",
            "created_at",
            "updated_at",
        ]
        for field in optional_fields:
            assert field in equipment

        # Date fields should be ISO format strings or None
        date_fields = [
            "purchase_date",
            "warranty_expiry",
            "last_maintenance_date",
            "next_due_date",
            "created_at",
            "updated_at",
        ]
        for field in date_fields:
            if equipment.get(field) is not None:
                # Should be parseable as datetime
                datetime.fromisoformat(equipment[field].replace("Z", "+00:00"))

    return _assert


@pytest.fixture
def assert_maintenance_shape():
    """Factory fixture for asserting maintenance record response shape"""

    def _assert(record: dict):
        """Assert maintenance record has correct shape and required fields"""
        # Required fields
        assert "id" in record
        assert isinstance(record["id"], int)

        assert "equipment_id" in record
        assert isinstance(record["equipment_id"], int)

        assert "maintenance_type" in record
        assert record["maintenance_type"] in [
            "preventive",
            "corrective",
            "emergency",
            "inspection",
            "calibration",
        ]

        assert "status" in record
        assert record["status"] in [
            "scheduled",
            "in_progress",
            "completed",
            "overdue",
            "cancelled",
        ]

        assert "scheduled_date" in record
        assert "description" in record
        assert isinstance(record["description"], str)

        # Numeric fields
        assert "cost" in record
        assert isinstance(record["cost"], (int, float))

        assert "downtime_hours" in record
        assert isinstance(record["downtime_hours"], (int, float))

        # Optional fields
        optional_fields = [
            "date_performed",
            "next_due_date",
            "performed_by",
            "parts_replaced",
            "issues_found",
            "resolution",
            "created_at",
            "updated_at",
        ]
        for field in optional_fields:
            assert field in record

        # Date validation
        date_fields = [
            "scheduled_date",
            "date_performed",
            "next_due_date",
            "created_at",
            "updated_at",
        ]
        for field in date_fields:
            if record.get(field) is not None:
                datetime.fromisoformat(record[field].replace("Z", "+00:00"))

    return _assert


@pytest.fixture
def assert_paginated_response():
    """Factory fixture for asserting paginated response shape"""

    def _assert(response: dict):
        """Assert paginated response has correct shape"""
        assert "items" in response
        assert isinstance(response["items"], list)

        assert "total" in response
        assert isinstance(response["total"], int)
        assert response["total"] >= 0

        assert "page" in response
        assert isinstance(response["page"], int)
        assert response["page"] >= 1

        assert "size" in response
        assert isinstance(response["size"], int)
        assert response["size"] >= 1

        assert "pages" in response
        assert isinstance(response["pages"], int)
        assert response["pages"] >= 0

        # Validate pagination math
        if response["total"] > 0:
            expected_pages = (response["total"] + response["size"] - 1) // response[
                "size"
            ]
            assert response["pages"] == expected_pages

    return _assert
