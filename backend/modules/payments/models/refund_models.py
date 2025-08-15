# backend/modules/payments/models/refund_models.py

from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Numeric,
    Boolean,
    Text,
    DateTime,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from decimal import Decimal
from datetime import datetime
import enum

from core.database import Base
from core.mixins import TimestampMixin


class RefundReason(str, enum.Enum):
    """Standard refund reason codes"""

    # Order issues
    ORDER_CANCELLED = "order_cancelled"
    ORDER_MISTAKE = "order_mistake"
    WRONG_ITEMS = "wrong_items"
    MISSING_ITEMS = "missing_items"

    # Quality issues
    FOOD_QUALITY = "food_quality"
    COLD_FOOD = "cold_food"
    INCORRECT_PREPARATION = "incorrect_preparation"

    # Service issues
    LONG_WAIT = "long_wait"
    POOR_SERVICE = "poor_service"

    # Payment issues
    DUPLICATE_CHARGE = "duplicate_charge"
    OVERCHARGE = "overcharge"
    PRICE_DISPUTE = "price_dispute"

    # Other
    CUSTOMER_REQUEST = "customer_request"
    GOODWILL = "goodwill"
    TEST_REFUND = "test_refund"
    OTHER = "other"


class RefundCategory(str, enum.Enum):
    """Refund categories for reporting"""

    ORDER_ISSUE = "order_issue"
    QUALITY_ISSUE = "quality_issue"
    SERVICE_ISSUE = "service_issue"
    PAYMENT_ISSUE = "payment_issue"
    OTHER = "other"


class RefundApprovalStatus(str, enum.Enum):
    """Refund approval workflow states"""

    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"


class RefundPolicy(Base, TimestampMixin):
    """
    Configurable refund policies by restaurant
    """

    __tablename__ = "refund_policies"

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)

    # Policy settings
    name = Column(String(100), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)

    # Automatic approval thresholds
    auto_approve_enabled = Column(Boolean, default=False)
    auto_approve_threshold = Column(Numeric(10, 2), default=Decimal("50.00"))

    # Time limits
    refund_window_hours = Column(Integer, default=168)  # 7 days default

    # Partial refund settings
    allow_partial_refunds = Column(Boolean, default=True)
    min_refund_percentage = Column(Integer, default=0)
    max_refund_percentage = Column(Integer, default=100)

    # Reason requirements
    require_reason = Column(Boolean, default=True)
    require_approval_above = Column(Numeric(10, 2), nullable=True)

    # Fee handling
    refund_processing_fee = Column(Boolean, default=True)
    deduct_processing_fee = Column(Boolean, default=False)
    processing_fee_amount = Column(Numeric(10, 2), default=Decimal("0"))

    # Notification settings
    notify_customer = Column(Boolean, default=True)
    notify_manager = Column(Boolean, default=True)
    manager_notification_threshold = Column(Numeric(10, 2), default=Decimal("100.00"))

    # Metadata
    created_by = Column(Integer, ForeignKey("users.id"))
    updated_by = Column(Integer, ForeignKey("users.id"))


class RefundRequest(Base, TimestampMixin):
    """
    Customer refund requests before processing
    """

    __tablename__ = "refund_requests"

    id = Column(Integer, primary_key=True)
    request_number = Column(String(50), unique=True, nullable=False)

    # Order and payment info
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False)

    # Request details
    requested_amount = Column(Numeric(10, 2), nullable=False)
    reason_code = Column(SQLEnum(RefundReason), nullable=False)
    category = Column(SQLEnum(RefundCategory), nullable=False)
    reason_details = Column(Text)

    # Customer info
    customer_id = Column(Integer, ForeignKey("customers.id"))
    customer_name = Column(String(255), nullable=False)
    customer_email = Column(String(255), nullable=False)
    customer_phone = Column(String(50))

    # Approval workflow
    approval_status = Column(
        SQLEnum(RefundApprovalStatus), default=RefundApprovalStatus.PENDING_APPROVAL
    )
    approved_by = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)
    rejection_reason = Column(Text)

    # Processing
    refund_id = Column(Integer, ForeignKey("refunds.id"))
    processed_at = Column(DateTime)

    # Items to refund (for partial refunds)
    refund_items = Column(JSONB, default=[])
    # Format: [{"item_id": 1, "quantity": 2, "amount": 20.00}]

    # Evidence/attachments
    evidence_urls = Column(JSONB, default=[])

    # Metadata
    priority = Column(String(20), default="normal")  # urgent, high, normal, low
    tags = Column(JSONB, default=[])
    notes = Column(Text)

    # Batch processing support
    batch_id = Column(String(50), nullable=True, index=True)
    batch_notes = Column(Text, nullable=True)

    # Relationships
    order = relationship("Order", backref="refund_requests")
    payment = relationship("Payment", backref="refund_requests")
    refund = relationship("Refund", backref="refund_request")


