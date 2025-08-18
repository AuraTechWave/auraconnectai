"""
Health monitoring API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timedelta

from core.database import get_db
from core.auth import get_current_user
from modules.auth.models import User
from modules.auth.permissions import Permission, check_permission

from ..services.health_service import HealthService
from ..schemas.health_schemas import (
    HealthCheckResponse, SystemMetrics, AlertCreate, AlertResponse,
    ErrorLogCreate, ErrorLogResponse, ErrorSummary, MonitoringDashboard,
    PerformanceMetrics
)
from ..models.health_models import Alert, ErrorLog, PerformanceMetric

router = APIRouter(prefix="/api/v1/health", tags=["Health Monitoring"])


@router.get("/", response_model=HealthCheckResponse)
async def health_check(
    db: Session = Depends(get_db)
):
    """
    Basic health check endpoint.
    
    This endpoint is publicly accessible and returns the overall system health.
    """
    service = HealthService(db)
    return await service.check_health()


@router.get("/detailed", response_model=HealthCheckResponse)
async def detailed_health_check(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Detailed health check with component information.
    
    Requires authentication.
    """
    check_permission(current_user, Permission.SYSTEM_ADMIN)
    service = HealthService(db)
    return await service.check_health()


@router.get("/metrics", response_model=SystemMetrics)
async def get_system_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get current system metrics.
    
    Returns CPU, memory, disk usage, and performance metrics.
    """
    check_permission(current_user, Permission.SYSTEM_ADMIN)
    service = HealthService(db)
    return service.get_system_metrics()


@router.get("/performance", response_model=List[PerformanceMetrics])
async def get_performance_metrics(
    time_window_minutes: int = Query(5, ge=1, le=60),
    endpoint: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get performance metrics for API endpoints.
    
    Returns response times and error rates aggregated by endpoint.
    """
    check_permission(current_user, Permission.SYSTEM_ADMIN)
    
    # Build query - use database-agnostic approach
    # First get basic aggregates
    query = db.query(
        PerformanceMetric.endpoint,
        PerformanceMetric.method,
        func.avg(PerformanceMetric.response_time_ms).label("avg_response_time"),
        func.min(PerformanceMetric.response_time_ms).label("min_response_time"),
        func.max(PerformanceMetric.response_time_ms).label("max_response_time"),
        func.count(PerformanceMetric.id).label("request_count"),
        func.count(PerformanceMetric.id).filter(
            PerformanceMetric.status_code >= 400
        ).label("error_count")
    ).filter(
        PerformanceMetric.created_at >= datetime.utcnow() - timedelta(minutes=time_window_minutes)
    )
    
    if endpoint:
        query = query.filter(PerformanceMetric.endpoint == endpoint)
    
    results = query.group_by(
        PerformanceMetric.endpoint,
        PerformanceMetric.method
    ).all()
    
    metrics = []
    for result in results:
        error_rate = (result.error_count / result.request_count * 100) if result.request_count > 0 else 0
        
        # For percentiles, we need to fetch all response times for this endpoint
        # This is less efficient but database-agnostic
        response_times = db.query(PerformanceMetric.response_time_ms).filter(
            PerformanceMetric.endpoint == result.endpoint,
            PerformanceMetric.method == result.method,
            PerformanceMetric.created_at >= datetime.utcnow() - timedelta(minutes=time_window_minutes)
        ).order_by(PerformanceMetric.response_time_ms).all()
        
        # Calculate percentiles in Python
        response_times_list = [rt[0] for rt in response_times]
        p50 = _calculate_percentile(response_times_list, 0.5)
        p95 = _calculate_percentile(response_times_list, 0.95)
        p99 = _calculate_percentile(response_times_list, 0.99)
        
        metrics.append(PerformanceMetrics(
            endpoint=result.endpoint,
            method=result.method,
            avg_response_time_ms=result.avg_response_time or 0,
            p50_response_time_ms=p50,
            p95_response_time_ms=p95,
            p99_response_time_ms=p99,
            request_count=result.request_count,
            error_count=result.error_count,
            error_rate=error_rate,
            time_window_minutes=time_window_minutes
        ))
    
    return metrics


def _calculate_percentile(sorted_list: List[float], percentile: float) -> float:
    """Calculate percentile from a sorted list"""
    if not sorted_list:
        return 0.0
    
    index = int(percentile * (len(sorted_list) - 1))
    return sorted_list[index]


