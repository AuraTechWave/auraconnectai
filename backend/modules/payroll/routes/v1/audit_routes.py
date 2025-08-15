# backend/modules/payroll/routes/v1/audit_routes.py

"""
Audit trail endpoints for payroll operations.

This module has been refactored into smaller sub-modules for better maintainability.
It now acts as an aggregator for all audit-related endpoints.
"""

from .audit import router

# Export the aggregated router
__all__ = ["router"]
