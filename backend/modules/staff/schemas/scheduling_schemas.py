from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict
from datetime import date, datetime, time, timezone
from enum import Enum

from ..enums.scheduling_enums import ShiftStatus, SwapStatus, ShiftType, RecurrenceType, DayOfWeek, AvailabilityStatus, BreakType


class ShiftTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    role_id: int
    location_id: int
    start_time: time
    end_time: time
    days_of_week: List[int] = Field(..., min_items=1, max_items=7)  # 0=Monday, 6=Sunday
    is_active: bool = True
    min_staff: int = Field(1, ge=1)
    max_staff: int = Field(1, ge=1)
    hourly_rate: Optional[float] = None
    description: Optional[str] = None

    @validator('end_time')
    def validate_end_time(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('End time must be after start time')
        return v

    @validator('max_staff')
    def validate_max_staff(cls, v, values):
        if 'min_staff' in values and v < values['min_staff']:
            raise ValueError('Max staff cannot be less than min staff')
        return v


class ShiftTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    role_id: Optional[int] = None
    location_id: Optional[int] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    days_of_week: Optional[List[int]] = Field(None, min_items=1, max_items=7)
    is_active: Optional[bool] = None
    min_staff: Optional[int] = Field(None, ge=1)
    max_staff: Optional[int] = Field(None, ge=1)
    hourly_rate: Optional[float] = None
    description: Optional[str] = None


class ShiftTemplateResponse(BaseModel):
    id: int
    name: str
    role_id: int
    location_id: int
    start_time: time
    end_time: time
    days_of_week: List[int]
    is_active: bool
    min_staff: int
    max_staff: int
    hourly_rate: Optional[float]
    description: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True


class ShiftCreate(BaseModel):
    staff_id: int
    role_id: int
    location_id: int
    date: date
    start_time: time
    end_time: time
    status: ShiftStatus = ShiftStatus.DRAFT
    hourly_rate: Optional[float] = None
    notes: Optional[str] = None
    template_id: Optional[int] = None

    @validator('end_time')
    def validate_end_time(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('End time must be after start time')
        return v


class ShiftUpdate(BaseModel):
    staff_id: Optional[int] = None
    role_id: Optional[int] = None
    location_id: Optional[int] = None
    date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    status: Optional[ShiftStatus] = None
    hourly_rate: Optional[float] = None
    notes: Optional[str] = None


class ShiftResponse(BaseModel):
    id: int
    staff_id: int
    role_id: int
    location_id: int
    date: date
    start_time: time
    end_time: time
    status: ShiftStatus
    hourly_rate: Optional[float]
    notes: Optional[str]
    template_id: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]
    published_at: Optional[datetime]
    estimated_cost: Optional[float]

    class Config:
        orm_mode = True


class ShiftBreakCreate(BaseModel):
    shift_id: int
    start_time: time
    end_time: time
    break_type: str = "lunch"  # lunch, rest, other
    is_paid: bool = False
    notes: Optional[str] = None

    @validator('end_time')
    def validate_end_time(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('Break end time must be after start time')
        return v


class ShiftBreakResponse(BaseModel):
    id: int
    shift_id: int
    start_time: time
    end_time: time
    break_type: str
    is_paid: bool
    notes: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True


class AvailabilityCreate(BaseModel):
    staff_id: int
    day_of_week: int = Field(..., ge=0, le=6)  # 0=Monday, 6=Sunday
    start_time: time
    end_time: time
    is_available: bool = True
    priority: int = Field(1, ge=1, le=5)  # 1=lowest, 5=highest
    notes: Optional[str] = None

    @validator('end_time')
    def validate_end_time(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('End time must be after start time')
        return v


class AvailabilityUpdate(BaseModel):
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_available: Optional[bool] = None
    priority: Optional[int] = Field(None, ge=1, le=5)
    notes: Optional[str] = None


class AvailabilityResponse(BaseModel):
    id: int
    staff_id: int
    day_of_week: int
    start_time: time
    end_time: time
    is_available: bool
    priority: int
    notes: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True


class ShiftSwapRequest(BaseModel):
    from_shift_id: int = Field(..., gt=0, description="ID of the shift to swap from")
    to_shift_id: Optional[int] = Field(None, gt=0, description="ID of the shift to swap with")
    to_staff_id: Optional[int] = Field(None, gt=0, description="ID of the staff to assign shift to")
    reason: str = Field(..., min_length=1, max_length=500)
    urgency: Optional[str] = Field("normal", regex="^(urgent|normal|flexible)$", description="Urgency level of swap request")
    preferred_dates: Optional[List[date]] = None
    preferred_response_by: Optional[datetime] = None
    
    @validator('from_shift_id')
    def validate_from_shift_id(cls, v):
        if v <= 0:
            raise ValueError('from_shift_id must be a positive integer')
        return v
    
    @validator('to_shift_id')
    def validate_to_shift_id(cls, v):
        if v is not None and v <= 0:
            raise ValueError('to_shift_id must be a positive integer')
        return v
    
    @validator('to_staff_id')
    def validate_to_staff_id(cls, v):
        if v is not None and v <= 0:
            raise ValueError('to_staff_id must be a positive integer')
        return v
    
    @validator('to_staff_id')
    def validate_swap_target(cls, v, values):
        # Check if both are None or both are set
        to_shift_id = values.get('to_shift_id')
        if v is None and to_shift_id is None:
            raise ValueError('Must specify either to_shift_id or to_staff_id')
        if v is not None and to_shift_id is not None:
            raise ValueError('Cannot specify both to_shift_id and to_staff_id')
        return v
    
    @validator('preferred_response_by')
    def validate_response_deadline(cls, v):
        if v is not None and v <= datetime.now(timezone.utc):
            raise ValueError('preferred_response_by must be in the future')
        return v


class ShiftSwapApproval(BaseModel):
    swap_id: int
    status: SwapStatus
    manager_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    alternative_shift_id: Optional[int] = None


class ShiftSwapResponse(BaseModel):
    id: int
    requester_id: int
    requester_name: str
    from_shift_id: int
    from_shift_details: Dict
    to_shift_id: Optional[int]
    to_shift_details: Optional[Dict]
    to_staff_id: Optional[int]
    to_staff_name: Optional[str]
    status: SwapStatus
    reason: Optional[str]
    manager_notes: Optional[str]
    rejection_reason: Optional[str]
    approved_by_id: Optional[int]
    approved_by_name: Optional[str]
    approved_at: Optional[datetime]
    approval_level: Optional[str]
    auto_approval_eligible: bool
    auto_approval_reason: Optional[str]
    response_deadline: Optional[datetime]
    requester_notified: bool
    to_staff_notified: bool
    manager_notified: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


class ShiftSwapListFilter(BaseModel):
    status: Optional[SwapStatus] = None
    requester_id: Optional[int] = None
    staff_id: Optional[int] = None  # Shows swaps where user is requester or target
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    pending_approval: Optional[bool] = None
    
    
class SwapApprovalRuleCreate(BaseModel):
    rule_name: str
    is_active: bool = True
    priority: int = 0
    max_hours_difference: Optional[float] = None
    same_role_required: bool = True
    same_location_required: bool = True
    min_advance_notice_hours: int = 24
    max_advance_notice_hours: Optional[int] = None
    min_tenure_days: int = 90
    max_swaps_per_month: int = 3
    no_recent_violations: bool = True
    performance_rating_min: Optional[float] = None
    blackout_dates: List[date] = []
    restricted_shifts: List[str] = []
    peak_hours_restricted: bool = False
    requires_manager_approval: bool = True
    requires_both_staff_consent: bool = True
    approval_timeout_hours: int = 48


class SwapApprovalRuleUpdate(BaseModel):
    rule_name: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None
    max_hours_difference: Optional[float] = None
    same_role_required: Optional[bool] = None
    same_location_required: Optional[bool] = None
    min_advance_notice_hours: Optional[int] = None
    max_advance_notice_hours: Optional[int] = None
    min_tenure_days: Optional[int] = None
    max_swaps_per_month: Optional[int] = None
    no_recent_violations: Optional[bool] = None
    performance_rating_min: Optional[float] = None
    blackout_dates: Optional[List[date]] = None
    restricted_shifts: Optional[List[str]] = None
    peak_hours_restricted: Optional[bool] = None
    requires_manager_approval: Optional[bool] = None
    requires_both_staff_consent: Optional[bool] = None
    approval_timeout_hours: Optional[int] = None


class SwapApprovalRuleResponse(BaseModel):
    id: int
    restaurant_id: int
    rule_name: str
    is_active: bool
    priority: int
    max_hours_difference: Optional[float]
    same_role_required: bool
    same_location_required: bool
    min_advance_notice_hours: int
    max_advance_notice_hours: Optional[int]
    min_tenure_days: int
    max_swaps_per_month: int
    no_recent_violations: bool
    performance_rating_min: Optional[float]
    blackout_dates: List[date]
    restricted_shifts: List[str]
    peak_hours_restricted: bool
    requires_manager_approval: bool
    requires_both_staff_consent: bool
    approval_timeout_hours: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


class ShiftSwapHistory(BaseModel):
    total_swaps: int
    approved_swaps: int
    rejected_swaps: int
    pending_swaps: int
    cancelled_swaps: int
    average_approval_time_hours: Optional[float]
    most_common_reasons: List[Dict[str, Any]]
    swap_trends: List[Dict[str, Any]]


# Schedule Generation Schemas
class ScheduleGenerationRequest(BaseModel):
    start_date: date
    end_date: date
    location_id: int
    use_templates: bool = True
    auto_assign: bool = False
    respect_availability: bool = True
    max_hours_per_week: float = 40
    min_hours_between_shifts: int = 8
    use_historical_demand: bool = False
    demand_lookback_days: int = 90
    buffer_percentage: float = 10.0
    use_flexible_shifts: bool = False
    min_shift_hours: int = 4
    max_shift_hours: int = 8
    

class SchedulePublishRequest(BaseModel):
    start_date: date
    end_date: date
    send_notifications: bool = True
    notes: Optional[str] = None


class SchedulePublishResponse(BaseModel):
    id: int
    start_date: date
    end_date: date
    published_by_id: int
    published_at: datetime
    notifications_sent: bool
    notification_count: int
    total_shifts: int
    total_hours: float
    estimated_labor_cost: float
    notes: Optional[str]
    
    class Config:
        orm_mode = True


# Dashboard Analytics Schemas
class StaffingAnalytics(BaseModel):
    date: date
    location_id: int
    scheduled_staff: int
    required_staff: int
    coverage_percentage: float
    estimated_labor_cost: float
    shifts_by_role: Dict[str, int]
    

class StaffScheduleSummary(BaseModel):
    staff_id: int
    staff_name: str
    week_start: date
    total_shifts: int
    total_hours: float
    overtime_hours: float
    availability_compliance: float
    estimated_earnings: float


# Conflict Detection Schema
class ScheduleConflict(BaseModel):
    conflict_type: str  # "overlap", "insufficient_rest", "availability", "max_hours"
    severity: str  # "error", "warning"
    shift_ids: List[int]
    description: str
    resolution_suggestions: List[str]


# Update forward references
ShiftResponse.update_forward_refs()