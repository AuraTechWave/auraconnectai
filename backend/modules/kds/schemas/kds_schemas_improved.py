# backend/modules/kds/schemas/kds_schemas_improved.py

"""
Improved Pydantic schemas with comprehensive validation for Kitchen Display System.
"""

from pydantic import BaseModel, Field, validator, root_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime, timedelta
from enum import Enum
import re

from ..models.kds_models import StationType, StationStatus, DisplayStatus


# Enums for validation
AssignmentType = Literal["category", "tag", "custom"]
LayoutMode = Literal["grid", "list", "single", "compact", "expanded"]
WebSocketMessageType = Literal[
    "new_item",
    "update_item",
    "remove_item",
    "station_update",
    "heartbeat",
    "error",
    "reconnect",
]


class StationCreate(BaseModel):
    """Schema for creating a kitchen station with enhanced validation"""

    name: str = Field(..., min_length=1, max_length=100, description="Station name")
    station_type: StationType
    display_name: Optional[str] = Field(
        None, max_length=100, description="Display name (defaults to name)"
    )
    color_code: Optional[str] = Field(None, description="Hex color code for station")
    priority: int = Field(
        50,
        ge=0,
        le=100,
        description="Station priority (0-100, higher = more important)",
    )
    max_active_items: int = Field(
        10, ge=1, le=50, description="Maximum concurrent active items"
    )
    prep_time_multiplier: float = Field(
        1.0, ge=0.1, le=5.0, description="Multiplier for prep time estimates"
    )
    warning_time_minutes: int = Field(
        5, ge=1, le=30, description="Minutes before item is considered late"
    )
    critical_time_minutes: int = Field(
        10, ge=1, le=60, description="Minutes before item is critical"
    )
    features: List[str] = Field(
        default_factory=list, max_items=20, description="Station features/capabilities"
    )
    printer_id: Optional[str] = Field(
        None, max_length=50, description="Associated printer ID"
    )

    @validator("name")
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError("Name cannot be empty or whitespace only")
        # Sanitize name
        v = v.strip()
        if not re.match(r"^[\w\s\-]+$", v):
            raise ValueError(
                "Name can only contain letters, numbers, spaces, and hyphens"
            )
        return v

    @validator("display_name", always=True)
    def set_display_name(cls, v, values):
        if v:
            v = v.strip()
            if not v:
                return values.get("name")
        return v or values.get("name")

    @validator("color_code")
    def validate_color_code(cls, v):
        if v:
            v = v.strip().upper()
            if not re.match(r"^#[0-9A-F]{6}$", v):
                raise ValueError("Color code must be in hex format (#RRGGBB)")
        return v

    @validator("features")
    def validate_features(cls, v):
        if v:
            # Remove duplicates and empty strings
            v = list(set(f.strip() for f in v if f.strip()))
            # Validate feature names
            for feature in v:
                if not re.match(r"^[\w\-]+$", feature):
                    raise ValueError(f"Invalid feature name: {feature}")
        return v

    @root_validator
    def validate_time_settings(cls, values):
        warning = values.get("warning_time_minutes", 5)
        critical = values.get("critical_time_minutes", 10)

        if critical <= warning:
            raise ValueError("Critical time must be greater than warning time")

        return values


