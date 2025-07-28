# backend/core/menu_sync_models.py

from sqlalchemy import (Column, Integer, String, ForeignKey, DateTime, 
                        Float, Text, Boolean, JSON, Enum as SQLEnum, Index)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from backend.core.database import Base  
from backend.core.mixins import TimestampMixin
from enum import Enum
from datetime import datetime
import uuid


class SyncDirection(str, Enum):
    """Direction of synchronization"""
    PUSH = "push"           # AuraConnect -> POS
    PULL = "pull"           # POS -> AuraConnect
    BIDIRECTIONAL = "bidirectional"  # Both directions


class SyncStatus(str, Enum):
    """Status of synchronization operation"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    ERROR = "error"
    CONFLICT = "conflict"
    CANCELLED = "cancelled"


class ConflictResolution(str, Enum):
    """How to resolve sync conflicts"""
    MANUAL = "manual"           # Require manual resolution
    POS_WINS = "pos_wins"       # POS data takes precedence
    AURA_WINS = "aura_wins"     # AuraConnect data takes precedence
    LATEST_WINS = "latest_wins" # Most recently updated wins


class POSMenuMapping(Base, TimestampMixin):
    """Maps AuraConnect menu entities to POS system entities"""
    __tablename__ = "pos_menu_mappings"

    id = Column(Integer, primary_key=True, index=True)
    
    # POS Integration
    pos_integration_id = Column(Integer, ForeignKey("pos_integrations.id"), nullable=False)
    pos_vendor = Column(String(50), nullable=False, index=True)  # square, toast, clover, etc.
    
    # Entity mapping
    entity_type = Column(String(50), nullable=False, index=True)  # category, item, modifier_group, modifier
    aura_entity_id = Column(Integer, nullable=False)  # ID in AuraConnect system
    pos_entity_id = Column(String(255), nullable=False)  # ID in POS system
    pos_entity_data = Column(JSON, nullable=True)  # Full POS entity data for reference
    
    # Sync configuration
    sync_enabled = Column(Boolean, nullable=False, default=True)
    sync_direction = Column(SQLEnum(SyncDirection), nullable=False, default=SyncDirection.BIDIRECTIONAL)
    conflict_resolution = Column(SQLEnum(ConflictResolution), nullable=False, default=ConflictResolution.MANUAL)
    
    # Sync metadata
    last_sync_at = Column(DateTime, nullable=True)
    last_sync_direction = Column(SQLEnum(SyncDirection), nullable=True)
    aura_last_modified = Column(DateTime, nullable=True)
    pos_last_modified = Column(DateTime, nullable=True)
    sync_hash = Column(String(64), nullable=True)  # Hash of synced data for change detection
    
    # Status tracking
    is_active = Column(Boolean, nullable=False, default=True)
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    pos_integration = relationship("POSIntegration")
    sync_logs = relationship("MenuSyncLog", back_populates="mapping")
    
    # Indexes for performance
    __table_args__ = (
        Index('ix_pos_menu_mappings_entity', 'entity_type', 'aura_entity_id'),
        Index('ix_pos_menu_mappings_pos_entity', 'pos_vendor', 'pos_entity_id'),
        Index('ix_pos_menu_mappings_sync_status', 'sync_enabled', 'is_active'),
    )

    def __repr__(self):
        return f"<POSMenuMapping(entity_type='{self.entity_type}', aura_id={self.aura_entity_id}, pos_id='{self.pos_entity_id}')>"


class MenuSyncJob(Base, TimestampMixin):
    """Tracks menu synchronization jobs"""
    __tablename__ = "menu_sync_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False, unique=True, index=True)
    
    # Job configuration
    pos_integration_id = Column(Integer, ForeignKey("pos_integrations.id"), nullable=False)
    sync_direction = Column(SQLEnum(SyncDirection), nullable=False)
    entity_types = Column(JSON, nullable=True)  # Specific entity types to sync, null = all
    entity_ids = Column(JSON, nullable=True)  # Specific entity IDs to sync, null = all
    
    # Job execution
    status = Column(SQLEnum(SyncStatus), nullable=False, default=SyncStatus.PENDING)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)  # For scheduled jobs
    
    # Results
    total_entities = Column(Integer, nullable=False, default=0)
    processed_entities = Column(Integer, nullable=False, default=0)
    successful_entities = Column(Integer, nullable=False, default=0)
    failed_entities = Column(Integer, nullable=False, default=0)
    conflicts_detected = Column(Integer, nullable=False, default=0)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    
    # Metadata
    triggered_by = Column(String(50), nullable=True)  # user, scheduler, webhook, etc.
    triggered_by_id = Column(Integer, nullable=True)  # User ID if triggered by user
    job_config = Column(JSON, nullable=True)  # Additional configuration
    
    # Relationships
    pos_integration = relationship("POSIntegration")
    sync_logs = relationship("MenuSyncLog", back_populates="sync_job")
    
    def __repr__(self):
        return f"<MenuSyncJob(id={self.job_id}, status='{self.status}', direction='{self.sync_direction}')>"


class MenuSyncLog(Base, TimestampMixin):
    """Detailed log of individual menu entity sync operations"""
    __tablename__ = "menu_sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    # Job and mapping references
    sync_job_id = Column(Integer, ForeignKey("menu_sync_jobs.id"), nullable=False)
    mapping_id = Column(Integer, ForeignKey("pos_menu_mappings.id"), nullable=True)
    
    # Entity details
    entity_type = Column(String(50), nullable=False, index=True)
    aura_entity_id = Column(Integer, nullable=True)
    pos_entity_id = Column(String(255), nullable=True)
    
    # Operation details
    operation = Column(String(50), nullable=False)  # create, update, delete, conflict
    sync_direction = Column(SQLEnum(SyncDirection), nullable=False)
    status = Column(SQLEnum(SyncStatus), nullable=False)
    
    # Data comparison
    aura_data_before = Column(JSON, nullable=True)
    aura_data_after = Column(JSON, nullable=True)
    pos_data_before = Column(JSON, nullable=True)
    pos_data_after = Column(JSON, nullable=True)
    changes_detected = Column(JSON, nullable=True)  # Specific fields that changed
    
    # Conflict information
    conflict_type = Column(String(100), nullable=True)
    conflict_resolution = Column(SQLEnum(ConflictResolution), nullable=True)
    conflict_resolved_by = Column(Integer, nullable=True)  # User ID who resolved conflict
    conflict_resolved_at = Column(DateTime, nullable=True)
    
    # Performance and debugging
    processing_time_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)
    debug_info = Column(JSON, nullable=True)
    
    # Versioning integration
    menu_version_id = Column(Integer, ForeignKey("menu_versions.id"), nullable=True)
    version_created = Column(Boolean, nullable=False, default=False)
    
    # Relationships
    sync_job = relationship("MenuSyncJob", back_populates="sync_logs")
    mapping = relationship("POSMenuMapping", back_populates="sync_logs")
    menu_version = relationship("MenuVersion")
    
    # Indexes for queries and analytics
    __table_args__ = (
        Index('ix_menu_sync_logs_job_status', 'sync_job_id', 'status'),
        Index('ix_menu_sync_logs_entity', 'entity_type', 'aura_entity_id'),
        Index('ix_menu_sync_logs_conflict', 'status', 'conflict_type'),
        Index('ix_menu_sync_logs_time', 'created_at'),
    )

    def __repr__(self):
        return f"<MenuSyncLog(entity_type='{self.entity_type}', operation='{self.operation}', status='{self.status}')>"


class MenuSyncConflict(Base, TimestampMixin):
    """Tracks unresolved sync conflicts that require manual intervention"""
    __tablename__ = "menu_sync_conflicts"

    id = Column(Integer, primary_key=True, index=True)
    conflict_id = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False, unique=True, index=True)
    
    # Conflict context
    sync_job_id = Column(Integer, ForeignKey("menu_sync_jobs.id"), nullable=False)
    sync_log_id = Column(Integer, ForeignKey("menu_sync_logs.id"), nullable=False)
    mapping_id = Column(Integer, ForeignKey("pos_menu_mappings.id"), nullable=True)
    
    # Entity information
    entity_type = Column(String(50), nullable=False, index=True)
    aura_entity_id = Column(Integer, nullable=True)
    pos_entity_id = Column(String(255), nullable=True)
    
    # Conflict details
    conflict_type = Column(String(100), nullable=False, index=True)  # data_mismatch, deleted_entity, etc.
    conflict_description = Column(Text, nullable=True)
    severity = Column(String(20), nullable=False, default="medium")  # low, medium, high, critical
    
    # Conflicting data
    aura_current_data = Column(JSON, nullable=True)
    pos_current_data = Column(JSON, nullable=True)
    conflicting_fields = Column(JSON, nullable=True)  # List of fields with conflicts
    
    # Resolution
    status = Column(String(20), nullable=False, default="unresolved")  # unresolved, resolved, ignored
    resolution_strategy = Column(SQLEnum(ConflictResolution), nullable=True)
    resolved_by = Column(Integer, nullable=True)  # User ID who resolved conflict
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    
    # Metadata
    auto_resolvable = Column(Boolean, nullable=False, default=False)
    priority = Column(Integer, nullable=False, default=5)  # 1-10, higher = more urgent
    tags = Column(JSON, nullable=True)  # Custom tags for categorization
    
    # Relationships
    sync_job = relationship("MenuSyncJob")
    sync_log = relationship("MenuSyncLog")
    mapping = relationship("POSMenuMapping")
    
    # Indexes
    __table_args__ = (
        Index('ix_menu_sync_conflicts_unresolved', 'status', 'severity'),
        Index('ix_menu_sync_conflicts_entity', 'entity_type', 'aura_entity_id'),
        Index('ix_menu_sync_conflicts_priority', 'priority', 'created_at'),
    )
    
    def __repr__(self):
        return f"<MenuSyncConflict(conflict_type='{self.conflict_type}', status='{self.status}', severity='{self.severity}')>"


class MenuSyncConfig(Base, TimestampMixin):
    """Configuration for menu synchronization per POS integration"""
    __tablename__ = "menu_sync_configs"

    id = Column(Integer, primary_key=True, index=True)
    pos_integration_id = Column(Integer, ForeignKey("pos_integrations.id"), nullable=False, unique=True)
    
    # Global sync settings
    sync_enabled = Column(Boolean, nullable=False, default=True)
    default_sync_direction = Column(SQLEnum(SyncDirection), nullable=False, default=SyncDirection.BIDIRECTIONAL)
    default_conflict_resolution = Column(SQLEnum(ConflictResolution), nullable=False, default=ConflictResolution.MANUAL)
    
    # Scheduling
    auto_sync_enabled = Column(Boolean, nullable=False, default=False)
    sync_frequency_minutes = Column(Integer, nullable=True)  # Auto-sync interval
    sync_time_windows = Column(JSON, nullable=True)  # Allowed sync time windows
    max_concurrent_jobs = Column(Integer, nullable=False, default=1)
    
    # Entity-specific settings
    sync_categories = Column(Boolean, nullable=False, default=True)
    sync_items = Column(Boolean, nullable=False, default=True)
    sync_modifiers = Column(Boolean, nullable=False, default=True)
    sync_pricing = Column(Boolean, nullable=False, default=True)
    sync_availability = Column(Boolean, nullable=False, default=True)
    
    # Data handling
    create_missing_categories = Column(Boolean, nullable=False, default=True)
    preserve_aura_customizations = Column(Boolean, nullable=False, default=True)
    backup_before_sync = Column(Boolean, nullable=False, default=True)
    max_batch_size = Column(Integer, nullable=False, default=100)
    
    # Versioning integration
    create_version_on_pull = Column(Boolean, nullable=False, default=True)
    version_name_template = Column(String(200), nullable=True)  # Template for auto-generated version names
    
    # Notification settings
    notify_on_conflicts = Column(Boolean, nullable=False, default=True)
    notify_on_errors = Column(Boolean, nullable=False, default=True)
    notification_emails = Column(JSON, nullable=True)  # List of email addresses
    
    # Advanced settings
    field_mappings = Column(JSON, nullable=True)  # Custom field mappings between systems
    transformation_rules = Column(JSON, nullable=True)  # Data transformation rules
    validation_rules = Column(JSON, nullable=True)  # Custom validation rules
    
    # Performance settings
    rate_limit_requests = Column(Integer, nullable=True)  # Max requests per minute to POS
    timeout_seconds = Column(Integer, nullable=False, default=30)
    retry_failed_operations = Column(Boolean, nullable=False, default=True)
    
    # Relationships
    pos_integration = relationship("POSIntegration")
    
    def __repr__(self):
        return f"<MenuSyncConfig(pos_integration_id={self.pos_integration_id}, sync_enabled={self.sync_enabled})>"


class MenuSyncStatistics(Base, TimestampMixin):
    """Aggregated statistics for menu synchronization performance and health"""
    __tablename__ = "menu_sync_statistics"

    id = Column(Integer, primary_key=True, index=True)
    pos_integration_id = Column(Integer, ForeignKey("pos_integrations.id"), nullable=False)
    
    # Time period for statistics
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    period_type = Column(String(20), nullable=False)  # hour, day, week, month
    
    # Job statistics
    total_jobs = Column(Integer, nullable=False, default=0)
    successful_jobs = Column(Integer, nullable=False, default=0)
    failed_jobs = Column(Integer, nullable=False, default=0)
    avg_job_duration_seconds = Column(Float, nullable=True)
    
    # Entity statistics
    total_entities_synced = Column(Integer, nullable=False, default=0)
    categories_synced = Column(Integer, nullable=False, default=0)
    items_synced = Column(Integer, nullable=False, default=0)
    modifiers_synced = Column(Integer, nullable=False, default=0)
    
    # Direction statistics
    push_operations = Column(Integer, nullable=False, default=0)
    pull_operations = Column(Integer, nullable=False, default=0)
    
    # Conflict statistics
    total_conflicts = Column(Integer, nullable=False, default=0)
    resolved_conflicts = Column(Integer, nullable=False, default=0)
    unresolved_conflicts = Column(Integer, nullable=False, default=0)
    
    # Performance metrics
    avg_sync_time_per_entity_ms = Column(Float, nullable=True)
    success_rate_percentage = Column(Float, nullable=True)
    error_rate_percentage = Column(Float, nullable=True)
    
    # Data quality metrics
    data_consistency_score = Column(Float, nullable=True)  # 0-100 score
    last_successful_full_sync = Column(DateTime, nullable=True)
    
    # Relationships
    pos_integration = relationship("POSIntegration")
    
    # Indexes
    __table_args__ = (
        Index('ix_menu_sync_stats_period', 'pos_integration_id', 'period_type', 'period_end'),
        Index('ix_menu_sync_stats_performance', 'success_rate_percentage', 'error_rate_percentage'),
    )
    
    def __repr__(self):
        return f"<MenuSyncStatistics(period={self.period_type}, success_rate={self.success_rate_percentage}%)>"