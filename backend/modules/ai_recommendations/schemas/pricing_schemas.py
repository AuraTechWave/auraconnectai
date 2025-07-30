# backend/modules/ai_recommendations/schemas/pricing_schemas.py

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional, Any
from datetime import datetime, date, time
from decimal import Decimal
from enum import Enum


class PricingStrategy(str, Enum):
    """Available pricing strategies"""
    DEMAND_BASED = "demand_based"
    COMPETITION_BASED = "competition_based"
    COST_PLUS = "cost_plus"
    VALUE_BASED = "value_based"
    PSYCHOLOGICAL = "psychological"
    DYNAMIC = "dynamic"
    SEASONAL = "seasonal"


class PriceOptimizationGoal(str, Enum):
    """Goals for price optimization"""
    MAXIMIZE_REVENUE = "maximize_revenue"
    MAXIMIZE_PROFIT = "maximize_profit"
    MAXIMIZE_VOLUME = "maximize_volume"
    CLEAR_INVENTORY = "clear_inventory"
    MATCH_COMPETITION = "match_competition"


class DemandLevel(str, Enum):
    """Demand level categories"""
    VERY_LOW = "very_low"
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    VERY_HIGH = "very_high"


class PriceElasticity(str, Enum):
    """Price elasticity categories"""
    HIGHLY_ELASTIC = "highly_elastic"  # Price sensitive
    ELASTIC = "elastic"
    UNIT_ELASTIC = "unit_elastic"
    INELASTIC = "inelastic"
    HIGHLY_INELASTIC = "highly_inelastic"  # Price insensitive


class MenuItemPricingContext(BaseModel):
    """Context information for pricing a menu item"""
    menu_item_id: int
    current_price: Decimal = Field(..., gt=0, description="Current menu price")
    base_cost: Decimal = Field(..., gt=0, description="Cost to make the item")
    
    # Historical data
    avg_daily_sales: float = Field(..., ge=0, description="Average daily sales quantity")
    sales_trend: float = Field(..., description="Sales trend (-1 to 1)")
    last_price_change: Optional[datetime] = None
    
    # Inventory context
    inventory_level: float = Field(..., ge=0, le=100, description="Current inventory %")
    days_until_expiry: Optional[int] = Field(None, ge=0)
    
    # Market context
    competitor_prices: Optional[List[Decimal]] = Field(None, description="Competitor prices for similar items")
    local_market_index: float = Field(default=1.0, gt=0, description="Local market price index")
    
    # Demand indicators
    current_demand: DemandLevel = Field(default=DemandLevel.NORMAL)
    seasonal_factor: float = Field(default=1.0, gt=0, description="Seasonal demand multiplier")
    event_factor: float = Field(default=1.0, gt=0, description="Special event multiplier")
    
    # Customer context
    price_elasticity: PriceElasticity = Field(default=PriceElasticity.UNIT_ELASTIC)
    customer_rating: Optional[float] = Field(None, ge=1, le=5)
    
    class Config:
        json_schema_extra = {
            "example": {
                "menu_item_id": 101,
                "current_price": "12.99",
                "base_cost": "4.50",
                "avg_daily_sales": 25.5,
                "sales_trend": 0.15,
                "inventory_level": 75.0,
                "current_demand": "high",
                "price_elasticity": "elastic"
            }
        }


class PricingRecommendation(BaseModel):
    """Individual pricing recommendation for a menu item"""
    menu_item_id: int
    item_name: str
    current_price: Decimal
    recommended_price: Decimal
    min_recommended_price: Decimal
    max_recommended_price: Decimal
    
    # Pricing metrics
    price_change_percentage: float
    expected_demand_change: float
    expected_revenue_impact: float
    expected_profit_impact: float
    
    # Recommendation details
    confidence_score: float = Field(..., ge=0, le=1)
    strategy_used: PricingStrategy
    factors_considered: List[str]
    
    # Reasoning
    primary_reason: str
    detailed_reasoning: List[str]
    risks: List[str]
    
    # Implementation
    implementation_notes: Optional[str] = None
    recommended_duration_days: Optional[int] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "menu_item_id": 101,
                "item_name": "Grilled Salmon",
                "current_price": "18.99",
                "recommended_price": "21.99",
                "min_recommended_price": "19.99",
                "max_recommended_price": "23.99",
                "price_change_percentage": 15.8,
                "expected_demand_change": -5.2,
                "expected_revenue_impact": 9.8,
                "expected_profit_impact": 12.3,
                "confidence_score": 0.85,
                "strategy_used": "demand_based",
                "primary_reason": "High demand and low inventory warrant price increase"
            }
        }


