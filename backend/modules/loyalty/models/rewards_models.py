# backend/modules/loyalty/models/rewards_models.py

from sqlalchemy import (Column, Integer, String, ForeignKey, DateTime, 
                        Float, Text, Boolean, Enum as SQLEnum, Index, CheckConstraint)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from backend.core.database import Base
from backend.core.mixins import TimestampMixin
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional


class RewardType(str, Enum):
    """Types of rewards available"""
    POINTS_DISCOUNT = "points_discount"      # Discount using points
    PERCENTAGE_DISCOUNT = "percentage_discount"  # Percentage off order
    FIXED_DISCOUNT = "fixed_discount"        # Fixed dollar amount off
    FREE_ITEM = "free_item"                  # Free menu item
    FREE_DELIVERY = "free_delivery"          # Free delivery fee
    BONUS_POINTS = "bonus_points"            # Extra points multiplier
    CASHBACK = "cashback"                    # Cash back to customer
    GIFT_CARD = "gift_card"                  # Gift card value
    TIER_UPGRADE = "tier_upgrade"            # Temporary tier upgrade
    CUSTOM = "custom"                        # Custom reward type


class RewardStatus(str, Enum):
    """Status of reward instances"""
    AVAILABLE = "available"      # Ready to be used
    RESERVED = "reserved"        # Reserved for checkout
    REDEEMED = "redeemed"       # Successfully used
    EXPIRED = "expired"         # Past expiration date
    REVOKED = "revoked"         # Manually revoked by admin
    PENDING = "pending"         # Waiting for approval/processing


class TriggerType(str, Enum):
    """Types of reward triggers"""
    ORDER_COMPLETE = "order_complete"        # After order completion
    POINTS_EARNED = "points_earned"          # When points are earned
    TIER_UPGRADE = "tier_upgrade"            # When tier is upgraded
    BIRTHDAY = "birthday"                    # On customer birthday
    ANNIVERSARY = "anniversary"              # Account anniversary
    REFERRAL_SUCCESS = "referral_success"    # Successful referral
    MILESTONE = "milestone"                  # Achievement milestone
    MANUAL = "manual"                        # Manually awarded
    SCHEDULED = "scheduled"                  # Time-based trigger
    CONDITIONAL = "conditional"              # Complex condition-based


class RewardTemplate(Base, TimestampMixin):
    """Templates for different types of rewards"""
    __tablename__ = "reward_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    
    # Reward Configuration
    reward_type = Column(SQLEnum(RewardType), nullable=False, index=True)
    value = Column(Float, nullable=True)  # Monetary value or points cost
    percentage = Column(Float, nullable=True)  # For percentage discounts
    points_cost = Column(Integer, nullable=True)  # Points required to redeem
    
    # Item-specific rewards
    item_id = Column(Integer, nullable=True)  # Specific menu item
    category_ids = Column(JSONB, nullable=True)  # Applicable categories
    
    # Usage Restrictions
    min_order_amount = Column(Float, nullable=True)
    max_discount_amount = Column(Float, nullable=True)
    max_uses_per_customer = Column(Integer, nullable=True)
    max_uses_total = Column(Integer, nullable=True)
    
    # Validity
    valid_days = Column(Integer, nullable=False, default=30)  # Days valid after creation
    valid_from_date = Column(DateTime, nullable=True)
    valid_until_date = Column(DateTime, nullable=True)
    
    # Tier Restrictions
    eligible_tiers = Column(JSONB, nullable=True)  # List of eligible customer tiers
    
    # Trigger Configuration
    trigger_type = Column(SQLEnum(TriggerType), nullable=False, index=True)
    trigger_conditions = Column(JSONB, nullable=True)  # Complex trigger conditions
    auto_apply = Column(Boolean, default=False)  # Auto-apply at checkout
    
    # Display and Notification
    title = Column(String(200), nullable=False)
    subtitle = Column(String(300), nullable=True)
    terms_and_conditions = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)
    icon = Column(String(50), nullable=True)
    
    # Status and Settings
    is_active = Column(Boolean, default=True, index=True)
    is_featured = Column(Boolean, default=False)
    priority = Column(Integer, default=0)  # Higher priority shows first
    
    # Statistics
    total_issued = Column(Integer, default=0)
    total_redeemed = Column(Integer, default=0)
    
    # Relationships
    reward_instances = relationship("CustomerReward", back_populates="template", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('valid_days > 0', name='valid_days_positive'),
        CheckConstraint('points_cost >= 0 OR points_cost IS NULL', name='points_cost_non_negative'),
        CheckConstraint('value >= 0 OR value IS NULL', name='value_non_negative'),
        CheckConstraint('percentage >= 0 AND percentage <= 100 OR percentage IS NULL', name='percentage_valid_range'),
        Index('ix_reward_templates_type_active', 'reward_type', 'is_active'),
        Index('ix_reward_templates_trigger', 'trigger_type', 'is_active'),
    )
    
    def __repr__(self):
        return f"<RewardTemplate(id={self.id}, name='{self.name}', type='{self.reward_type}')>"


