# backend/modules/equipment/schemas_improved.py

"""
Improved Pydantic schemas with comprehensive validation for Equipment module.
"""

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from typing import Optional, List, Literal, Annotated
from datetime import datetime, date
from decimal import Decimal
import re


# Enums for validation
EquipmentStatusType = Literal["operational", "maintenance", "out_of_service"]
MaintenanceType = Literal["preventive", "repair", "inspection", "calibration"]
MaintenanceStatus = Literal["scheduled", "in_progress", "completed", "cancelled"]
SortByEquipment = Literal["equipment_name", "next_due_date", "status", "created_at"]
SortByMaintenance = Literal["scheduled_date", "date_performed", "status", "cost"]
SortOrder = Literal["asc", "desc"]


class EquipmentBase(BaseModel):
    """Base equipment schema with common fields"""

    equipment_name: str = Field(
        ..., min_length=1, max_length=200, description="Equipment name"
    )
    equipment_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Type of equipment (e.g., Kitchen, HVAC, Storage)",
    )
    manufacturer: Optional[str] = Field(
        None, max_length=100, description="Equipment manufacturer"
    )
    model_number: Optional[str] = Field(
        None, max_length=100, description="Model number"
    )
    serial_number: Optional[str] = Field(
        None, max_length=100, description="Serial number"
    )
    location: Optional[str] = Field(
        None, max_length=200, description="Physical location of equipment"
    )

    @field_validator("equipment_name", "equipment_type", mode="after")
    def validate_not_empty(cls, v):
        if v and not v.strip():
            raise ValueError("Cannot be empty or whitespace only")
        return v.strip() if v else v

    @field_validator("serial_number", mode="after")
    def validate_serial_number(cls, v):
        if v:
            # Remove spaces and convert to uppercase
            v = v.strip().upper()
            # Validate format (alphanumeric with optional dashes)
            if not re.match(r"^[A-Z0-9\-]+$", v):
                raise ValueError(
                    "Serial number must contain only letters, numbers, and dashes"
                )
        return v


class EquipmentCreate(EquipmentBase):
    """Schema for creating equipment"""

    purchase_date: Optional[date] = Field(None, description="Date of purchase")
    warranty_expiry: Optional[date] = Field(None, description="Warranty expiry date")
    purchase_cost: Optional[Annotated[Decimal, Field(None, gt=0, max_digits=10, decimal_places=2)]] = Field(
        None, description="Purchase cost"
    )
    is_critical: bool = Field(
        False, description="Whether equipment is critical for operations"
    )
    maintenance_interval_days: Optional[int] = Field(
        None, gt=0, le=3650, description="Maintenance interval in days"  # Max 10 years
    )
    maintenance_notes: Optional[str] = Field(
        None, max_length=1000, description="General maintenance notes"
    )

    @model_validator(mode='before')
    def validate_dates(cls, values):
        purchase_date = values.get("purchase_date")
        warranty_expiry = values.get("warranty_expiry")

        if purchase_date and warranty_expiry:
            if purchase_date > warranty_expiry:
                raise ValueError("Warranty expiry date must be after purchase date")

        if purchase_date and purchase_date > date.today():
            raise ValueError("Purchase date cannot be in the future")

        return values

    @field_validator("purchase_cost", mode="after")
    def validate_cost(cls, v):
        if v is not None and v > Decimal("1000000"):
            raise ValueError("Purchase cost seems unusually high. Please verify.")
        return v


class EquipmentUpdate(BaseModel):
    """Schema for updating equipment"""

    equipment_name: Optional[str] = Field(None, min_length=1, max_length=200)
    equipment_type: Optional[str] = Field(None, min_length=1, max_length=100)
    manufacturer: Optional[str] = Field(None, max_length=100)
    model_number: Optional[str] = Field(None, max_length=100)
    serial_number: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=200)
    status: Optional[EquipmentStatusType] = None
    warranty_expiry: Optional[date] = None
    is_critical: Optional[bool] = None
    maintenance_interval_days: Optional[int] = Field(None, gt=0, le=3650)
    maintenance_notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("warranty_expiry", mode="after")
    def validate_warranty_expiry(cls, v):
        if v and v < date.today():
            # Warning, but allow updating to past date
            pass
        return v

    class Config:
        validate_assignment = True


class Equipment(EquipmentBase):
    """Schema for equipment response"""

    id: int
    status: EquipmentStatusType
    purchase_date: Optional[date]
    warranty_expiry: Optional[date]
    purchase_cost: Optional[Decimal]
    is_critical: bool
    maintenance_interval_days: Optional[int]
    maintenance_notes: Optional[str]
    next_maintenance_date: Optional[date]
    last_maintenance_date: Optional[date]
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: int
    updated_by: Optional[int]

    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed


class MaintenanceRecordBase(BaseModel):
    """Base maintenance record schema"""

    equipment_id: int = Field(..., gt=0)
    maintenance_type: MaintenanceType
    scheduled_date: date
    description: Optional[str] = Field(None, max_length=1000)
    estimated_duration_hours: Optional[float] = Field(
        None, gt=0, le=168, description="Estimated duration in hours"  # Max 1 week
    )
    estimated_cost: Optional[Annotated[Decimal, Field(None, ge=0, max_digits=10, decimal_places=2)]] = Field(
        None, description="Estimated cost"
    )

    @field_validator("scheduled_date", mode="after")
    def validate_scheduled_date(cls, v):
        if v < date.today():
            raise ValueError("Scheduled date cannot be in the past")
        return v

    @field_validator("estimated_cost", mode="after")
    def validate_estimated_cost(cls, v):
        if v is not None and v > Decimal("100000"):
            raise ValueError("Estimated cost seems unusually high. Please verify.")
        return v


