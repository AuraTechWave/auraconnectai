# backend/modules/analytics/routers/analytics_router.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Union
from datetime import date, datetime, timedelta
import logging

from core.database import get_db
from core.auth import get_current_user, User

from ..services.permissions_service import (
    AnalyticsPermission, PermissionsService, require_analytics_permission
)
from ..services.async_processing import (
    async_processor, TaskStatus, submit_large_report_task
)

from ..services.sales_report_service import SalesReportService
from ..services.realtime_metrics_service import realtime_metrics_service
from ..services.dashboard_widgets_service import dashboard_widgets_service
from ..schemas.analytics_schemas import (
    SalesFilterRequest, SalesSummaryResponse, SalesDetailResponse,
    StaffPerformanceResponse, ProductPerformanceResponse, PaginatedSalesResponse,
    SalesReportRequest, ReportExecutionResponse, DashboardMetricsResponse,
    ReportTemplateRequest, ReportTemplateResponse, SalesComparisonRequest,
    SalesComparisonResponse
)
from ..schemas.realtime_schemas import (
    RealtimeDashboardResponse, WidgetConfiguration, DashboardLayout
)

router = APIRouter(prefix="/analytics", tags=["Analytics & Reporting"])
logger = logging.getLogger(__name__)


@router.get("/dashboard", response_model=DashboardMetricsResponse)
async def get_dashboard_metrics(
    current_date: Optional[date] = Query(None, description="Date for dashboard metrics"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analytics_permission(AnalyticsPermission.VIEW_DASHBOARD))
):
    """
    Get dashboard metrics for sales analytics (legacy endpoint).
    
    Returns current day metrics with comparisons to previous periods,
    top performers, trends, and active alerts.
    
    Note: For real-time updates, use /analytics/realtime/dashboard endpoints
    """
    try:
        service = SalesReportService(db)
        return service.get_dashboard_metrics(current_date)
    
    except Exception as e:
        logger.error(f"Error getting dashboard metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dashboard metrics"
        )


@router.get("/dashboard/realtime", response_model=RealtimeDashboardResponse)
async def get_realtime_dashboard_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analytics_permission(AnalyticsPermission.VIEW_DASHBOARD))
):
    """
    Get real-time dashboard metrics with enhanced features.
    
    Returns comprehensive real-time metrics including:
    - Current revenue, orders, customers
    - Growth indicators with live updates
    - Top performers with rankings
    - Hourly trends for visualization
    - Active alerts and critical metrics
    """
    try:
        snapshot = await realtime_metrics_service.get_current_dashboard_snapshot()
        
        return RealtimeDashboardResponse(
            timestamp=snapshot.timestamp,
            revenue_today=float(snapshot.revenue_today),
            orders_today=snapshot.orders_today,
            customers_today=snapshot.customers_today,
            average_order_value=float(snapshot.average_order_value),
            revenue_growth=snapshot.revenue_growth,
            order_growth=snapshot.order_growth,
            customer_growth=snapshot.customer_growth,
            top_staff=[
                {
                    "id": staff["id"],
                    "name": staff["name"],
                    "revenue": staff["revenue"],
                    "orders": staff["orders"],
                    "rank": idx + 1
                }
                for idx, staff in enumerate(snapshot.top_staff)
            ],
            top_products=snapshot.top_products,
            hourly_trends=[
                {
                    "hour": trend["hour"],
                    "revenue": trend["revenue"],
                    "orders": trend["orders"],
                    "customers": trend["customers"]
                }
                for trend in snapshot.hourly_trends
            ],
            active_alerts=snapshot.active_alerts,
            critical_metrics=snapshot.critical_metrics,
            last_updated=snapshot.timestamp,
            update_frequency=30,
            data_freshness="real-time"
        )
    
    except Exception as e:
        logger.error(f"Error getting real-time dashboard metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve real-time dashboard metrics"
        )


