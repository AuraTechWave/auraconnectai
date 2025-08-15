"""
Schemas for order routing rules and configurations.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from decimal import Decimal
from enum import Enum


class RouteTargetType(str, Enum):
    """Types of routing targets"""

    STATION = "station"
    STAFF = "staff"
    TEAM = "team"
    QUEUE = "queue"


class RuleConditionOperator(str, Enum):
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


class RuleStatus(str, Enum):
    """Status of routing rules"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    TESTING = "testing"
    SCHEDULED = "scheduled"


class RoutingStrategy(str, Enum):
    """Load balancing strategies"""

    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    SKILL_BASED = "skill_based"
    PRIORITY_BASED = "priority_based"
    RANDOM = "random"


# Condition Schemas
class RuleConditionBase(BaseModel):
    """Base schema for rule conditions"""

    field_path: str = Field(
        ...,
        description="Path to the field to evaluate (e.g., 'order.type', 'item.category')",
    )
    operator: RuleConditionOperator
    value: Any = Field(..., description="Value to compare against")
    condition_group: int = Field(0, description="Group number for AND/OR logic")
    is_negated: bool = Field(False, description="Negate the condition")

    @validator("field_path")
    def validate_field_path(cls, v):
        """Validate field path format"""
        if not v or not all(part.strip() for part in v.split(".")):
            raise ValueError("Invalid field path format")
        return v


class RuleConditionCreate(RuleConditionBase):
    """Schema for creating a rule condition"""

    pass


class RuleConditionResponse(RuleConditionBase):
    """Schema for rule condition response"""

    id: int
    rule_id: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# Action Schemas
class RuleActionBase(BaseModel):
    """Base schema for rule actions"""

    action_type: str = Field(
        ..., description="Type of action (route, notify, tag, priority, split)"
    )
    action_config: Dict[str, Any] = Field(
        ..., description="Action-specific configuration"
    )
    execution_order: int = Field(0, description="Order of execution")
    condition_expression: Optional[str] = Field(
        None, description="Additional condition for this action"
    )

    @validator("action_type")
    def validate_action_type(cls, v):
        """Validate action type"""
        valid_types = ["route", "notify", "tag", "priority", "split", "log", "webhook"]
        if v not in valid_types:
            raise ValueError(f"Invalid action type. Must be one of: {valid_types}")
        return v


class RuleActionCreate(RuleActionBase):
    """Schema for creating a rule action"""

    pass


class RuleActionResponse(RuleActionBase):
    """Schema for rule action response"""

    id: int
    rule_id: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# Routing Rule Schemas
class RoutingRuleBase(BaseModel):
    """Base schema for routing rules"""

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: int = Field(0, ge=0, le=1000, description="Rule priority (0-1000)")
    status: RuleStatus = Field(RuleStatus.ACTIVE)
    target_type: RouteTargetType
    target_id: Optional[int] = None
    target_config: Optional[Dict[str, Any]] = None
    active_from: Optional[datetime] = None
    active_until: Optional[datetime] = None
    schedule_config: Optional[Dict[str, Any]] = None

    @validator("schedule_config")
    def validate_schedule_config(cls, v):
        """Validate schedule configuration"""
        if v:
            if "days" in v and not isinstance(v["days"], list):
                raise ValueError("Schedule days must be a list")
            if "hours" in v:
                if (
                    not isinstance(v["hours"], dict)
                    or "start" not in v["hours"]
                    or "end" not in v["hours"]
                ):
                    raise ValueError("Schedule hours must have start and end times")
        return v


class RoutingRuleCreate(RoutingRuleBase):
    """Schema for creating a routing rule"""

    conditions: List[RuleConditionCreate] = Field(..., min_items=1)
    actions: List[RuleActionCreate] = Field(..., min_items=1)


class RoutingRuleUpdate(BaseModel):
    """Schema for updating a routing rule"""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    priority: Optional[int] = Field(None, ge=0, le=1000)
    status: Optional[RuleStatus] = None
    target_type: Optional[RouteTargetType] = None
    target_id: Optional[int] = None
    target_config: Optional[Dict[str, Any]] = None
    active_from: Optional[datetime] = None
    active_until: Optional[datetime] = None
    schedule_config: Optional[Dict[str, Any]] = None


class RoutingRuleResponse(RoutingRuleBase):
    """Schema for routing rule response"""

    id: int
    conditions: List[RuleConditionResponse] = []
    actions: List[RuleActionResponse] = []
    evaluation_count: int = 0
    match_count: int = 0
    last_matched_at: Optional[datetime] = None
    created_by: int
    updated_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# Route Evaluation Schemas
class RouteEvaluationRequest(BaseModel):
    """Request to evaluate routing rules for an order"""

    order_id: int
    force_evaluation: bool = Field(
        False, description="Force re-evaluation even if cached"
    )
    test_mode: bool = Field(
        False, description="Run in test mode without applying routes"
    )
    include_inactive: bool = Field(
        False, description="Include inactive rules in evaluation"
    )


