# backend/modules/loyalty/schemas/rewards_schemas.py

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from ..models.rewards_models import RewardType, RewardStatus, TriggerType


# Enums for API
class RewardTypeEnum(str, Enum):
    POINTS_DISCOUNT = "points_discount"
    PERCENTAGE_DISCOUNT = "percentage_discount"
    FIXED_DISCOUNT = "fixed_discount"
    FREE_ITEM = "free_item"
    FREE_DELIVERY = "free_delivery"
    BONUS_POINTS = "bonus_points"
    CASHBACK = "cashback"
    GIFT_CARD = "gift_card"
    TIER_UPGRADE = "tier_upgrade"
    CUSTOM = "custom"


class RewardStatusEnum(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    REDEEMED = "redeemed"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING = "pending"


class TriggerTypeEnum(str, Enum):
    ORDER_COMPLETE = "order_complete"
    POINTS_EARNED = "points_earned"
    TIER_UPGRADE = "tier_upgrade"
    BIRTHDAY = "birthday"
    ANNIVERSARY = "anniversary"
    REFERRAL_SUCCESS = "referral_success"
    MILESTONE = "milestone"
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    CONDITIONAL = "conditional"


# Base schemas
class RewardTemplateBase(BaseModel):
    """Base schema for reward templates"""

    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    reward_type: RewardTypeEnum
    value: Optional[float] = Field(None, ge=0)
    percentage: Optional[float] = Field(None, ge=0, le=100)
    points_cost: Optional[int] = Field(None, ge=0)

    # Item-specific
    item_id: Optional[int] = None
    category_ids: Optional[List[int]] = None

    # Restrictions
    min_order_amount: Optional[float] = Field(None, ge=0)
    max_discount_amount: Optional[float] = Field(None, ge=0)
    max_uses_per_customer: Optional[int] = Field(None, ge=1)
    max_uses_total: Optional[int] = Field(None, ge=1)

    # Validity
    valid_days: int = Field(30, ge=1, le=365)
    valid_from_date: Optional[datetime] = None
    valid_until_date: Optional[datetime] = None

    # Eligibility
    eligible_tiers: Optional[List[str]] = None

    # Trigger
    trigger_type: TriggerTypeEnum
    trigger_conditions: Optional[Dict[str, Any]] = None
    auto_apply: bool = False

    # Display
    title: str = Field(..., max_length=200)
    subtitle: Optional[str] = Field(None, max_length=300)
    terms_and_conditions: Optional[str] = None
    image_url: Optional[str] = Field(None, max_length=500)
    icon: Optional[str] = Field(None, max_length=50)

    # Settings
    is_active: bool = True
    is_featured: bool = False
    priority: int = Field(0, ge=0)


class RewardTemplateCreate(RewardTemplateBase):
    """Schema for creating reward templates"""

    @field_validator("eligible_tiers", mode="after")
    def validate_tiers(cls, v):
        if v:
            valid_tiers = ["bronze", "silver", "gold", "platinum", "vip"]
            for tier in v:
                if tier.lower() not in valid_tiers:
                    raise ValueError(f"Invalid tier: {tier}")
        return v

    @field_validator("trigger_conditions", mode="after")
    def validate_trigger_conditions(cls, v, values):
        if v and "trigger_type" in values:
            trigger_type = info.data["trigger_type"]

            # Validate conditions based on trigger type
            if trigger_type == TriggerTypeEnum.ORDER_COMPLETE:
                allowed_keys = ["min_order_amount", "item_categories", "day_of_week"]
            elif trigger_type == TriggerTypeEnum.MILESTONE:
                allowed_keys = ["total_orders", "total_spent", "lifetime_points"]
            else:
                allowed_keys = list(v.keys())  # Allow all for other types

            for key in v.keys():
                if key not in allowed_keys:
                    raise ValueError(
                        f'Invalid condition "{key}" for trigger type {trigger_type}'
                    )

        return v


class RewardTemplateUpdate(BaseModel):
    """Schema for updating reward templates"""

    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    value: Optional[float] = Field(None, ge=0)
    percentage: Optional[float] = Field(None, ge=0, le=100)
    points_cost: Optional[int] = Field(None, ge=0)
    min_order_amount: Optional[float] = Field(None, ge=0)
    max_discount_amount: Optional[float] = Field(None, ge=0)
    max_uses_per_customer: Optional[int] = Field(None, ge=1)
    max_uses_total: Optional[int] = Field(None, ge=1)
    valid_days: Optional[int] = Field(None, ge=1, le=365)
    eligible_tiers: Optional[List[str]] = None
    trigger_conditions: Optional[Dict[str, Any]] = None
    auto_apply: Optional[bool] = None
    title: Optional[str] = Field(None, max_length=200)
    subtitle: Optional[str] = Field(None, max_length=300)
    terms_and_conditions: Optional[str] = None
    image_url: Optional[str] = Field(None, max_length=500)
    icon: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    priority: Optional[int] = Field(None, ge=0)


class RewardTemplate(RewardTemplateBase):
    """Schema for reward template response"""

    id: int
    total_issued: int
    total_redeemed: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Customer Reward schemas
class CustomerRewardBase(BaseModel):
    """Base schema for customer rewards"""

    reward_type: RewardTypeEnum
    title: str = Field(..., max_length=200)
    description: Optional[str] = None
    value: Optional[float] = None
    percentage: Optional[float] = None
    points_cost: Optional[int] = None


class CustomerReward(CustomerRewardBase):
    """Schema for customer reward response"""

    id: int
    customer_id: int
    template_id: int
    code: str
    status: RewardStatusEnum
    valid_from: datetime
    valid_until: datetime
    redeemed_at: Optional[datetime]
    redeemed_amount: Optional[float]
    order_id: Optional[int]
    created_at: datetime

    # Computed properties
    is_valid: bool
    is_expired: bool
    days_until_expiry: Optional[int]

    class Config:
        from_attributes = True


class CustomerRewardSummary(BaseModel):
    """Simplified customer reward for listings"""

    id: int
    code: str
    title: str
    reward_type: RewardTypeEnum
    value: Optional[float]
    percentage: Optional[float]
    status: RewardStatusEnum
    valid_until: datetime
    days_until_expiry: Optional[int]


# Campaign schemas
class RewardCampaignBase(BaseModel):
    """Base schema for reward campaigns"""

    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    template_id: int
    target_criteria: Optional[Dict[str, Any]] = None
    target_tiers: Optional[List[str]] = None
    target_segments: Optional[List[int]] = None
    start_date: datetime
    end_date: datetime
    max_rewards_total: Optional[int] = Field(None, ge=1)
    max_rewards_per_customer: int = Field(1, ge=1)
    is_active: bool = True
    is_automated: bool = False


class RewardCampaignCreate(RewardCampaignBase):
    """Schema for creating reward campaigns"""

    @field_validator("end_date", mode="after")
    def validate_end_date(cls, v, values):
        if "start_date" in values and v <= values["start_date"]:
            raise ValueError("End date must be after start date")
        return v

    @field_validator("target_tiers", mode="after")
    def validate_target_tiers(cls, v):
        if v:
            valid_tiers = ["bronze", "silver", "gold", "platinum", "vip"]
            for tier in v:
                if tier.lower() not in valid_tiers:
                    raise ValueError(f"Invalid tier: {tier}")
        return v


class RewardCampaignUpdate(BaseModel):
    """Schema for updating reward campaigns"""

    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    target_criteria: Optional[Dict[str, Any]] = None
    target_tiers: Optional[List[str]] = None
    target_segments: Optional[List[int]] = None
    end_date: Optional[datetime] = None
    max_rewards_total: Optional[int] = Field(None, ge=1)
    max_rewards_per_customer: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None
    is_automated: Optional[bool] = None


class RewardCampaign(RewardCampaignBase):
    """Schema for reward campaign response"""

    id: int
    rewards_distributed: int
    target_audience_size: Optional[int]
    created_at: datetime
    updated_at: datetime

    # Related data
    template: Optional[RewardTemplate] = None

    class Config:
        from_attributes = True


# Redemption schemas
class RewardRedemptionRequest(BaseModel):
    """Schema for reward redemption request"""

    reward_code: str = Field(..., max_length=20)
    order_id: int
    staff_member_id: Optional[int] = None


class RewardRedemptionResponse(BaseModel):
    """Schema for reward redemption response"""

    success: bool
    discount_amount: Optional[float] = None
    reward_title: Optional[str] = None
    points_deducted: Optional[int] = None
    error: Optional[str] = None


class RewardRedemption(BaseModel):
    """Schema for redemption history"""

    id: int
    reward_id: int
    customer_id: int
    order_id: int
    original_order_amount: float
    discount_applied: float
    final_order_amount: float
    redemption_method: str
    staff_member_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# Points transaction schemas
class LoyaltyPointsTransaction(BaseModel):
    """Schema for points transaction"""

    id: int
    customer_id: int
    transaction_type: str
    points_change: int
    points_balance_before: int
    points_balance_after: int
    reason: str
    order_id: Optional[int]
    reward_id: Optional[int]
    source: str
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# Analytics schemas
class RewardAnalytics(BaseModel):
    """Schema for reward analytics"""

    total_issued: int
    total_redeemed: int
    total_expired: int
    redemption_rate: float
    total_discount_value: float
    average_discount_per_redemption: float


class RewardTemplateAnalytics(RewardAnalytics):
    """Schema for reward template specific analytics"""

    template_id: int
    template_name: str
    template_type: RewardTypeEnum


class CustomerLoyaltyStats(BaseModel):
    """Schema for customer loyalty statistics"""

    customer_id: int
    loyalty_points: int
    lifetime_points: int
    tier: str
    total_rewards_received: int
    total_rewards_redeemed: int
    total_discount_received: float
    points_earned_this_month: int
    points_redeemed_this_month: int
    next_tier_points_needed: Optional[int]


# Search and filter schemas
class RewardSearchParams(BaseModel):
    """Parameters for searching rewards"""

    customer_id: Optional[int] = None
    template_id: Optional[int] = None
    reward_type: Optional[RewardTypeEnum] = None
    status: Optional[List[RewardStatusEnum]] = None
    valid_only: bool = True
    expiring_soon: Optional[int] = Field(None, ge=1, le=30)  # Days until expiry
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    sort_by: str = Field(
        "created_at", pattern="^(created_at|valid_until|redeemed_at|value)$"
    )
    sort_order: str = Field("desc", pattern="^(asc|desc)$")


class RewardSearchResponse(BaseModel):
    """Response for reward search"""

    rewards: List[CustomerRewardSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


# Manual reward issuance
class ManualRewardIssuance(BaseModel):
    """Schema for manually issuing rewards"""

    customer_id: int
    template_id: int
    custom_message: Optional[str] = None
    notify_customer: bool = True


class BulkRewardIssuance(BaseModel):
    """Schema for bulk reward issuance"""

    customer_ids: List[int] = Field(..., min_items=1, max_items=1000)
    template_id: int
    custom_message: Optional[str] = None
    notify_customers: bool = True


class BulkRewardIssuanceResponse(BaseModel):
    """Response for bulk reward issuance"""

    total_customers: int
    successful_issuances: int
    failed_issuances: int
    errors: List[str]
    issued_reward_codes: List[str]


# Order completion processing
class OrderCompletionReward(BaseModel):
    """Schema for order completion reward processing"""

    order_id: int
    process_rewards: bool = True
    process_points: bool = True


class OrderCompletionResponse(BaseModel):
    """Response for order completion processing"""

    success: bool
    points_earned: int
    rewards_triggered: List[Dict[str, Any]]
    tier_upgrade: Optional[Dict[str, str]]
    error: Optional[str]