class StationUpdate(BaseModel):
    """Schema for updating a kitchen station with validation"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    station_type: Optional[StationType] = None
    status: Optional[StationStatus] = None
    display_name: Optional[str] = Field(None, max_length=100)
    color_code: Optional[str] = None
    priority: Optional[int] = Field(None, ge=0, le=100)
    max_active_items: Optional[int] = Field(None, ge=1, le=50)
    prep_time_multiplier: Optional[float] = Field(None, ge=0.1, le=5.0)
    warning_time_minutes: Optional[int] = Field(None, ge=1, le=30)
    critical_time_minutes: Optional[int] = Field(None, ge=1, le=60)
    features: Optional[List[str]] = Field(None, max_items=20)
    printer_id: Optional[str] = Field(None, max_length=50)
    current_staff_id: Optional[int] = Field(None, gt=0)

    @validator("name")
    def validate_name(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Name cannot be empty or whitespace only")
            if not re.match(r"^[\w\s\-]+$", v):
                raise ValueError(
                    "Name can only contain letters, numbers, spaces, and hyphens"
                )
        return v

    @validator("color_code")
    def validate_color_code(cls, v):
        if v is not None:
            v = v.strip().upper()
            if not re.match(r"^#[0-9A-F]{6}$", v):
                raise ValueError("Color code must be in hex format (#RRGGBB)")
        return v

    @root_validator
    def validate_time_settings(cls, values):
        # Only validate if both values are being updated
        if "warning_time_minutes" in values and "critical_time_minutes" in values:
            warning = values.get("warning_time_minutes")
            critical = values.get("critical_time_minutes")

            if warning and critical and critical <= warning:
                raise ValueError("Critical time must be greater than warning time")

        return values


class StationResponse(BaseModel):
    """Response schema for kitchen station with computed fields"""

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
    efficiency_score: Optional[float] = None

    @validator("average_wait_time")
    def round_wait_time(cls, v):
        return round(v, 2) if v is not None else None

    @validator("efficiency_score")
    def validate_efficiency(cls, v):
        if v is not None:
            return max(0.0, min(100.0, round(v, 2)))
        return v

    class Config:
        orm_mode = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class KitchenDisplayCreate(BaseModel):
    """Schema for creating a kitchen display with validation"""

    station_id: int = Field(..., gt=0)
    display_number: int = Field(
        1, ge=1, le=10, description="Display number within station"
    )
    name: str = Field(..., min_length=1, max_length=100, description="Display name")
    ip_address: Optional[str] = Field(
        None, description="IP address for network displays"
    )
    layout_mode: LayoutMode = Field("grid", description="Display layout mode")
    items_per_page: int = Field(6, ge=1, le=20, description="Items shown per page")
    auto_clear_completed: bool = Field(True, description="Auto-clear completed items")
    auto_clear_delay_seconds: int = Field(
        30, ge=10, le=300, description="Delay before auto-clearing"
    )

    @validator("name")
    def validate_name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty")
        return v

    @validator("ip_address")
    def validate_ip_address(cls, v):
        if v:
            # Basic IP validation
            parts = v.split(".")
            if len(parts) != 4:
                raise ValueError("Invalid IP address format")
            for part in parts:
                try:
                    num = int(part)
                    if num < 0 or num > 255:
                        raise ValueError("Invalid IP address")
                except ValueError:
                    raise ValueError("Invalid IP address format")
        return v


class KitchenDisplayUpdate(BaseModel):
    """Schema for updating a kitchen display"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    ip_address: Optional[str] = None
    is_active: Optional[bool] = None
    layout_mode: Optional[LayoutMode] = None
    items_per_page: Optional[int] = Field(None, ge=1, le=20)
    auto_clear_completed: Optional[bool] = None
    auto_clear_delay_seconds: Optional[int] = Field(None, ge=10, le=300)

    @validator("ip_address")
    def validate_ip_address(cls, v):
        if v:
            parts = v.split(".")
            if len(parts) != 4:
                raise ValueError("Invalid IP address format")
            for part in parts:
                try:
                    num = int(part)
                    if num < 0 or num > 255:
                        raise ValueError("Invalid IP address")
                except ValueError:
                    raise ValueError("Invalid IP address format")
        return v


