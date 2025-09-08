# backend/modules/orders/schemas/sync_schemas.py

"""
Pydantic schemas for order synchronization.

Defines request/response models for sync-related API endpoints.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class SyncStatusEnum(str, Enum):
    """Sync status values"""

    pending = "pending"
    in_progress = "in_progress"
    synced = "synced"
    failed = "failed"
    conflict = "conflict"
    retry = "retry"


class SyncDirectionEnum(str, Enum):
    """Sync direction values"""

    local_to_remote = "local_to_remote"
    remote_to_local = "remote_to_local"
    bidirectional = "bidirectional"


class ConflictResolutionMethod(str, Enum):
    """Conflict resolution methods"""

    local_wins = "local_wins"
    remote_wins = "remote_wins"
    merge = "merge"
    manual = "manual"
    ignore = "ignore"


class SyncBatchResponse(BaseModel):
    """Response model for sync batch"""

    id: int
    batch_id: str
    batch_type: str
    batch_size: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    total_orders: int = 0
    successful_syncs: int = 0
    failed_syncs: int = 0
    conflict_count: int = 0
    avg_sync_time_ms: Optional[float] = None
    error_summary: Optional[Dict[str, Any]] = None
    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed


class SyncConflictResponse(BaseModel):
    """Response model for sync conflict"""

    id: int
    order_id: int
    conflict_type: str
    detected_at: datetime
    local_data: Dict[str, Any]
    remote_data: Dict[str, Any]
    differences: Optional[Dict[str, Any]] = None
    resolution_status: str
    resolution_method: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[int] = None
    resolution_notes: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed


class SyncStatusResponse(BaseModel):
    """Response model for sync status overview"""

    sync_status_counts: Dict[str, int]
    unsynced_orders: int
    pending_conflicts: int
    last_batch: Optional[Dict[str, Any]] = None
    scheduler: Dict[str, Any]
    configuration: Dict[str, Any]


class SyncConfigurationUpdate(BaseModel):
    """Request model for updating sync configuration"""

    sync_enabled: Optional[bool] = Field(
        None, description="Enable/disable automatic sync"
    )
    sync_interval_minutes: Optional[int] = Field(
        None, ge=1, le=1440, description="Sync interval in minutes (1-1440)"
    )
    conflict_resolution_mode: Optional[str] = Field(
        None, description="Conflict resolution mode (auto/manual)"
    )

    @field_validator("conflict_resolution_mode")
    def validate_conflict_mode(cls, v):
        if v and v not in ["auto", "manual"]:
            raise ValueError("Invalid conflict resolution mode")
        return v


class ManualSyncRequest(BaseModel):
    """Request model for manual sync"""

    order_ids: Optional[List[int]] = Field(
        None, description="Specific order IDs to sync (empty for all pending)"
    )
    force: bool = Field(False, description="Force sync even if recently synced")


class ConflictResolutionRequest(BaseModel):
    """Request model for resolving conflicts"""

    resolution_method: ConflictResolutionMethod
    notes: Optional[str] = Field(None, max_length=500)
    final_data: Optional[Dict[str, Any]] = Field(
        None, description="Final data to use (for merge resolution)"
    )


class OrderSyncStatusResponse(BaseModel):
    """Response model for individual order sync status"""

    order_id: int
    sync_status: str
    sync_direction: Optional[str] = None
    attempt_count: int = 0
    last_attempt_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None
    synced_at: Optional[datetime] = None
    last_error: Optional[str] = None
    error_code: Optional[str] = None
    remote_id: Optional[str] = None
    local_checksum: Optional[str] = None
    remote_checksum: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed


class SyncLogResponse(BaseModel):
    """Response model for sync log entry"""

    id: int
    batch_id: Optional[int] = None
    order_id: int
    operation: str
    sync_direction: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed


class SyncMetricsResponse(BaseModel):
    """Response model for sync metrics"""

    total_synced_today: int
    total_failed_today: int
    average_sync_time_ms: float
    sync_success_rate: float
    pending_orders: int
    retry_queue_size: int
    conflict_rate: float
    last_successful_batch: Optional[datetime] = None
    next_scheduled_sync: Optional[datetime] = None


class BatchSyncRequest(BaseModel):
    """Request model for batch sync operations"""

    order_ids: List[int] = Field(..., min_items=1, max_items=100)
    priority: bool = Field(False, description="Process with high priority")
    ignore_recent_sync: bool = Field(False, description="Sync even if recently synced")


class SyncHealthCheckResponse(BaseModel):
    """Response model for sync health check"""

    status: str = Field(..., description="healthy, warning, or critical")
    issues: List[str] = Field(default_factory=list)
    last_check: datetime
    metrics: Dict[str, Any]
    recommendations: List[str] = Field(default_factory=list)
