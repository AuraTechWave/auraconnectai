# backend/modules/analytics/routers/ai_insights_router.py

import logging
from typing import Optional, List
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status, Query

from backend.core.database import get_db
from backend.core.auth import get_current_staff_user
from backend.modules.staff.models.staff_models import StaffMember
from ..services.permissions_service import (
    AnalyticsPermission, PermissionsService, require_analytics_permission
)
from sqlalchemy.orm import Session

from ..schemas.ai_insights_schemas import (
    InsightRequest, InsightResponse, AIInsightSummary,
    InsightType, ConfidenceLevel
)
from ..services.ai_insights_service import create_ai_insights_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ai-insights",
    tags=["Analytics AI Insights"]
)


@router.post("/generate", response_model=InsightResponse)
async def generate_ai_insights(
    request: InsightRequest,
    current_user: dict = Depends(require_analytics_permission(AnalyticsPermission.VIEW_DASHBOARD)),
    db: Session = Depends(get_db)
):
    """
    Generate AI-powered analytics insights based on historical data.
    
    This endpoint analyzes business data to provide:
    - Peak time analysis for optimal staffing
    - Product trend predictions
    - Customer behavior patterns
    - Seasonal pattern detection
    - Anomaly detection
    
    Requires 'analytics_view' permission.
    """
    # Permission already checked by require_analytics_permission decorator
    
    try:
        start_time = datetime.now()
        
        # Create service instance
        insights_service = create_ai_insights_service(db)
        
        # Generate insights
        insights = await insights_service.generate_insights(request)
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Check if results were cached
        cache_hit = processing_time < 0.1  # Assume cached if very fast
        
        # Build response
        response = InsightResponse(
            success=True,
            insights=insights,
            processing_time=processing_time,
            cache_hit=cache_hit,
            warnings=[]
        )
        
        # Add warnings if confidence is low
        if insights.peak_times and insights.peak_times.confidence == ConfidenceLevel.LOW:
            response.warnings.append("Peak time analysis has low confidence due to limited data")
        
        if insights.product_insights and insights.product_insights.confidence == ConfidenceLevel.LOW:
            response.warnings.append("Product trend analysis has low confidence due to limited data")
        
        return response
        
    except Exception as e:
        logger.error(f"Error generating AI insights: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate AI insights"
        )


@router.get("/peak-times", response_model=InsightResponse)
async def get_peak_time_insights(
    date_from: Optional[date] = Query(None, description="Start date for analysis"),
    date_to: Optional[date] = Query(None, description="End date for analysis"),
    force_refresh: bool = Query(False, description="Force regeneration of insights"),
    current_user: dict = Depends(require_analytics_permission(AnalyticsPermission.VIEW_DASHBOARD)),
    db: Session = Depends(get_db)
):
    """
    Get AI insights specifically for peak business hours.
    
    Analyzes order patterns to identify:
    - Primary and secondary peak hours
    - Quiet periods for reduced staffing
    - Weekly patterns by day
    - Staffing recommendations
    """
    # Permission already checked by require_analytics_permission decorator
    
    # Build request
    request = InsightRequest(
        insight_types=[InsightType.PEAK_TIME],
        date_from=date_from,
        date_to=date_to,
        force_refresh=force_refresh
    )
    
    return await generate_ai_insights(request, current_user, db)


@router.get("/product-trends", response_model=InsightResponse)
async def get_product_trend_insights(
    date_from: Optional[date] = Query(None, description="Start date for analysis"),
    date_to: Optional[date] = Query(None, description="End date for analysis"),
    force_refresh: bool = Query(False, description="Force regeneration of insights"),
    current_user: dict = Depends(require_analytics_permission(AnalyticsPermission.VIEW_DASHBOARD)),
    db: Session = Depends(get_db)
):
    """
    Get AI insights for product performance trends.
    
    Analyzes product sales to identify:
    - Rising products to stock up on
    - Declining products needing promotion
    - Stable performers
    - New trending items
    - Demand predictions
    """
    # Permission already checked by require_analytics_permission decorator
    
    # Build request
    request = InsightRequest(
        insight_types=[InsightType.PRODUCT_TREND],
        date_from=date_from,
        date_to=date_to,
        force_refresh=force_refresh
    )
    
    return await generate_ai_insights(request, current_user, db)


