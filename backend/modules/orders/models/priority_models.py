"""
Order prioritization models for intelligent queue management.
"""

from sqlalchemy import (
    Column, Integer, String, ForeignKey, DateTime, 
    Numeric, Text, Boolean, Enum, JSON, Float, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
from core.mixins import TimestampMixin
from datetime import datetime
import enum


class PriorityAlgorithmType(enum.Enum):
    """Types of priority algorithms"""
    PREPARATION_TIME = "preparation_time"      # Based on estimated prep time
    DELIVERY_WINDOW = "delivery_window"        # Based on promised delivery time
    VIP_STATUS = "vip_status"                 # Based on customer VIP level
    ORDER_VALUE = "order_value"               # Based on order total
    WAIT_TIME = "wait_time"                   # Based on how long customer waited
    ITEM_COMPLEXITY = "item_complexity"       # Based on order complexity
    COMPOSITE = "composite"                   # Weighted combination
    CUSTOM = "custom"                        # Custom algorithm


class PriorityScoreType(enum.Enum):
    """How priority scores are calculated"""
    LINEAR = "linear"          # Linear scaling
    EXPONENTIAL = "exponential"  # Exponential scaling
    LOGARITHMIC = "logarithmic"  # Logarithmic scaling
    STEP = "step"             # Step function
    CUSTOM = "custom"         # Custom function


class PriorityRule(Base, TimestampMixin):
    """Individual priority calculation rules"""
    __tablename__ = "priority_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    algorithm_type = Column(
        Enum(PriorityAlgorithmType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True
    )
    
    # Rule configuration
    is_active = Column(Boolean, default=True, index=True)
    weight = Column(Float, default=1.0)  # Weight in composite scoring
    min_score = Column(Float, default=0.0)
    max_score = Column(Float, default=100.0)
    
    # Algorithm parameters (JSON for flexibility)
    parameters = Column(JSON, nullable=False, default=dict)
    # Examples:
    # preparation_time: {"base_minutes": 15, "penalty_per_minute": 2}
    # delivery_window: {"grace_minutes": 10, "critical_minutes": 30}
    # vip_status: {"bronze": 10, "silver": 20, "gold": 30, "platinum": 50, "vip": 100}
    
    # Scoring function
    score_type = Column(
        Enum(PriorityScoreType, values_callable=lambda obj: [e.value for e in obj]),
        default=PriorityScoreType.LINEAR
    )
    score_function = Column(Text)  # Custom scoring function (if needed)
    
    # Conditions (when to apply this rule)
    conditions = Column(JSON, default=dict)
    # Example: {"order_type": ["delivery", "takeout"], "min_order_value": 50}
    
    # Relationships
    priority_profiles = relationship("PriorityProfileRule", back_populates="rule")
    
    # Indexes
    __table_args__ = (
        Index('idx_priority_rule_active', 'is_active'),
        Index('idx_priority_rule_type', 'algorithm_type', 'is_active'),
    )


class PriorityProfile(Base, TimestampMixin):
    """Collection of priority rules for different scenarios"""
    __tablename__ = "priority_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    is_active = Column(Boolean, default=True, index=True)
    is_default = Column(Boolean, default=False)  # Default profile to use
    
    # Profile application
    queue_types = Column(JSON, default=list)  # Which queue types to apply to
    order_types = Column(JSON, default=list)  # Which order types to apply to
    time_ranges = Column(JSON, default=list)  # Time-based activation
    
    # Score normalization
    normalize_scores = Column(Boolean, default=True)
    normalization_method = Column(String(50), default="min_max")
    
    # Relationships
    profile_rules = relationship("PriorityProfileRule", back_populates="profile", cascade="all, delete-orphan")
    queue_configurations = relationship("QueuePriorityConfig", back_populates="priority_profile")
    
    # Indexes
    __table_args__ = (
        Index('idx_priority_profile_active', 'is_active'),
        Index('idx_priority_profile_default', 'is_default', 'is_active'),
    )


class PriorityProfileRule(Base):
    """Association between profiles and rules with specific weights"""
    __tablename__ = "priority_profile_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("priority_profiles.id"), nullable=False, index=True)
    rule_id = Column(Integer, ForeignKey("priority_rules.id"), nullable=False, index=True)
    
    # Override rule settings
    weight_override = Column(Float)  # Override rule's default weight
    is_required = Column(Boolean, default=False)  # Must have data for this rule
    fallback_score = Column(Float, default=0.0)  # Score if data unavailable
    
    # Thresholds
    min_threshold = Column(Float)  # Don't apply if score below this
    max_threshold = Column(Float)  # Cap score at this value
    
    # Relationships
    profile = relationship("PriorityProfile", back_populates="profile_rules")
    rule = relationship("PriorityRule", back_populates="priority_profiles")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('profile_id', 'rule_id', name='uq_profile_rule'),
    )


