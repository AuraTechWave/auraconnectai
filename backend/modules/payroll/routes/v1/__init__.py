# backend/modules/payroll/routes/v1/__init__.py

"""
Payroll Module API v1 Routes Package

Version 1 of the payroll API providing:
- Tax calculation endpoints
- Payroll configuration management
- Employee payment management
- Batch processing capabilities
- Audit trail access
"""

from .payroll_v1_routes import router as payroll_v1_router

__all__ = ["payroll_v1_router"]