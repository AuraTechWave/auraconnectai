from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Enum, Boolean, Time, JSON, Text, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import relationship
from core.database import Base
from datetime import datetime
from ..enums.scheduling_enums import ShiftStatus, ShiftType, RecurrenceType, DayOfWeek, AvailabilityStatus, SwapStatus, BreakType


class EnhancedShift(Base):
    __tablename__ = "enhanced_shifts"
    
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff_members.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"))
    location_id = Column(Integer, nullable=False)
    
    # Time details
    date = Column(DateTime, nullable=False, index=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    
    # Shift details
    shift_type = Column(Enum(ShiftType, values_callable=lambda obj: [e.value for e in obj], create_type=False), default=ShiftType.REGULAR)
    status = Column(Enum(ShiftStatus, values_callable=lambda obj: [e.value for e in obj], create_type=False), default=ShiftStatus.DRAFT)
    
    # Template reference
    template_id = Column(Integer, ForeignKey("shift_templates.id"))
    
    # Labor cost
    hourly_rate = Column(Float)
    estimated_cost = Column(Float)
    actual_cost = Column(Float)
    
    # Notes and metadata
    notes = Column(Text)
    color = Column(String)  # For UI display
    
    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by_id = Column(Integer, ForeignKey("staff_members.id"))
    published_at = Column(DateTime)
    
    # Relationships
    staff_member = relationship("StaffMember", foreign_keys=[staff_id], back_populates="scheduled_shifts")
    created_by = relationship("StaffMember", foreign_keys=[created_by_id])
    role = relationship("Role")
    template = relationship("ShiftTemplate", back_populates="shifts")
    breaks = relationship("ShiftBreak", back_populates="shift", cascade="all, delete-orphan")
    swap_requests_from = relationship("ShiftSwap", foreign_keys="ShiftSwap.from_shift_id", back_populates="from_shift")
    swap_requests_to = relationship("ShiftSwap", foreign_keys="ShiftSwap.to_shift_id", back_populates="to_shift")
    
    __table_args__ = (
        CheckConstraint('end_time > start_time', name='check_shift_times'),
    )


class ShiftTemplate(Base):
    __tablename__ = "shift_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    
    # Role and location
    role_id = Column(Integer, ForeignKey("roles.id"))
    location_id = Column(Integer)
    
    # Time pattern
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    
    # Recurrence
    recurrence_type = Column(Enum(RecurrenceType, values_callable=lambda obj: [e.value for e in obj], create_type=False), default=RecurrenceType.NONE)
    recurrence_days = Column(JSON)  # List of DayOfWeek values
    
    # Requirements
    min_staff = Column(Integer, default=1)
    max_staff = Column(Integer)
    preferred_staff = Column(Integer)
    
    # Labor cost estimates
    estimated_hourly_rate = Column(Float)
    
    # Active status
    is_active = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    role = relationship("Role")
    shifts = relationship("EnhancedShift", back_populates="template")
    requirements = relationship("ShiftRequirement", back_populates="template", cascade="all, delete-orphan")


class StaffAvailability(Base):
    __tablename__ = "staff_availability"
    
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff_members.id"), nullable=False)
    
    # Day of week or specific date
    day_of_week = Column(Enum(DayOfWeek, create_type=False))  # For recurring availability
    specific_date = Column(DateTime)  # For specific date availability
    
    # Time slots
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    
    # Availability type
    status = Column(Enum(AvailabilityStatus, create_type=False), default=AvailabilityStatus.AVAILABLE)
    
    # Preferences
    max_hours_per_day = Column(Float)
    preferred_shifts = Column(JSON)  # List of shift template IDs
    
    # Valid period
    effective_from = Column(DateTime, default=datetime.utcnow)
    effective_until = Column(DateTime)
    
    # Notes
    notes = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    staff_member = relationship("StaffMember", back_populates="availability")
    
    __table_args__ = (
        CheckConstraint('end_time > start_time', name='check_availability_times'),
        CheckConstraint('(day_of_week IS NOT NULL) != (specific_date IS NOT NULL)', name='check_availability_type'),
    )


class ShiftSwap(Base):
    __tablename__ = "shift_swaps"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Requester and shifts
    requester_id = Column(Integer, ForeignKey("staff_members.id"), nullable=False)
    from_shift_id = Column(Integer, ForeignKey("enhanced_shifts.id"), nullable=False)
    to_shift_id = Column(Integer, ForeignKey("enhanced_shifts.id"))
    to_staff_id = Column(Integer, ForeignKey("staff_members.id"))
    
    # Status
    status = Column(Enum(SwapStatus, create_type=False), default=SwapStatus.PENDING)
    
    # Approval
    approved_by_id = Column(Integer, ForeignKey("staff_members.id"))
    approved_at = Column(DateTime)
    
    # Reason and notes
    reason = Column(Text)
    manager_notes = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    requester = relationship("StaffMember", foreign_keys=[requester_id])
    to_staff = relationship("StaffMember", foreign_keys=[to_staff_id])
    approved_by = relationship("StaffMember", foreign_keys=[approved_by_id])
    from_shift = relationship("EnhancedShift", foreign_keys=[from_shift_id], back_populates="swap_requests_from")
    to_shift = relationship("EnhancedShift", foreign_keys=[to_shift_id], back_populates="swap_requests_to")


class ShiftBreak(Base):
    __tablename__ = "shift_breaks"
    
    id = Column(Integer, primary_key=True, index=True)
    shift_id = Column(Integer, ForeignKey("enhanced_shifts.id"), nullable=False)
    
    # Break details
    break_type = Column(Enum(BreakType, create_type=False), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    
    # Paid/unpaid
    is_paid = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    shift = relationship("EnhancedShift", back_populates="breaks")
    
    __table_args__ = (
        CheckConstraint('end_time > start_time', name='check_break_times'),
    )


class ShiftRequirement(Base):
    __tablename__ = "shift_requirements"
    
    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("shift_templates.id"), nullable=False)
    
    # Skill/certification requirements
    skill_name = Column(String, nullable=False)
    skill_level = Column(Integer, default=1)  # 1-5 scale
    is_mandatory = Column(Boolean, default=True)
    
    # Relationships
    template = relationship("ShiftTemplate", back_populates="requirements")


class SchedulePublication(Base):
    __tablename__ = "schedule_publications"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Period
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    
    # Publication details
    published_by_id = Column(Integer, ForeignKey("staff_members.id"), nullable=False)
    published_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Notification tracking
    notifications_sent = Column(Boolean, default=False)
    notification_count = Column(Integer, default=0)
    
    # Statistics
    total_shifts = Column(Integer)
    total_hours = Column(Float)
    estimated_labor_cost = Column(Float)
    
    # Metadata
    notes = Column(Text)
    
    # Relationships
    published_by = relationship("StaffMember")
    
    __table_args__ = (
        UniqueConstraint('start_date', 'end_date', name='unique_publication_period'),
    )