@router.post("/alerts", response_model=AlertResponse)
async def create_alert(
    alert_data: AlertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new system alert.
    
    Used by monitoring systems to create alerts.
    """
    check_permission(current_user, Permission.SYSTEM_ADMIN)
    service = HealthService(db)
    return service.create_alert(alert_data)


@router.get("/alerts", response_model=List[AlertResponse])
async def get_alerts(
    resolved: Optional[bool] = None,
    severity: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get system alerts.
    
    Can filter by resolved status and severity.
    """
    check_permission(current_user, Permission.SYSTEM_ADMIN)
    
    query = db.query(Alert)
    
    if resolved is not None:
        query = query.filter(Alert.resolved == resolved)
    
    if severity:
        query = query.filter(Alert.severity == severity)
    
    alerts = query.order_by(Alert.triggered_at.desc()).limit(limit).all()
    
    return [
        AlertResponse(
            id=str(alert.id),
            alert_type=alert.alert_type,
            severity=alert.severity,
            component=alert.component,
            title=alert.title,
            description=alert.description,
            threshold_value=alert.threshold_value,
            actual_value=alert.actual_value,
            metadata=alert.metadata,
            triggered_at=alert.triggered_at,
            acknowledged=alert.acknowledged,
            acknowledged_at=alert.acknowledged_at,
            acknowledged_by=alert.acknowledged_by,
            resolved=alert.resolved,
            resolved_at=alert.resolved_at
        )
        for alert in alerts
    ]


@router.put("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Acknowledge an alert.
    """
    check_permission(current_user, Permission.SYSTEM_ADMIN)
    
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.acknowledged = True
    alert.acknowledged_at = datetime.utcnow()
    alert.acknowledged_by = current_user.id
    
    db.commit()
    
    return {"message": "Alert acknowledged"}


@router.put("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Resolve an alert.
    """
    check_permission(current_user, Permission.SYSTEM_ADMIN)
    
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.resolved = True
    alert.resolved_at = datetime.utcnow()
    
    db.commit()
    
    return {"message": "Alert resolved"}


@router.post("/errors/log", status_code=201)
async def log_error(
    error_data: ErrorLogCreate,
    db: Session = Depends(get_db)
):
    """
    Log an error for monitoring.
    
    This endpoint can be called by the application to log errors.
    """
    service = HealthService(db)
    service.log_error(error_data)
    return {"message": "Error logged"}


@router.get("/errors", response_model=List[ErrorLogResponse])
async def get_errors(
    resolved: Optional[bool] = None,
    error_type: Optional[str] = None,
    endpoint: Optional[str] = None,
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get error logs.
    
    Can filter by various criteria.
    """
    check_permission(current_user, Permission.SYSTEM_ADMIN)
    
    query = db.query(ErrorLog).filter(
        ErrorLog.created_at >= datetime.utcnow() - timedelta(hours=hours)
    )
    
    if resolved is not None:
        query = query.filter(ErrorLog.resolved == resolved)
    
    if error_type:
        query = query.filter(ErrorLog.error_type == error_type)
    
    if endpoint:
        query = query.filter(ErrorLog.endpoint == endpoint)
    
    errors = query.order_by(ErrorLog.created_at.desc()).limit(limit).all()
    
    return [
        ErrorLogResponse(
            id=str(error.id),
            error_type=error.error_type,
            error_message=error.error_message,
            stack_trace=error.stack_trace,
            endpoint=error.endpoint,
            method=error.method,
            status_code=error.status_code,
            user_id=error.user_id,
            restaurant_id=error.restaurant_id,
            request_id=error.request_id,
            tags=error.tags,
            created_at=error.created_at,
            resolved=error.resolved,
            resolved_at=error.resolved_at
        )
        for error in errors
    ]


@router.get("/errors/summary", response_model=ErrorSummary)
async def get_error_summary(
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get error summary statistics.
    """
    check_permission(current_user, Permission.SYSTEM_ADMIN)
    
    time_threshold = datetime.utcnow() - timedelta(hours=hours)
    
    # Total and unique errors
    total_errors = db.query(ErrorLog).filter(
        ErrorLog.created_at >= time_threshold
    ).count()
    
    unique_errors = db.query(
        func.count(func.distinct(ErrorLog.error_type))
    ).filter(
        ErrorLog.created_at >= time_threshold
    ).scalar()
    
    # Error rate
    error_rate = total_errors / hours if hours > 0 else 0
    
    # Top errors
    top_errors = db.query(
        ErrorLog.error_type,
        func.count(ErrorLog.id).label("count")
    ).filter(
        ErrorLog.created_at >= time_threshold
    ).group_by(
        ErrorLog.error_type
    ).order_by(
        func.count(ErrorLog.id).desc()
    ).limit(10).all()
    
    # Affected endpoints
    affected_endpoints = db.query(
        ErrorLog.endpoint,
        func.count(ErrorLog.id).label("error_count")
    ).filter(
        ErrorLog.created_at >= time_threshold,
        ErrorLog.endpoint.isnot(None)
    ).group_by(
        ErrorLog.endpoint
    ).order_by(
        func.count(ErrorLog.id).desc()
    ).limit(10).all()
    
    return ErrorSummary(
        total_errors=total_errors,
        unique_errors=unique_errors,
        error_rate_per_hour=error_rate,
        top_errors=[
            {"error_type": e.error_type, "count": e.count}
            for e in top_errors
        ],
        affected_endpoints=[
            {"endpoint": e.endpoint, "error_count": e.error_count}
            for e in affected_endpoints
        ],
        time_window_hours=hours
    )


@router.get("/dashboard", response_model=MonitoringDashboard)
async def get_monitoring_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get complete monitoring dashboard data.
    
    Combines health check, metrics, performance, errors, and alerts.
    """
    check_permission(current_user, Permission.SYSTEM_ADMIN)
    
    service = HealthService(db)
    
    # Get all components
    health = await service.check_health()
    system_metrics = service.get_system_metrics()
    
    # Get performance metrics (last 5 minutes)
    performance = await get_performance_metrics(5, None, db, current_user)
    
    # Get recent errors (last hour)
    recent_errors = await get_errors(None, None, None, 1, 10, db, current_user)
    
    # Get active alerts
    active_alerts = await get_alerts(False, None, 10, db, current_user)
    
    # Get error summary (last 24 hours)
    error_summary = await get_error_summary(24, db, current_user)
    
    return MonitoringDashboard(
        health=health,
        system_metrics=system_metrics,
        performance=performance[:5],  # Top 5 endpoints
        recent_errors=recent_errors[:5],  # Last 5 errors
        active_alerts=active_alerts,
        error_summary=error_summary
    )