class MaintenanceRecordCreate(MaintenanceRecordBase):
    """Schema for creating maintenance record"""

    assigned_to: Optional[str] = Field(
        None, max_length=100, description="Person assigned to perform maintenance"
    )
    priority: int = Field(2, ge=1, le=5, description="Priority (1=Highest, 5=Lowest)")


class MaintenanceRecordUpdate(BaseModel):
    """Schema for updating maintenance record"""

    maintenance_type: Optional[MaintenanceType] = None
    scheduled_date: Optional[date] = None
    description: Optional[str] = Field(None, max_length=1000)
    estimated_duration_hours: Optional[float] = Field(None, gt=0, le=168)
    estimated_cost: Optional[Annotated[Decimal, Field(None, ge=0, max_digits=10, decimal_places=2)]] = None
    assigned_to: Optional[str] = Field(None, max_length=100)
    priority: Optional[int] = Field(None, ge=1, le=5)
    status: Optional[MaintenanceStatus] = None
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("scheduled_date", mode="after")
    def validate_scheduled_date(cls, v):
        # Allow past dates for updates (rescheduling)
        return v


class MaintenanceRecordComplete(BaseModel):
    """Schema for completing maintenance record"""

    date_performed: date = Field(..., description="Date maintenance was performed")
    performed_by: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Person who performed maintenance",
    )
    actual_duration_hours: float = Field(
        ..., gt=0, le=168, description="Actual duration in hours"
    )
    cost: Annotated[Decimal, Field(..., ge=0, max_digits=10, decimal_places=2)] = Field(..., description="Actual cost")
    downtime_hours: float = Field(
        0, ge=0, le=168, description="Equipment downtime in hours"
    )
    parts_replaced: Optional[str] = Field(
        None, max_length=1000, description="List of parts replaced"
    )
    notes: Optional[str] = Field(None, max_length=2000, description="Completion notes")

    @field_validator("date_performed", mode="after")
    def validate_date_performed(cls, v):
        if v > date.today():
            raise ValueError("Performance date cannot be in the future")
        return v

    @field_validator("cost", mode="after")
    def validate_cost(cls, v):
        if v > Decimal("100000"):
            raise ValueError("Cost seems unusually high. Please verify.")
        return v

    @model_validator(mode='before')
    def validate_durations(cls, values):
        actual = values.get("actual_duration_hours")
        downtime = values.get("downtime_hours")

        if actual and downtime and downtime > actual:
            raise ValueError("Downtime cannot exceed actual duration")

        return values


class MaintenanceRecord(MaintenanceRecordBase):
    """Schema for maintenance record response"""

    id: int
    status: MaintenanceStatus
    assigned_to: Optional[str]
    priority: int
    date_performed: Optional[date]
    performed_by: Optional[str]
    actual_duration_hours: Optional[float]
    cost: Optional[Decimal]
    downtime_hours: Optional[float]
    parts_replaced: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: int
    updated_by: Optional[int]

    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed


class EquipmentWithMaintenance(Equipment):
    """Equipment with maintenance history"""

    maintenance_records: List[MaintenanceRecord] = []
    total_maintenance_count: int = 0
    total_maintenance_cost: float = 0.0
    average_downtime_hours: float = 0.0


class EquipmentSearchParams(BaseModel):
    """Parameters for equipment search"""

    query: Optional[str] = Field(None, max_length=200)
    equipment_type: Optional[str] = Field(None, max_length=100)
    status: Optional[EquipmentStatusType] = None
    location: Optional[str] = Field(None, max_length=200)
    is_critical: Optional[bool] = None
    needs_maintenance: Optional[bool] = None
    sort_by: SortByEquipment = "equipment_name"
    sort_order: SortOrder = "asc"
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)


class MaintenanceSearchParams(BaseModel):
    """Parameters for maintenance record search"""

    equipment_id: Optional[int] = Field(None, gt=0)
    maintenance_type: Optional[MaintenanceType] = None
    status: Optional[MaintenanceStatus] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    performed_by: Optional[str] = Field(None, max_length=100)
    sort_by: SortByMaintenance = "scheduled_date"
    sort_order: SortOrder = "desc"
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)

    @model_validator(mode='before')
    def validate_date_range(cls, values):
        date_from = values.get("date_from")
        date_to = values.get("date_to")

        if date_from and date_to and date_from > date_to:
            raise ValueError("date_from must be before date_to")

        return values


class EquipmentListResponse(BaseModel):
    """Response for equipment list"""

    items: List[Equipment]
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    size: int = Field(..., ge=1)
    pages: int = Field(..., ge=0)


class MaintenanceListResponse(BaseModel):
    """Response for maintenance record list"""

    items: List[MaintenanceRecord]
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    size: int = Field(..., ge=1)
    pages: int = Field(..., ge=0)


class MaintenanceSummary(BaseModel):
    """Summary statistics for maintenance"""

    total_equipment: int = Field(..., ge=0)
    operational_count: int = Field(..., ge=0)
    maintenance_count: int = Field(..., ge=0)
    out_of_service_count: int = Field(..., ge=0)
    overdue_maintenance: int = Field(..., ge=0)
    upcoming_maintenance_7_days: int = Field(..., ge=0)
    upcoming_maintenance_30_days: int = Field(..., ge=0)
    total_maintenance_cost_mtd: float = Field(..., ge=0)
    total_maintenance_cost_ytd: float = Field(..., ge=0)
    average_downtime_hours: float = Field(..., ge=0)
    critical_equipment_down: int = Field(..., ge=0)

    @field_validator("average_downtime_hours", mode="after")
    def round_average(cls, v):
        return round(v, 2)
