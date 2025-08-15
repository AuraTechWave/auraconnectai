# backend/core/menu_sync_schemas.py

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
import uuid


class SyncDirection(str, Enum):
    PUSH = "push"
    PULL = "pull"
    BIDIRECTIONAL = "bidirectional"


class SyncStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    ERROR = "error"
    CONFLICT = "conflict"
    CANCELLED = "cancelled"


class ConflictResolution(str, Enum):
    MANUAL = "manual"
    POS_WINS = "pos_wins"
    AURA_WINS = "aura_wins"
    LATEST_WINS = "latest_wins"


# Base schemas for menu sync models
class POSMenuMappingBase(BaseModel):
    pos_integration_id: int
    pos_vendor: str = Field(..., max_length=50)
    entity_type: str = Field(..., max_length=50)
    aura_entity_id: int
    pos_entity_id: str = Field(..., max_length=255)
    pos_entity_data: Optional[Dict[str, Any]] = None
    sync_enabled: bool = True
    sync_direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    conflict_resolution: ConflictResolution = ConflictResolution.MANUAL


class POSMenuMappingCreate(POSMenuMappingBase):
    pass


class POSMenuMappingUpdate(BaseModel):
    sync_enabled: Optional[bool] = None
    sync_direction: Optional[SyncDirection] = None
    conflict_resolution: Optional[ConflictResolution] = None
    pos_entity_data: Optional[Dict[str, Any]] = None


class POSMenuMapping(POSMenuMappingBase):
    id: int
    last_sync_at: Optional[datetime] = None
    last_sync_direction: Optional[SyncDirection] = None
    aura_last_modified: Optional[datetime] = None
    pos_last_modified: Optional[datetime] = None
    sync_hash: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Menu sync job schemas
class MenuSyncJobBase(BaseModel):
    pos_integration_id: int
    sync_direction: SyncDirection
    entity_types: Optional[List[str]] = None
    entity_ids: Optional[List[int]] = None
    scheduled_at: Optional[datetime] = None


class MenuSyncJobCreate(MenuSyncJobBase):
    triggered_by: Optional[str] = None
    triggered_by_id: Optional[int] = None
    job_config: Optional[Dict[str, Any]] = None


class MenuSyncJobUpdate(BaseModel):
    status: Optional[SyncStatus] = None
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None


class MenuSyncJob(MenuSyncJobBase):
    id: int
    job_id: uuid.UUID
    status: SyncStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_entities: int = 0
    processed_entities: int = 0
    successful_entities: int = 0
    failed_entities: int = 0
    conflicts_detected: int = 0
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    triggered_by: Optional[str] = None
    triggered_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Menu sync log schemas
class MenuSyncLogBase(BaseModel):
    entity_type: str = Field(..., max_length=50)
    aura_entity_id: Optional[int] = None
    pos_entity_id: Optional[str] = None
    operation: str = Field(..., max_length=50)
    sync_direction: SyncDirection
    status: SyncStatus


class MenuSyncLogCreate(MenuSyncLogBase):
    sync_job_id: int
    mapping_id: Optional[int] = None
    aura_data_before: Optional[Dict[str, Any]] = None
    aura_data_after: Optional[Dict[str, Any]] = None
    pos_data_before: Optional[Dict[str, Any]] = None
    pos_data_after: Optional[Dict[str, Any]] = None
    changes_detected: Optional[Dict[str, Any]] = None
    processing_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    debug_info: Optional[Dict[str, Any]] = None


class MenuSyncLog(MenuSyncLogBase):
    id: int
    sync_job_id: int
    mapping_id: Optional[int] = None
    aura_data_before: Optional[Dict[str, Any]] = None
    aura_data_after: Optional[Dict[str, Any]] = None
    pos_data_before: Optional[Dict[str, Any]] = None
    pos_data_after: Optional[Dict[str, Any]] = None
    changes_detected: Optional[Dict[str, Any]] = None
    conflict_type: Optional[str] = None
    conflict_resolution: Optional[ConflictResolution] = None
    conflict_resolved_by: Optional[int] = None
    conflict_resolved_at: Optional[datetime] = None
    processing_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    menu_version_id: Optional[int] = None
    version_created: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Menu sync conflict schemas
class MenuSyncConflictBase(BaseModel):
    entity_type: str = Field(..., max_length=50)
    aura_entity_id: Optional[int] = None
    pos_entity_id: Optional[str] = None
    conflict_type: str = Field(..., max_length=100)
    conflict_description: Optional[str] = None
    severity: str = Field(default="medium", max_length=20)


