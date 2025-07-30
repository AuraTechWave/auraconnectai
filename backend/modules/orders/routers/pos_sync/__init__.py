# backend/modules/orders/routers/pos_sync/__init__.py

"""
POS sync router module.

Provides simplified sync endpoints for POS terminals.
"""

from fastapi import APIRouter
from .manual_sync import router as manual_sync_router
from .status import router as status_router

# Create main router
router = APIRouter(prefix="/pos", tags=["pos-sync"])

# Include sub-routers
router.include_router(manual_sync_router)
router.include_router(status_router)

__all__ = ["router"]