# backend/modules/equipment/schemas.py

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

from .models import MaintenanceStatus, MaintenanceType, EquipmentStatus


class EquipmentBase(BaseModel):
    """Base schema for equipment"""

    equipment_name: str = Field(
        ..., min_length=1, max_length=200, description="Name of the equipment"
    )
    equipment_type: str = Field(
        ..., min_length=1, max_length=100, description="Type of equipment"
    )
    manufacturer: Optional[str] = Field(None, max_length=200)
    model_number: Optional[str] = Field(None, max_length=100)
    serial_number: Optional[str] = Field(None, max_length=100)
    purchase_date: Optional[datetime] = None
    warranty_expiry: Optional[datetime] = None
    location: Optional[str] = Field(None, max_length=200)
    maintenance_interval_days: Optional[int] = Field(
        None, ge=1, description="Days between preventive maintenance"
    )
    notes: Optional[str] = None
    is_critical: bool = Field(default=False, description="Is this critical equipment?")


class EquipmentCreate(EquipmentBase):
    """Schema for creating equipment"""

    pass


class EquipmentUpdate(BaseModel):
    """Schema for updating equipment"""

    equipment_name: Optional[str] = Field(None, min_length=1, max_length=200)
    equipment_type: Optional[str] = Field(None, min_length=1, max_length=100)
    manufacturer: Optional[str] = Field(None, max_length=200)
    model_number: Optional[str] = Field(None, max_length=100)
    serial_number: Optional[str] = Field(None, max_length=100)
    purchase_date: Optional[datetime] = None
    warranty_expiry: Optional[datetime] = None
    location: Optional[str] = Field(None, max_length=200)
    status: Optional[EquipmentStatus] = None
    maintenance_interval_days: Optional[int] = Field(None, ge=1)
    notes: Optional[str] = None
    is_critical: Optional[bool] = None
    is_active: Optional[bool] = None


class Equipment(EquipmentBase):
    """Schema for equipment response"""

    id: int
    status: EquipmentStatus
    last_maintenance_date: Optional[datetime]
    next_due_date: Optional[datetime]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int]
    updated_by: Optional[int]

    class Config:
        from_attributes = True


class EquipmentWithMaintenance(Equipment):
    """Schema for equipment with maintenance history"""

    maintenance_records: List["MaintenanceRecord"] = []
    total_maintenance_count: int = 0
    total_maintenance_cost: float = 0.0
    average_downtime_hours: float = 0.0


class MaintenanceRecordBase(BaseModel):
    """Base schema for maintenance records"""

    equipment_id: int
    maintenance_type: MaintenanceType = MaintenanceType.PREVENTIVE
    scheduled_date: datetime
    description: str = Field(
        ..., min_length=1, description="Description of maintenance work"
    )
    performed_by: Optional[str] = Field(None, max_length=200)
    cost: float = Field(default=0.0, ge=0)
    parts_replaced: Optional[str] = None

    @field_validator("scheduled_date")
    def validate_scheduled_date(cls, v):
        """Ensure scheduled date is reasonable"""
        if v < datetime(2000, 1, 1):
            raise ValueError("Scheduled date cannot be before year 2000")
        return v


class MaintenanceRecordCreate(MaintenanceRecordBase):
    """Schema for creating maintenance records"""

    status: MaintenanceStatus = MaintenanceStatus.SCHEDULED


class MaintenanceRecordUpdate(BaseModel):
    """Schema for updating maintenance records"""

    maintenance_type: Optional[MaintenanceType] = None
    status: Optional[MaintenanceStatus] = None
    scheduled_date: Optional[datetime] = None
    date_performed: Optional[datetime] = None
    description: Optional[str] = Field(None, min_length=1)
    performed_by: Optional[str] = Field(None, max_length=200)
    cost: Optional[float] = Field(None, ge=0)
    parts_replaced: Optional[str] = None
    issues_found: Optional[str] = None
    resolution: Optional[str] = None
    downtime_hours: Optional[float] = Field(None, ge=0)

    @field_validator("date_performed")
    def validate_date_performed(cls, v):
        """Ensure date_performed is not in the future"""
        if v and v > datetime.now():
            raise ValueError("Date performed cannot be in the future")
        return v

    @field_validator("scheduled_date")
    def validate_scheduled_date(cls, v):
        """Ensure scheduled date is reasonable"""
        if v and v < datetime(2000, 1, 1):
            raise ValueError("Scheduled date cannot be before year 2000")
        return v


class MaintenanceRecord(MaintenanceRecordBase):
    """Schema for maintenance record response"""

    id: int
    status: MaintenanceStatus
    date_performed: Optional[datetime]
    next_due_date: Optional[datetime]
    issues_found: Optional[str]
    resolution: Optional[str]
    downtime_hours: float
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int]
    completed_by: Optional[int]
    equipment: Optional[Equipment] = None

    class Config:
        from_attributes = True


class MaintenanceRecordComplete(BaseModel):
    """Schema for completing a maintenance record"""

    date_performed: datetime = Field(default_factory=datetime.now)
    performed_by: str = Field(..., min_length=1, max_length=200)
    cost: Optional[float] = Field(default=0.0, ge=0)
    parts_replaced: Optional[str] = None
    issues_found: Optional[str] = None
    resolution: Optional[str] = None
    downtime_hours: float = Field(default=0.0, ge=0)
    next_due_date: Optional[datetime] = None

    @field_validator("date_performed")
    def validate_date_performed(cls, v):
        """Ensure date_performed is not in the future"""
        if v > datetime.now():
            raise ValueError("Date performed cannot be in the future")
        return v


# Search/Filter schemas
class EquipmentSearchParams(BaseModel):
    """Parameters for searching equipment"""

    query: Optional[str] = None
    equipment_type: Optional[str] = None
    status: Optional[EquipmentStatus] = None
    location: Optional[str] = None
    is_critical: Optional[bool] = None
    needs_maintenance: Optional[bool] = None
    sort_by: str = Field(
        default="equipment_name",
        pattern="^(equipment_name|next_due_date|status|created_at)$",
    )
    sort_order: str = Field(default="asc", pattern="^(asc|desc)$")
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class MaintenanceSearchParams(BaseModel):
    """Parameters for searching maintenance records"""

    equipment_id: Optional[int] = None
    maintenance_type: Optional[MaintenanceType] = None
    status: Optional[MaintenanceStatus] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    performed_by: Optional[str] = None
    sort_by: str = Field(
        default="scheduled_date",
        pattern="^(scheduled_date|date_performed|status|cost)$",
    )
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


# Response schemas
class PaginatedResponse(BaseModel):
    """Base schema for paginated responses"""

    total: int
    page: int
    size: int
    pages: int


class EquipmentListResponse(PaginatedResponse):
    """Response schema for equipment list"""

    items: List[Equipment]


class MaintenanceListResponse(PaginatedResponse):
    """Response schema for maintenance list"""

    items: List[MaintenanceRecord]


class MaintenanceSummary(BaseModel):
    """Summary statistics for maintenance"""

    total_equipment: int
    operational_equipment: int
    needs_maintenance: int
    under_maintenance: int
    overdue_maintenance: int
    scheduled_this_week: int
    completed_this_month: int
    total_cost_this_month: float
    average_downtime_hours: float


# Update forward references
EquipmentWithMaintenance.model_rebuild()
MaintenanceRecord.model_rebuild()
