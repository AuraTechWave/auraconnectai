# backend/modules/kds/routes/kds_performance_routes.py

"""
Performance and analytics routes for Kitchen Display System
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from datetime import datetime

from core.database import get_db
from core.auth import get_current_user
from ..services.kds_performance_service import (
    KDSPerformanceService,
    TimeRange,
    StationMetrics,
    KitchenAnalytics,
)

router = APIRouter(prefix="/api/v1/kds/performance", tags=["KDS Performance"])


@router.get("/station/{station_id}/metrics")
async def get_station_metrics(
    station_id: int,
    time_range: TimeRange = Query(TimeRange.TODAY),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get performance metrics for a specific station"""
    
    service = KDSPerformanceService(db)
    
    try:
        metrics = service.get_station_metrics(
            station_id=station_id,
            time_range=time_range,
            start_date=start_date,
            end_date=end_date,
        )
        
        return {
            "success": True,
            "data": metrics.__dict__,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving metrics: {str(e)}")


@router.get("/kitchen/analytics")
async def get_kitchen_analytics(
    restaurant_id: int = Query(..., description="Restaurant ID"),
    time_range: TimeRange = Query(TimeRange.TODAY),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get overall kitchen performance analytics"""
    
    service = KDSPerformanceService(db)
    
    try:
        analytics = service.get_kitchen_analytics(
            restaurant_id=restaurant_id,
            time_range=time_range,
            start_date=start_date,
            end_date=end_date,
        )
        
        return {
            "success": True,
            "data": analytics.__dict__,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving analytics: {str(e)}")


@router.get("/real-time")
async def get_real_time_metrics(
    station_id: Optional[int] = Query(None, description="Filter by station ID"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get real-time performance metrics"""
    
    service = KDSPerformanceService(db)
    
    try:
        metrics = service.get_real_time_metrics(station_id=station_id)
        
        return {
            "success": True,
            "data": metrics,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving real-time metrics: {str(e)}")


@router.get("/staff/{staff_id}/performance")
async def get_staff_performance(
    staff_id: int,
    time_range: TimeRange = Query(TimeRange.TODAY),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get performance metrics for a specific staff member"""
    
    service = KDSPerformanceService(db)
    
    try:
        performance = service.get_staff_performance(
            staff_id=staff_id,
            time_range=time_range,
        )
        
        return {
            "success": True,
            "data": performance,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving staff performance: {str(e)}")


@router.get("/report")
async def generate_performance_report(
    restaurant_id: int = Query(..., description="Restaurant ID"),
    time_range: TimeRange = Query(TimeRange.TODAY),
    format: str = Query("json", pattern="^(json|pdf|csv)$"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Generate comprehensive performance report"""
    
    service = KDSPerformanceService(db)
    
    try:
        report = service.generate_performance_report(
            restaurant_id=restaurant_id,
            time_range=time_range,
            format=format,
        )
        
        return {
            "success": True,
            "data": report,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")


@router.get("/stations/comparison")
async def compare_stations(
    restaurant_id: int = Query(..., description="Restaurant ID"),
    time_range: TimeRange = Query(TimeRange.TODAY),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Compare performance across all stations"""
    
    service = KDSPerformanceService(db)
    
    try:
        from ..models.kds_models import KitchenStation
        
        # Get all stations
        stations = db.query(KitchenStation).all()
        
        comparisons = []
        for station in stations:
            try:
                metrics = service.get_station_metrics(
                    station_id=station.id,
                    time_range=time_range,
                )
                comparisons.append({
                    "station_id": station.id,
                    "station_name": station.name,
                    "station_type": station.station_type.value,
                    "metrics": {
                        "completion_rate": metrics.completion_rate,
                        "average_prep_time": metrics.average_prep_time,
                        "items_per_hour": metrics.items_per_hour,
                        "late_percentage": metrics.late_order_percentage,
                        "current_load": metrics.current_load,
                    },
                })
            except Exception as e:
                # Skip stations with no data
                continue
        
        # Sort by efficiency (completion rate)
        comparisons.sort(key=lambda x: x["metrics"]["completion_rate"], reverse=True)
        
        return {
            "success": True,
            "data": {
                "time_range": time_range.value,
                "stations": comparisons,
                "best_performing": comparisons[0] if comparisons else None,
                "needs_attention": [
                    s for s in comparisons
                    if s["metrics"]["completion_rate"] < 80
                    or s["metrics"]["late_percentage"] > 20
                ],
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error comparing stations: {str(e)}")


@router.get("/trends")
async def get_performance_trends(
    restaurant_id: int = Query(..., description="Restaurant ID"),
    metric: str = Query(..., pattern="^(completion_rate|prep_time|throughput|accuracy)$"),
    period: str = Query("week", pattern="^(day|week|month)$"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get performance trends over time"""
    
    service = KDSPerformanceService(db)
    
    try:
        # This would need implementation to track historical data
        # For now, return sample trend data
        trends = {
            "metric": metric,
            "period": period,
            "data_points": [],
            "trend": "improving",  # or "declining", "stable"
            "average": 0,
            "change_percentage": 0,
        }
        
        return {
            "success": True,
            "data": trends,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving trends: {str(e)}")


@router.post("/alerts/configure")
async def configure_performance_alerts(
    station_id: Optional[int] = None,
    alerts_config: Dict[str, Any] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Configure performance alerts and thresholds"""
    
    # This would configure alerts for:
    # - Low completion rates
    # - High wait times
    # - Station bottlenecks
    # - Staff performance issues
    
    return {
        "success": True,
        "message": "Alert configuration updated",
        "config": alerts_config,
    }


@router.get("/insights")
async def get_performance_insights(
    restaurant_id: int = Query(..., description="Restaurant ID"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get AI-powered performance insights and recommendations"""
    
    service = KDSPerformanceService(db)
    
    try:
        # Get current analytics
        analytics = service.get_kitchen_analytics(
            restaurant_id=restaurant_id,
            time_range=TimeRange.TODAY,
        )
        
        # Generate insights
        insights = []
        
        if analytics.bottleneck_stations:
            insights.append({
                "type": "bottleneck",
                "severity": "high",
                "message": f"Stations {', '.join(analytics.bottleneck_stations)} are causing delays",
                "recommendation": "Consider redistributing items or adding staff",
            })
        
        if analytics.efficiency_score < 70:
            insights.append({
                "type": "efficiency",
                "severity": "medium",
                "message": f"Overall efficiency is {analytics.efficiency_score}%",
                "recommendation": "Review workflows and provide additional training",
            })
        
        if analytics.average_order_time > 20:
            insights.append({
                "type": "speed",
                "severity": "medium",
                "message": f"Average order time is {analytics.average_order_time} minutes",
                "recommendation": "Optimize prep processes and station assignments",
            })
        
        # Positive insights
        if analytics.efficiency_score > 85:
            insights.append({
                "type": "achievement",
                "severity": "info",
                "message": f"Excellent efficiency score of {analytics.efficiency_score}%",
                "recommendation": "Maintain current performance levels",
            })
        
        return {
            "success": True,
            "data": {
                "insights": insights,
                "summary": {
                    "efficiency_score": analytics.efficiency_score,
                    "average_order_time": analytics.average_order_time,
                    "peak_hours": analytics.peak_hours,
                },
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating insights: {str(e)}")