# backend/modules/analytics/schemas/pos_analytics_schemas.py

"""
Pydantic schemas for POS analytics endpoints.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional, Any, Union
from datetime import datetime, date
from decimal import Decimal
from enum import Enum


class POSHealthStatus(str, Enum):
    """Health status for POS terminals"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    OFFLINE = "offline"


class AlertSeverity(str, Enum):
    """Alert severity levels"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class TimeRange(str, Enum):
    """Predefined time ranges for analytics"""

    LAST_HOUR = "last_hour"
    LAST_24_HOURS = "last_24_hours"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"
    CUSTOM = "custom"


class POSProviderSummary(BaseModel):
    """Summary metrics for a POS provider"""

    provider_id: int
    provider_name: str
    provider_code: str
    is_active: bool

    # Terminal stats
    total_terminals: int
    active_terminals: int
    offline_terminals: int

    # Transaction metrics (current period)
    total_transactions: int
    successful_transactions: int
    failed_transactions: int
    transaction_success_rate: float
    total_transaction_value: Decimal

    # Sync metrics
    total_syncs: int
    sync_success_rate: float
    average_sync_time_ms: float

    # Webhook metrics
    total_webhooks: int
    webhook_success_rate: float

    # Health
    overall_health_status: POSHealthStatus
    uptime_percentage: float
    active_alerts: int


class POSTerminalSummary(BaseModel):
    """Summary metrics for a POS terminal"""

    terminal_id: str
    terminal_name: Optional[str]
    terminal_location: Optional[str]
    provider_id: int
    provider_name: str

    # Status
    is_online: bool
    health_status: POSHealthStatus
    last_seen_at: datetime
    offline_duration_minutes: Optional[int]

    # Recent metrics (24h)
    recent_transactions: int
    recent_errors: int
    recent_sync_failures: int
    recent_success_rate: float

    # Performance
    average_response_time_ms: Optional[float]

    # Alerts
    has_active_alerts: bool
    alert_count: int


class POSTransactionTrend(BaseModel):
    """Transaction trend data point"""

    timestamp: datetime
    transaction_count: int
    transaction_value: Decimal
    success_rate: float
    average_value: Decimal


class POSSyncMetrics(BaseModel):
    """Sync performance metrics"""

    total_syncs: int
    successful_syncs: int
    failed_syncs: int
    pending_syncs: int
    success_rate: float
    average_sync_time_ms: float

    # Breakdown by status
    sync_status_breakdown: Dict[str, int]

    # Recent failures
    recent_failures: List[Dict[str, Any]]


class POSWebhookMetrics(BaseModel):
    """Webhook processing metrics"""

    total_webhooks: int
    successful_webhooks: int
    failed_webhooks: int
    pending_webhooks: int
    success_rate: float
    average_processing_time_ms: float

    # Breakdown by event type
    event_type_breakdown: Dict[str, int]

    # Recent failures
    recent_failures: List[Dict[str, Any]]


class POSErrorAnalysis(BaseModel):
    """Error analysis for POS operations"""

    total_errors: int
    error_rate: float

    # Error breakdown
    error_types: List[Dict[str, Union[str, int, float]]]  # [{type, count, percentage}]

    # Trending errors
    trending_errors: List[Dict[str, Any]]

    # Affected terminals
    affected_terminals: List[Dict[str, Union[str, int]]]  # [{terminal_id, error_count}]


class POSPerformanceMetrics(BaseModel):
    """Performance metrics for POS operations"""

    # Response times
    response_time_p50: float
    response_time_p95: float
    response_time_p99: float
    average_response_time: float

    # Throughput
    transactions_per_minute: float
    syncs_per_minute: float
    webhooks_per_minute: float

    # Capacity
    peak_load_percentage: float
    capacity_utilization: float


class POSAlert(BaseModel):
    """POS analytics alert"""

    alert_id: str
    alert_type: str
    severity: AlertSeverity

    # Source
    provider_id: Optional[int]
    provider_name: Optional[str]
    terminal_id: Optional[str]

    # Alert details
    title: str
    description: str
    metric_value: Optional[float]
    threshold_value: Optional[float]

    # Status
    is_active: bool
    acknowledged: bool
    acknowledged_by: Optional[str]
    acknowledged_at: Optional[datetime]

    # Timestamps
    created_at: datetime
    resolved_at: Optional[datetime]

    # Context
    context_data: Dict[str, Any]


class POSDashboardRequest(BaseModel):
    """Request for POS analytics dashboard data"""

    time_range: TimeRange = Field(TimeRange.LAST_24_HOURS)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    provider_ids: Optional[List[int]] = None
    terminal_ids: Optional[List[str]] = None
    include_offline: bool = Field(True)

    @validator("start_date", "end_date")
    def validate_dates(cls, v, values):
        if values.get("time_range") == TimeRange.CUSTOM and not v:
            raise ValueError("start_date and end_date required for custom time range")
        return v


class POSDashboardResponse(BaseModel):
    """Response for POS analytics dashboard"""

    # Overview metrics
    total_providers: int
    active_providers: int
    total_terminals: int
    online_terminals: int

    # Transaction summary
    total_transactions: int
    successful_transactions: int
    transaction_success_rate: float
    total_transaction_value: Decimal
    average_transaction_value: Decimal

    # Performance summary
    overall_uptime: float
    average_sync_time_ms: float
    average_webhook_time_ms: float

    # Provider breakdown
    providers: List[POSProviderSummary]

    # Terminal health
    healthy_terminals: int
    degraded_terminals: int
    critical_terminals: int
    offline_terminals: int

    # Trends
    transaction_trends: List[POSTransactionTrend]

    # Active alerts
    active_alerts: List[POSAlert]

    # Timestamp
    generated_at: datetime
    time_range: str


class POSProviderDetailsRequest(BaseModel):
    """Request for detailed POS provider analytics"""

    provider_id: int
    time_range: TimeRange = Field(TimeRange.LAST_24_HOURS)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    include_terminals: bool = Field(True)
    include_errors: bool = Field(True)


class POSProviderDetailsResponse(BaseModel):
    """Response for detailed POS provider analytics"""

    provider: POSProviderSummary

    # Detailed metrics
    sync_metrics: POSSyncMetrics
    webhook_metrics: POSWebhookMetrics
    error_analysis: POSErrorAnalysis
    performance_metrics: POSPerformanceMetrics

    # Terminal breakdown
    terminals: Optional[List[POSTerminalSummary]]

    # Historical trends
    hourly_trends: List[Dict[str, Any]]
    daily_trends: List[Dict[str, Any]]

    # Recent events
    recent_transactions: List[Dict[str, Any]]
    recent_errors: List[Dict[str, Any]]

    # Generated metadata
    generated_at: datetime
    time_range: str


class POSTerminalDetailsRequest(BaseModel):
    """Request for detailed terminal analytics"""

    terminal_id: str
    time_range: TimeRange = Field(TimeRange.LAST_24_HOURS)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class POSTerminalDetailsResponse(BaseModel):
    """Response for detailed terminal analytics"""

    terminal: POSTerminalSummary

    # Detailed metrics
    transaction_metrics: Dict[str, Any]
    sync_metrics: POSSyncMetrics
    error_analysis: POSErrorAnalysis
    performance_metrics: POSPerformanceMetrics

    # Historical data
    hourly_trends: List[Dict[str, Any]]
    daily_trends: List[Dict[str, Any]]

    # Recent activity
    recent_transactions: List[Dict[str, Any]]
    recent_syncs: List[Dict[str, Any]]
    recent_errors: List[Dict[str, Any]]

    # Alerts
    active_alerts: List[POSAlert]
    alert_history: List[POSAlert]

    # Generated metadata
    generated_at: datetime
    time_range: str


class POSComparisonRequest(BaseModel):
    """Request for comparing POS providers"""

    provider_ids: List[int] = Field(..., min_items=2, max_items=5)
    time_range: TimeRange = Field(TimeRange.LAST_7_DAYS)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    metrics: List[str] = Field(
        default=["transactions", "success_rate", "sync_performance", "uptime"]
    )


class POSComparisonResponse(BaseModel):
    """Response for POS provider comparison"""

    providers: List[POSProviderSummary]

    # Comparison metrics
    comparison_data: Dict[str, List[Dict[str, Any]]]

    # Rankings
    rankings: Dict[str, List[Dict[str, Any]]]  # metric -> [{provider_id, value, rank}]

    # Insights
    insights: List[str]

    # Generated metadata
    generated_at: datetime
    time_range: str


class POSExportRequest(BaseModel):
    """Request for exporting POS analytics data"""

    report_type: str = Field(..., pattern="^(summary|detailed|transactions|errors)$")
    format: str = Field(..., pattern="^(csv|xlsx|pdf)$")
    time_range: TimeRange = Field(TimeRange.LAST_7_DAYS)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    provider_ids: Optional[List[int]] = None
    terminal_ids: Optional[List[str]] = None
    include_charts: bool = Field(False)  # For PDF exports
