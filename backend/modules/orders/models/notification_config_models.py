# backend/modules/orders/models/notification_config_models.py

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, Index, 
    UniqueConstraint, CheckConstraint, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from core.database import Base
from core.mixins import TimestampMixin
from enum import Enum
from typing import Optional


class NotificationChannelStatus(str, Enum):
    """Status of notification channels"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    FAILED = "failed"


class NotificationRetryStrategy(str, Enum):
    """Retry strategies for failed notifications"""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    NO_RETRY = "no_retry"


class NotificationChannelConfig(Base, TimestampMixin):
    """Dynamic configuration for notification channels"""
    __tablename__ = "notification_channel_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    channel_name = Column(String(50), nullable=False, unique=True, index=True)
    channel_type = Column(String(20), nullable=False)  # push, email, sms, webhook
    
    # Status and availability
    status = Column(
        SQLEnum(NotificationChannelStatus), 
        nullable=False, 
        default=NotificationChannelStatus.ACTIVE,
        index=True
    )
    is_enabled = Column(Boolean, nullable=False, default=True)
    maintenance_message = Column(Text, nullable=True)
    
    # Configuration
    config = Column(JSONB, nullable=False, default={})
    # Examples:
    # Email: {"smtp_host": "...", "smtp_port": 587, "from_address": "..."}
    # SMS: {"twilio_account_sid": "...", "from_number": "..."}
    # Push: {"fcm_server_key": "...", "apns_cert_path": "..."}
    
    # Retry configuration
    retry_strategy = Column(
        SQLEnum(NotificationRetryStrategy),
        nullable=False,
        default=NotificationRetryStrategy.EXPONENTIAL_BACKOFF
    )
    max_retry_attempts = Column(Integer, nullable=False, default=3)
    initial_retry_delay_seconds = Column(Integer, nullable=False, default=60)
    max_retry_delay_seconds = Column(Integer, nullable=False, default=3600)
    retry_backoff_multiplier = Column(Integer, nullable=False, default=2)
    
    # Rate limiting
    rate_limit_per_minute = Column(Integer, nullable=True)
    rate_limit_per_hour = Column(Integer, nullable=True)
    rate_limit_per_day = Column(Integer, nullable=True)
    
    # Priority settings
    priority_threshold = Column(String(20), nullable=True)  # Only send high/urgent priority
    
    # Health check
    last_health_check = Column(DateTime, nullable=True)
    health_check_status = Column(String(20), nullable=True)
    health_check_message = Column(Text, nullable=True)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    auto_disable_after_failures = Column(Integer, nullable=True, default=10)
    
    # Metadata
    description = Column(Text, nullable=True)
    updated_by = Column(Integer, nullable=True)
    
    __table_args__ = (
        CheckConstraint('max_retry_attempts >= 0', name='check_max_retry_attempts'),
        CheckConstraint('initial_retry_delay_seconds > 0', name='check_initial_delay'),
        CheckConstraint('retry_backoff_multiplier >= 1', name='check_backoff_multiplier'),
        Index('idx_notification_channel_status', 'channel_type', 'status'),
    )


class NotificationRetryQueue(Base, TimestampMixin):
    """Queue for retrying failed notifications"""
    __tablename__ = "notification_retry_queue"
    
    id = Column(Integer, primary_key=True, index=True)
    notification_id = Column(Integer, nullable=False, index=True)
    channel_name = Column(String(50), nullable=False, index=True)
    
    # Retry information
    retry_count = Column(Integer, nullable=False, default=0)
    next_retry_at = Column(DateTime, nullable=False, index=True)
    last_retry_at = Column(DateTime, nullable=True)
    
    # Error tracking
    last_error = Column(Text, nullable=True)
    error_count = Column(Integer, nullable=False, default=0)
    
    # Original notification data
    recipient = Column(String, nullable=False)
    subject = Column(String, nullable=True)
    message = Column(Text, nullable=False)
    notification_metadata = Column(JSONB, nullable=True, default={})
    
    # Status
    is_abandoned = Column(Boolean, nullable=False, default=False)
    abandoned_reason = Column(Text, nullable=True)
    
    __table_args__ = (
        Index('idx_retry_queue_next_attempt', 'next_retry_at', 'is_abandoned'),
        Index('idx_retry_queue_notification', 'notification_id', 'channel_name'),
    )


class NotificationChannelStats(Base, TimestampMixin):
    """Statistics for notification channels"""
    __tablename__ = "notification_channel_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    channel_name = Column(String(50), nullable=False, index=True)
    
    # Time window
    stat_date = Column(DateTime, nullable=False, index=True)
    stat_hour = Column(Integer, nullable=False)  # 0-23
    
    # Counters
    total_sent = Column(Integer, nullable=False, default=0)
    total_delivered = Column(Integer, nullable=False, default=0)
    total_failed = Column(Integer, nullable=False, default=0)
    total_retried = Column(Integer, nullable=False, default=0)
    
    # Performance metrics
    avg_delivery_time_ms = Column(Integer, nullable=True)
    p95_delivery_time_ms = Column(Integer, nullable=True)
    p99_delivery_time_ms = Column(Integer, nullable=True)
    
    # Error breakdown
    error_breakdown = Column(JSONB, nullable=True, default={})
    
    __table_args__ = (
        UniqueConstraint('channel_name', 'stat_date', 'stat_hour', name='uq_channel_stats_hour'),
        Index('idx_channel_stats_lookup', 'channel_name', 'stat_date'),
    )