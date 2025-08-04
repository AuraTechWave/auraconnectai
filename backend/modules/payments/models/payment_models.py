# backend/modules/payments/models/payment_models.py

from sqlalchemy import (
    Column, Integer, String, ForeignKey, DateTime, Numeric, Text, 
    Boolean, Index, Enum as SQLEnum, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from core.database import Base
from core.mixins import TimestampMixin
from datetime import datetime
from enum import Enum
import uuid


class PaymentGateway(str, Enum):
    """Supported payment gateways"""
    STRIPE = "stripe"
    SQUARE = "square"
    PAYPAL = "paypal"
    CASH = "cash"  # For in-person payments
    MANUAL = "manual"  # For manual processing


class PaymentStatus(str, Enum):
    """Payment status states"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    DISPUTED = "disputed"
    REQUIRES_ACTION = "requires_action"  # For 3D Secure, etc.


class PaymentMethod(str, Enum):
    """Payment method types"""
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    WALLET = "wallet"  # Apple Pay, Google Pay
    PAYPAL = "paypal"
    CASH = "cash"
    CHECK = "check"
    GIFT_CARD = "gift_card"
    STORE_CREDIT = "store_credit"


class RefundStatus(str, Enum):
    """Refund status states"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Payment(Base, TimestampMixin):
    """Payment transaction record"""
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    payment_id = Column(String(100), nullable=False, unique=True, index=True)  # Our internal ID
    
    # Order relationship
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    
    # Payment gateway information
    gateway = Column(SQLEnum(PaymentGateway), nullable=False, index=True)
    gateway_payment_id = Column(String(255), nullable=True, index=True)  # External ID from gateway
    gateway_customer_id = Column(String(255), nullable=True)  # Customer ID at gateway
    
    # Payment details
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    status = Column(SQLEnum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING, index=True)
    method = Column(SQLEnum(PaymentMethod), nullable=True)
    
    # Customer information
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    customer_email = Column(String(255), nullable=True)
    customer_name = Column(String(255), nullable=True)
    
    # Payment method details (encrypted in production)
    payment_method_details = Column(JSONB, nullable=True)
    # Examples:
    # Card: {"last4": "4242", "brand": "visa", "exp_month": 12, "exp_year": 2025}
    # PayPal: {"payer_id": "XXX", "payer_email": "user@example.com"}
    
    # Transaction details
    description = Column(Text, nullable=True)
    statement_descriptor = Column(String(255), nullable=True)
    
    # Processing information
    processed_at = Column(DateTime, nullable=True)
    fee_amount = Column(Numeric(10, 2), nullable=True)  # Processing fee
    net_amount = Column(Numeric(10, 2), nullable=True)  # Amount after fees
    
    # Error handling
    failure_code = Column(String(50), nullable=True)
    failure_message = Column(Text, nullable=True)
    
    # Metadata
    metadata = Column(JSONB, nullable=True, default={})
    
    # Idempotency
    idempotency_key = Column(String(255), nullable=True, unique=True)
    
    # Relations
    order = relationship("Order", back_populates="payments")
    customer = relationship("Customer", back_populates="payments")
    refunds = relationship("Refund", back_populates="payment", cascade="all, delete-orphan")
    webhooks = relationship("PaymentWebhook", back_populates="payment", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_payment_order_status', 'order_id', 'status'),
        Index('idx_payment_gateway_id', 'gateway', 'gateway_payment_id'),
        Index('idx_payment_customer', 'customer_id', 'status'),
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.payment_id:
            self.payment_id = f"pay_{uuid.uuid4().hex[:16]}"


class Refund(Base, TimestampMixin):
    """Payment refund record"""
    __tablename__ = "refunds"
    
    id = Column(Integer, primary_key=True, index=True)
    refund_id = Column(String(100), nullable=False, unique=True, index=True)
    
    # Payment relationship
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False, index=True)
    
    # Gateway information
    gateway = Column(SQLEnum(PaymentGateway), nullable=False)
    gateway_refund_id = Column(String(255), nullable=True, index=True)
    
    # Refund details
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    status = Column(SQLEnum(RefundStatus), nullable=False, default=RefundStatus.PENDING, index=True)
    reason = Column(Text, nullable=True)
    
    # Processing information
    processed_at = Column(DateTime, nullable=True)
    fee_refunded = Column(Numeric(10, 2), nullable=True)
    
    # Error handling
    failure_code = Column(String(50), nullable=True)
    failure_message = Column(Text, nullable=True)
    
    # Metadata
    metadata = Column(JSONB, nullable=True, default={})
    
    # Who initiated the refund
    initiated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relations
    payment = relationship("Payment", back_populates="refunds")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.refund_id:
            self.refund_id = f"ref_{uuid.uuid4().hex[:16]}"


class PaymentWebhook(Base, TimestampMixin):
    """Webhook events from payment gateways"""
    __tablename__ = "payment_webhooks"
    
    id = Column(Integer, primary_key=True, index=True)
    webhook_id = Column(String(100), nullable=False, unique=True, index=True)
    
    # Gateway information
    gateway = Column(SQLEnum(PaymentGateway), nullable=False, index=True)
    gateway_event_id = Column(String(255), nullable=True, unique=True)
    
    # Event details
    event_type = Column(String(100), nullable=False, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True, index=True)
    
    # Webhook data
    headers = Column(JSONB, nullable=True)
    payload = Column(JSONB, nullable=False)
    
    # Processing
    processed = Column(Boolean, nullable=False, default=False, index=True)
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    
    # Relations
    payment = relationship("Payment", back_populates="webhooks")
    
    __table_args__ = (
        Index('idx_webhook_gateway_event', 'gateway', 'event_type', 'processed'),
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.webhook_id:
            self.webhook_id = f"wh_{uuid.uuid4().hex[:16]}"


class PaymentGatewayConfig(Base, TimestampMixin):
    """Configuration for payment gateways"""
    __tablename__ = "payment_gateway_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    gateway = Column(SQLEnum(PaymentGateway), nullable=False, unique=True, index=True)
    
    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    is_test_mode = Column(Boolean, nullable=False, default=True)
    
    # Configuration (encrypted in production)
    config = Column(JSONB, nullable=False, default={})
    # Examples:
    # Stripe: {"publishable_key": "pk_test_...", "secret_key": "sk_test_...", "webhook_secret": "whsec_..."}
    # Square: {"application_id": "...", "access_token": "...", "location_id": "..."}
    # PayPal: {"client_id": "...", "client_secret": "...", "mode": "sandbox"}
    
    # Supported features
    supports_refunds = Column(Boolean, nullable=False, default=True)
    supports_partial_refunds = Column(Boolean, nullable=False, default=True)
    supports_recurring = Column(Boolean, nullable=False, default=False)
    supports_save_card = Column(Boolean, nullable=False, default=True)
    
    # Fee structure
    fee_percentage = Column(Numeric(5, 2), nullable=True)  # e.g., 2.9
    fee_fixed = Column(Numeric(10, 2), nullable=True)  # e.g., 0.30
    
    # Webhook configuration
    webhook_url = Column(String(500), nullable=True)
    webhook_events = Column(JSONB, nullable=True, default=[])
    
    # Metadata
    description = Column(Text, nullable=True)
    
    __table_args__ = (
        Index('idx_gateway_config_active', 'gateway', 'is_active'),
    )


class CustomerPaymentMethod(Base, TimestampMixin):
    """Saved payment methods for customers"""
    __tablename__ = "customer_payment_methods"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Customer relationship
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    
    # Gateway information
    gateway = Column(SQLEnum(PaymentGateway), nullable=False)
    gateway_payment_method_id = Column(String(255), nullable=False)
    gateway_customer_id = Column(String(255), nullable=False)
    
    # Payment method details
    method_type = Column(SQLEnum(PaymentMethod), nullable=False)
    display_name = Column(String(255), nullable=True)  # e.g., "Visa ending in 4242"
    
    # Card details (if applicable)
    card_last4 = Column(String(4), nullable=True)
    card_brand = Column(String(50), nullable=True)
    card_exp_month = Column(Integer, nullable=True)
    card_exp_year = Column(Integer, nullable=True)
    
    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    is_default = Column(Boolean, nullable=False, default=False)
    
    # Metadata
    metadata = Column(JSONB, nullable=True, default={})
    
    # Relations
    customer = relationship("Customer", back_populates="payment_methods")
    
    __table_args__ = (
        Index('idx_customer_payment_method', 'customer_id', 'is_active'),
        UniqueConstraint('customer_id', 'gateway', 'gateway_payment_method_id', name='uq_customer_gateway_method'),
    )