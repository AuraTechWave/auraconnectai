# backend/modules/reservations/schemas/reservation_schemas.py

"""
Pydantic schemas for reservation system.
"""

from pydantic import BaseModel, Field, validator, field_validator
from datetime import date, time, datetime
from typing import Optional, List, Dict
from enum import Enum


class ReservationStatus(str, Enum):
    """Reservation status enum for schemas"""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    SEATED = "seated"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    WAITLIST_CONVERTED = "waitlist_converted"


class WaitlistStatus(str, Enum):
    """Waitlist status enum for schemas"""

    WAITING = "waiting"
    NOTIFIED = "notified"
    CONFIRMED = "confirmed"
    CONVERTED = "converted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class NotificationMethod(str, Enum):
    """Notification method enum for schemas"""

    EMAIL = "email"
    SMS = "sms"
    BOTH = "both"
    NONE = "none"


class TimeSlot(BaseModel):
    """Time slot for availability"""

    time: time
    available: bool
    capacity_remaining: int
    waitlist_count: int = 0


class ReservationBase(BaseModel):
    """Base reservation schema"""

    reservation_date: date
    reservation_time: time
    party_size: int = Field(..., ge=1, le=20)
    duration_minutes: Optional[int] = Field(90, ge=30, le=240)
    special_requests: Optional[str] = Field(None, max_length=500)
    dietary_restrictions: Optional[List[str]] = []
    occasion: Optional[str] = Field(None, max_length=100)
    notification_method: Optional[NotificationMethod] = NotificationMethod.EMAIL


class ReservationCreate(ReservationBase):
    """Schema for creating a new reservation"""

    source: Optional[str] = "website"

    @field_validator("reservation_date")
    @classmethod
    def validate_date(cls, v):
        if v < date.today():
            raise ValueError("Reservation date cannot be in the past")
        return v

    @field_validator("reservation_time")
    @classmethod
    def validate_time(cls, v):
        # Basic validation - actual hours checked against settings
        if v < time(0, 0) or v > time(23, 59):
            raise ValueError("Invalid time")
        return v


class ReservationUpdate(BaseModel):
    """Schema for updating a reservation"""

    reservation_date: Optional[date] = None
    reservation_time: Optional[time] = None
    party_size: Optional[int] = Field(None, ge=1, le=20)
    special_requests: Optional[str] = Field(None, max_length=500)
    dietary_restrictions: Optional[List[str]] = None
    occasion: Optional[str] = Field(None, max_length=100)
    notification_method: Optional[NotificationMethod] = None


class ReservationResponse(BaseModel):
    """Schema for reservation response"""

    id: int
    customer_id: int
    reservation_date: date
    reservation_time: time
    party_size: int
    duration_minutes: int
    status: ReservationStatus
    confirmation_code: str
    source: str

    # Table assignment
    table_numbers: Optional[str] = None

    # Customer info
    customer_name: str
    customer_email: str
    customer_phone: Optional[str] = None

    # Preferences
    special_requests: Optional[str] = None
    dietary_restrictions: List[str] = []
    occasion: Optional[str] = None
    notification_method: NotificationMethod

    # Status flags
    reminder_sent: bool = False
    converted_from_waitlist: bool = False

    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    seated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    # Cancellation info
    cancellation_reason: Optional[str] = None
    cancelled_by: Optional[str] = None

    class Config:
        from_attributes = True


class ReservationListResponse(BaseModel):
    """Schema for list of reservations"""

    reservations: List[ReservationResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool


class TableAvailability(BaseModel):
    """Table availability for a time slot"""

    table_number: str
    section: str
    capacity: int
    features: List[str] = []
    is_available: bool


class ReservationAvailability(BaseModel):
    """Schema for checking reservation availability"""

    date: date
    party_size: int
    time_slots: List[TimeSlot]
    available_tables: List[TableAvailability] = []
    is_fully_booked: bool = False
    waitlist_available: bool = True
    special_date_info: Optional[Dict] = None


class ReservationCancellation(BaseModel):
    """Schema for cancelling a reservation"""

    reason: str = Field(..., min_length=1, max_length=500)
    cancelled_by: str = "customer"  # customer, staff, system


class ReservationConfirmation(BaseModel):
    """Schema for confirming a reservation"""

    confirmed: bool = True
    special_requests_update: Optional[str] = None


class WaitlistBase(BaseModel):
    """Base waitlist schema"""

    requested_date: date
    requested_time_start: time
    requested_time_end: time
    party_size: int = Field(..., ge=1, le=20)
    flexible_date: bool = False
    flexible_time: bool = False
    alternative_dates: Optional[List[date]] = []
    special_requests: Optional[str] = Field(None, max_length=500)
    notification_method: NotificationMethod = NotificationMethod.EMAIL


class WaitlistCreate(WaitlistBase):
    """Schema for creating waitlist entry"""

    @field_validator("requested_date")
    @classmethod
    def validate_date(cls, v):
        if v < date.today():
            raise ValueError("Requested date cannot be in the past")
        return v

    @field_validator("alternative_dates")
    @classmethod
    def validate_alternative_dates(cls, v):
        if v:
            for alt_date in v:
                if alt_date < date.today():
                    raise ValueError("Alternative dates cannot be in the past")
        return v


class WaitlistResponse(BaseModel):
    """Schema for waitlist response"""

    id: int
    customer_id: int
    requested_date: date
    requested_time_start: time
    requested_time_end: time
    party_size: int

    # Flexibility
    flexible_date: bool
    flexible_time: bool
    alternative_dates: List[date]

    # Status
    status: WaitlistStatus
    position: Optional[int] = None
    estimated_wait_time: Optional[int] = None  # in minutes

    # Customer info
    customer_name: str
    customer_email: str
    customer_phone: Optional[str] = None

    # Notification
    notification_method: NotificationMethod
    notified_at: Optional[datetime] = None
    notification_expires_at: Optional[datetime] = None

    # Other
    special_requests: Optional[str] = None
    priority: int = 0

    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WaitlistListResponse(BaseModel):
    """Schema for list of waitlist entries"""

    waitlist_entries: List[WaitlistResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool


class ReservationSettingsResponse(BaseModel):
    """Schema for reservation settings"""

    advance_booking_days: int
    min_advance_hours: int
    max_party_size: int
    min_party_size: int
    slot_duration_minutes: int
    default_reservation_duration: int
    operating_hours: Dict[str, Dict[str, str]]
    total_capacity: int
    waitlist_enabled: bool
    require_confirmation: bool
    send_reminders: bool

    class Config:
        from_attributes = True


class StaffReservationUpdate(BaseModel):
    """Schema for staff updating reservations"""

    status: Optional[ReservationStatus] = None
    table_numbers: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=500)