class RefundAuditLog(Base, TimestampMixin):
    """
    Audit trail for all refund activities
    """

    __tablename__ = "refund_audit_logs"

    id = Column(Integer, primary_key=True)

    # References
    refund_id = Column(Integer, ForeignKey("refunds.id"))
    refund_request_id = Column(Integer, ForeignKey("refund_requests.id"))

    # Action details
    action = Column(
        String(50), nullable=False
    )  # created, approved, rejected, processed, failed
    actor_id = Column(Integer, ForeignKey("users.id"))
    actor_type = Column(String(20))  # user, system, customer

    # State tracking
    previous_state = Column(JSONB)
    new_state = Column(JSONB)

    # Additional info
    reason = Column(Text)
    audit_metadata = Column(JSONB, default={})

    # IP tracking for security
    ip_address = Column(String(45))
    user_agent = Column(String(255))


# Extend the existing Refund model with new fields
def enhance_refund_model():
    """
    This function shows the additional fields to add to the existing Refund model
    These should be added via a migration
    """
    additional_fields = {
        "reason_code": Column(SQLEnum(RefundReason)),
        "category": Column(SQLEnum(RefundCategory)),
        "approval_status": Column(SQLEnum(RefundApprovalStatus)),
        "approved_by": Column(Integer, ForeignKey("users.id")),
        "approved_at": Column(DateTime),
        "refund_type": Column(String(20)),  # full, partial, credit
        "credit_issued": Column(Boolean, default=False),
        "credit_amount": Column(Numeric(10, 2)),
        "original_payment_method": Column(String(50)),
        "refund_method": Column(String(50)),  # original, credit, cash
        "expected_completion_date": Column(DateTime),
        "actual_completion_date": Column(DateTime),
        "notification_sent": Column(Boolean, default=False),
        "notification_sent_at": Column(DateTime),
        "receipt_url": Column(String(500)),
        "batch_id": Column(String(50)),  # For batch processing
        "is_disputed": Column(Boolean, default=False),
        "dispute_notes": Column(Text),
    }
    return additional_fields


# Reason category mapping
REASON_CATEGORY_MAP = {
    RefundReason.ORDER_CANCELLED: RefundCategory.ORDER_ISSUE,
    RefundReason.ORDER_MISTAKE: RefundCategory.ORDER_ISSUE,
    RefundReason.WRONG_ITEMS: RefundCategory.ORDER_ISSUE,
    RefundReason.MISSING_ITEMS: RefundCategory.ORDER_ISSUE,
    RefundReason.FOOD_QUALITY: RefundCategory.QUALITY_ISSUE,
    RefundReason.COLD_FOOD: RefundCategory.QUALITY_ISSUE,
    RefundReason.INCORRECT_PREPARATION: RefundCategory.QUALITY_ISSUE,
    RefundReason.LONG_WAIT: RefundCategory.SERVICE_ISSUE,
    RefundReason.POOR_SERVICE: RefundCategory.SERVICE_ISSUE,
    RefundReason.DUPLICATE_CHARGE: RefundCategory.PAYMENT_ISSUE,
    RefundReason.OVERCHARGE: RefundCategory.PAYMENT_ISSUE,
    RefundReason.PRICE_DISPUTE: RefundCategory.PAYMENT_ISSUE,
    RefundReason.CUSTOMER_REQUEST: RefundCategory.OTHER,
    RefundReason.GOODWILL: RefundCategory.OTHER,
    RefundReason.TEST_REFUND: RefundCategory.OTHER,
    RefundReason.OTHER: RefundCategory.OTHER,
}


def get_refund_category(reason: RefundReason) -> RefundCategory:
    """Get the category for a refund reason"""
    return REASON_CATEGORY_MAP.get(reason, RefundCategory.OTHER)
