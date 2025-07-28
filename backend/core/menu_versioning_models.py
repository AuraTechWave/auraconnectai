# backend/core/menu_versioning_models.py

from sqlalchemy import (Column, Integer, String, ForeignKey, DateTime,
                        Float, Text, Boolean, JSON, Enum as SQLEnum)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from backend.core.database import Base
from backend.core.mixins import TimestampMixin
from enum import Enum
from datetime import datetime
import uuid
import json


class VersionType(str, Enum):
    """Types of menu versions"""
    MANUAL = "manual"           # User-created version
    SCHEDULED = "scheduled"     # Scheduled automatic version
    ROLLBACK = "rollback"       # Rollback to previous version
    MIGRATION = "migration"     # System migration version
    AUTO_SAVE = "auto_save"     # Automatic periodic save


class ChangeType(str, Enum):
    """Types of changes in audit trail"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ACTIVATE = "activate"
    DEACTIVATE = "deactivate"
    PRICE_CHANGE = "price_change"
    AVAILABILITY_CHANGE = "availability_change"
    CATEGORY_CHANGE = "category_change"
    MODIFIER_CHANGE = "modifier_change"


class MenuVersion(Base, TimestampMixin):
    """Menu versions for tracking changes over time"""
    __tablename__ = "menu_versions"

    id = Column(Integer, primary_key=True, index=True)
    version_number = Column(String(50), nullable=False, index=True)  # e.g., "v1.0.0", "2024-01-15-001"
    version_name = Column(String(200), nullable=True)  # Human-readable name
    description = Column(Text, nullable=True)
    version_type = Column(SQLEnum(VersionType), nullable=False, default=VersionType.MANUAL)
    
    # Version status
    is_active = Column(Boolean, nullable=False, default=False)  # Only one version can be active
    is_published = Column(Boolean, nullable=False, default=False)
    published_at = Column(DateTime, nullable=True)
    scheduled_publish_at = Column(DateTime, nullable=True)
    
    # Metadata
    created_by = Column(Integer, nullable=False)  # User ID who created this version
    total_items = Column(Integer, nullable=False, default=0)
    total_categories = Column(Integer, nullable=False, default=0)
    total_modifiers = Column(Integer, nullable=False, default=0)
    
    # Version comparison data
    changes_summary = Column(JSON, nullable=True)  # Summary of changes from previous version
    parent_version_id = Column(Integer, ForeignKey("menu_versions.id"), nullable=True)
    
    # Soft delete
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    parent_version = relationship("MenuVersion", remote_side=[id])
    child_versions = relationship("MenuVersion", back_populates="parent_version")
    category_versions = relationship("MenuCategoryVersion", back_populates="menu_version")
    item_versions = relationship("MenuItemVersion", back_populates="menu_version")
    modifier_versions = relationship("ModifierGroupVersion", back_populates="menu_version")
    audit_entries = relationship("MenuAuditLog", back_populates="menu_version")

    def __repr__(self):
        return f"<MenuVersion(id={self.id}, version='{self.version_number}', active={self.is_active})>"


class MenuCategoryVersion(Base, TimestampMixin):
    """Versioned menu categories"""
    __tablename__ = "menu_category_versions"

    id = Column(Integer, primary_key=True, index=True)
    menu_version_id = Column(Integer, ForeignKey("menu_versions.id"), nullable=False)
    original_category_id = Column(Integer, ForeignKey("menu_categories.id"), nullable=False)
    
    # Category data (snapshot)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    display_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    parent_category_id = Column(Integer, nullable=True)  # Reference to original parent
    image_url = Column(String(500), nullable=True)
    
    # Version metadata
    change_type = Column(SQLEnum(ChangeType), nullable=False)
    change_summary = Column(Text, nullable=True)
    changed_fields = Column(JSON, nullable=True)  # List of fields that changed
    
    # Relationships
    menu_version = relationship("MenuVersion", back_populates="category_versions")
    original_category = relationship("MenuCategory")

    def __repr__(self):
        return f"<MenuCategoryVersion(id={self.id}, name='{self.name}', version_id={self.menu_version_id})>"


class MenuItemVersion(Base, TimestampMixin):
    """Versioned menu items"""
    __tablename__ = "menu_item_versions"

    id = Column(Integer, primary_key=True, index=True)
    menu_version_id = Column(Integer, ForeignKey("menu_versions.id"), nullable=False)
    original_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=False)
    
    # Item data (snapshot)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    category_id = Column(Integer, nullable=False)
    sku = Column(String(50), nullable=True)
    
    # Status and availability
    is_active = Column(Boolean, nullable=False, default=True)
    is_available = Column(Boolean, nullable=False, default=True)
    availability_start_time = Column(String(8), nullable=True)
    availability_end_time = Column(String(8), nullable=True)
    
    # Nutritional and dietary info
    calories = Column(Integer, nullable=True)
    dietary_tags = Column(JSON, nullable=True)
    allergen_info = Column(JSON, nullable=True)
    
    # Image and display
    image_url = Column(String(500), nullable=True)
    display_order = Column(Integer, nullable=False, default=0)
    
    # Preparation info
    prep_time_minutes = Column(Integer, nullable=True)
    cooking_instructions = Column(Text, nullable=True)
    
    # Version metadata
    change_type = Column(SQLEnum(ChangeType), nullable=False)
    change_summary = Column(Text, nullable=True)
    changed_fields = Column(JSON, nullable=True)
    price_history = Column(JSON, nullable=True)  # Track price changes
    
    # Relationships
    menu_version = relationship("MenuVersion", back_populates="item_versions")
    original_item = relationship("MenuItem")
    modifier_versions = relationship("MenuItemModifierVersion", back_populates="menu_item_version")

    def __repr__(self):
        return f"<MenuItemVersion(id={self.id}, name='{self.name}', price={self.price}, version_id={self.menu_version_id})>"


class ModifierGroupVersion(Base, TimestampMixin):
    """Versioned modifier groups"""
    __tablename__ = "modifier_group_versions"

    id = Column(Integer, primary_key=True, index=True)
    menu_version_id = Column(Integer, ForeignKey("menu_versions.id"), nullable=False)
    original_group_id = Column(Integer, ForeignKey("modifier_groups.id"), nullable=False)
    
    # Group data (snapshot)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    selection_type = Column(String(20), nullable=False, default="single")  # single, multiple
    is_required = Column(Boolean, nullable=False, default=False)
    min_selections = Column(Integer, nullable=False, default=0)
    max_selections = Column(Integer, nullable=True)
    display_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Version metadata
    change_type = Column(SQLEnum(ChangeType), nullable=False)
    change_summary = Column(Text, nullable=True)
    changed_fields = Column(JSON, nullable=True)
    
    # Relationships
    menu_version = relationship("MenuVersion", back_populates="modifier_versions")
    original_group = relationship("ModifierGroup")
    modifier_versions = relationship("ModifierVersion", back_populates="modifier_group_version")

    def __repr__(self):
        return f"<ModifierGroupVersion(id={self.id}, name='{self.name}', version_id={self.menu_version_id})>"


class ModifierVersion(Base, TimestampMixin):
    """Versioned individual modifiers"""
    __tablename__ = "modifier_versions"

    id = Column(Integer, primary_key=True, index=True)
    modifier_group_version_id = Column(Integer, ForeignKey("modifier_group_versions.id"), nullable=False)
    original_modifier_id = Column(Integer, ForeignKey("modifiers.id"), nullable=False)
    
    # Modifier data (snapshot)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    price_adjustment = Column(Float, nullable=False, default=0.0)
    is_active = Column(Boolean, nullable=False, default=True)
    display_order = Column(Integer, nullable=False, default=0)
    
    # Version metadata
    change_type = Column(SQLEnum(ChangeType), nullable=False)
    change_summary = Column(Text, nullable=True)
    changed_fields = Column(JSON, nullable=True)
    
    # Relationships
    modifier_group_version = relationship("ModifierGroupVersion", back_populates="modifier_versions")
    original_modifier = relationship("Modifier")

    def __repr__(self):
        return f"<ModifierVersion(id={self.id}, name='{self.name}', price_adj={self.price_adjustment})>"


class MenuItemModifierVersion(Base, TimestampMixin):
    """Versioned associations between menu items and modifier groups"""
    __tablename__ = "menu_item_modifier_versions"

    id = Column(Integer, primary_key=True, index=True)
    menu_item_version_id = Column(Integer, ForeignKey("menu_item_versions.id"), nullable=False)
    modifier_group_version_id = Column(Integer, ForeignKey("modifier_group_versions.id"), nullable=False)
    original_association_id = Column(Integer, ForeignKey("menu_item_modifiers.id"), nullable=True)
    
    # Association data
    is_required = Column(Boolean, nullable=False, default=False)
    display_order = Column(Integer, nullable=False, default=0)
    
    # Version metadata
    change_type = Column(SQLEnum(ChangeType), nullable=False)
    
    # Relationships
    menu_item_version = relationship("MenuItemVersion", back_populates="modifier_versions")
    modifier_group_version = relationship("ModifierGroupVersion")

    def __repr__(self):
        return f"<MenuItemModifierVersion(item_version_id={self.menu_item_version_id}, group_version_id={self.modifier_group_version_id})>"


class MenuAuditLog(Base, TimestampMixin):
    """Comprehensive audit trail for menu changes"""
    __tablename__ = "menu_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    menu_version_id = Column(Integer, ForeignKey("menu_versions.id"), nullable=True)
    
    # Action details
    action = Column(String(50), nullable=False)  # create_version, publish_version, rollback, etc.
    entity_type = Column(String(50), nullable=False)  # menu_item, category, modifier, etc.
    entity_id = Column(Integer, nullable=True)  # ID of the affected entity
    entity_name = Column(String(200), nullable=True)  # Name for easier identification
    
    # Change details
    change_type = Column(SQLEnum(ChangeType), nullable=False)
    old_values = Column(JSON, nullable=True)  # Previous values
    new_values = Column(JSON, nullable=True)  # New values
    changed_fields = Column(JSON, nullable=True)  # List of changed field names
    change_summary = Column(Text, nullable=True)  # Human-readable summary
    
    # Context
    user_id = Column(Integer, nullable=False)  # Who made the change
    user_role = Column(String(50), nullable=True)  # Role at time of change
    ip_address = Column(String(45), nullable=True)  # IPv4/IPv6 address
    user_agent = Column(Text, nullable=True)  # Browser/client info
    session_id = Column(String(100), nullable=True)  # Session identifier
    
    # Additional metadata
    batch_id = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=True)  # Group related changes
    parent_log_id = Column(Integer, ForeignKey("menu_audit_logs.id"), nullable=True)  # For nested changes
    tags = Column(JSON, nullable=True)  # Custom tags for filtering
    
    # Relationships
    menu_version = relationship("MenuVersion", back_populates="audit_entries")
    parent_log = relationship("MenuAuditLog", remote_side=[id])
    child_logs = relationship("MenuAuditLog", back_populates="parent_log")

    def __repr__(self):
        return f"<MenuAuditLog(id={self.id}, action='{self.action}', entity='{self.entity_type}', user={self.user_id})>"


class MenuVersionSchedule(Base, TimestampMixin):
    """Scheduled menu version activations"""
    __tablename__ = "menu_version_schedules"

    id = Column(Integer, primary_key=True, index=True)
    menu_version_id = Column(Integer, ForeignKey("menu_versions.id"), nullable=False)
    
    # Schedule details
    scheduled_at = Column(DateTime, nullable=False)
    timezone = Column(String(50), nullable=False, default="UTC")
    is_recurring = Column(Boolean, nullable=False, default=False)
    recurrence_pattern = Column(JSON, nullable=True)  # For recurring schedules
    
    # Status
    status = Column(String(20), nullable=False, default="pending")  # pending, executed, cancelled, failed
    executed_at = Column(DateTime, nullable=True)
    execution_result = Column(JSON, nullable=True)  # Result details
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    
    # Metadata
    created_by = Column(Integer, nullable=False)
    notes = Column(Text, nullable=True)
    
    # Relationships
    menu_version = relationship("MenuVersion")

    def __repr__(self):
        return f"<MenuVersionSchedule(id={self.id}, version_id={self.menu_version_id}, scheduled_at={self.scheduled_at})>"


class MenuVersionComparison(Base, TimestampMixin):
    """Cached comparison results between menu versions"""
    __tablename__ = "menu_version_comparisons"

    id = Column(Integer, primary_key=True, index=True)
    from_version_id = Column(Integer, ForeignKey("menu_versions.id"), nullable=False)
    to_version_id = Column(Integer, ForeignKey("menu_versions.id"), nullable=False)
    
    # Comparison results
    comparison_data = Column(JSON, nullable=False)  # Detailed diff data
    summary = Column(JSON, nullable=False)  # Summary statistics
    
    # Cache metadata
    generated_by = Column(Integer, nullable=False)
    expires_at = Column(DateTime, nullable=True)  # Cache expiration
    
    # Relationships
    from_version = relationship("MenuVersion", foreign_keys=[from_version_id])
    to_version = relationship("MenuVersion", foreign_keys=[to_version_id])

    def __repr__(self):
        return f"<MenuVersionComparison(from={self.from_version_id}, to={self.to_version_id})>"