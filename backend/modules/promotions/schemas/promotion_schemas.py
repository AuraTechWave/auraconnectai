# backend/modules/promotions/schemas/promotion_schemas.py

from pydantic import BaseModel, Field, field_validator, UUID4
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum

from ..models.promotion_models import (
    PromotionType,
    PromotionStatus,
    CouponType,
    DiscountTarget,
    ReferralStatus,
)


# Base schemas
class PromotionBase(BaseModel):
    """Base promotion schema"""

    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    promotion_type: PromotionType
    start_date: datetime
    end_date: datetime
    timezone: str = "UTC"
    discount_type: str
    discount_value: float = Field(..., ge=0)
    max_discount_amount: Optional[float] = Field(None, ge=0)
    min_order_amount: Optional[float] = Field(None, ge=0)
    target_type: DiscountTarget = DiscountTarget.ORDER_TOTAL
    target_items: Optional[Dict[str, Any]] = None
    target_customer_segments: Optional[List[str]] = None
    target_tiers: Optional[List[str]] = None
    max_uses_total: Optional[int] = Field(None, ge=1)
    max_uses_per_customer: int = Field(1, ge=1)
    conditions: Optional[Dict[str, Any]] = None
    stackable: bool = False
    requires_coupon: bool = False
    title: Optional[str] = Field(None, max_length=200)
    subtitle: Optional[str] = Field(None, max_length=300)
    image_url: Optional[str] = Field(None, max_length=500)
    banner_text: Optional[str] = Field(None, max_length=200)
    terms_and_conditions: Optional[str] = None
    priority: int = Field(0, ge=0)
    auto_apply: bool = False
    is_featured: bool = False
    is_public: bool = True
    ab_test_variant: Optional[str] = None
    ab_test_traffic_split: float = Field(100.0, ge=0, le=100)


class PromotionCreate(PromotionBase):
    """Schema for creating a promotion"""

    @field_validator("end_date")
    def end_date_after_start_date(cls, v, info):
        start_date = info.data.get("start_date")
        if start_date and v <= start_date:
            raise ValueError("End date must be after start date")
        return v

    @field_validator("discount_value")
    def validate_discount_value(cls, v, info):
        discount_type = info.data.get("discount_type")
        if discount_type == "percentage" and v > 100:
            raise ValueError("Percentage discount cannot exceed 100%")
        return v


class PromotionUpdate(BaseModel):
    """Schema for updating a promotion"""

    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    status: Optional[PromotionStatus] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    discount_value: Optional[float] = Field(None, ge=0)
    max_discount_amount: Optional[float] = Field(None, ge=0)
    min_order_amount: Optional[float] = Field(None, ge=0)
    max_uses_total: Optional[int] = Field(None, ge=1)
    max_uses_per_customer: Optional[int] = Field(None, ge=1)
    title: Optional[str] = Field(None, max_length=200)
    subtitle: Optional[str] = Field(None, max_length=300)
    image_url: Optional[str] = Field(None, max_length=500)
    priority: Optional[int] = Field(None, ge=0)
    is_featured: Optional[bool] = None
    is_public: Optional[bool] = None


class Promotion(PromotionBase):
    """Full promotion schema for responses"""

    id: int
    uuid: UUID4
    status: PromotionStatus
    current_uses: int
    impressions: int
    clicks: int
    conversions: int
    revenue_generated: float
    created_at: datetime
    updated_at: datetime

    # Computed properties
    is_active: bool
    usage_percentage: float
    days_remaining: int

    class Config:
        from_attributes = True


class PromotionSummary(BaseModel):
    """Summary promotion schema for lists"""

    id: int
    uuid: UUID4
    name: str
    promotion_type: PromotionType
    status: PromotionStatus
    discount_type: str
    discount_value: float
    start_date: datetime
    end_date: datetime
    current_uses: int
    max_uses_total: Optional[int]
    is_featured: bool
    is_active: bool
    days_remaining: int

    class Config:
        from_attributes = True