@router.post("/reports/sales-summary", response_model=SalesSummaryResponse)
async def generate_sales_summary(
    filters: SalesFilterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analytics_permission(AnalyticsPermission.VIEW_SALES_REPORTS))
):
    """
    Generate a comprehensive sales summary report.
    
    Provides aggregated metrics including revenue, orders, customers,
    growth comparisons, and key performance indicators.
    """
    try:
        service = SalesReportService(db)
        return service.generate_sales_summary(filters)
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error generating sales summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate sales summary"
        )


@router.post("/reports/sales-detailed", response_model=PaginatedSalesResponse)
async def generate_detailed_sales_report(
    filters: SalesFilterRequest,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=1000, description="Items per page"),
    sort_by: str = Query("total_revenue", description="Field to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analytics_permission(AnalyticsPermission.VIEW_SALES_REPORTS))
):
    """
    Generate detailed sales report with filtering and pagination.
    
    Returns detailed breakdown of sales data with support for various
    filters including date ranges, staff, products, and categories.
    """
    try:
        service = SalesReportService(db)
        return service.generate_detailed_sales_report(
            filters, page, per_page, sort_by, sort_order
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error generating detailed sales report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate detailed sales report"
        )


@router.post("/reports/staff-performance", response_model=List[StaffPerformanceResponse])
async def generate_staff_performance_report(
    filters: SalesFilterRequest,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analytics_permission(AnalyticsPermission.VIEW_STAFF_REPORTS))
):
    """
    Generate staff performance analytics report.
    
    Provides detailed performance metrics for staff members including
    revenue generated, orders handled, efficiency metrics, and rankings.
    """
    try:
        service = SalesReportService(db)
        return service.generate_staff_performance_report(filters, page, per_page)
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error generating staff performance report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate staff performance report"
        )


@router.post("/reports/product-performance", response_model=List[ProductPerformanceResponse])
async def generate_product_performance_report(
    filters: SalesFilterRequest,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analytics_permission(AnalyticsPermission.VIEW_PRODUCT_REPORTS))
):
    """
    Generate product performance analytics report.
    
    Provides detailed performance metrics for products including
    sales quantities, revenue, popularity rankings, and market share.
    """
    try:
        service = SalesReportService(db)
        return service.generate_product_performance_report(filters, page, per_page)
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error generating product performance report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate product performance report"
        )


@router.get("/reports/quick-stats")
async def get_quick_stats(
    date_from: Optional[date] = Query(None, description="Start date"),
    date_to: Optional[date] = Query(None, description="End date"),
    staff_id: Optional[int] = Query(None, description="Filter by staff member"),
    category_id: Optional[int] = Query(None, description="Filter by category"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analytics_permission(AnalyticsPermission.VIEW_SALES_REPORTS))
):
    """
    Get quick statistics for the specified period and filters.
    
    Returns key metrics in a simplified format for dashboard widgets
    and quick reference displays.
    """
    try:
        # Build filters
        filters = SalesFilterRequest(
            date_from=date_from,
            date_to=date_to,
            staff_ids=[staff_id] if staff_id else None,
            category_ids=[category_id] if category_id else None
        )
        
        service = SalesReportService(db)
        summary = service.generate_sales_summary(filters)
        
        # Return simplified stats
        return {
            "period": {
                "start": summary.period_start,
                "end": summary.period_end
            },
            "metrics": {
                "total_revenue": float(summary.total_revenue),
                "total_orders": summary.total_orders,
                "average_order_value": float(summary.average_order_value),
                "unique_customers": summary.unique_customers
            },
            "growth": {
                "revenue_growth": float(summary.revenue_growth) if summary.revenue_growth else None,
                "order_growth": float(summary.order_growth) if summary.order_growth else None
            }
        }
    
    except Exception as e:
        logger.error(f"Error getting quick stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve quick statistics"
        )


