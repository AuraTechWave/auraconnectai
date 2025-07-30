# backend/modules/payroll/routes/v1/audit/__init__.py

"""
Audit module routes.

Aggregates all audit-related endpoints.
"""

from fastapi import APIRouter
from .logs_routes import router as logs_router
from .summary_routes import router as summary_router
from .compliance_routes import router as compliance_router

# Create main audit router
router = APIRouter()

# Include sub-routers
router.include_router(logs_router, prefix="/logs", tags=["Audit Logs"])
router.include_router(summary_router, prefix="", tags=["Audit Summary"])
router.include_router(compliance_router, prefix="/compliance", tags=["Audit Compliance"])

__all__ = ["router"]