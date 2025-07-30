# backend/modules/orders/routers/webhook_monitoring_router.py

"""
Main monitoring router that combines all webhook monitoring sub-routers.

This module imports and combines the modular webhook monitoring routers.
"""

from fastapi import APIRouter

from .webhook.health_router import router as health_router
from .webhook.providers_router import router as providers_router
from .webhook.monitoring_router import router as monitoring_router

# Create the main router that will be included in the app
router = APIRouter()

# Include all sub-routers
router.include_router(health_router)
router.include_router(providers_router)
router.include_router(monitoring_router)