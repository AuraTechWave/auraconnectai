# backend/modules/ai_recommendations/schemas/__init__.py

from .pricing_schemas import (
    PricingStrategy,
    PriceOptimizationGoal,
    DemandLevel,
    PriceElasticity,
    MenuItemPricingContext,
    PricingRecommendation,
    BulkPricingRequest,
    PricingRecommendationSet,
    PriceTestingConfig,
    PriceTestingResult
)

from .staffing_schemas import (
    StaffRole,
    ShiftType,
    DayOfWeek,
    StaffingLevel,
    DemandForecast,
    StaffRequirement,
    ShiftRecommendation,
    StaffingPattern,
    StaffingOptimizationRequest,
    StaffingRecommendationSet,
    StaffPerformanceMetrics,
    LaborCostAnalysis
)

__all__ = [
    # Pricing schemas
    "PricingStrategy",
    "PriceOptimizationGoal",
    "DemandLevel",
    "PriceElasticity",
    "MenuItemPricingContext",
    "PricingRecommendation",
    "BulkPricingRequest",
    "PricingRecommendationSet",
    "PriceTestingConfig",
    "PriceTestingResult",
    
    # Staffing schemas
    "StaffRole",
    "ShiftType",
    "DayOfWeek",
    "StaffingLevel",
    "DemandForecast",
    "StaffRequirement",
    "ShiftRecommendation",
    "StaffingPattern",
    "StaffingOptimizationRequest",
    "StaffingRecommendationSet",
    "StaffPerformanceMetrics",
    "LaborCostAnalysis"
]