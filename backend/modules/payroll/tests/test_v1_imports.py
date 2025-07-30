# backend/modules/payroll/tests/test_v1_imports.py

"""
Test file to verify all v1 imports work correctly.
"""

import pytest


def test_v1_imports():
    """Test that all v1 components can be imported."""
    # Test route imports
    from ..routes.v1.payroll_v1_routes import router as v1_router
    from ..routes.v1.batch_processing_routes import router as batch_router
    from ..routes.v1.webhook_routes import router as webhook_router
    from ..routes.v1.audit_routes import router as audit_router
    
    # Test schema imports
    from ..schemas.batch_processing_schemas import (
        BatchPayrollRequest,
        BatchPayrollResponse,
        BatchJobStatus,
        EmployeePayrollResult
    )
    
    from ..schemas.webhook_schemas import (
        WebhookEventType,
        WebhookSubscriptionRequest,
        WebhookSubscriptionResponse
    )
    
    from ..schemas.audit_schemas import (
        AuditEventType,
        AuditLogEntry,
        AuditLogFilter
    )
    
    # Test service imports
    from ..services.batch_payroll_service import BatchPayrollService
    
    # Test model imports
    from ..models.payroll_configuration import (
        PayrollJobTracking,
        PayrollWebhookSubscription
    )
    
    from ..models.payroll_audit import PayrollAuditLog
    
    # Verify routers have expected attributes
    assert hasattr(v1_router, 'routes')
    assert hasattr(batch_router, 'routes')
    assert hasattr(webhook_router, 'routes')
    assert hasattr(audit_router, 'routes')
    
    # Verify enums
    assert WebhookEventType.PAYROLL_STARTED
    assert AuditEventType.PAYROLL_CALCULATED
    
    print("✅ All v1 imports working correctly!")


if __name__ == "__main__":
    test_v1_imports()