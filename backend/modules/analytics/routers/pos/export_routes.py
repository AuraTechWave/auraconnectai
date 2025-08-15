# backend/modules/analytics/routers/pos/export_routes.py

"""
POS Analytics export and trends routes.

Handles data export and trend analysis endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional
import logging

from core.database import get_db
from core.auth import get_current_user
from core.auth import User
from core.auth import require_permission

# ValidationError replaced with standard ValueError

from ...schemas.pos_analytics_schemas import POSExportRequest, TimeRange
from ...services.pos_trends_service import POSTrendsService
from ...services.pos_export_service import POSExportService
from .helpers import parse_time_range, get_media_type

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/trends/transactions")
async def get_transaction_trends(
    time_range: TimeRange = Query(TimeRange.LAST_7_DAYS),
    provider_id: Optional[int] = Query(None, description="Filter by provider"),
    terminal_id: Optional[str] = Query(None, description="Filter by terminal"),
    granularity: str = Query("hourly", pattern="^(hourly|daily|weekly)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("analytics:read")),
):
    """
    Get transaction trend data for charts.

    Returns time-series data for transaction volumes and values.

    Requires: analytics.view permission
    """

    try:
        service = POSTrendsService(db)

        # Convert time range
        start_date, end_date = parse_time_range(time_range, None, None)

        trends = await service.get_transaction_trends(
            start_date=start_date,
            end_date=end_date,
            provider_id=provider_id,
            terminal_id=terminal_id,
            granularity=granularity,
        )

        return {
            "trends": trends,
            "time_range": time_range.value,
            "granularity": granularity,
            "data_points": len(trends),
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting transaction trends: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve transaction trends",
        )


@router.get("/trends/performance")
async def get_performance_trends(
    metric: str = Query(..., pattern="^(response_time|success_rate|error_rate)$"),
    time_range: TimeRange = Query(TimeRange.LAST_7_DAYS),
    provider_id: Optional[int] = Query(None, description="Filter by provider"),
    granularity: str = Query("daily", pattern="^(hourly|daily|weekly)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("analytics:read")),
):
    """
    Get performance metric trends.

    Returns time-series data for performance metrics.

    Requires: analytics.view permission
    """

    try:
        service = POSTrendsService(db)

        # Convert time range
        start_date, end_date = parse_time_range(time_range, None, None)

        trends = await service.get_performance_trends(
            metric=metric,
            start_date=start_date,
            end_date=end_date,
            provider_id=provider_id,
            granularity=granularity,
        )

        return {
            "metric": metric,
            "trends": trends,
            "time_range": time_range.value,
            "granularity": granularity,
            "data_points": len(trends),
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting performance trends: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve performance trends",
        )


@router.post("/export")
async def export_pos_analytics(
    request: POSExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("analytics:read")),
):
    """
    Export POS analytics data to file.

    Supports CSV, Excel, and PDF formats with various report types.

    Requires: analytics.export permission
    """

    try:
        service = POSExportService(db)

        # Convert time range
        start_date, end_date = parse_time_range(
            request.time_range, request.start_date, request.end_date
        )

        # Generate export
        file_path = await service.export_analytics(
            report_type=request.report_type,
            format=request.format,
            start_date=start_date,
            end_date=end_date,
            provider_ids=request.provider_ids,
            terminal_ids=request.terminal_ids,
            include_charts=request.include_charts,
            user_id=current_user.id,
        )

        # Return file
        filename = f"pos_analytics_{request.report_type}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.{request.format}"

        return FileResponse(
            path=file_path, filename=filename, media_type=get_media_type(request.format)
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error exporting POS analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export POS analytics",
        )


@router.get("/export/templates")
async def get_export_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("analytics:read")),
):
    """
    Get available export templates.

    Returns list of predefined export configurations.

    Requires: analytics.view permission
    """

    return {
        "templates": [
            {
                "id": "daily_summary",
                "name": "Daily Summary Report",
                "description": "Summary of all POS activity for a single day",
                "report_type": "summary",
                "default_format": "pdf",
                "default_time_range": "last_24_hours",
            },
            {
                "id": "weekly_performance",
                "name": "Weekly Performance Report",
                "description": "Detailed performance metrics for the past week",
                "report_type": "detailed",
                "default_format": "xlsx",
                "default_time_range": "last_7_days",
            },
            {
                "id": "monthly_transactions",
                "name": "Monthly Transaction Report",
                "description": "Complete transaction history for the month",
                "report_type": "transactions",
                "default_format": "csv",
                "default_time_range": "last_30_days",
            },
            {
                "id": "error_analysis",
                "name": "Error Analysis Report",
                "description": "Detailed analysis of errors and failures",
                "report_type": "errors",
                "default_format": "xlsx",
                "default_time_range": "last_7_days",
            },
        ]
    }
