# backend/modules/analytics/routers/predictive/forecasting_router.py

"""
Forecasting endpoints for predictive analytics.

Handles demand forecasting and time series predictions.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import logging

from core.database import get_db
from core.auth import get_current_user
from modules.staff.models.staff_models import StaffMember
from modules.analytics.schemas.predictive_analytics_schemas import (
    DemandForecastRequest,
    DemandForecast,
    BatchPredictionRequest,
    BatchForecastResult,
    ModelType,
    TimeGranularity,
)
from modules.analytics.services.demand_prediction_service import DemandPredictionService
from modules.analytics.services.permissions_service import require_analytics_permission
from modules.analytics.constants import (
    MAX_BATCH_SIZE,
    DEFAULT_HORIZON_DAYS,
    CACHE_TTL_SECONDS,
)
from modules.analytics.middleware.rate_limiter import rate_limit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/forecasting", tags=["predictive-forecasting"])


@router.post("/demand", response_model=DemandForecast)
async def forecast_demand(
    request: DemandForecastRequest,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user),
) -> DemandForecast:
    """
    Generate demand forecast for a specific entity.

    Args:
        request: Demand forecast parameters

    Returns:
        DemandForecast with predictions and confidence intervals

    Example Response:
        {
            "entity_id": 1,
            "entity_type": "product",
            "entity_name": "Latte",
            "predictions": [
                {
                    "timestamp": "2024-02-01T00:00:00",
                    "predicted_value": 125.5,
                    "lower_bound": 110.2,
                    "upper_bound": 140.8,
                    "confidence": 0.95
                }
            ],
            "metadata": {
                "model_used": "ensemble",
                "training_period_days": 90,
                "features_used": ["historical_demand", "seasonality", "trend"]
            },
            "insights": ["Increasing trend detected", "Weekend peaks observed"],
            "recommended_actions": ["Increase weekend inventory", "Monitor Tuesday demand"]
        }

    Raises:
        HTTPException: 400 if insufficient data, 403 if unauthorized
    """
    require_analytics_permission(current_user, "view_sales_analytics")

    try:
        service = DemandPredictionService(db)
        forecast = await service.forecast_demand(request)

        logger.info(
            f"Demand forecast generated for {request.entity_type} {request.entity_id} "
            f"by user {current_user.id}"
        )

        return forecast

    except ValueError as e:
        logger.warning(f"Invalid forecast request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Forecast generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate forecast. Please try again later.",
        )


@router.post("/batch", response_model=BatchForecastResult)
@rate_limit("batch_forecast", tokens=5)  # Batch requests consume more resources
async def batch_forecast(
    request: Request,
    batch_request: BatchPredictionRequest,
    background: bool = Query(False, description="Run as background task"),
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user),
) -> BatchForecastResult:
    """
    Generate forecasts for multiple entities in batch.

    Args:
        request: Batch forecast parameters
        background: Whether to run as background task

    Returns:
        BatchForecastResult with individual forecasts or task ID

    Example Response:
        {
            "forecasts": [
                {
                    "entity_id": 1,
                    "entity_type": "product",
                    "predictions": [...],
                    "status": "success"
                },
                {
                    "entity_id": 2,
                    "entity_type": "product",
                    "status": "failed",
                    "error": "Insufficient data"
                }
            ],
            "summary": {
                "total_requested": 2,
                "successful": 1,
                "failed": 1
            }
        }

    Raises:
        HTTPException: 400 if batch size exceeds limit
    """
    require_analytics_permission(current_user, "manage_analytics")

    if len(batch_request.entity_ids) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Batch size exceeds maximum limit of {MAX_BATCH_SIZE}",
        )

    try:
        service = DemandPredictionService(db)

        if background:
            # TODO: Implement async task queue (Celery/RQ)
            task_id = await service.schedule_batch_forecast(batch_request)
            return BatchForecastResult(
                task_id=task_id,
                status="scheduled",
                message=f"Batch forecast scheduled with task ID: {task_id}",
            )
        else:
            result = await service.batch_forecast(batch_request)
            return result

    except Exception as e:
        logger.error(f"Batch forecast failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Batch forecast failed. Please try again later."
        )


@router.get("/models", response_model=List[Dict[str, Any]])
async def list_available_models(
    current_user: StaffMember = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    List available forecasting models and their characteristics.

    Returns:
        List of model information with capabilities

    Example Response:
        [
            {
                "model_type": "arima",
                "name": "ARIMA",
                "description": "AutoRegressive Integrated Moving Average",
                "best_for": "Stationary time series with clear patterns",
                "min_data_points": 30,
                "supports_seasonality": true,
                "supports_external_factors": false
            }
        ]
    """
    require_analytics_permission(current_user, "view_sales_analytics")

    models = [
        {
            "model_type": ModelType.ARIMA,
            "name": "ARIMA",
            "description": "AutoRegressive Integrated Moving Average",
            "best_for": "Stationary time series with clear patterns",
            "min_data_points": 30,
            "supports_seasonality": True,
            "supports_external_factors": False,
        },
        {
            "model_type": ModelType.EXPONENTIAL_SMOOTHING,
            "name": "Exponential Smoothing",
            "description": "Weighted average with exponential decay",
            "best_for": "Time series with trend and seasonality",
            "min_data_points": 20,
            "supports_seasonality": True,
            "supports_external_factors": False,
        },
        {
            "model_type": ModelType.PROPHET,
            "name": "Prophet",
            "description": "Facebook's forecasting model",
            "best_for": "Multiple seasonalities and holidays",
            "min_data_points": 60,
            "supports_seasonality": True,
            "supports_external_factors": True,
        },
        {
            "model_type": ModelType.MOVING_AVERAGE,
            "name": "Moving Average",
            "description": "Simple or weighted moving average",
            "best_for": "Short-term forecasts with limited data",
            "min_data_points": 7,
            "supports_seasonality": False,
            "supports_external_factors": False,
        },
        {
            "model_type": ModelType.ENSEMBLE,
            "name": "Ensemble",
            "description": "Combination of multiple models",
            "best_for": "Maximum accuracy with sufficient data",
            "min_data_points": 60,
            "supports_seasonality": True,
            "supports_external_factors": True,
        },
    ]

    return models
