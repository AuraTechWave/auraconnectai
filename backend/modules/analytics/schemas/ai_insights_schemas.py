# backend/modules/analytics/schemas/ai_insights_schemas.py

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime, date, time
from decimal import Decimal
from enum import Enum


class InsightType(str, Enum):
    """Types of AI-generated insights"""

    PEAK_TIME = "peak_time"
    PRODUCT_TREND = "product_trend"
    CUSTOMER_PATTERN = "customer_pattern"
    REVENUE_FORECAST = "revenue_forecast"
    SEASONALITY = "seasonality"
    ANOMALY = "anomaly"
    RECOMMENDATION = "recommendation"


class ConfidenceLevel(str, Enum):
    """Confidence levels for AI predictions"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TimePattern(BaseModel):
    """Time-based pattern analysis"""

    hour: int = Field(..., ge=0, le=23, description="Hour of day (0-23)")
    day_of_week: Optional[int] = Field(
        None, ge=0, le=6, description="Day of week (0=Monday)"
    )
    intensity: float = Field(..., ge=0, le=1, description="Activity intensity (0-1)")
    order_count: int = Field(..., description="Average orders in this period")
    revenue: Decimal = Field(..., description="Average revenue in this period")
    customer_count: int = Field(..., description="Average unique customers")


class PeakTimeInsight(BaseModel):
    """Insights about peak business hours"""

    insight_type: InsightType = Field(InsightType.PEAK_TIME)
    primary_peak: TimePattern = Field(..., description="Busiest time period")
    secondary_peak: Optional[TimePattern] = Field(
        None, description="Second busiest period"
    )
    quiet_periods: List[TimePattern] = Field(
        default_factory=list, description="Low activity periods"
    )
    weekly_pattern: Dict[str, List[TimePattern]] = Field(
        ..., description="Peak times by day of week"
    )
    confidence: ConfidenceLevel = Field(..., description="Confidence in analysis")
    recommendations: List[str] = Field(..., description="Actionable recommendations")

    class Config:
        json_schema_extra = {
            "example": {
                "insight_type": "peak_time",
                "primary_peak": {
                    "hour": 12,
                    "day_of_week": None,
                    "intensity": 0.95,
                    "order_count": 45,
                    "revenue": "2500.00",
                    "customer_count": 38,
                },
                "confidence": "high",
                "recommendations": [
                    "Schedule more staff during 12:00-13:00",
                    "Prepare inventory for lunch rush",
                ],
            }
        }


class ProductTrend(BaseModel):
    """Product popularity and trend information"""

    product_id: int
    product_name: str
    trend_direction: str = Field(..., description="rising, falling, stable")
    trend_strength: float = Field(..., ge=0, le=1, description="Trend strength (0-1)")
    current_rank: int = Field(..., description="Current popularity rank")
    previous_rank: Optional[int] = Field(None, description="Previous period rank")
    velocity: float = Field(..., description="Rate of change")
    predicted_demand: Optional[int] = Field(
        None, description="Predicted units for next period"
    )
    seasonality_factor: Optional[float] = Field(
        None, description="Seasonal influence (0-1)"
    )


class ProductInsight(BaseModel):
    """AI insights for product performance"""

    insight_type: InsightType = Field(InsightType.PRODUCT_TREND)
    top_rising: List[ProductTrend] = Field(
        ..., description="Products gaining popularity"
    )
    top_falling: List[ProductTrend] = Field(
        ..., description="Products losing popularity"
    )
    stable_performers: List[ProductTrend] = Field(
        ..., description="Consistently popular products"
    )
    new_trending: List[ProductTrend] = Field(
        ..., description="Newly introduced trending items"
    )
    confidence: ConfidenceLevel
    analysis_period: Dict[str, date] = Field(..., description="Period analyzed")
    recommendations: List[str]

    class Config:
        json_schema_extra = {
            "example": {
                "insight_type": "product_trend",
                "top_rising": [
                    {
                        "product_id": 101,
                        "product_name": "Seasonal Salad",
                        "trend_direction": "rising",
                        "trend_strength": 0.85,
                        "current_rank": 3,
                        "previous_rank": 8,
                        "velocity": 0.45,
                        "predicted_demand": 150,
                    }
                ],
                "confidence": "high",
                "recommendations": [
                    "Increase inventory for Seasonal Salad",
                    "Consider promotional pricing for declining items",
                ],
            }
        }


class CustomerPattern(BaseModel):
    """Customer behavior pattern"""

    pattern_name: str = Field(..., description="Name of the pattern")
    description: str = Field(..., description="Pattern description")
    customer_segment: Optional[str] = Field(
        None, description="Customer segment affected"
    )
    frequency: str = Field(..., description="daily, weekly, monthly")
    impact_score: float = Field(..., ge=0, le=1, description="Business impact (0-1)")
    examples: List[Dict[str, Any]] = Field(..., description="Example occurrences")


class CustomerInsight(BaseModel):
    """AI insights for customer behavior"""

    insight_type: InsightType = Field(InsightType.CUSTOMER_PATTERN)
    patterns_detected: List[CustomerPattern]
    repeat_customer_rate: float = Field(
        ..., description="Percentage of repeat customers"
    )
    average_order_frequency: float = Field(
        ..., description="Orders per customer per month"
    )
    churn_risk_segments: List[Dict[str, Any]] = Field(
        ..., description="Customer segments at risk"
    )
    lifetime_value_trends: Dict[str, float] = Field(..., description="CLV by segment")
    confidence: ConfidenceLevel
    recommendations: List[str]


class SeasonalityPattern(BaseModel):
    """Seasonal pattern detection"""

    season_name: str = Field(..., description="Season or period name")
    start_month: int = Field(..., ge=1, le=12)
    end_month: int = Field(..., ge=1, le=12)
    impact_multiplier: float = Field(..., description="Revenue impact multiplier")
    affected_products: List[int] = Field(..., description="Product IDs affected")
    historical_accuracy: float = Field(
        ..., ge=0, le=1, description="Historical prediction accuracy"
    )


class AnomalyDetection(BaseModel):
    """Anomaly detection results"""

    anomaly_date: date
    anomaly_type: str = Field(..., description="revenue_spike, order_drop, etc.")
    severity: str = Field(..., description="high, medium, low")
    deviation_percentage: float
    potential_causes: List[str]
    affected_metrics: Dict[str, float]


class AIInsightSummary(BaseModel):
    """Comprehensive AI insights summary"""

    generated_at: datetime = Field(default_factory=datetime.utcnow)
    analysis_period: Dict[str, date]
    peak_times: Optional[PeakTimeInsight] = None
    product_insights: Optional[ProductInsight] = None
    customer_insights: Optional[CustomerInsight] = None
    seasonality: List[SeasonalityPattern] = Field(default_factory=list)
    anomalies: List[AnomalyDetection] = Field(default_factory=list)
    overall_recommendations: List[str]
    next_update: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "generated_at": "2025-01-29T12:00:00",
                "analysis_period": {"start": "2025-01-01", "end": "2025-01-29"},
                "overall_recommendations": [
                    "Optimize staffing for detected peak hours",
                    "Stock up on trending products",
                    "Launch retention campaign for at-risk segments",
                ],
                "next_update": "2025-01-30T00:00:00",
            }
        }


class InsightRequest(BaseModel):
    """Request for AI insights generation"""

    insight_types: List[InsightType] = Field(
        ..., description="Types of insights to generate"
    )
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    min_confidence: ConfidenceLevel = Field(
        ConfidenceLevel.MEDIUM, description="Minimum confidence level"
    )
    include_recommendations: bool = Field(
        True, description="Include actionable recommendations"
    )
    force_refresh: bool = Field(False, description="Force regeneration of insights")


class InsightResponse(BaseModel):
    """Response containing AI insights"""

    success: bool
    insights: AIInsightSummary
    processing_time: float = Field(
        ..., description="Time taken to generate insights (seconds)"
    )
    cache_hit: bool = Field(..., description="Whether insights were served from cache")
    warnings: List[str] = Field(
        default_factory=list, description="Any warnings during processing"
    )
