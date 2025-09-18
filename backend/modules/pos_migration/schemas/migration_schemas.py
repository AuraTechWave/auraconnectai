"""
POS Migration Schemas

Pydantic schemas for API validation and serialization.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, ConfigDict
from uuid import UUID

from ..models.migration_models import MigrationStatus, POSProvider, DataEntityType


class DataMappingBase(BaseModel):
    """Base schema for data mapping"""
    entity_type: DataEntityType
    source_field: str
    target_field: str
    transformation_function: Optional[str] = None
    default_value: Optional[str] = None
    is_required: bool = False
    validation_regex: Optional[str] = None
    data_type: Optional[str] = None


class DataMappingCreate(DataMappingBase):
    """Schema for creating data mapping"""
    pass


class DataMappingUpdate(BaseModel):
    """Schema for updating data mapping"""
    target_field: Optional[str] = None
    transformation_function: Optional[str] = None
    default_value: Optional[str] = None
    user_approved: Optional[bool] = None


class DataMappingResponse(DataMappingBase):
    """Schema for data mapping response"""
    id: int
    migration_job_id: UUID
    ai_suggested: bool = False
    confidence_score: Optional[float] = None
    user_approved: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class MigrationJobBase(BaseModel):
    """Base schema for migration job"""
    job_name: str = Field(..., min_length=1, max_length=255)
    source_provider: POSProvider
    target_provider: str = "auraconnect"
    entities_to_migrate: List[DataEntityType]
    mapping_rules: Optional[Dict[str, Any]] = None
    transformation_rules: Optional[Dict[str, Any]] = None
    validation_rules: Optional[Dict[str, Any]] = None
    batch_size: int = Field(default=100, ge=1, le=10000)
    rate_limit: Optional[int] = Field(default=None, ge=1, le=1000)
    parallel_workers: int = Field(default=1, ge=1, le=10)


class MigrationJobCreate(MigrationJobBase):
    """Schema for creating migration job"""
    source_credentials: Dict[str, Any]  # Will be encrypted
    source_api_endpoint: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    rollback_enabled: bool = True
    
    @field_validator("source_credentials", mode="after")
    def validate_credentials(cls, v, values):
        """Validate required credentials based on provider"""
        provider = info.data.get("source_provider")
        if provider == POSProvider.SQUARE:
            required = ["access_token", "location_id"]
        elif provider == POSProvider.CLOVER:
            required = ["api_key", "merchant_id"]
        elif provider == POSProvider.TOAST:
            required = ["client_id", "client_secret", "restaurant_guid"]
        else:
            required = ["api_key"]
        
        missing = [key for key in required if key not in v]
        if missing:
            raise ValueError(f"Missing required credentials: {missing}")
        return v


class MigrationJobUpdate(BaseModel):
    """Schema for updating migration job"""
    job_name: Optional[str] = None
    status: Optional[MigrationStatus] = None
    batch_size: Optional[int] = None
    rate_limit: Optional[int] = None
    parallel_workers: Optional[int] = None
    scheduled_at: Optional[datetime] = None


class MigrationJobResponse(MigrationJobBase):
    """Schema for migration job response"""
    id: UUID
    restaurant_id: int
    status: MigrationStatus
    progress_percentage: float
    current_entity: Optional[str] = None
    entities_completed: List[str] = []
    
    # Statistics
    total_records: int = 0
    records_processed: int = 0
    records_succeeded: int = 0
    records_failed: int = 0
    records_skipped: int = 0
    
    # Timing
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    
    # Error info
    error_count: int = 0
    last_error: Optional[str] = None
    
    # Audit
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class MigrationJobDetail(MigrationJobResponse):
    """Detailed migration job response with relationships"""
    mappings: List[DataMappingResponse] = []
    recent_logs: List["MigrationLogResponse"] = []
    validation_summary: Dict[str, Any] = {}
    
    model_config = ConfigDict(from_attributes=True)


class MigrationLogResponse(BaseModel):
    """Schema for migration log response"""
    id: int
    migration_job_id: UUID
    log_level: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    action: Optional[str] = None
    message: str
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ValidationResultResponse(BaseModel):
    """Schema for validation result response"""
    id: int
    migration_job_id: UUID
    entity_type: str
    entity_id: Optional[str] = None
    validation_type: str
    is_valid: bool
    validation_errors: Optional[List[Dict[str, Any]]] = None
    warnings: Optional[List[Dict[str, Any]]] = None
    auto_fixed: bool = False
    manual_review_required: bool = False
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class MigrationTemplateBase(BaseModel):
    """Base schema for migration template"""
    template_name: str = Field(..., min_length=1, max_length=255)
    source_provider: POSProvider
    target_provider: str = "auraconnect"
    description: Optional[str] = None
    default_mappings: Dict[str, Any]
    transformation_rules: Optional[Dict[str, Any]] = None
    validation_rules: Optional[Dict[str, Any]] = None
    recommended_batch_size: Optional[int] = None


class MigrationTemplateCreate(MigrationTemplateBase):
    """Schema for creating migration template"""
    version: str = "1.0.0"
    common_issues: Optional[Dict[str, Any]] = None
    resolution_steps: Optional[Dict[str, Any]] = None
    performance_tips: Optional[Dict[str, Any]] = None


class MigrationTemplateResponse(MigrationTemplateBase):
    """Schema for migration template response"""
    id: int
    version: str
    is_active: bool
    usage_count: int
    success_rate: Optional[float] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class MigrationAnalysisRequest(BaseModel):
    """Request schema for analyzing source POS data"""
    source_provider: POSProvider
    source_credentials: Dict[str, Any]
    source_api_endpoint: Optional[str] = None
    entities_to_analyze: List[DataEntityType]
    sample_size: int = Field(default=100, ge=1, le=1000)


class MigrationAnalysisResponse(BaseModel):
    """Response schema for migration analysis"""
    source_provider: POSProvider
    analysis_date: datetime
    entities_analyzed: Dict[str, Dict[str, Any]]  # entity_type -> stats
    suggested_mappings: List[DataMappingBase]
    compatibility_score: float  # 0.0 to 1.0
    estimated_duration_minutes: int
    potential_issues: List[Dict[str, Any]]
    recommendations: List[str]


class MigrationProgressUpdate(BaseModel):
    """WebSocket message for progress updates"""
    job_id: UUID
    status: MigrationStatus
    progress_percentage: float
    current_entity: Optional[str] = None
    message: str
    timestamp: datetime
    
    # Statistics update
    records_processed: Optional[int] = None
    records_succeeded: Optional[int] = None
    records_failed: Optional[int] = None
    
    # Error info
    error: Optional[Dict[str, Any]] = None


class BulkMigrationRequest(BaseModel):
    """Request for bulk migration operations"""
    job_ids: List[UUID]
    action: str  # "start", "pause", "cancel", "retry"
    
    @field_validator("action", mode="after")
    def validate_action(cls, v):
        allowed = ["start", "pause", "cancel", "retry"]
        if v not in allowed:
            raise ValueError(f"Action must be one of {allowed}")
        return v


class MigrationStatsResponse(BaseModel):
    """Statistics for migration dashboard"""
    total_jobs: int
    jobs_by_status: Dict[str, int]
    jobs_by_provider: Dict[str, int]
    average_success_rate: float
    average_duration_minutes: float
    total_records_migrated: int
    recent_jobs: List[MigrationJobResponse]
    common_errors: List[Dict[str, Any]]