# backend/modules/equipment/tests/test_equipment_routes.py

import pytest
from datetime import datetime, timedelta
from fastapi import status
from fastapi.testclient import TestClient

from modules.equipment.models import Equipment, MaintenanceRecord, EquipmentStatus, MaintenanceStatus


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
    def test_create_equipment(self, client: TestClient, headers: dict, equipment_data: dict, assert_equipment_shape):
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
        assert result["next_due_date"] is not None  # Should be calculated from maintenance_interval_days
    
    @pytest.mark.negative
    def test_create_equipment_missing_required_fields(self, client: TestClient, headers: dict):
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
    def test_get_equipment(self, client: TestClient, headers: dict, created_equipment_api: dict, assert_equipment_shape):
        """Test getting equipment by ID with maintenance history"""
        response = client.get(f"/api/equipment/{created_equipment_api['id']}", headers=headers)
        
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
    
    def test_update_equipment(self, client: TestClient, headers: dict, created_equipment_api: dict, assert_equipment_shape):
        """Test updating equipment"""
        update_data = {
            "location": "Updated Location",
            "status": "needs_maintenance",
            "notes": "Equipment needs service",
            "maintenance_interval_days": 60
        }
        
        response = client.put(
            f"/api/equipment/{created_equipment_api['id']}",
            json=update_data,
            headers=headers
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
        response = client.put("/api/equipment/999999", json=update_data, headers=headers)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        error = response.json()
        assert "not found" in error["detail"].lower()
    
    def test_delete_equipment(self, client: TestClient, headers: dict, created_equipment_api: dict):
        """Test soft deleting equipment"""
        equipment_id = created_equipment_api['id']
        
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
    def test_search_equipment(self, client: TestClient, headers: dict, multiple_equipment: list, 
                            assert_equipment_shape, assert_paginated_response):
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
        response = client.get("/api/equipment/search?equipment_type=Refrigeration", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        
        assert_paginated_response(result)
        assert result["total"] >= 1
        assert all(item["equipment_type"] == "Refrigeration" for item in result["items"])
        
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
            headers=headers
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
        response = client.get("/api/equipment/search?sort_by=equipment_name&sort_order=desc", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        
        if len(result["items"]) > 1:
            names = [item["equipment_name"] for item in result["items"]]
            assert names == sorted(names, reverse=True)
    
    # Maintenance endpoint tests
    @pytest.mark.smoke
    def test_create_maintenance_record(self, client: TestClient, headers: dict, created_equipment_api: dict, 
                                     maintenance_data: dict, assert_maintenance_shape):
        """Test creating maintenance record"""
        maintenance_data["equipment_id"] = created_equipment_api["id"]
        
        response = client.post("/api/equipment/maintenance", json=maintenance_data, headers=headers)
        
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
    def test_create_maintenance_invalid_equipment(self, client: TestClient, headers: dict, maintenance_data: dict):
        """Test creating maintenance for non-existent equipment returns 404"""
        maintenance_data["equipment_id"] = 999999
        
        response = client.post("/api/equipment/maintenance", json=maintenance_data, headers=headers)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        error = response.json()
        assert "not found" in error["detail"].lower()
        assert "999999" in error["detail"]
    
    def test_update_maintenance_record(self, client: TestClient, headers: dict, sample_equipment: dict):
        """Test updating maintenance record"""
        # Create a record
        create_data = {
            "equipment_id": sample_equipment["id"],
            "maintenance_type": "preventive",
            "scheduled_date": datetime.now().isoformat(),
            "description": "Test maintenance"
        }
        create_response = client.post("/api/equipment/maintenance", json=create_data, headers=headers)
        record = create_response.json()
        
        # Update it
        update_data = {
            "status": "in_progress",
            "performed_by": "John Doe",
            "cost": 150.50
        }
        
        response = client.put(
            f"/api/equipment/maintenance/{record['id']}",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["status"] == "in_progress"
        assert result["performed_by"] == "John Doe"
        assert result["cost"] == 150.50
    
    def test_complete_maintenance(self, client: TestClient, headers: dict, sample_equipment: dict):
        """Test completing maintenance record"""
        # Create a record
        create_data = {
            "equipment_id": sample_equipment["id"],
            "maintenance_type": "corrective",
            "scheduled_date": datetime.now().isoformat(),
            "description": "Fix issue"
        }
        create_response = client.post("/api/equipment/maintenance", json=create_data, headers=headers)
        record = create_response.json()
        
        # Complete it
        completion_data = {
            "date_performed": datetime.now().isoformat(),
            "performed_by": "Jane Technician",
            "cost": 250.00,
            "parts_replaced": "New filter",
            "issues_found": "Filter was clogged",
            "resolution": "Replaced filter",
            "downtime_hours": 1.5
        }
        
        response = client.post(
            f"/api/equipment/maintenance/{record['id']}/complete",
            json=completion_data,
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["status"] == "completed"
        assert result["date_performed"] is not None
        assert result["cost"] == 250.00
        assert result["downtime_hours"] == 1.5
    
    def test_delete_maintenance_record(self, client: TestClient, headers: dict, sample_equipment: dict):
        """Test deleting maintenance record"""
        # Create a record
        create_data = {
            "equipment_id": sample_equipment["id"],
            "maintenance_type": "inspection",
            "scheduled_date": (datetime.now() + timedelta(days=14)).isoformat(),
            "description": "Future inspection"
        }
        create_response = client.post("/api/equipment/maintenance", json=create_data, headers=headers)
        record = create_response.json()
        
        # Delete it
        response = client.delete(f"/api/equipment/maintenance/{record['id']}", headers=headers)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_search_maintenance_records(self, client: TestClient, headers: dict, sample_equipment: dict):
        """Test searching maintenance records"""
        # Create multiple records
        records_data = [
            {
                "equipment_id": sample_equipment["id"],
                "maintenance_type": "preventive",
                "scheduled_date": datetime.now().isoformat(),
                "description": "Preventive check"
            },
            {
                "equipment_id": sample_equipment["id"],
                "maintenance_type": "corrective",
                "scheduled_date": (datetime.now() + timedelta(days=3)).isoformat(),
                "description": "Fix issue"
            }
        ]
        
        for data in records_data:
            client.post("/api/equipment/maintenance", json=data, headers=headers)
        
        # Search by equipment ID
        response = client.get(
            f"/api/equipment/maintenance/search?equipment_id={sample_equipment['id']}",
            headers=headers
        )
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["total"] >= 2
        
        # Search by type
        response = client.get(
            "/api/equipment/maintenance/search?maintenance_type=preventive",
            headers=headers
        )
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert all(item["maintenance_type"] == "preventive" for item in result["items"])
    
    @pytest.mark.integration
    def test_maintenance_summary(self, client: TestClient, headers: dict, created_equipment_api: dict):
        """Test getting maintenance summary statistics"""
        response = client.get("/api/equipment/maintenance/summary", headers=headers)
        
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        
        # Verify all required fields are present
        required_fields = [
            "total_equipment", "operational_equipment", "needs_maintenance",
            "under_maintenance", "overdue_maintenance", "scheduled_this_week",
            "completed_this_month", "total_cost_this_month", "average_downtime_hours"
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
    def test_create_equipment_no_permission(self, client: TestClient, headers_read_only: dict):
        """Test creating equipment without permission"""
        data = {
            "equipment_name": "Test Equipment",
            "equipment_type": "Test Type"
        }
        
        response = client.post("/api/equipment/", json=data, headers=headers_read_only)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_get_equipment_with_read_permission(self, client: TestClient, headers_read_only: dict, sample_equipment: dict):
        """Test getting equipment with read-only permission"""
        response = client.get(f"/api/equipment/{sample_equipment['id']}", headers=headers_read_only)
        
        assert response.status_code == status.HTTP_200_OK