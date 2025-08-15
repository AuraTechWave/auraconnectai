# backend/modules/equipment/services/equipment_service.py

from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from fastapi import HTTPException, status

from ..models import (
    Equipment,
    MaintenanceRecord,
    EquipmentStatus,
    MaintenanceStatus,
    MaintenanceType,
)
from ..schemas import (
    EquipmentCreate,
    EquipmentUpdate,
    EquipmentSearchParams,
    MaintenanceRecordCreate,
    MaintenanceRecordUpdate,
    MaintenanceRecordComplete,
    MaintenanceSearchParams,
    MaintenanceSummary,
)


class EquipmentService:
    """Service for managing equipment and maintenance"""

    def __init__(self, db: Session):
        self.db = db

    # Equipment CRUD operations
    def create_equipment(
        self, equipment_data: EquipmentCreate, user_id: int
    ) -> Equipment:
        """Create new equipment"""
        # Check for duplicate serial number
        if equipment_data.serial_number:
            existing = (
                self.db.query(Equipment)
                .filter(Equipment.serial_number == equipment_data.serial_number)
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Equipment with serial number {equipment_data.serial_number} already exists",
                )

        equipment = Equipment(
            **equipment_data.dict(), created_by=user_id, updated_by=user_id
        )

        # Calculate next due date if maintenance interval is set
        if equipment.maintenance_interval_days:
            equipment.next_due_date = datetime.now() + timedelta(
                days=equipment.maintenance_interval_days
            )

        self.db.add(equipment)
        self.db.commit()
        self.db.refresh(equipment)
        return equipment

    def get_equipment(self, equipment_id: int) -> Equipment:
        """Get equipment by ID"""
        equipment = (
            self.db.query(Equipment)
            .filter(Equipment.id == equipment_id, Equipment.is_active == True)
            .first()
        )

        if not equipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Equipment with ID {equipment_id} not found",
            )

        return equipment

    def update_equipment(
        self, equipment_id: int, update_data: EquipmentUpdate, user_id: int
    ) -> Equipment:
        """Update equipment"""
        equipment = self.get_equipment(equipment_id)

        # Check for duplicate serial number if updating
        if (
            update_data.serial_number
            and update_data.serial_number != equipment.serial_number
        ):
            existing = (
                self.db.query(Equipment)
                .filter(
                    Equipment.serial_number == update_data.serial_number,
                    Equipment.id != equipment_id,
                )
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Equipment with serial number {update_data.serial_number} already exists",
                )

        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(equipment, field, value)

        equipment.updated_by = user_id

        # Recalculate next due date if maintenance interval changed
        if (
            "maintenance_interval_days" in update_dict
            and equipment.maintenance_interval_days
        ):
            if equipment.last_maintenance_date:
                equipment.next_due_date = equipment.last_maintenance_date + timedelta(
                    days=equipment.maintenance_interval_days
                )
            else:
                equipment.next_due_date = datetime.now() + timedelta(
                    days=equipment.maintenance_interval_days
                )

        self.db.commit()
        self.db.refresh(equipment)
        return equipment

    def delete_equipment(self, equipment_id: int) -> None:
        """Soft delete equipment"""
        equipment = self.get_equipment(equipment_id)
        equipment.is_active = False
        equipment.status = EquipmentStatus.RETIRED
        self.db.commit()

    def search_equipment(
        self, params: EquipmentSearchParams
    ) -> Tuple[List[Equipment], int]:
        """Search equipment with filters"""
        query = self.db.query(Equipment).filter(Equipment.is_active == True)

        # Apply filters
        if params.query:
            search_term = f"%{params.query}%"
            query = query.filter(
                or_(
                    Equipment.equipment_name.ilike(search_term),
                    Equipment.equipment_type.ilike(search_term),
                    Equipment.manufacturer.ilike(search_term),
                    Equipment.model_number.ilike(search_term),
                    Equipment.serial_number.ilike(search_term),
                    Equipment.location.ilike(search_term),
                )
            )

        if params.equipment_type:
            query = query.filter(Equipment.equipment_type == params.equipment_type)

        if params.status:
            query = query.filter(Equipment.status == params.status)

        if params.location:
            query = query.filter(Equipment.location.ilike(f"%{params.location}%"))

        if params.is_critical is not None:
            query = query.filter(Equipment.is_critical == params.is_critical)

        if params.needs_maintenance:
            # Equipment that needs maintenance (overdue or due soon)
            threshold_date = datetime.now() + timedelta(days=7)
            query = query.filter(
                or_(
                    Equipment.next_due_date <= threshold_date,
                    Equipment.status == EquipmentStatus.NEEDS_MAINTENANCE,
                )
            )

        # Get total count
        total = query.count()

        # Apply sorting
        sort_column = getattr(Equipment, params.sort_by)
        if params.sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        query = query.offset(params.offset).limit(params.limit)

        return query.all(), total

    # Maintenance record operations
    def create_maintenance_record(
        self, record_data: MaintenanceRecordCreate, user_id: int
    ) -> MaintenanceRecord:
        """Create maintenance record"""
        # Verify equipment exists
        equipment = self.get_equipment(record_data.equipment_id)

        record = MaintenanceRecord(**record_data.dict(), created_by=user_id)

        self.db.add(record)

        # Update equipment status if needed
        if record.status == MaintenanceStatus.IN_PROGRESS:
            equipment.status = EquipmentStatus.UNDER_MAINTENANCE

        self.db.commit()
        self.db.refresh(record)
        return record

    def get_maintenance_record(self, record_id: int) -> MaintenanceRecord:
        """Get maintenance record by ID"""
        record = (
            self.db.query(MaintenanceRecord)
            .filter(MaintenanceRecord.id == record_id)
            .first()
        )

        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Maintenance record with ID {record_id} not found",
            )

        return record

    def update_maintenance_record(
        self, record_id: int, update_data: MaintenanceRecordUpdate
    ) -> MaintenanceRecord:
        """Update maintenance record"""
        record = self.get_maintenance_record(record_id)
        equipment = self.get_equipment(record.equipment_id)

        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(record, field, value)

        # Update equipment status based on maintenance status
        if "status" in update_dict:
            if record.status == MaintenanceStatus.IN_PROGRESS:
                equipment.status = EquipmentStatus.UNDER_MAINTENANCE
            elif record.status == MaintenanceStatus.COMPLETED:
                equipment.status = EquipmentStatus.OPERATIONAL
                # Update last maintenance date and calculate next due date
                if record.date_performed:
                    equipment.last_maintenance_date = record.date_performed
                    if equipment.maintenance_interval_days:
                        equipment.next_due_date = record.date_performed + timedelta(
                            days=equipment.maintenance_interval_days
                        )

        self.db.commit()
        self.db.refresh(record)
        return record

    def complete_maintenance(
        self, record_id: int, completion_data: MaintenanceRecordComplete, user_id: int
    ) -> MaintenanceRecord:
        """Complete a maintenance record"""
        record = self.get_maintenance_record(record_id)

        if record.status == MaintenanceStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maintenance record is already completed",
            )

        equipment = self.get_equipment(record.equipment_id)

        # Update record with completion data
        for field, value in completion_data.dict(exclude_unset=True).items():
            setattr(record, field, value)

        record.status = MaintenanceStatus.COMPLETED
        record.completed_by = user_id

        # Update equipment
        equipment.status = EquipmentStatus.OPERATIONAL
        equipment.last_maintenance_date = record.date_performed

        # Calculate next due date
        if completion_data.next_due_date:
            equipment.next_due_date = completion_data.next_due_date
            record.next_due_date = completion_data.next_due_date
        elif equipment.maintenance_interval_days:
            next_due = record.date_performed + timedelta(
                days=equipment.maintenance_interval_days
            )
            equipment.next_due_date = next_due
            record.next_due_date = next_due

        self.db.commit()
        self.db.refresh(record)
        return record

    def delete_maintenance_record(self, record_id: int) -> None:
        """Delete maintenance record"""
        record = self.get_maintenance_record(record_id)

        if record.status == MaintenanceStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete completed maintenance records",
            )

        self.db.delete(record)
        self.db.commit()

    def search_maintenance_records(
        self, params: MaintenanceSearchParams
    ) -> Tuple[List[MaintenanceRecord], int]:
        """Search maintenance records with filters"""
        query = self.db.query(MaintenanceRecord)

        # Apply filters
        if params.equipment_id:
            query = query.filter(MaintenanceRecord.equipment_id == params.equipment_id)

        if params.maintenance_type:
            query = query.filter(
                MaintenanceRecord.maintenance_type == params.maintenance_type
            )

        if params.status:
            query = query.filter(MaintenanceRecord.status == params.status)

        if params.date_from:
            query = query.filter(MaintenanceRecord.scheduled_date >= params.date_from)

        if params.date_to:
            query = query.filter(MaintenanceRecord.scheduled_date <= params.date_to)

        if params.performed_by:
            query = query.filter(
                MaintenanceRecord.performed_by.ilike(f"%{params.performed_by}%")
            )

        # Get total count
        total = query.count()

        # Apply sorting
        sort_column = getattr(MaintenanceRecord, params.sort_by)
        if params.sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        query = query.offset(params.offset).limit(params.limit)

        return query.all(), total

    def get_maintenance_summary(self) -> MaintenanceSummary:
        """Get maintenance summary statistics"""
        # Equipment statistics
        total_equipment = (
            self.db.query(Equipment).filter(Equipment.is_active == True).count()
        )

        operational = (
            self.db.query(Equipment)
            .filter(
                Equipment.is_active == True,
                Equipment.status == EquipmentStatus.OPERATIONAL,
            )
            .count()
        )

        needs_maintenance = (
            self.db.query(Equipment)
            .filter(
                Equipment.is_active == True,
                Equipment.status == EquipmentStatus.NEEDS_MAINTENANCE,
            )
            .count()
        )

        under_maintenance = (
            self.db.query(Equipment)
            .filter(
                Equipment.is_active == True,
                Equipment.status == EquipmentStatus.UNDER_MAINTENANCE,
            )
            .count()
        )

        # Overdue maintenance
        overdue = (
            self.db.query(Equipment)
            .filter(
                Equipment.is_active == True,
                Equipment.next_due_date < datetime.now(),
                Equipment.next_due_date.isnot(None),
            )
            .count()
        )

        # Scheduled this week
        week_end = datetime.now() + timedelta(days=7)
        scheduled_week = (
            self.db.query(MaintenanceRecord)
            .filter(
                MaintenanceRecord.status == MaintenanceStatus.SCHEDULED,
                MaintenanceRecord.scheduled_date <= week_end,
            )
            .count()
        )

        # Completed this month
        month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0)
        completed_month = (
            self.db.query(MaintenanceRecord)
            .filter(
                MaintenanceRecord.status == MaintenanceStatus.COMPLETED,
                MaintenanceRecord.date_performed >= month_start,
            )
            .count()
        )

        # Cost this month
        cost_result = (
            self.db.query(func.sum(MaintenanceRecord.cost))
            .filter(
                MaintenanceRecord.status == MaintenanceStatus.COMPLETED,
                MaintenanceRecord.date_performed >= month_start,
            )
            .scalar()
        )
        total_cost_month = cost_result or 0.0

        # Average downtime
        downtime_result = (
            self.db.query(func.avg(MaintenanceRecord.downtime_hours))
            .filter(
                MaintenanceRecord.status == MaintenanceStatus.COMPLETED,
                MaintenanceRecord.downtime_hours > 0,
            )
            .scalar()
        )
        avg_downtime = downtime_result or 0.0

        return MaintenanceSummary(
            total_equipment=total_equipment,
            operational_equipment=operational,
            needs_maintenance=needs_maintenance,
            under_maintenance=under_maintenance,
            overdue_maintenance=overdue,
            scheduled_this_week=scheduled_week,
            completed_this_month=completed_month,
            total_cost_this_month=total_cost_month,
            average_downtime_hours=round(avg_downtime, 2),
        )

    def check_and_update_overdue_maintenance(self):
        """Check and update status for overdue maintenance"""
        # Find overdue scheduled maintenance
        overdue_records = (
            self.db.query(MaintenanceRecord)
            .filter(
                MaintenanceRecord.status == MaintenanceStatus.SCHEDULED,
                MaintenanceRecord.scheduled_date < datetime.now(),
            )
            .all()
        )

        for record in overdue_records:
            record.status = MaintenanceStatus.OVERDUE
            equipment = self.get_equipment(record.equipment_id)
            equipment.status = EquipmentStatus.NEEDS_MAINTENANCE

        # Find equipment with overdue preventive maintenance
        overdue_equipment = (
            self.db.query(Equipment)
            .filter(
                Equipment.is_active == True,
                Equipment.next_due_date < datetime.now(),
                Equipment.next_due_date.isnot(None),
                Equipment.status == EquipmentStatus.OPERATIONAL,
            )
            .all()
        )

        for equipment in overdue_equipment:
            equipment.status = EquipmentStatus.NEEDS_MAINTENANCE

        self.db.commit()
