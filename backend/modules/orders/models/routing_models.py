"""
Order routing models for advanced rule-based routing configuration.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Boolean,
    Enum,
    Text,
    JSON,
    Float,
    Index,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from core.database import Base
from core.mixins import TimestampMixin
import enum
from typing import Optional
from datetime import datetime


class RouteTargetType(enum.Enum):
    """Types of routing targets"""

    STATION = "station"  # Route to kitchen station
    STAFF = "staff"  # Route to specific staff member
    TEAM = "team"  # Route to a team/group
    QUEUE = "queue"  # Route to a queue/pool


class RuleConditionOperator(enum.Enum):
    """Operators for rule conditions"""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    IN = "in"
    NOT_IN = "not_in"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    BETWEEN = "between"
    REGEX = "regex"


class RuleStatus(enum.Enum):
    """Status of routing rules"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    TESTING = "testing"  # Test mode - logs but doesn't route
    SCHEDULED = "scheduled"  # Will activate at specific time


class OrderRoutingRule(Base, TimestampMixin):
    """Configurable rules for routing orders"""

    __tablename__ = "order_routing_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, unique=True)
    description = Column(Text, nullable=True)

    # Rule configuration
    priority = Column(
        Integer, nullable=False, default=0, index=True
    )  # Higher priority evaluated first
    status = Column(
        Enum(RuleStatus), nullable=False, default=RuleStatus.ACTIVE, index=True
    )

    # Target configuration
    target_type = Column(Enum(RouteTargetType), nullable=False)
    target_id = Column(Integer, nullable=True)  # ID of station/staff/team
    target_config = Column(JSONB, nullable=True)  # Additional target configuration

    # Rule timing
    active_from = Column(DateTime, nullable=True)
    active_until = Column(DateTime, nullable=True)

    # Rule scheduling (days/times when active)
    schedule_config = Column(
        JSONB, nullable=True
    )  # {"days": ["monday", "tuesday"], "hours": {"start": "09:00", "end": "17:00"}}

    # Performance tracking
    evaluation_count = Column(Integer, default=0)
    match_count = Column(Integer, default=0)
    last_matched_at = Column(DateTime, nullable=True)

    # Rule metadata
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    conditions = relationship(
        "RoutingRuleCondition", back_populates="rule", cascade="all, delete-orphan"
    )
    actions = relationship(
        "RoutingRuleAction", back_populates="rule", cascade="all, delete-orphan"
    )
    logs = relationship("RoutingRuleLog", back_populates="rule")

    __table_args__ = (
        Index("idx_routing_rule_priority_status", "priority", "status"),
        CheckConstraint(
            "priority >= 0 AND priority <= 1000", name="check_priority_range"
        ),
    )


class RoutingRuleCondition(Base, TimestampMixin):
    """Conditions that must be met for a routing rule to apply"""

    __tablename__ = "routing_rule_conditions"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(
        Integer,
        ForeignKey("order_routing_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Condition configuration
    field_path = Column(
        String(200), nullable=False
    )  # e.g., "order.type", "item.category", "customer.vip_status"
    operator = Column(Enum(RuleConditionOperator), nullable=False)
    value = Column(JSONB, nullable=False)  # Flexible value storage

    # Logical grouping
    condition_group = Column(Integer, default=0)  # For AND/OR grouping
    is_negated = Column(Boolean, default=False)  # NOT condition

    # Relationships
    rule = relationship("OrderRoutingRule", back_populates="conditions")

    __table_args__ = (
        Index("idx_rule_condition_rule_group", "rule_id", "condition_group"),
    )


class RoutingRuleAction(Base, TimestampMixin):
    """Actions to take when a routing rule matches"""

    __tablename__ = "routing_rule_actions"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(
        Integer,
        ForeignKey("order_routing_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Action configuration
    action_type = Column(
        String(50), nullable=False
    )  # "route", "notify", "tag", "priority", "split"
    action_config = Column(JSONB, nullable=False)  # Action-specific configuration
    execution_order = Column(
        Integer, default=0
    )  # Order of execution for multiple actions

    # Conditional execution
    condition_expression = Column(
        Text, nullable=True
    )  # Optional additional condition for this action

    # Relationships
    rule = relationship("OrderRoutingRule", back_populates="actions")


class RoutingRuleLog(Base, TimestampMixin):
    """Audit log for routing rule evaluations"""

    __tablename__ = "routing_rule_logs"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(
        Integer, ForeignKey("order_routing_rules.id"), nullable=False, index=True
    )
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)

    # Evaluation details
    matched = Column(Boolean, nullable=False)
    evaluation_time_ms = Column(Float, nullable=True)  # Time taken to evaluate

    # Context at evaluation
    order_context = Column(JSONB, nullable=True)  # Snapshot of order data
    conditions_evaluated = Column(
        JSONB, nullable=True
    )  # Which conditions passed/failed

    # Actions taken
    actions_executed = Column(JSONB, nullable=True)  # What actions were performed
    routing_result = Column(JSONB, nullable=True)  # Where the order was routed

    # Error tracking
    error_occurred = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)

    # Relationships
    rule = relationship("OrderRoutingRule", back_populates="logs")

    __table_args__ = (
        Index("idx_routing_log_rule_order", "rule_id", "order_id"),
        Index("idx_routing_log_created", "created_at"),
    )


class RouteOverride(Base, TimestampMixin):
    """Manual overrides for routing decisions"""

    __tablename__ = "route_overrides"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, unique=True)

    # Override configuration
    override_type = Column(
        String(50), nullable=False
    )  # "manual", "system", "emergency"
    target_type = Column(Enum(RouteTargetType), nullable=False)
    target_id = Column(Integer, nullable=False)

    # Override metadata
    reason = Column(Text, nullable=True)
    overridden_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=True)

    # Original routing info
    original_route = Column(JSONB, nullable=True)  # What the system would have done

    __table_args__ = (
        Index("idx_route_override_order", "order_id"),
        Index("idx_route_override_expires", "expires_at"),
    )


