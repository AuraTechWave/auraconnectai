# backend/modules/equipment/tests/test_equipment_routes.py

import pytest
from datetime import datetime, timedelta
from fastapi import status
from fastapi.testclient import TestClient

from modules.equipment.models import Equipment, MaintenanceRecord, EquipmentStatus, MaintenanceStatus


class TestEquipmentRoutes:
    """Test equipment API routes"""
    
    @pytest.fixture
    def headers(self, auth_token):
        """Auth headers for requests"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    @pytest.fixture
    def sample_equipment(self, client: TestClient, headers: dict):
        """Create sample equipment for testing"""
        data = {
            "equipment_name": "Test Oven",
            "equipment_type": "Cooking Equipment",
            "manufacturer": "Test Manufacturer",
            "model_number": "TM-1000",
            "serial_number": "SN-TEST-001",
            "location": "Test Kitchen",
            "maintenance_interval_days": 90,
            "is_critical": True
        }
        response = client.post("/api/equipment/", json=data, headers=headers)
        assert response.status_code == status.HTTP_201_CREATED
        return response.json()
    
    # Equipment endpoint tests
    def test_create_equipment(self, client: TestClient, headers: dict):
        """Test creating equipment"""
        data = {
            "equipment_name": "Commercial Dishwasher",
            "equipment_type": "Cleaning Equipment",
            "manufacturer": "CleanTech",
            "model_number": "CT-5000",
            "serial_number": "SN-DISH-001",
            "location": "Main Kitchen",
            "maintenance_interval_days": 60,
            "is_critical": True
        }
        
        response = client.post("/api/equipment/", json=data, headers=headers)
        
        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()
        assert result["equipment_name"] == "Commercial Dishwasher"
        assert result["status"] == "operational"
        assert result["next_due_date"] is not None
    
    def test_create_equipment_missing_name(self, client: TestClient, headers: dict):
        """Test creating equipment without required field"""
        data = {
            "equipment_type": "Cooking Equipment"
        }
        
        response = client.post("/api/equipment/", json=data, headers=headers)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_get_equipment(self, client: TestClient, headers: dict, sample_equipment: dict):
        """Test getting equipment by ID"""
        response = client.get(f"/api/equipment/{sample_equipment['id']}", headers=headers)
        
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["id"] == sample_equipment["id"]
        assert result["equipment_name"] == sample_equipment["equipment_name"]
        assert "maintenance_records" in result
    
    def test_get_nonexistent_equipment(self, client: TestClient, headers: dict):
        """Test getting non-existent equipment returns 404"""
        response = client.get("/api/equipment/999999", headers=headers)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()
    
    def test_update_equipment(self, client: TestClient, headers: dict, sample_equipment: dict):
        """Test updating equipment"""
        update_data = {
            "location": "Updated Location",
            "status": "needs_maintenance",
            "notes": "Equipment needs service"
        }
        
        response = client.put(
            f"/api/equipment/{sample_equipment['id']}",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["location"] == "Updated Location"
        assert result["status"] == "needs_maintenance"
        assert result["notes"] == "Equipment needs service"
    
    def test_delete_equipment(self, client: TestClient, headers: dict, sample_equipment: dict):
        """Test deleting equipment"""
        response = client.delete(f"/api/equipment/{sample_equipment['id']}", headers=headers)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify it's soft deleted
        get_response = client.get(f"/api/equipment/{sample_equipment['id']}", headers=headers)
        assert get_response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_search_equipment(self, client: TestClient, headers: dict, db_session):
        """Test searching equipment with filters"""
        # Create test equipment
        equipment_data = [
            {
                "equipment_name": "Refrigerator A",
                "equipment_type": "Refrigeration",
                "location": "Kitchen",
                "is_critical": True
            },
            {
                "equipment_name": "Freezer B",
                "equipment_type": "Refrigeration",
                "location": "Storage",
                "is_critical": False
            },
            {
                "equipment_name": "Oven C",
                "equipment_type": "Cooking",
                "location": "Kitchen",
                "is_critical": True
            }
        ]
        
        for data in equipment_data:
            client.post("/api/equipment/", json=data, headers=headers)
        
        # Test search by query
        response = client.get("/api/equipment/search?query=Refrigerator", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["total"] >= 1
        assert any("Refrigerator" in item["equipment_name"] for item in result["items"])
        
        # Test filter by type
        response = client.get("/api/equipment/search?equipment_type=Refrigeration", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["total"] >= 2
        
        # Test filter by critical
        response = client.get("/api/equipment/search?is_critical=true", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert all(item["is_critical"] for item in result["items"])
        
        # Test pagination
        response = client.get("/api/equipment/search?page=1&size=2", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert len(result["items"]) <= 2
        assert "pages" in result
    
    # Maintenance endpoint tests
    def test_create_maintenance_record(self, client: TestClient, headers: dict, sample_equipment: dict):
        """Test creating maintenance record"""
        data = {
            "equipment_id": sample_equipment["id"],
            "maintenance_type": "preventive",
            "scheduled_date": (datetime.now() + timedelta(days=7)).isoformat(),
            "description": "Quarterly maintenance check",
            "performed_by": "Tech Team"
        }
        
        response = client.post("/api/equipment/maintenance", json=data, headers=headers)
        
        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()
        assert result["equipment_id"] == sample_equipment["id"]
        assert result["maintenance_type"] == "preventive"
        assert result["status"] == "scheduled"
    
    def test_create_maintenance_invalid_equipment(self, client: TestClient, headers: dict):
        """Test creating maintenance for invalid equipment"""
        data = {
            "equipment_id": 999999,
            "maintenance_type": "preventive",
            "scheduled_date": datetime.now().isoformat(),
            "description": "Test maintenance"
        }
        
        response = client.post("/api/equipment/maintenance", json=data, headers=headers)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
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
    
    def test_maintenance_summary(self, client: TestClient, headers: dict, sample_equipment: dict):
        """Test getting maintenance summary"""
        response = client.get("/api/equipment/maintenance/summary", headers=headers)
        
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert "total_equipment" in result
        assert "operational_equipment" in result
        assert "needs_maintenance" in result
        assert "completed_this_month" in result
        assert "total_cost_this_month" in result
    
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