"""
Schemas for order queue management.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum


class QueueType(str, Enum):
    """Types of order queues"""

    KITCHEN = "kitchen"
    BAR = "bar"
    DELIVERY = "delivery"
    TAKEOUT = "takeout"
    DINE_IN = "dine_in"
    CATERING = "catering"
    DRIVE_THRU = "drive_thru"
    CUSTOM = "custom"


class QueueStatus(str, Enum):
    """Queue operational status"""

    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"
    MAINTENANCE = "maintenance"


class QueueItemStatus(str, Enum):
    """Status of items in queue"""

    QUEUED = "queued"
    IN_PREPARATION = "in_preparation"
    READY = "ready"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DELAYED = "delayed"


# Queue Management Schemas
class QueueBase(BaseModel):
    """Base schema for queues"""

    name: str = Field(..., min_length=1, max_length=100)
    queue_type: QueueType
    display_name: Optional[str] = None
    description: Optional[str] = None
    priority: int = Field(0, ge=0, le=100)
    max_capacity: Optional[int] = Field(None, gt=0)
    auto_sequence: bool = True
    default_prep_time: int = Field(15, ge=1)
    warning_threshold: int = Field(5, ge=1)
    critical_threshold: int = Field(10, ge=1)
    color_code: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    icon: Optional[str] = None
    display_columns: List[str] = []
    operating_hours: Optional[Dict[str, Any]] = None
    station_assignments: List[int] = []
    routing_rules: Optional[Dict[str, Any]] = None


class QueueCreate(QueueBase):
    """Schema for creating a queue"""

    pass


class QueueUpdate(BaseModel):
    """Schema for updating a queue"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    display_name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[QueueStatus] = None
    priority: Optional[int] = Field(None, ge=0, le=100)
    max_capacity: Optional[int] = Field(None, gt=0)
    auto_sequence: Optional[bool] = None
    default_prep_time: Optional[int] = Field(None, ge=1)
    warning_threshold: Optional[int] = Field(None, ge=1)
    critical_threshold: Optional[int] = Field(None, ge=1)
    color_code: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    operating_hours: Optional[Dict[str, Any]] = None
    station_assignments: Optional[List[int]] = None
    routing_rules: Optional[Dict[str, Any]] = None


class QueueResponse(QueueBase):
    """Schema for queue response"""

    id: int
    status: QueueStatus
    current_size: int
    avg_wait_time: Optional[float]
    items_completed_today: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# Queue Item Schemas
class QueueItemBase(BaseModel):
    """Base schema for queue items"""

    order_id: int
    priority: int = Field(0, ge=-100, le=100)
    is_expedited: bool = False
    display_name: Optional[str] = None
    display_details: Optional[Dict[str, Any]] = None
    customer_name: Optional[str] = None


class QueueItemCreate(QueueItemBase):
    """Schema for adding item to queue"""

    queue_id: int
    estimated_ready_time: Optional[datetime] = None
    hold_until: Optional[datetime] = None
    hold_reason: Optional[str] = None
    assign_to_id: Optional[int] = None
    station_id: Optional[int] = None


class QueueItemUpdate(BaseModel):
    """Schema for updating queue item"""

    priority: Optional[int] = Field(None, ge=-100, le=100)
    is_expedited: Optional[bool] = None
    status: Optional[QueueItemStatus] = None
    substatus: Optional[str] = None
    estimated_ready_time: Optional[datetime] = None
    assigned_to_id: Optional[int] = None
    station_id: Optional[int] = None
    hold_until: Optional[datetime] = None
    hold_reason: Optional[str] = None
    display_details: Optional[Dict[str, Any]] = None


class QueueItemResponse(QueueItemBase):
    """Schema for queue item response"""

    id: int
    queue_id: int
    sequence_number: int
    status: QueueItemStatus
    substatus: Optional[str]
    queued_at: datetime
    started_at: Optional[datetime]
    ready_at: Optional[datetime]
    completed_at: Optional[datetime]
    estimated_ready_time: Optional[datetime]
    assigned_to_id: Optional[int]
    assigned_at: Optional[datetime]
    station_id: Optional[int]
    hold_until: Optional[datetime]
    hold_reason: Optional[str]
    delay_minutes: Optional[int]
    prep_time_actual: Optional[int]
    wait_time_actual: Optional[int]

    class Config:
        from_attributes = True


# Queue Operations Schemas
class MoveItemRequest(BaseModel):
    """Request to move item in queue"""

    item_id: int
    new_position: int = Field(..., ge=1)
    reason: Optional[str] = None


class BulkMoveRequest(BaseModel):
    """Request to move multiple items"""

    moves: List[Dict[str, int]]  # [{"item_id": 1, "new_position": 5}, ...]
    reason: Optional[str] = None


class TransferItemRequest(BaseModel):
    """Request to transfer item between queues"""

    item_id: int
    target_queue_id: int
    maintain_priority: bool = True
    reason: Optional[str] = None


