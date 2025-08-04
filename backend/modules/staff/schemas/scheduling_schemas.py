from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from datetime import datetime, date, time
from ..enums.scheduling_enums import ShiftStatus, ShiftType, RecurrenceType, DayOfWeek, AvailabilityStatus, SwapStatus, BreakType


# Shift Template Schemas
class ShiftTemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    role_id: Optional[int] = None
    location_id: int
    start_time: time
    end_time: time
    recurrence_type: RecurrenceType = RecurrenceType.NONE
    recurrence_days: Optional[List[DayOfWeek]] = None
    min_staff: int = 1
    max_staff: Optional[int] = None
    preferred_staff: Optional[int] = None
    estimated_hourly_rate: Optional[float] = None
    

class ShiftTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    role_id: Optional[int] = None
    location_id: Optional[int] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    recurrence_type: Optional[RecurrenceType] = None
    recurrence_days: Optional[List[DayOfWeek]] = None
    min_staff: Optional[int] = None
    max_staff: Optional[int] = None
    preferred_staff: Optional[int] = None
    estimated_hourly_rate: Optional[float] = None
    is_active: Optional[bool] = None


class ShiftTemplateResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    role_id: Optional[int]
    location_id: int
    start_time: time
    end_time: time
    recurrence_type: RecurrenceType
    recurrence_days: Optional[List[DayOfWeek]]
    min_staff: int
    max_staff: Optional[int]
    preferred_staff: Optional[int]
    estimated_hourly_rate: Optional[float]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


# Enhanced Shift Schemas
class ShiftCreate(BaseModel):
    staff_id: int
    role_id: Optional[int] = None
    location_id: int
    date: date
    start_time: datetime
    end_time: datetime
    shift_type: ShiftType = ShiftType.REGULAR
    template_id: Optional[int] = None
    hourly_rate: Optional[float] = None
    notes: Optional[str] = None
    color: Optional[str] = None
    
    @validator('end_time')
    def validate_times(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('End time must be after start time')
        return v


class ShiftUpdate(BaseModel):
    staff_id: Optional[int] = None
    role_id: Optional[int] = None
    location_id: Optional[int] = None
    date: Optional[date] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    shift_type: Optional[ShiftType] = None
    status: Optional[ShiftStatus] = None
    hourly_rate: Optional[float] = None
    notes: Optional[str] = None
    color: Optional[str] = None


class ShiftResponse(BaseModel):
    id: int
    staff_id: int
    staff_name: Optional[str]
    role_id: Optional[int]
    role_name: Optional[str]
    location_id: int
    date: date
    start_time: datetime
    end_time: datetime
    shift_type: ShiftType
    status: ShiftStatus
    template_id: Optional[int]
    hourly_rate: Optional[float]
    estimated_cost: Optional[float]
    actual_cost: Optional[float]
    notes: Optional[str]
    color: Optional[str]
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime]
    breaks: List['ShiftBreakResponse'] = []
    
    class Config:
        orm_mode = True


# Break Schemas
class ShiftBreakCreate(BaseModel):
    shift_id: int
    break_type: BreakType
    start_time: datetime
    end_time: datetime
    is_paid: bool = False
    
    @validator('end_time')
    def validate_break_times(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('Break end time must be after start time')
        return v


class ShiftBreakResponse(BaseModel):
    id: int
    shift_id: int
    break_type: BreakType
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    is_paid: bool
    
    class Config:
        orm_mode = True


# Availability Schemas
class AvailabilityCreate(BaseModel):
    staff_id: int
    day_of_week: Optional[DayOfWeek] = None
    specific_date: Optional[date] = None
    start_time: time
    end_time: time
    status: AvailabilityStatus = AvailabilityStatus.AVAILABLE
    max_hours_per_day: Optional[float] = None
    preferred_shifts: Optional[List[int]] = None
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None
    notes: Optional[str] = None
    
    @validator('specific_date')
    def validate_availability_type(cls, v, values):
        if v is not None and values.get('day_of_week') is not None:
            raise ValueError('Cannot specify both day_of_week and specific_date')
        if v is None and values.get('day_of_week') is None:
            raise ValueError('Must specify either day_of_week or specific_date')
        return v


class AvailabilityUpdate(BaseModel):
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    status: Optional[AvailabilityStatus] = None
    max_hours_per_day: Optional[float] = None
    preferred_shifts: Optional[List[int]] = None
    effective_until: Optional[datetime] = None
    notes: Optional[str] = None


class AvailabilityResponse(BaseModel):
    id: int
    staff_id: int
    staff_name: Optional[str]
    day_of_week: Optional[DayOfWeek]
    specific_date: Optional[date]
    start_time: time
    end_time: time
    status: AvailabilityStatus
    max_hours_per_day: Optional[float]
    preferred_shifts: Optional[List[int]]
    effective_from: datetime
    effective_until: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


# Shift Swap Schemas
class ShiftSwapRequest(BaseModel):
    from_shift_id: int
    to_shift_id: Optional[int] = None
    to_staff_id: Optional[int] = None
    reason: Optional[str] = None
    
    @validator('to_staff_id')
    def validate_swap_target(cls, v, values):
        if v is None and values.get('to_shift_id') is None:
            raise ValueError('Must specify either to_shift_id or to_staff_id')
        return v


class ShiftSwapApproval(BaseModel):
    status: SwapStatus
    manager_notes: Optional[str] = None


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
    approved_by_id: Optional[int]
    approved_by_name: Optional[str]
    approved_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        orm_mode = True


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