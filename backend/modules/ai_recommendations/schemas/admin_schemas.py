# backend/modules/ai_recommendations/schemas/admin_schemas.py

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from decimal import Decimal


class FeedbackSummaryResponse(BaseModel):
    """Summary of feedback across models and domains"""

    time_period: Dict[str, datetime]
    total_feedback_count: int
    unique_users: int
    average_rating: float

    rating_distribution: Dict[str, int] = Field(
        description="Count of feedback by rating (1-5)"
    )

    feedback_by_type: Dict[str, int] = Field(
        description="Count by feedback type (positive, negative, suggestion)"
    )

    top_positive_comments: List[Dict[str, Any]] = Field(
        description="Top rated feedback with comments"
    )

    top_negative_comments: List[Dict[str, Any]] = Field(
        description="Lowest rated feedback with comments"
    )

    model_breakdown: List[Dict[str, Any]] = Field(
        description="Feedback stats broken down by model"
    )

    domain_breakdown: List[Dict[str, Any]] = Field(
        description="Feedback stats broken down by domain"
    )


class ModelPerformanceResponse(BaseModel):
    """Performance metrics for AI models"""

    model_type: str
    domain: Optional[str] = None
    endpoint: Optional[str] = None

    # Request metrics
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate: float = Field(ge=0, le=1)

    # Performance metrics
    avg_response_time: float = Field(description="Average response time in seconds")
    p95_response_time: float = Field(description="95th percentile response time")
    avg_confidence_score: float = Field(ge=0, le=1)

    # Feedback metrics
    feedback_count: int
    average_rating: Optional[float] = Field(None, ge=1, le=5)
    positive_feedback_rate: Optional[float] = Field(None, ge=0, le=1)

    # Business impact
    estimated_value_impact: Optional[float] = None
    adoption_rate: Optional[float] = Field(None, ge=0, le=1)

    class Config:
        json_encoders = {Decimal: float}


class DomainInsightsResponse(BaseModel):
    """Detailed insights for a specific domain"""

    domain: str
    analysis_period: Dict[str, datetime]

    # Usage statistics
    total_suggestions: int
    unique_users: int
    suggestions_per_user: float
    peak_usage_hour: int = Field(ge=0, le=23)

    # Model performance
    models_used: List[str]
    primary_model: str
    model_performance: List[ModelPerformanceResponse]

    # Feedback analysis
    overall_satisfaction: float = Field(ge=1, le=5)
    feedback_sentiment: Dict[str, float] = Field(
        description="Sentiment breakdown (positive, neutral, negative)"
    )

    # Common patterns
    top_use_cases: List[Dict[str, Any]]
    common_issues: List[Dict[str, Any]]
    improvement_suggestions: List[str]

    # Trends
    usage_trend: str = Field(description="increasing, stable, or decreasing")
    satisfaction_trend: str = Field(description="improving, stable, or declining")


class FeedbackTrendResponse(BaseModel):
    """Feedback trends over time"""

    time_range: Dict[str, datetime]
    interval: str

    trends: List[Dict[str, Any]] = Field(description="Time series data points")

    summary_stats: Dict[str, Any] = Field(
        description="Summary statistics for the period"
    )

    significant_changes: List[Dict[str, Any]] = Field(
        description="Significant changes detected in trends"
    )


class FeedbackDetailEntry(BaseModel):
    """Detailed feedback entry"""

    id: int
    suggestion_id: str
    user_id: Optional[int]
    session_id: Optional[str]

    model_type: str
    domain: str
    endpoint: str

    rating: int = Field(ge=1, le=5)
    feedback_type: str
    comment: Optional[str]

    # Context
    suggestion_context: Dict[str, Any]
    value_impact: Optional[float]

    created_at: datetime

    class Config:
        orm_mode = True


class ModelComparisonResponse(BaseModel):
    """Model comparison results"""

    models_compared: List[str]
    metric: str
    time_period: Dict[str, datetime]

    comparison_data: List[Dict[str, Any]] = Field(description="Comparison data points")

    winner: str = Field(description="Best performing model")
    improvement_percentage: float = Field(
        description="Improvement of winner over average"
    )

    statistical_significance: bool
    confidence_level: float = Field(ge=0, le=1)

    recommendations: List[str]


class ImprovementRecommendation(BaseModel):
    """Recommendation for improving AI model performance"""

    priority: str = Field(description="high, medium, or low")
    category: str = Field(
        description="model_accuracy, user_experience, performance, or adoption"
    )

    title: str
    description: str

    affected_models: List[str]
    affected_domains: List[str]

    expected_impact: Dict[str, Any] = Field(
        description="Expected improvements if implemented"
    )

    implementation_steps: List[str]
    estimated_effort: str = Field(description="low, medium, or high")

    supporting_data: Dict[str, Any] = Field(
        description="Data supporting this recommendation"
    )


class AlertConfiguration(BaseModel):
    """Alert configuration for AI monitoring"""

    low_rating_threshold: float = Field(2.5, ge=1, le=5)
    high_failure_rate: float = Field(0.2, ge=0, le=1)
    low_confidence_threshold: float = Field(0.5, ge=0, le=1)

    notification_channels: List[str] = Field(
        default=["email"], description="email, slack, webhook"
    )

    check_interval_minutes: int = Field(60, ge=5, le=1440)

    # Specific alerts
    enable_performance_alerts: bool = True
    enable_feedback_alerts: bool = True
    enable_usage_anomaly_alerts: bool = True

    # Recipients
    alert_recipients: List[str] = Field(
        default=[], description="Email addresses or webhook URLs"
    )