class CustomerReward(Base, TimestampMixin):
    """Individual reward instances for customers"""
    __tablename__ = "customer_rewards_v2"  # v2 to avoid conflict with existing table
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    template_id = Column(Integer, ForeignKey("reward_templates.id"), nullable=False, index=True)
    
    # Reward Details (copied from template for historical consistency)
    reward_type = Column(SQLEnum(RewardType), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    value = Column(Float, nullable=True)
    percentage = Column(Float, nullable=True)
    points_cost = Column(Integer, nullable=True)
    
    # Unique reward code for redemption
    code = Column(String(20), unique=True, nullable=False, index=True)
    
    # Status and Usage
    status = Column(SQLEnum(RewardStatus), nullable=False, default=RewardStatus.AVAILABLE, index=True)
    reserved_at = Column(DateTime, nullable=True)
    reserved_until = Column(DateTime, nullable=True)
    redeemed_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    revoked_reason = Column(String(500), nullable=True)
    
    # Validity
    valid_from = Column(DateTime, nullable=False, default=datetime.utcnow)
    valid_until = Column(DateTime, nullable=False)
    
    # Usage tracking
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)  # Order where redeemed
    redeemed_amount = Column(Float, nullable=True)  # Actual discount applied
    
    # Metadata
    issued_by = Column(Integer, ForeignKey("rbac_users.id"), nullable=True)  # Admin who manually issued
    trigger_data = Column(JSONB, nullable=True)  # Data from trigger event
    
    # Relationships
    customer = relationship("Customer")
    template = relationship("RewardTemplate", back_populates="reward_instances")
    order = relationship("Order")
    issued_by_user = relationship("RBACUser")
    
    # Indexes for performance
    __table_args__ = (
        Index('ix_customer_rewards_v2_customer_status', 'customer_id', 'status'),
        Index('ix_customer_rewards_v2_validity', 'valid_from', 'valid_until'),
        Index('ix_customer_rewards_v2_expiry', 'valid_until', 'status'),
    )
    
    @property
    def is_valid(self) -> bool:
        """Check if reward is currently valid"""
        now = datetime.utcnow()
        return (self.valid_from <= now <= self.valid_until and 
                self.status == RewardStatus.AVAILABLE)
    
    @property
    def is_expired(self) -> bool:
        """Check if reward has expired"""
        return datetime.utcnow() > self.valid_until
    
    @property
    def days_until_expiry(self) -> Optional[int]:
        """Days until reward expires"""
        if self.is_expired:
            return 0
        return (self.valid_until - datetime.utcnow()).days
    
    def __repr__(self):
        return f"<CustomerReward(id={self.id}, customer_id={self.customer_id}, code='{self.code}', status='{self.status}')>"


class RewardCampaign(Base, TimestampMixin):
    """Marketing campaigns for reward distribution"""
    __tablename__ = "reward_campaigns"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    
    # Campaign Configuration
    template_id = Column(Integer, ForeignKey("reward_templates.id"), nullable=False)
    
    # Target Audience
    target_criteria = Column(JSONB, nullable=True)  # Customer targeting criteria
    target_tiers = Column(JSONB, nullable=True)  # Specific customer tiers
    target_segments = Column(JSONB, nullable=True)  # Customer segments
    
    # Campaign Timing
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    
    # Distribution Limits
    max_rewards_total = Column(Integer, nullable=True)
    max_rewards_per_customer = Column(Integer, default=1)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_automated = Column(Boolean, default=False)  # Auto-distribute based on criteria
    
    # Statistics
    rewards_distributed = Column(Integer, default=0)
    target_audience_size = Column(Integer, nullable=True)
    
    # Relationships
    template = relationship("RewardTemplate")
    
    def __repr__(self):
        return f"<RewardCampaign(id={self.id}, name='{self.name}', active={self.is_active})>"