# Coupon schemas
class CouponBase(BaseModel):
    """Base coupon schema"""

    coupon_type: CouponType = CouponType.SINGLE_USE
    max_uses: int = Field(1, ge=1)
    customer_id: Optional[int] = None
    customer_email: Optional[str] = Field(None, max_length=255)
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None


class CouponCreate(CouponBase):
    """Schema for creating a coupon"""

    promotion_id: int
    code: Optional[str] = Field(None, max_length=50)  # Auto-generated if not provided
    batch_id: Optional[str] = None
    generation_method: str = "manual"


class CouponBulkCreate(BaseModel):
    """Schema for bulk coupon creation"""

    promotion_id: int
    quantity: int = Field(..., ge=1, le=10000)
    coupon_type: CouponType = CouponType.MULTI_USE
    max_uses: int = Field(1, ge=1)
    prefix: Optional[str] = Field(None, max_length=10)
    suffix: Optional[str] = Field(None, max_length=10)
    length: int = Field(8, ge=4, le=20)
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None


class Coupon(CouponBase):
    """Full coupon schema for responses"""

    id: int
    promotion_id: int
    code: str
    current_uses: int
    is_active: bool
    batch_id: Optional[str]
    generation_method: str
    created_at: datetime
    updated_at: datetime

    # Computed properties
    is_valid: bool
    remaining_uses: int

    # Related data
    promotion: Optional[PromotionSummary] = None

    class Config:
        from_attributes = True


class CouponValidationRequest(BaseModel):
    """Schema for coupon validation requests"""

    code: str = Field(..., max_length=50)
    customer_id: Optional[int] = None
    order_total: float = Field(..., ge=0)
    order_items: Optional[List[Dict[str, Any]]] = None


class CouponValidationResponse(BaseModel):
    """Schema for coupon validation responses"""

    is_valid: bool
    coupon: Optional[Coupon] = None
    discount_amount: float = 0.0
    error_message: Optional[str] = None
    applicable_items: Optional[List[Dict[str, Any]]] = None


# Referral program schemas
class ReferralProgramBase(BaseModel):
    """Base referral program schema"""

    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    referrer_reward_type: str
    referrer_reward_value: float = Field(..., ge=0)
    referee_reward_type: str
    referee_reward_value: float = Field(..., ge=0)
    min_referee_order_amount: float = Field(0.0, ge=0)
    max_referrals_per_customer: Optional[int] = Field(None, ge=1)
    referral_validity_days: int = Field(30, ge=1)
    start_date: datetime
    end_date: Optional[datetime] = None


class ReferralProgramCreate(ReferralProgramBase):
    """Schema for creating a referral program"""

    @field_validator("end_date")
    def end_date_after_start_date(cls, v, info):
        if v and info.data.get("start_date") and v <= info.data["start_date"]:
            raise ValueError("End date must be after start date")
        return v


class ReferralProgram(ReferralProgramBase):
    """Full referral program schema"""

    id: int
    is_active: bool
    total_referrals: int
    successful_referrals: int
    total_rewards_issued: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomerReferralBase(BaseModel):
    """Base customer referral schema"""

    referee_email: str = Field(..., max_length=255)


class CustomerReferralCreate(CustomerReferralBase):
    """Schema for creating a referral"""

    program_id: int
    referrer_id: int


class CustomerReferral(CustomerReferralBase):
    """Full customer referral schema"""

    id: int
    program_id: int
    referrer_id: int
    referee_id: Optional[int]
    referral_code: str
    status: ReferralStatus
    completed_at: Optional[datetime]
    qualifying_order_id: Optional[int]
    referrer_rewarded: bool
    referee_rewarded: bool
    referrer_reward_amount: Optional[float]
    referee_reward_amount: Optional[float]
    expires_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Usage and analytics schemas