class BulkPricingRequest(BaseModel):
    """Request for bulk pricing recommendations"""
    category_ids: Optional[List[int]] = Field(None, description="Filter by categories")
    menu_item_ids: Optional[List[int]] = Field(None, description="Specific items to price")
    
    # Optimization parameters
    optimization_goal: PriceOptimizationGoal = Field(default=PriceOptimizationGoal.MAXIMIZE_PROFIT)
    strategies_to_use: List[PricingStrategy] = Field(default=[PricingStrategy.DYNAMIC])
    
    # Constraints
    max_price_increase_percent: float = Field(default=20.0, ge=0, le=100)
    max_price_decrease_percent: float = Field(default=15.0, ge=0, le=100)
    maintain_price_relationships: bool = Field(default=True, description="Maintain relative pricing between items")
    round_to_nearest: Decimal = Field(default=Decimal("0.05"), description="Round prices to nearest value")
    
    # Context
    time_horizon_days: int = Field(default=7, ge=1, le=90)
    include_competitors: bool = Field(default=True)
    
    @validator('round_to_nearest')
    def validate_rounding(cls, v):
        valid_values = [Decimal("0.01"), Decimal("0.05"), Decimal("0.10"), 
                       Decimal("0.25"), Decimal("0.50"), Decimal("1.00")]
        if v not in valid_values:
            raise ValueError(f"round_to_nearest must be one of {valid_values}")
        return v


class PricingRecommendationSet(BaseModel):
    """Set of pricing recommendations"""
    request_id: str = Field(..., description="Unique request identifier")
    generated_at: datetime
    valid_until: datetime
    
    # Recommendations
    recommendations: List[PricingRecommendation]
    total_items_analyzed: int
    total_recommendations: int
    
    # Summary metrics
    avg_price_change_percent: float
    expected_total_revenue_impact: float
    expected_total_profit_impact: float
    
    # Strategy summary
    strategies_used: Dict[PricingStrategy, int]
    optimization_goal: PriceOptimizationGoal
    
    # Implementation plan
    implementation_phases: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Phased implementation plan"
    )
    
    # Warnings and notes
    warnings: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    
    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "price-rec-2025-01-29-001",
                "generated_at": "2025-01-29T10:00:00Z",
                "valid_until": "2025-02-05T10:00:00Z",
                "total_items_analyzed": 50,
                "total_recommendations": 15,
                "avg_price_change_percent": 8.5,
                "expected_total_revenue_impact": 12.3,
                "expected_total_profit_impact": 15.7
            }
        }


class PriceTestingConfig(BaseModel):
    """Configuration for A/B price testing"""
    test_name: str
    menu_item_ids: List[int]
    
    # Test variants
    control_price: Decimal
    test_prices: List[Decimal]
    
    # Test parameters
    test_duration_days: int = Field(default=14, ge=7, le=30)
    min_sample_size_per_variant: int = Field(default=100, ge=50)
    
    # Allocation
    traffic_allocation: Dict[str, float] = Field(
        default_factory=lambda: {"control": 0.5, "variant_a": 0.5},
        description="Traffic allocation between variants"
    )
    
    # Success metrics
    primary_metric: str = Field(default="revenue_per_customer")
    secondary_metrics: List[str] = Field(default_factory=list)
    
    @validator('traffic_allocation')
    def validate_allocation(cls, v):
        total = sum(v.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError("Traffic allocation must sum to 1.0")
        return v


class PriceTestingResult(BaseModel):
    """Results from price testing"""
    test_name: str
    menu_item_id: int
    test_duration_actual: int
    
    # Results by variant
    variant_results: Dict[str, Dict[str, Any]]
    
    # Statistical analysis
    winner: Optional[str] = None
    confidence_level: float
    statistical_significance: bool
    
    # Recommendations
    recommended_price: Decimal
    expected_improvement: float
    implementation_confidence: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "test_name": "Salmon Pricing Test",
                "menu_item_id": 101,
                "test_duration_actual": 14,
                "winner": "variant_a",
                "confidence_level": 0.95,
                "statistical_significance": True,
                "recommended_price": "21.99",
                "expected_improvement": 8.5
            }
        }