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
    
    # Additional fields from main branch
    algorithm_type: Optional[PriorityAlgorithm] = None
    weight: Optional[float] = Field(None, ge=0, le=100)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    score_function: Optional[str] = None
    conditions: Dict[str, Any] = Field(default_factory=dict)
    
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
    
    # Additional fields from main branch
    algorithm_type: Optional[PriorityAlgorithm] = None
    weight: Optional[float] = Field(None, ge=0, le=100)
    parameters: Optional[Dict[str, Any]] = None
    score_function: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None


class PriorityRuleResponse(PriorityRuleBase):
    """Schema for priority rule responses"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


class PriorityRuleListResponse(BaseModel):
    """Response for list of priority rules"""
    items: List[PriorityRuleResponse]
    total: int
    page: int
    per_page: int
    pages: int


class PriorityProfileRuleBase(BaseModel):
    """Base schema for profile-rule associations"""
    rule_id: int
    weight: float = Field(1.0, ge=0)
    is_active: bool = True
    override_config: Optional[Dict[str, Any]] = None
    boost_conditions: Optional[Dict[str, Any]] = None
    
    # Additional fields from main branch
    weight_override: Optional[float] = None
    is_required: bool = False
    fallback_score: float = Field(0.0, ge=0)
    min_threshold: Optional[float] = None
    max_threshold: Optional[float] = None


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
    
    # Additional fields from main branch
    queue_types: List[str] = Field(default_factory=list)
    order_types: List[str] = Field(default_factory=list)
    time_ranges: List[Dict[str, Any]] = Field(default_factory=list)
    normalize_scores: bool = True
    normalization_method: str = "min_max"


class PriorityProfileCreate(PriorityProfileBase):
    """Schema for creating priority profiles"""
    rules: List[PriorityProfileRuleBase] = Field(default_factory=list)
    
    # Additional field from main branch
    rule_assignments: List[Dict[str, Any]] = Field(default_factory=list)
    # Example: [{"rule_id": 1, "weight_override": 2.0, "is_required": true}]


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
    
    # Additional fields from main branch
    queue_types: Optional[List[str]] = None
    order_types: Optional[List[str]] = None
    time_ranges: Optional[List[Dict[str, Any]]] = None
    normalize_scores: Optional[bool] = None
    normalization_method: Optional[str] = None


class PriorityProfileRuleResponse(PriorityProfileRuleBase):
    """Schema for profile-rule association responses"""
    id: int
    created_at: datetime
    rule: PriorityRuleResponse
    
    model_config = ConfigDict(from_attributes=True)


class PriorityProfileResponse(BaseModel):
    """Schema for priority profile responses"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    rule_count: Optional[int] = 0
    
    model_config = ConfigDict(from_attributes=True)


class PriorityProfileDetailResponse(PriorityProfileResponse):
    """Schema for detailed priority profile responses with rules"""
    profile_rules: List[PriorityProfileRuleResponse] = []


class PriorityProfileListResponse(BaseModel):
    """Response for list of priority profiles"""
    items: List[PriorityProfileResponse]
    total: int
    page: int
    per_page: int
    pages: int


class QueuePriorityConfigBase(BaseModel):
    """Base schema for queue priority configurations"""
    queue_id: int
    profile_id: int
    is_active: bool = True
    priority_enabled: bool = True
    auto_rebalance: bool = True
    rebalance_interval_minutes: int = Field(5, ge=1)
    rebalance_threshold: float = Field(0.2, ge=0, le=1)
    max_position_change: int = Field(5, ge=1)
    boost_new_items: bool = True
    boost_duration_seconds: int = Field(30, ge=0)
    queue_overrides: Optional[Dict[str, Any]] = None
    peak_hours_config: Optional[Dict[str, Any]] = None
    
    # Additional fields from main branch
    priority_boost_vip: float = Field(20.0, ge=0)
    priority_boost_delayed: float = Field(15.0, ge=0)
    priority_boost_large_party: float = Field(10.0, ge=0)
    rebalance_enabled: bool = True
    rebalance_interval: int = Field(300, ge=1)
    peak_hours: List[Dict[str, Any]] = Field(default_factory=list)
    peak_multiplier: float = Field(1.5, ge=1)


class QueuePriorityConfigCreate(QueuePriorityConfigBase):
    """Schema for creating queue priority configurations"""
    pass


class QueuePriorityConfigUpdate(BaseModel):
    """Schema for updating queue priority configurations"""
    profile_id: Optional[int] = None
    is_active: Optional[bool] = None
    priority_enabled: Optional[bool] = None
    auto_rebalance: Optional[bool] = None
    rebalance_interval_minutes: Optional[int] = Field(None, ge=1)
    rebalance_threshold: Optional[float] = Field(None, ge=0, le=1)
    max_position_change: Optional[int] = Field(None, ge=1)
    boost_new_items: Optional[bool] = None
    boost_duration_seconds: Optional[int] = Field(None, ge=0)
    queue_overrides: Optional[Dict[str, Any]] = None
    peak_hours_config: Optional[Dict[str, Any]] = None
    
    # Additional fields from main branch
    priority_boost_vip: Optional[float] = Field(None, ge=0)
    priority_boost_delayed: Optional[float] = Field(None, ge=0)
    priority_boost_large_party: Optional[float] = Field(None, ge=0)
    rebalance_enabled: Optional[bool] = None
    rebalance_interval: Optional[int] = Field(None, ge=1)
    peak_hours: Optional[List[Dict[str, Any]]] = None
    peak_multiplier: Optional[float] = Field(None, ge=1)


