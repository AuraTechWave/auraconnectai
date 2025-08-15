# backend/modules/kds/routes/__init__.py

"""
Kitchen Display System routes.
"""

from fastapi import APIRouter
from .kds_routes import router as kds_router
from .kds_performance_routes import router as performance_router
from .kds_realtime_routes import router as realtime_router

# Create main router
router = APIRouter(tags=["Kitchen Display System"])

# Include sub-routers (no prefix needed as they already define full paths)
router.include_router(kds_router)
router.include_router(performance_router)
router.include_router(realtime_router)

__all__ = ["router"]