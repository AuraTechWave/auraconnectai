# backend/modules/orders/models/pricing_rule_models.py

from sqlalchemy import (
    Column, Integer, String, ForeignKey, DateTime, Numeric, Text, 
    Boolean, Index, Enum as SQLEnum, UniqueConstraint, CheckConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from core.database import Base
from core.mixins import TimestampMixin
from datetime import datetime
from enum import Enum
import uuid


class RuleType(str, Enum):
    """Types of pricing rules"""
    PERCENTAGE_DISCOUNT = "percentage_discount"
    FIXED_DISCOUNT = "fixed_discount"
    BUNDLE_DISCOUNT = "bundle_discount"
    BOGO = "bogo"  # Buy One Get One
    HAPPY_HOUR = "happy_hour"
    LOYALTY_DISCOUNT = "loyalty_discount"
    QUANTITY_DISCOUNT = "quantity_discount"
    CATEGORY_DISCOUNT = "category_discount"
    TIME_BASED = "time_based"
    CUSTOM = "custom"


class RuleStatus(str, Enum):
    """Status of pricing rules"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SCHEDULED = "scheduled"
    EXPIRED = "expired"
    TESTING = "testing"


class RulePriority(int, Enum):
    """Priority levels for rule application"""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    DEFAULT = 5


class ConflictResolution(str, Enum):
    """How to handle conflicting rules"""
    HIGHEST_DISCOUNT = "highest_discount"
    FIRST_MATCH = "first_match"
    COMBINE_ADDITIVE = "combine_additive"
    COMBINE_MULTIPLICATIVE = "combine_multiplicative"
    PRIORITY_BASED = "priority_based"


class PricingRule(Base, TimestampMixin):
    """Configurable pricing rules with conditions"""
    __tablename__ = "pricing_rules"
    
    id = Column(Integer, primary_key=True)
    rule_id = Column(String(50), unique=True, nullable=False, index=True)
    
    # Basic info
    name = Column(String(100), nullable=False)
    description = Column(Text)
    rule_type = Column(SQLEnum(RuleType), nullable=False, index=True)
    status = Column(SQLEnum(RuleStatus), nullable=False, default=RuleStatus.ACTIVE, index=True)
    priority = Column(Integer, nullable=False, default=RulePriority.DEFAULT.value)
    
    # Restaurant association
    restaurant_id = Column(Integer, ForeignKey('restaurants.id'), nullable=False)
    
    # Rule configuration
    discount_value = Column(Numeric(10, 2))  # Percentage or fixed amount
    max_discount_amount = Column(Numeric(10, 2))  # Cap for percentage discounts
    min_order_amount = Column(Numeric(10, 2))  # Minimum order value
    
    # Conditions (JSON for flexibility)
    conditions = Column(JSONB, nullable=False, default={})
    """
    Example conditions:
    {
        "time": {
            "days_of_week": [1, 2, 3, 4, 5],  # Mon-Fri
            "start_time": "14:00",
            "end_time": "17:00"
        },
        "items": {
            "menu_item_ids": [1, 2, 3],
            "category_ids": [10, 11],
            "exclude_item_ids": [4, 5]
        },
        "customer": {
            "loyalty_tier": ["gold", "platinum"],
            "min_orders": 5,
            "tags": ["vip", "frequent"]
        },
        "order": {
            "min_items": 2,
            "payment_methods": ["credit_card", "cash"],
            "order_types": ["dine_in", "takeout"]
        }
    }
    """
    
    # Validity period
    valid_from = Column(DateTime, nullable=False, default=datetime.utcnow)
    valid_until = Column(DateTime)
    
    # Usage limits
    max_uses_total = Column(Integer)  # Total uses across all customers
    max_uses_per_customer = Column(Integer)
    current_uses = Column(Integer, default=0)
    
    # Stacking rules
    stackable = Column(Boolean, default=False)
    excluded_rule_ids = Column(JSONB, default=[])  # Rules that can't be combined with this
    conflict_resolution = Column(SQLEnum(ConflictResolution), default=ConflictResolution.HIGHEST_DISCOUNT)
    
    # Tracking
    requires_code = Column(Boolean, default=False)
    promo_code = Column(String(50), index=True)
    
    # Metadata
    tags = Column(JSONB, default=[])
    rule_metadata = Column(JSONB, default={})
    
    # Relationships
    restaurant = relationship("Restaurant", back_populates="pricing_rules")
    applications = relationship("PricingRuleApplication", back_populates="rule")
    
    # Indexes
    __table_args__ = (
        Index('idx_rule_restaurant_status', 'restaurant_id', 'status'),
        Index('idx_rule_validity', 'valid_from', 'valid_until'),
        Index('idx_rule_type_status', 'rule_type', 'status'),
        CheckConstraint('priority >= 1 AND priority <= 5', name='check_priority_range'),
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.rule_id:
            self.rule_id = f"RULE_{uuid.uuid4().hex[:8].upper()}"
    
    def is_valid(self, check_time: datetime = None) -> bool:
        """Check if rule is currently valid"""
        if self.status != RuleStatus.ACTIVE:
            return False
        
        check_time = check_time or datetime.utcnow()
        
        if check_time < self.valid_from:
            return False
        
        if self.valid_until and check_time > self.valid_until:
            return False
        
        if self.max_uses_total and self.current_uses >= self.max_uses_total:
            return False
        
        return True


class PricingRuleApplication(Base, TimestampMixin):
    """Track applications of pricing rules to orders"""
    __tablename__ = "pricing_rule_applications"
    
    id = Column(Integer, primary_key=True)
    
    # References
    rule_id = Column(Integer, ForeignKey('pricing_rules.id'), nullable=False)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    order_item_id = Column(Integer, ForeignKey('order_items.id'))  # If item-specific
    customer_id = Column(Integer, ForeignKey('customers.id'))
    
    # Application details
    discount_amount = Column(Numeric(10, 2), nullable=False)
    original_amount = Column(Numeric(10, 2), nullable=False)
    final_amount = Column(Numeric(10, 2), nullable=False)
    
    # Tracking
    applied_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    applied_by = Column(String(50))  # 'system', 'manual', 'api'
    
    # Debug info
    conditions_met = Column(JSONB, default={})  # Which conditions were satisfied
    application_metadata = Column(JSONB, default={})
    
    # Relationships
    rule = relationship("PricingRule", back_populates="applications")
    order = relationship("Order", back_populates="pricing_applications")
    
    # Indexes
    __table_args__ = (
        Index('idx_application_order', 'order_id'),
        Index('idx_application_rule', 'rule_id'),
        Index('idx_application_customer', 'customer_id'),
    )


class PricingRuleMetrics(Base):
    """Metrics for pricing rule performance"""
    __tablename__ = "pricing_rule_metrics"
    
    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('pricing_rules.id'), nullable=False)
    
    # Aggregated metrics (updated periodically)
    date = Column(DateTime, nullable=False)
    applications_count = Column(Integer, default=0)
    total_discount_amount = Column(Numeric(12, 2), default=0)
    unique_customers = Column(Integer, default=0)
    conversion_rate = Column(Numeric(5, 2))  # Percentage
    average_order_value = Column(Numeric(10, 2))
    
    # Performance metrics
    conflicts_skipped = Column(Integer, default=0)
    stacking_count = Column(Integer, default=0)
    
    # Metadata
    metrics_metadata = Column(JSONB, default={})
    
    # Indexes
    __table_args__ = (
        Index('idx_metrics_rule_date', 'rule_id', 'date'),
        UniqueConstraint('rule_id', 'date', name='uq_rule_metrics_date'),
    )