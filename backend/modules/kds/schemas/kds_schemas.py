# backend/modules/kds/schemas/kds_schemas.py

"""
Pydantic schemas for Kitchen Display System.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from ..models.kds_models import StationType, StationStatus, DisplayStatus


class ItemStatusUpdate(BaseModel):
    """Schema for updating item status"""
    
    status: DisplayStatus
    staff_id: Optional[int] = None
    reason: Optional[str] = None


class StationCreate(BaseModel):
    """Schema for creating a kitchen station"""

    name: str = Field(..., min_length=1, max_length=100)
    station_type: StationType
    display_name: Optional[str] = None
    color_code: Optional[str] = Field(None, regex="^#[0-9A-Fa-f]{6}$")
    priority: int = Field(0, ge=0, le=100)
    max_active_items: int = Field(10, ge=1, le=50)
    prep_time_multiplier: float = Field(1.0, ge=0.1, le=5.0)
    warning_time_minutes: int = Field(5, ge=1, le=30)
    critical_time_minutes: int = Field(10, ge=1, le=60)
    features: List[str] = Field(default_factory=list)
    printer_id: Optional[str] = None

    @validator("display_name", always=True)
    def set_display_name(cls, v, values):
        return v or values.get("name")


class StationUpdate(BaseModel):
    """Schema for updating a kitchen station"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    station_type: Optional[StationType] = None
    status: Optional[StationStatus] = None
    display_name: Optional[str] = None
    color_code: Optional[str] = Field(None, regex="^#[0-9A-Fa-f]{6}$")
    priority: Optional[int] = Field(None, ge=0, le=100)
    max_active_items: Optional[int] = Field(None, ge=1, le=50)
    prep_time_multiplier: Optional[float] = Field(None, ge=0.1, le=5.0)
    warning_time_minutes: Optional[int] = Field(None, ge=1, le=30)
    critical_time_minutes: Optional[int] = Field(None, ge=1, le=60)
    features: Optional[List[str]] = None
    printer_id: Optional[str] = None
    current_staff_id: Optional[int] = None


class StationResponse(BaseModel):
    """Response schema for kitchen station"""

    id: int
    name: str
    station_type: StationType
    status: StationStatus
    display_name: str
    color_code: Optional[str]
    priority: int
    max_active_items: int
    prep_time_multiplier: float
    warning_time_minutes: int
    critical_time_minutes: int
    features: List[str]
    printer_id: Optional[str]
    current_staff_id: Optional[int]
    staff_assigned_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    # Computed fields
    active_items_count: int = 0
    pending_items_count: int = 0
    average_wait_time: Optional[float] = None

    class Config:
        orm_mode = True


# NOTE: KDSOrderItemResponse and KDSWebSocketMessage are defined later in this file
# with complete field definitions to avoid redefinition issues


class KitchenDisplayCreate(BaseModel):
    """Schema for creating a kitchen display"""

    station_id: int
    display_number: int = Field(1, ge=1, le=10)
    name: Optional[str] = None
    ip_address: Optional[str] = None
    layout_mode: str = Field("grid", regex="^(grid|list|single)$")
    items_per_page: int = Field(6, ge=1, le=20)
    auto_clear_completed: bool = True
    auto_clear_delay_seconds: int = Field(30, ge=10, le=300)


class KitchenDisplayUpdate(BaseModel):
    """Schema for updating a kitchen display"""

    name: Optional[str] = None
    ip_address: Optional[str] = None
    is_active: Optional[bool] = None
    layout_mode: Optional[str] = Field(None, regex="^(grid|list|single)$")
    items_per_page: Optional[int] = Field(None, ge=1, le=20)
    auto_clear_completed: Optional[bool] = None
    auto_clear_delay_seconds: Optional[int] = Field(None, ge=10, le=300)


class KitchenDisplayResponse(BaseModel):
    """Response schema for kitchen display"""

    id: int
    station_id: int
    display_number: int
    name: Optional[str]
    ip_address: Optional[str]
    last_heartbeat: Optional[datetime]
    is_active: bool
    layout_mode: str
    items_per_page: int
    auto_clear_completed: bool
    auto_clear_delay_seconds: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True


class StationAssignmentCreate(BaseModel):
    """Schema for creating station assignments"""

    station_id: int
    category_name: Optional[str] = None
    tag_name: Optional[str] = None
    priority: int = Field(0, ge=0, le=100)
    is_primary: bool = True
    prep_time_override: Optional[int] = Field(None, ge=1, le=120)
    conditions: Dict[str, Any] = Field(default_factory=dict)

    @validator("category_name")
    def validate_assignment(cls, v, values):
        if not v and not values.get("tag_name"):
            raise ValueError("Either category_name or tag_name must be provided")
        return v


class StationAssignmentResponse(BaseModel):
    """Response schema for station assignment"""

    id: int
    station_id: int
    category_name: Optional[str]
    tag_name: Optional[str]
    priority: int
    is_primary: bool
    prep_time_override: Optional[int]
    conditions: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True


class MenuItemStationCreate(BaseModel):
    """Schema for assigning menu items to stations"""

    menu_item_id: int
    station_id: int
    is_primary: bool = True
    sequence: int = Field(0, ge=0, le=10)
    prep_time_minutes: int = Field(..., ge=1, le=120)
    station_notes: Optional[str] = None


class MenuItemStationResponse(BaseModel):
    """Response schema for menu item station assignment"""

    id: int
    menu_item_id: int
    station_id: int
    is_primary: bool
    sequence: int
    prep_time_minutes: int
    station_notes: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True


class OrderItemDisplay(BaseModel):
    """Schema for displaying order items on KDS"""

    order_id: int
    order_item_id: int
    table_number: Optional[int]
    display_name: str
    quantity: int
    modifiers: List[str] = Field(default_factory=list)
    special_instructions: Optional[str]
    course_number: int = 1
    priority: int = 0
    fire_time: Optional[datetime] = None


class KDSOrderItemResponse(BaseModel):
    """Response schema for KDS order items"""

    id: int
    order_item_id: int
    station_id: int
    display_name: str
    quantity: int
    modifiers: List[str]
    special_instructions: Optional[str]
    status: DisplayStatus
    sequence_number: Optional[int]
    received_at: datetime
    started_at: Optional[datetime]
    target_time: Optional[datetime]
    completed_at: Optional[datetime]
    acknowledged_at: Optional[datetime]
    priority: int
    course_number: int
    fire_time: Optional[datetime]
    started_by_id: Optional[int]
    completed_by_id: Optional[int]
    recall_count: int
    last_recalled_at: Optional[datetime]
    recall_reason: Optional[str]

    # Computed fields
    wait_time_seconds: int
    is_late: bool

    # Related data
    order_id: Optional[int] = None
    table_number: Optional[int] = None
    server_name: Optional[str] = None

    class Config:
        orm_mode = True


class StationSummary(BaseModel):
    """Summary statistics for a station"""

    station_id: int
    station_name: str
    station_type: StationType
    status: StationStatus
    active_items: int
    pending_items: int
    completed_today: int
    average_wait_time: float
    late_items: int
    staff_name: Optional[str]
    last_activity: Optional[datetime]


class KDSWebSocketMessage(BaseModel):
    """WebSocket message format for KDS updates"""

    type: str = Field(
        ..., regex="^(new_item|update_item|remove_item|station_update|heartbeat)$"
    )
    station_id: Optional[int] = None
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