@router.get("/reports/top-performers")
async def get_top_performers(
    metric: str = Query("revenue", pattern="^(revenue|orders|efficiency)$", description="Performance metric"),
    period_days: int = Query(7, ge=1, le=365, description="Period in days"),
    limit: int = Query(10, ge=1, le=50, description="Number of top performers"),
    entity_type: str = Query("staff", pattern="^(staff|product|category)$", description="Entity type"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analytics_permission(AnalyticsPermission.VIEW_SALES_REPORTS))
):
    """
    Get top performers for the specified metric and period.
    
    Returns ranked list of top performing entities (staff, products, or categories)
    based on the selected performance metric.
    """
    try:
        # Calculate date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=period_days)
        
        filters = SalesFilterRequest(
            date_from=start_date,
            date_to=end_date
        )
        
        service = SalesReportService(db)
        
        if entity_type == "staff":
            performers = service.generate_staff_performance_report(
                filters, page=1, per_page=limit
            )
            return [
                {
                    "id": p.staff_id,
                    "name": p.staff_name,
                    "metric_value": float(p.total_revenue_generated) if metric == "revenue" 
                                  else p.total_orders_handled,
                    "rank": p.revenue_rank if metric == "revenue" else p.order_count_rank
                }
                for p in performers
            ]
        
        elif entity_type == "product":
            performers = service.generate_product_performance_report(
                filters, page=1, per_page=limit
            )
            return [
                {
                    "id": p.product_id,
                    "name": p.product_name,
                    "metric_value": float(p.revenue_generated) if metric == "revenue"
                                  else p.quantity_sold,
                    "rank": p.revenue_rank if metric == "revenue" else p.popularity_rank
                }
                for p in performers
            ]
        
        else:
            # Category performance would be implemented similarly
            return []
    
    except Exception as e:
        logger.error(f"Error getting top performers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve top performers"
        )


@router.get("/reports/trends")
async def get_trends(
    metric: str = Query("revenue", pattern="^(revenue|orders|customers)$", description="Trend metric"),
    period_days: int = Query(30, ge=7, le=365, description="Period in days"),
    granularity: str = Query("daily", pattern="^(hourly|daily|weekly)$", description="Data granularity"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analytics_permission(AnalyticsPermission.VIEW_SALES_REPORTS))
):
    """
    Get trend data for the specified metric and period.
    
    Returns time series data for visualization in charts and graphs.
    Supports different granularities and metrics.
    """
    try:
        # Use optimized trend service for better performance
        from ..services.trend_service import TrendService
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=period_days)
        
        trend_service = TrendService(db)
        
        # Get trend data using optimized snapshots
        if metric == "revenue":
            trend_points = trend_service.get_revenue_trend(
                start_date, end_date, granularity
            )
        elif metric == "orders":
            trend_points = trend_service.get_order_trend(
                start_date, end_date, granularity
            )
        elif metric == "customers":
            trend_points = trend_service.get_customer_trend(
                start_date, end_date, granularity
            )
        else:
            trend_points = []
        
        # Format for API response
        trend_data = [
            {
                "date": point.date.isoformat(),
                "value": point.value,
                "change_percentage": point.change_percentage
            }
            for point in trend_points
        ]
        
        # Get trend statistics
        trend_stats = trend_service.get_trend_statistics(trend_points)
        
        return {
            "metric": metric,
            "period": {
                "start": start_date,
                "end": end_date,
                "days": period_days
            },
            "granularity": granularity,
            "data": trend_data,
            "statistics": trend_stats
        }
    
    except Exception as e:
        logger.error(f"Error getting trends: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve trend data"
        )


@router.get("/health")
async def health_check():
    """
    Health check endpoint for the analytics service.
    """
    return {
        "status": "healthy",
        "service": "analytics",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }


