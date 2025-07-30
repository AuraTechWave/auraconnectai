# backend/modules/analytics/routers/pos/__init__.py

"""
POS Analytics router module.

Combines all POS analytics sub-routers.
"""

from fastapi import APIRouter
from .dashboard_routes import router as dashboard_router
from .details_routes import router as details_router
from .alerts_routes import router as alerts_router
from .export_routes import router as export_router

# Create main POS analytics router
router = APIRouter(prefix="/analytics/pos", tags=["POS Analytics"])

# Include all sub-routers
router.include_router(dashboard_router)
router.include_router(details_router)
router.include_router(alerts_router)
router.include_router(export_router)

__all__ = ["router"]