class MenuSyncConflictCreate(MenuSyncConflictBase):
    sync_job_id: int
    sync_log_id: int
    mapping_id: Optional[int] = None
    aura_current_data: Optional[Dict[str, Any]] = None
    pos_current_data: Optional[Dict[str, Any]] = None
    conflicting_fields: Optional[List[str]] = None
    auto_resolvable: bool = False
    priority: int = Field(default=5, ge=1, le=10)
    tags: Optional[List[str]] = None


class MenuSyncConflictResolve(BaseModel):
    resolution_strategy: ConflictResolution
    resolution_notes: Optional[str] = None


class MenuSyncConflict(MenuSyncConflictBase):
    id: int
    conflict_id: uuid.UUID
    sync_job_id: int
    sync_log_id: int
    mapping_id: Optional[int] = None
    aura_current_data: Optional[Dict[str, Any]] = None
    pos_current_data: Optional[Dict[str, Any]] = None
    conflicting_fields: Optional[List[str]] = None
    status: str = "unresolved"
    resolution_strategy: Optional[ConflictResolution] = None
    resolved_by: Optional[int] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    auto_resolvable: bool = False
    priority: int
    tags: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Menu sync configuration schemas
class MenuSyncConfigBase(BaseModel):
    sync_enabled: bool = True
    default_sync_direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    default_conflict_resolution: ConflictResolution = ConflictResolution.MANUAL
    auto_sync_enabled: bool = False
    sync_frequency_minutes: Optional[int] = None
    sync_time_windows: Optional[List[Dict[str, str]]] = None
    max_concurrent_jobs: int = Field(default=1, ge=1, le=10)


class MenuSyncConfigCreate(MenuSyncConfigBase):
    pos_integration_id: int


class MenuSyncConfigUpdate(BaseModel):
    sync_enabled: Optional[bool] = None
    default_sync_direction: Optional[SyncDirection] = None
    default_conflict_resolution: Optional[ConflictResolution] = None
    auto_sync_enabled: Optional[bool] = None
    sync_frequency_minutes: Optional[int] = None
    sync_time_windows: Optional[List[Dict[str, str]]] = None
    max_concurrent_jobs: Optional[int] = None
    sync_categories: Optional[bool] = None
    sync_items: Optional[bool] = None
    sync_modifiers: Optional[bool] = None
    sync_pricing: Optional[bool] = None
    sync_availability: Optional[bool] = None
    create_missing_categories: Optional[bool] = None
    preserve_aura_customizations: Optional[bool] = None
    backup_before_sync: Optional[bool] = None
    max_batch_size: Optional[int] = None
    create_version_on_pull: Optional[bool] = None
    version_name_template: Optional[str] = None
    notify_on_conflicts: Optional[bool] = None
    notify_on_errors: Optional[bool] = None
    notification_emails: Optional[List[str]] = None
    field_mappings: Optional[Dict[str, str]] = None
    transformation_rules: Optional[Dict[str, Any]] = None
    validation_rules: Optional[Dict[str, Any]] = None
    rate_limit_requests: Optional[int] = None
    timeout_seconds: Optional[int] = None
    retry_failed_operations: Optional[bool] = None


class MenuSyncConfig(MenuSyncConfigBase):
    id: int
    pos_integration_id: int
    sync_categories: bool = True
    sync_items: bool = True
    sync_modifiers: bool = True
    sync_pricing: bool = True
    sync_availability: bool = True
    create_missing_categories: bool = True
    preserve_aura_customizations: bool = True
    backup_before_sync: bool = True
    max_batch_size: int = 100
    create_version_on_pull: bool = True
    version_name_template: Optional[str] = None
    notify_on_conflicts: bool = True
    notify_on_errors: bool = True
    notification_emails: Optional[List[str]] = None
    field_mappings: Optional[Dict[str, str]] = None
    transformation_rules: Optional[Dict[str, Any]] = None
    validation_rules: Optional[Dict[str, Any]] = None
    rate_limit_requests: Optional[int] = None
    timeout_seconds: int = 30
    retry_failed_operations: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Request/Response schemas for API endpoints
class StartSyncRequest(BaseModel):
    pos_integration_id: int
    sync_direction: SyncDirection
    entity_types: Optional[List[str]] = None
    entity_ids: Optional[List[int]] = None
    force_sync: bool = False
    conflict_resolution: Optional[ConflictResolution] = None


