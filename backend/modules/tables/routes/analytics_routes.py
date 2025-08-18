"""
REST API routes for table analytics.

This module provides endpoints for:
- Turn time analytics
- Table performance metrics
- Peak hours analysis
- Historical data queries
"""

from typing import Optional
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.auth import get_current_active_user
from core.models import User
from ..services.table_analytics_service import TableAnalyticsService
from ..schemas.table_schemas import (
    CurrentAnalytics,
    TurnTimeAnalytics,
    TablePerformanceMetrics,
    PeakHoursAnalysis
)

router = APIRouter(prefix="/analytics", tags=["tables-analytics"])
analytics_service = TableAnalyticsService()


@router.get("/current", response_model=CurrentAnalytics)
async def get_current_analytics(
    floor_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current real-time analytics for tables."""
    
    if not current_user.restaurant_id:
        raise HTTPException(status_code=400, detail="User not associated with a restaurant")
    
    analytics = await analytics_service.get_current_analytics(
        db=db,
        restaurant_id=current_user.restaurant_id,
        floor_id=floor_id
    )
    
    return CurrentAnalytics(**analytics)


@router.get("/turn-times")
async def get_turn_time_analytics(
    start_date: date,
    end_date: date,
    floor_id: Optional[int] = Query(None),
    group_by: str = Query("day", enum=["day", "hour", "day_of_week"]),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get turn time analytics for a date range.
    
    Parameters:
    - start_date: Start date for analysis
    - end_date: End date for analysis
    - floor_id: Optional floor filter
    - group_by: Grouping method (day, hour, day_of_week)
    """
    
    if not current_user.restaurant_id:
        raise HTTPException(status_code=400, detail="User not associated with a restaurant")
    
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="End date must be after start date")
    
    if (end_date - start_date).days > 90:
        raise HTTPException(status_code=400, detail="Date range cannot exceed 90 days")
    
    analytics = await analytics_service.get_turn_time_analytics(
        db=db,
        restaurant_id=current_user.restaurant_id,
        start_date=start_date,
        end_date=end_date,
        floor_id=floor_id,
        group_by=group_by
    )
    
    return analytics


@router.get("/performance")
async def get_table_performance_metrics(
    start_date: date,
    end_date: date,
    table_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get performance metrics for tables.
    
    Parameters:
    - start_date: Start date for analysis
    - end_date: End date for analysis
    - table_id: Optional specific table filter
    """
    
    if not current_user.restaurant_id:
        raise HTTPException(status_code=400, detail="User not associated with a restaurant")
    
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="End date must be after start date")
    
    metrics = await analytics_service.get_table_performance_metrics(
        db=db,
        restaurant_id=current_user.restaurant_id,
        start_date=start_date,
        end_date=end_date,
        table_id=table_id
    )
    
    return metrics


@router.get("/peak-hours", response_model=PeakHoursAnalysis)
async def get_peak_hours_analysis(
    lookback_days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get peak hours analysis for table occupancy.
    
    Parameters:
    - lookback_days: Number of days to analyze (7-90)
    """
    
    if not current_user.restaurant_id:
        raise HTTPException(status_code=400, detail="User not associated with a restaurant")
    
    analysis = await analytics_service.get_peak_hours_analysis(
        db=db,
        restaurant_id=current_user.restaurant_id,
        lookback_days=lookback_days
    )
    
    return PeakHoursAnalysis(**analysis)


@router.get("/average-turn-time")
async def get_average_turn_time(
    lookback_days: int = Query(7, ge=1, le=30),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get average turn time for the restaurant.
    
    Parameters:
    - lookback_days: Number of days to analyze (1-30)
    """
    
    if not current_user.restaurant_id:
        raise HTTPException(status_code=400, detail="User not associated with a restaurant")
    
    avg_time = await analytics_service.get_average_turn_time(
        db=db,
        restaurant_id=current_user.restaurant_id,
        lookback_days=lookback_days
    )
    
    return {
        "average_turn_time_minutes": avg_time,
        "lookback_days": lookback_days,
        "calculated_at": datetime.utcnow().isoformat()
    }


@router.get("/reservations")
async def get_reservation_analytics(
    start_date: date,
    end_date: date,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get analytics for table reservations.
    
    Parameters:
    - start_date: Start date for analysis
    - end_date: End date for analysis
    """
    
    if not current_user.restaurant_id:
        raise HTTPException(status_code=400, detail="User not associated with a restaurant")
    
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="End date must be after start date")
    
    analytics = await analytics_service.get_reservation_analytics(
        db=db,
        restaurant_id=current_user.restaurant_id,
        start_date=start_date,
        end_date=end_date
    )
    
    return analytics


@router.get("/heat-map")
async def get_heat_map_data(
    floor_id: Optional[int] = Query(None),
    period_days: int = Query(7, ge=1, le=30),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get heat map data for table occupancy visualization.
    
    Parameters:
    - floor_id: Optional floor filter
    - period_days: Number of days to analyze (1-30)
    """
    
    if not current_user.restaurant_id:
        raise HTTPException(status_code=400, detail="User not associated with a restaurant")
    
    # Use the realtime manager's heat map method
    from ..websocket.realtime_table_manager import realtime_table_manager
    
    heat_map = await realtime_table_manager._get_heat_map_data(
        db=db,
        restaurant_id=current_user.restaurant_id,
        floor_id=floor_id
    )
    
    return heat_map