class RewardRedemption(Base, TimestampMixin):
    """Detailed tracking of reward redemptions"""
    __tablename__ = "reward_redemptions"
    
    id = Column(Integer, primary_key=True, index=True)
    reward_id = Column(Integer, ForeignKey("customer_rewards_v2.id"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    
    # Redemption Details
    original_order_amount = Column(Float, nullable=False)
    discount_applied = Column(Float, nullable=False)
    final_order_amount = Column(Float, nullable=False)
    
    # Additional Context
    redemption_method = Column(String(50), nullable=False, default="manual")  # manual, auto, api
    pos_terminal_id = Column(String(50), nullable=True)
    staff_member_id = Column(Integer, ForeignKey("staff_members.id"), nullable=True)
    
    # Metadata
    redemption_data = Column(JSONB, nullable=True)  # Additional redemption context
    
    # Relationships
    reward = relationship("CustomerReward")
    customer = relationship("Customer")
    order = relationship("Order")
    staff_member = relationship("StaffMember")
    
    def __repr__(self):
        return f"<RewardRedemption(id={self.id}, reward_id={self.reward_id}, discount={self.discount_applied})>"


class LoyaltyPointsTransaction(Base, TimestampMixin):
    """Detailed tracking of all loyalty points transactions"""
    __tablename__ = "loyalty_points_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    
    # Transaction Details
    transaction_type = Column(String(50), nullable=False, index=True)  # earned, redeemed, expired, adjusted
    points_change = Column(Integer, nullable=False)  # Positive for earning, negative for spending
    points_balance_before = Column(Integer, nullable=False)
    points_balance_after = Column(Integer, nullable=False)
    
    # Context
    reason = Column(String(200), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    reward_id = Column(Integer, ForeignKey("customer_rewards_v2.id"), nullable=True)
    
    # Metadata
    source = Column(String(50), nullable=False, default="system")  # system, manual, api, import
    reference_id = Column(String(100), nullable=True)  # External reference
    staff_member_id = Column(Integer, ForeignKey("staff_members.id"), nullable=True)
    transaction_data = Column(JSONB, nullable=True)
    
    # Expiration tracking (for earned points)
    expires_at = Column(DateTime, nullable=True)
    is_expired = Column(Boolean, default=False)
    
    # Relationships
    customer = relationship("Customer")
    order = relationship("Order")
    reward = relationship("CustomerReward")
    staff_member = relationship("StaffMember")
    
    # Indexes
    __table_args__ = (
        Index('ix_loyalty_points_transactions_customer_type', 'customer_id', 'transaction_type'),
        Index('ix_loyalty_points_transactions_date', 'created_at'),
        Index('ix_loyalty_points_transactions_expiry', 'expires_at', 'is_expired'),
    )
    
    def __repr__(self):
        return f"<LoyaltyPointsTransaction(id={self.id}, customer_id={self.customer_id}, points={self.points_change})>"


class RewardAnalytics(Base, TimestampMixin):
    """Aggregated analytics for reward performance"""
    __tablename__ = "reward_analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("reward_templates.id"), nullable=False, index=True)
    
    # Time Period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    period_type = Column(String(20), nullable=False, default="daily")  # daily, weekly, monthly
    
    # Metrics
    rewards_issued = Column(Integer, default=0)
    rewards_redeemed = Column(Integer, default=0)
    rewards_expired = Column(Integer, default=0)
    total_discount_value = Column(Float, default=0.0)
    unique_customers = Column(Integer, default=0)
    
    # Performance Metrics
    redemption_rate = Column(Float, default=0.0)  # Percentage of issued rewards redeemed
    avg_redemption_days = Column(Float, default=0.0)  # Average days to redeem
    customer_satisfaction_score = Column(Float, nullable=True)
    
    # Revenue Impact
    revenue_impact = Column(Float, default=0.0)  # Net revenue impact
    customer_retention_impact = Column(Float, nullable=True)
    
    # Relationships
    template = relationship("RewardTemplate")
    
    # Unique constraint for period
    __table_args__ = (
        Index('ix_reward_analytics_template_period', 'template_id', 'period_start', 'period_end', unique=True),
    )
    
    def __repr__(self):
        return f"<RewardAnalytics(template_id={self.template_id}, period={self.period_start}-{self.period_end})>"