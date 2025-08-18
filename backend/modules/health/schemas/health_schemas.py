"""
Pydantic schemas for health monitoring endpoints.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class HealthStatus(str, Enum):
    """Health status values"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentStatus(BaseModel):
    """Status of a single component"""
    name: str
    status: HealthStatus
    response_time_ms: Optional[float] = None
    details: Optional[Dict[str, Any]] = None
    last_checked: datetime
    message: Optional[str] = None


class HealthCheckResponse(BaseModel):
    """Overall health check response"""
    status: HealthStatus
    timestamp: datetime
    version: str
    uptime_seconds: float
    components: List[ComponentStatus]
    checks_passed: int
    checks_failed: int


class DatabaseHealth(BaseModel):
    """Database health information"""
    status: HealthStatus
    connection_pool_size: int
    active_connections: int
    idle_connections: int
    response_time_ms: float
    can_connect: bool
    version: Optional[str] = None


class RedisHealth(BaseModel):
    """Redis health information"""
    status: HealthStatus
    connected_clients: int
    used_memory_mb: float
    total_memory_mb: float
    response_time_ms: float
    can_connect: bool
    version: Optional[str] = None


class MetricType(str, Enum):
    """Types of metrics"""
    GAUGE = "gauge"
    COUNTER = "counter"
    HISTOGRAM = "histogram"


class MetricData(BaseModel):
    """Single metric data point"""
    name: str
    type: MetricType
    value: float
    unit: Optional[str] = None
    tags: Dict[str, str] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PerformanceMetrics(BaseModel):
    """Performance metrics response"""
    endpoint: str
    method: str
    avg_response_time_ms: float
    p50_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    request_count: int
    error_count: int
    error_rate: float
    time_window_minutes: int = 5


class SystemMetrics(BaseModel):
    """System-wide metrics"""
    cpu_usage_percent: float
    memory_usage_mb: float
    memory_total_mb: float
    disk_usage_percent: float
    disk_free_gb: float
    active_connections: int
    request_rate_per_second: float
    error_rate_per_second: float
    average_response_time_ms: float


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AlertType(str, Enum):
    """Types of alerts"""
    ERROR_RATE = "error_rate"
    PERFORMANCE = "performance"
    AVAILABILITY = "availability"
    RESOURCE = "resource"
    SECURITY = "security"


class AlertCreate(BaseModel):
    """Create a new alert"""
    alert_type: AlertType
    severity: AlertSeverity
    component: str
    title: str
    description: Optional[str] = None
    threshold_value: Optional[float] = None
    actual_value: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AlertResponse(AlertCreate):
    """Alert response with additional fields"""
    id: str
    triggered_at: datetime
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[int] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class ErrorLogCreate(BaseModel):
    """Create error log entry"""
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    status_code: Optional[int] = None
    user_id: Optional[int] = None
    restaurant_id: Optional[int] = None
    request_id: Optional[str] = None
    tags: Dict[str, Any] = Field(default_factory=dict)


class ErrorLogResponse(ErrorLogCreate):
    """Error log response"""
    id: str
    created_at: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class ErrorSummary(BaseModel):
    """Error summary statistics"""
    total_errors: int
    unique_errors: int
    error_rate_per_hour: float
    top_errors: List[Dict[str, Any]]
    affected_endpoints: List[Dict[str, Any]]
    time_window_hours: int = 24


class MonitoringDashboard(BaseModel):
    """Complete monitoring dashboard data"""
    health: HealthCheckResponse
    system_metrics: SystemMetrics
    performance: List[PerformanceMetrics]
    recent_errors: List[ErrorLogResponse]
    active_alerts: List[AlertResponse]
    error_summary: ErrorSummary