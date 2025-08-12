# backend/modules/promotions/models/promotion_models.py

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum
import uuid
from datetime import datetime

from core.database import Base
from core.mixins import TimestampMixin


class PromotionType(str, Enum):
    """Types of promotions"""
    PERCENTAGE_DISCOUNT = "percentage_discount"    # 20% off
    FIXED_DISCOUNT = "fixed_discount"             # $10 off
    BOGO = "buy_one_get_one"                      # Buy one get one free/discounted
    FREE_SHIPPING = "free_shipping"               # Free delivery
    BUNDLE_DISCOUNT = "bundle_discount"           # Discount on specific combinations
    TIERED_DISCOUNT = "tiered_discount"           # Spend $50 get 10%, $100 get 20%
    CASHBACK = "cashback"                         # Get money back
    LOYALTY_MULTIPLIER = "loyalty_multiplier"     # 2x points
    REFERRAL_BONUS = "referral_bonus"             # Referral rewards
    SEASONAL = "seasonal"                         # Holiday/seasonal promotions
    FLASH_SALE = "flash_sale"                     # Limited time offers
    MEMBERSHIP_DISCOUNT = "membership_discount"    # Member-only discounts


class PromotionStatus(str, Enum):
    """Promotion status states"""
    DRAFT = "draft"                               # Being created
    SCHEDULED = "scheduled"                       # Scheduled to start
    ACTIVE = "active"                            # Currently running
    PAUSED = "paused"                           # Temporarily paused
    EXPIRED = "expired"                         # Past end date
    CANCELLED = "cancelled"                     # Manually cancelled
    ENDED = "ended"                            # Completed successfully


class CouponType(str, Enum):
    """Types of coupons"""
    SINGLE_USE = "single_use"                   # One-time use
    MULTI_USE = "multi_use"                     # Limited uses
    UNLIMITED = "unlimited"                     # No usage limit
    CUSTOMER_SPECIFIC = "customer_specific"      # Tied to specific customer
    BULK_GENERATED = "bulk_generated"           # Generated in bulk


class DiscountTarget(str, Enum):
    """What the discount applies to"""
    ORDER_TOTAL = "order_total"                 # Total order value
    SHIPPING = "shipping"                       # Shipping costs
    SPECIFIC_ITEMS = "specific_items"           # Specific menu items
    CATEGORIES = "categories"                   # Item categories
    BRANDS = "brands"                          # Specific brands
    MINIMUM_QUANTITY = "minimum_quantity"       # Based on quantity


class ReferralStatus(str, Enum):
    """Referral program status"""
    PENDING = "pending"                         # Referral sent, not completed
    COMPLETED = "completed"                     # Successfully referred
    REWARDED = "rewarded"                      # Rewards issued
    EXPIRED = "expired"                        # Referral expired
    CANCELLED = "cancelled"                    # Cancelled referral


class Promotion(Base, TimestampMixin):
    """Main promotion/campaign model"""
    __tablename__ = "promotions"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True)
    
    # Basic information
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text)
    promotion_type = Column(String(50), nullable=False, index=True)
    status = Column(String(20), nullable=False, default=PromotionStatus.DRAFT, index=True)
    
    # Timing
    start_date = Column(DateTime, nullable=False, index=True)
    end_date = Column(DateTime, nullable=False, index=True)
    timezone = Column(String(50), default="UTC")
    
    # Discount configuration
    discount_type = Column(String(50), nullable=False)  # percentage, fixed, etc.
    discount_value = Column(Float, nullable=False)
    max_discount_amount = Column(Float)  # Cap for percentage discounts
    min_order_amount = Column(Float)     # Minimum order to qualify
    
    # Target configuration
    target_type = Column(String(50), nullable=False, default=DiscountTarget.ORDER_TOTAL)
    target_items = Column(JSONB)         # Specific items/categories
    target_customer_segments = Column(JSONB)  # Customer segments
    target_tiers = Column(JSONB)         # Loyalty tiers
    
    # Usage limits
    max_uses_total = Column(Integer)     # Total usage limit
    max_uses_per_customer = Column(Integer, default=1)
    current_uses = Column(Integer, default=0)
    
    # Conditions and rules
    conditions = Column(JSONB)           # Complex conditions
    stackable = Column(Boolean, default=False)  # Can combine with other promos
    requires_coupon = Column(Boolean, default=False)
    
    # Display and marketing
    title = Column(String(200))          # Marketing title
    subtitle = Column(String(300))
    image_url = Column(String(500))
    banner_text = Column(String(200))
    terms_and_conditions = Column(Text)
    
    # Priority and scheduling
    priority = Column(Integer, default=0, index=True)
    auto_apply = Column(Boolean, default=False)
    is_featured = Column(Boolean, default=False)
    is_public = Column(Boolean, default=True)
    
    # A/B testing
    ab_test_variant = Column(String(50))
    ab_test_traffic_split = Column(Float, default=100.0)
    
    # Analytics
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    revenue_generated = Column(Float, default=0.0)
    
    # Relationships
    coupons = relationship("Coupon", back_populates="promotion", cascade="all, delete-orphan")
    usages = relationship("PromotionUsage", back_populates="promotion")
    analytics = relationship("PromotionAnalytics", back_populates="promotion")
    
    # Indexes
    __table_args__ = (
        Index('ix_promotions_status_dates', 'status', 'start_date', 'end_date'),
        Index('ix_promotions_type_status', 'promotion_type', 'status'),
        Index('ix_promotions_active', 'status', 'start_date', 'end_date'),
        Index('ix_promotions_featured', 'is_featured', 'status'),
    )
    
    @property
    def is_active(self) -> bool:
        """Check if promotion is currently active"""
        now = datetime.utcnow()
        return (
            self.status == PromotionStatus.ACTIVE and
            self.start_date <= now <= self.end_date
        )
    
    @property
    def usage_percentage(self) -> float:
        """Calculate usage percentage"""
        if not self.max_uses_total:
            return 0.0
        return (self.current_uses / self.max_uses_total) * 100
    
    @property
    def days_remaining(self) -> int:
        """Days remaining for promotion"""
        if self.end_date:
            delta = self.end_date - datetime.utcnow()
            return max(0, delta.days)
        return 0


