# backend/modules/payroll/routes/payroll_routes.py

"""
Main payroll routes combining all payroll module endpoints.

This router aggregates all payroll-related endpoints:
- Tax calculations
- Configuration management
- Payment records
- Tax rules and policies
"""

from fastapi import APIRouter
from datetime import datetime
from .tax_calculation_routes import router as tax_calculation_router
from .configuration_routes import router as configuration_router
from .payment_routes import router as payment_router

# Create main payroll router
router = APIRouter(prefix="/api/payroll", tags=["Payroll"])

# Include sub-routers
router.include_router(tax_calculation_router, prefix="/tax", tags=["Payroll Tax"])
router.include_router(
    configuration_router, prefix="/config", tags=["Payroll Configuration"]
)
router.include_router(payment_router, prefix="/payments", tags=["Payroll Payments"])


@router.get("/health")
async def payroll_health_check():
    """
    Health check endpoint for payroll module.

    Returns:
        dict: Health status of payroll module
    """
    return {
        "status": "healthy",
        "module": "payroll",
        "timestamp": datetime.utcnow().isoformat(),
    }
