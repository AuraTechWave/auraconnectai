# backend/modules/settings/models/settings_models.py

"""
Comprehensive settings and configuration models.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    Boolean,
    Enum as SQLEnum,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional

from core.database import Base, TimestampMixin


class SettingCategory(str, Enum):
    """Categories for settings"""

    GENERAL = "general"
    OPERATIONS = "operations"
    PAYMENT = "payment"
    POS_INTEGRATION = "pos_integration"
    NOTIFICATIONS = "notifications"
    SECURITY = "security"
    DISPLAY = "display"
    FEATURES = "features"
    API = "api"
    COMPLIANCE = "compliance"


class SettingType(str, Enum):
    """Data types for settings"""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    JSON = "json"
    DATETIME = "datetime"
    ENUM = "enum"
    FILE = "file"
    SECRET = "secret"


class SettingScope(str, Enum):
    """Scope levels for settings"""

    SYSTEM = "system"  # Global system settings
    RESTAURANT = "restaurant"  # Restaurant-specific
    LOCATION = "location"  # Location-specific
    USER = "user"  # User preferences


class Setting(Base, TimestampMixin):
    """Core settings storage"""

    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)

    # Setting identification
    key = Column(String(100), nullable=False, index=True)
    category = Column(SQLEnum(SettingCategory), nullable=False)
    scope = Column(SQLEnum(SettingScope), nullable=False)

    # Scope references
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Value storage
    value = Column(Text, nullable=False)  # Stored as JSON string
    value_type = Column(SQLEnum(SettingType), nullable=False)

    # Metadata
    label = Column(String(200), nullable=False)
    description = Column(Text)
    is_sensitive = Column(Boolean, default=False)  # If true, value is encrypted
    is_public = Column(Boolean, default=False)  # If true, can be accessed without auth

    # Validation
    validation_rules = Column(JSON, default={})  # JSON schema or custom rules
    allowed_values = Column(JSON, default=[])  # For enum types
    default_value = Column(Text)  # Default as JSON string

    # UI hints
    ui_config = Column(JSON, default={})  # Display configuration
    sort_order = Column(Integer, default=0)

    # Audit
    modified_by_id = Column(Integer, ForeignKey("users.id"))
    modified_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    restaurant = relationship("Restaurant", foreign_keys=[restaurant_id])
    location = relationship("Location", foreign_keys=[location_id])
    user = relationship("User", foreign_keys=[user_id])
    modified_by = relationship("User", foreign_keys=[modified_by_id])

    # Ensure unique settings per scope
    __table_args__ = (
        UniqueConstraint(
            "key",
            "scope",
            "restaurant_id",
            "location_id",
            "user_id",
            name="uq_setting_key_scope",
        ),
        Index("idx_setting_lookup", "key", "scope", "restaurant_id"),
    )


class SettingDefinition(Base, TimestampMixin):
    """Definition of available settings"""

    __tablename__ = "setting_definitions"

    id = Column(Integer, primary_key=True)

    # Setting definition
    key = Column(String(100), unique=True, nullable=False)
    category = Column(SQLEnum(SettingCategory), nullable=False)
    scope = Column(SQLEnum(SettingScope), nullable=False)
    value_type = Column(SQLEnum(SettingType), nullable=False)

    # Display information
    label = Column(String(200), nullable=False)
    description = Column(Text)
    help_text = Column(Text)

    # Default and validation
    default_value = Column(Text)  # JSON string
    validation_rules = Column(JSON, default={})
    allowed_values = Column(JSON, default=[])

    # Requirements
    is_required = Column(Boolean, default=False)
    is_sensitive = Column(Boolean, default=False)
    requires_restart = Column(Boolean, default=False)

    # Dependencies
    depends_on = Column(JSON, default=[])  # List of other setting keys
    conflicts_with = Column(JSON, default=[])

    # UI configuration
    ui_config = Column(JSON, default={})
    sort_order = Column(Integer, default=0)

    # Feature flags
    is_active = Column(Boolean, default=True)
    is_deprecated = Column(Boolean, default=False)
    deprecation_message = Column(Text)

    # Versioning
    introduced_version = Column(String(20))
    deprecated_version = Column(String(20))
    removed_version = Column(String(20))


class SettingGroup(Base, TimestampMixin):
    """Grouping of related settings"""

    __tablename__ = "setting_groups"

    id = Column(Integer, primary_key=True)

    name = Column(String(100), unique=True, nullable=False)
    label = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(SQLEnum(SettingCategory), nullable=False)

    # Group configuration
    settings = Column(JSON, default=[])  # List of setting keys
    ui_config = Column(JSON, default={})
    sort_order = Column(Integer, default=0)

    # Access control
    required_permission = Column(String(100))
    is_advanced = Column(Boolean, default=False)


class SettingHistory(Base):
    """Audit log for setting changes"""

    __tablename__ = "setting_history"

    id = Column(Integer, primary_key=True)

    # Reference to setting
    setting_key = Column(String(100), nullable=False)
    scope = Column(SQLEnum(SettingScope), nullable=False)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Change information
    old_value = Column(Text)  # Encrypted if sensitive
    new_value = Column(Text)  # Encrypted if sensitive
    change_type = Column(String(20))  # create, update, delete

    # Metadata
    changed_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    change_reason = Column(Text)
    ip_address = Column(String(45))
    user_agent = Column(String(255))

    # Relationships
    changed_by = relationship("User", foreign_keys=[changed_by_id])

    # Index for efficient history queries
    __table_args__ = (
        Index("idx_setting_history_lookup", "setting_key", "changed_at"),
        Index("idx_setting_history_scope", "scope", "restaurant_id", "changed_at"),
    )


class ConfigurationTemplate(Base, TimestampMixin):
    """Pre-defined configuration templates"""

    __tablename__ = "configuration_templates"

    id = Column(Integer, primary_key=True)

    name = Column(String(100), unique=True, nullable=False)
    label = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(String(50), nullable=False)

    # Template data
    settings = Column(JSON, nullable=False)  # Key-value pairs
    scope = Column(SQLEnum(SettingScope), nullable=False)

    # Usage
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    usage_count = Column(Integer, default=0)

    # Metadata
    created_by_id = Column(Integer, ForeignKey("users.id"))
    tags = Column(JSON, default=[])

    # Relationships
    created_by = relationship("User")


class FeatureFlag(Base, TimestampMixin):
    """Feature flag management"""

    __tablename__ = "feature_flags"

    id = Column(Integer, primary_key=True)

    # Flag identification
    key = Column(String(100), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # Flag state
    is_enabled = Column(Boolean, default=False)
    rollout_percentage = Column(Integer, default=0)  # 0-100

    # Targeting
    enabled_restaurants = Column(JSON, default=[])  # List of restaurant IDs
    enabled_users = Column(JSON, default=[])  # List of user IDs
    targeting_rules = Column(JSON, default={})  # Complex targeting rules

    # Schedule
    enabled_from = Column(DateTime)
    enabled_until = Column(DateTime)

    # Dependencies
    depends_on = Column(JSON, default=[])  # Other feature flags

    # Metadata
    created_by_id = Column(Integer, ForeignKey("users.id"))
    tags = Column(JSON, default=[])

    # Relationships
    created_by = relationship("User")


class APIKey(Base, TimestampMixin):
    """API key management"""

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True)

    # Key information
    key_hash = Column(String(255), unique=True, nullable=False)  # Hashed key
    key_prefix = Column(
        String(10), nullable=False
    )  # First few chars for identification
    name = Column(String(100), nullable=False)
    description = Column(Text)

    # Ownership
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Permissions
    scopes = Column(JSON, default=[])  # List of allowed scopes
    allowed_ips = Column(JSON, default=[])  # IP whitelist

    # Status
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime)
    usage_count = Column(Integer, default=0)

    # Expiration
    expires_at = Column(DateTime)

    # Rate limiting
    rate_limit_per_hour = Column(Integer)
    rate_limit_per_day = Column(Integer)

    # Relationships
    restaurant = relationship("Restaurant")
    created_by = relationship("User")

    # Index for efficient key lookup
    __table_args__ = (Index("idx_api_key_lookup", "key_prefix", "is_active"),)


class Webhook(Base, TimestampMixin):
    """Webhook configuration"""

    __tablename__ = "webhooks"

    id = Column(Integer, primary_key=True)

    # Webhook details
    name = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    description = Column(Text)

    # Ownership
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Events
    events = Column(JSON, nullable=False)  # List of event types

    # Configuration
    secret = Column(String(255))  # For signature verification
    headers = Column(JSON, default={})  # Custom headers

    # Retry configuration
    max_retries = Column(Integer, default=3)
    retry_delay_seconds = Column(Integer, default=60)
    timeout_seconds = Column(Integer, default=30)

    # Status
    is_active = Column(Boolean, default=True)
    last_triggered_at = Column(DateTime)
    last_success_at = Column(DateTime)
    last_failure_at = Column(DateTime)
    failure_count = Column(Integer, default=0)

    # Relationships
    restaurant = relationship("Restaurant")
    created_by = relationship("User")
