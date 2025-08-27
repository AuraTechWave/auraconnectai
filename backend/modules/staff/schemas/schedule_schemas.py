# backend/modules/staff/schemas/schedule_schemas.py

from pydantic import BaseModel, Field, validator, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date, time

# Import existing schemas we can reuse
from .scheduling_schemas import SchedulePublishRequest as BaseSchedulePublishRequest


# Schedule Preview Schemas
class SchedulePreviewResponse(BaseModel):
    """Response schema for schedule preview"""

    date_range: Dict[str, str]  # {start: "2023-01-01", end: "2023-01-07"}
    total_shifts: int
    by_date: Dict[str, List[Dict[str, Any]]]  # Date -> list of shifts
    by_staff: List[Dict[str, Any]]  # List of staff with their shifts
    summary: Dict[str, Any]  # Summary statistics

    class Config:
        from_attributes = True


class PaginatedPreviewResponse(BaseModel):
    """Paginated response for schedule preview"""

    items: List[Dict[str, Any]]
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool

    class Config:
        from_attributes = True


# Enhanced Schedule Publish Request
class SchedulePublishRequest(BaseSchedulePublishRequest):
    """Extended schedule publish request with notification channels"""

    notification_channels: Optional[List[str]] = ["email", "in_app"]

    @field_validator("notification_channels")
    @classmethod
    def validate_channels(cls, v):
        if v:
            valid_channels = ["email", "sms", "push", "in_app"]
            for channel in v:
                if channel not in valid_channels:
                    raise ValueError(f"Invalid notification channel: {channel}")
        return v


# Schedule CRUD Schemas
class ScheduleCreateRequest(BaseModel):
    """Request schema for creating a schedule/shift"""

    staff_id: int
    date: date
    start_time: time
    end_time: time
    break_duration: Optional[int] = Field(0, description="Break duration in minutes")
    notes: Optional[str] = None

    @field_validator("end_time")
    @classmethod
    def validate_times(cls, v, values):
        if "start_time" in values and v <= values["start_time"]:
            # Allow overnight shifts
            pass
        return v

    @field_validator("break_duration")
    @classmethod
    def validate_break_duration(cls, v):
        if v and v < 0:
            raise ValueError("Break duration cannot be negative")
        return v


class ScheduleUpdateRequest(BaseModel):
    """Request schema for updating a schedule/shift"""

    start_time: Optional[time] = None
    end_time: Optional[time] = None
    break_duration: Optional[int] = None
    notes: Optional[str] = None

    @field_validator("break_duration")
    @classmethod
    def validate_break_duration(cls, v):
        if v is not None and v < 0:
            raise ValueError("Break duration cannot be negative")
        return v


class ScheduleResponse(BaseModel):
    """Response schema for schedule/shift"""

    id: int
    staff_id: int
    staff_name: str
    role: Optional[str]
    date: date
    start_time: time
    end_time: time
    total_hours: float
    break_duration: int
    notes: Optional[str]
    is_published: bool
    published_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Notification Schemas
class NotificationResult(BaseModel):
    """Result of notification sending"""

    success: bool
    total_staff: int
    notifications_sent: Dict[str, int]  # channel -> count
    errors: List[Dict[str, str]] = []


class ShiftReminderRequest(BaseModel):
    """Request for sending shift reminders"""

    restaurant_id: int
    hours_before: int = Field(
        2, ge=1, le=24, description="Hours before shift to send reminder"
    )


# Cache Management Schemas
class CacheWarmRequest(BaseModel):
    """Request to warm schedule cache"""

    week_start: date
    include_filters: Optional[List[Dict[str, Any]]] = None


class CacheStatsResponse(BaseModel):
    """Cache statistics response"""

    total_cached_previews: int
    cache_keys: List[str]
    oldest_cache: Optional[str]
    newest_cache: Optional[str]
    total_size_bytes: int
    hit_rate: Optional[float] = None

    class Config:
        from_attributes = True


# Analytics and Reporting Schemas
class ScheduleAnalytics(BaseModel):
    """Schedule analytics response"""

    period: Dict[str, str]  # start/end dates
    total_shifts: int
    total_hours: float
    average_shift_length: float
    staff_utilization: Dict[str, float]  # staff_id -> utilization %
    coverage_gaps: List[Dict[str, Any]]
    labor_cost_estimate: Optional[float]

    class Config:
        from_attributes = True


class StaffScheduleMetrics(BaseModel):
    """Individual staff schedule metrics"""

    staff_id: int
    staff_name: str
    period_start: date
    period_end: date
    total_shifts: int
    total_hours: float
    average_hours_per_shift: float
    longest_shift_hours: float
    days_worked: int
    overtime_hours: float
    utilization_percentage: float

    class Config:
        from_attributes = True


# Batch Operations
class BatchScheduleOperation(BaseModel):
    """Batch schedule operation request"""

    operation: str  # "create", "update", "delete", "publish"
    schedule_ids: Optional[List[int]] = None
    schedule_data: Optional[List[Dict[str, Any]]] = None
    parameters: Optional[Dict[str, Any]] = None


class BatchOperationResult(BaseModel):
    """Result of batch schedule operation"""

    operation: str
    total_processed: int
    successful: int
    failed: int
    errors: List[Dict[str, str]] = []
    results: List[Dict[str, Any]] = []
