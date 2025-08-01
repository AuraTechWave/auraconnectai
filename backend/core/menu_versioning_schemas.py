# backend/core/menu_versioning_schemas.py

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
import json


class VersionType(str, Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    ROLLBACK = "rollback"
    MIGRATION = "migration"
    AUTO_SAVE = "auto_save"


class ChangeType(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ACTIVATE = "activate"
    DEACTIVATE = "deactivate"
    PRICE_CHANGE = "price_change"
    AVAILABILITY_CHANGE = "availability_change"
    CATEGORY_CHANGE = "category_change"
    MODIFIER_CHANGE = "modifier_change"


# Base schemas
class MenuVersionBase(BaseModel):
    version_name: Optional[str] = None
    description: Optional[str] = None
    version_type: VersionType = VersionType.MANUAL
    scheduled_publish_at: Optional[datetime] = None


class MenuVersionCreate(MenuVersionBase):
    pass


class MenuVersionUpdate(BaseModel):
    version_name: Optional[str] = None
    description: Optional[str] = None
    scheduled_publish_at: Optional[datetime] = None


class MenuVersion(MenuVersionBase):
    id: int
    version_number: str
    is_active: bool
    is_published: bool
    published_at: Optional[datetime]
    created_by: int
    total_items: int
    total_categories: int
    total_modifiers: int
    changes_summary: Optional[Dict[str, Any]]
    parent_version_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Category version schemas
class MenuCategoryVersionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    display_order: int = 0
    is_active: bool = True
    parent_category_id: Optional[int] = None
    image_url: Optional[str] = None


class MenuCategoryVersion(MenuCategoryVersionBase):
    id: int
    menu_version_id: int
    original_category_id: int
    change_type: ChangeType
    change_summary: Optional[str]
    changed_fields: Optional[List[str]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Item version schemas
class MenuItemVersionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    price: float = Field(..., ge=0)
    category_id: int
    sku: Optional[str] = None
    is_active: bool = True
    is_available: bool = True
    availability_start_time: Optional[str] = None
    availability_end_time: Optional[str] = None
    calories: Optional[int] = None
    dietary_tags: Optional[List[str]] = []
    allergen_info: Optional[List[str]] = []
    image_url: Optional[str] = None
    display_order: int = 0
    prep_time_minutes: Optional[int] = None
    cooking_instructions: Optional[str] = None


class MenuItemVersion(MenuItemVersionBase):
    id: int
    menu_version_id: int
    original_item_id: int
    change_type: ChangeType
    change_summary: Optional[str]
    changed_fields: Optional[List[str]]
    price_history: Optional[List[Dict[str, Any]]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Modifier schemas
class ModifierVersionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    price_adjustment: float = 0.0
    is_active: bool = True
    display_order: int = 0


class ModifierVersion(ModifierVersionBase):
    id: int
    modifier_group_version_id: int
    original_modifier_id: int
    change_type: ChangeType
    change_summary: Optional[str]
    changed_fields: Optional[List[str]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ModifierGroupVersionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    selection_type: str = Field(default="single", pattern="^(single|multiple)$")
    is_required: bool = False
    min_selections: int = Field(default=0, ge=0)
    max_selections: Optional[int] = None
    display_order: int = 0
    is_active: bool = True

    @validator('max_selections')
    def validate_max_selections(cls, v, values):
        if v is not None and 'min_selections' in values:
            if v < values['min_selections']:
                raise ValueError('max_selections must be >= min_selections')
        return v


class ModifierGroupVersion(ModifierGroupVersionBase):
    id: int
    menu_version_id: int
    original_group_id: int
    change_type: ChangeType
    change_summary: Optional[str]
    changed_fields: Optional[List[str]]
    modifier_versions: List[ModifierVersion] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Audit log schemas
class MenuAuditLogBase(BaseModel):
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    entity_name: Optional[str] = None
    change_type: ChangeType
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    changed_fields: Optional[List[str]] = None
    change_summary: Optional[str] = None
    user_role: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    tags: Optional[List[str]] = []


class MenuAuditLog(MenuAuditLogBase):
    id: int
    menu_version_id: Optional[int]
    user_id: int
    batch_id: Optional[str]
    parent_log_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Version comparison schemas
class FieldComparison(BaseModel):
    field_name: str
    old_value: Any
    new_value: Any
    change_type: str  # added, removed, modified


class EntityComparison(BaseModel):
    entity_type: str
    entity_id: int
    entity_name: str
    change_type: ChangeType
    field_changes: List[FieldComparison] = []


class MenuVersionComparison(BaseModel):
    from_version_id: int
    to_version_id: int
    from_version_number: str
    to_version_number: str
    summary: Dict[str, int]  # counts by change type
    categories: List[EntityComparison] = []
    items: List[EntityComparison] = []
    modifiers: List[EntityComparison] = []
    generated_at: datetime

    class Config:
        from_attributes = True


# Schedule schemas
class MenuVersionScheduleBase(BaseModel):
    scheduled_at: datetime
    timezone: str = "UTC"
    is_recurring: bool = False
    recurrence_pattern: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class MenuVersionScheduleCreate(MenuVersionScheduleBase):
    menu_version_id: int


class MenuVersionSchedule(MenuVersionScheduleBase):
    id: int
    menu_version_id: int
    status: str
    executed_at: Optional[datetime]
    execution_result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    retry_count: int
    max_retries: int
    created_by: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Request/Response schemas
class CreateVersionRequest(BaseModel):
    version_name: Optional[str] = None
    description: Optional[str] = None
    version_type: VersionType = VersionType.MANUAL
    include_inactive: bool = False  # Whether to include inactive items
    scheduled_publish_at: Optional[datetime] = None


class PublishVersionRequest(BaseModel):
    scheduled_at: Optional[datetime] = None
    force: bool = False  # Force publish even if another version is active


class RollbackVersionRequest(BaseModel):
    target_version_id: int
    create_backup: bool = True
    rollback_reason: str


class VersionComparisonRequest(BaseModel):
    from_version_id: int
    to_version_id: int
    include_details: bool = True
    entity_types: Optional[List[str]] = None  # Filter by entity types


# Response schemas
class MenuVersionWithDetails(MenuVersion):
    categories: List[MenuCategoryVersion] = []
    items: List[MenuItemVersion] = []
    modifiers: List[ModifierGroupVersion] = []
    audit_entries: List[MenuAuditLog] = []
    parent_version: Optional[MenuVersion] = None


class PaginatedMenuVersions(BaseModel):
    items: List[MenuVersion]
    total: int
    page: int
    size: int
    pages: int


class PaginatedAuditLogs(BaseModel):
    items: List[MenuAuditLog]
    total: int
    page: int
    size: int
    pages: int


class MenuVersionStats(BaseModel):
    total_versions: int
    active_version: Optional[MenuVersion]
    published_versions: int
    draft_versions: int
    scheduled_versions: int
    latest_change: Optional[datetime]
    total_changes_today: int
    most_changed_items: List[Dict[str, Any]]


class BulkChangeRequest(BaseModel):
    entity_type: str  # "item", "category", "modifier"
    entity_ids: List[int]
    changes: Dict[str, Any]
    change_reason: str


class VersionExportRequest(BaseModel):
    version_id: int
    format: str = Field(default="json", pattern="^(json|csv|excel)$")
    include_audit_trail: bool = False
    include_inactive: bool = False


class VersionImportRequest(BaseModel):
    import_data: Dict[str, Any]
    import_mode: str = Field(default="merge", pattern="^(merge|replace|append)$")
    create_version: bool = True
    version_name: Optional[str] = None