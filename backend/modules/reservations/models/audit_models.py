# backend/modules/reservations/models/audit_models.py

"""
Audit models for reservation system.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
import enum


class AuditAction(enum.Enum):
    """Audit action types"""

    CREATED = "created"
    UPDATED = "updated"
    CANCELLED = "cancelled"
    CONFIRMED = "confirmed"
    SEATED = "seated"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    MANUAL_OVERRIDE = "manual_override"
    TABLE_CHANGED = "table_changed"
    PROMOTED_FROM_WAITLIST = "promoted_from_waitlist"
    NOTIFICATION_SENT = "notification_sent"
    REMINDER_SENT = "reminder_sent"


class ReservationAuditLog(Base):
    """Detailed audit log for reservation changes"""

    __tablename__ = "reservation_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=False)
    action = Column(String(50), nullable=False)

    # Who made the change
    user_id = Column(Integer, ForeignKey("users.id"))
    user_type = Column(String(20))  # customer, staff, admin, system
    user_ip = Column(String(45))  # IP address for security
    user_agent = Column(String(255))  # Browser/app info

    # What changed
    field_changes = Column(JSON)  # {"field": {"old": value, "new": value}}
    reason = Column(Text)  # Reason for manual override

    # When
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Additional context
    metadata = Column(JSON)  # Any additional data

    # Relationships
    reservation = relationship("Reservation", backref="audit_logs")
    user = relationship("User", backref="reservation_audit_logs")

    # Indexes for performance
    __table_args__ = (
        Index("idx_reservation_audit_reservation_id", "reservation_id"),
        Index("idx_reservation_audit_user_id", "user_id"),
        Index("idx_reservation_audit_timestamp", "timestamp"),
        Index("idx_reservation_audit_action", "action"),
    )

    def __repr__(self):
        return (
            f"<ReservationAuditLog {self.id} - {self.action} on {self.reservation_id}>"
        )


class WaitlistAuditLog(Base):
    """Audit log for waitlist changes"""

    __tablename__ = "waitlist_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    waitlist_id = Column(Integer, ForeignKey("waitlist_entries.id"), nullable=False)
    action = Column(String(50), nullable=False)

    # Who made the change
    user_id = Column(Integer, ForeignKey("users.id"))
    user_type = Column(String(20))

    # What changed
    field_changes = Column(JSON)
    reason = Column(Text)

    # When
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Additional context
    metadata = Column(JSON)

    # Relationships
    waitlist_entry = relationship("Waitlist", backref="audit_logs")
    user = relationship("User", backref="waitlist_audit_logs")

    __table_args__ = (
        Index("idx_waitlist_audit_waitlist_id", "waitlist_id"),
        Index("idx_waitlist_audit_timestamp", "timestamp"),
    )
