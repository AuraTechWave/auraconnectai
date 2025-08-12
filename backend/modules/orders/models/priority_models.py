"""
Priority models for intelligent order queue management and prioritization.
"""

from sqlalchemy import (
    Column, Integer, String, ForeignKey, DateTime, 
    Numeric, Text, Boolean, Enum, JSON, Float, Index, UniqueConstraint,
    CheckConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from core.database import Base
from core.mixins import TimestampMixin
from datetime import datetime
import enum


class PriorityAlgorithm(enum.Enum):
    """Types of priority algorithms"""
    FIFO = "fifo"                    # First In First Out
    WEIGHTED = "weighted"            # Multi-factor weighted scoring
    DYNAMIC = "dynamic"              # Adaptive based on conditions
    CUSTOM = "custom"                # Custom algorithm
    FAIR_SHARE = "fair_share"        # Ensures fairness across customers
    REVENUE_OPTIMIZED = "revenue_optimized"  # Maximizes revenue


class PriorityScoreType(enum.Enum):
    """Types of priority scoring factors"""
    WAIT_TIME = "wait_time"
    ORDER_VALUE = "order_value"
    VIP_STATUS = "vip_status"
    DELIVERY_TIME = "delivery_time"
    PREP_COMPLEXITY = "prep_complexity"
    CUSTOMER_LOYALTY = "customer_loyalty"
    PEAK_HOURS = "peak_hours"
    GROUP_SIZE = "group_size"
    SPECIAL_NEEDS = "special_needs"
    CUSTOM = "custom"


class PriorityRule(Base, TimestampMixin):
    """Individual priority calculation rules"""
    __tablename__ = "priority_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    
    # Rule configuration
    score_type = Column(
        Enum(PriorityScoreType, values_callable=lambda obj: [e.value for e in obj],
             create_type=False),
        nullable=False,
        index=True
    )
    is_active = Column(Boolean, default=True)
    
    # Score calculation - stored as structured JSON, not executable code
    score_config = Column(JSONB, nullable=False)
    # Example config:
    # {
    #   "type": "linear",
    #   "base_score": 10,
    #   "multiplier": 1.5,
    #   "threshold": {"min": 0, "max": 100},
    #   "conditions": [
    #     {"field": "wait_time", "operator": "gt", "value": 10, "adjustment": 5}
    #   ]
    # }
    
    # Value ranges
    min_score = Column(Float, default=0.0)
    max_score = Column(Float, default=100.0)
    default_weight = Column(Float, default=1.0)
    
    # Normalization
    normalize_output = Column(Boolean, default=True)
    normalization_method = Column(String(50), default="min_max")
    
    # Relationships
    profile_rules = relationship("PriorityProfileRule", back_populates="rule")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('min_score <= max_score', name='check_score_range'),
        CheckConstraint('default_weight >= 0', name='check_positive_weight'),
    )


class PriorityProfile(Base, TimestampMixin):
    """Collection of priority rules forming a strategy"""
    __tablename__ = "priority_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    
    # Profile configuration
    algorithm_type = Column(
        Enum(PriorityAlgorithm, values_callable=lambda obj: [e.value for e in obj],
             create_type=False),
        nullable=False,
        default=PriorityAlgorithm.WEIGHTED
    )
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    
    # Score aggregation
    aggregation_method = Column(String(50), default="weighted_sum")  # weighted_sum, max, min, average
    total_weight_normalization = Column(Boolean, default=True)
    
    # Boundaries
    min_total_score = Column(Float, default=0.0)
    max_total_score = Column(Float, default=100.0)
    
    # Performance settings
    cache_duration_seconds = Column(Integer, default=60)
    recalculation_threshold = Column(Float, default=0.1)  # Minimum change to trigger recalc
    
    # Relationships
    profile_rules = relationship("PriorityProfileRule", back_populates="profile", 
                               cascade="all, delete-orphan")
    queue_configs = relationship("QueuePriorityConfig", back_populates="profile")
    
    # Indexes
    __table_args__ = (
        Index('idx_profile_active_default', 'is_active', 'is_default'),
    )


class PriorityProfileRule(Base):
    """Junction table linking profiles to rules with weights"""
    __tablename__ = "priority_profile_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("priority_profiles.id"), nullable=False)
    rule_id = Column(Integer, ForeignKey("priority_rules.id"), nullable=False)
    
    # Rule configuration within profile
    weight = Column(Float, nullable=False, default=1.0)
    is_active = Column(Boolean, default=True)
    
    # Override rule settings
    override_config = Column(JSONB)  # Override rule's score_config
    boost_conditions = Column(JSONB)  # Additional conditions for boosting
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    profile = relationship("PriorityProfile", back_populates="profile_rules")
    rule = relationship("PriorityRule", back_populates="profile_rules")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('profile_id', 'rule_id', name='uq_profile_rule'),
        CheckConstraint('weight >= 0', name='check_positive_rule_weight'),
    )


