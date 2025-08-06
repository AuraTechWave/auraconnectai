# backend/modules/equipment/tests/test_equipment_schemas.py

import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError

from modules.equipment.schemas import (
    EquipmentCreate, EquipmentUpdate, EquipmentSearchParams,
    MaintenanceRecordCreate, MaintenanceRecordUpdate, MaintenanceRecordComplete,
    MaintenanceSearchParams
)
from modules.equipment.models import MaintenanceStatus, MaintenanceType, EquipmentStatus


class TestEquipmentSchemas:
    """Test equipment schemas validation"""
    
    def test_equipment_create_valid(self):
        """Test creating valid equipment schema"""
        data = {
            "equipment_name": "Test Equipment",
            "equipment_type": "Test Type",
            "manufacturer": "Test Manufacturer",
            "location": "Test Location",
            "maintenance_interval_days": 90,
            "is_critical": True
        }
        
        schema = EquipmentCreate(**data)
        assert schema.equipment_name == "Test Equipment"
        assert schema.maintenance_interval_days == 90
        assert schema.is_critical is True
    
    def test_equipment_create_missing_required(self):
        """Test equipment create with missing required fields"""
        data = {
            "equipment_type": "Test Type"  # Missing equipment_name
        }
        
        with pytest.raises(ValidationError) as exc_info:
            EquipmentCreate(**data)
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("equipment_name",) for error in errors)
    
    def test_equipment_create_empty_name(self):
        """Test equipment create with empty name"""
        data = {
            "equipment_name": "",  # Empty string
            "equipment_type": "Test Type"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            EquipmentCreate(**data)
        
        errors = exc_info.value.errors()
        assert any("at least 1 character" in str(error) for error in errors)
    
    def test_equipment_update_partial(self):
        """Test equipment update with partial data"""
        data = {
            "location": "New Location",
            "status": EquipmentStatus.NEEDS_MAINTENANCE
        }
        
        schema = EquipmentUpdate(**data)
        assert schema.location == "New Location"
        assert schema.status == EquipmentStatus.NEEDS_MAINTENANCE
        assert schema.equipment_name is None  # Other fields are optional
    
    def test_equipment_search_params(self):
        """Test equipment search parameters"""
        params = EquipmentSearchParams(
            query="refrigerator",
            equipment_type="Refrigeration",
            status=EquipmentStatus.OPERATIONAL,
            is_critical=True,
            sort_by="next_due_date",
            sort_order="desc",
            limit=100,
            offset=50
        )
        
        assert params.query == "refrigerator"
        assert params.limit == 100
        assert params.offset == 50
    
    def test_equipment_search_params_invalid_sort(self):
        """Test equipment search with invalid sort field"""
        with pytest.raises(ValidationError):
            EquipmentSearchParams(sort_by="invalid_field")
    
    def test_maintenance_record_create_valid(self):
        """Test creating valid maintenance record schema"""
        data = {
            "equipment_id": 1,
            "maintenance_type": MaintenanceType.PREVENTIVE,
            "scheduled_date": datetime.now() + timedelta(days=7),
            "description": "Quarterly maintenance",
            "performed_by": "John Doe",
            "cost": 150.50
        }
        
        schema = MaintenanceRecordCreate(**data)
        assert schema.equipment_id == 1
        assert schema.maintenance_type == MaintenanceType.PREVENTIVE
        assert schema.cost == 150.50
    
    def test_maintenance_record_create_past_date_validation(self):
        """Test maintenance record with very old date"""
        data = {
            "equipment_id": 1,
            "maintenance_type": MaintenanceType.PREVENTIVE,
            "scheduled_date": datetime(1999, 12, 31),  # Before year 2000
            "description": "Test maintenance"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            MaintenanceRecordCreate(**data)
        
        errors = exc_info.value.errors()
        assert any("before year 2000" in str(error) for error in errors)
    
    def test_maintenance_record_update_future_date_validation(self):
        """Test maintenance update with future performed date"""
        data = {
            "date_performed": datetime.now() + timedelta(days=1),  # Future date
            "status": MaintenanceStatus.COMPLETED
        }
        
        with pytest.raises(ValidationError) as exc_info:
            MaintenanceRecordUpdate(**data)
        
        errors = exc_info.value.errors()
        assert any("cannot be in the future" in str(error) for error in errors)
    
    def test_maintenance_record_complete_valid(self):
        """Test completing maintenance record"""
        data = {
            "date_performed": datetime.now() - timedelta(hours=2),
            "performed_by": "Jane Technician",
            "cost": 250.00,
            "parts_replaced": "Filter, Oil",
            "issues_found": "Filter was clogged",
            "resolution": "Replaced filter and oil",
            "downtime_hours": 2.5
        }
        
        schema = MaintenanceRecordComplete(**data)
        assert schema.performed_by == "Jane Technician"
        assert schema.downtime_hours == 2.5
    
    def test_maintenance_record_complete_future_date_fails(self):
        """Test completing maintenance with future date fails"""
        data = {
            "date_performed": datetime.now() + timedelta(days=1),
            "performed_by": "Test Tech"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            MaintenanceRecordComplete(**data)
        
        errors = exc_info.value.errors()
        assert any("cannot be in the future" in str(error) for error in errors)
    
    def test_maintenance_search_params(self):
        """Test maintenance search parameters"""
        params = MaintenanceSearchParams(
            equipment_id=1,
            maintenance_type=MaintenanceType.CORRECTIVE,
            status=MaintenanceStatus.IN_PROGRESS,
            date_from=datetime.now() - timedelta(days=30),
            date_to=datetime.now(),
            performed_by="John",
            sort_by="cost",
            sort_order="desc",
            limit=25
        )
        
        assert params.equipment_id == 1
        assert params.maintenance_type == MaintenanceType.CORRECTIVE
        assert params.limit == 25
    
    def test_negative_values_validation(self):
        """Test that negative values are rejected"""
        # Test negative maintenance interval
        with pytest.raises(ValidationError):
            EquipmentCreate(
                equipment_name="Test",
                equipment_type="Test",
                maintenance_interval_days=-1  # Negative value
            )
        
        # Test negative cost
        with pytest.raises(ValidationError):
            MaintenanceRecordCreate(
                equipment_id=1,
                maintenance_type=MaintenanceType.PREVENTIVE,
                scheduled_date=datetime.now(),
                description="Test",
                cost=-100.00  # Negative cost
            )
        
        # Test negative downtime
        with pytest.raises(ValidationError):
            MaintenanceRecordComplete(
                date_performed=datetime.now(),
                performed_by="Test",
                downtime_hours=-1.5  # Negative downtime
            )
    
    def test_pagination_limits(self):
        """Test pagination parameter limits"""
        # Test max limit
        params = EquipmentSearchParams(limit=500)
        assert params.limit == 500
        
        # Test exceeding max limit
        with pytest.raises(ValidationError):
            EquipmentSearchParams(limit=501)
        
        # Test zero limit
        with pytest.raises(ValidationError):
            EquipmentSearchParams(limit=0)
        
        # Test negative offset
        with pytest.raises(ValidationError):
            EquipmentSearchParams(offset=-1)