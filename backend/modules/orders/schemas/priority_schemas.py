"""
Pydantic schemas for priority management system.
"""

from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum

from ..models.priority_models import (
    PriorityAlgorithm, PriorityScoreType
)
from ..models.queue_models import QueueStatus, QueueItemStatus


class PriorityRuleBase(BaseModel):
    """Base schema for priority rules"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    score_type: PriorityScoreType
    is_active: bool = True
    score_config: Dict[str, Any] = Field(..., description="Score calculation configuration")
    min_score: float = Field(0.0, ge=0)
    max_score: float = Field(100.0, gt=0)
    default_weight: float = Field(1.0, ge=0)
    normalize_output: bool = True
    normalization_method: str = Field("min_max", pattern="^(min_max|z_score|percentile)$")
    
    @validator('score_config')
    def validate_score_config(cls, v):
        """Validate score configuration structure"""
        required_fields = ['type']
        if not all(field in v for field in required_fields):
            raise ValueError(f"score_config must contain: {required_fields}")
        
        # Validate config type
        valid_types = ['linear', 'exponential', 'logarithmic', 'step', 'custom']
        if v.get('type') not in valid_types:
            raise ValueError(f"score_config.type must be one of: {valid_types}")
        
        return v
    
    @validator('max_score')
    def validate_score_range(cls, v, values):
        """Ensure max_score > min_score"""
        if 'min_score' in values and v <= values['min_score']:
            raise ValueError("max_score must be greater than min_score")
        return v


class PriorityRuleCreate(PriorityRuleBase):
    """Schema for creating priority rules"""
    pass


class PriorityRuleUpdate(BaseModel):
    """Schema for updating priority rules"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    score_type: Optional[PriorityScoreType] = None
    is_active: Optional[bool] = None
    score_config: Optional[Dict[str, Any]] = None
    min_score: Optional[float] = Field(None, ge=0)
    max_score: Optional[float] = Field(None, gt=0)
    default_weight: Optional[float] = Field(None, ge=0)
    normalize_output: Optional[bool] = None
    normalization_method: Optional[str] = Field(None, pattern="^(min_max|z_score|percentile)$")


class PriorityRuleResponse(PriorityRuleBase):
    """Schema for priority rule responses"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


class PriorityProfileRuleBase(BaseModel):
    """Base schema for profile-rule associations"""
    rule_id: int
    weight: float = Field(1.0, ge=0)
    is_active: bool = True
    override_config: Optional[Dict[str, Any]] = None
    boost_conditions: Optional[Dict[str, Any]] = None


class PriorityProfileBase(BaseModel):
    """Base schema for priority profiles"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    algorithm_type: PriorityAlgorithm = PriorityAlgorithm.WEIGHTED
    is_active: bool = True
    is_default: bool = False
    aggregation_method: str = Field("weighted_sum", 
                                  pattern="^(weighted_sum|max|min|average|multiply)$")
    total_weight_normalization: bool = True
    min_total_score: float = Field(0.0, ge=0)
    max_total_score: float = Field(100.0, gt=0)
    cache_duration_seconds: int = Field(60, ge=0, le=3600)
    recalculation_threshold: float = Field(0.1, ge=0, le=1.0)


class PriorityProfileCreate(PriorityProfileBase):
    """Schema for creating priority profiles"""
    rules: List[PriorityProfileRuleBase] = Field(default_factory=list)


class PriorityProfileUpdate(BaseModel):
    """Schema for updating priority profiles"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    algorithm_type: Optional[PriorityAlgorithm] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    aggregation_method: Optional[str] = Field(None, 
                                            pattern="^(weighted_sum|max|min|average|multiply)$")
    total_weight_normalization: Optional[bool] = None
    min_total_score: Optional[float] = Field(None, ge=0)
    max_total_score: Optional[float] = Field(None, gt=0)
    cache_duration_seconds: Optional[int] = Field(None, ge=0, le=3600)
    recalculation_threshold: Optional[float] = Field(None, ge=0, le=1.0)


class PriorityProfileRuleResponse(PriorityProfileRuleBase):
    """Schema for profile-rule association responses"""
    id: int
    created_at: datetime
    rule: PriorityRuleResponse
    
    model_config = ConfigDict(from_attributes=True)


class PriorityProfileResponse(PriorityProfileBase):
    """Schema for priority profile responses"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    rule_count: int = 0
    
    model_config = ConfigDict(from_attributes=True)


class PriorityProfileDetailResponse(PriorityProfileResponse):
    """Detailed profile response with rules"""
    profile_rules: List[PriorityProfileRuleResponse] = Field(default_factory=list)


class QueuePriorityConfigBase(BaseModel):
    """Base schema for queue priority configuration"""
    queue_id: int
    profile_id: int
    is_active: bool = True
    priority_enabled: bool = True
    auto_rebalance: bool = True
    rebalance_interval_minutes: int = Field(5, ge=1, le=60)
    rebalance_threshold: float = Field(0.2, ge=0, le=1.0)
    max_position_change: int = Field(5, ge=0, le=50)
    boost_new_items: bool = True
    boost_duration_seconds: int = Field(30, ge=0, le=300)
    queue_overrides: Optional[Dict[str, Any]] = None
    peak_hours_config: Optional[Dict[str, Any]] = None


