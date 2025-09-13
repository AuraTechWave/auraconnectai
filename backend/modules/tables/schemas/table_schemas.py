# backend/modules/tables/schemas/table_schemas.py

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict
from decimal import Decimal

from ..models.table_models import (
    TableStatus,
    TableShape,
    FloorStatus,
    ReservationStatus,
)


# Floor Schemas
class FloorBase(BaseModel):
    """Base floor schema"""

    name: str = Field(..., max_length=100)
    display_name: Optional[str] = Field(None, max_length=100)
    floor_number: int = Field(1, ge=0)
    width: int = Field(1000, gt=0)
    height: int = Field(800, gt=0)
    background_image: Optional[str] = None
    grid_size: int = Field(20, gt=0)
    max_capacity: Optional[int] = Field(None, gt=0)
    layout_config: Optional[Dict[str, Any]] = {}


class FloorCreate(FloorBase):
    """Floor creation schema"""

    status: FloorStatus = FloorStatus.ACTIVE
    is_default: bool = False


class FloorUpdate(BaseModel):
    """Floor update schema"""

    name: Optional[str] = Field(None, max_length=100)
    display_name: Optional[str] = Field(None, max_length=100)
    floor_number: Optional[int] = Field(None, ge=0)
    width: Optional[int] = Field(None, gt=0)
    height: Optional[int] = Field(None, gt=0)
    background_image: Optional[str] = None
    grid_size: Optional[int] = Field(None, gt=0)
    status: Optional[FloorStatus] = None
    is_default: Optional[bool] = None
    max_capacity: Optional[int] = Field(None, gt=0)
    layout_config: Optional[Dict[str, Any]] = None


class FloorResponse(FloorBase):
    """Floor response schema"""

    id: int
    restaurant_id: int
    status: FloorStatus
    is_default: bool
    table_count: Optional[int] = 0
    occupied_tables: Optional[int] = 0
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed


# Table Schemas
class TableBase(BaseModel):
    """Base table schema"""

    table_number: str = Field(..., max_length=20)
    display_name: Optional[str] = Field(None, max_length=50)
    min_capacity: int = Field(1, ge=1)
    max_capacity: int = Field(..., ge=1)
    preferred_capacity: Optional[int] = None

    @field_validator("preferred_capacity", mode="after")
    def validate_preferred_capacity(cls, v, values):
        if v is not None:
            min_cap = info.data.get("min_capacity", 1)
            max_cap = info.data.get("max_capacity")
            if max_cap and (v < min_cap or v > max_cap):
                raise ValueError(
                    "Preferred capacity must be between min and max capacity"
                )
        return v


class TableLayoutData(BaseModel):
    """Table layout position data"""

    position_x: int = Field(0, ge=0)
    position_y: int = Field(0, ge=0)
    width: int = Field(100, gt=0)
    height: int = Field(100, gt=0)
    rotation: int = Field(0, ge=0, lt=360)
    shape: TableShape = TableShape.RECTANGLE
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")


class TableFeatures(BaseModel):
    """Table features"""

    has_power_outlet: bool = False
    is_wheelchair_accessible: bool = False
    is_by_window: bool = False
    is_private: bool = False
    is_combinable: bool = True


class TableCreate(TableBase, TableLayoutData, TableFeatures):
    """Table creation schema"""

    floor_id: int
    section: Optional[str] = Field(None, max_length=50)
    zone: Optional[str] = Field(None, max_length=50)
    server_station: Optional[str] = Field(None, max_length=50)
    properties: Optional[Dict[str, Any]] = {}


class TableUpdate(BaseModel):
    """Table update schema"""

    table_number: Optional[str] = Field(None, max_length=20)
    display_name: Optional[str] = Field(None, max_length=50)
    floor_id: Optional[int] = None
    min_capacity: Optional[int] = Field(None, ge=1)
    max_capacity: Optional[int] = Field(None, ge=1)
    preferred_capacity: Optional[int] = None
    position_x: Optional[int] = Field(None, ge=0)
    position_y: Optional[int] = Field(None, ge=0)
    width: Optional[int] = Field(None, gt=0)
    height: Optional[int] = Field(None, gt=0)
    rotation: Optional[int] = Field(None, ge=0, lt=360)
    shape: Optional[TableShape] = None
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    status: Optional[TableStatus] = None
    is_active: Optional[bool] = None
    has_power_outlet: Optional[bool] = None
    is_wheelchair_accessible: Optional[bool] = None
    is_by_window: Optional[bool] = None
    is_private: Optional[bool] = None
    is_combinable: Optional[bool] = None
    section: Optional[str] = Field(None, max_length=50)
    zone: Optional[str] = Field(None, max_length=50)
    server_station: Optional[str] = Field(None, max_length=50)
    properties: Optional[Dict[str, Any]] = None