class QueuePriorityConfig(Base, TimestampMixin):
    """Priority configuration for specific queues"""
    __tablename__ = "queue_priority_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    queue_id = Column(Integer, ForeignKey("order_queues.id"), nullable=False, unique=True)
    profile_id = Column(Integer, ForeignKey("priority_profiles.id"), nullable=False)
    
    # Queue-specific settings
    is_active = Column(Boolean, default=True)
    priority_enabled = Column(Boolean, default=True)
    
    # Rebalancing settings
    auto_rebalance = Column(Boolean, default=True)
    rebalance_interval_minutes = Column(Integer, default=5)
    rebalance_threshold = Column(Float, default=0.2)  # Trigger if fairness < threshold
    last_rebalance_time = Column(DateTime(timezone=True))
    
    # Position constraints
    max_position_change = Column(Integer, default=5)  # Max positions an item can jump
    boost_new_items = Column(Boolean, default=True)
    boost_duration_seconds = Column(Integer, default=30)
    
    # Override settings
    queue_overrides = Column(JSONB)  # Queue-specific rule overrides
    peak_hours_config = Column(JSONB)  # Time-based adjustments
    
    # Relationships
    queue = relationship("OrderQueue")
    profile = relationship("PriorityProfile", back_populates="queue_configs")
    priority_scores = relationship("OrderPriorityScore", back_populates="config")
    
    # Indexes
    __table_args__ = (
        Index('idx_queue_priority_active', 'queue_id', 'is_active'),
    )


class OrderPriorityScore(Base):
    """Calculated priority scores for orders in queues"""
    __tablename__ = "order_priority_scores"
    
    id = Column(Integer, primary_key=True, index=True)
    queue_item_id = Column(Integer, ForeignKey("queue_items.id"), nullable=False, unique=True)
    config_id = Column(Integer, ForeignKey("queue_priority_configs.id"), nullable=False)
    
    # Scores
    total_score = Column(Float, nullable=False, index=True)
    base_score = Column(Float, nullable=False)
    boost_score = Column(Float, default=0.0)
    
    # Score components (stored as JSONB for querying)
    score_components = Column(JSONB, nullable=False)
    # Example:
    # {
    #   "wait_time": {"value": 15, "score": 25.5, "weight": 2.0},
    #   "order_value": {"value": 150.00, "score": 30.0, "weight": 1.5},
    #   "vip_status": {"value": true, "score": 20.0, "weight": 1.0}
    # }
    
    # Calculation metadata
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())
    algorithm_version = Column(String(20))
    calculation_time_ms = Column(Integer)
    
    # Boost information
    is_boosted = Column(Boolean, default=False)
    boost_expires_at = Column(DateTime(timezone=True))
    boost_reason = Column(String(100))
    
    # Relationships
    queue_item = relationship("QueueItem")
    config = relationship("QueuePriorityConfig", back_populates="priority_scores")
    
    # Indexes
    __table_args__ = (
        Index('idx_priority_score_queue', 'config_id', 'total_score'),
        Index('idx_priority_score_boost', 'is_boosted', 'boost_expires_at'),
    )


class PriorityAdjustmentLog(Base):
    """Log manual priority adjustments"""
    __tablename__ = "priority_adjustment_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    queue_item_id = Column(Integer, ForeignKey("queue_items.id"), nullable=False, index=True)
    
    # Adjustment details
    old_score = Column(Float, nullable=False)
    new_score = Column(Float, nullable=False)
    adjustment_type = Column(String(50), nullable=False)  # manual, boost, penalty
    adjustment_reason = Column(String(200))
    
    # Position change
    old_position = Column(Integer)
    new_position = Column(Integer)
    
    # Who made the change
    adjusted_by_id = Column(Integer, ForeignKey("staff_members.id"))
    adjusted_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    queue_item = relationship("QueueItem")
    adjusted_by = relationship("StaffMember")


class PriorityMetrics(Base):
    """Track priority system performance metrics"""
    __tablename__ = "priority_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    queue_id = Column(Integer, ForeignKey("order_queues.id"), nullable=False, index=True)
    
    # Time period
    metric_date = Column(DateTime(timezone=True), nullable=False)
    hour_of_day = Column(Integer)  # 0-23
    
    # Fairness metrics
    gini_coefficient = Column(Float)  # 0-1, lower is more fair
    max_wait_variance = Column(Float)  # Variance in wait times
    position_change_avg = Column(Float)  # Average position changes
    
    # Performance metrics
    avg_calculation_time_ms = Column(Float)
    total_calculations = Column(Integer, default=0)
    cache_hit_rate = Column(Float)
    
    # Rebalancing metrics
    rebalance_count = Column(Integer, default=0)
    avg_rebalance_impact = Column(Float)  # Avg positions changed
    manual_adjustments = Column(Integer, default=0)
    
    # Algorithm effectiveness
    revenue_impact = Column(Numeric(10, 2))  # Compared to baseline
    customer_satisfaction_score = Column(Float)  # If available
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    queue = relationship("OrderQueue")
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint('queue_id', 'metric_date', 'hour_of_day', 
                        name='uq_priority_metrics_period'),
        Index('idx_priority_metrics_date', 'queue_id', 'metric_date'),
    )