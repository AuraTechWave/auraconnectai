from fastapi import APIRouter
from .reservation_routes import router as reservation_router
from .waitlist_routes import router as waitlist_router
from .staff_reservation_routes import router as staff_router

# Create main router
router = APIRouter(prefix="/reservations", tags=["Reservations"])

# Include sub-routers
router.include_router(reservation_router)
router.include_router(waitlist_router, prefix="/waitlist", tags=["Waitlist"])
router.include_router(staff_router, prefix="/staff", tags=["Staff Reservations"])

__all__ = ["router"]