class RouteEvaluationResult(BaseModel):
    """Result of route evaluation"""

    order_id: int
    evaluated_rules: int
    matched_rules: List[Dict[str, Any]]
    routing_decision: Dict[str, Any]
    evaluation_time_ms: float
    test_mode: bool
    errors: List[str] = []


# Override Schemas
class RouteOverrideCreate(BaseModel):
    """Schema for creating a route override"""

    order_id: int
    override_type: str = Field(
        ..., description="Type of override (manual, system, emergency)"
    )
    target_type: RouteTargetType
    target_id: int
    reason: Optional[str] = None
    expires_at: Optional[datetime] = None


class RouteOverrideResponse(BaseModel):
    """Schema for route override response"""

    id: int
    order_id: int
    override_type: str
    target_type: RouteTargetType
    target_id: int
    reason: Optional[str]
    overridden_by: int
    expires_at: Optional[datetime]
    original_route: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


# Staff Capability Schemas
class StaffCapabilityCreate(BaseModel):
    """Schema for creating staff capability"""

    staff_id: int
    capability_type: str = Field(
        ..., description="Type of capability (category, station, skill, certification)"
    )
    capability_value: str = Field(..., description="Value of the capability")
    max_concurrent_orders: int = Field(5, ge=1)
    is_available: bool = True
    skill_level: int = Field(3, ge=1, le=5)
    preference_weight: float = Field(1.0, gt=0)
    available_schedule: Optional[Dict[str, Any]] = None


class StaffCapabilityResponse(BaseModel):
    """Schema for staff capability response"""

    id: int
    staff_id: int
    capability_type: str
    capability_value: str
    max_concurrent_orders: int
    is_available: bool
    skill_level: int
    preference_weight: float
    available_schedule: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# Team Schemas
class TeamRoutingConfigCreate(BaseModel):
    """Schema for creating team routing config"""

    team_name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: bool = True
    routing_strategy: RoutingStrategy = RoutingStrategy.ROUND_ROBIN
    max_concurrent_orders: Optional[int] = None
    specializations: Optional[List[str]] = None
    load_balancing_config: Optional[Dict[str, Any]] = None
    schedule_config: Optional[Dict[str, Any]] = None


class TeamRoutingConfigResponse(BaseModel):
    """Schema for team routing config response"""

    id: int
    team_name: str
    description: Optional[str]
    is_active: bool
    routing_strategy: str
    max_concurrent_orders: Optional[int]
    current_load: int
    specializations: Optional[List[str]]
    load_balancing_config: Optional[Dict[str, Any]]
    schedule_config: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class TeamMemberCreate(BaseModel):
    """Schema for adding team member"""

    team_id: int
    staff_id: int
    is_active: bool = True
    role_in_team: Optional[str] = None
    weight: float = Field(1.0, gt=0)
    available_from: Optional[datetime] = None
    available_until: Optional[datetime] = None


class TeamMemberResponse(BaseModel):
    """Schema for team member response"""

    id: int
    team_id: int
    staff_id: int
    is_active: bool
    role_in_team: Optional[str]
    weight: float
    current_load: int
    available_from: Optional[datetime]
    available_until: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# Routing Log Schemas
class RoutingLogQuery(BaseModel):
    """Query parameters for routing logs"""

    rule_id: Optional[int] = None
    order_id: Optional[int] = None
    matched_only: bool = False
    error_only: bool = False
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)


class RoutingLogResponse(BaseModel):
    """Schema for routing log response"""

    id: int
    rule_id: int
    order_id: int
    matched: bool
    evaluation_time_ms: Optional[float]
    order_context: Optional[Dict[str, Any]]
    conditions_evaluated: Optional[Dict[str, Any]]
    actions_executed: Optional[Dict[str, Any]]
    routing_result: Optional[Dict[str, Any]]
    error_occurred: bool
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# Bulk Operations
class BulkRuleStatusUpdate(BaseModel):
    """Schema for bulk rule status update"""

    rule_ids: List[int] = Field(..., min_items=1)
    status: RuleStatus
    reason: Optional[str] = None


class RoutingRuleTestRequest(BaseModel):
    """Request to test routing rules"""

    rule_id: Optional[int] = None
    test_order_data: Dict[str, Any] = Field(
        ..., description="Mock order data for testing"
    )
    include_all_rules: bool = Field(False, description="Test against all rules")


class RoutingRuleTestResult(BaseModel):
    """Result of routing rule test"""

    rule_id: Optional[int]
    rule_name: Optional[str]
    matched: bool
    conditions_results: List[Dict[str, Any]]
    would_execute_actions: List[Dict[str, Any]]
    routing_target: Optional[Dict[str, Any]]
    test_notes: List[str] = []
