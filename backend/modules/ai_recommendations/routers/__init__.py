# backend/modules/ai_recommendations/routers/__init__.py

from fastapi import APIRouter
from .pricing_router import router as pricing_router
from .staffing_router import router as staffing_router

# Create main router for AI recommendations
router = APIRouter(prefix="/ai-recommendations", tags=["AI Recommendations"])

# Include sub-routers
router.include_router(pricing_router)
router.include_router(staffing_router)

__all__ = ["router"]