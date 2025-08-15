# backend/modules/sms/models/sms_models.py

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey,
    Enum as SQLEnum, JSON, Index, UniqueConstraint, CheckConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum

from core.database import Base


class SMSProvider(str, Enum):
    """Supported SMS providers"""
    TWILIO = "twilio"
    AWS_SNS = "aws_sns"
    SENDGRID = "sendgrid"
    MESSAGEBIRD = "messagebird"


class SMSStatus(str, Enum):
    """SMS delivery status"""
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    UNDELIVERED = "undelivered"
    BOUNCED = "bounced"


class SMSDirection(str, Enum):
    """Direction of SMS message"""
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class SMSTemplateCategory(str, Enum):
    """Categories for SMS templates"""
    RESERVATION = "reservation"
    ORDER = "order"
    MARKETING = "marketing"
    AUTHENTICATION = "authentication"
    NOTIFICATION = "notification"
    REMINDER = "reminder"
    ALERT = "alert"


class SMSMessage(Base):
    """Model for tracking SMS messages"""
    __tablename__ = "sms_messages"

    id = Column(Integer, primary_key=True, index=True)
    
    # Message details
    provider = Column(SQLEnum(SMSProvider), nullable=False, default=SMSProvider.TWILIO)
    direction = Column(SQLEnum(SMSDirection), nullable=False, default=SMSDirection.OUTBOUND)
    status = Column(SQLEnum(SMSStatus), nullable=False, default=SMSStatus.QUEUED)
    
    # Phone numbers
    from_number = Column(String(20), nullable=False)
    to_number = Column(String(20), nullable=False, index=True)
    
    # Content
    message_body = Column(Text, nullable=False)
    template_id = Column(Integer, ForeignKey("sms_templates.id"), nullable=True)
    template_variables = Column(JSON, nullable=True)
    
    # Provider details
    provider_message_id = Column(String(255), nullable=True, unique=True, index=True)
    provider_response = Column(JSON, nullable=True)
    provider_error = Column(Text, nullable=True)
    
    # Cost tracking
    segments_count = Column(Integer, default=1)
    cost_amount = Column(Float, nullable=True)
    cost_currency = Column(String(3), default="USD")
    
    # Delivery tracking
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    retry_count = Column(Integer, default=0)
    next_retry_at = Column(DateTime, nullable=True)
    
    # Association with business entities
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=True)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    
    # Metadata
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    template = relationship("SMSTemplate", back_populates="messages")
    customer = relationship("Customer", backref="sms_messages", foreign_keys=[customer_id])
    
    # Indexes
    __table_args__ = (
        Index("idx_sms_messages_status_created", "status", "created_at"),
        Index("idx_sms_messages_customer_created", "customer_id", "created_at"),
        Index("idx_sms_messages_provider_status", "provider", "status"),
    )


class SMSTemplate(Base):
    """Model for SMS message templates"""
    __tablename__ = "sms_templates"

    id = Column(Integer, primary_key=True, index=True)
    
    # Template details
    name = Column(String(100), nullable=False, unique=True)
    category = Column(SQLEnum(SMSTemplateCategory), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Content
    template_body = Column(Text, nullable=False)
    variables = Column(JSON, nullable=True)  # List of required variables
    
    # Configuration
    is_active = Column(Boolean, default=True, nullable=False)
    max_length = Column(Integer, default=160)
    estimated_segments = Column(Integer, default=1)
    
    # Usage tracking
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)
    
    # Version control
    version = Column(Integer, default=1)
    parent_template_id = Column(Integer, ForeignKey("sms_templates.id"), nullable=True)
    
    # Metadata
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    messages = relationship("SMSMessage", back_populates="template")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("max_length > 0", name="check_max_length_positive"),
        CheckConstraint("estimated_segments > 0", name="check_segments_positive"),
    )


class SMSOptOut(Base):
    """Model for managing SMS opt-out preferences"""
    __tablename__ = "sms_opt_outs"

    id = Column(Integer, primary_key=True, index=True)
    
    # Phone and customer
    phone_number = Column(String(20), nullable=False, unique=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    
    # Opt-out details
    opted_out = Column(Boolean, default=True, nullable=False)
    opt_out_date = Column(DateTime, nullable=False, server_default=func.now())
    opt_out_reason = Column(String(255), nullable=True)
    opt_out_method = Column(String(50), nullable=True)  # 'sms_reply', 'web', 'phone', 'email'
    
    # Opt-in (if they re-subscribe)
    opted_in_date = Column(DateTime, nullable=True)
    opt_in_method = Column(String(50), nullable=True)
    
    # Category-specific opt-outs
    categories_opted_out = Column(JSON, nullable=True, default=list)  # List of SMSTemplateCategory values
    
    # Compliance
    compliance_notes = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    
    # Metadata
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Indexes
    __table_args__ = (
        Index("idx_opt_out_customer", "customer_id", "opted_out"),
        Index("idx_opt_out_date", "opt_out_date"),
    )


class SMSCost(Base):
    """Model for tracking SMS costs and billing"""
    __tablename__ = "sms_costs"

    id = Column(Integer, primary_key=True, index=True)
    
    # Billing period
    billing_period_start = Column(DateTime, nullable=False, index=True)
    billing_period_end = Column(DateTime, nullable=False, index=True)
    
    # Provider and costs
    provider = Column(SQLEnum(SMSProvider), nullable=False)
    total_messages = Column(Integer, default=0)
    total_segments = Column(Integer, default=0)
    
    # Cost breakdown
    outbound_cost = Column(Float, default=0.0)
    inbound_cost = Column(Float, default=0.0)
    phone_number_cost = Column(Float, default=0.0)
    additional_fees = Column(Float, default=0.0)
    total_cost = Column(Float, default=0.0)
    currency = Column(String(3), default="USD")
    
    # Cost per category
    cost_by_category = Column(JSON, nullable=True)  # {category: {count: x, cost: y}}
    
    # Provider invoice details
    provider_invoice_id = Column(String(255), nullable=True)
    provider_invoice_url = Column(String(500), nullable=True)
    
    # Internal tracking
    is_paid = Column(Boolean, default=False)
    paid_at = Column(DateTime, nullable=True)
    payment_reference = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Indexes
    __table_args__ = (
        Index("idx_sms_cost_period", "billing_period_start", "billing_period_end"),
        Index("idx_sms_cost_provider_period", "provider", "billing_period_start"),
        UniqueConstraint("provider", "billing_period_start", "billing_period_end", 
                        name="unique_provider_billing_period"),
    )