class TableResponse(TableBase, TableLayoutData, TableFeatures):
    """Table response schema"""

    id: int
    restaurant_id: int
    floor_id: int
    status: TableStatus
    is_active: bool
    section: Optional[str]
    zone: Optional[str]
    server_station: Optional[str]
    qr_code: Optional[str]
    properties: Dict[str, Any]
    current_session: Optional["TableSessionResponse"] = None
    floor_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed


# Table Session Schemas
class TableSessionCreate(BaseModel):
    """Create table session"""

    table_id: int
    guest_count: int = Field(..., gt=0)
    guest_name: Optional[str] = Field(None, max_length=100)
    guest_phone: Optional[str] = Field(None, max_length=20)
    server_id: Optional[int] = None
    combined_table_ids: Optional[List[int]] = []


class TableSessionUpdate(BaseModel):
    """Update table session"""

    guest_count: Optional[int] = Field(None, gt=0)
    guest_name: Optional[str] = Field(None, max_length=100)
    guest_phone: Optional[str] = Field(None, max_length=20)
    server_id: Optional[int] = None
    order_id: Optional[int] = None


class TableSessionResponse(BaseModel):
    """Table session response"""

    id: int
    restaurant_id: int
    table_id: int
    start_time: datetime
    end_time: Optional[datetime]
    guest_count: int
    guest_name: Optional[str]
    guest_phone: Optional[str]
    order_id: Optional[int]
    server_id: Optional[int]
    server_name: Optional[str] = None
    duration_minutes: Optional[int] = None
    combined_tables: Optional[List[Dict[str, Any]]] = []
    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed


# Reservation Schemas
class TableReservationBase(BaseModel):
    """Base reservation schema"""

    reservation_date: datetime
    guest_count: int = Field(..., gt=0)
    guest_name: str = Field(..., max_length=100)
    guest_phone: str = Field(..., max_length=20)
    guest_email: Optional[str] = Field(None, max_length=100)
    duration_minutes: int = Field(120, gt=0)


class TableReservationCreate(TableReservationBase):
    """Create reservation"""

    table_id: Optional[int] = None  # Can be auto-assigned
    customer_id: Optional[int] = None
    special_requests: Optional[str] = Field(None, max_length=500)
    occasion: Optional[str] = Field(None, max_length=50)
    table_preferences: Optional[Dict[str, Any]] = {}
    deposit_amount: Optional[Decimal] = None
    source: Optional[str] = Field("website", max_length=50)


class TableReservationUpdate(BaseModel):
    """Update reservation"""

    table_id: Optional[int] = None
    reservation_date: Optional[datetime] = None
    guest_count: Optional[int] = Field(None, gt=0)
    guest_name: Optional[str] = Field(None, max_length=100)
    guest_phone: Optional[str] = Field(None, max_length=20)
    guest_email: Optional[str] = Field(None, max_length=100)
    duration_minutes: Optional[int] = Field(None, gt=0)
    special_requests: Optional[str] = Field(None, max_length=500)
    occasion: Optional[str] = Field(None, max_length=50)
    table_preferences: Optional[Dict[str, Any]] = None
    status: Optional[ReservationStatus] = None


class TableReservationResponse(TableReservationBase):
    """Reservation response"""

    id: int
    restaurant_id: int
    table_id: Optional[int]
    customer_id: Optional[int]
    reservation_code: str
    special_requests: Optional[str]
    occasion: Optional[str]
    status: ReservationStatus
    confirmed_at: Optional[datetime]
    seated_at: Optional[datetime]
    completed_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    cancellation_reason: Optional[str]
    table_preferences: Dict[str, Any]
    deposit_amount: Optional[Decimal]
    deposit_paid: bool
    reminder_sent: bool
    reminder_sent_at: Optional[datetime]
    source: Optional[str]
    table_number: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed


# Layout Schemas
class TableLayoutCreate(BaseModel):
    """Create table layout"""

    name: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    layout_data: Dict[str, Any]
    is_active: bool = False
    is_default: bool = False
    active_days: Optional[List[str]] = None
    active_from_time: Optional[str] = Field(
        None, pattern="^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"
    )
    active_to_time: Optional[str] = Field(
        None, pattern="^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"
    )
    event_date: Optional[datetime] = None
    event_name: Optional[str] = Field(None, max_length=100)


