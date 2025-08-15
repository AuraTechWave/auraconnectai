# backend/modules/analytics/schemas/realtime_schemas.py

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union, Literal
from datetime import datetime, date
from decimal import Decimal
from enum import Enum


class MetricType(str, Enum):
    """Types of real-time metrics"""

    REVENUE = "revenue"
    ORDERS = "orders"
    CUSTOMERS = "customers"
    AVERAGE_ORDER_VALUE = "average_order_value"
    STAFF_PERFORMANCE = "staff_performance"
    PRODUCT_PERFORMANCE = "product_performance"
    SYSTEM_STATUS = "system_status"


class AlertSeverity(str, Enum):
    """Alert severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WebSocketMessageType(str, Enum):
    """WebSocket message types"""

    DASHBOARD_UPDATE = "dashboard_update"
    METRIC_UPDATE = "metric_update"
    ALERT_NOTIFICATION = "alert_notification"
    SYSTEM_STATUS = "system_status"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    SUBSCRIPTION_CONFIRM = "subscription_confirm"


# Request schemas


class MetricSubscriptionRequest(BaseModel):
    """Request to subscribe to specific metrics"""

    metrics: List[str] = Field(..., description="List of metric names to subscribe to")
    update_interval: Optional[int] = Field(
        30, ge=1, le=300, description="Update interval in seconds"
    )

    @validator("metrics")
    def validate_metrics(cls, v):
        if not v:
            raise ValueError("At least one metric must be specified")
        return v


class DashboardSubscriptionRequest(BaseModel):
    """Request to subscribe to dashboard updates"""

    include_trends: bool = Field(True, description="Include hourly trends data")
    include_performers: bool = Field(True, description="Include top performers data")
    include_alerts: bool = Field(True, description="Include active alerts")
    update_interval: Optional[int] = Field(
        30, ge=10, le=300, description="Update interval in seconds"
    )


class AlertSubscriptionRequest(BaseModel):
    """Request to subscribe to alert notifications"""

    severity_levels: List[AlertSeverity] = Field(
        default_factory=lambda: [AlertSeverity.HIGH, AlertSeverity.CRITICAL],
        description="Alert severity levels to receive",
    )


class CurrentDataRequest(BaseModel):
    """Request for current data"""

    data_type: str = Field(..., description="Type of data requested")
    metric_name: Optional[str] = Field(
        None, description="Specific metric name if requesting metric data"
    )
    include_history: bool = Field(False, description="Include historical data")
    history_hours: Optional[int] = Field(
        24, ge=1, le=168, description="Hours of history to include"
    )


# Response schemas


class RealtimeMetricResponse(BaseModel):
    """Response schema for real-time metric data"""

    metric_name: str
    value: float
    timestamp: datetime
    change_percentage: Optional[float] = None
    previous_value: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), Decimal: lambda v: float(v)}


class HourlyTrendPoint(BaseModel):
    """Single point in hourly trend data"""

    hour: str = Field(..., description="Hour timestamp in ISO format")
    revenue: float = Field(0.0, description="Revenue for this hour")
    orders: int = Field(0, description="Orders count for this hour")
    customers: int = Field(0, description="Unique customers for this hour")

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class TopPerformerResponse(BaseModel):
    """Response schema for top performer data"""

    id: int
    name: str
    revenue: float
    orders: int
    rank: Optional[int] = None
    change_from_previous: Optional[float] = None

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class RealtimeDashboardResponse(BaseModel):
    """Enhanced dashboard response with real-time capabilities"""

    timestamp: datetime

    # Current metrics
    revenue_today: float
    orders_today: int
    customers_today: int
    average_order_value: float

    # Growth indicators
    revenue_growth: float
    order_growth: float
    customer_growth: float

    # Performance data
    top_staff: List[TopPerformerResponse] = Field(default_factory=list)
    top_products: List[Dict[str, Any]] = Field(default_factory=list)

    # Trend data
    hourly_trends: List[HourlyTrendPoint] = Field(default_factory=list)

    # Alert information
    active_alerts: int = Field(0, description="Number of active alerts")
    critical_metrics: List[str] = Field(
        default_factory=list, description="Metrics requiring attention"
    )

    # System status
    last_updated: datetime
    update_frequency: int = Field(30, description="Update frequency in seconds")
    data_freshness: str = Field("real-time", description="Data freshness indicator")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), Decimal: lambda v: float(v)}


class AlertNotificationResponse(BaseModel):
    """Response schema for alert notifications"""

    alert_id: int
    alert_name: str
    severity: AlertSeverity
    message: str
    metric_name: str
    current_value: float
    threshold_value: float
    triggered_at: datetime
    estimated_impact: Optional[str] = None
    recommended_actions: List[str] = Field(default_factory=list)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), Decimal: lambda v: float(v)}


class WebSocketStatsResponse(BaseModel):
    """Response schema for WebSocket connection statistics"""

    total_connections: int
    dashboard_subscribers: int
    metric_subscribers: Dict[str, int] = Field(default_factory=dict)
    alert_subscribers: int
    connections_by_user: Dict[str, int] = Field(default_factory=dict)
    uptime_seconds: float
    average_latency_ms: Optional[float] = None
    message_throughput: Dict[str, int] = Field(default_factory=dict)


class SystemStatusResponse(BaseModel):
    """Response schema for system status"""

    status: str = Field(..., description="Overall system status")
    services: Dict[str, str] = Field(
        default_factory=dict, description="Status of individual services"
    )
    metrics: Dict[str, Any] = Field(default_factory=dict, description="System metrics")
    last_health_check: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# WebSocket message schemas


class WebSocketMessage(BaseModel):
    """Base WebSocket message schema"""

    type: WebSocketMessageType
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime
    message_id: str

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class SubscriptionMessage(BaseModel):
    """WebSocket subscription message"""

    type: Literal["subscribe"] = "subscribe"
    data: Dict[str, Any] = Field(
        ..., description="Subscription data including subscription_type and parameters"
    )

    @validator("data")
    def validate_subscription_data(cls, v):
        subscription_type = v.get("subscription_type")
        if not subscription_type:
            raise ValueError("subscription_type is required")

        if subscription_type not in ["dashboard", "metrics", "alerts"]:
            raise ValueError("Invalid subscription_type")

        return v


class UnsubscriptionMessage(BaseModel):
    """WebSocket unsubscription message"""

    type: Literal["unsubscribe"] = "unsubscribe"
    data: Dict[str, Any] = Field(
        ..., description="Unsubscription data including subscription_type"
    )


class HeartbeatMessage(BaseModel):
    """WebSocket heartbeat message"""

    type: Literal["heartbeat"] = "heartbeat"
    data: Dict[str, Any] = Field(default_factory=dict)


class ErrorMessage(BaseModel):
    """WebSocket error message"""

    type: Literal["error"] = "error"
    data: Dict[str, str] = Field(..., description="Error information")

    @validator("data")
    def validate_error_data(cls, v):
        if "error" not in v:
            raise ValueError("error field is required in error messages")
        return v


# Event schemas for integration


class OrderCompletedEvent(BaseModel):
    """Event schema for order completion"""

    order_id: int
    staff_id: int
    customer_id: Optional[int] = None
    total_amount: Decimal
    items_count: int
    completed_at: datetime
    table_no: Optional[int] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), Decimal: lambda v: float(v)}


class StaffActionEvent(BaseModel):
    """Event schema for staff actions"""

    staff_id: int
    action_type: str = Field(..., description="Type of action performed")
    action_data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    shift_id: Optional[int] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class SystemEvent(BaseModel):
    """Event schema for system events"""

    event_type: str
    event_data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    source_service: str
    severity: AlertSeverity = AlertSeverity.LOW

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# Dashboard widget schemas


class WidgetConfiguration(BaseModel):
    """Configuration for dashboard widgets"""

    widget_id: str
    widget_type: str = Field(
        ..., description="Type of widget (chart, metric, table, etc.)"
    )
    title: str
    position: Dict[str, int] = Field(
        ..., description="Widget position (x, y, width, height)"
    )
    refresh_interval: int = Field(
        30, ge=5, le=300, description="Refresh interval in seconds"
    )
    data_source: str = Field(..., description="Data source for the widget")
    config: Dict[str, Any] = Field(
        default_factory=dict, description="Widget-specific configuration"
    )


class DashboardLayout(BaseModel):
    """Dashboard layout configuration"""

    layout_id: str
    name: str
    description: Optional[str] = None
    widgets: List[WidgetConfiguration]
    created_by: int
    is_default: bool = False
    is_public: bool = False
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class WidgetDataResponse(BaseModel):
    """Response schema for widget data"""

    widget_id: str
    widget_type: str
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime
    cache_status: str = Field(
        "fresh", description="Cache status (fresh, cached, stale)"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# Cache and performance schemas


class CacheStatus(BaseModel):
    """Cache status information"""

    cache_key: str
    status: str = Field(..., description="Cache status (hit, miss, expired)")
    ttl_seconds: Optional[int] = None
    size_bytes: Optional[int] = None
    last_updated: Optional[datetime] = None
    hit_count: int = 0
    miss_count: int = 0

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class PerformanceMetrics(BaseModel):
    """Performance metrics for real-time system"""

    average_response_time_ms: float
    peak_response_time_ms: float
    requests_per_second: float
    active_connections: int
    memory_usage_mb: float
    cache_hit_rate: float
    error_rate: float
    uptime_seconds: float

    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
