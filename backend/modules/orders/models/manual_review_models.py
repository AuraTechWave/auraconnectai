# backend/modules/orders/models/manual_review_models.py

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Boolean,
    JSON,
    Enum,
)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from core.database import Base


class ReviewReason(str, enum.Enum):
    """Reasons for manual review"""

    MISSING_RECIPE = "missing_recipe"
    INSUFFICIENT_STOCK = "insufficient_stock"
    INVENTORY_NOT_FOUND = "inventory_not_found"
    RECIPE_CIRCULAR_DEPENDENCY = "recipe_circular_dependency"
    SYNC_CONFLICT = "sync_conflict"
    CONCURRENT_MODIFICATION = "concurrent_modification"
    OTHER = "other"


class ReviewStatus(str, enum.Enum):
    """Status of manual review"""

    PENDING = "pending"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"


class ManualReviewQueue(Base):
    """Queue for orders requiring manual review"""

    __tablename__ = "manual_review_queue"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    reason = Column(
        Enum(
            ReviewReason,
            values_callable=lambda obj: [e.value for e in obj],
            create_type=False,
        ),
        nullable=False,
    )
    status = Column(
        Enum(
            ReviewStatus,
            values_callable=lambda obj: [e.value for e in obj],
            create_type=False,
        ),
        default=ReviewStatus.PENDING,
        nullable=False,
    )

    # Details about the issue
    error_details = Column(JSON, nullable=True)  # Structured error information
    error_message = Column(Text, nullable=True)  # Human-readable error message

    # Review tracking
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    review_notes = Column(Text, nullable=True)
    resolution_action = Column(String(255), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    assigned_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    # Priority and escalation
    priority = Column(
        Integer, default=0, nullable=False
    )  # Higher number = higher priority
    escalated = Column(Boolean, default=False, nullable=False)
    escalation_reason = Column(Text, nullable=True)

    # Relationships
    order = relationship("Order", backref="manual_reviews")
    assigned_user = relationship(
        "User", foreign_keys=[assigned_to], backref="assigned_reviews"
    )
    reviewer = relationship(
        "User", foreign_keys=[reviewed_by], backref="completed_reviews"
    )


class InventoryAdjustmentAttempt(Base):
    """Log of failed inventory adjustment attempts"""

    __tablename__ = "inventory_adjustment_attempts"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    attempt_number = Column(Integer, default=1, nullable=False)

    # Error information
    error_type = Column(String(100), nullable=False)
    error_message = Column(Text, nullable=False)
    error_details = Column(JSON, nullable=True)

    # What was attempted
    attempted_deductions = Column(
        JSON, nullable=True
    )  # List of attempted inventory changes
    menu_items_affected = Column(
        JSON, nullable=True
    )  # Menu items that couldn't be processed

    # Timestamps
    attempted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    attempted_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    order = relationship("Order", backref="adjustment_attempts")
    user = relationship("User", backref="adjustment_attempts")
