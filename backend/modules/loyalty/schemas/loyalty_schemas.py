# backend/modules/loyalty/schemas/loyalty_schemas.py

"""
Comprehensive schemas for loyalty and rewards system.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, date
from pydantic import BaseModel, Field, validator, root_validator
from decimal import Decimal

from ..models.rewards_models import (
    RewardType, RewardStatus, TriggerType
)


# ========== Loyalty Program Schemas ==========

class LoyaltyProgramBase(BaseModel):
    """Base loyalty program schema"""
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    points_per_dollar: float = Field(1.0, ge=0)
    points_expiry_days: Optional[int] = Field(None, ge=1)
    is_active: bool = True


class LoyaltyProgramCreate(LoyaltyProgramBase):
    """Create loyalty program"""
    tiers: Optional[List[Dict[str, Any]]] = []
    welcome_bonus_points: int = Field(0, ge=0)
    referral_bonus_points: int = Field(0, ge=0)
    birthday_bonus_points: int = Field(0, ge=0)


class LoyaltyProgramUpdate(BaseModel):
    """Update loyalty program"""
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    points_per_dollar: Optional[float] = Field(None, ge=0)
    points_expiry_days: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None
    welcome_bonus_points: Optional[int] = Field(None, ge=0)
    referral_bonus_points: Optional[int] = Field(None, ge=0)
    birthday_bonus_points: Optional[int] = Field(None, ge=0)


class LoyaltyProgramResponse(LoyaltyProgramBase):
    """Loyalty program response"""
    id: int
    restaurant_id: int
    tiers: List[Dict[str, Any]]
    welcome_bonus_points: int
    referral_bonus_points: int
    birthday_bonus_points: int
    total_members: int
    active_members: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


# ========== Customer Loyalty Schemas ==========

class CustomerLoyaltyBase(BaseModel):
    """Base customer loyalty schema"""
    customer_id: int
    points_balance: int = 0
    lifetime_points_earned: int = 0
    lifetime_points_spent: int = 0
    current_tier: str = "bronze"
    tier_progress: float = 0.0


class CustomerLoyaltyCreate(CustomerLoyaltyBase):
    """Create customer loyalty record"""
    program_id: int
    referred_by_customer_id: Optional[int] = None


class CustomerLoyaltyUpdate(BaseModel):
    """Update customer loyalty"""
    points_balance: Optional[int] = None
    current_tier: Optional[str] = None
    tier_progress: Optional[float] = None
    is_active: Optional[bool] = None


class CustomerLoyaltyResponse(CustomerLoyaltyBase):
    """Customer loyalty response"""
    id: int
    program_id: int
    joined_at: datetime
    last_activity_at: Optional[datetime]
    next_tier_points: Optional[int]
    points_expiring_soon: int
    available_rewards: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


class CustomerLoyaltyStats(BaseModel):
    """Customer loyalty statistics"""
    customer_id: int
    points_balance: int
    lifetime_points_earned: int
    lifetime_points_spent: int
    current_tier: str
    tier_benefits: List[Dict[str, Any]]
    points_history: List[Dict[str, Any]]
    rewards_earned: int
    rewards_redeemed: int
    average_order_value: float
    visit_frequency: str
    member_since: date
    days_until_tier_upgrade: Optional[int]
    points_expiring_30_days: int


# ========== Points Transaction Schemas ==========

class PointsTransactionBase(BaseModel):
    """Base points transaction schema"""
    customer_id: int
    transaction_type: str = Field(..., regex="^(earned|redeemed|expired|adjusted|transferred)$")
    points_change: int
    reason: str = Field(..., max_length=200)
    order_id: Optional[int] = None
    reward_id: Optional[int] = None


class PointsTransactionCreate(PointsTransactionBase):
    """Create points transaction"""
    source: str = Field("system", max_length=50)
    reference_id: Optional[str] = Field(None, max_length=100)
    expires_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = {}


class PointsTransactionResponse(PointsTransactionBase):
    """Points transaction response"""
    id: int
    points_balance_before: int
    points_balance_after: int
    source: str
    reference_id: Optional[str]
    expires_at: Optional[datetime]
    is_expired: bool
    staff_member_id: Optional[int]
    staff_member_name: Optional[str]
    created_at: datetime
    
    class Config:
        orm_mode = True


class PointsAdjustment(BaseModel):
    """Manual points adjustment"""
    customer_id: int
    points: int = Field(..., description="Positive to add, negative to deduct")
    reason: str = Field(..., min_length=5, max_length=200)
    expires_at: Optional[datetime] = None
    notify_customer: bool = True


class PointsTransfer(BaseModel):
    """Transfer points between customers"""
    from_customer_id: int
    to_customer_id: int
    points: int = Field(..., gt=0)
    reason: Optional[str] = Field("Points transfer", max_length=200)
    
    @root_validator
    def validate_transfer(cls, values):
        if values.get('from_customer_id') == values.get('to_customer_id'):
            raise ValueError("Cannot transfer points to the same customer")
        return values


# ========== Reward Template Schemas ==========

class RewardTemplateBase(BaseModel):
    """Base reward template schema"""
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    reward_type: RewardType
    value: Optional[float] = Field(None, ge=0)
    percentage: Optional[float] = Field(None, ge=0, le=100)
    points_cost: Optional[int] = Field(None, ge=0)
    title: str = Field(..., max_length=200)
    subtitle: Optional[str] = Field(None, max_length=300)
    terms_and_conditions: Optional[str] = None
    image_url: Optional[str] = Field(None, max_length=500)
    icon: Optional[str] = Field(None, max_length=50)


class RewardTemplateCreate(RewardTemplateBase):
    """Create reward template"""
    item_id: Optional[int] = None
    category_ids: Optional[List[int]] = []
    min_order_amount: Optional[float] = Field(None, ge=0)
    max_discount_amount: Optional[float] = Field(None, ge=0)
    max_uses_per_customer: Optional[int] = Field(None, ge=1)
    max_uses_total: Optional[int] = Field(None, ge=1)
    valid_days: int = Field(30, ge=1)
    valid_from_date: Optional[datetime] = None
    valid_until_date: Optional[datetime] = None
    eligible_tiers: Optional[List[str]] = []
    trigger_type: TriggerType
    trigger_conditions: Optional[Dict[str, Any]] = {}
    auto_apply: bool = False
    is_featured: bool = False
    priority: int = Field(0, ge=0)


class RewardTemplateUpdate(BaseModel):
    """Update reward template"""
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    value: Optional[float] = Field(None, ge=0)
    percentage: Optional[float] = Field(None, ge=0, le=100)
    points_cost: Optional[int] = Field(None, ge=0)
    title: Optional[str] = Field(None, max_length=200)
    subtitle: Optional[str] = Field(None, max_length=300)
    terms_and_conditions: Optional[str] = None
    image_url: Optional[str] = Field(None, max_length=500)
    icon: Optional[str] = Field(None, max_length=50)
    min_order_amount: Optional[float] = Field(None, ge=0)
    max_discount_amount: Optional[float] = Field(None, ge=0)
    max_uses_per_customer: Optional[int] = Field(None, ge=1)
    max_uses_total: Optional[int] = Field(None, ge=1)
    eligible_tiers: Optional[List[str]] = None
    auto_apply: Optional[bool] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    priority: Optional[int] = Field(None, ge=0)


class RewardTemplateResponse(RewardTemplateBase):
    """Reward template response"""
    id: int
    item_id: Optional[int]
    category_ids: List[int]
    min_order_amount: Optional[float]
    max_discount_amount: Optional[float]
    max_uses_per_customer: Optional[int]
    max_uses_total: Optional[int]
    valid_days: int
    valid_from_date: Optional[datetime]
    valid_until_date: Optional[datetime]
    eligible_tiers: List[str]
    trigger_type: str
    trigger_conditions: Dict[str, Any]
    auto_apply: bool
    is_active: bool
    is_featured: bool
    priority: int
    total_issued: int
    total_redeemed: int
    redemption_rate: float
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


# ========== Customer Reward Schemas ==========

class CustomerRewardBase(BaseModel):
    """Base customer reward schema"""
    customer_id: int
    template_id: int
    reward_type: RewardType
    title: str
    description: Optional[str]
    value: Optional[float]
    percentage: Optional[float]
    points_cost: Optional[int]


class CustomerRewardCreate(CustomerRewardBase):
    """Create customer reward (usually system-generated)"""
    trigger_data: Optional[Dict[str, Any]] = {}
    valid_days_override: Optional[int] = None


class ManualRewardIssuance(BaseModel):
    """Manual reward issuance request"""
    customer_id: int
    template_id: int
    reason: str = Field(..., min_length=5, max_length=200)
    valid_days_override: Optional[int] = Field(None, ge=1, le=365)
    notify_customer: bool = True


class BulkRewardIssuance(BaseModel):
    """Bulk reward issuance request"""
    template_id: int
    customer_ids: Optional[List[int]] = Field(None, min_items=1, max_items=1000)
    customer_criteria: Optional[Dict[str, Any]] = None
    reason: str = Field(..., min_length=5, max_length=200)
    notify_customers: bool = True
    
    @root_validator
    def validate_targeting(cls, values):
        customer_ids = values.get('customer_ids')
        customer_criteria = values.get('customer_criteria')
        
        if not customer_ids and not customer_criteria:
            raise ValueError("Either customer_ids or customer_criteria must be provided")
        if customer_ids and customer_criteria:
            raise ValueError("Provide either customer_ids or customer_criteria, not both")
        
        return values


class CustomerRewardResponse(CustomerRewardBase):
    """Customer reward response"""
    id: int
    code: str
    status: str
    valid_from: datetime
    valid_until: datetime
    is_valid: bool
    is_expired: bool
    days_until_expiry: int
    reserved_at: Optional[datetime]
    redeemed_at: Optional[datetime]
    order_id: Optional[int]
    redeemed_amount: Optional[float]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


class CustomerRewardSummary(BaseModel):
    """Summary of customer's rewards"""
    customer_id: int
    available_rewards: int
    total_rewards_earned: int
    total_rewards_redeemed: int
    rewards_expiring_soon: int
    total_savings: float
    rewards_by_type: Dict[str, int]
    recent_rewards: List[CustomerRewardResponse]


