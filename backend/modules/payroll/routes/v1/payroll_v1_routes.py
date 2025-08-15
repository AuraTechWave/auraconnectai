# backend/modules/payroll/routes/v1/payroll_v1_routes.py

"""
Main payroll API v1 router with versioning support.

Aggregates all v1 payroll endpoints with proper versioning.
"""

from fastapi import APIRouter
from datetime import datetime

# Import existing routers
from ..tax_calculation_routes import router as tax_router
from ..configuration_routes import router as config_router
from ..payment_routes import router as payment_router

# Import new v1-specific routers
from .batch_processing_routes import router as batch_router
from .webhook_routes import router as webhook_router
from .audit_routes import router as audit_router

# Create v1 router with version prefix
router = APIRouter(prefix="/api/v1/payroll", tags=["Payroll v1"])

# Include all sub-routers
router.include_router(tax_router, prefix="/tax", tags=["Tax Calculations"])
router.include_router(config_router, prefix="/config", tags=["Configuration"])
router.include_router(payment_router, prefix="/payments", tags=["Payments"])
router.include_router(batch_router, prefix="/batch", tags=["Batch Processing"])
router.include_router(webhook_router, prefix="/webhooks", tags=["Webhooks"])
router.include_router(audit_router, prefix="/audit", tags=["Audit Trail"])


@router.get("/health")
async def payroll_health_check_v1():
    """
    Health check endpoint for payroll module v1.

    Returns:
        dict: Health status with version information
    """
    return {
        "status": "healthy",
        "module": "payroll",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/info")
async def payroll_api_info():
    """
    Get API information and capabilities.

    Returns:
        dict: API version, features, and deprecation notices
    """
    return {
        "version": "1.0.0",
        "release_date": "2025-01-30",
        "features": [
            "Tax calculations with multi-jurisdiction support",
            "Payroll configuration management",
            "Employee payment tracking",
            "Batch payroll processing",
            "Webhook integrations",
            "Comprehensive audit trail",
            "Export capabilities",
            "Background task processing",
        ],
        "deprecation_warnings": [],
        "rate_limits": {
            "tax_calculations": "100 requests/minute",
            "batch_processing": "10 requests/hour",
            "exports": "3 concurrent requests",
        },
        "documentation": "/docs#/Payroll%20v1",
        "support": "payroll-api@auraconnect.ai",
    }
