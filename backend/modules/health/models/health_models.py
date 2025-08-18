"""
Models for health monitoring and metrics tracking.
"""

from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, JSON, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

from core.database import Base


class HealthMetric(Base):
    """Store health metrics for monitoring"""
    __tablename__ = "health_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_name = Column(String(100), nullable=False)
    metric_type = Column(String(50), nullable=False)  # gauge, counter, histogram
    value = Column(Float, nullable=False)
    unit = Column(String(20))  # ms, count, percentage, bytes
    tags = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_health_metrics_name_created', 'metric_name', 'created_at'),
        Index('idx_health_metrics_type', 'metric_type'),
    )


class SystemHealth(Base):
    """Track overall system health status"""
    __tablename__ = "system_health"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    component = Column(String(50), nullable=False)  # api, database, redis, etc.
    status = Column(String(20), nullable=False)  # healthy, degraded, unhealthy
    response_time_ms = Column(Float)
    details = Column(JSON, default={})
    last_checked = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_system_health_component', 'component'),
        Index('idx_system_health_status', 'status'),
    )


class ErrorLog(Base):
    """Track application errors for monitoring"""
    __tablename__ = "error_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    error_type = Column(String(100), nullable=False)
    error_message = Column(Text)
    stack_trace = Column(Text)
    endpoint = Column(String(200))
    method = Column(String(10))
    status_code = Column(Integer)
    user_id = Column(Integer)
    restaurant_id = Column(Integer)
    request_id = Column(String(100))
    tags = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime)
    
    __table_args__ = (
        Index('idx_error_logs_created', 'created_at'),
        Index('idx_error_logs_type', 'error_type'),
        Index('idx_error_logs_endpoint', 'endpoint'),
        Index('idx_error_logs_resolved', 'resolved'),
    )


class PerformanceMetric(Base):
    """Track API endpoint performance"""
    __tablename__ = "performance_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    endpoint = Column(String(200), nullable=False)
    method = Column(String(10), nullable=False)
    response_time_ms = Column(Float, nullable=False)
    status_code = Column(Integer)
    request_size_bytes = Column(Integer)
    response_size_bytes = Column(Integer)
    cpu_usage_percent = Column(Float)
    memory_usage_mb = Column(Float)
    db_query_count = Column(Integer)
    db_query_time_ms = Column(Float)
    cache_hits = Column(Integer, default=0)
    cache_misses = Column(Integer, default=0)
    user_id = Column(Integer)
    restaurant_id = Column(Integer)
    request_id = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_performance_endpoint_created', 'endpoint', 'created_at'),
        Index('idx_performance_method', 'method'),
        Index('idx_performance_status', 'status_code'),
    )


class Alert(Base):
    """Store system alerts"""
    __tablename__ = "alerts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_type = Column(String(50), nullable=False)  # error_rate, performance, availability
    severity = Column(String(20), nullable=False)  # critical, warning, info
    component = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    threshold_value = Column(Float)
    actual_value = Column(Float)
    triggered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime)
    acknowledged_by = Column(Integer)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime)
    metadata = Column(JSON, default={})
    
    __table_args__ = (
        Index('idx_alerts_type_triggered', 'alert_type', 'triggered_at'),
        Index('idx_alerts_severity', 'severity'),
        Index('idx_alerts_acknowledged', 'acknowledged'),
        Index('idx_alerts_resolved', 'resolved'),
    )