# backend/modules/analytics/routers/analytics_router.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Union
from datetime import date, datetime
import logging

from backend.core.database import get_db
from backend.core.auth import get_current_staff_user
from backend.core.exceptions import ValidationError, NotFoundError, PermissionError

from ..services.sales_report_service import SalesReportService
from ..schemas.analytics_schemas import (
    SalesFilterRequest, SalesSummaryResponse, SalesDetailResponse,
    StaffPerformanceResponse, ProductPerformanceResponse, PaginatedSalesResponse,
    SalesReportRequest, ReportExecutionResponse, DashboardMetricsResponse,
    ReportTemplateRequest, ReportTemplateResponse, SalesComparisonRequest,
    SalesComparisonResponse
)

router = APIRouter(prefix="/analytics", tags=["Analytics & Reporting"])
logger = logging.getLogger(__name__)


@router.get("/dashboard", response_model=DashboardMetricsResponse)
async def get_dashboard_metrics(
    current_date: Optional[date] = Query(None, description="Date for dashboard metrics"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_staff_user)
):
    """
    Get real-time dashboard metrics for sales analytics.
    
    Returns current day metrics with comparisons to previous periods,
    top performers, trends, and active alerts.
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


@router.post("/reports/sales-summary", response_model=SalesSummaryResponse)
async def generate_sales_summary(
    filters: SalesFilterRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_staff_user)
):
    """
    Generate a comprehensive sales summary report.
    
    Provides aggregated metrics including revenue, orders, customers,
    growth comparisons, and key performance indicators.
    """
    try:
        service = SalesReportService(db)
        return service.generate_sales_summary(filters)
    
    except ValidationError as e:
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
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_staff_user)
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
    
    except ValidationError as e:
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
    current_user: dict = Depends(get_current_staff_user)
):
    """
    Generate staff performance analytics report.
    
    Provides detailed performance metrics for staff members including
    revenue generated, orders handled, efficiency metrics, and rankings.
    """
    try:
        service = SalesReportService(db)
        return service.generate_staff_performance_report(filters, page, per_page)
    
    except ValidationError as e:
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
    current_user: dict = Depends(get_current_staff_user)
):
    """
    Generate product performance analytics report.
    
    Provides detailed performance metrics for products including
    sales quantities, revenue, popularity rankings, and market share.
    """
    try:
        service = SalesReportService(db)
        return service.generate_product_performance_report(filters, page, per_page)
    
    except ValidationError as e:
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
    current_user: dict = Depends(get_current_staff_user)
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
    metric: str = Query("revenue", regex="^(revenue|orders|efficiency)$", description="Performance metric"),
    period_days: int = Query(7, ge=1, le=365, description="Period in days"),
    limit: int = Query(10, ge=1, le=50, description="Number of top performers"),
    entity_type: str = Query("staff", regex="^(staff|product|category)$", description="Entity type"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_staff_user)
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
    metric: str = Query("revenue", regex="^(revenue|orders|customers)$", description="Trend metric"),
    period_days: int = Query(30, ge=7, le=365, description="Period in days"),
    granularity: str = Query("daily", regex="^(hourly|daily|weekly)$", description="Data granularity"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_staff_user)
):
    """
    Get trend data for the specified metric and period.
    
    Returns time series data for visualization in charts and graphs.
    Supports different granularities and metrics.
    """
    try:
        # This would implement trend calculation logic
        # For now, return a placeholder structure
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=period_days)
        
        # Generate mock trend data (would be replaced with actual calculation)
        trend_data = []
        
        current_date = start_date
        while current_date <= end_date:
            # Get data for this period
            filters = SalesFilterRequest(
                date_from=current_date,
                date_to=current_date
            )
            
            service = SalesReportService(db)
            day_summary = service.generate_sales_summary(filters)
            
            value = 0
            if metric == "revenue":
                value = float(day_summary.total_revenue)
            elif metric == "orders":
                value = day_summary.total_orders
            elif metric == "customers":
                value = day_summary.unique_customers
            
            trend_data.append({
                "date": current_date.isoformat(),
                "value": value
            })
            
            current_date += timedelta(days=1)
        
        return {
            "metric": metric,
            "period": {
                "start": start_date,
                "end": end_date,
                "days": period_days
            },
            "granularity": granularity,
            "data": trend_data
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


# Export endpoints (would be implemented with actual export logic)
@router.post("/export/csv")
async def export_to_csv(
    request: SalesReportRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_staff_user)
):
    """
    Export sales report to CSV format.
    """
    # This would implement CSV export logic
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="CSV export functionality is not yet implemented"
    )


@router.post("/export/pdf")
async def export_to_pdf(
    request: SalesReportRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_staff_user)
):
    """
    Export sales report to PDF format.
    """
    # This would implement PDF export logic
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="PDF export functionality is not yet implemented"
    )


@router.post("/export/excel")
async def export_to_excel(
    request: SalesReportRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_staff_user)
):
    """
    Export sales report to Excel format.
    """
    # This would implement Excel export logic
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Excel export functionality is not yet implemented"
    )