class QueuePriorityConfigResponse(QueuePriorityConfigBase):
    """Schema for queue priority configuration responses"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    profile_name: Optional[str] = None
    queue_name: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class QueuePriorityConfigListResponse(BaseModel):
    """Response for list of queue priority configurations"""
    items: List[QueuePriorityConfigResponse]
    total: int


class OrderPriorityScoreBase(BaseModel):
    """Base schema for order priority scores"""
    queue_item_id: int
    config_id: int
    total_score: float
    base_score: float
    boost_score: float = 0.0
    score_components: Dict[str, Any]
    calculated_at: datetime
    algorithm_version: Optional[str] = None
    calculation_time_ms: Optional[int] = None
    is_boosted: bool = False
    boost_expires_at: Optional[datetime] = None
    boost_reason: Optional[str] = None
    
    # Additional fields from main branch
    order_id: int
    queue_id: int
    normalized_score: Optional[float] = None
    profile_used: Optional[str] = None
    factors_applied: Optional[Dict[str, Any]] = None
    priority_tier: Optional[str] = None
    suggested_sequence: Optional[int] = None


class OrderPriorityScoreResponse(OrderPriorityScoreBase):
    """Schema for order priority score responses"""
    id: int
    
    model_config = ConfigDict(from_attributes=True)


class PriorityAdjustmentBase(BaseModel):
    """Base schema for priority adjustments"""
    queue_item_id: int
    old_score: float
    new_score: float
    adjustment_type: str = Field(..., pattern="^(manual|boost|penalty)$")
    adjustment_reason: Optional[str] = None
    old_position: Optional[int] = None
    new_position: Optional[int] = None
    adjusted_by_id: Optional[int] = None
    adjusted_at: datetime
    
    # Additional fields from main branch
    order_id: int
    old_priority: float
    new_priority: float
    old_sequence: Optional[int] = None
    new_sequence: Optional[int] = None
    affected_orders: Optional[Dict[str, Any]] = None


class PriorityAdjustmentRequest(BaseModel):
    """Schema for priority adjustment requests"""
    queue_item_id: int
    new_score: float
    adjustment_type: str = Field(..., pattern="^(manual|boost|penalty)$")
    adjustment_reason: str
    duration_seconds: Optional[int] = Field(None, ge=0)


class PriorityAdjustmentResponse(PriorityAdjustmentBase):
    """Schema for priority adjustment responses"""
    id: int
    
    model_config = ConfigDict(from_attributes=True)


class QueueRebalanceBase(BaseModel):
    """Base schema for queue rebalancing"""
    queue_id: int
    items_processed: int
    items_moved: int
    fairness_improvement: float
    execution_time_ms: int
    dry_run: bool = False


class QueueRebalanceRequest(BaseModel):
    """Schema for queue rebalancing requests"""
    queue_id: int
    force: bool = False
    dry_run: bool = False


class QueueRebalanceResponse(QueueRebalanceBase):
    """Schema for queue rebalancing responses"""
    pass


class PriorityMetricsQuery(BaseModel):
    """Schema for priority metrics queries"""
    start_date: datetime
    end_date: datetime
    queue_id: Optional[int] = None
    aggregation: str = Field("hourly", pattern="^(hourly|daily|weekly|monthly)$")


class PriorityMetricsResponse(BaseModel):
    """Schema for priority metrics responses"""
    queue_id: int
    queue_name: str
    period: str
    metrics: Dict[str, Dict[str, Any]]


class BulkPriorityCalculateRequest(BaseModel):
    """Schema for bulk priority calculation requests"""
    queue_id: int
    order_ids: Optional[List[int]] = None
    apply_boost: bool = False
    boost_duration_seconds: Optional[int] = Field(None, ge=0)


class BulkPriorityCalculateResponse(BaseModel):
    """Schema for bulk priority calculation responses"""
    queue_id: int
    items_processed: int
    items_updated: int
    average_score_change: float
    execution_time_ms: int
    errors: List[Dict[str, Any]]


# Additional schemas from main branch
class PriorityCalculationRequest(BaseModel):
    """Schema for priority calculation requests"""
    order_id: int
    queue_id: int
    profile_override: Optional[int] = None


class PriorityScoreResponse(BaseModel):
    """Schema for priority score responses"""
    order_id: int
    queue_id: int
    total_score: float
    normalized_score: float
    score_components: Dict[str, float]
    priority_tier: str
    suggested_sequence: int
    calculated_at: datetime


class ManualPriorityAdjustmentRequest(BaseModel):
    """Schema for manual priority adjustment requests"""
    order_id: int
    queue_id: int
    new_priority: float
    reason: str


class RebalanceQueueRequest(BaseModel):
    """Schema for queue rebalancing requests"""
    queue_id: int


class RebalanceQueueResponse(BaseModel):
    """Schema for queue rebalancing responses"""
    queue_id: int
    items_processed: int
    items_moved: int
    fairness_improvement: float
    execution_time_ms: int


class PriorityMetricsRequest(BaseModel):
    """Schema for priority metrics requests"""
    start_date: datetime
    end_date: datetime
    profile_id: Optional[int] = None
    queue_id: Optional[int] = None


class BatchProfileRuleUpdate(BaseModel):
    """Schema for batch profile rule updates"""
    assignments: List[Dict[str, Any]]
