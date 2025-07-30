# backend/modules/analytics/routers/pos_analytics_router.py

"""
POS Analytics router for admin dashboard.

Provides comprehensive analytics for POS operations including:
- Provider performance metrics
- Terminal health monitoring
- Transaction analytics
- Sync and webhook performance
- Error analysis and alerting
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from backend.core.database import get_db
from backend.core.auth import get_current_user
from backend.modules.staff.models import StaffMember
from backend.core.rbac import require_permissions, Permission

from ..schemas.pos_analytics_schemas import (
    POSDashboardRequest, POSDashboardResponse,
    POSProviderDetailsRequest, POSProviderDetailsResponse,
    POSTerminalDetailsRequest, POSTerminalDetailsResponse,
    POSComparisonRequest, POSComparisonResponse,
    POSExportRequest, TimeRange, AlertSeverity
)
from ..services.pos_analytics_service import POSAnalyticsService

router = APIRouter(prefix="/analytics/pos", tags=["POS Analytics"])
logger = logging.getLogger(__name__)


@router.post("/dashboard", response_model=POSDashboardResponse)
async def get_pos_analytics_dashboard(
    request: POSDashboardRequest,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
):
    """
    Get comprehensive POS analytics dashboard data.
    
    Returns overview metrics, provider summaries, terminal health,
    transaction trends, and active alerts.
    
    Requires: analytics.view permission
    """
    # Check permissions
    await require_permissions(current_user, [Permission.ANALYTICS_VIEW])
    
    try:
        service = POSAnalyticsService(db)
        
        # Convert time range to dates
        start_date, end_date = _parse_time_range(
            request.time_range,
            request.start_date,
            request.end_date
        )
        
        # Get dashboard data
        dashboard_data = await service.get_dashboard_data(
            start_date=start_date,
            end_date=end_date,
            provider_ids=request.provider_ids,
            terminal_ids=request.terminal_ids,
            include_offline=request.include_offline
        )
        
        return dashboard_data
        
    except Exception as e:
        logger.error(f"Error getting POS analytics dashboard: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve POS analytics dashboard"
        )


@router.post("/provider/{provider_id}/details", response_model=POSProviderDetailsResponse)
async def get_provider_analytics_details(
    provider_id: int,
    request: POSProviderDetailsRequest,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
):
    """
    Get detailed analytics for a specific POS provider.
    
    Returns comprehensive metrics including sync performance,
    webhook processing, error analysis, and terminal breakdown.
    
    Requires: analytics.view permission
    """
    await require_permissions(current_user, [Permission.ANALYTICS_VIEW])
    
    try:
        service = POSAnalyticsService(db)
        
        # Validate provider exists
        if not service.validate_provider_exists(provider_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"POS provider {provider_id} not found"
            )
        
        # Convert time range
        start_date, end_date = _parse_time_range(
            request.time_range,
            request.start_date,
            request.end_date
        )
        
        # Get provider details
        provider_details = await service.get_provider_details(
            provider_id=provider_id,
            start_date=start_date,
            end_date=end_date,
            include_terminals=request.include_terminals,
            include_errors=request.include_errors
        )
        
        return provider_details
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting provider analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve provider analytics"
        )


@router.post("/terminal/{terminal_id}/details", response_model=POSTerminalDetailsResponse)
async def get_terminal_analytics_details(
    terminal_id: str,
    request: POSTerminalDetailsRequest,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
):
    """
    Get detailed analytics for a specific POS terminal.
    
    Returns transaction metrics, sync performance, error analysis,
    and historical trends for the terminal.
    
    Requires: analytics.view permission
    """
    await require_permissions(current_user, [Permission.ANALYTICS_VIEW])
    
    try:
        service = POSAnalyticsService(db)
        
        # Validate terminal exists
        if not service.validate_terminal_exists(terminal_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"POS terminal {terminal_id} not found"
            )
        
        # Convert time range
        start_date, end_date = _parse_time_range(
            request.time_range,
            request.start_date,
            request.end_date
        )
        
        # Get terminal details
        terminal_details = await service.get_terminal_details(
            terminal_id=terminal_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return terminal_details
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting terminal analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve terminal analytics"
        )


@router.post("/compare", response_model=POSComparisonResponse)
async def compare_pos_providers(
    request: POSComparisonRequest,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
):
    """
    Compare analytics metrics across multiple POS providers.
    
    Returns side-by-side comparison of key metrics, rankings,
    and insights for selected providers.
    
    Requires: analytics.view permission
    """
    await require_permissions(current_user, [Permission.ANALYTICS_VIEW])
    
    try:
        service = POSAnalyticsService(db)
        
        # Convert time range
        start_date, end_date = _parse_time_range(
            request.time_range,
            request.start_date,
            request.end_date
        )
        
        # Get comparison data
        comparison = await service.compare_providers(
            provider_ids=request.provider_ids,
            start_date=start_date,
            end_date=end_date,
            metrics=request.metrics
        )
        
        return comparison
        
    except Exception as e:
        logger.error(f"Error comparing POS providers: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compare POS providers"
        )


@router.get("/alerts/active")
async def get_active_pos_alerts(
    severity: Optional[AlertSeverity] = Query(None, description="Filter by severity"),
    provider_id: Optional[int] = Query(None, description="Filter by provider"),
    terminal_id: Optional[str] = Query(None, description="Filter by terminal"),
    limit: int = Query(50, ge=1, le=200, description="Maximum alerts to return"),
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
):
    """
    Get active POS analytics alerts.
    
    Returns list of active alerts with filtering options.
    
    Requires: analytics.view permission
    """
    await require_permissions(current_user, [Permission.ANALYTICS_VIEW])
    
    try:
        service = POSAnalyticsService(db)
        
        alerts = service.get_active_alerts(
            severity=severity,
            provider_id=provider_id,
            terminal_id=terminal_id,
            limit=limit
        )
        
        return {
            "alerts": alerts,
            "total_count": len(alerts),
            "filters": {
                "severity": severity,
                "provider_id": provider_id,
                "terminal_id": terminal_id
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting POS alerts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve POS alerts"
        )


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_pos_alert(
    alert_id: str,
    notes: Optional[str] = Query(None, description="Acknowledgment notes"),
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
):
    """
    Acknowledge a POS analytics alert.
    
    Marks the alert as acknowledged by the current user.
    
    Requires: analytics.manage permission
    """
    await require_permissions(current_user, [Permission.ANALYTICS_MANAGE])
    
    try:
        service = POSAnalyticsService(db)
        
        success = service.acknowledge_alert(
            alert_id=alert_id,
            acknowledged_by=current_user.id,
            notes=notes
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found or already acknowledged"
            )
        
        return {
            "success": True,
            "message": "Alert acknowledged successfully",
            "alert_id": alert_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error acknowledging alert: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to acknowledge alert"
        )


@router.get("/health/terminals")
async def get_terminal_health_summary(
    provider_id: Optional[int] = Query(None, description="Filter by provider"),
    health_status: Optional[str] = Query(None, description="Filter by health status"),
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
):
    """
    Get summary of terminal health status.
    
    Returns breakdown of terminal health across providers.
    
    Requires: analytics.view permission
    """
    await require_permissions(current_user, [Permission.ANALYTICS_VIEW])
    
    try:
        service = POSAnalyticsService(db)
        
        health_summary = service.get_terminal_health_summary(
            provider_id=provider_id,
            health_status=health_status
        )
        
        return health_summary
        
    except Exception as e:
        logger.error(f"Error getting terminal health: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve terminal health"
        )


@router.get("/trends/transactions")
async def get_transaction_trends(
    time_range: TimeRange = Query(TimeRange.LAST_7_DAYS),
    provider_id: Optional[int] = Query(None, description="Filter by provider"),
    terminal_id: Optional[str] = Query(None, description="Filter by terminal"),
    granularity: str = Query("hourly", regex="^(hourly|daily|weekly)$"),
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
):
    """
    Get transaction trend data for charts.
    
    Returns time-series data for transaction volumes and values.
    
    Requires: analytics.view permission
    """
    await require_permissions(current_user, [Permission.ANALYTICS_VIEW])
    
    try:
        service = POSAnalyticsService(db)
        
        # Convert time range
        start_date, end_date = _parse_time_range(time_range, None, None)
        
        trends = service.get_transaction_trends(
            start_date=start_date,
            end_date=end_date,
            provider_id=provider_id,
            terminal_id=terminal_id,
            granularity=granularity
        )
        
        return {
            "trends": trends,
            "time_range": time_range.value,
            "granularity": granularity,
            "data_points": len(trends)
        }
        
    except Exception as e:
        logger.error(f"Error getting transaction trends: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve transaction trends"
        )


@router.post("/export")
async def export_pos_analytics(
    request: POSExportRequest,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
):
    """
    Export POS analytics data to file.
    
    Supports CSV, Excel, and PDF formats with various report types.
    
    Requires: analytics.export permission
    """
    await require_permissions(current_user, [Permission.ANALYTICS_EXPORT])
    
    try:
        service = POSAnalyticsService(db)
        
        # Convert time range
        start_date, end_date = _parse_time_range(
            request.time_range,
            request.start_date,
            request.end_date
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
            user_id=current_user.id
        )
        
        # Return file
        return FileResponse(
            path=file_path,
            filename=f"pos_analytics_{request.report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{request.format}",
            media_type=_get_media_type(request.format)
        )
        
    except Exception as e:
        logger.error(f"Error exporting POS analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export POS analytics"
        )


@router.post("/refresh")
async def refresh_pos_analytics_data(
    provider_id: Optional[int] = Query(None, description="Specific provider to refresh"),
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
):
    """
    Manually trigger refresh of POS analytics data.
    
    Forces recalculation of aggregated metrics.
    
    Requires: analytics.manage permission
    """
    await require_permissions(current_user, [Permission.ANALYTICS_MANAGE])
    
    try:
        service = POSAnalyticsService(db)
        
        # Trigger refresh
        task_id = await service.trigger_data_refresh(
            provider_id=provider_id,
            requested_by=current_user.id
        )
        
        return {
            "success": True,
            "message": "Analytics refresh triggered",
            "task_id": task_id,
            "provider_id": provider_id
        }
        
    except Exception as e:
        logger.error(f"Error refreshing POS analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh POS analytics"
        )


# Helper functions

def _parse_time_range(
    time_range: TimeRange,
    start_date: Optional[datetime],
    end_date: Optional[datetime]
) -> tuple[datetime, datetime]:
    """Parse time range into start and end dates"""
    
    if time_range == TimeRange.CUSTOM:
        if not start_date or not end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date and end_date required for custom time range"
            )
        return start_date, end_date
    
    # Calculate based on predefined range
    now = datetime.now()
    
    if time_range == TimeRange.LAST_HOUR:
        return now - timedelta(hours=1), now
    elif time_range == TimeRange.LAST_24_HOURS:
        return now - timedelta(days=1), now
    elif time_range == TimeRange.LAST_7_DAYS:
        return now - timedelta(days=7), now
    elif time_range == TimeRange.LAST_30_DAYS:
        return now - timedelta(days=30), now
    else:
        # Default to last 24 hours
        return now - timedelta(days=1), now


def _get_media_type(format: str) -> str:
    """Get media type for file format"""
    media_types = {
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf"
    }
    return media_types.get(format, "application/octet-stream")