class StaffRoutingCapability(Base, TimestampMixin):
    """Defines what types of orders staff members can handle"""

    __tablename__ = "staff_routing_capabilities"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(
        Integer, ForeignKey("staff_members.id"), nullable=False, index=True
    )

    # Capability definition
    capability_type = Column(
        String(50), nullable=False
    )  # "category", "station", "skill", "certification"
    capability_value = Column(
        String(100), nullable=False
    )  # "grill", "sushi_chef", "alcohol_service"

    # Capacity and availability
    max_concurrent_orders = Column(Integer, default=5)
    is_available = Column(Boolean, default=True)

    # Skill level/preference
    skill_level = Column(Integer, default=3)  # 1-5 scale
    preference_weight = Column(Float, default=1.0)  # For load balancing

    # Time restrictions
    available_schedule = Column(
        JSONB, nullable=True
    )  # Schedule when this capability is active

    __table_args__ = (
        UniqueConstraint(
            "staff_id",
            "capability_type",
            "capability_value",
            name="uq_staff_capability",
        ),
        Index("idx_staff_capability_type_value", "capability_type", "capability_value"),
    )


class TeamRoutingConfig(Base, TimestampMixin):
    """Configuration for team-based routing"""

    __tablename__ = "team_routing_configs"

    id = Column(Integer, primary_key=True, index=True)
    team_name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)

    # Team configuration
    is_active = Column(Boolean, default=True)
    routing_strategy = Column(
        String(50), nullable=False, default="round_robin"
    )  # "round_robin", "least_loaded", "skill_based"

    # Team capacity
    max_concurrent_orders = Column(Integer, nullable=True)
    current_load = Column(Integer, default=0)

    # Team specialization
    specializations = Column(
        JSONB, nullable=True
    )  # ["lunch_rush", "catering", "delivery"]

    # Load balancing configuration
    load_balancing_config = Column(JSONB, nullable=True)

    # Team schedule
    schedule_config = Column(JSONB, nullable=True)

    __table_args__ = (Index("idx_team_routing_active", "is_active"),)


class TeamMember(Base, TimestampMixin):
    """Members of routing teams"""

    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(
        Integer,
        ForeignKey("team_routing_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    staff_id = Column(
        Integer, ForeignKey("staff_members.id"), nullable=False, index=True
    )

    # Member configuration
    is_active = Column(Boolean, default=True)
    role_in_team = Column(String(50), nullable=True)  # "lead", "member", "backup"

    # Load balancing
    weight = Column(Float, default=1.0)  # For weighted distribution
    current_load = Column(Integer, default=0)

    # Availability
    available_from = Column(DateTime, nullable=True)
    available_until = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "staff_id", name="uq_team_member"),
        Index("idx_team_member_staff", "staff_id"),
    )
