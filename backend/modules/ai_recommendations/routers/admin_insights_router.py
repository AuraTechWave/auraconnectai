# backend/modules/ai_recommendations/routers/admin_insights_router.py

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel, Field

from core.database import get_db
from core.auth import get_current_user, require_permission, User
from ..schemas.admin_schemas import (
    FeedbackSummaryResponse,
    ModelPerformanceResponse,
    DomainInsightsResponse,
    FeedbackTrendResponse,
)
from ..services.feedback_analytics_service import feedback_analytics_service

router = APIRouter(prefix="/admin/insights", tags=["AI Admin Insights"])


class TimeRange(BaseModel):
    """Time range for queries"""

    start_date: datetime
    end_date: datetime

    @classmethod
    def from_days(cls, days: int):
        """Create time range from number of days"""
        end = datetime.utcnow()
        start = end - timedelta(days=days)
        return cls(start_date=start, end_date=end)


@router.get("/feedback/summary", response_model=FeedbackSummaryResponse)
@require_permission("ai.view_insights")
async def get_feedback_summary(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    model_type: Optional[str] = Query(None, description="Filter by model type"),
    domain: Optional[str] = Query(None, description="Filter by domain"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get feedback summary for AI models

    Requires permission: ai.view_insights
    """
    time_range = TimeRange.from_days(days)

    summary = await feedback_analytics_service.get_feedback_summary(
        db=db,
        start_date=time_range.start_date,
        end_date=time_range.end_date,
        model_type=model_type,
        domain=domain,
    )

    return summary


@router.get("/model/performance", response_model=List[ModelPerformanceResponse])
@require_permission("ai.view_insights")
async def get_model_performance(
    days: int = Query(7, ge=1, le=90),
    group_by: str = Query("model_type", regex="^(model_type|domain|endpoint)$"),
    min_requests: int = Query(10, ge=1, description="Minimum requests to include"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get model performance metrics grouped by specified dimension

    Requires permission: ai.view_insights
    """
    time_range = TimeRange.from_days(days)

    performance_data = await feedback_analytics_service.get_model_performance(
        db=db,
        start_date=time_range.start_date,
        end_date=time_range.end_date,
        group_by=group_by,
        min_requests=min_requests,
    )

    return performance_data


@router.get("/domain/{domain}", response_model=DomainInsightsResponse)
@require_permission("ai.view_insights")
async def get_domain_insights(
    domain: str,
    days: int = Query(30, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed insights for a specific domain

    Requires permission: ai.view_insights
    """
    time_range = TimeRange.from_days(days)

    insights = await feedback_analytics_service.get_domain_insights(
        db=db,
        domain=domain,
        start_date=time_range.start_date,
        end_date=time_range.end_date,
    )

    if not insights:
        raise HTTPException(
            status_code=404, detail=f"No data found for domain: {domain}"
        )

    return insights


@router.get("/feedback/trends", response_model=FeedbackTrendResponse)
@require_permission("ai.view_insights")
async def get_feedback_trends(
    days: int = Query(30, ge=7, le=90),
    interval: str = Query("daily", regex="^(hourly|daily|weekly)$"),
    model_type: Optional[str] = None,
    domain: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get feedback trends over time

    Requires permission: ai.view_insights
    """
    time_range = TimeRange.from_days(days)

    trends = await feedback_analytics_service.get_feedback_trends(
        db=db,
        start_date=time_range.start_date,
        end_date=time_range.end_date,
        interval=interval,
        model_type=model_type,
        domain=domain,
    )

    return trends


@router.get("/feedback/details")
@require_permission("ai.view_insights")
async def get_feedback_details(
    suggestion_id: Optional[str] = None,
    user_id: Optional[int] = None,
    rating_min: Optional[int] = Query(None, ge=1, le=5),
    rating_max: Optional[int] = Query(None, ge=1, le=5),
    has_comment: Optional[bool] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed feedback entries with filtering

    Requires permission: ai.view_insights
    """
    filters = {}

    if suggestion_id:
        filters["suggestion_id"] = suggestion_id
    if user_id:
        filters["user_id"] = user_id
    if rating_min:
        filters["rating_min"] = rating_min
    if rating_max:
        filters["rating_max"] = rating_max
    if has_comment is not None:
        filters["has_comment"] = has_comment

    feedback_entries = await feedback_analytics_service.get_feedback_details(
        db=db, filters=filters, offset=offset, limit=limit
    )

    return feedback_entries


@router.get("/metrics/export")
@require_permission("ai.export_data")
async def export_metrics(
    format: str = Query("json", regex="^(json|csv)$"),
    days: int = Query(30, ge=1, le=365),
    include_feedback: bool = Query(True),
    include_performance: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Export AI metrics and insights

    Requires permission: ai.export_data
    """
    time_range = TimeRange.from_days(days)

    export_data = await feedback_analytics_service.export_metrics(
        db=db,
        start_date=time_range.start_date,
        end_date=time_range.end_date,
        format=format,
        include_feedback=include_feedback,
        include_performance=include_performance,
    )

    if format == "csv":
        from fastapi.responses import Response

        return Response(
            content=export_data,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=ai_metrics_{datetime.utcnow().strftime('%Y%m%d')}.csv"
            },
        )

    return export_data


@router.post("/alerts/configure")
@require_permission("ai.configure_alerts")
async def configure_alerts(
    alert_config: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Configure alerts for AI model performance

    Example config:
    {
        "low_rating_threshold": 2.5,
        "high_failure_rate": 0.2,
        "low_confidence_threshold": 0.5,
        "notification_channels": ["email", "slack"],
        "check_interval_minutes": 60
    }

    Requires permission: ai.configure_alerts
    """
    result = await feedback_analytics_service.configure_alerts(
        db=db, user_id=current_user.id, config=alert_config
    )

    return {"success": True, "message": "Alert configuration updated", "config": result}


@router.get("/comparison")
@require_permission("ai.view_insights")
async def compare_models(
    model_types: List[str] = Query(..., description="Model types to compare"),
    metric: str = Query(
        "average_rating",
        regex="^(average_rating|success_rate|response_time|confidence_score)$",
    ),
    days: int = Query(30, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Compare performance across different models

    Requires permission: ai.view_insights
    """
    if len(model_types) < 2:
        raise HTTPException(
            status_code=400, detail="At least 2 model types required for comparison"
        )

    time_range = TimeRange.from_days(days)

    comparison = await feedback_analytics_service.compare_models(
        db=db,
        model_types=model_types,
        metric=metric,
        start_date=time_range.start_date,
        end_date=time_range.end_date,
    )

    return comparison


@router.get("/recommendations")
@require_permission("ai.view_insights")
async def get_improvement_recommendations(
    min_feedback_count: int = Query(50, ge=10),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get AI-powered recommendations for improving model performance

    Requires permission: ai.view_insights
    """
    recommendations = await feedback_analytics_service.get_improvement_recommendations(
        db=db, min_feedback_count=min_feedback_count
    )

    return {
        "generated_at": datetime.utcnow(),
        "recommendations": recommendations,
        "based_on_feedback_count": min_feedback_count,
    }
