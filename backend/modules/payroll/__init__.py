# backend/modules/payroll/__init__.py

"""
Payroll Module - Phase 3: Payroll Engine (AUR-305)

Comprehensive payroll processing module with:
- Tax calculation engine
- Payroll configuration management
- Employee payment tracking
- Multi-jurisdiction support
- Integration with staff and tax modules
"""

from .routes.payroll_routes import router as payroll_router

__version__ = "3.0.0"
__all__ = ["payroll_router"]