"""
UI-specific schemas for settings configuration interface.

These schemas are optimized for frontend consumption and UI rendering.
"""

from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum

from ..models.settings_models import SettingCategory, SettingType, SettingScope


class UIFieldType(str, Enum):
    """UI field types for rendering"""
    TEXT = "text"
    NUMBER = "number"
    TOGGLE = "toggle"
    SELECT = "select"
    MULTISELECT = "multiselect"
    TEXTAREA = "textarea"
    JSON = "json"
    DATE = "date"
    TIME = "time"
    DATETIME = "datetime"
    COLOR = "color"
    FILE = "file"
    PASSWORD = "password"
    EMAIL = "email"
    URL = "url"
    PHONE = "phone"
    CURRENCY = "currency"
    PERCENTAGE = "percentage"


class SettingUIField(BaseModel):
    """UI field configuration for a setting"""
    
    key: str
    label: str
    description: Optional[str]
    help_text: Optional[str]
    value: Any
    default_value: Any
    field_type: UIFieldType
    is_required: bool = False
    is_sensitive: bool = False
    is_readonly: bool = False
    is_advanced: bool = False
    
    # Validation
    validation_rules: Dict[str, Any] = {}
    allowed_values: Optional[List[Any]] = None
    
    # UI hints
    placeholder: Optional[str] = None
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    icon: Optional[str] = None
    columns: int = Field(12, ge=1, le=12)  # Grid columns
    
    # Dependencies
    depends_on: Optional[Dict[str, Any]] = None
    enables: Optional[List[str]] = None
    disables: Optional[List[str]] = None
    
    # State
    is_modified: bool = False
    has_error: bool = False
    error_message: Optional[str] = None
    requires_restart: bool = False


class SettingsSection(BaseModel):
    """A section/group of related settings"""
    
    id: str
    name: str
    label: str
    description: Optional[str]
    icon: Optional[str]
    category: SettingCategory
    settings: List[SettingUIField]
    is_expanded: bool = True
    is_advanced: bool = False
    required_permission: Optional[str]
    sort_order: int = 0


class SettingsSectionResponse(BaseModel):
    """Response for settings sections"""
    
    sections: List[SettingsSection]
    total_settings: int
    modified_count: int
    has_errors: bool


class SettingsUIResponse(BaseModel):
    """Complete UI response for settings dashboard"""
    
    categories: List[Dict[str, Any]]  # Category metadata
    sections: List[SettingsSection]
    metadata: Dict[str, Any]
    has_unsaved_changes: bool
    requires_restart: List[str]  # Settings that need restart
    last_saved: Optional[datetime]
    can_edit: bool
    can_reset: bool


class ValidationError(BaseModel):
    """Validation error detail"""
    
    field: str
    message: str
    code: str
    context: Optional[Dict[str, Any]] = None


class SettingsValidationResponse(BaseModel):
    """Validation response"""
    
    is_valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationError]
    dependencies_met: bool
    conflicts_detected: List[Dict[str, Any]]


class SettingChange(BaseModel):
    """A single setting change"""
    
    key: str
    value: Any
    previous_value: Optional[Any] = None
    scope: Optional[SettingScope] = None
    category: Optional[SettingCategory] = None


class SettingsBulkOperationRequest(BaseModel):
    """Bulk settings operation request"""
    
    settings: List[SettingChange]
    scope: SettingScope
    restaurant_id: Optional[int] = None
    location_id: Optional[int] = None
    user_id: Optional[int] = None
    validate_only: bool = False
    reason: Optional[str] = None


class SettingsBulkOperationResponse(BaseModel):
    """Bulk operation response"""
    
    success: bool
    processed: int
    failed: int
    errors: List[ValidationError]
    changes: List[SettingChange]
    requires_restart: List[str]
    rollback_performed: bool = False


class SettingsResetRequest(BaseModel):
    """Reset settings request"""
    
    scope: SettingScope
    category: Optional[SettingCategory] = None
    setting_keys: Optional[List[str]] = None
    restaurant_id: Optional[int] = None
    location_id: Optional[int] = None
    user_id: Optional[int] = None
    confirm: bool = Field(..., description="Must be true to execute")


class SettingsExportRequest(BaseModel):
    """Export settings request"""
    
    scope: SettingScope
    categories: Optional[List[SettingCategory]] = None
    include_sensitive: bool = False
    include_metadata: bool = True
    format: str = Field("json", enum=["json", "yaml", "env"])
    restaurant_id: Optional[int] = None


class SettingsImportRequest(BaseModel):
    """Import settings request"""
    
    data: Dict[str, Any]
    scope: SettingScope
    merge_strategy: str = Field("override", enum=["override", "merge", "skip_existing"])
    validate_only: bool = False
    restaurant_id: Optional[int] = None


class SettingsSearchRequest(BaseModel):
    """Search settings request"""
    
    query: str = Field(..., min_length=2)
    scope: Optional[SettingScope] = None
    categories: Optional[List[SettingCategory]] = None
    include_advanced: bool = False
    limit: int = Field(50, ge=1, le=100)


class SettingDifference(BaseModel):
    """Difference between current and template setting"""
    
    key: str
    label: str
    current_value: Any
    template_value: Any
    is_missing: bool = False
    is_extra: bool = False
    category: SettingCategory


class SettingsComparisonResponse(BaseModel):
    """Comparison with template response"""
    
    template_name: str
    template_description: Optional[str]
    differences: List[SettingDifference]
    missing_count: int
    extra_count: int
    different_count: int
    can_apply: bool


class UIMetadataResponse(BaseModel):
    """UI metadata for settings interface"""
    
    categories: List[Dict[str, Any]]
    scopes: List[Dict[str, Any]]
    field_types: List[Dict[str, Any]]
    validation_rules: Dict[str, Any]
    presets: List[Dict[str, Any]]
    permissions: Dict[str, bool]
    feature_flags: Dict[str, bool]
    ui_config: Dict[str, Any]


class SettingHistoryEntry(BaseModel):
    """Setting history entry for UI"""
    
    id: int
    setting_key: str
    old_value: Any
    new_value: Any
    changed_by: str
    changed_at: datetime
    change_reason: Optional[str]
    
    class Config:
        from_attributes = True


class PendingChange(BaseModel):
    """A pending setting change"""
    
    key: str
    label: str
    current_value: Any
    new_value: Any
    requires_restart: bool
    requires_confirmation: bool
    impact_description: Optional[str]


class RestartRequiredResponse(BaseModel):
    """Response for settings requiring restart"""
    
    requires_restart: bool
    settings: List[PendingChange]
    restart_message: str
    can_restart_now: bool
    estimated_downtime_seconds: Optional[int]