# backend/modules/analytics/routers/pos/dashboard_routes.py

"""
POS Analytics dashboard routes.

Handles main dashboard and summary endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import logging

from backend.core.database import get_db
from backend.core.auth import get_current_user
from backend.modules.staff.models import StaffMember
from backend.core.rbac import require_permissions, Permission

from ...schemas.pos_analytics_schemas import (
    POSDashboardRequest, POSDashboardResponse, TimeRange
)
from ...services.pos_dashboard_service import POSDashboardService
from .helpers import parse_time_range

router = APIRouter()
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
        service = POSDashboardService(db)
        
        # Convert time range to dates
        start_date, end_date = parse_time_range(
            request.time_range,
            request.start_date,
            request.end_date
        )
        
        # Get dashboard data (with caching)
        dashboard_data = await service.get_dashboard_data(
            start_date=start_date,
            end_date=end_date,
            provider_ids=request.provider_ids,
            terminal_ids=request.terminal_ids,
            include_offline=request.include_offline
        )
        
        return dashboard_data
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting POS analytics dashboard: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve POS analytics dashboard"
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
        service = POSDashboardService(db)
        
        health_summary = await service.get_terminal_health_summary(
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
        service = POSDashboardService(db)
        
        # Trigger refresh and clear cache
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