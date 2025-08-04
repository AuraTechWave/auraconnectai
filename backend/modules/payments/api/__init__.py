# backend/modules/payments/api/__init__.py

from fastapi import APIRouter
from .payment_endpoints import router as payment_endpoints_router
from .split_bill_endpoints import router as split_bill_router

# Create main payment router
payment_router = APIRouter()

# Include sub-routers
payment_router.include_router(payment_endpoints_router)
payment_router.include_router(split_bill_router)

__all__ = ['payment_router']