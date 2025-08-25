"""
POS Migration Models

Database models for tracking POS migrations, jobs, and mapping rules.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column, Integer, String, DateTime, JSON, Boolean, 
    ForeignKey, Text, Float, Index, UniqueConstraint,
    CheckConstraint, event
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.dialects.postgresql import UUID
import uuid

from core.database import Base
from core.models import TimestampMixin, TenantMixin


class MigrationStatus(str, Enum):
    """Migration job status enum"""
    PENDING = "pending"
    ANALYZING = "analyzing"
    MAPPING = "mapping"
    VALIDATING = "validating"
    MIGRATING = "migrating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    ROLLBACK = "rollback"


class POSProvider(str, Enum):
    """Supported POS providers"""
    SQUARE = "square"
    CLOVER = "clover"
    TOAST = "toast"
    LIGHTSPEED = "lightspeed"
    SHOPIFY = "shopify"
    CUSTOM = "custom"


class DataEntityType(str, Enum):
    """Types of data entities to migrate"""
    MENU_ITEMS = "menu_items"
    CATEGORIES = "categories"
    MODIFIERS = "modifiers"
    CUSTOMERS = "customers"
    ORDERS = "orders"
    PAYMENTS = "payments"
    INVENTORY = "inventory"
    EMPLOYEES = "employees"
    TABLES = "tables"
    DISCOUNTS = "discounts"
    TAXES = "taxes"


class POSMigrationJob(Base, TimestampMixin, TenantMixin):
    """
    Main migration job tracking table.
    Stores migration configuration and status.
    """
    __tablename__ = "pos_migration_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_name = Column(String(255), nullable=False)
    source_provider = Column(String(50), nullable=False)
    target_provider = Column(String(50), default="auraconnect")
    
    # Authentication & Connection
    source_credentials = Column(JSON, nullable=False)  # Encrypted in service layer
    source_api_endpoint = Column(String(500))
    
    # Migration Configuration
    entities_to_migrate = Column(JSON, nullable=False)  # List of DataEntityType
    mapping_rules = Column(JSON)  # Custom field mappings
    transformation_rules = Column(JSON)  # Data transformation rules
    validation_rules = Column(JSON)  # Validation criteria
    
    # Status & Progress
    status = Column(String(20), default=MigrationStatus.PENDING)
    progress_percentage = Column(Float, default=0.0)
    current_entity = Column(String(50))
    entities_completed = Column(JSON, default=list)
    
    # Statistics
    total_records = Column(Integer, default=0)
    records_processed = Column(Integer, default=0)
    records_succeeded = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)
    records_skipped = Column(Integer, default=0)
    
    # Timing
    scheduled_at = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    estimated_completion = Column(DateTime)
    
    # Error Handling
    error_count = Column(Integer, default=0)
    last_error = Column(Text)
    error_details = Column(JSON)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Audit & Compliance
    created_by = Column(Integer, ForeignKey("users.id"))
    approved_by = Column(Integer, ForeignKey("users.id"))
    approval_notes = Column(Text)
    compliance_checks = Column(JSON)
    
    # Performance
    batch_size = Column(Integer, default=100)
    rate_limit = Column(Integer)  # Requests per minute
    parallel_workers = Column(Integer, default=1)
    
    # Rollback Support
    rollback_enabled = Column(Boolean, default=True)
    rollback_checkpoint = Column(JSON)
    
    # Relationships
    mappings = relationship("DataMapping", back_populates="migration_job", cascade="all, delete-orphan")
    logs = relationship("MigrationLog", back_populates="migration_job", cascade="all, delete-orphan")
    validations = relationship("ValidationResult", back_populates="migration_job", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index("idx_migration_status_restaurant", "status", "restaurant_id"),
        Index("idx_migration_created_at", "created_at"),
        CheckConstraint("progress_percentage >= 0 AND progress_percentage <= 100"),
    )
    
    @validates("source_provider")
    def validate_provider(self, key, value):
        """Validate POS provider"""
        if value not in [p.value for p in POSProvider]:
            raise ValueError(f"Unsupported POS provider: {value}")
        return value


class DataMapping(Base, TimestampMixin):
    """
    Stores field mapping rules between source and target systems.
    Supports AI-suggested mappings with confidence scores.
    """
    __tablename__ = "pos_data_mappings"
    
    id = Column(Integer, primary_key=True)
    migration_job_id = Column(UUID(as_uuid=True), ForeignKey("pos_migration_jobs.id"))
    entity_type = Column(String(50), nullable=False)
    
    # Mapping Configuration
    source_field = Column(String(255), nullable=False)
    target_field = Column(String(255), nullable=False)
    transformation_function = Column(String(100))  # e.g., "uppercase", "date_format"
    default_value = Column(String(500))
    
    # AI Assistance
    ai_suggested = Column(Boolean, default=False)
    confidence_score = Column(Float)  # 0.0 to 1.0
    user_approved = Column(Boolean, default=False)
    
    # Validation
    is_required = Column(Boolean, default=False)
    validation_regex = Column(String(500))
    data_type = Column(String(50))
    
    # Relationships
    migration_job = relationship("POSMigrationJob", back_populates="mappings")
    
    __table_args__ = (
        UniqueConstraint("migration_job_id", "entity_type", "source_field", name="uq_mapping"),
        Index("idx_mapping_entity", "migration_job_id", "entity_type"),
    )


class MigrationLog(Base, TimestampMixin):
    """
    Detailed audit log for migration operations.
    Tracks every action for compliance and debugging.
    """
    __tablename__ = "pos_migration_logs"
    
    id = Column(Integer, primary_key=True)
    migration_job_id = Column(UUID(as_uuid=True), ForeignKey("pos_migration_jobs.id"))
    
    # Log Details
    log_level = Column(String(20))  # INFO, WARNING, ERROR, DEBUG
    entity_type = Column(String(50))
    entity_id = Column(String(255))  # Source system ID
    action = Column(String(100))  # fetch, transform, validate, insert, update
    
    # Message & Data
    message = Column(Text, nullable=False)
    source_data = Column(JSON)
    transformed_data = Column(JSON)
    
    # Error Information
    error_type = Column(String(100))
    error_message = Column(Text)
    stack_trace = Column(Text)
    
    # Performance Metrics
    duration_ms = Column(Integer)
    memory_usage_mb = Column(Float)
    
    # Relationships
    migration_job = relationship("POSMigrationJob", back_populates="logs")
    
    __table_args__ = (
        Index("idx_log_job_level", "migration_job_id", "log_level"),
        Index("idx_log_created", "created_at"),
    )


class ValidationResult(Base, TimestampMixin):
    """
    Stores validation results for migrated data.
    Helps ensure data integrity and compliance.
    """
    __tablename__ = "pos_validation_results"
    
    id = Column(Integer, primary_key=True)
    migration_job_id = Column(UUID(as_uuid=True), ForeignKey("pos_migration_jobs.id"))
    
    # Validation Context
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(255))
    validation_type = Column(String(100))  # schema, business_rule, referential_integrity
    
    # Results
    is_valid = Column(Boolean, nullable=False)
    validation_errors = Column(JSON)
    warnings = Column(JSON)
    
    # Data Snapshot
    validated_data = Column(JSON)
    expected_values = Column(JSON)
    actual_values = Column(JSON)
    
    # Remediation
    auto_fixed = Column(Boolean, default=False)
    fix_applied = Column(JSON)
    manual_review_required = Column(Boolean, default=False)
    
    # Relationships
    migration_job = relationship("POSMigrationJob", back_populates="validations")
    
    __table_args__ = (
        Index("idx_validation_job_type", "migration_job_id", "entity_type"),
        Index("idx_validation_invalid", "migration_job_id", "is_valid"),
    )


class MigrationTemplate(Base, TimestampMixin, TenantMixin):
    """
    Reusable migration templates for common POS transitions.
    Stores best practices and optimized configurations.
    """
    __tablename__ = "pos_migration_templates"
    
    id = Column(Integer, primary_key=True)
    template_name = Column(String(255), nullable=False, unique=True)
    source_provider = Column(String(50), nullable=False)
    target_provider = Column(String(50), default="auraconnect")
    
    # Template Configuration
    default_mappings = Column(JSON, nullable=False)
    transformation_rules = Column(JSON)
    validation_rules = Column(JSON)
    recommended_batch_size = Column(Integer)
    
    # Metadata
    description = Column(Text)
    version = Column(String(20))
    is_active = Column(Boolean, default=True)
    usage_count = Column(Integer, default=0)
    success_rate = Column(Float)
    
    # Best Practices
    common_issues = Column(JSON)
    resolution_steps = Column(JSON)
    performance_tips = Column(JSON)
    
    __table_args__ = (
        Index("idx_template_provider", "source_provider", "target_provider"),
    )


# Event listeners for audit trail
@event.listens_for(POSMigrationJob, "before_update")
def migration_job_before_update(mapper, connection, target):
    """Track status changes"""
    if target.status == MigrationStatus.MIGRATING and not target.started_at:
        target.started_at = datetime.utcnow()
    elif target.status in [MigrationStatus.COMPLETED, MigrationStatus.FAILED]:
        target.completed_at = datetime.utcnow()