class ExpediteItemRequest(BaseModel):
    """Request to expedite an item"""

    item_id: int
    priority_boost: int = Field(10, ge=1, le=50)
    move_to_front: bool = False
    reason: str


class HoldItemRequest(BaseModel):
    """Request to hold an item"""

    item_id: int
    hold_until: Optional[datetime] = None
    hold_minutes: Optional[int] = Field(None, ge=1, le=1440)  # Max 24 hours
    reason: str

    @field_validator("hold_until")
    def validate_hold(cls, v, info):
        if v is None and info.data.get("hold_minutes") is None:
            raise ValueError("Either hold_until or hold_minutes must be provided")
        return v


class BatchStatusUpdateRequest(BaseModel):
    """Request to update status of multiple items"""

    item_ids: List[int]
    new_status: QueueItemStatus
    reason: Optional[str] = None


# Queue Analytics Schemas
class QueueMetricsRequest(BaseModel):
    """Request for queue metrics"""

    queue_id: Optional[int] = None
    start_date: datetime
    end_date: datetime
    granularity: str = Field("hour", pattern="^(hour|day|week|month)$")


class QueueMetricsResponse(BaseModel):
    """Queue performance metrics"""

    queue_id: int
    queue_name: str
    period: Dict[str, datetime]
    volume: Dict[str, int]  # items_queued, completed, cancelled, delayed
    timing: Dict[str, float]  # avg_wait, max_wait, min_wait, avg_prep
    performance: Dict[str, float]  # on_time_percentage, etc.
    capacity: Dict[str, Any]  # utilization metrics


class QueueStatusSummary(BaseModel):
    """Current queue status summary"""

    queue_id: int
    queue_name: str
    status: QueueStatus
    current_size: int
    active_items: int
    ready_items: int
    on_hold_items: int
    avg_wait_time: float
    longest_wait_time: float
    next_ready_time: Optional[datetime]
    staff_assigned: int
    capacity_percentage: float


# Sequence Rule Schemas
class SequenceRuleBase(BaseModel):
    """Base schema for sequence rules"""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: bool = True
    priority: int = Field(0, ge=0)
    conditions: Dict[str, Any]
    priority_adjustment: int = Field(0, ge=-50, le=50)
    sequence_adjustment: int = Field(0, ge=-10, le=10)
    auto_expedite: bool = False
    assign_to_station: Optional[int] = None


class SequenceRuleCreate(SequenceRuleBase):
    """Schema for creating sequence rule"""

    queue_id: int


class SequenceRuleUpdate(BaseModel):
    """Schema for updating sequence rule"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = Field(None, ge=0)
    conditions: Optional[Dict[str, Any]] = None
    priority_adjustment: Optional[int] = Field(None, ge=-50, le=50)
    sequence_adjustment: Optional[int] = Field(None, ge=-10, le=10)
    auto_expedite: Optional[bool] = None
    assign_to_station: Optional[int] = None


class SequenceRuleResponse(SequenceRuleBase):
    """Schema for sequence rule response"""

    id: int
    queue_id: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# Display Configuration Schemas
class DisplayConfigBase(BaseModel):
    """Base schema for display configuration"""

    name: str = Field(..., min_length=1, max_length=100)
    display_type: str = Field(..., pattern="^(customer|kitchen|pickup)$")
    queues_shown: List[int]
    layout: str = Field("grid", pattern="^(grid|list|board)$")
    items_per_page: int = Field(20, ge=5, le=100)
    refresh_interval: int = Field(30, ge=5, le=300)
    status_filter: List[QueueItemStatus] = []
    hide_completed_after: int = Field(300, ge=0)
    theme: str = Field("light", pattern="^(light|dark|auto)$")
    font_size: str = Field("medium", pattern="^(small|medium|large|xl)$")
    show_images: bool = True
    show_prep_time: bool = True
    show_customer_info: bool = False
    enable_sound: bool = True
    alert_new_item: bool = True
    alert_ready: bool = True
    alert_delayed: bool = True
    location: Optional[str] = None


class DisplayConfigCreate(DisplayConfigBase):
    """Schema for creating display config"""

    pass


class DisplayConfigResponse(DisplayConfigBase):
    """Schema for display config response"""

    id: int
    ip_address: Optional[str]
    last_active: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# WebSocket Messages
class QueueUpdateMessage(BaseModel):
    """WebSocket message for queue updates"""

    event_type: str  # item_added, item_updated, item_removed, queue_updated
    queue_id: int
    item_id: Optional[int] = None
    data: Dict[str, Any]
    timestamp: datetime


class QueueSubscriptionRequest(BaseModel):
    """Request to subscribe to queue updates"""

    queue_ids: List[int]
    event_types: List[str] = ["all"]
    include_metrics: bool = False
