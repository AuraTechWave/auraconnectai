# backend/modules/tables/models/table_models.py

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    DECIMAL,
    JSON,
    Enum as SQLEnum,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum

from core.database import Base
from core.mixins import TimestampMixin

# Import core models
from modules.core.models import Floor, FloorStatus, Restaurant


class TableStatus(str, Enum):
    """Table availability status"""

    AVAILABLE = "available"
    OCCUPIED = "occupied"
    RESERVED = "reserved"
    BLOCKED = "blocked"  # Temporarily unavailable
    CLEANING = "cleaning"  # Being cleaned
    MAINTENANCE = "maintenance"  # Under maintenance


class TableShape(str, Enum):
    """Table shape for visual representation"""

    SQUARE = "square"
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    OVAL = "oval"
    HEXAGON = "hexagon"
    CUSTOM = "custom"


class ReservationStatus(str, Enum):
    """Reservation status"""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    SEATED = "seated"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


# Floor model is now imported from modules.core.models


class Table(Base, TimestampMixin):
    """Restaurant table configuration and state"""

    __tablename__ = "tables"

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    floor_id = Column(Integer, ForeignKey("floors.id"), nullable=False)

    # Basic info
    table_number = Column(String(20), nullable=False)
    display_name = Column(String(50))

    # Capacity
    min_capacity = Column(Integer, nullable=False, default=1)
    max_capacity = Column(Integer, nullable=False)
    preferred_capacity = Column(Integer)  # Optimal number of guests

    # Position and dimensions (for layout designer)
    position_x = Column(Integer, nullable=False, default=0)
    position_y = Column(Integer, nullable=False, default=0)
    width = Column(Integer, nullable=False, default=100)
    height = Column(Integer, nullable=False, default=100)
    rotation = Column(Integer, default=0)  # Rotation in degrees

    # Visual properties
    shape = Column(SQLEnum(TableShape), default=TableShape.RECTANGLE)
    color = Column(String(7))  # Hex color code

    # Status
    status = Column(SQLEnum(TableStatus), default=TableStatus.AVAILABLE)
    is_active = Column(Boolean, default=True)
    is_combinable = Column(
        Boolean, default=True
    )  # Can be combined with adjacent tables

    # Features
    has_power_outlet = Column(Boolean, default=False)
    is_wheelchair_accessible = Column(Boolean, default=False)
    is_by_window = Column(Boolean, default=False)
    is_private = Column(Boolean, default=False)

    # Section/zone info
    section = Column(String(50))  # e.g., "Patio", "Bar", "Main Dining"
    zone = Column(String(50))  # e.g., "Smoking", "Non-smoking"
    server_station = Column(String(50))  # Assigned server station

    # QR code for digital menu
    qr_code = Column(String(200))

    # Additional properties
    properties = Column(JSON, default={})  # Flexible properties storage

    # Relationships
    restaurant = relationship("Restaurant", back_populates="tables")
    floor = relationship("Floor", back_populates="tables")
    current_session = relationship(
        "TableSession",
        uselist=False,
        back_populates="table",
        primaryjoin="and_(Table.id==TableSession.table_id, TableSession.end_time.is_(None))",
    )
    sessions = relationship(
        "TableSession", back_populates="table", foreign_keys="TableSession.table_id"
    )
    reservations = relationship("TableReservation", back_populates="table")

    __table_args__ = (
        UniqueConstraint(
            "restaurant_id", "table_number", name="uix_table_restaurant_number"
        ),
        CheckConstraint("min_capacity <= max_capacity", name="chk_table_capacity"),
        CheckConstraint("rotation >= 0 AND rotation < 360", name="chk_table_rotation"),
    )


class TableSession(Base, TimestampMixin):
    """Active table occupancy session"""

    __tablename__ = "table_sessions"

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=False)

    # Session info
    start_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_time = Column(DateTime)

    # Guest info
    guest_count = Column(Integer, nullable=False)
    guest_name = Column(String(100))
    guest_phone = Column(String(20))

    # Order association
    order_id = Column(Integer, ForeignKey("orders.id"))

    # Server assignment
    server_id = Column(Integer, ForeignKey("staff.id"))

    # Relationships
    restaurant = relationship("Restaurant")
    table = relationship("Table", back_populates="sessions", foreign_keys=[table_id])
    order = relationship("Order")
    server = relationship("Staff")
    combined_tables = relationship("TableCombination", back_populates="session")


