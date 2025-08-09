# backend/modules/insights/schemas/insight_schemas.py

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator
from decimal import Decimal

from ..models.insight_models import (
    InsightType, InsightSeverity, InsightStatus, 
    InsightDomain, NotificationChannel
)


# Base Schemas
class InsightBase(BaseModel):
    """Base insight schema"""
    type: InsightType
    severity: InsightSeverity
    domain: InsightDomain
    title: str = Field(..., max_length=200)
    description: str
    impact_score: Optional[float] = Field(None, ge=0, le=100)
    estimated_value: Optional[Decimal] = Field(None, ge=0)
    recommendations: List[str] = []
    metrics: Dict[str, Any] = {}
    related_entity_type: Optional[str] = Field(None, max_length=50)
    related_entity_id: Optional[int] = None
    confidence_score: Optional[float] = Field(None, ge=0, le=1)


class InsightCreate(InsightBase):
    """Create insight schema"""
    generated_by: str = Field(..., max_length=100)
    thread_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    notification_config: Optional[Dict[str, Any]] = {}


class InsightUpdate(BaseModel):
    """Update insight schema"""
    status: Optional[InsightStatus] = None
    resolution_notes: Optional[str] = None


class InsightResponse(InsightBase):
    """Insight response schema"""
    id: int
    restaurant_id: int
    status: InsightStatus
    thread_id: Optional[str]
    parent_insight_id: Optional[int]
    generated_by: str
    expires_at: Optional[datetime]
    acknowledged_by_id: Optional[int]
    acknowledged_at: Optional[datetime]
    resolved_by_id: Optional[int]
    resolved_at: Optional[datetime]
    resolution_notes: Optional[str]
    notifications_sent: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    # Computed fields
    age_hours: Optional[float] = None
    time_to_acknowledge: Optional[float] = None
    rating_summary: Optional[Dict[str, int]] = None
    
    class Config:
        from_attributes = True


# Rating Schemas
class InsightRatingCreate(BaseModel):
    """Create rating schema"""
    rating: str = Field(..., regex="^(useful|irrelevant|needs_followup)$")
    comment: Optional[str] = Field(None, max_length=500)


class InsightRatingResponse(BaseModel):
    """Rating response schema"""
    id: int
    insight_id: int
    user_id: int
    user_name: Optional[str] = None
    rating: str
    comment: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


# Action Schemas
class InsightActionCreate(BaseModel):
    """Create action schema"""
    action_type: str = Field(..., max_length=50)
    action_details: Optional[Dict[str, Any]] = {}


class InsightActionResponse(BaseModel):
    """Action response schema"""
    id: int
    insight_id: int
    user_id: int
    user_name: Optional[str] = None
    action_type: str
    action_details: Dict[str, Any]
    created_at: datetime
    
    class Config:
        from_attributes = True


# Notification Rule Schemas
class NotificationRuleCreate(BaseModel):
    """Create notification rule schema"""
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    domains: List[InsightDomain] = []
    types: List[InsightType] = []
    min_severity: Optional[InsightSeverity] = None
    min_impact_score: Optional[float] = Field(None, ge=0, le=100)
    min_estimated_value: Optional[Decimal] = Field(None, ge=0)
    channels: List[NotificationChannel]
    recipients: Dict[str, List[str]]
    immediate: bool = True
    batch_hours: Optional[List[int]] = Field(None, description="Hours for batch send (0-23)")
    max_per_hour: Optional[int] = Field(None, gt=0)
    max_per_day: Optional[int] = Field(None, gt=0)
    
    @validator('batch_hours')
    def validate_batch_hours(cls, v):
        if v:
            for hour in v:
                if hour < 0 or hour > 23:
                    raise ValueError('Batch hours must be between 0 and 23')
        return v


class NotificationRuleUpdate(BaseModel):
    """Update notification rule schema"""
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    domains: Optional[List[InsightDomain]] = None
    types: Optional[List[InsightType]] = None
    min_severity: Optional[InsightSeverity] = None
    min_impact_score: Optional[float] = Field(None, ge=0, le=100)
    min_estimated_value: Optional[Decimal] = Field(None, ge=0)
    channels: Optional[List[NotificationChannel]] = None
    recipients: Optional[Dict[str, List[str]]] = None
    immediate: Optional[bool] = None
    batch_hours: Optional[List[int]] = None
    max_per_hour: Optional[int] = Field(None, gt=0)
    max_per_day: Optional[int] = Field(None, gt=0)


class NotificationRuleResponse(BaseModel):
    """Notification rule response schema"""
    id: int
    restaurant_id: int
    name: str
    description: Optional[str]
    is_active: bool
    domains: List[str]
    types: List[str]
    min_severity: Optional[str]
    min_impact_score: Optional[float]
    min_estimated_value: Optional[float]
    channels: List[str]
    recipients: Dict[str, List[str]]
    immediate: bool
    batch_hours: Optional[List[int]]
    max_per_hour: Optional[int]
    max_per_day: Optional[int]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Thread Schemas
class ThreadSummary(BaseModel):
    """Thread summary schema"""
    thread_id: str
    title: str
    category: Optional[str]
    total_insights: int
    total_value: float
    is_recurring: bool
    first_date: datetime
    last_date: datetime
    latest_insight: Optional[Dict[str, Any]]


class ThreadTimeline(BaseModel):
    """Thread timeline schema"""
    thread: Dict[str, Any]
    timeline: List[Dict[str, Any]]
    patterns: Dict[str, Any]
    summary: Dict[str, Any]


# Analytics Schemas
class InsightAnalytics(BaseModel):
    """Insight analytics schema"""
    period: Dict[str, Optional[datetime]]
    total_generated: int
    by_domain: Dict[str, int]
    by_type: Dict[str, int]
    by_severity: Dict[str, int]
    total_value: float
    acceptance_rate: float
    avg_time_to_acknowledge: float
    avg_time_to_resolve: float


class UserEngagement(BaseModel):
    """User engagement schema"""
    user_id: int
    period_days: int
    ratings_given: Dict[str, int]
    actions_taken: Dict[str, int]
    total_insights_interacted: int
    engagement_score: float


# Bulk Operations
class BulkInsightUpdate(BaseModel):
    """Bulk update insights"""
    insight_ids: List[int]
    status: InsightStatus
    notes: Optional[str] = None


class BulkInsightAction(BaseModel):
    """Bulk action on insights"""
    insight_ids: List[int]
    action: str = Field(..., regex="^(acknowledge|dismiss|export)$")