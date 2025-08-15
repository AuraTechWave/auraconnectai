# backend/modules/orders/routers/external_pos_webhook_router.py

"""
Main router that combines all webhook sub-routers.

This module imports and combines the modular webhook routers.
"""

from fastapi import APIRouter

from .webhook.events_router import router as events_router

# Create the main router that will be included in the app
router = APIRouter()

# Include the events router (for receiving webhooks)
router.include_router(events_router)

# Note: The other routers (health, providers, monitoring) are included
# via webhook_monitoring_router.py to maintain backward compatibility
