"""
Pydantic schemas for order prioritization.
"""

from typing import Optional, Dict, List, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum

from ..models.priority_models import (
    PriorityAlgorithmType, PriorityScoreType
)


class PriorityRuleBase(BaseModel):
    """Base schema for priority rules"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    algorithm_type: PriorityAlgorithmType
    is_active: bool = True
    weight: float = Field(1.0, ge=0, le=100)
    min_score: float = Field(0.0, ge=0)
    max_score: float = Field(100.0, le=1000)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    score_type: PriorityScoreType = PriorityScoreType.LINEAR
    score_function: Optional[str] = None
    conditions: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('max_score')
    def validate_score_range(cls, v, values):
        if 'min_score' in values and v <= values['min_score']:
            raise ValueError('max_score must be greater than min_score')
        return v


class PriorityRuleCreate(PriorityRuleBase):
    """Schema for creating priority rules"""
    pass


class PriorityRuleUpdate(BaseModel):
    """Schema for updating priority rules"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    weight: Optional[float] = Field(None, ge=0, le=100)
    min_score: Optional[float] = Field(None, ge=0)
    max_score: Optional[float] = Field(None, le=1000)
    parameters: Optional[Dict[str, Any]] = None
    score_type: Optional[PriorityScoreType] = None
    score_function: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None


class PriorityRuleResponse(PriorityRuleBase):
    """Response schema for priority rules"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        orm_mode = True


class PriorityProfileBase(BaseModel):
    """Base schema for priority profiles"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: bool = True
    is_default: bool = False
    queue_types: List[str] = Field(default_factory=list)
    order_types: List[str] = Field(default_factory=list)
    time_ranges: List[Dict[str, Any]] = Field(default_factory=list)
    normalize_scores: bool = True
    normalization_method: str = "min_max"


class PriorityProfileCreate(PriorityProfileBase):
    """Schema for creating priority profiles"""
    rule_assignments: List[Dict[str, Any]] = Field(default_factory=list)
    # Example: [{"rule_id": 1, "weight_override": 2.0, "is_required": true}]


class PriorityProfileUpdate(BaseModel):
    """Schema for updating priority profiles"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    queue_types: Optional[List[str]] = None
    order_types: Optional[List[str]] = None
    time_ranges: Optional[List[Dict[str, Any]]] = None
    normalize_scores: Optional[bool] = None
    normalization_method: Optional[str] = None


class PriorityProfileResponse(PriorityProfileBase):
    """Response schema for priority profiles"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    rule_count: int = 0
    
    class Config:
        orm_mode = True


class QueuePriorityConfigBase(BaseModel):
    """Base schema for queue priority configuration"""
    queue_id: int
    priority_profile_id: int
    priority_boost_vip: float = Field(20.0, ge=0, le=100)
    priority_boost_delayed: float = Field(15.0, ge=0, le=100)
    priority_boost_large_party: float = Field(10.0, ge=0, le=100)
    rebalance_enabled: bool = True
    rebalance_interval: int = Field(300, ge=60, le=3600)  # Seconds
    max_position_change: int = Field(5, ge=1, le=20)
    peak_hours: List[Dict[str, Any]] = Field(default_factory=list)
    peak_multiplier: float = Field(1.5, ge=1.0, le=3.0)


class QueuePriorityConfigCreate(QueuePriorityConfigBase):
    """Schema for creating queue priority config"""
    pass


class QueuePriorityConfigUpdate(BaseModel):
    """Schema for updating queue priority config"""
    priority_profile_id: Optional[int] = None
    priority_boost_vip: Optional[float] = Field(None, ge=0, le=100)
    priority_boost_delayed: Optional[float] = Field(None, ge=0, le=100)
    priority_boost_large_party: Optional[float] = Field(None, ge=0, le=100)
    rebalance_enabled: Optional[bool] = None
    rebalance_interval: Optional[int] = Field(None, ge=60, le=3600)
    max_position_change: Optional[int] = Field(None, ge=1, le=20)
    peak_hours: Optional[List[Dict[str, Any]]] = None
    peak_multiplier: Optional[float] = Field(None, ge=1.0, le=3.0)


class QueuePriorityConfigResponse(QueuePriorityConfigBase):
    """Response schema for queue priority config"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    profile_name: Optional[str] = None
    
    class Config:
        orm_mode = True


class PriorityCalculationRequest(BaseModel):
    """Request to calculate priority for an order"""
    order_id: int
    queue_id: int
    profile_override: Optional[int] = None


class PriorityScoreResponse(BaseModel):
    """Response for calculated priority score"""
    order_id: int
    queue_id: int
    total_score: float
    normalized_score: float
    score_components: Dict[str, Dict[str, Any]]
    profile_used: str
    calculated_at: datetime
    priority_tier: str
    suggested_sequence: Optional[int] = None
    
    class Config:
        orm_mode = True


class ManualPriorityAdjustmentRequest(BaseModel):
    """Request to manually adjust order priority"""
    order_id: int
    queue_id: int
    new_priority: float = Field(..., ge=0, le=1000)
    reason: str = Field(..., min_length=1, max_length=200)


class PriorityAdjustmentResponse(BaseModel):
    """Response for priority adjustment"""
    id: int
    order_id: int
    queue_item_id: int
    old_priority: float
    new_priority: float
    old_sequence: int
    new_sequence: int
    adjustment_reason: str
    adjusted_by_id: int
    adjusted_at: datetime
    affected_orders: List[Dict[str, Any]]
    
    class Config:
        orm_mode = True


class RebalanceQueueRequest(BaseModel):
    """Request to rebalance a queue"""
    queue_id: int
    force: bool = False  # Force rebalance even if disabled


class RebalanceQueueResponse(BaseModel):
    """Response for queue rebalancing"""
    success: bool
    message: str
    items_reordered: int = 0
    changes: List[Dict[str, Any]] = Field(default_factory=list)


class PriorityMetricsRequest(BaseModel):
    """Request for priority metrics"""
    profile_id: Optional[int] = None
    queue_id: Optional[int] = None
    start_date: datetime
    end_date: datetime
    granularity: str = "hour"  # hour, day, week


class PriorityMetricsResponse(BaseModel):
    """Response for priority metrics"""
    profile_id: Optional[int]
    queue_id: Optional[int]
    period: Dict[str, datetime]
    effectiveness: Dict[str, float]
    fairness: Dict[str, float]
    performance: Dict[str, float]
    business_impact: Dict[str, Any]
    
    class Config:
        orm_mode = True


class ProfileRuleAssignment(BaseModel):
    """Schema for assigning rules to profiles"""
    rule_id: int
    weight_override: Optional[float] = None
    is_required: bool = False
    fallback_score: float = 0.0
    min_threshold: Optional[float] = None
    max_threshold: Optional[float] = None


class BatchProfileRuleUpdate(BaseModel):
    """Schema for batch updating profile rules"""
    profile_id: int
    assignments: List[ProfileRuleAssignment]