class TableCombination(Base, TimestampMixin):
    """Track combined tables for larger parties"""

    __tablename__ = "table_combinations"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("table_sessions.id"), nullable=False)
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=False)
    is_primary = Column(Boolean, default=False)  # Primary table in combination

    # Relationships
    session = relationship("TableSession", back_populates="combined_tables")
    table = relationship("Table")

    __table_args__ = (
        UniqueConstraint(
            "session_id", "table_id", name="uix_combination_session_table"
        ),
    )


class TableReservation(Base, TimestampMixin):
    """Table reservations"""

    __tablename__ = "table_reservations"

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    table_id = Column(Integer, ForeignKey("tables.id"))  # Nullable for auto-assignment
    customer_id = Column(Integer, ForeignKey("customers.id"))

    # Reservation details
    reservation_code = Column(String(20), unique=True, nullable=False)
    reservation_date = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=120)  # Expected duration

    # Guest info
    guest_count = Column(Integer, nullable=False)
    guest_name = Column(String(100), nullable=False)
    guest_phone = Column(String(20), nullable=False)
    guest_email = Column(String(100))

    # Special requests
    special_requests = Column(String(500))
    occasion = Column(String(50))  # Birthday, Anniversary, etc.

    # Status
    status = Column(SQLEnum(ReservationStatus), default=ReservationStatus.PENDING)
    confirmed_at = Column(DateTime)
    seated_at = Column(DateTime)
    completed_at = Column(DateTime)
    cancelled_at = Column(DateTime)
    cancellation_reason = Column(String(200))

    # Table preferences
    table_preferences = Column(
        JSON, default={}
    )  # e.g., {"by_window": true, "quiet": true}

    # Deposit/prepayment
    deposit_amount = Column(DECIMAL(10, 2))
    deposit_paid = Column(Boolean, default=False)

    # Notifications
    reminder_sent = Column(Boolean, default=False)
    reminder_sent_at = Column(DateTime)

    # Source
    source = Column(String(50))  # walk-in, phone, website, app

    # Relationships
    restaurant = relationship("Restaurant")
    table = relationship("Table", back_populates="reservations")
    customer = relationship("Customer")

    __table_args__ = (
        CheckConstraint("guest_count > 0", name="chk_reservation_guest_count"),
    )


class TableLayout(Base, TimestampMixin):
    """Saved table layout configurations"""

    __tablename__ = "table_layouts"

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)

    name = Column(String(100), nullable=False)
    description = Column(String(500))

    # Layout data (JSON with table positions, floors, etc.)
    layout_data = Column(JSON, nullable=False)

    # Usage
    is_active = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False)

    # Schedule (optional)
    active_days = Column(JSON)  # e.g., ["monday", "tuesday"]
    active_from_time = Column(String(5))  # e.g., "18:00"
    active_to_time = Column(String(5))  # e.g., "22:00"

    # Special event
    event_date = Column(DateTime)
    event_name = Column(String(100))

    # Relationships
    restaurant = relationship("Restaurant")

    __table_args__ = (
        UniqueConstraint("restaurant_id", "name", name="uix_layout_restaurant_name"),
    )


class TableStateLog(Base, TimestampMixin):
    """Log of table state changes for analytics"""

    __tablename__ = "table_state_logs"

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=False)

    # State change
    previous_status = Column(SQLEnum(TableStatus))
    new_status = Column(SQLEnum(TableStatus), nullable=False)
    changed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    changed_by_id = Column(Integer, ForeignKey("staff.id"))

    # Context
    session_id = Column(Integer, ForeignKey("table_sessions.id"))
    reservation_id = Column(Integer, ForeignKey("table_reservations.id"))
    reason = Column(String(200))

    # Duration in previous state (minutes)
    duration_minutes = Column(Integer)

    # Relationships
    restaurant = relationship("Restaurant")
    table = relationship("Table")
    changed_by = relationship("Staff")
    session = relationship("TableSession")
    reservation = relationship("TableReservation")
