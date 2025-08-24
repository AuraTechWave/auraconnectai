# backend/modules/email/models/email_models.py

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey,
    Enum as SQLEnum, JSON, Index, UniqueConstraint, CheckConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum

from core.database import Base


class EmailProvider(str, Enum):
    """Supported email providers"""
    SENDGRID = "sendgrid"
    AWS_SES = "aws_ses"
    MAILGUN = "mailgun"
    SMTP = "smtp"


class EmailStatus(str, Enum):
    """Email delivery status"""
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"
    COMPLAINED = "complained"
    OPENED = "opened"
    CLICKED = "clicked"


class EmailDirection(str, Enum):
    """Direction of email message"""
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class EmailTemplateCategory(str, Enum):
    """Categories for email templates"""
    RESERVATION = "reservation"
    ORDER = "order"
    MARKETING = "marketing"
    AUTHENTICATION = "authentication"
    NOTIFICATION = "notification"
    REMINDER = "reminder"
    ALERT = "alert"
    INVOICE = "invoice"
    RECEIPT = "receipt"


class EmailMessage(Base):
    """Model for tracking email messages"""
    __tablename__ = "email_messages"

    id = Column(Integer, primary_key=True, index=True)
    
    # Message details
    provider = Column(SQLEnum(EmailProvider), nullable=False, default=EmailProvider.SENDGRID)
    direction = Column(SQLEnum(EmailDirection), nullable=False, default=EmailDirection.OUTBOUND)
    status = Column(SQLEnum(EmailStatus), nullable=False, default=EmailStatus.QUEUED)
    
    # Email addresses
    from_email = Column(String(255), nullable=False)
    from_name = Column(String(255), nullable=True)
    to_email = Column(String(255), nullable=False, index=True)
    to_name = Column(String(255), nullable=True)
    cc_emails = Column(JSON, nullable=True)  # List of CC emails
    bcc_emails = Column(JSON, nullable=True)  # List of BCC emails
    reply_to_email = Column(String(255), nullable=True)
    
    # Content
    subject = Column(String(500), nullable=False)
    html_body = Column(Text, nullable=True)
    text_body = Column(Text, nullable=True)
    template_id = Column(Integer, ForeignKey("email_templates.id"), nullable=True)
    template_variables = Column(JSON, nullable=True)
    
    # Provider details
    provider_message_id = Column(String(255), nullable=True, unique=True, index=True)
    provider_response = Column(JSON, nullable=True)
    provider_error = Column(Text, nullable=True)
    
    # Tracking
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    bounced_at = Column(DateTime, nullable=True)
    complained_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    
    # Retry handling
    retry_count = Column(Integer, default=0)
    next_retry_at = Column(DateTime, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)  # For scheduled emails
    
    # Association with business entities
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=True)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Metadata
    metadata = Column(JSON, nullable=True)
    headers = Column(JSON, nullable=True)  # Custom email headers
    tags = Column(JSON, nullable=True)  # Email tags for categorization
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    template = relationship("EmailTemplate", back_populates="messages")
    attachments = relationship("EmailAttachment", back_populates="email_message", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_email_messages_status', 'status'),
        Index('idx_email_messages_scheduled', 'scheduled_at', 'status'),
        Index('idx_email_messages_retry', 'next_retry_at', 'status'),
        Index('idx_email_messages_customer', 'customer_id', 'created_at'),
    )


class EmailTemplate(Base):
    """Model for email templates"""
    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True, index=True)
    
    # Template identification
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    category = Column(SQLEnum(EmailTemplateCategory), nullable=False)
    
    # Content
    subject_template = Column(String(500), nullable=False)
    html_body_template = Column(Text, nullable=False)
    text_body_template = Column(Text, nullable=True)
    
    # Provider specific template IDs
    sendgrid_template_id = Column(String(255), nullable=True)
    ses_template_name = Column(String(255), nullable=True)
    
    # Variables
    variables = Column(JSON, nullable=True)  # List of expected variables
    default_values = Column(JSON, nullable=True)  # Default values for variables
    
    # Settings
    is_active = Column(Boolean, nullable=False, default=True)
    is_transactional = Column(Boolean, nullable=False, default=True)
    
    # Metadata
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    messages = relationship("EmailMessage", back_populates="template")
    
    # Indexes
    __table_args__ = (
        Index('idx_email_templates_category', 'category'),
        Index('idx_email_templates_active', 'is_active'),
    )


class EmailAttachment(Base):
    """Model for email attachments"""
    __tablename__ = "email_attachments"

    id = Column(Integer, primary_key=True, index=True)
    email_message_id = Column(Integer, ForeignKey("email_messages.id"), nullable=False)
    
    # Attachment details
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    content_id = Column(String(255), nullable=True)  # For inline attachments
    size_bytes = Column(Integer, nullable=False)
    
    # Storage
    storage_path = Column(String(500), nullable=True)  # Path in object storage
    content_base64 = Column(Text, nullable=True)  # For small attachments
    
    # Metadata
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    
    # Relationships
    email_message = relationship("EmailMessage", back_populates="attachments")


class EmailUnsubscribe(Base):
    """Model for tracking email unsubscribes"""
    __tablename__ = "email_unsubscribes"

    id = Column(Integer, primary_key=True, index=True)
    
    # Unsubscribe details
    email = Column(String(255), nullable=False, unique=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    
    # Unsubscribe type
    unsubscribe_all = Column(Boolean, nullable=False, default=False)
    unsubscribed_categories = Column(JSON, nullable=True)  # List of EmailTemplateCategory values
    
    # Tracking
    unsubscribed_at = Column(DateTime, nullable=False, server_default=func.now())
    unsubscribe_token = Column(String(255), nullable=True, unique=True)
    unsubscribe_reason = Column(Text, nullable=True)
    
    # Resubscribe
    resubscribed_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Metadata
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class EmailBounce(Base):
    """Model for tracking email bounces"""
    __tablename__ = "email_bounces"

    id = Column(Integer, primary_key=True, index=True)
    
    # Bounce details
    email = Column(String(255), nullable=False, index=True)
    email_message_id = Column(Integer, ForeignKey("email_messages.id"), nullable=True)
    
    # Bounce type
    bounce_type = Column(String(50), nullable=False)  # hard, soft, block
    bounce_subtype = Column(String(50), nullable=True)
    
    # Provider details
    provider = Column(SQLEnum(EmailProvider), nullable=False)
    provider_response = Column(JSON, nullable=True)
    diagnostic_code = Column(Text, nullable=True)
    
    # Status
    is_permanent = Column(Boolean, nullable=False, default=False)
    retry_count = Column(Integer, default=0)
    
    # Timestamps
    bounced_at = Column(DateTime, nullable=False, server_default=func.now())
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_email_bounces_email', 'email', 'is_permanent'),
        Index('idx_email_bounces_type', 'bounce_type'),
    )