# Export endpoints with full implementation
@router.post("/export/csv")
async def export_to_csv(
    request: SalesReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analytics_permission(AnalyticsPermission.EXPORT_REPORTS))
):
    """
    Export sales report to CSV format.
    
    Supports all report types: sales_summary, sales_detailed, 
    staff_performance, and product_performance.
    """
    try:
        from ..services.export_service import ExportService
        export_service = ExportService(db)
        
        return await export_service.export_sales_report(
            request=request,
            format_type="csv",
            executed_by=current_user["id"]
        )
    
    except Exception as e:
        logger.error(f"Error exporting CSV: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export CSV report"
        )


@router.post("/export/pdf")
async def export_to_pdf(
    request: SalesReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analytics_permission(AnalyticsPermission.EXPORT_REPORTS))
):
    """
    Export sales report to PDF format.
    
    Creates a professional PDF report with tables, charts, and formatting.
    Requires ReportLab library: pip install reportlab
    """
    try:
        from ..services.export_service import ExportService
        export_service = ExportService(db)
        
        return await export_service.export_sales_report(
            request=request,
            format_type="pdf",
            executed_by=current_user["id"]
        )
    
    except Exception as e:
        logger.error(f"Error exporting PDF: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export PDF report"
        )


@router.post("/export/excel")
async def export_to_excel(
    request: SalesReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analytics_permission(AnalyticsPermission.EXPORT_REPORTS))
):
    """
    Export sales report to Excel format.
    
    Creates a formatted Excel workbook with styling, formulas, and charts.
    Requires OpenPyXL library: pip install openpyxl
    """
    try:
        from ..services.export_service import ExportService
        export_service = ExportService(db)
        
        return await export_service.export_sales_report(
            request=request,
            format_type="xlsx",
            executed_by=current_user["id"]
        )
    
    except Exception as e:
        logger.error(f"Error exporting Excel: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export Excel report"
        )


# Alerting endpoints
@router.post("/alerts/rules")
async def create_alert_rule(
    name: str,
    description: str,
    metric_name: str,
    condition_type: str,
    threshold_value: float,
    evaluation_period: str,
    notification_channels: List[str],
    notification_recipients: List[str],
    comparison_period: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new alert rule for sales analytics.
    
    Monitor metrics and trigger notifications when conditions are met.
    """
    try:
        from ..services.alerting_service import AlertingService
        
        alerting_service = AlertingService(db)
        
        rule = alerting_service.create_alert_rule(
            name=name,
            description=description,
            metric_name=metric_name,
            condition_type=condition_type,
            threshold_value=Decimal(str(threshold_value)),
            evaluation_period=evaluation_period,
            notification_channels=notification_channels,
            notification_recipients=notification_recipients,
            created_by=current_user["id"],
            comparison_period=comparison_period
        )
        
        return {
            "success": True,
            "rule_id": rule.id,
            "rule_name": rule.name,
            "message": "Alert rule created successfully"
        }
    
    except Exception as e:
        logger.error(f"Error creating alert rule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create alert rule"
        )


@router.get("/alerts/rules")
async def get_alert_rules(
    include_inactive: bool = Query(False, description="Include inactive rules"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all alert rules for the current user.
    """
    try:
        from ..services.alerting_service import AlertingService
        
        alerting_service = AlertingService(db)
        rules = alerting_service.get_alert_rules(
            include_inactive=include_inactive,
            created_by=current_user["id"]
        )
        
        return [
            {
                "id": rule.id,
                "name": rule.name,
                "description": rule.description,
                "metric_name": rule.metric_name,
                "condition_type": rule.condition_type,
                "threshold_value": float(rule.threshold_value),
                "evaluation_period": rule.evaluation_period,
                "is_active": rule.is_active,
                "trigger_count": rule.trigger_count,
                "last_triggered_at": rule.last_triggered_at,
                "created_at": rule.created_at
            }
            for rule in rules
        ]
    
    except Exception as e:
        logger.error(f"Error getting alert rules: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve alert rules"
        )


@router.post("/alerts/evaluate")
async def evaluate_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manually trigger evaluation of all active alert rules.
    """
    try:
        from ..services.alerting_service import AlertingService
        
        alerting_service = AlertingService(db)
        results = await alerting_service.evaluate_all_alerts()
        
        return results
    
    except Exception as e:
        logger.error(f"Error evaluating alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to evaluate alerts"
        )


@router.post("/alerts/rules/{rule_id}/test")
async def test_alert_rule(
    rule_id: int,
    test_value: Optional[float] = Query(None, description="Test value to evaluate"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Test an alert rule without triggering notifications.
    """
    try:
        from ..services.alerting_service import AlertingService
        from ..models.analytics_models import AlertRule
        
        # Get the rule
        rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
        if not rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert rule not found"
            )
        
        alerting_service = AlertingService(db)
        result = await alerting_service.test_alert_rule(rule, test_value)
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing alert rule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to test alert rule"
        )


