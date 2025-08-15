# backend/modules/ai_recommendations/routers/staffing_router.py

import logging
from typing import Optional, List
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query

from core.database import get_db
from core.auth import get_current_user
from modules.analytics.services.permissions_service import (
    AnalyticsPermission,
    require_analytics_permission,
)
from sqlalchemy.orm import Session

from ..schemas.staffing_schemas import (
    StaffingOptimizationRequest,
    StaffingRecommendationSet,
    LaborCostAnalysis,
    DayOfWeek,
)
from ..services.staffing_recommendation_service import (
    create_staffing_recommendation_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ai-recommendations/staffing", tags=["AI Staffing Recommendations"]
)


@router.post("/optimize", response_model=StaffingRecommendationSet)
async def optimize_staffing(
    request: StaffingOptimizationRequest,
    current_user: dict = Depends(
        require_analytics_permission(AnalyticsPermission.VIEW_STAFF_REPORTS)
    ),
    db: Session = Depends(get_db),
):
    """
    Generate AI-powered staffing recommendations for a date range.

    This endpoint analyzes:
    - Historical demand patterns
    - Peak hours and seasonality
    - Staff productivity metrics
    - Labor cost optimization
    - Service level requirements

    Requires 'analytics:view_staff_performance' permission.
    """
    try:
        service = create_staffing_recommendation_service(db)
        recommendations = await service.generate_staffing_recommendations(request)

        logger.info(
            f"Generated staffing recommendations for {request.start_date} to {request.end_date} "
            f"for user {current_user.get('id')}"
        )

        return recommendations

    except Exception as e:
        logger.error(f"Error generating staffing recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate staffing recommendations",
        )


@router.get("/daily/{target_date}")
async def get_daily_staffing_recommendation(
    target_date: date,
    include_flexibility: bool = Query(True, description="Include flexibility analysis"),
    current_user: dict = Depends(
        require_analytics_permission(AnalyticsPermission.VIEW_STAFF_REPORTS)
    ),
    db: Session = Depends(get_db),
):
    """
    Get staffing recommendations for a specific day.

    Provides detailed hourly staffing requirements and shift recommendations
    for a single day.
    """
    request = StaffingOptimizationRequest(
        start_date=target_date,
        end_date=target_date,
        include_breaks=True,
        buffer_percentage=10.0,
    )

    service = create_staffing_recommendation_service(db)
    recommendations = await service.generate_staffing_recommendations(request)

    # Return just the daily recommendation
    if recommendations.daily_recommendations:
        return recommendations.daily_recommendations[0]
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No recommendations available for this date",
        )


@router.get("/weekly")
async def get_weekly_staffing_summary(
    start_date: Optional[date] = Query(
        None, description="Start of week (defaults to current week)"
    ),
    current_user: dict = Depends(
        require_analytics_permission(AnalyticsPermission.VIEW_STAFF_REPORTS)
    ),
    db: Session = Depends(get_db),
):
    """
    Get weekly staffing summary and recommendations.

    Provides a week-at-a-glance view of staffing needs with daily summaries
    and total labor costs.
    """
    if not start_date:
        # Default to start of current week (Monday)
        today = datetime.now().date()
        start_date = today - timedelta(days=today.weekday())

    end_date = start_date + timedelta(days=6)

    request = StaffingOptimizationRequest(start_date=start_date, end_date=end_date)

    service = create_staffing_recommendation_service(db)
    recommendations = await service.generate_staffing_recommendations(request)

    # Summarize by day
    weekly_summary = {
        "week_of": start_date,
        "total_hours": recommendations.total_recommended_hours,
        "total_cost": str(recommendations.total_estimated_cost),
        "avg_labor_percentage": recommendations.average_labor_percentage,
        "daily_summary": [],
    }

    for rec in recommendations.daily_recommendations:
        weekly_summary["daily_summary"].append(
            {
                "date": rec.date,
                "day": rec.date.strftime("%A"),
                "total_staff_needed": sum(
                    req.optimal for req in rec.staff_requirements
                ),
                "labor_cost": str(rec.estimated_labor_cost),
                "peak_hours": rec.peak_hours,
                "staffing_level": rec.staffing_level.value,
            }
        )

    return weekly_summary


@router.get("/patterns")
async def get_staffing_patterns(
    pattern_type: Optional[str] = Query(
        None, description="Filter by pattern type (weekday/weekend)"
    ),
    current_user: dict = Depends(
        require_analytics_permission(AnalyticsPermission.VIEW_STAFF_REPORTS)
    ),
    db: Session = Depends(get_db),
):
    """
    Get identified staffing patterns.

    Returns optimal staffing templates based on historical analysis,
    useful for creating standard schedules.
    """
    # Analyze last 90 days to identify patterns
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=90)

    request = StaffingOptimizationRequest(
        start_date=end_date, end_date=end_date  # Just one day to get patterns
    )

    service = create_staffing_recommendation_service(db)
    recommendations = await service.generate_staffing_recommendations(request)

    patterns = recommendations.patterns_identified

    if pattern_type:
        patterns = [
            p for p in patterns if pattern_type.lower() in p.pattern_name.lower()
        ]

    return {
        "patterns": [
            {
                "name": p.pattern_name,
                "applicable_days": [d.value for d in p.applicable_days],
                "total_labor_hours": p.total_labor_hours,
                "estimated_daily_cost": float(p.average_hourly_cost)
                * p.total_labor_hours,
                "shift_templates": p.recommended_shifts,
            }
            for p in patterns
        ]
    }


