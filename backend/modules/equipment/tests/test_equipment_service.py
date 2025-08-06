# backend/modules/equipment/tests/test_equipment_service.py

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException

from modules.equipment.service import EquipmentService
from modules.equipment.models import Equipment, MaintenanceRecord, EquipmentStatus, MaintenanceStatus, MaintenanceType
from modules.equipment.schemas import (
    EquipmentCreate, EquipmentUpdate, EquipmentSearchParams,
    MaintenanceRecordCreate, MaintenanceRecordUpdate, MaintenanceRecordComplete,
    MaintenanceSearchParams
)


class TestEquipmentService:
    """Test equipment service operations"""
    
    @pytest.fixture
    def service(self, db_session: Session):
        """Create equipment service instance"""
        return EquipmentService(db_session)
    
    @pytest.fixture
    def sample_equipment_data(self):
        """Sample equipment data for testing"""
        return EquipmentCreate(
            equipment_name="Commercial Oven",
            equipment_type="Cooking Equipment",
            manufacturer="Kitchen Pro",
            model_number="CP-2000",
            serial_number="SN123456",
            location="Main Kitchen",
            maintenance_interval_days=90,
            is_critical=True
        )
    
    @pytest.fixture
    def created_equipment(self, service: EquipmentService, sample_equipment_data: EquipmentCreate):
        """Create equipment for testing"""
        return service.create_equipment(sample_equipment_data, user_id=1)
    
    # Equipment CRUD tests
    def test_create_equipment(self, service: EquipmentService, sample_equipment_data: EquipmentCreate):
        """Test creating new equipment"""
        equipment = service.create_equipment(sample_equipment_data, user_id=1)
        
        assert equipment.id is not None
        assert equipment.equipment_name == "Commercial Oven"
        assert equipment.equipment_type == "Cooking Equipment"
        assert equipment.serial_number == "SN123456"
        assert equipment.status == EquipmentStatus.OPERATIONAL
        assert equipment.is_critical is True
        assert equipment.maintenance_interval_days == 90
        assert equipment.next_due_date is not None
        assert equipment.created_by == 1
    
    def test_create_equipment_duplicate_serial(self, service: EquipmentService, created_equipment: Equipment):
        """Test creating equipment with duplicate serial number"""
        duplicate_data = EquipmentCreate(
            equipment_name="Another Oven",
            equipment_type="Cooking Equipment",
            serial_number="SN123456"  # Same serial number
        )
        
        with pytest.raises(HTTPException) as exc_info:
            service.create_equipment(duplicate_data, user_id=1)
        
        assert exc_info.value.status_code == 400
        assert "already exists" in str(exc_info.value.detail)
    
    def test_get_equipment(self, service: EquipmentService, created_equipment: Equipment):
        """Test retrieving equipment by ID"""
        equipment = service.get_equipment(created_equipment.id)
        
        assert equipment.id == created_equipment.id
        assert equipment.equipment_name == created_equipment.equipment_name
    
    def test_get_nonexistent_equipment(self, service: EquipmentService):
        """Test retrieving non-existent equipment returns 404"""
        with pytest.raises(HTTPException) as exc_info:
            service.get_equipment(999999)
        
        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail)
    
    def test_update_equipment(self, service: EquipmentService, created_equipment: Equipment):
        """Test updating equipment"""
        update_data = EquipmentUpdate(
            location="Storage Room",
            maintenance_interval_days=60,
            status=EquipmentStatus.NEEDS_MAINTENANCE
        )
        
        updated = service.update_equipment(created_equipment.id, update_data, user_id=2)
        
        assert updated.location == "Storage Room"
        assert updated.maintenance_interval_days == 60
        assert updated.status == EquipmentStatus.NEEDS_MAINTENANCE
        assert updated.updated_by == 2
    
    def test_update_nonexistent_equipment(self, service: EquipmentService):
        """Test updating non-existent equipment returns 404"""
        update_data = EquipmentUpdate(location="New Location")
        
        with pytest.raises(HTTPException) as exc_info:
            service.update_equipment(999999, update_data, user_id=1)
        
        assert exc_info.value.status_code == 404
    
    def test_delete_equipment(self, service: EquipmentService, created_equipment: Equipment, db_session: Session):
        """Test soft deleting equipment"""
        service.delete_equipment(created_equipment.id)
        
        # Refresh from database
        db_session.refresh(created_equipment)
        
        assert created_equipment.is_active is False
        assert created_equipment.status == EquipmentStatus.RETIRED
    
    def test_delete_nonexistent_equipment(self, service: EquipmentService):
        """Test deleting non-existent equipment returns 404"""
        with pytest.raises(HTTPException) as exc_info:
            service.delete_equipment(999999)
        
        assert exc_info.value.status_code == 404
    
    def test_search_equipment(self, service: EquipmentService, db_session: Session):
        """Test searching equipment with filters"""
        # Create test equipment
        equipment1 = Equipment(
            equipment_name="Refrigerator Unit 1",
            equipment_type="Refrigeration",
            location="Main Kitchen",
            status=EquipmentStatus.OPERATIONAL,
            is_critical=True,
            created_by=1,
            updated_by=1
        )
        equipment2 = Equipment(
            equipment_name="Freezer Unit 2",
            equipment_type="Refrigeration",
            location="Storage",
            status=EquipmentStatus.NEEDS_MAINTENANCE,
            is_critical=False,
            created_by=1,
            updated_by=1
        )
        equipment3 = Equipment(
            equipment_name="Dishwasher Pro",
            equipment_type="Cleaning",
            location="Main Kitchen",
            status=EquipmentStatus.OPERATIONAL,
            is_critical=True,
            created_by=1,
            updated_by=1
        )
        
        db_session.add_all([equipment1, equipment2, equipment3])
        db_session.commit()
        
        # Test search by query
        params = EquipmentSearchParams(query="Refrigerator")
        results, total = service.search_equipment(params)
        assert total == 1
        assert results[0].equipment_name == "Refrigerator Unit 1"
        
        # Test filter by type
        params = EquipmentSearchParams(equipment_type="Refrigeration")
        results, total = service.search_equipment(params)
        assert total == 2
        
        # Test filter by status
        params = EquipmentSearchParams(status=EquipmentStatus.NEEDS_MAINTENANCE)
        results, total = service.search_equipment(params)
        assert total == 1
        assert results[0].equipment_name == "Freezer Unit 2"
        
        # Test filter by critical
        params = EquipmentSearchParams(is_critical=True)
        results, total = service.search_equipment(params)
        assert total == 2
        
        # Test pagination
        params = EquipmentSearchParams(limit=2, offset=0)
        results, total = service.search_equipment(params)
        assert len(results) == 2
        assert total == 3
    
    # Maintenance record tests
    def test_create_maintenance_record(self, service: EquipmentService, created_equipment: Equipment):
        """Test creating maintenance record"""
        record_data = MaintenanceRecordCreate(
            equipment_id=created_equipment.id,
            maintenance_type=MaintenanceType.PREVENTIVE,
            scheduled_date=datetime.now() + timedelta(days=7),
            description="Quarterly maintenance check",
            performed_by="John Technician"
        )
        
        record = service.create_maintenance_record(record_data, user_id=1)
        
        assert record.id is not None
        assert record.equipment_id == created_equipment.id
        assert record.maintenance_type == MaintenanceType.PREVENTIVE
        assert record.status == MaintenanceStatus.SCHEDULED
        assert record.created_by == 1
    
    def test_create_maintenance_invalid_equipment(self, service: EquipmentService):
        """Test creating maintenance for non-existent equipment"""
        record_data = MaintenanceRecordCreate(
            equipment_id=999999,
            maintenance_type=MaintenanceType.PREVENTIVE,
            scheduled_date=datetime.now() + timedelta(days=7),
            description="Test maintenance"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            service.create_maintenance_record(record_data, user_id=1)
        
        assert exc_info.value.status_code == 404
    
    def test_update_maintenance_record(self, service: EquipmentService, created_equipment: Equipment):
        """Test updating maintenance record"""
        # Create a record
        record_data = MaintenanceRecordCreate(
            equipment_id=created_equipment.id,
            maintenance_type=MaintenanceType.PREVENTIVE,
            scheduled_date=datetime.now() + timedelta(days=7),
            description="Test maintenance"
        )
        record = service.create_maintenance_record(record_data, user_id=1)
        
        # Update it
        update_data = MaintenanceRecordUpdate(
            status=MaintenanceStatus.IN_PROGRESS,
            performed_by="Jane Technician",
            cost=150.00
        )
        
        updated = service.update_maintenance_record(record.id, update_data)
        
        assert updated.status == MaintenanceStatus.IN_PROGRESS
        assert updated.performed_by == "Jane Technician"
        assert updated.cost == 150.00
    
    def test_complete_maintenance(self, service: EquipmentService, created_equipment: Equipment, db_session: Session):
        """Test completing maintenance record"""
        # Create a scheduled record
        record_data = MaintenanceRecordCreate(
            equipment_id=created_equipment.id,
            maintenance_type=MaintenanceType.PREVENTIVE,
            scheduled_date=datetime.now(),
            description="Test maintenance"
        )
        record = service.create_maintenance_record(record_data, user_id=1)
        
        # Complete it
        completion_data = MaintenanceRecordComplete(
            date_performed=datetime.now(),
            performed_by="John Technician",
            cost=200.00,
            parts_replaced="Filter, Oil",
            downtime_hours=2.5
        )
        
        completed = service.complete_maintenance(record.id, completion_data, user_id=2)
        
        assert completed.status == MaintenanceStatus.COMPLETED
        assert completed.date_performed is not None
        assert completed.cost == 200.00
        assert completed.completed_by == 2
        
        # Check equipment was updated
        db_session.refresh(created_equipment)
        assert created_equipment.status == EquipmentStatus.OPERATIONAL
        assert created_equipment.last_maintenance_date is not None
    
    def test_complete_already_completed_maintenance(self, service: EquipmentService, created_equipment: Equipment):
        """Test completing already completed maintenance fails"""
        # Create and complete a record
        record_data = MaintenanceRecordCreate(
            equipment_id=created_equipment.id,
            maintenance_type=MaintenanceType.PREVENTIVE,
            scheduled_date=datetime.now(),
            description="Test maintenance"
        )
        record = service.create_maintenance_record(record_data, user_id=1)
        
        completion_data = MaintenanceRecordComplete(
            date_performed=datetime.now(),
            performed_by="John Technician"
        )
        service.complete_maintenance(record.id, completion_data, user_id=1)
        
        # Try to complete again
        with pytest.raises(HTTPException) as exc_info:
            service.complete_maintenance(record.id, completion_data, user_id=1)
        
        assert exc_info.value.status_code == 400
        assert "already completed" in str(exc_info.value.detail)
    
    def test_delete_maintenance_record(self, service: EquipmentService, created_equipment: Equipment, db_session: Session):
        """Test deleting maintenance record"""
        # Create a scheduled record
        record_data = MaintenanceRecordCreate(
            equipment_id=created_equipment.id,
            maintenance_type=MaintenanceType.PREVENTIVE,
            scheduled_date=datetime.now() + timedelta(days=7),
            description="Test maintenance"
        )
        record = service.create_maintenance_record(record_data, user_id=1)
        record_id = record.id
        
        # Delete it
        service.delete_maintenance_record(record_id)
        
        # Verify it's gone
        with pytest.raises(HTTPException):
            service.get_maintenance_record(record_id)
    
    def test_delete_completed_maintenance_fails(self, service: EquipmentService, created_equipment: Equipment):
        """Test deleting completed maintenance record fails"""
        # Create and complete a record
        record_data = MaintenanceRecordCreate(
            equipment_id=created_equipment.id,
            maintenance_type=MaintenanceType.PREVENTIVE,
            scheduled_date=datetime.now(),
            description="Test maintenance"
        )
        record = service.create_maintenance_record(record_data, user_id=1)
        
        completion_data = MaintenanceRecordComplete(
            date_performed=datetime.now(),
            performed_by="John Technician"
        )
        service.complete_maintenance(record.id, completion_data, user_id=1)
        
        # Try to delete
        with pytest.raises(HTTPException) as exc_info:
            service.delete_maintenance_record(record.id)
        
        assert exc_info.value.status_code == 400
        assert "Cannot delete completed" in str(exc_info.value.detail)
    
    def test_check_overdue_maintenance(self, service: EquipmentService, db_session: Session):
        """Test checking and updating overdue maintenance"""
        # Create equipment with overdue maintenance
        equipment = Equipment(
            equipment_name="Test Equipment",
            equipment_type="Test Type",
            status=EquipmentStatus.OPERATIONAL,
            next_due_date=datetime.now() - timedelta(days=7),  # Overdue
            created_by=1,
            updated_by=1
        )
        db_session.add(equipment)
        db_session.commit()
        
        # Create overdue maintenance record
        record = MaintenanceRecord(
            equipment_id=equipment.id,
            maintenance_type=MaintenanceType.PREVENTIVE,
            status=MaintenanceStatus.SCHEDULED,
            scheduled_date=datetime.now() - timedelta(days=3),  # Overdue
            description="Overdue maintenance",
            created_by=1
        )
        db_session.add(record)
        db_session.commit()
        
        # Run overdue check
        service.check_and_update_overdue_maintenance()
        
        # Verify updates
        db_session.refresh(equipment)
        db_session.refresh(record)
        
        assert equipment.status == EquipmentStatus.NEEDS_MAINTENANCE
        assert record.status == MaintenanceStatus.OVERDUE
    
    def test_maintenance_summary(self, service: EquipmentService, db_session: Session):
        """Test getting maintenance summary statistics"""
        # Create test data
        equipment1 = Equipment(
            equipment_name="Equipment 1",
            equipment_type="Type A",
            status=EquipmentStatus.OPERATIONAL,
            created_by=1,
            updated_by=1
        )
        equipment2 = Equipment(
            equipment_name="Equipment 2",
            equipment_type="Type B",
            status=EquipmentStatus.NEEDS_MAINTENANCE,
            created_by=1,
            updated_by=1
        )
        db_session.add_all([equipment1, equipment2])
        db_session.commit()
        
        # Create maintenance record
        record = MaintenanceRecord(
            equipment_id=equipment1.id,
            maintenance_type=MaintenanceType.PREVENTIVE,
            status=MaintenanceStatus.COMPLETED,
            scheduled_date=datetime.now() - timedelta(days=7),
            date_performed=datetime.now() - timedelta(days=5),
            description="Completed maintenance",
            cost=250.00,
            downtime_hours=3.0,
            created_by=1
        )
        db_session.add(record)
        db_session.commit()
        
        # Get summary
        summary = service.get_maintenance_summary()
        
        assert summary.total_equipment == 2
        assert summary.operational_equipment == 1
        assert summary.needs_maintenance == 1
        assert summary.completed_this_month >= 1
        assert summary.total_cost_this_month >= 250.00