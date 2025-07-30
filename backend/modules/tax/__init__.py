# backend/modules/tax/__init__.py

"""
Tax Services Module - Phase 2 (AUR-304)

Comprehensive tax management system with multi-jurisdiction support,
compliance automation, and external service integrations.
"""

from .routes.tax_routes import router as tax_router

__version__ = "2.0.0"
__all__ = ["tax_router"]