class PromotionUsageBase(BaseModel):
    """Base promotion usage schema"""

    promotion_id: int
    customer_id: Optional[int]
    order_id: int
    discount_amount: float
    original_order_amount: float
    final_order_amount: float
    usage_method: str
    coupon_code: Optional[str]


class PromotionUsage(PromotionUsageBase):
    """Full promotion usage schema"""

    id: int
    staff_member_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class PromotionAnalyticsBase(BaseModel):
    """Base promotion analytics schema"""

    promotion_id: int
    date: datetime
    period_type: str
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    revenue: float = 0.0
    discount_amount: float = 0.0
    unique_customers: int = 0


class PromotionAnalytics(PromotionAnalyticsBase):
    """Full promotion analytics schema"""

    id: int
    conversion_rate: float
    average_order_value: float
    customer_acquisition_cost: float
    return_on_investment: float
    created_at: datetime

    class Config:
        from_attributes = True


# Search and filter schemas
class PromotionSearchParams(BaseModel):
    """Parameters for searching promotions"""

    query: Optional[str] = None
    promotion_type: Optional[List[PromotionType]] = None
    status: Optional[List[PromotionStatus]] = None
    discount_type: Optional[List[str]] = None
    is_featured: Optional[bool] = None
    is_public: Optional[bool] = None
    start_date_from: Optional[datetime] = None
    start_date_to: Optional[datetime] = None
    target_customer_segment: Optional[str] = None
    requires_coupon: Optional[bool] = None
    stackable: Optional[bool] = None
    min_discount_value: Optional[float] = None
    max_discount_value: Optional[float] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    sort_by: str = "created_at"
    sort_order: str = Field("desc", pattern="^(asc|desc)$")


class PromotionSearchResponse(BaseModel):
    """Response for promotion search"""

    promotions: List[PromotionSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


# Discount calculation schemas
class DiscountCalculationRequest(BaseModel):
    """Request for calculating discounts"""

    customer_id: Optional[int] = None
    order_total: float = Field(..., ge=0)
    order_items: List[Dict[str, Any]]
    coupon_codes: Optional[List[str]] = None
    promotion_ids: Optional[List[int]] = None
    customer_tier: Optional[str] = None


class DiscountCalculationResponse(BaseModel):
    """Response for discount calculations"""

    original_total: float
    final_total: float
    total_discount: float
    applied_promotions: List[Dict[str, Any]]
    applicable_promotions: List[PromotionSummary]
    invalid_coupons: List[str]
    warnings: List[str]


# A/B Testing schemas
class ABTestVariant(BaseModel):
    """A/B test variant configuration"""

    variant_name: str
    traffic_split: float = Field(..., ge=0, le=100)
    promotion_config: Dict[str, Any]


class ABTestConfig(BaseModel):
    """A/B test configuration"""

    test_name: str
    variants: List[ABTestVariant]
    start_date: datetime
    end_date: datetime
    success_metric: str

    @field_validator("variants")
    def validate_traffic_split(cls, v):
        total_split = sum(variant.traffic_split for variant in v)
        if abs(total_split - 100.0) > 0.01:  # Allow for floating point precision
            raise ValueError("Total traffic split must equal 100%")
        return v


# Reporting schemas
class PromotionReport(BaseModel):
    """Promotion performance report"""

    promotion: PromotionSummary
    analytics: Dict[str, Any]
    top_customers: List[Dict[str, Any]]
    usage_by_day: List[Dict[str, Any]]
    revenue_impact: Dict[str, float]
    conversion_funnel: Dict[str, int]


class CouponReport(BaseModel):
    """Coupon usage report"""

    total_generated: int
    total_used: int
    usage_rate: float
    top_performing_codes: List[Dict[str, Any]]
    usage_by_customer_segment: Dict[str, int]


class ReferralReport(BaseModel):
    """Referral program report"""

    program: ReferralProgram
    total_sent: int
    total_completed: int
    completion_rate: float
    total_rewards_issued: float
    average_time_to_complete: float
    top_referrers: List[Dict[str, Any]]