class QueuePriorityConfigCreate(QueuePriorityConfigBase):
    """Schema for creating queue priority config"""
    pass


class QueuePriorityConfigUpdate(BaseModel):
    """Schema for updating queue priority config"""
    profile_id: Optional[int] = None
    is_active: Optional[bool] = None
    priority_enabled: Optional[bool] = None
    auto_rebalance: Optional[bool] = None
    rebalance_interval_minutes: Optional[int] = Field(None, ge=1, le=60)
    rebalance_threshold: Optional[float] = Field(None, ge=0, le=1.0)
    max_position_change: Optional[int] = Field(None, ge=0, le=50)
    boost_new_items: Optional[bool] = None
    boost_duration_seconds: Optional[int] = Field(None, ge=0, le=300)
    queue_overrides: Optional[Dict[str, Any]] = None
    peak_hours_config: Optional[Dict[str, Any]] = None


class QueuePriorityConfigResponse(QueuePriorityConfigBase):
    """Schema for queue priority config responses"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    last_rebalance_time: Optional[datetime]
    profile_name: Optional[str] = None
    queue_name: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class OrderPriorityScoreResponse(BaseModel):
    """Schema for order priority score responses"""
    id: int
    queue_item_id: int
    total_score: float
    base_score: float
    boost_score: float
    score_components: Dict[str, Dict[str, Any]]
    calculated_at: datetime
    algorithm_version: Optional[str]
    calculation_time_ms: Optional[int]
    is_boosted: bool
    boost_expires_at: Optional[datetime]
    boost_reason: Optional[str]
    
    model_config = ConfigDict(from_attributes=True)


class PriorityAdjustmentRequest(BaseModel):
    """Schema for manual priority adjustments"""
    queue_item_id: int
    new_score: float = Field(..., ge=0)
    adjustment_type: str = Field(..., pattern="^(manual|boost|penalty)$")
    adjustment_reason: str = Field(..., min_length=1, max_length=200)
    duration_seconds: Optional[int] = Field(None, ge=0, le=3600)


class PriorityAdjustmentResponse(BaseModel):
    """Schema for priority adjustment responses"""
    id: int
    queue_item_id: int
    old_score: float
    new_score: float
    old_position: Optional[int]
    new_position: Optional[int]
    adjustment_type: str
    adjustment_reason: Optional[str]
    adjusted_by_id: Optional[int]
    adjusted_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class QueueRebalanceRequest(BaseModel):
    """Schema for queue rebalancing requests"""
    queue_id: int
    force: bool = Field(False, description="Force rebalance even if threshold not met")
    dry_run: bool = Field(False, description="Simulate rebalance without applying")


class QueueRebalanceResponse(BaseModel):
    """Schema for queue rebalance responses"""
    queue_id: int
    items_rebalanced: int
    average_position_change: float
    max_position_change: int
    fairness_before: float
    fairness_after: float
    execution_time_ms: int
    dry_run: bool


class PriorityMetricsQuery(BaseModel):
    """Schema for querying priority metrics"""
    queue_id: Optional[int] = None
    start_date: datetime
    end_date: datetime
    metric_type: Optional[str] = Field(None, 
                                      pattern="^(fairness|performance|rebalancing|effectiveness)$")
    aggregation: str = Field("hourly", pattern="^(hourly|daily|weekly)$")


class PriorityMetricsResponse(BaseModel):
    """Schema for priority metrics responses"""
    queue_id: int
    queue_name: str
    period: str
    metrics: Dict[str, Any]
    
    model_config = ConfigDict(from_attributes=True)


class BulkPriorityCalculateRequest(BaseModel):
    """Schema for bulk priority calculation"""
    queue_id: int
    order_ids: Optional[List[int]] = None
    recalculate_all: bool = False
    apply_boost: bool = False
    boost_duration_seconds: Optional[int] = Field(None, ge=0, le=300)


class BulkPriorityCalculateResponse(BaseModel):
    """Schema for bulk priority calculation response"""
    queue_id: int
    items_processed: int
    items_updated: int
    average_score_change: float
    execution_time_ms: int
    errors: List[Dict[str, Any]] = Field(default_factory=list)


# List response schemas with pagination
class PriorityRuleListResponse(BaseModel):
    """Paginated list of priority rules"""
    items: List[PriorityRuleResponse]
    total: int
    page: int
    per_page: int
    pages: int


class PriorityProfileListResponse(BaseModel):
    """Paginated list of priority profiles"""
    items: List[PriorityProfileResponse]
    total: int
    page: int
    per_page: int
    pages: int


class QueuePriorityConfigListResponse(BaseModel):
    """List of queue priority configurations"""
    items: List[QueuePriorityConfigResponse]
    total: int