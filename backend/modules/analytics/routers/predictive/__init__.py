# backend/modules/analytics/routers/predictive/__init__.py

"""
Predictive analytics routers.

Modular routing for forecasting, stock optimization, and monitoring.
"""

from fastapi import APIRouter

from .forecasting_router import router as forecasting_router
from .stock_router import router as stock_router
from .monitoring_router import router as monitoring_router

# Create main predictive router
predictive_router = APIRouter(prefix="/predictive", tags=["predictive-analytics"])

# Include sub-routers
predictive_router.include_router(forecasting_router)
predictive_router.include_router(stock_router)
predictive_router.include_router(monitoring_router)

__all__ = ["predictive_router"]
