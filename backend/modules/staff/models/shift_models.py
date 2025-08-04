from sqlalchemy import Column, Integer, DateTime, ForeignKey, Boolean, Float, String, Text, Time, Date
from sqlalchemy.orm import relationship
from core.database import Base
from datetime import datetime


class Shift(Base):
    __tablename__ = "shifts"
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff_members.id"))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    date = Column(DateTime, nullable=False)
    location_id = Column(Integer)


class Schedule(Base):
    """Enhanced schedule/shift model with publishing and notification features"""
    __tablename__ = "schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, nullable=False, index=True)
    staff_id = Column(Integer, ForeignKey("staff_members.id"), nullable=False)
    
    # Time details
    date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    total_hours = Column(Float, nullable=False)
    break_duration = Column(Integer, default=0)  # minutes
    
    # Publishing details
    is_published = Column(Boolean, default=False, index=True)
    published_at = Column(DateTime, nullable=True)
    published_by = Column(Integer, ForeignKey("staff_members.id"), nullable=True)
    
    # Notification tracking
    reminder_sent = Column(Boolean, default=False)
    
    # Notes and metadata
    notes = Column(Text, nullable=True)
    
    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("staff_members.id"), nullable=True)
    
    # Relationships
    staff = relationship("StaffMember", foreign_keys=[staff_id], back_populates="schedules")
    published_by_user = relationship("StaffMember", foreign_keys=[published_by])
    created_by_user = relationship("StaffMember", foreign_keys=[created_by])