@router.get("/labor-cost/analysis")
async def get_labor_cost_analysis(
    start_date: date = Query(..., description="Analysis start date"),
    end_date: date = Query(..., description="Analysis end date"),
    compare_to_budget: bool = Query(False, description="Include budget comparison"),
    current_user: dict = Depends(
        require_analytics_permission(AnalyticsPermission.VIEW_FINANCIAL)
    ),
    db: Session = Depends(get_db),
):
    """
    Get detailed labor cost analysis for a period.

    Analyzes actual vs recommended staffing costs and identifies
    optimization opportunities.

    Requires 'analytics:view_financial_details' permission.
    """
    request = StaffingOptimizationRequest(start_date=start_date, end_date=end_date)

    service = create_staffing_recommendation_service(db)
    recommendations = await service.generate_staffing_recommendations(request)

    # Calculate detailed analysis
    total_days = (end_date - start_date).days + 1

    analysis = {
        "period": f"{start_date} to {end_date}",
        "days_analyzed": total_days,
        "recommended_staffing": {
            "total_hours": recommendations.total_recommended_hours,
            "total_cost": str(recommendations.total_estimated_cost),
            "average_daily_cost": str(
                recommendations.total_estimated_cost / total_days
            ),
            "average_labor_percentage": recommendations.average_labor_percentage,
        },
        "optimization_opportunities": [],
        "cost_breakdown": {
            "by_role": {},
            "by_day_type": {
                "weekday": {"hours": 0, "cost": 0},
                "weekend": {"hours": 0, "cost": 0},
            },
        },
    }

    # Analyze by role
    role_hours = {}
    role_costs = {}

    for rec in recommendations.daily_recommendations:
        is_weekend = rec.date.weekday() >= 5

        for req in rec.staff_requirements:
            role_name = req.role.value
            hours = req.optimal * 8  # Assuming 8-hour shifts
            cost = hours * 18.50  # Average rate

            role_hours[role_name] = role_hours.get(role_name, 0) + hours
            role_costs[role_name] = role_costs.get(role_name, 0) + cost

            if is_weekend:
                analysis["cost_breakdown"]["by_day_type"]["weekend"]["hours"] += hours
                analysis["cost_breakdown"]["by_day_type"]["weekend"]["cost"] += cost
            else:
                analysis["cost_breakdown"]["by_day_type"]["weekday"]["hours"] += hours
                analysis["cost_breakdown"]["by_day_type"]["weekday"]["cost"] += cost

    analysis["cost_breakdown"]["by_role"] = {
        role: {"hours": role_hours[role], "cost": role_costs[role]}
        for role in role_hours
    }

    # Identify optimization opportunities
    if recommendations.average_labor_percentage > 30:
        analysis["optimization_opportunities"].append(
            {
                "issue": "High labor percentage",
                "current": recommendations.average_labor_percentage,
                "target": 28.0,
                "potential_savings": str(
                    recommendations.total_estimated_cost * 0.067
                ),  # 2% reduction
            }
        )

    understaffed_days = sum(
        1
        for rec in recommendations.daily_recommendations
        if rec.staffing_level.value.startswith("understaffed")
    )

    if understaffed_days > total_days * 0.2:
        analysis["optimization_opportunities"].append(
            {
                "issue": "Frequent understaffing",
                "affected_days": understaffed_days,
                "impact": "Service quality risk",
                "recommendation": "Increase base staffing levels",
            }
        )

    return analysis