class Coupon(Base, TimestampMixin):
    """Coupon codes for promotions"""
    __tablename__ = "coupons"
    
    id = Column(Integer, primary_key=True, index=True)
    promotion_id = Column(Integer, ForeignKey("promotions.id"), nullable=False, index=True)
    
    # Coupon details
    code = Column(String(50), unique=True, nullable=False, index=True)
    coupon_type = Column(String(30), nullable=False, default=CouponType.SINGLE_USE)
    
    # Usage tracking
    max_uses = Column(Integer, default=1)
    current_uses = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, index=True)
    
    # Customer association
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    customer_email = Column(String(255), index=True)  # For guest users
    
    # Validity
    valid_from = Column(DateTime, default=func.now())
    valid_until = Column(DateTime)
    
    # Generation metadata
    batch_id = Column(String(100), index=True)  # For bulk generation
    generation_method = Column(String(50))      # manual, auto, bulk
    generated_by = Column(Integer, ForeignKey("rbac_users.id"))
    
    # Relationships
    promotion = relationship("Promotion", back_populates="coupons")
    customer = relationship("Customer", foreign_keys=[customer_id])
    usages = relationship("CouponUsage", back_populates="coupon")
    
    # Indexes
    __table_args__ = (
        Index('ix_coupons_code_active', 'code', 'is_active'),
        Index('ix_coupons_customer_active', 'customer_id', 'is_active'),
        Index('ix_coupons_batch', 'batch_id', 'coupon_type'),
    )
    
    @property  
    def is_valid(self) -> bool:
        """Check if coupon is currently valid"""
        now = datetime.utcnow()
        return (
            self.is_active and
            self.current_uses < self.max_uses and
            (not self.valid_from or self.valid_from <= now) and
            (not self.valid_until or now <= self.valid_until)
        )
    
    @property
    def remaining_uses(self) -> int:
        """Remaining uses for this coupon"""
        return max(0, self.max_uses - self.current_uses)


class ReferralProgram(Base, TimestampMixin):
    """Referral program configuration"""
    __tablename__ = "referral_programs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Program details
    name = Column(String(200), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True, index=True)
    
    # Rewards configuration
    referrer_reward_type = Column(String(50), nullable=False)  # discount, points, cash
    referrer_reward_value = Column(Float, nullable=False)
    referee_reward_type = Column(String(50), nullable=False)
    referee_reward_value = Column(Float, nullable=False)
    
    # Conditions
    min_referee_order_amount = Column(Float, default=0.0)
    max_referrals_per_customer = Column(Integer)
    referral_validity_days = Column(Integer, default=30)
    
    # Timing
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime)
    
    # Tracking
    total_referrals = Column(Integer, default=0)
    successful_referrals = Column(Integer, default=0)
    total_rewards_issued = Column(Float, default=0.0)
    
    # Relationships
    referrals = relationship("CustomerReferral", back_populates="program")


class CustomerReferral(Base, TimestampMixin):  
    """Individual customer referrals"""
    __tablename__ = "customer_referrals"
    
    id = Column(Integer, primary_key=True, index=True)
    program_id = Column(Integer, ForeignKey("referral_programs.id"), nullable=False, index=True)
    
    # Referral parties
    referrer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    referee_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    referee_email = Column(String(255), index=True)  # Before signup
    
    # Referral tracking
    referral_code = Column(String(50), unique=True, nullable=False, index=True)
    status = Column(String(20), nullable=False, default=ReferralStatus.PENDING, index=True)
    
    # Completion tracking
    completed_at = Column(DateTime)
    qualifying_order_id = Column(Integer, ForeignKey("orders.id"))
    referrer_rewarded = Column(Boolean, default=False)
    referee_rewarded = Column(Boolean, default=False)
    
    # Reward details
    referrer_reward_amount = Column(Float)
    referee_reward_amount = Column(Float)
    referrer_reward_issued_at = Column(DateTime)
    referee_reward_issued_at = Column(DateTime)
    
    # Expiration
    expires_at = Column(DateTime, index=True)
    
    # Relationships
    program = relationship("ReferralProgram", back_populates="referrals")
    referrer = relationship("Customer", foreign_keys=[referrer_id], back_populates="referrals_made")
    referee = relationship("Customer", foreign_keys=[referee_id], back_populates="referrals_received")
    qualifying_order = relationship("Order", foreign_keys=[qualifying_order_id])
    
    # Indexes
    __table_args__ = (
        Index('ix_referrals_status_expires', 'status', 'expires_at'),
        Index('ix_referrals_referrer_status', 'referrer_id', 'status'),
        Index('ix_referrals_code_status', 'referral_code', 'status'),
    )


