# backend/modules/equipment/models.py

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Float,
    Boolean,
    Text,
    Enum as SQLEnum,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum

from core.database import Base


class MaintenanceStatus(str, Enum):
    """Status of maintenance tasks"""

    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class MaintenanceType(str, Enum):
    """Type of maintenance"""

    PREVENTIVE = "preventive"
    CORRECTIVE = "corrective"
    EMERGENCY = "emergency"
    INSPECTION = "inspection"
    CALIBRATION = "calibration"


class EquipmentStatus(str, Enum):
    """Status of equipment"""

    OPERATIONAL = "operational"
    NEEDS_MAINTENANCE = "needs_maintenance"
    UNDER_MAINTENANCE = "under_maintenance"
    OUT_OF_SERVICE = "out_of_service"
    RETIRED = "retired"


class Equipment(Base):
    """Equipment model for tracking restaurant equipment"""

    __tablename__ = "equipment"

    id = Column(Integer, primary_key=True, index=True)
    equipment_name = Column(String(200), nullable=False, index=True)
    equipment_type = Column(String(100), nullable=False)
    manufacturer = Column(String(200))
    model_number = Column(String(100))
    serial_number = Column(String(100), unique=True, index=True)
    purchase_date = Column(DateTime)
    warranty_expiry = Column(DateTime)
    location = Column(String(200))
    status = Column(
        SQLEnum(EquipmentStatus), default=EquipmentStatus.OPERATIONAL, nullable=False
    )

    # Maintenance schedule fields
    maintenance_interval_days = Column(Integer)  # For preventive maintenance
    last_maintenance_date = Column(DateTime)
    next_due_date = Column(DateTime, index=True)  # For preventive maintenance cycles

    # Additional fields
    notes = Column(Text)
    is_critical = Column(Boolean, default=False)  # Critical equipment flag
    is_active = Column(Boolean, default=True)

    # Audit fields
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))
    updated_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    maintenance_records = relationship(
        "MaintenanceRecord", back_populates="equipment", cascade="all, delete-orphan"
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_equipment_status_next_due", "status", "next_due_date"),
        Index("idx_equipment_type_status", "equipment_type", "status"),
    )


class MaintenanceRecord(Base):
    """Maintenance record for equipment"""

    __tablename__ = "maintenance_records"

    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(
        Integer,
        ForeignKey("equipment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Maintenance details
    maintenance_type = Column(
        SQLEnum(MaintenanceType), default=MaintenanceType.PREVENTIVE, nullable=False
    )
    status = Column(
        SQLEnum(MaintenanceStatus),
        default=MaintenanceStatus.SCHEDULED,
        nullable=False,
        index=True,
    )

    # Dates
    scheduled_date = Column(DateTime, nullable=False)
    date_performed = Column(DateTime)
    next_due_date = Column(DateTime)  # For tracking next maintenance cycle

    # Details
    description = Column(Text, nullable=False)
    performed_by = Column(String(200))
    cost = Column(Float, default=0.0)
    parts_replaced = Column(Text)

    # Completion details
    issues_found = Column(Text)
    resolution = Column(Text)
    downtime_hours = Column(Float, default=0.0)

    # Audit fields
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))
    completed_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    equipment = relationship("Equipment", back_populates="maintenance_records")

    # Indexes for performance
    __table_args__ = (
        Index("idx_maintenance_status_date", "status", "scheduled_date"),
        Index("idx_maintenance_equipment_status", "equipment_id", "status"),
        Index("idx_maintenance_type_status", "maintenance_type", "status"),
    )
