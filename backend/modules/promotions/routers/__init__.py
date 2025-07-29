# backend/modules/promotions/routers/__init__.py

from fastapi import APIRouter
from .promotion_router import router as promotion_router
from .coupon_router import router as coupon_router
from .referral_router import router as referral_router
from .analytics_router import router as analytics_router
from .scheduling_router import router as scheduling_router
from .automation_router import router as automation_router
from .ab_testing_router import router as ab_testing_router

# Create main promotions router
router = APIRouter(prefix="/api/v1", tags=["promotions"])

# Include all sub-routers
router.include_router(promotion_router)
router.include_router(coupon_router)
router.include_router(referral_router)
router.include_router(analytics_router)
router.include_router(scheduling_router)
router.include_router(automation_router)
router.include_router(ab_testing_router)

__all__ = ["router"]