class KitchenDisplayResponse(BaseModel):
    """Response schema for kitchen display"""

    id: int
    station_id: int
    display_number: int
    name: str
    ip_address: Optional[str]
    last_heartbeat: Optional[datetime]
    is_active: bool
    is_online: bool = False
    layout_mode: str
    items_per_page: int
    auto_clear_completed: bool
    auto_clear_delay_seconds: int
    created_at: datetime
    updated_at: Optional[datetime]

    @validator("is_online", always=True)
    def check_online_status(cls, v, values):
        last_heartbeat = values.get("last_heartbeat")
        if last_heartbeat:
            # Consider online if heartbeat within last 2 minutes
            return (datetime.utcnow() - last_heartbeat) < timedelta(minutes=2)
        return False

    class Config:
        orm_mode = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class StationAssignmentCreate(BaseModel):
    """Schema for creating station assignments with validation"""

    station_id: int = Field(..., gt=0)
    assignment_type: AssignmentType
    assignment_value: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Category name, tag name, or custom value",
    )
    priority: int = Field(50, ge=0, le=100, description="Assignment priority")
    is_primary: bool = Field(True, description="Primary station for this assignment")
    prep_time_override: Optional[int] = Field(
        None, ge=1, le=120, description="Override prep time in minutes"
    )
    conditions: Dict[str, Any] = Field(
        default_factory=dict, description="Additional routing conditions"
    )

    @validator("assignment_value")
    def validate_assignment_value(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Assignment value cannot be empty")
        return v

    @validator("conditions")
    def validate_conditions(cls, v):
        # Validate condition structure
        allowed_keys = ["time_range", "days_of_week", "order_type", "min_quantity"]
        for key in v.keys():
            if key not in allowed_keys:
                raise ValueError(f"Invalid condition key: {key}")
        return v


class StationAssignmentResponse(BaseModel):
    """Response schema for station assignment"""

    id: int
    station_id: int
    assignment_type: str
    assignment_value: str
    priority: int
    is_primary: bool
    prep_time_override: Optional[int]
    conditions: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class MenuItemStationCreate(BaseModel):
    """Schema for assigning menu items to stations"""

    menu_item_id: int = Field(..., gt=0)
    station_id: int = Field(..., gt=0)
    is_primary: bool = Field(True, description="Primary station for this item")
    sequence: int = Field(0, ge=0, le=10, description="Preparation sequence order")
    prep_time_minutes: int = Field(
        ..., ge=1, le=120, description="Preparation time in minutes"
    )
    station_notes: Optional[str] = Field(
        None, max_length=500, description="Special instructions for this station"
    )

    @validator("station_notes")
    def validate_notes(cls, v):
        if v:
            v = v.strip()
            if len(v) > 500:
                raise ValueError("Station notes too long (max 500 characters)")
        return v


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
        json_encoders = {datetime: lambda v: v.isoformat()}


class OrderItemDisplay(BaseModel):
    """Schema for displaying order items on KDS with validation"""

    order_id: int = Field(..., gt=0)
    order_item_id: int = Field(..., gt=0)
    table_number: Optional[int] = Field(None, ge=1, le=9999)
    display_name: str = Field(
        ..., min_length=1, max_length=200, description="Item display name"
    )
    quantity: int = Field(..., ge=1, le=999)
    modifiers: List[str] = Field(
        default_factory=list, max_items=20, description="Item modifiers"
    )
    special_instructions: Optional[str] = Field(
        None, max_length=500, description="Special preparation instructions"
    )
    course_number: int = Field(
        1, ge=1, le=10, description="Course number for sequencing"
    )
    priority: int = Field(0, ge=0, le=100, description="Item priority")
    fire_time: Optional[datetime] = Field(None, description="Scheduled fire time")

    @validator("display_name")
    def validate_display_name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Display name cannot be empty")
        return v

    @validator("modifiers")
    def validate_modifiers(cls, v):
        if v:
            # Clean up modifiers
            v = [m.strip() for m in v if m.strip()]
            # Limit modifier length
            for mod in v:
                if len(mod) > 50:
                    raise ValueError("Modifier too long (max 50 characters)")
        return v

    @validator("fire_time")
    def validate_fire_time(cls, v):
        if v and v < datetime.utcnow():
            raise ValueError("Fire time cannot be in the past")
        return v


class KDSOrderItemResponse(BaseModel):
    """Response schema for KDS order items with computed fields"""

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
    wait_time_seconds: int = 0
    is_late: bool = False
    urgency_level: str = "normal"

    # Related data
    order_id: Optional[int] = None
    table_number: Optional[int] = None
    server_name: Optional[str] = None

    @validator("wait_time_seconds", always=True)
    def calculate_wait_time(cls, v, values):
        received_at = values.get("received_at")
        completed_at = values.get("completed_at")

        if received_at:
            end_time = completed_at or datetime.utcnow()
            return int((end_time - received_at).total_seconds())
        return 0

    @validator("is_late", always=True)
    def check_if_late(cls, v, values):
        target_time = values.get("target_time")
        status = values.get("status")

        if target_time and status not in [
            DisplayStatus.COMPLETED,
            DisplayStatus.CANCELLED,
        ]:
            return datetime.utcnow() > target_time
        return False

    @validator("urgency_level", always=True)
    def calculate_urgency(cls, v, values):
        is_late = values.get("is_late", False)
        wait_time = values.get("wait_time_seconds", 0)
        priority = values.get("priority", 0)

        if is_late or wait_time > 900:  # 15 minutes
            return "critical"
        elif wait_time > 600 or priority >= 80:  # 10 minutes
            return "high"
        elif wait_time > 300 or priority >= 50:  # 5 minutes
            return "medium"
        else:
            return "normal"

    class Config:
        orm_mode = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class StationSummary(BaseModel):
    """Summary statistics for a station with validation"""

    station_id: int
    station_name: str
    station_type: StationType
    status: StationStatus
    active_items: int = Field(ge=0)
    pending_items: int = Field(ge=0)
    completed_today: int = Field(ge=0)
    average_wait_time: float = Field(ge=0.0)
    late_items: int = Field(ge=0)
    staff_name: Optional[str]
    last_activity: Optional[datetime]
    efficiency_percentage: float = Field(ge=0.0, le=100.0)

    @validator("average_wait_time")
    def round_wait_time(cls, v):
        return round(v, 2)

    @validator("efficiency_percentage")
    def round_efficiency(cls, v):
        return round(v, 2)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class KDSWebSocketMessage(BaseModel):
    """WebSocket message format for KDS updates with validation"""

    type: WebSocketMessageType
    station_id: Optional[int] = Field(None, gt=0)
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sequence: Optional[int] = Field(
        None, description="Message sequence number for ordering"
    )

    @validator("data")
    def validate_data(cls, v, values):
        msg_type = values.get("type")

        # Validate data structure based on message type
        if msg_type in ["new_item", "update_item"]:
            if "item" not in v:
                raise ValueError(f"Message type '{msg_type}' requires 'item' in data")
        elif msg_type == "remove_item":
            if "item_id" not in v:
                raise ValueError(
                    "Message type 'remove_item' requires 'item_id' in data"
                )
        elif msg_type == "station_update":
            if "station" not in v and "action" not in v:
                raise ValueError(
                    "Message type 'station_update' requires 'station' or 'action' in data"
                )
        elif msg_type == "error":
            if "message" not in v:
                raise ValueError("Message type 'error' requires 'message' in data")

        return v

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class BulkStationStatusUpdate(BaseModel):
    """Schema for bulk station status updates"""

    station_ids: List[int] = Field(
        ..., min_items=1, max_items=50, description="List of station IDs to update"
    )
    status: StationStatus

    @validator("station_ids")
    def validate_station_ids(cls, v):
        # Remove duplicates
        v = list(set(v))
        # Ensure all positive
        if any(id <= 0 for id in v):
            raise ValueError("All station IDs must be positive")
        return v


class KDSMetrics(BaseModel):
    """Real-time KDS metrics"""

    total_stations: int = Field(ge=0)
    active_stations: int = Field(ge=0)
    total_pending_items: int = Field(ge=0)
    total_active_items: int = Field(ge=0)
    average_wait_time_seconds: float = Field(ge=0.0)
    items_per_minute: float = Field(ge=0.0)
    late_percentage: float = Field(ge=0.0, le=100.0)
    busiest_station: Optional[str] = None

    @validator("average_wait_time_seconds", "items_per_minute", "late_percentage")
    def round_metrics(cls, v):
        return round(v, 2)
