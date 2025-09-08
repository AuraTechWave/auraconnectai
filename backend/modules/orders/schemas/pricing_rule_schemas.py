# backend/modules/orders/schemas/pricing_rule_schemas.py

from typing import List, Dict, Any, Optional
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum

from ..models.pricing_rule_models import (
    RuleType,
    RuleStatus,
    RulePriority,
    ConflictResolution,
)


# Request/Response Models


class PricingRuleConditions(BaseModel):
    """Flexible conditions for pricing rules"""

    time: Optional[Dict[str, Any]] = None
    items: Optional[Dict[str, Any]] = None
    customer: Optional[Dict[str, Any]] = None
    order: Optional[Dict[str, Any]] = None


class CreatePricingRuleRequest(BaseModel):
    """Request to create a new pricing rule"""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    rule_type: RuleType
    priority: int = Field(RulePriority.DEFAULT.value, ge=1, le=5)

    # Discount configuration
    discount_value: Decimal = Field(..., gt=0)
    max_discount_amount: Optional[Decimal] = None
    min_order_amount: Optional[Decimal] = None

    # Conditions
    conditions: PricingRuleConditions = Field(default_factory=PricingRuleConditions)

    # Validity
    valid_from: datetime = Field(default_factory=datetime.utcnow)
    valid_until: Optional[datetime] = None

    # Usage limits
    max_uses_total: Optional[int] = None
    max_uses_per_customer: Optional[int] = None

    # Stacking
    stackable: bool = False
    excluded_rule_ids: List[str] = Field(default_factory=list)
    conflict_resolution: ConflictResolution = ConflictResolution.HIGHEST_DISCOUNT

    # Other
    requires_code: bool = False
    promo_code: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

    @field_validator("valid_until")
    def validate_dates(cls, v, info):
        if v and "valid_from" in info.data and v <= info.data["valid_from"]:
            raise ValueError("valid_until must be after valid_from")
        return v

    @field_validator("promo_code")
    def validate_promo_code(cls, v, info):
        if info.data.get("requires_code") and not v:
            raise ValueError("promo_code is required when requires_code is True")
        return v


class UpdatePricingRuleRequest(BaseModel):
    """Request to update a pricing rule"""

    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[RuleStatus] = None
    priority: Optional[int] = Field(None, ge=1, le=5)

    # Discount configuration
    discount_value: Optional[Decimal] = Field(None, gt=0)
    max_discount_amount: Optional[Decimal] = None
    min_order_amount: Optional[Decimal] = None

    # Conditions
    conditions: Optional[PricingRuleConditions] = None

    # Validity
    valid_until: Optional[datetime] = None

    # Usage limits
    max_uses_total: Optional[int] = None
    max_uses_per_customer: Optional[int] = None

    # Stacking
    stackable: Optional[bool] = None
    excluded_rule_ids: Optional[List[str]] = None

    # Other
    tags: Optional[List[str]] = None


class PricingRuleResponse(BaseModel):
    """Response with pricing rule details"""

    id: int
    rule_id: str
    name: str
    description: Optional[str]
    rule_type: RuleType
    status: RuleStatus
    priority: int

    # Restaurant
    restaurant_id: int

    # Discount
    discount_value: float
    max_discount_amount: Optional[float]
    min_order_amount: Optional[float]

    # Conditions
    conditions: Dict[str, Any]

    # Validity
    valid_from: datetime
    valid_until: Optional[datetime]
    is_valid: bool

    # Usage
    max_uses_total: Optional[int]
    max_uses_per_customer: Optional[int]
    current_uses: int

    # Stacking
    stackable: bool
    excluded_rule_ids: List[str]
    conflict_resolution: ConflictResolution

    # Other
    requires_code: bool
    promo_code: Optional[str]
    tags: List[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Debug Models


class DebugTraceEntry(BaseModel):
    """Single debug trace entry"""

    timestamp: datetime
    event_type: str
    message: str
    data: Dict[str, Any] = Field(default_factory=dict)


class RuleEvaluationResult(BaseModel):
    """Result of evaluating a single rule"""

    rule_id: int
    rule_name: str
    rule_type: RuleType
    priority: int
    applicable: bool
    skip_reason: Optional[str] = None
    conditions_met: Dict[str, bool] = Field(default_factory=dict)
    discount_amount: Decimal = Decimal("0")

    # For debugging
    evaluation_time_ms: Optional[float] = None

    class Config:
        arbitrary_types_allowed = True


class ConflictInfo(BaseModel):
    """Information about rule conflicts"""

    conflicting_rules: List[int]
    resolution_method: ConflictResolution
    selected_rule_id: int
    reason: str


class PricingRuleDebugInfo(BaseModel):
    """Complete debug information for pricing rule evaluation"""

    order_id: int
    evaluation_timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Summary
    rules_evaluated: int
    rules_applied: int
    rules_skipped: int = 0
    conflicts_resolved: int = 0

    # Financial impact
    total_discount: Decimal
    original_amount: Decimal = Decimal("0")
    final_amount: Decimal = Decimal("0")

    # Detailed results
    evaluation_results: List[RuleEvaluationResult]
    applied_rules: List[Dict[str, Any]] = Field(default_factory=list)
    skipped_rules: List[Dict[str, Any]] = Field(default_factory=list)
    conflicts: List[ConflictInfo] = Field(default_factory=list)

    # Debug traces
    debug_traces: List[DebugTraceEntry]

    # Performance metrics
    total_evaluation_time_ms: Optional[float] = None
    metrics: Dict[str, int] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True


# API Response Models


class PricingRuleApplicationResponse(BaseModel):
    """Response for a pricing rule application"""

    id: int
    rule_id: int
    rule_name: str
    order_id: int
    discount_amount: float
    original_amount: float
    final_amount: float
    applied_at: datetime
    conditions_met: Dict[str, bool]

    model_config = ConfigDict(from_attributes=True)


class PricingRuleMetricsResponse(BaseModel):
    """Metrics for a pricing rule"""

    rule_id: int
    rule_name: str
    date_range: Dict[str, datetime]

    # Usage metrics
    total_applications: int
    unique_customers: int
    total_discount_amount: float
    average_discount: float

    # Performance metrics
    conversion_rate: Optional[float]
    average_order_value: Optional[float]
    conflicts_skipped: int
    stacking_count: int

    # Trends
    daily_applications: List[Dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)


# Validation schemas


class ValidatePricingRuleRequest(BaseModel):
    """Request to validate rule conditions"""

    conditions: Dict[str, Any]
    rule_type: RuleType
    test_order_data: Optional[Dict[str, Any]] = None


class ValidatePricingRuleResponse(BaseModel):
    """Response from rule validation"""

    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    normalized_conditions: Optional[Dict[str, Any]] = None