class TableLayoutUpdate(BaseModel):
    """Update table layout"""

    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    layout_data: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    active_days: Optional[List[str]] = None
    active_from_time: Optional[str] = Field(
        None, pattern="^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"
    )
    active_to_time: Optional[str] = Field(
        None, pattern="^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"
    )
    event_date: Optional[datetime] = None
    event_name: Optional[str] = Field(None, max_length=100)


class TableLayoutResponse(BaseModel):
    """Layout response"""

    id: int
    restaurant_id: int
    name: str
    description: Optional[str]
    layout_data: Dict[str, Any]
    is_active: bool
    is_default: bool
    active_days: Optional[List[str]]
    active_from_time: Optional[str]
    active_to_time: Optional[str]
    event_date: Optional[datetime]
    event_name: Optional[str]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed


# Bulk Operations
class BulkTableCreate(BaseModel):
    """Bulk create tables"""

    floor_id: int
    tables: List[TableCreate]


class BulkTableUpdate(BaseModel):
    """Bulk update tables"""

    table_ids: List[int]
    update_data: TableUpdate


# Status Updates
class TableStatusUpdate(BaseModel):
    """Update table status"""

    status: TableStatus
    reason: Optional[str] = Field(None, max_length=200)


class BulkTableStatusUpdate(BaseModel):
    """Bulk update table status"""

    table_ids: List[int]
    status: TableStatus
    reason: Optional[str] = Field(None, max_length=200)


# Analytics
class TableUtilizationStats(BaseModel):
    """Table utilization statistics"""

    table_id: int
    table_number: str
    total_sessions: int
    total_guests: int
    total_revenue: Decimal
    avg_session_duration: float
    avg_guests_per_session: float
    occupancy_rate: float
    peak_hours: List[int]


class FloorHeatmapData(BaseModel):
    """Floor heatmap data for visualization"""

    floor_id: int
    floor_name: str
    period: str  # e.g., "today", "week", "month"
    heatmap_data: List[Dict[str, Any]]  # Table positions with utilization intensity


# Real-time Update Schemas
class RealtimeTableStatus(BaseModel):
    """Real-time table status update"""

    id: int
    table_number: str
    floor_id: int
    status: TableStatus
    capacity: Dict[str, int]
    position: Dict[str, int]
    current_session: Optional[Dict[str, Any]]
    features: Dict[str, bool]


class RealtimeTurnTimeUpdate(BaseModel):
    """Real-time turn time update"""

    turn_times: Dict[int, float]  # table_id -> minutes
    average_turn_time: float
    active_tables: int
    timestamp: datetime


class RealtimeHeatMapData(BaseModel):
    """Real-time heat map data"""

    data: List[Dict[str, Any]]
    period_days: int
    max_occupancy_score: float
    timestamp: datetime


class RealtimeOccupancyUpdate(BaseModel):
    """Real-time occupancy status update"""

    overview: Dict[str, Any]
    turn_times: Dict[str, Any]
    status_breakdown: Dict[str, int]
    timestamp: datetime


class RealtimeAlert(BaseModel):
    """Real-time alert notification"""

    type: str  # long_turn_time, high_occupancy, etc.
    severity: str  # info, warning, error
    table_id: Optional[int]
    table_number: Optional[str]
    message: str
    data: Dict[str, Any]


class WebSocketMessage(BaseModel):
    """WebSocket message format"""

    type: str
    data: Optional[Dict[str, Any]]
    table_id: Optional[int]
    timestamp: datetime
    message: Optional[str]


class WebSocketSubscription(BaseModel):
    """WebSocket subscription request"""

    type: str
    floor_id: Optional[int]
    table_ids: Optional[List[int]]
    update_types: Optional[List[str]]


# Turn Time Analytics Schemas
class TurnTimeAnalytics(BaseModel):
    """Turn time analytics response"""

    analytics: Dict[str, Dict[str, Any]]
    overall: Dict[str, Any]


class TablePerformanceMetrics(BaseModel):
    """Table performance metrics"""

    table: Dict[str, Any]
    performance: Dict[str, Any]


class PeakHoursAnalysis(BaseModel):
    """Peak hours analysis"""

    heat_map: List[Dict[str, Any]]
    peak_hours: List[Dict[str, Any]]
    analysis_period_days: int


class CurrentAnalytics(BaseModel):
    """Current real-time analytics"""

    overview: Dict[str, Any]
    turn_times: Dict[str, Any]
    status_breakdown: Dict[str, int]
    timestamp: datetime
