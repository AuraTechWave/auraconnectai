# backend/modules/payroll/routes/__init__.py

"""
Payroll Module Routes Package

This package contains API routes for payroll-specific functionality:
- Tax calculation endpoints
- Payroll configuration management
- Employee payment management
- Tax rules and policy management
"""

from .payroll_routes import router as payroll_router
from .tax_calculation_routes import router as tax_calculation_router
from .configuration_routes import router as configuration_router
from .payment_routes import router as payment_router

__all__ = [
    "payroll_router",
    "tax_calculation_router", 
    "configuration_router",
    "payment_router"
]