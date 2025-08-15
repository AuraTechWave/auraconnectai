# backend/modules/orders/models/external_pos_models.py

"""
Models for handling external POS webhook events.

Supports incoming webhooks from external payment systems like
Square, Stripe, Toast, etc. for payment updates.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Numeric,
    Text,
    Boolean,
    Enum,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from core.database import Base
from core.mixins import TimestampMixin
from datetime import datetime
import uuid


class ExternalPOSProvider(Base, TimestampMixin):
    """Configuration for external POS providers"""

    __tablename__ = "external_pos_providers"

    id = Column(Integer, primary_key=True, index=True)
    provider_code = Column(String(50), unique=True, nullable=False, index=True)
    provider_name = Column(String(100), nullable=False)
    webhook_endpoint_id = Column(String(100), unique=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Authentication configuration
    auth_type = Column(String(50), nullable=False)  # hmac, api_key, oauth
    auth_config = Column(JSONB, nullable=False)  # Store keys, secrets, etc.

    # Provider-specific settings
    settings = Column(JSONB, nullable=True)
    supported_events = Column(JSONB, nullable=False, default=list)

    # Rate limiting
    rate_limit_per_minute = Column(Integer, default=60)

    # Relationships
    webhook_events = relationship(
        "ExternalPOSWebhookEvent",
        back_populates="provider",
        cascade="all, delete-orphan",
    )

    @property
    def total_events(self):
        """Total number of webhook events for this provider"""
        return len(self.webhook_events) if self.webhook_events else 0

    @property
    def failed_events_count(self):
        """Count of failed webhook events"""
        if not self.webhook_events:
            return 0
        return sum(
            1 for event in self.webhook_events if event.processing_status == "failed"
        )


class ExternalPOSWebhookEvent(Base, TimestampMixin):
    """Incoming webhook events from external POS systems"""

    __tablename__ = "external_pos_webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(
        UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False
    )

    # Provider information
    provider_id = Column(
        Integer, ForeignKey("external_pos_providers.id"), nullable=False, index=True
    )

    # Event details
    event_type = Column(
        String(100), nullable=False, index=True
    )  # payment.completed, payment.failed, etc.
    event_timestamp = Column(DateTime, nullable=False, index=True)

    # Request information
    request_headers = Column(JSONB, nullable=False)
    request_body = Column(JSONB, nullable=False)
    request_signature = Column(String(500), nullable=True)

    # Processing status
    processing_status = Column(
        String(50), nullable=False, default="pending", index=True
    )
    processed_at = Column(DateTime, nullable=True)
    processing_attempts = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)

    # Validation
    is_verified = Column(Boolean, default=False, nullable=False)
    verification_details = Column(JSONB, nullable=True)

    # Relationships
    provider = relationship("ExternalPOSProvider", back_populates="webhook_events")
    payment_updates = relationship(
        "ExternalPOSPaymentUpdate",
        back_populates="webhook_event",
        cascade="all, delete-orphan",
    )
    logs = relationship(
        "ExternalPOSWebhookLog",
        back_populates="webhook_event",
        cascade="all, delete-orphan",
        order_by="ExternalPOSWebhookLog.occurred_at.desc()",
    )

    __table_args__ = (
        Index("idx_webhook_event_processing", "processing_status", "created_at"),
        Index("idx_webhook_event_provider_type", "provider_id", "event_type"),
    )

    @property
    def is_failed(self):
        """Check if webhook processing failed"""
        return self.processing_status == "failed"

    @property
    def is_processed(self):
        """Check if webhook was successfully processed"""
        return self.processing_status == "processed"

    @property
    def processing_duration(self):
        """Calculate processing duration in seconds"""
        if self.processed_at and self.created_at:
            return (self.processed_at - self.created_at).total_seconds()
        return None

    @property
    def latest_payment_update(self):
        """Get the most recent payment update"""
        if self.payment_updates:
            return max(self.payment_updates, key=lambda x: x.created_at)
        return None


class ExternalPOSPaymentUpdate(Base, TimestampMixin):
    """Payment updates from external POS systems"""

    __tablename__ = "external_pos_payment_updates"

    id = Column(Integer, primary_key=True, index=True)
    webhook_event_id = Column(
        Integer,
        ForeignKey("external_pos_webhook_events.id"),
        nullable=False,
        index=True,
    )

    # External references
    external_transaction_id = Column(String(200), nullable=False, index=True)
    external_order_id = Column(String(200), nullable=True, index=True)
    external_payment_id = Column(String(200), nullable=True, index=True)

    # Local order mapping
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)

    # Payment details
    payment_status = Column(
        String(50), nullable=False
    )  # completed, failed, pending, refunded
    payment_method = Column(String(50), nullable=False)  # card, cash, mobile, etc.
    payment_amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")

    # Additional payment info
    tip_amount = Column(Numeric(10, 2), nullable=True)
    tax_amount = Column(Numeric(10, 2), nullable=True)
    discount_amount = Column(Numeric(10, 2), nullable=True)

    # Card details (if applicable)
    card_last_four = Column(String(4), nullable=True)
    card_brand = Column(String(50), nullable=True)

    # Customer info
    customer_email = Column(String(255), nullable=True)
    customer_phone = Column(String(50), nullable=True)

    # Processing
    is_processed = Column(Boolean, default=False, nullable=False, index=True)
    processed_at = Column(DateTime, nullable=True)
    processing_notes = Column(Text, nullable=True)

    # Raw data from provider
    raw_payment_data = Column(JSONB, nullable=False)

    webhook_event = relationship(
        "ExternalPOSWebhookEvent", back_populates="payment_updates"
    )
    order = relationship("Order", backref="external_payment_updates")

    __table_args__ = (
        Index(
            "idx_payment_update_external_refs",
            "external_transaction_id",
            "external_order_id",
        ),
        Index("idx_payment_update_processing", "is_processed", "created_at"),
    )

    @property
    def total_amount(self):
        """Calculate total amount including tip"""
        total = self.payment_amount or 0
        if self.tip_amount:
            total += self.tip_amount
        return total

    @property
    def is_matched(self):
        """Check if payment is matched to a local order"""
        return self.order_id is not None


class ExternalPOSWebhookLog(Base, TimestampMixin):
    """Detailed logging for webhook processing"""

    __tablename__ = "external_pos_webhook_logs"

    id = Column(Integer, primary_key=True, index=True)
    webhook_event_id = Column(
        Integer,
        ForeignKey("external_pos_webhook_events.id"),
        nullable=False,
        index=True,
    )

    log_level = Column(String(20), nullable=False)  # info, warning, error
    log_type = Column(
        String(50), nullable=False
    )  # validation, processing, mapping, etc.
    message = Column(Text, nullable=False)
    details = Column(JSONB, nullable=True)

    occurred_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    webhook_event = relationship("ExternalPOSWebhookEvent", back_populates="logs")

    __table_args__ = (
        Index("idx_webhook_log_event", "webhook_event_id", "occurred_at"),
    )