class QueuePriorityConfig(Base, TimestampMixin):
    """Priority configuration for specific queues"""
    __tablename__ = "queue_priority_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    queue_id = Column(Integer, ForeignKey("order_queues.id"), nullable=False, unique=True)
    priority_profile_id = Column(Integer, ForeignKey("priority_profiles.id"), nullable=False)
    
    # Queue-specific overrides
    priority_boost_vip = Column(Float, default=20.0)  # Extra points for VIP
    priority_boost_delayed = Column(Float, default=15.0)  # Extra points if delayed
    priority_boost_large_party = Column(Float, default=10.0)  # For large groups
    
    # Rebalancing settings
    rebalance_enabled = Column(Boolean, default=True)
    rebalance_interval = Column(Integer, default=300)  # Seconds between rebalancing
    max_position_change = Column(Integer, default=5)  # Max positions to move in one rebalance
    
    # Time-based adjustments
    peak_hours = Column(JSON, default=list)  # Peak hour definitions
    peak_multiplier = Column(Float, default=1.5)  # Priority multiplier during peak
    
    # Relationships
    queue = relationship("OrderQueue")
    priority_profile = relationship("PriorityProfile", back_populates="queue_configurations")
    
    # Indexes
    __table_args__ = (
        Index('idx_queue_priority_config', 'queue_id'),
    )


class OrderPriorityScore(Base):
    """Calculated priority scores for orders"""
    __tablename__ = "order_priority_scores"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    queue_id = Column(Integer, ForeignKey("order_queues.id"), nullable=False, index=True)
    
    # Overall score
    total_score = Column(Float, nullable=False, index=True)
    normalized_score = Column(Float)  # 0-100 normalized
    
    # Component scores
    score_components = Column(JSON, nullable=False)
    # Example: {
    #   "preparation_time": 25.5,
    #   "delivery_window": 30.0,
    #   "vip_status": 20.0,
    #   "wait_time": 15.5
    # }
    
    # Calculation metadata
    profile_used = Column(String(100))  # Which profile was used
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())
    factors_applied = Column(JSON)  # What factors were considered
    
    # Priority decision
    priority_tier = Column(String(20))  # high, medium, low
    suggested_sequence = Column(Integer)  # Suggested queue position
    
    # Relationships
    order = relationship("Order")
    queue = relationship("OrderQueue")
    
    # Indexes
    __table_args__ = (
        UniqueConstraint('order_id', 'queue_id', name='uq_order_queue_score'),
        Index('idx_priority_score_order', 'order_id'),
        Index('idx_priority_score_queue', 'queue_id', 'total_score'),
    )


class PriorityAdjustmentLog(Base):
    """Log of manual priority adjustments"""
    __tablename__ = "priority_adjustment_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    queue_item_id = Column(Integer, ForeignKey("queue_items.id"), nullable=False)
    
    # Adjustment details
    old_priority = Column(Float, nullable=False)
    new_priority = Column(Float, nullable=False)
    old_sequence = Column(Integer)
    new_sequence = Column(Integer)
    
    # Reason and authorization
    adjustment_reason = Column(String(200), nullable=False)
    adjusted_by_id = Column(Integer, ForeignKey("staff_members.id"), nullable=False)
    adjusted_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Impact
    affected_orders = Column(JSON)  # Orders that were resequenced
    
    # Relationships
    order = relationship("Order")
    queue_item = relationship("QueueItem")
    adjusted_by = relationship("StaffMember")
    
    # Indexes
    __table_args__ = (
        Index('idx_priority_adjustment_order', 'order_id'),
        Index('idx_priority_adjustment_time', 'adjusted_at'),
    )


class PriorityMetrics(Base):
    """Metrics for priority algorithm performance"""
    __tablename__ = "priority_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("priority_profiles.id"), nullable=False, index=True)
    queue_id = Column(Integer, ForeignKey("order_queues.id"), nullable=False, index=True)
    
    # Time period
    metric_date = Column(DateTime(timezone=True), nullable=False)
    hour_of_day = Column(Integer)  # 0-23
    
    # Effectiveness metrics
    avg_wait_time_reduction = Column(Float)  # % reduction vs FIFO
    on_time_delivery_rate = Column(Float)  # % delivered on time
    vip_satisfaction_score = Column(Float)  # VIP order performance
    
    # Fairness metrics
    fairness_index = Column(Float)  # Gini coefficient for wait times
    max_wait_time_ratio = Column(Float)  # Max wait vs average
    priority_override_count = Column(Integer, default=0)
    
    # Algorithm performance
    avg_calculation_time_ms = Column(Float)  # Time to calculate priority
    rebalance_count = Column(Integer, default=0)
    avg_position_changes = Column(Float)  # Avg positions moved per rebalance
    
    # Business impact
    revenue_impact = Column(Float)  # Estimated revenue impact
    customer_complaints = Column(Integer, default=0)
    staff_overrides = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    profile = relationship("PriorityProfile")
    queue = relationship("OrderQueue")
    
    # Indexes
    __table_args__ = (
        UniqueConstraint('profile_id', 'queue_id', 'metric_date', 'hour_of_day', name='uq_priority_metrics_period'),
        Index('idx_priority_metrics_date', 'metric_date'),
        Index('idx_priority_metrics_profile', 'profile_id', 'metric_date'),
    )