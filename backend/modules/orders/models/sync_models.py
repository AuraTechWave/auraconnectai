# backend/modules/orders/models/sync_models.py

"""
Order synchronization models for tracking sync status and history.

Handles offline order synchronization, conflict resolution, and sync metrics.
"""

from sqlalchemy import (
    Column, Integer, String, ForeignKey, DateTime, Boolean,
    Text, Enum as SQLEnum, Index, Numeric, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum
import uuid

from core.database import Base
from core.mixins import TimestampMixin


class SyncStatus(str, Enum):
    """Order synchronization status"""
    PENDING = "pending"  # Not yet synced
    IN_PROGRESS = "in_progress"  # Currently syncing
    SYNCED = "synced"  # Successfully synced
    FAILED = "failed"  # Sync failed
    CONFLICT = "conflict"  # Sync conflict detected
    RETRY = "retry"  # Scheduled for retry


class SyncDirection(str, Enum):
    """Sync direction for order data"""
    LOCAL_TO_REMOTE = "local_to_remote"  # POS to cloud
    REMOTE_TO_LOCAL = "remote_to_local"  # Cloud to POS
    BIDIRECTIONAL = "bidirectional"  # Both ways


class OrderSyncStatus(Base, TimestampMixin):
    """Track synchronization status for each order"""
    __tablename__ = "order_sync_status"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    
    # Sync tracking
    sync_status = Column(
        SQLEnum(SyncStatus),
        nullable=False,
        default=SyncStatus.PENDING,
        index=True
    )
    sync_direction = Column(
        SQLEnum(SyncDirection),
        nullable=False,
        default=SyncDirection.LOCAL_TO_REMOTE
    )
    
    # Sync attempts
    attempt_count = Column(Integer, nullable=False, default=0)
    last_attempt_at = Column(DateTime, nullable=True)
    next_retry_at = Column(DateTime, nullable=True, index=True)
    
    # Success tracking
    synced_at = Column(DateTime, nullable=True)
    sync_duration_ms = Column(Integer, nullable=True)
    
    # Error tracking
    last_error = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)
    error_count = Column(Integer, nullable=False, default=0)
    
    # Conflict resolution
    conflict_detected_at = Column(DateTime, nullable=True)
    conflict_resolution = Column(String(50), nullable=True)  # auto, manual, ignore
    conflict_data = Column(JSONB, nullable=True)  # Store conflicting versions
    
    # Remote system tracking
    remote_id = Column(String(255), nullable=True, index=True)
    remote_system = Column(String(50), nullable=True)  # cloud, partner_pos, etc.
    remote_version = Column(Integer, nullable=True)
    
    # Checksums for data integrity
    local_checksum = Column(String(64), nullable=True)
    remote_checksum = Column(String(64), nullable=True)
    
    # Relationships
    order = relationship("Order", backref="sync_status")
    
    # Indexes
    __table_args__ = (
        Index('idx_sync_status_pending', 'sync_status', 'next_retry_at'),
        Index('idx_sync_status_order', 'order_id', 'sync_status'),
        UniqueConstraint('order_id', name='uq_order_sync_status'),
    )


class SyncBatch(Base, TimestampMixin):
    """Track batch synchronization operations"""
    __tablename__ = "sync_batches"
    
    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True)
    
    # Batch details
    batch_type = Column(String(50), nullable=False)  # scheduled, manual, retry
    batch_size = Column(Integer, nullable=False, default=0)
    
    # Timing
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    
    # Results
    total_orders = Column(Integer, nullable=False, default=0)
    successful_syncs = Column(Integer, nullable=False, default=0)
    failed_syncs = Column(Integer, nullable=False, default=0)
    conflict_count = Column(Integer, nullable=False, default=0)
    
    # Performance metrics
    avg_sync_time_ms = Column(Numeric(10, 2), nullable=True)
    max_sync_time_ms = Column(Integer, nullable=True)
    min_sync_time_ms = Column(Integer, nullable=True)
    
    # Error summary
    error_summary = Column(JSONB, nullable=True)
    
    # System info
    initiated_by = Column(String(50), nullable=True)  # system, user_id, api
    pos_terminal_id = Column(String(50), nullable=True)
    
    # Relationships
    sync_logs = relationship("SyncLog", back_populates="batch")


class SyncLog(Base, TimestampMixin):
    """Detailed log of each sync operation"""
    __tablename__ = "sync_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("sync_batches.id"), nullable=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    
    # Operation details
    operation = Column(String(50), nullable=False)  # create, update, delete
    sync_direction = Column(SQLEnum(SyncDirection), nullable=False)
    
    # Status
    status = Column(String(50), nullable=False)  # success, failed, conflict
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    
    # Data tracking
    data_before = Column(JSONB, nullable=True)  # State before sync
    data_after = Column(JSONB, nullable=True)   # State after sync
    changes_made = Column(JSONB, nullable=True)  # Delta of changes
    
    # Error details
    error_message = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)
    error_details = Column(JSONB, nullable=True)
    
    # Remote system response
    remote_response = Column(JSONB, nullable=True)
    http_status_code = Column(Integer, nullable=True)
    
    # Relationships
    batch = relationship("SyncBatch", back_populates="sync_logs")
    order = relationship("Order")
    
    # Indexes
    __table_args__ = (
        Index('idx_sync_log_batch_status', 'batch_id', 'status'),
        Index('idx_sync_log_order_time', 'order_id', 'started_at'),
    )


class SyncConfiguration(Base, TimestampMixin):
    """Configuration for sync behavior"""
    __tablename__ = "sync_configurations"
    
    id = Column(Integer, primary_key=True, index=True)
    config_key = Column(String(100), unique=True, nullable=False, index=True)
    config_value = Column(JSONB, nullable=False)
    
    # Common configurations
    # sync_interval_minutes: 10
    # max_retry_attempts: 3
    # retry_backoff_multiplier: 2
    # batch_size: 50
    # conflict_resolution_mode: auto/manual
    # sync_enabled: true/false
    
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Audit
    updated_by = Column(Integer, ForeignKey("staff_members.id"), nullable=True)
    
    @classmethod
    def get_config(cls, db_session, key: str, default=None):
        """Get configuration value by key"""
        config = db_session.query(cls).filter(
            cls.config_key == key,
            cls.is_active == True
        ).first()
        return config.config_value if config else default


class SyncConflict(Base, TimestampMixin):
    """Track and manage sync conflicts"""
    __tablename__ = "sync_conflicts"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    
    # Conflict details
    conflict_type = Column(String(50), nullable=False)  # data_mismatch, version_conflict, etc.
    detected_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Conflicting data
    local_data = Column(JSONB, nullable=False)
    remote_data = Column(JSONB, nullable=False)
    differences = Column(JSONB, nullable=True)
    
    # Resolution
    resolution_status = Column(String(50), nullable=False, default="pending")  # pending, resolved, ignored
    resolution_method = Column(String(50), nullable=True)  # local_wins, remote_wins, merge, manual
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(Integer, ForeignKey("staff_members.id"), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    
    # Final data after resolution
    final_data = Column(JSONB, nullable=True)
    
    # Relationships
    order = relationship("Order")
    resolver = relationship("StaffMember", foreign_keys=[resolved_by])
    
    # Indexes
    __table_args__ = (
        Index('idx_conflict_status', 'resolution_status', 'detected_at'),
        Index('idx_conflict_order', 'order_id', 'resolution_status'),
    )