# ========== Reward Redemption Schemas ==========

class RewardRedemptionRequest(BaseModel):
    """Request to redeem a reward"""
    reward_code: str
    order_id: int
    order_amount: float = Field(..., gt=0)
    
    @validator('reward_code')
    def validate_code(cls, v):
        if not v or len(v) < 5:
            raise ValueError("Invalid reward code")
        return v.upper()


class RewardRedemptionResponse(BaseModel):
    """Reward redemption response"""
    success: bool
    reward_id: int
    discount_amount: float
    final_order_amount: float
    message: str
    redemption_id: Optional[int]


class RewardValidationRequest(BaseModel):
    """Request to validate a reward"""
    reward_code: str
    order_amount: float = Field(..., gt=0)
    order_items: Optional[List[Dict[str, Any]]] = []


class RewardValidationResponse(BaseModel):
    """Reward validation response"""
    is_valid: bool
    reward_type: Optional[str]
    discount_amount: Optional[float]
    applicable_items: Optional[List[int]]
    validation_errors: List[str]
    terms_and_conditions: Optional[str]


# ========== Campaign Schemas ==========

class RewardCampaignBase(BaseModel):
    """Base reward campaign schema"""
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    template_id: int
    start_date: datetime
    end_date: datetime
    max_rewards_total: Optional[int] = Field(None, ge=1)
    max_rewards_per_customer: int = Field(1, ge=1)