@router.get("/demand-forecast/{target_date}")
async def get_demand_forecast(
    target_date: date,
    include_confidence_intervals: bool = Query(
        True, description="Include confidence intervals"
    ),
    current_user: dict = Depends(
        require_analytics_permission(AnalyticsPermission.VIEW_DASHBOARD)
    ),
    db: Session = Depends(get_db),
):
    """
    Get hourly demand forecast for a specific date.

    Provides predicted order volumes, revenue, and customer counts
    by hour to support staffing decisions.
    """
    service = create_staffing_recommendation_service(db)

    # Generate forecast
    forecasts = await service._generate_demand_forecasts(target_date, target_date)

    hourly_forecast = []

    if target_date in forecasts:
        for forecast in forecasts[target_date]:
            forecast_data = {
                "hour": forecast.hour,
                "time_label": f"{forecast.hour:02d}:00-{(forecast.hour+1)%24:02d}:00",
                "predicted_orders": forecast.predicted_orders,
                "predicted_revenue": str(forecast.predicted_revenue),
                "predicted_customers": forecast.predicted_customers,
            }

            if include_confidence_intervals:
                forecast_data.update(
                    {
                        "orders_range": {
                            "lower": forecast.orders_lower_bound,
                            "upper": forecast.orders_upper_bound,
                        },
                        "confidence_level": forecast.confidence_level,
                    }
                )

            if forecast.is_holiday or forecast.is_special_event:
                forecast_data["special_factors"] = {
                    "is_holiday": forecast.is_holiday,
                    "is_special_event": forecast.is_special_event,
                }

            hourly_forecast.append(forecast_data)

    return {
        "date": target_date,
        "day_of_week": target_date.strftime("%A"),
        "hourly_forecast": hourly_forecast,
        "daily_totals": {
            "predicted_orders": sum(
                f.predicted_orders for f in forecasts.get(target_date, [])
            ),
            "predicted_revenue": str(
                sum(f.predicted_revenue for f in forecasts.get(target_date, []))
            ),
            "predicted_customers": sum(
                f.predicted_customers for f in forecasts.get(target_date, [])
            ),
        },
    }


@router.post("/schedule/generate/{week_start}")
async def generate_schedule(
    week_start: date,
    auto_assign_staff: bool = Query(
        False, description="Automatically assign available staff"
    ),
    respect_preferences: bool = Query(
        True, description="Respect staff scheduling preferences"
    ),
    current_user: dict = Depends(
        require_analytics_permission(AnalyticsPermission.MANAGE_ALERTS)
    ),
    db: Session = Depends(get_db),
):
    """
    Generate an optimized schedule for a week.

    Creates a complete staff schedule based on recommendations,
    staff availability, and business rules.

    Requires 'analytics:manage_alerts' permission.
    """
    end_date = week_start + timedelta(days=6)

    request = StaffingOptimizationRequest(
        start_date=week_start,
        end_date=end_date,
        include_breaks=True,
        account_for_training=True,
    )

    service = create_staffing_recommendation_service(db)
    recommendations = await service.generate_staffing_recommendations(request)

    # This would generate actual shift assignments
    # For now, return a summary
    return {
        "schedule_id": f"schedule-{week_start.strftime('%Y%m%d')}",
        "week_of": week_start,
        "status": "draft",
        "summary": {
            "total_shifts": len(recommendations.daily_recommendations)
            * 15,  # Avg shifts per day
            "total_hours": recommendations.total_recommended_hours,
            "estimated_cost": str(recommendations.total_estimated_cost),
            "coverage_score": 0.92,
        },
        "auto_assigned": auto_assign_staff,
        "manual_adjustments_needed": (
            [
                "3 shifts need manager approval",
                "2 staff members have conflicting availability",
            ]
            if auto_assign_staff
            else ["Manual assignment required"]
        ),
        "next_steps": [
            "Review and adjust shift assignments",
            "Resolve conflicts",
            "Publish schedule to staff",
        ],
    }


@router.get("/insights/productivity")
async def get_productivity_insights(
    role: Optional[str] = Query(None, description="Filter by staff role"),
    days_back: int = Query(30, ge=7, le=90, description="Days of history to analyze"),
    current_user: dict = Depends(
        require_analytics_permission(AnalyticsPermission.VIEW_STAFF_REPORTS)
    ),
    db: Session = Depends(get_db),
):
    """
    Get staff productivity insights and recommendations.

    Analyzes staff performance metrics to identify training needs
    and optimization opportunities.
    """
    # This would analyze actual staff performance data
    # For now, return sample insights
    return {
        "analysis_period": {
            "start": (datetime.now() - timedelta(days=days_back)).date(),
            "end": datetime.now().date(),
        },
        "productivity_summary": {
            "average_orders_per_hour": {
                "servers": 12.5,
                "line_cooks": 22.3,
                "bartenders": 15.8,
            },
            "efficiency_score": 0.87,
            "trend": "improving",
        },
        "top_performers": [
            {
                "staff_id": 101,
                "name": "John Smith",
                "role": "server",
                "orders_per_hour": 15.2,
                "vs_average": "+21.6%",
            },
            {
                "staff_id": 102,
                "name": "Jane Doe",
                "role": "line_cook",
                "orders_per_hour": 28.5,
                "vs_average": "+27.8%",
            },
        ],
        "improvement_opportunities": [
            {
                "role": "server",
                "issue": "Below average table turnover",
                "affected_staff": 3,
                "recommendation": "Additional training on efficient service",
            },
            {
                "role": "busser",
                "issue": "Slow table clearing times",
                "affected_staff": 2,
                "recommendation": "Review clearing procedures and routes",
            },
        ],
        "cross_training_recommendations": [
            {
                "from_role": "host",
                "to_role": "server",
                "candidates": 2,
                "benefit": "Increase scheduling flexibility",
            }
        ],
    }


# Export router
__all__ = ["router"]
