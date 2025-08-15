# backend/modules/analytics/schemas/predictive_analytics_schemas.py

"""
Schemas for Predictive Analytics module.

Handles demand forecasting, stock optimization, and predictive insights
for inventory management and business planning.
"""

from datetime import date, datetime
from typing import Dict, List, Optional, Any, Union
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field, validator


class ForecastType(str, Enum):
    """Types of forecasting models"""

    DEMAND = "demand"
    STOCK = "stock"
    REVENUE = "revenue"
    FOOTFALL = "footfall"
    SEASONAL = "seasonal"


class TimeGranularity(str, Enum):
    """Time granularity for predictions"""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class PredictionConfidence(str, Enum):
    """Confidence levels for predictions"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class ModelType(str, Enum):
    """Available prediction models"""

    ARIMA = "arima"
    PROPHET = "prophet"
    LSTM = "lstm"
    ENSEMBLE = "ensemble"
    MOVING_AVERAGE = "moving_average"
    EXPONENTIAL_SMOOTHING = "exponential_smoothing"


class SeasonalityType(str, Enum):
    """Types of seasonality patterns"""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    HOLIDAY = "holiday"
    CUSTOM = "custom"


# Request Schemas
class PredictionRequest(BaseModel):
    """Base request for predictions"""

    entity_id: Optional[int] = Field(
        None, description="ID of specific entity (product/category)"
    )
    entity_type: str = Field(
        ..., description="Type of entity: product, category, overall"
    )
    forecast_type: ForecastType
    time_granularity: TimeGranularity = TimeGranularity.DAILY
    horizon_days: int = Field(7, ge=1, le=365, description="Forecast horizon in days")
    include_confidence_intervals: bool = True
    model_type: Optional[ModelType] = None
    custom_parameters: Optional[Dict[str, Any]] = None


class DemandForecastRequest(PredictionRequest):
    """Request for demand forecasting"""

    include_external_factors: bool = True
    external_factors: Optional[Dict[str, Any]] = Field(
        None, description="External factors like weather, events, holidays"
    )

    def __init__(self, **data):
        data["forecast_type"] = ForecastType.DEMAND
        super().__init__(**data)


class StockOptimizationRequest(BaseModel):
    """Request for stock optimization"""

    product_ids: Optional[List[int]] = None
    category_ids: Optional[List[int]] = None
    optimization_objective: str = Field(
        "minimize_waste", description="minimize_waste, maximize_availability, balanced"
    )
    service_level: float = Field(
        0.95, ge=0.5, le=0.99, description="Target service level"
    )
    lead_time_days: int = Field(2, ge=0, description="Supplier lead time")
    include_safety_stock: bool = True
    budget_constraint: Optional[Decimal] = None


class BatchPredictionRequest(BaseModel):
    """Request for batch predictions"""

    predictions: List[PredictionRequest]
    priority: str = Field("normal", description="normal, high, low")
    callback_url: Optional[str] = None


# Response Schemas
class PredictionPoint(BaseModel):
    """Single prediction point"""

    timestamp: datetime
    predicted_value: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    confidence_level: Optional[float] = Field(None, ge=0, le=1)


class ForecastMetadata(BaseModel):
    """Metadata about the forecast"""

    model_used: ModelType
    training_period: Dict[str, date]
    seasonality_detected: List[SeasonalityType]
    accuracy_metrics: Dict[str, float]
    confidence: PredictionConfidence
    generated_at: datetime = Field(default_factory=datetime.now)


class DemandForecast(BaseModel):
    """Demand forecast response"""

    entity_id: Optional[int]
    entity_type: str
    entity_name: str
    predictions: List[PredictionPoint]
    metadata: ForecastMetadata
    insights: List[str]
    recommended_actions: List[Dict[str, Any]]


class StockRecommendation(BaseModel):
    """Stock level recommendation"""

    product_id: int
    product_name: str
    current_stock: float
    recommended_stock: float
    reorder_point: float
    reorder_quantity: float
    safety_stock: float
    expected_stockout_risk: float
    estimated_holding_cost: Decimal
    estimated_stockout_cost: Decimal


class StockOptimizationResult(BaseModel):
    """Result of stock optimization"""

    optimization_id: str
    recommendations: List[StockRecommendation]
    total_investment_required: Decimal
    expected_service_level: float


class BatchForecastResult(BaseModel):
    """Result of batch forecast request"""

    task_id: Optional[str] = None
    status: str
    message: Optional[str] = None
    forecasts: Optional[List[DemandForecast]] = None
    expected_waste_reduction: float
    optimization_summary: Dict[str, Any]
    generated_at: datetime = Field(default_factory=datetime.now)


class InventoryHealthCheck(BaseModel):
    """Health check result for inventory item"""

    product_id: int
    product_name: str
    current_stock: float
    days_of_stock_remaining: Optional[float]
    stockout_risk: float = Field(..., ge=0, le=1)
    overstock_risk: float = Field(..., ge=0, le=1)
    health_score: float = Field(..., ge=0, le=100)
    issues: List[str] = []
    recommendations: List[str] = []


class InventoryHealthReport(BaseModel):
    """Overall inventory health report"""

    report_id: str
    generated_at: datetime = Field(default_factory=datetime.now)
    total_products: int
    healthy_products: int
    at_risk_products: int
    critical_products: int
    overall_health_score: float = Field(..., ge=0, le=100)
    total_inventory_value: Decimal
    at_risk_value: Decimal
    health_checks: List[InventoryHealthCheck]
    summary_recommendations: List[str]


class PredictionAlert(BaseModel):
    """Alert for significant predictions"""

    alert_id: str
    alert_type: str = Field(..., description="stockout_risk, demand_spike, anomaly")
    severity: str = Field(..., description="low, medium, high, critical")
    entity_id: Optional[int]
    entity_name: str
    message: str
    predicted_impact: Dict[str, Any]
    recommended_actions: List[str]
    alert_time: datetime = Field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None


class ModelPerformance(BaseModel):
    """Model performance metrics"""

    model_type: ModelType
    entity_type: str
    mae: float = Field(..., description="Mean Absolute Error")
    mape: float = Field(..., description="Mean Absolute Percentage Error")
    rmse: float = Field(..., description="Root Mean Square Error")
    r_squared: float = Field(..., description="R-squared value")
    training_samples: int
    evaluation_period: Dict[str, date]
    last_updated: datetime


class ModelPerformanceReport(BaseModel):
    """Report containing model performance metrics for all models"""

    report_id: str
    generated_at: datetime = Field(default_factory=datetime.now)
    performance_metrics: List[ModelPerformance]
    best_performing_model: Optional[ModelType] = None
    recommendations: List[str] = []
    evaluation_summary: Dict[str, Any]


class ForecastComparison(BaseModel):
    """Comparison of forecast vs actuals"""

    entity_id: Optional[int]
    entity_name: str
    comparison_period: Dict[str, date]
    predictions: List[PredictionPoint]
    actuals: List[Dict[str, Any]]
    accuracy_metrics: Dict[str, float]
    deviation_analysis: Dict[str, Any]


class SeasonalPattern(BaseModel):
    """Detected seasonal pattern"""

    pattern_type: SeasonalityType
    strength: float = Field(..., ge=0, le=1, description="Pattern strength")
    period: int = Field(..., description="Period in time units")
    peak_periods: List[str]
    low_periods: List[str]
    impact_percentage: float


class TrendAnalysis(BaseModel):
    """Trend analysis results"""

    entity_id: Optional[int]
    entity_name: str
    trend_direction: str = Field(..., description="increasing, decreasing, stable")
    trend_strength: float = Field(..., ge=-1, le=1)
    change_points: List[datetime]
    seasonal_patterns: List[SeasonalPattern]
    growth_rate: float
    volatility: float


class PredictiveInsight(BaseModel):
    """Actionable predictive insight"""

    insight_id: str
    insight_type: str = Field(
        ..., description="demand_trend, stock_risk, revenue_opportunity, anomaly"
    )
    title: str
    description: str
    impact_score: float = Field(..., ge=0, le=10)
    affected_entities: List[Dict[str, Any]]
    recommended_actions: List[Dict[str, Any]]
    confidence: PredictionConfidence
    valid_until: datetime
    created_at: datetime = Field(default_factory=datetime.now)


class ForecastAccuracyReport(BaseModel):
    """Report on forecast accuracy"""

    report_id: str
    period: Dict[str, date]
    overall_accuracy: float
    model_performances: List[ModelPerformance]
    accuracy_by_category: Dict[str, float]
    accuracy_by_product: List[Dict[str, Any]]
    improvement_recommendations: List[str]
    generated_at: datetime = Field(default_factory=datetime.now)


class RealTimePredictionUpdate(BaseModel):
    """Real-time prediction update via WebSocket"""

    update_id: str
    update_type: str = Field(..., description="forecast_update, alert, insight")
    entity_id: Optional[int]
    entity_type: str
    data: Union[DemandForecast, PredictionAlert, PredictiveInsight]
    timestamp: datetime = Field(default_factory=datetime.now)


class PredictionExportRequest(BaseModel):
    """Request to export predictions"""

    forecast_ids: List[str]
    format: str = Field("csv", description="csv, excel, json")
    include_metadata: bool = True
    include_charts: bool = False
    date_range: Optional[Dict[str, date]] = None


class HistoricalDataRequest(BaseModel):
    """Request for historical data analysis"""

    entity_id: Optional[int]
    entity_type: str
    metric_type: str = Field(..., description="sales, stock_levels, revenue")
    date_from: date
    date_to: date
    aggregation: TimeGranularity = TimeGranularity.DAILY
    include_anomalies: bool = True
    include_seasonality: bool = True


class ModelTrainingRequest(BaseModel):
    """Request to train or retrain models"""

    entity_ids: Optional[List[int]] = None
    entity_type: str
    model_types: List[ModelType]
    training_period: Dict[str, date]
    validation_split: float = Field(0.2, ge=0.1, le=0.3)
    hyperparameter_tuning: bool = True
    custom_parameters: Optional[Dict[str, Any]] = None