class RewardCampaignCreate(RewardCampaignBase):
    """Create reward campaign"""
    target_criteria: Optional[Dict[str, Any]] = {}
    target_tiers: Optional[List[str]] = []
    target_segments: Optional[List[str]] = []
    is_automated: bool = False


class RewardCampaignUpdate(BaseModel):
    """Update reward campaign"""
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    end_date: Optional[datetime] = None
    max_rewards_total: Optional[int] = Field(None, ge=1)
    max_rewards_per_customer: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None
    is_automated: Optional[bool] = None


class RewardCampaignResponse(RewardCampaignBase):
    """Reward campaign response"""
    id: int
    target_criteria: Dict[str, Any]
    target_tiers: List[str]
    target_segments: List[str]
    is_active: bool
    is_automated: bool
    rewards_distributed: int
    target_audience_size: Optional[int]
    distribution_rate: float
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


# ========== Analytics Schemas ==========

class RewardAnalyticsRequest(BaseModel):
    """Request for reward analytics"""
    template_id: Optional[int] = None
    campaign_id: Optional[int] = None
    start_date: date
    end_date: date
    group_by: str = Field("day", regex="^(day|week|month)$")


class RewardAnalyticsResponse(BaseModel):
    """Reward analytics response"""
    period: Dict[str, date]
    summary: Dict[str, Any]
    trends: List[Dict[str, Any]]
    performance_metrics: Dict[str, float]
    customer_segments: List[Dict[str, Any]]
    revenue_impact: Dict[str, float]


class LoyaltyProgramAnalytics(BaseModel):
    """Overall loyalty program analytics"""
    program_id: int
    period: Dict[str, date]
    member_statistics: Dict[str, Any]
    points_statistics: Dict[str, Any]
    reward_statistics: Dict[str, Any]
    engagement_metrics: Dict[str, float]
    revenue_metrics: Dict[str, float]
    tier_distribution: Dict[str, int]
    top_performers: List[Dict[str, Any]]


# ========== Order Integration Schemas ==========

class OrderCompletionReward(BaseModel):
    """Check and issue rewards on order completion"""
    order_id: int
    customer_id: int
    order_amount: float = Field(..., gt=0)
    order_items: List[Dict[str, Any]]
    payment_method: Optional[str] = None


class OrderCompletionResponse(BaseModel):
    """Response after processing order for rewards"""
    points_earned: int
    rewards_triggered: List[Dict[str, Any]]
    tier_progress: Dict[str, Any]
    notifications_sent: bool


# ========== Search and Filter Schemas ==========

class RewardSearchParams(BaseModel):
    """Search parameters for rewards"""
    customer_id: Optional[int] = None
    reward_type: Optional[RewardType] = None
    status: Optional[RewardStatus] = None
    is_expired: Optional[bool] = None
    min_value: Optional[float] = Field(None, ge=0)
    max_value: Optional[float] = Field(None, ge=0)
    valid_on_date: Optional[date] = None
    search_text: Optional[str] = Field(None, max_length=100)
    sort_by: str = Field("created_at", regex="^(created_at|valid_until|value|status)$")
    sort_order: str = Field("desc", regex="^(asc|desc)$")
    page: int = Field(1, ge=1)
    limit: int = Field(50, ge=1, le=200)


class RewardSearchResponse(BaseModel):
    """Search response for rewards"""
    items: List[CustomerRewardResponse]
    total: int
    page: int
    pages: int
    has_next: bool
    has_prev: bool