class SyncStatusResponse(BaseModel):
    job_id: uuid.UUID
    status: SyncStatus
    progress: Dict[str, int]  # processed, total, conflicts, errors
    started_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    current_operation: Optional[str] = None


class BulkMappingCreateRequest(BaseModel):
    pos_integration_id: int
    mappings: List[Dict[str, Any]]  # Entity mappings to create
    sync_direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    conflict_resolution: ConflictResolution = ConflictResolution.MANUAL


class SyncHealthResponse(BaseModel):
    pos_integration_id: int
    overall_health: str  # healthy, warning, error
    last_successful_sync: Optional[datetime] = None
    pending_conflicts: int
    active_jobs: int
    sync_enabled: bool
    issues: List[Dict[str, str]]  # List of current issues
    recommendations: List[str]  # Recommended actions


class ConflictSummary(BaseModel):
    total_conflicts: int
    unresolved_conflicts: int
    by_entity_type: Dict[str, int]
    by_severity: Dict[str, int]
    by_conflict_type: Dict[str, int]
    oldest_conflict: Optional[datetime] = None


class SyncStatistics(BaseModel):
    pos_integration_id: int
    period_type: str
    period_start: datetime
    period_end: datetime
    total_jobs: int
    successful_jobs: int
    failed_jobs: int
    success_rate: float
    avg_job_duration: Optional[float] = None
    total_entities_synced: int
    conflicts_resolved: int
    unresolved_conflicts: int
    data_consistency_score: Optional[float] = None


# Paginated responses
class PaginatedMenuSyncJobs(BaseModel):
    items: List[MenuSyncJob]
    total: int
    page: int
    size: int
    pages: int


class PaginatedMenuSyncLogs(BaseModel):
    items: List[MenuSyncLog]
    total: int
    page: int
    size: int
    pages: int


class PaginatedMenuSyncConflicts(BaseModel):
    items: List[MenuSyncConflict]
    total: int
    page: int
    size: int
    pages: int


class PaginatedPOSMenuMappings(BaseModel):
    items: List[POSMenuMapping]
    total: int
    page: int
    size: int
    pages: int


# Entity sync schemas for different menu entities
class MenuCategorySync(BaseModel):
    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    display_order: int = 0
    is_active: bool = True
    parent_category_id: Optional[int] = None
    pos_specific_data: Optional[Dict[str, Any]] = None


class MenuItemSync(BaseModel):
    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    price: float
    category_id: int
    sku: Optional[str] = None
    is_active: bool = True
    is_available: bool = True
    availability_start_time: Optional[str] = None
    availability_end_time: Optional[str] = None
    calories: Optional[int] = None
    dietary_tags: Optional[List[str]] = None
    allergen_info: Optional[List[str]] = None
    image_url: Optional[str] = None
    display_order: int = 0
    prep_time_minutes: Optional[int] = None
    pos_specific_data: Optional[Dict[str, Any]] = None


class ModifierGroupSync(BaseModel):
    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    selection_type: str = "single"
    min_selections: int = 0
    max_selections: Optional[int] = None
    is_required: bool = False
    display_order: int = 0
    is_active: bool = True
    modifiers: Optional[List["ModifierSync"]] = None
    pos_specific_data: Optional[Dict[str, Any]] = None


class ModifierSync(BaseModel):
    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    price_adjustment: float = 0.0
    price_type: str = "fixed"
    is_active: bool = True
    is_available: bool = True
    display_order: int = 0
    pos_specific_data: Optional[Dict[str, Any]] = None


# Update forward references
ModifierGroupSync.model_rebuild()


# Validation schemas
class SyncValidationResult(BaseModel):
    is_valid: bool
    entity_type: str
    entity_id: Optional[int] = None
    pos_entity_id: Optional[str] = None
    validation_errors: List[str] = []
    validation_warnings: List[str] = []
    data_quality_score: Optional[float] = None


class BatchSyncValidationRequest(BaseModel):
    pos_integration_id: int
    entities: List[Dict[str, Any]]
    entity_type: str
    validation_rules: Optional[Dict[str, Any]] = None


class BatchSyncValidationResponse(BaseModel):
    total_entities: int
    valid_entities: int
    invalid_entities: int
    results: List[SyncValidationResult]
    overall_quality_score: float
    recommendations: List[str]
