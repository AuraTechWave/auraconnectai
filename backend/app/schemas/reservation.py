from pydantic import BaseModel, Field, field_validator
from datetime import date, time, datetime
from typing import Optional
from enum import Enum


class ReservationStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SEATED = "seated"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class ReservationBase(BaseModel):
    reservation_date: date
    reservation_time: time
    party_size: int = Field(..., ge=1, le=20)
    special_requests: Optional[str] = None


class ReservationCreate(ReservationBase):
    """Schema for creating a new reservation"""
    
    @field_validator('reservation_date', mode="after")
    def validate_date(cls, v):
        if v < date.today():
            raise ValueError('Reservation date cannot be in the past')
        # Maximum 90 days in advance
        if v > date.today().replace(day=date.today().day + 90):
            raise ValueError('Reservations can only be made up to 90 days in advance')
        return v
    
    @field_validator('reservation_time', mode="after")
    def validate_time(cls, v, values):
        # Restaurant hours: 11 AM to 10 PM
        if v < time(11, 0) or v > time(21, 30):
            raise ValueError('Reservations must be between 11:00 AM and 9:30 PM')
        return v


class ReservationUpdate(BaseModel):
    """Schema for updating a reservation"""
    reservation_date: Optional[date] = None
    reservation_time: Optional[time] = None
    party_size: Optional[int] = Field(None, ge=1, le=20)
    special_requests: Optional[str] = None
    status: Optional[ReservationStatus] = None


class ReservationInDB(ReservationBase):
    """Schema for reservation in database"""
    id: int
    customer_id: int
    status: ReservationStatus
    table_number: Optional[str] = None
    confirmation_code: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReservationResponse(ReservationInDB):
    """Schema for reservation response"""
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None


class ReservationListResponse(BaseModel):
    """Schema for list of reservations"""
    reservations: list[ReservationResponse]
    total: int
    page: int
    page_size: int


class ReservationAvailability(BaseModel):
    """Schema for checking reservation availability"""
    date: date
    available_times: list[time]
    is_fully_booked: bool = False


class ReservationCancellation(BaseModel):
    """Schema for cancelling a reservation"""
    reason: Optional[str] = None
    cancelled_by: str = "customer"  # customer, staff, system