# backend/modules/analytics/models/pos_analytics_models.py

"""
Models for POS-specific analytics and reporting.

Provides pre-aggregated data for POS performance metrics,
terminal analytics, and provider comparisons.
"""

from sqlalchemy import (
    Column, Integer, String, ForeignKey, DateTime, Numeric, Boolean,
    Index, Date, Enum as SQLEnum, Float, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from datetime import datetime, date
from enum import Enum
import uuid

from backend.core.database import Base
from backend.core.mixins import TimestampMixin


class POSMetricType(str, Enum):
    """Types of POS metrics tracked"""
    TRANSACTION_COUNT = "transaction_count"
    TRANSACTION_VALUE = "transaction_value"
    SYNC_SUCCESS_RATE = "sync_success_rate"
    WEBHOOK_SUCCESS_RATE = "webhook_success_rate"
    PROCESSING_TIME = "processing_time"
    ERROR_RATE = "error_rate"
    SETTLEMENT_TIME = "settlement_time"


class POSAnalyticsSnapshot(Base, TimestampMixin):
    """
    Pre-aggregated POS analytics data for dashboard performance.
    Updated hourly via background jobs.
    """
    __tablename__ = "pos_analytics_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True)
    
    # Time dimensions
    snapshot_date = Column(Date, nullable=False, index=True)
    snapshot_hour = Column(Integer, nullable=False)  # 0-23
    
    # POS dimensions
    provider_id = Column(Integer, ForeignKey("external_pos_providers.id"), nullable=True, index=True)
    terminal_id = Column(String(100), nullable=True, index=True)
    
    # Transaction metrics
    total_transactions = Column(Integer, nullable=False, default=0)
    successful_transactions = Column(Integer, nullable=False, default=0)
    failed_transactions = Column(Integer, nullable=False, default=0)
    total_transaction_value = Column(Numeric(12, 2), nullable=False, default=0.0)
    average_transaction_value = Column(Numeric(10, 2), nullable=False, default=0.0)
    
    # Sync metrics
    total_syncs = Column(Integer, nullable=False, default=0)
    successful_syncs = Column(Integer, nullable=False, default=0)
    failed_syncs = Column(Integer, nullable=False, default=0)
    average_sync_time_ms = Column(Float, nullable=False, default=0.0)
    
    # Webhook metrics
    total_webhooks = Column(Integer, nullable=False, default=0)
    successful_webhooks = Column(Integer, nullable=False, default=0)
    failed_webhooks = Column(Integer, nullable=False, default=0)
    average_webhook_processing_time_ms = Column(Float, nullable=False, default=0.0)
    
    # Error metrics
    total_errors = Column(Integer, nullable=False, default=0)
    error_types = Column(JSONB, nullable=False, default=dict)  # {error_type: count}
    
    # Performance metrics
    uptime_percentage = Column(Float, nullable=False, default=100.0)
    response_time_p50 = Column(Float, nullable=True)  # 50th percentile
    response_time_p95 = Column(Float, nullable=True)  # 95th percentile
    response_time_p99 = Column(Float, nullable=True)  # 99th percentile
    
    # Relationships
    provider = relationship("ExternalPOSProvider", lazy="joined")
    
    __table_args__ = (
        UniqueConstraint('snapshot_date', 'snapshot_hour', 'provider_id', 'terminal_id', 
                        name='uq_pos_snapshot_time_provider_terminal'),
        Index('idx_pos_snapshot_date_provider', 'snapshot_date', 'provider_id'),
        Index('idx_pos_snapshot_terminal', 'terminal_id', 'snapshot_date'),
    )
    
    @property
    def sync_success_rate(self):
        """Calculate sync success rate"""
        if self.total_syncs == 0:
            return 0.0
        return (self.successful_syncs / self.total_syncs) * 100
    
    @property
    def webhook_success_rate(self):
        """Calculate webhook success rate"""
        if self.total_webhooks == 0:
            return 0.0
        return (self.successful_webhooks / self.total_webhooks) * 100
    
    @property
    def transaction_success_rate(self):
        """Calculate transaction success rate"""
        if self.total_transactions == 0:
            return 0.0
        return (self.successful_transactions / self.total_transactions) * 100


class POSProviderPerformance(Base, TimestampMixin):
    """
    Aggregated performance metrics by POS provider.
    Used for provider comparison and health monitoring.
    """
    __tablename__ = "pos_provider_performance"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Provider and time
    provider_id = Column(Integer, ForeignKey("external_pos_providers.id"), nullable=False, index=True)
    measurement_date = Column(Date, nullable=False, index=True)
    
    # Aggregate metrics
    total_terminals = Column(Integer, nullable=False, default=0)
    active_terminals = Column(Integer, nullable=False, default=0)
    
    # Daily totals
    daily_transactions = Column(Integer, nullable=False, default=0)
    daily_transaction_value = Column(Numeric(12, 2), nullable=False, default=0.0)
    daily_syncs = Column(Integer, nullable=False, default=0)
    daily_webhooks = Column(Integer, nullable=False, default=0)
    daily_errors = Column(Integer, nullable=False, default=0)
    
    # Success rates
    overall_success_rate = Column(Float, nullable=False, default=0.0)
    sync_success_rate = Column(Float, nullable=False, default=0.0)
    webhook_success_rate = Column(Float, nullable=False, default=0.0)
    
    # Performance metrics
    average_response_time_ms = Column(Float, nullable=False, default=0.0)
    uptime_percentage = Column(Float, nullable=False, default=100.0)
    
    # Top issues
    top_error_types = Column(JSONB, nullable=False, default=list)  # [{type, count, percentage}]
    problematic_terminals = Column(JSONB, nullable=False, default=list)  # [{terminal_id, error_count}]
    
    # Relationships
    provider = relationship("ExternalPOSProvider", lazy="joined")
    
    __table_args__ = (
        UniqueConstraint('provider_id', 'measurement_date', 
                        name='uq_provider_performance_date'),
        Index('idx_provider_performance_date', 'measurement_date', 'provider_id'),
    )


class POSTerminalHealth(Base, TimestampMixin):
    """
    Health metrics for individual POS terminals.
    Used for monitoring and alerting.
    """
    __tablename__ = "pos_terminal_health"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Terminal identification
    terminal_id = Column(String(100), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("external_pos_providers.id"), nullable=False, index=True)
    
    # Status
    is_online = Column(Boolean, nullable=False, default=True)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    health_status = Column(String(50), nullable=False, default="healthy")  # healthy, degraded, critical
    
    # Recent metrics (last 24 hours)
    recent_transaction_count = Column(Integer, nullable=False, default=0)
    recent_error_count = Column(Integer, nullable=False, default=0)
    recent_sync_failures = Column(Integer, nullable=False, default=0)
    recent_success_rate = Column(Float, nullable=False, default=100.0)
    
    # Alert thresholds
    error_threshold_exceeded = Column(Boolean, nullable=False, default=False)
    sync_failure_threshold_exceeded = Column(Boolean, nullable=False, default=False)
    offline_duration_minutes = Column(Integer, nullable=False, default=0)
    
    # Terminal info
    terminal_name = Column(String(200), nullable=True)
    terminal_location = Column(String(500), nullable=True)
    terminal_metadata = Column(JSONB, nullable=False, default=dict)
    
    # Relationships
    provider = relationship("ExternalPOSProvider", lazy="joined")
    
    __table_args__ = (
        UniqueConstraint('terminal_id', 'provider_id', 
                        name='uq_terminal_health_terminal_provider'),
        Index('idx_terminal_health_status', 'health_status', 'provider_id'),
        Index('idx_terminal_health_lastseen', 'last_seen_at'),
    )


class POSAnalyticsAlert(Base, TimestampMixin):
    """
    Alerts generated from POS analytics monitoring.
    """
    __tablename__ = "pos_analytics_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True)
    
    # Alert details
    alert_type = Column(String(100), nullable=False, index=True)  # terminal_offline, high_error_rate, etc.
    severity = Column(String(50), nullable=False, index=True)  # info, warning, critical
    
    # Source
    provider_id = Column(Integer, ForeignKey("external_pos_providers.id"), nullable=True, index=True)
    terminal_id = Column(String(100), nullable=True, index=True)
    
    # Alert content
    title = Column(String(200), nullable=False)
    description = Column(String(1000), nullable=False)
    metric_value = Column(Float, nullable=True)
    threshold_value = Column(Float, nullable=True)
    
    # Status
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    acknowledged = Column(Boolean, nullable=False, default=False)
    acknowledged_by = Column(Integer, ForeignKey("staff_members.id"), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    
    # Alert metadata
    context_data = Column(JSONB, nullable=False, default=dict)
    notification_sent = Column(Boolean, nullable=False, default=False)
    
    # Relationships
    provider = relationship("ExternalPOSProvider", lazy="joined")
    acknowledger = relationship("StaffMember", lazy="joined")
    
    __table_args__ = (
        Index('idx_pos_alert_active', 'is_active', 'severity'),
        Index('idx_pos_alert_provider_time', 'provider_id', 'created_at'),
    )