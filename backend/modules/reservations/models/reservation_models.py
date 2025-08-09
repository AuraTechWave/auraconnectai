# backend/modules/reservations/models/reservation_models.py

"""
Enhanced reservation models with waitlist support and better tracking.
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Date, Time, Text, 
    Enum, Boolean, Float, JSON, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
import enum
from datetime import datetime


class ReservationStatus(enum.Enum):
    """Reservation status enum"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SEATED = "seated"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    WAITLIST_CONVERTED = "waitlist_converted"  # When waitlist converts to reservation


class WaitlistStatus(enum.Enum):
    """Waitlist status enum"""
    WAITING = "waiting"
    NOTIFIED = "notified"  # Customer has been notified of availability
    CONFIRMED = "confirmed"  # Customer confirmed they still want the table
    CONVERTED = "converted"  # Converted to actual reservation
    EXPIRED = "expired"  # Notification expired without response
    CANCELLED = "cancelled"


class NotificationMethod(enum.Enum):
    """Preferred notification method"""
    EMAIL = "email"
    SMS = "sms"
    BOTH = "both"
    NONE = "none"


class Reservation(Base):
    """Enhanced reservation model with better tracking and features"""
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    
    # Reservation details
    reservation_date = Column(Date, nullable=False, index=True)
    reservation_time = Column(Time, nullable=False, index=True)
    party_size = Column(Integer, nullable=False)
    duration_minutes = Column(Integer, default=90)  # Expected duration
    
    # Status and tracking
    status = Column(Enum(ReservationStatus), default=ReservationStatus.PENDING, index=True)
    confirmation_code = Column(String(10), unique=True, index=True)
    source = Column(String(50), default="website")  # website, phone, walk-in, waitlist
    
    # Table assignment
    table_ids = Column(JSON, default=list)  # List of assigned table IDs
    table_numbers = Column(String(100))  # Comma-separated table numbers for display
    
    # Customer preferences
    special_requests = Column(Text)
    dietary_restrictions = Column(JSON, default=list)
    occasion = Column(String(100))  # birthday, anniversary, business, etc.
    
    # Notification preferences
    notification_method = Column(Enum(NotificationMethod), default=NotificationMethod.EMAIL)
    reminder_sent = Column(Boolean, default=False)
    reminder_sent_at = Column(DateTime(timezone=True))
    
    # Waitlist conversion
    waitlist_id = Column(Integer, ForeignKey("waitlist_entries.id"))
    converted_from_waitlist = Column(Boolean, default=False)
    
    # Cancellation info
    cancelled_at = Column(DateTime(timezone=True))
    cancellation_reason = Column(Text)
    cancelled_by = Column(String(50))  # customer, staff, system
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    confirmed_at = Column(DateTime(timezone=True))
    seated_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # Audit tracking
    created_by = Column(Integer, ForeignKey("users.id"))
    updated_by = Column(Integer, ForeignKey("users.id"))
    confirmed_by = Column(Integer, ForeignKey("users.id"))
    seated_by = Column(Integer, ForeignKey("users.id"))
    completed_by = Column(Integer, ForeignKey("users.id"))
    
    # Relationships
    customer = relationship("Customer", back_populates="reservations")
    waitlist_entry = relationship("Waitlist", back_populates="reservation", uselist=False)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_reservation_date_time', 'reservation_date', 'reservation_time'),
        Index('idx_reservation_customer_date', 'customer_id', 'reservation_date'),
        Index('idx_reservation_status_date', 'status', 'reservation_date'),
    )

    def __repr__(self):
        return f"<Reservation {self.id} - {self.customer_id} on {self.reservation_date} at {self.reservation_time}>"


class Waitlist(Base):
    """Waitlist entries for when reservations are full"""
    __tablename__ = "waitlist_entries"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    
    # Requested details
    requested_date = Column(Date, nullable=False, index=True)
    requested_time_start = Column(Time, nullable=False)
    requested_time_end = Column(Time, nullable=False)
    party_size = Column(Integer, nullable=False)
    
    # Flexibility options
    flexible_date = Column(Boolean, default=False)
    flexible_time = Column(Boolean, default=False)
    alternative_dates = Column(JSON, default=list)  # List of alternative dates
    
    # Status tracking
    status = Column(Enum(WaitlistStatus), default=WaitlistStatus.WAITING, index=True)
    position = Column(Integer)  # Position in waitlist
    
    # Notification details
    notification_method = Column(Enum(NotificationMethod), default=NotificationMethod.EMAIL)
    notified_at = Column(DateTime(timezone=True))
    notification_expires_at = Column(DateTime(timezone=True))
    confirmed_at = Column(DateTime(timezone=True))
    
    # Special requests
    special_requests = Column(Text)
    priority = Column(Integer, default=0)  # Higher priority for VIP customers
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    expires_at = Column(DateTime(timezone=True))  # When the waitlist entry expires
    
    # Relationships
    customer = relationship("Customer", back_populates="waitlist_entries")
    reservation = relationship("Reservation", back_populates="waitlist_entry", uselist=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_waitlist_date_status', 'requested_date', 'status'),
        Index('idx_waitlist_customer_status', 'customer_id', 'status'),
    )