@router.get("/customer-patterns", response_model=InsightResponse)
async def get_customer_pattern_insights(
    date_from: Optional[date] = Query(None, description="Start date for analysis"),
    date_to: Optional[date] = Query(None, description="End date for analysis"),
    force_refresh: bool = Query(False, description="Force regeneration of insights"),
    current_user: dict = Depends(require_analytics_permission(AnalyticsPermission.VIEW_DASHBOARD)),
    db: Session = Depends(get_db)
):
    """
    Get AI insights for customer behavior patterns.
    
    Analyzes customer data to identify:
    - Repeat customer rates
    - Order frequency patterns
    - At-risk customer segments
    - Lifetime value trends
    - Retention recommendations
    """
    # Permission already checked by require_analytics_permission decorator
    
    # Build request
    request = InsightRequest(
        insight_types=[InsightType.CUSTOMER_PATTERN],
        date_from=date_from,
        date_to=date_to,
        force_refresh=force_refresh
    )
    
    return await generate_ai_insights(request, current_user, db)


@router.get("/comprehensive", response_model=InsightResponse)
async def get_comprehensive_insights(
    date_from: Optional[date] = Query(None, description="Start date for analysis"),
    date_to: Optional[date] = Query(None, description="End date for analysis"),
    min_confidence: ConfidenceLevel = Query(ConfidenceLevel.MEDIUM, description="Minimum confidence level"),
    force_refresh: bool = Query(False, description="Force regeneration of insights"),
    current_user: dict = Depends(require_analytics_permission(AnalyticsPermission.VIEW_DASHBOARD)),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive AI insights covering all analysis types.
    
    Includes:
    - Peak time analysis
    - Product trends
    - Customer patterns
    - Seasonality detection
    - Anomaly detection
    - Overall business recommendations
    """
    # Permission already checked by require_analytics_permission decorator
    
    # Build request for all insight types
    request = InsightRequest(
        insight_types=[
            InsightType.PEAK_TIME,
            InsightType.PRODUCT_TREND,
            InsightType.CUSTOMER_PATTERN,
            InsightType.SEASONALITY,
            InsightType.ANOMALY
        ],
        date_from=date_from,
        date_to=date_to,
        min_confidence=min_confidence,
        force_refresh=force_refresh
    )
    
    return await generate_ai_insights(request, current_user, db)


@router.get("/anomalies", response_model=InsightResponse)
async def get_anomaly_insights(
    date_from: Optional[date] = Query(None, description="Start date for analysis"),
    date_to: Optional[date] = Query(None, description="End date for analysis"),
    severity: Optional[str] = Query(None, description="Filter by severity (high, medium, low)"),
    current_user: dict = Depends(require_analytics_permission(AnalyticsPermission.VIEW_DASHBOARD)),
    db: Session = Depends(get_db)
):
    """
    Get AI-detected anomalies in business metrics.
    
    Detects:
    - Revenue spikes or drops
    - Unusual order patterns
    - Statistical outliers
    - Potential causes
    """
    # Permission already checked by require_analytics_permission decorator
    
    # Build request
    request = InsightRequest(
        insight_types=[InsightType.ANOMALY],
        date_from=date_from,
        date_to=date_to,
        force_refresh=True  # Always fresh for anomaly detection
    )
    
    # Generate insights
    response = await generate_ai_insights(request, current_user, db)
    
    # Filter by severity if requested
    if severity and response.insights.anomalies:
        response.insights.anomalies = [
            a for a in response.insights.anomalies 
            if a.severity.lower() == severity.lower()
        ]
    
    return response


@router.get("/seasonality", response_model=InsightResponse)
async def get_seasonality_insights(
    months_of_data: int = Query(12, ge=3, le=36, description="Months of historical data to analyze"),
    current_user: dict = Depends(require_analytics_permission(AnalyticsPermission.VIEW_DASHBOARD)),
    db: Session = Depends(get_db)
):
    """
    Get AI insights for seasonal patterns.
    
    Analyzes historical data to identify:
    - Monthly/quarterly patterns
    - Seasonal products
    - Revenue multipliers by season
    - Forecast accuracy
    """
    # Permission already checked by require_analytics_permission decorator
    
    # Calculate date range
    end_date = datetime.now().date()
    start_date = date(end_date.year, end_date.month, 1)
    
    # Go back specified months
    for _ in range(months_of_data - 1):
        if start_date.month == 1:
            start_date = date(start_date.year - 1, 12, 1)
        else:
            start_date = date(start_date.year, start_date.month - 1, 1)
    
    # Build request
    request = InsightRequest(
        insight_types=[InsightType.SEASONALITY],
        date_from=start_date,
        date_to=end_date,
        force_refresh=False
    )
    
    return await generate_ai_insights(request, current_user, db)


# Export router
__all__ = ["router"]