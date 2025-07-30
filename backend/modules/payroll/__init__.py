# backend/modules/payroll/__init__.py

"""
Payroll Module - Phase 3: Payroll Engine (AUR-305) & Phase 4: API & Schemas (AUR-306)

Comprehensive payroll processing module with:
- Tax calculation engine
- Payroll configuration management
- Employee payment tracking
- Multi-jurisdiction support
- Integration with staff and tax modules
- API v1 with batch processing, webhooks, and audit trail
"""

from .routes.payroll_routes import router as payroll_router
from .routes.v1.payroll_v1_routes import router as payroll_v1_router

__version__ = "4.0.0"
__all__ = ["payroll_router", "payroll_v1_router"]