class ReservationSettings(Base):
    """Restaurant-wide reservation settings"""
    __tablename__ = "reservation_settings"

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, default=1)  # For multi-tenant support
    
    # Booking rules
    advance_booking_days = Column(Integer, default=90)  # How far in advance
    min_advance_hours = Column(Integer, default=2)  # Minimum hours before reservation
    min_advance_minutes = Column(Integer, default=10)  # Cutoff time in minutes
    max_party_size = Column(Integer, default=20)
    min_party_size = Column(Integer, default=1)
    
    # Time slots
    slot_duration_minutes = Column(Integer, default=15)  # 15, 30, 60 minute slots
    default_reservation_duration = Column(Integer, default=90)  # Default duration
    
    # Operating hours (stored as JSON for flexibility)
    operating_hours = Column(JSON, default={
        "monday": {"open": "11:00", "close": "22:00"},
        "tuesday": {"open": "11:00", "close": "22:00"},
        "wednesday": {"open": "11:00", "close": "22:00"},
        "thursday": {"open": "11:00", "close": "22:00"},
        "friday": {"open": "11:00", "close": "23:00"},
        "saturday": {"open": "10:00", "close": "23:00"},
        "sunday": {"open": "10:00", "close": "21:00"}
    })
    
    # Capacity management
    total_capacity = Column(Integer, default=100)
    buffer_percentage = Column(Float, default=0.1)  # Keep 10% capacity as buffer
    
    # Waitlist settings
    waitlist_enabled = Column(Boolean, default=True)
    waitlist_notification_window = Column(Integer, default=30)  # Minutes to respond
    waitlist_auto_expire_hours = Column(Integer, default=24)
    
    # Confirmation settings
    require_confirmation = Column(Boolean, default=True)
    confirmation_required_hours = Column(Integer, default=24)  # Confirm 24h before
    auto_cancel_unconfirmed = Column(Boolean, default=False)
    
    # Reminder settings
    send_reminders = Column(Boolean, default=True)
    reminder_hours_before = Column(Integer, default=24)
    
    # No-show policy
    track_no_shows = Column(Boolean, default=True)
    no_show_threshold = Column(Integer, default=3)  # Block after 3 no-shows
    
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class TableConfiguration(Base):
    """Table configuration for capacity planning"""
    __tablename__ = "table_configurations"

    id = Column(Integer, primary_key=True)
    table_number = Column(String(20), unique=True, nullable=False)
    section = Column(String(50))  # main, patio, private, bar
    
    # Capacity
    min_capacity = Column(Integer, nullable=False)
    max_capacity = Column(Integer, nullable=False)
    preferred_capacity = Column(Integer)
    
    # Features
    is_combinable = Column(Boolean, default=True)  # Can be combined with adjacent tables
    combine_with = Column(JSON, default=list)  # List of table numbers it can combine with
    
    # Availability
    is_active = Column(Boolean, default=True)
    available_for_reservation = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # Higher priority tables assigned first
    
    # Special features
    features = Column(JSON, default=list)  # ["window", "booth", "high-chair", "wheelchair"]
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class SpecialDate(Base):
    """Special dates with modified availability or rules"""
    __tablename__ = "special_dates"

    id = Column(Integer, primary_key=True)
    date = Column(Date, unique=True, nullable=False, index=True)
    name = Column(String(100))  # "Valentine's Day", "New Year's Eve"
    
    # Modified hours
    is_closed = Column(Boolean, default=False)
    special_hours = Column(JSON)  # {"open": "17:00", "close": "23:00"}
    
    # Modified rules
    min_party_size = Column(Integer)
    max_party_size = Column(Integer)
    require_deposit = Column(Boolean, default=False)
    deposit_amount = Column(Float)
    
    # Capacity modifications
    capacity_modifier = Column(Float, default=1.0)  # 0.8 = 80% capacity
    
    # Special menu or pricing
    special_menu = Column(Boolean, default=False)
    price_modifier = Column(Float, default=1.0)  # 1.5 = 150% pricing
    
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ScheduledReminder(Base):
    """Scheduled reminders for reservations"""
    __tablename__ = "scheduled_reminders"

    id = Column(Integer, primary_key=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=False)
    
    # Scheduling
    scheduled_for = Column(DateTime(timezone=True), nullable=False, index=True)
    reminder_type = Column(String(50))  # reservation_reminder, confirmation_reminder
    
    # Status tracking
    status = Column(String(20), default="pending")  # pending, sent, failed, skipped
    sent_at = Column(DateTime(timezone=True))
    
    # Additional data
    reminder_data = Column(JSON)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    reservation = relationship("Reservation", backref="scheduled_reminders")
    
    # Index for efficient querying
    __table_args__ = (
        Index('idx_scheduled_reminders_status_scheduled', 'status', 'scheduled_for'),
    )