@router.get("/alerts/history")
async def get_alert_history(
    rule_id: Optional[int] = Query(None, description="Filter by rule ID"),
    days_back: int = Query(30, ge=1, le=365, description="Days of history"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get alert trigger history.
    """
    try:
        from ..services.alerting_service import AlertingService
        
        alerting_service = AlertingService(db)
        history = await alerting_service.get_alert_history(rule_id, days_back)
        
        return {
            "history": history,
            "total_alerts": len(history),
            "period_days": days_back
        }
    
    except Exception as e:
        logger.error(f"Error getting alert history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve alert history"
        )


# Async processing endpoints
@router.post("/async/large-report")
async def submit_large_report(
    filters: SalesFilterRequest,
    limit: int = Query(50000, ge=1000, le=100000, description="Maximum records to include"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analytics_permission(AnalyticsPermission.VIEW_SALES_REPORTS))
):
    """
    Submit a large report generation task for async processing.
    
    Use this endpoint for reports that may take a long time to generate.
    Returns a task ID that can be used to check progress.
    """
    try:
        # Apply data access filters based on permissions
        access_filters = PermissionsService.get_data_access_filters(current_user)
        
        # Merge with user filters
        filter_dict = filters.dict()
        if "staff_ids" in access_filters:
            filter_dict["staff_ids"] = access_filters["staff_ids"]
        
        task_id = await submit_large_report_task(
            filters=filter_dict,
            user_id=current_user["id"],
            limit=limit
        )
        
        return {
            "success": True,
            "task_id": task_id,
            "message": "Large report task submitted successfully",
            "estimated_time": "2-10 minutes depending on data size"
        }
    
    except Exception as e:
        logger.error(f"Error submitting large report task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit large report task"
        )


@router.get("/async/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get the status of an async task.
    """
    try:
        task = async_processor.get_task_status(task_id)
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        # Check if user can access this task
        if task.created_by != current_user["id"] and not PermissionsService.has_permission(
            current_user, AnalyticsPermission.ADMIN_ANALYTICS
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this task"
            )
        
        return {
            "task_id": task.id,
            "task_type": task.task_type,
            "status": task.status.value,
            "progress": task.progress,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "result": task.result,
            "error": task.error
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve task status"
        )


@router.get("/async/tasks")
async def get_user_tasks(
    status_filter: Optional[TaskStatus] = Query(None, description="Filter by task status"),
    current_user: User = Depends(get_current_user)
):
    """
    Get all async tasks for the current user.
    """
    try:
        tasks = async_processor.get_user_tasks(
            user_id=current_user["id"],
            status_filter=status_filter
        )
        
        return {
            "tasks": [
                {
                    "task_id": task.id,
                    "task_type": task.task_type,
                    "status": task.status.value,
                    "progress": task.progress,
                    "created_at": task.created_at,
                    "completed_at": task.completed_at,
                    "error": task.error
                }
                for task in tasks
            ],
            "total_tasks": len(tasks)
        }
    
    except Exception as e:
        logger.error(f"Error getting user tasks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user tasks"
        )


@router.delete("/async/tasks/{task_id}")
async def cancel_task(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Cancel a pending or running async task.
    """
    try:
        task = async_processor.get_task_status(task_id)
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        # Check if user can cancel this task
        if task.created_by != current_user["id"] and not PermissionsService.has_permission(
            current_user, AnalyticsPermission.ADMIN_ANALYTICS
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to cancel this task"
            )
        
        success = async_processor.cancel_task(task_id)
        
        if success:
            return {
                "success": True,
                "message": "Task cancelled successfully"
            }
        else:
            return {
                "success": False,
                "message": "Task cannot be cancelled (already completed or failed)"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel task"
        )


@router.get("/async/queue-status")
async def get_queue_status(
    current_user: User = Depends(require_analytics_permission(AnalyticsPermission.ADMIN_ANALYTICS))
):
    """
    Get overall async queue status (admin only).
    """
    try:
        status = async_processor.get_queue_status()
        return status
    
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve queue status"
        )


# Permissions endpoints
@router.get("/permissions/summary")
async def get_permissions_summary(
    current_user: User = Depends(get_current_user)
):
    """
    Get summary of current user's analytics permissions.
    """
    try:
        from ..services.permissions_service import get_permission_summary
        
        summary = get_permission_summary(current_user)
        return summary
    
    except Exception as e:
        logger.error(f"Error getting permissions summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve permissions summary"
        )


# Dashboard widgets endpoints
@router.post("/widgets/data")
async def get_widget_data(
    widget_config: WidgetConfiguration,
    force_refresh: bool = Query(False, description="Force refresh widget data"),
    current_user: User = Depends(require_analytics_permission(AnalyticsPermission.VIEW_DASHBOARD))
):
    """
    Get data for a specific dashboard widget
    """
    try:
        widget_response = await dashboard_widgets_service.get_widget_data(
            widget_config, force_refresh
        )
        
        return {
            "success": True,
            "data": widget_response.dict(),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting widget data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve widget data"
        )


@router.post("/dashboard/layout/data")
async def get_dashboard_layout_data(
    layout: DashboardLayout,
    force_refresh: bool = Query(False, description="Force refresh all widget data"),
    current_user: User = Depends(require_analytics_permission(AnalyticsPermission.VIEW_DASHBOARD))
):
    """
    Get data for all widgets in a dashboard layout
    """
    try:
        layout_data = await dashboard_widgets_service.get_dashboard_layout_data(
            layout, force_refresh
        )
        
        return {
            "success": True,
            "layout_id": layout.layout_id,
            "widgets": {
                widget_id: widget_response.dict() 
                for widget_id, widget_response in layout_data.items()
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting dashboard layout data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dashboard layout data"
        )


@router.get("/dashboard/layout/default")
async def get_default_dashboard_layout(
    current_user: User = Depends(require_analytics_permission(AnalyticsPermission.VIEW_DASHBOARD))
):
    """
    Get default dashboard layout for the current user
    """
    try:
        layout = await dashboard_widgets_service.create_default_dashboard_layout(
            current_user["id"]
        )
        
        return {
            "success": True,
            "layout": layout.dict(),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error creating default dashboard layout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create default dashboard layout"
        )


@router.delete("/widgets/cache")
async def invalidate_widget_cache(
    widget_id: Optional[str] = Query(None, description="Specific widget ID to invalidate"),
    current_user: User = Depends(require_analytics_permission(AnalyticsPermission.ADMIN_ANALYTICS))
):
    """
    Invalidate widget cache (admin only)
    """
    try:
        dashboard_widgets_service.invalidate_widget_cache(widget_id)
        
        return {
            "success": True,
            "message": f"Widget cache invalidated for: {widget_id or 'all widgets'}",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error invalidating widget cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invalidate widget cache"
        )