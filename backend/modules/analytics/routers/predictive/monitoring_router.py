# backend/modules/analytics/routers/predictive/monitoring_router.py

"""
Forecast monitoring and accuracy tracking endpoints.

Handles forecast performance tracking and model evaluation.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
import logging

from core.database import get_db
from core.auth import get_current_user
from modules.staff.models.staff_models import StaffMember
from modules.analytics.schemas.predictive_analytics_schemas import (
    ForecastComparison,
    ForecastAccuracyReport,
    ModelPerformanceReport,
    PredictionAlert,
)
from modules.analytics.services.forecast_monitoring_service import (
    ForecastMonitoringService,
)
from modules.analytics.services.permissions_service import require_analytics_permission
from modules.analytics.constants import (
    MIN_ACCURACY_THRESHOLD,
    ANOMALY_DETECTION_WINDOW_DAYS,
    MAX_HISTORICAL_DAYS,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/monitoring", tags=["predictive-monitoring"])


class TrackAccuracyRequest(BaseModel):
    """Request model for tracking forecast accuracy"""

    entity_type: str
    entity_id: Optional[int] = None
    predictions: List[Dict[str, Any]]
    actuals: List[Dict[str, Any]]


@router.post("/accuracy/track", response_model=ForecastComparison)
async def track_forecast_accuracy(
    request: TrackAccuracyRequest,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user),
) -> ForecastComparison:
    """
    Track and compare forecast accuracy against actual values.

    Args:
        entity_type: Type of entity (product, category, overall)
        entity_id: Specific entity ID (optional)
        predictions: List of predicted values with timestamps
        actuals: List of actual values with timestamps

    Returns:
        ForecastComparison with accuracy metrics

    Example Response:
        {
            "entity_type": "product",
            "entity_id": 1,
            "comparison_period": {
                "start": "2024-01-01",
                "end": "2024-01-31"
            },
            "predictions": [...],
            "actuals": [...],
            "accuracy_metrics": {
                "mae": 5.2,
                "mape": 8.5,
                "rmse": 7.1,
                "bias": -0.5,
                "r_squared": 0.85,
                "directional_accuracy": 0.78
            },
            "deviation_analysis": {
                "max_over_prediction": {"date": "2024-01-15", "value": 15.3},
                "max_under_prediction": {"date": "2024-01-20", "value": -12.1},
                "systematic_bias": "slight_under_prediction",
                "confidence_interval_accuracy": 0.92
            }
        }

    Raises:
        HTTPException: 400 if data mismatch, 403 if unauthorized
    """
    require_analytics_permission(current_user, "view_analytics_reports")

    try:
        service = ForecastMonitoringService(db)
        comparison = await service.track_forecast_accuracy(
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            predictions=request.predictions,
            actuals=request.actuals,
        )

        logger.info(
            f"Forecast accuracy tracked for {request.entity_type} {request.entity_id} "
            f"by user {current_user.id}"
        )

        return comparison

    except ValueError as e:
        logger.warning(f"Invalid accuracy tracking request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Accuracy tracking failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to track forecast accuracy."
        )


@router.get("/accuracy/report", response_model=ForecastAccuracyReport)
async def get_accuracy_report(
    entity_type: str = Query(..., description="Entity type to report on"),
    entity_id: Optional[int] = Query(None, description="Specific entity ID"),
    start_date: date = Query(..., description="Report start date"),
    end_date: date = Query(..., description="Report end date"),
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user),
) -> ForecastAccuracyReport:
    """
    Generate comprehensive forecast accuracy report.

    Args:
        entity_type: Type of entity to analyze
        entity_id: Specific entity (optional)
        start_date: Report period start
        end_date: Report period end

    Returns:
        ForecastAccuracyReport with detailed metrics

    Example Response:
        {
            "entity_type": "product",
            "entity_id": 1,
            "period": {"start": "2024-01-01", "end": "2024-01-31"},
            "overall_metrics": {
                "mean_accuracy": 91.5,
                "median_accuracy": 93.2,
                "std_deviation": 5.8
            },
            "model_performance": {
                "arima": {"accuracy": 89.5, "sample_size": 20},
                "ensemble": {"accuracy": 93.5, "sample_size": 10}
            },
            "time_based_analysis": {
                "weekday_accuracy": 92.1,
                "weekend_accuracy": 89.8,
                "trend": "improving"
            },
            "recommendations": [
                "Consider using ensemble model for better accuracy",
                "Weekend predictions need improvement"
            ]
        }
    """
    require_analytics_permission(current_user, "view_analytics_reports")

    # Validate date range
    if (end_date - start_date).days > MAX_HISTORICAL_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"Date range cannot exceed {MAX_HISTORICAL_DAYS} days",
        )

    try:
        service = ForecastMonitoringService(db)
        report = await service.generate_accuracy_report(
            entity_type=entity_type,
            entity_id=entity_id,
            start_date=start_date,
            end_date=end_date,
        )

        return report

    except Exception as e:
        logger.error(f"Accuracy report generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to generate accuracy report."
        )


@router.get("/performance/models", response_model=ModelPerformanceReport)
async def get_model_performance(
    days: int = Query(30, ge=7, le=365, description="Days of history to analyze"),
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user),
) -> ModelPerformanceReport:
    """
    Compare performance across different forecasting models.

    Args:
        days: Number of historical days to analyze

    Returns:
        ModelPerformanceReport with comparative metrics

    Example Response:
        {
            "evaluation_period": {"start": "2024-01-01", "end": "2024-01-31"},
            "models": [
                {
                    "model_type": "ensemble",
                    "usage_count": 150,
                    "avg_accuracy": 92.5,
                    "best_accuracy": 98.2,
                    "worst_accuracy": 81.3,
                    "computation_time_ms": 250
                }
            ],
            "best_performing_model": "ensemble",
            "recommendations": {
                "short_term": "moving_average",
                "medium_term": "exponential_smoothing",
                "long_term": "ensemble"
            }
        }
    """
    require_analytics_permission(current_user, "view_analytics_reports")

    try:
        service = ForecastMonitoringService(db)
        report = await service.compare_model_performance(days=days)

        return report

    except Exception as e:
        logger.error(f"Model performance report failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to generate model performance report."
        )


@router.get("/alerts/anomalies", response_model=List[PredictionAlert])
async def get_forecast_anomalies(
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    recent_days: int = Query(
        ANOMALY_DETECTION_WINDOW_DAYS,
        ge=1,
        le=30,
        description="Days to check for anomalies",
    ),
    min_severity: str = Query(
        "medium", description="Minimum severity: low, medium, high"
    ),
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user),
) -> List[PredictionAlert]:
    """
    Detect and retrieve forecast anomalies and accuracy degradations.

    Args:
        entity_type: Filter by entity type
        recent_days: Number of recent days to analyze
        min_severity: Minimum alert severity to return

    Returns:
        List of prediction alerts

    Example Response:
        [
            {
                "alert_id": "550e8400-e29b-41d4-a716-446655440000",
                "alert_type": "accuracy_degradation",
                "severity": "high",
                "entity_id": 5,
                "entity_name": "Cappuccino",
                "message": "Forecast accuracy dropped from 92% to 75%",
                "detected_at": "2024-02-01T10:30:00",
                "predicted_impact": {
                    "potential_stockout": true,
                    "revenue_impact": -500.00
                },
                "recommended_actions": [
                    "Review recent sales patterns",
                    "Consider model retraining",
                    "Manually adjust forecasts"
                ]
            }
        ]
    """
    require_analytics_permission(current_user, "view_analytics_reports")

    try:
        service = ForecastMonitoringService(db)

        # Get anomalies for all or specific entity types
        alerts = []

        if entity_type:
            entity_alerts = await service.detect_forecast_anomalies(
                entity_type=entity_type, entity_id=None, recent_days=recent_days
            )
            alerts.extend(entity_alerts)
        else:
            # Check all entity types
            for etype in ["product", "category", "overall"]:
                entity_alerts = await service.detect_forecast_anomalies(
                    entity_type=etype, entity_id=None, recent_days=recent_days
                )
                alerts.extend(entity_alerts)

        # Filter by severity
        severity_order = {"low": 1, "medium": 2, "high": 3}
        min_severity_level = severity_order.get(min_severity, 2)

        filtered_alerts = [
            alert
            for alert in alerts
            if severity_order.get(alert.severity, 0) >= min_severity_level
        ]

        return filtered_alerts

    except Exception as e:
        logger.error(f"Anomaly detection failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to detect forecast anomalies."
        )


@router.post("/retrain", response_model=dict)
async def trigger_model_retrain(
    entity_type: str,
    entity_id: Optional[int] = None,
    model_type: Optional[str] = None,
    reason: str = Query(..., description="Reason for retraining"),
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user),
) -> dict:
    """
    Trigger model retraining for specific entity.

    Args:
        entity_type: Type of entity
        entity_id: Specific entity ID
        model_type: Specific model to retrain
        reason: Reason for retraining

    Returns:
        Retraining task information

    Example Response:
        {
            "task_id": "retrain-550e8400-e29b-41d4",
            "status": "scheduled",
            "entity_type": "product",
            "entity_id": 5,
            "model_type": "ensemble",
            "scheduled_at": "2024-02-01T11:00:00",
            "estimated_completion": "2024-02-01T11:05:00",
            "reason": "Accuracy degradation detected"
        }
    """
    require_analytics_permission(current_user, "manage_analytics")

    try:
        service = ForecastMonitoringService(db)

        # TODO: Implement async task queue for model retraining
        task_info = await service.schedule_model_retrain(
            entity_type=entity_type,
            entity_id=entity_id,
            model_type=model_type,
            reason=reason,
            triggered_by=current_user.id,
        )

        logger.info(
            f"Model retraining scheduled for {entity_type} {entity_id} "
            f"by user {current_user.id}: {reason}"
        )

        return task_info

    except Exception as e:
        logger.error(f"Failed to schedule retraining: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to schedule model retraining."
        )