class PromotionUsage(Base, TimestampMixin):
    """Track promotion usage"""
    __tablename__ = "promotion_usages"
    
    id = Column(Integer, primary_key=True, index=True)
    promotion_id = Column(Integer, ForeignKey("promotions.id"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    
    # Usage details
    discount_amount = Column(Float, nullable=False)
    original_order_amount = Column(Float, nullable=False)
    final_order_amount = Column(Float, nullable=False)
    
    # Context
    usage_method = Column(String(50))    # auto_applied, coupon_code, manual
    coupon_code = Column(String(50))
    staff_member_id = Column(Integer, ForeignKey("staff_members.id"))
    
    # Relationships
    promotion = relationship("Promotion", back_populates="usages")
    customer = relationship("Customer", foreign_keys=[customer_id])
    order = relationship("Order", foreign_keys=[order_id])
    
    # Indexes
    __table_args__ = (
        Index('ix_promotion_usages_promo_customer', 'promotion_id', 'customer_id'),
        Index('ix_promotion_usages_order', 'order_id'),
        Index('ix_promotion_usages_date', 'created_at'),
    )


class CouponUsage(Base, TimestampMixin):
    """Track coupon usage"""
    __tablename__ = "coupon_usages"
    
    id = Column(Integer, primary_key=True, index=True)
    coupon_id = Column(Integer, ForeignKey("coupons.id"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    
    # Usage details
    discount_amount = Column(Float, nullable=False)
    usage_context = Column(JSONB)  # Additional context data
    
    # Relationships
    coupon = relationship("Coupon", back_populates="usages")
    customer = relationship("Customer", foreign_keys=[customer_id])
    order = relationship("Order", foreign_keys=[order_id])


class PromotionAnalytics(Base, TimestampMixin):
    """Analytics data for promotions"""
    __tablename__ = "promotion_analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    promotion_id = Column(Integer, ForeignKey("promotions.id"), nullable=False, index=True)
    
    # Time period
    date = Column(DateTime, nullable=False, index=True)
    period_type = Column(String(20), nullable=False)  # daily, weekly, monthly
    
    # Metrics
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    revenue = Column(Float, default=0.0)
    discount_amount = Column(Float, default=0.0)
    unique_customers = Column(Integer, default=0)
    
    # Calculated metrics
    conversion_rate = Column(Float, default=0.0)
    average_order_value = Column(Float, default=0.0)
    customer_acquisition_cost = Column(Float, default=0.0)
    return_on_investment = Column(Float, default=0.0)
    
    # Relationships
    promotion = relationship("Promotion", back_populates="analytics")
    
    # Indexes
    __table_args__ = (
        Index('ix_promotion_analytics_promo_date', 'promotion_id', 'date'),
        Index('ix_promotion_analytics_period', 'period_type', 'date'),
    )


class PromotionRule(Base, TimestampMixin):
    """Complex promotion rules and conditions"""
    __tablename__ = "promotion_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    promotion_id = Column(Integer, ForeignKey("promotions.id"), nullable=False, index=True)
    
    # Rule configuration
    rule_type = Column(String(50), nullable=False)  # customer_segment, item_quantity, etc.
    rule_operator = Column(String(20), nullable=True)  # equals, greater_than, in, etc.
    rule_value = Column(JSONB, nullable=True)

    # Automation-specific configuration (for marketing campaign triggers and actions)
    # These fields are optional and will be populated by automation & scheduling services.
    condition_type = Column(String(50), nullable=True, index=True)  # e.g., customer_lifecycle, purchase_behavior
    condition_value = Column(JSONB, nullable=True)  # JSON structure defining the condition specifics
    action_type = Column(String(50), nullable=True)  # e.g., activate_promotion, deactivate_promotion
    action_value = Column(JSONB, nullable=True)  # JSON detailing action parameters (duration_hours, status, etc.)

    # Metadata
    description = Column(String(500))
    is_active = Column(Boolean, default=True)
    
    # Relationships
    promotion = relationship("Promotion", foreign_keys=[promotion_id])


# Update Customer model to include referral relationships
from modules.customers.models.customer_models import Customer

# Add referral relationships to Customer model
Customer.referrals_made = relationship(
    "CustomerReferral", 
    foreign_keys="CustomerReferral.referrer_id",
    back_populates="referrer"
)
Customer.referrals_received = relationship(
    "CustomerReferral",
    foreign_keys="CustomerReferral.referee_id", 
    back_populates="referee"
)