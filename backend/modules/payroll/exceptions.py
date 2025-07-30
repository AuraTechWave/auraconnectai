# backend/modules/payroll/exceptions.py

"""
Custom exceptions for payroll module.
"""

from typing import Optional, List, Dict, Any
from .schemas.error_schemas import ErrorDetail, PayrollErrorCodes


class PayrollException(Exception):
    """Base exception for payroll module"""
    def __init__(
        self,
        message: str,
        code: str = PayrollErrorCodes.DATABASE_ERROR,
        details: Optional[List[ErrorDetail]] = None,
        status_code: int = 400
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or []
        self.status_code = status_code


class PayrollValidationError(PayrollException):
    """Validation error for payroll operations"""
    def __init__(self, message: str, field: Optional[str] = None, details: Optional[List[ErrorDetail]] = None):
        if field and not details:
            details = [ErrorDetail(field=field, message=message)]
        super().__init__(
            message=message,
            code=PayrollErrorCodes.INVALID_AMOUNT,
            details=details,
            status_code=422
        )


class PayrollCalculationError(PayrollException):
    """Error during payroll calculations"""
    def __init__(self, message: str, details: Optional[List[ErrorDetail]] = None):
        super().__init__(
            message=message,
            code=PayrollErrorCodes.TAX_CALCULATION_FAILED,
            details=details,
            status_code=400
        )


class PayrollConfigurationError(PayrollException):
    """Configuration-related errors"""
    def __init__(self, message: str, config_key: Optional[str] = None):
        details = []
        if config_key:
            details.append(ErrorDetail(field=config_key, message=message))
        super().__init__(
            message=message,
            code=PayrollErrorCodes.CONFIG_NOT_FOUND,
            details=details,
            status_code=404
        )


class PayrollNotFoundError(PayrollException):
    """Resource not found error"""
    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} with identifier {identifier} not found",
            code=PayrollErrorCodes.RECORD_NOT_FOUND,
            status_code=404
        )


class PayrollPermissionError(PayrollException):
    """Permission-related errors"""
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            message=message,
            code=PayrollErrorCodes.INSUFFICIENT_PERMISSIONS,
            status_code=403
        )


class PayrollBusinessRuleError(PayrollException):
    """Business rule violation errors"""
    def __init__(self, message: str, rule: str, details: Optional[List[ErrorDetail]] = None):
        super().__init__(
            message=message,
            code=f"PAYROLL_RULE_{rule.upper()}",
            details=details,
            status_code=400
        )


# New domain-specific exceptions for Phase 4

class BatchProcessingError(PayrollException):
    """Error during batch processing operations"""
    def __init__(self, message: str, job_id: Optional[str] = None, details: Optional[List[ErrorDetail]] = None):
        if job_id:
            message = f"Batch job {job_id}: {message}"
        super().__init__(
            message=message,
            code=PayrollErrorCodes.BATCH_PROCESSING_ERROR,
            details=details,
            status_code=500
        )


class JobNotFoundException(PayrollException):
    """Job not found error"""
    def __init__(self, job_id: str):
        super().__init__(
            message=f"Batch job {job_id} not found",
            code=PayrollErrorCodes.JOB_NOT_FOUND,
            status_code=404
        )


class JobCancellationError(PayrollException):
    """Error when cancelling a job"""
    def __init__(self, job_id: str, reason: str):
        super().__init__(
            message=f"Cannot cancel job {job_id}: {reason}",
            code=PayrollErrorCodes.JOB_CANCELLATION_FAILED,
            status_code=400
        )


class WebhookError(PayrollException):
    """Base webhook error"""
    def __init__(self, message: str, webhook_url: Optional[str] = None, status_code: int = 500):
        if webhook_url:
            message = f"Webhook {webhook_url}: {message}"
        super().__init__(
            message=message,
            code=PayrollErrorCodes.WEBHOOK_ERROR,
            status_code=status_code
        )


class WebhookDeliveryError(WebhookError):
    """Error delivering webhook notification"""
    def __init__(self, webhook_url: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        details = []
        if status_code:
            details.append(ErrorDetail(field="http_status", message=str(status_code)))
        if response_body:
            details.append(ErrorDetail(field="response", message=response_body[:200]))  # Truncate long responses
        
        super().__init__(
            message=f"Failed to deliver webhook: HTTP {status_code}" if status_code else "Failed to deliver webhook",
            webhook_url=webhook_url,
            status_code=500
        )
        self.details = details


class WebhookValidationError(WebhookError):
    """Webhook validation error"""
    def __init__(self, message: str, field: str):
        super().__init__(
            message=message,
            status_code=422
        )
        self.details = [ErrorDetail(field=field, message=message)]


class AuditLogError(PayrollException):
    """Error related to audit logging"""
    def __init__(self, message: str, operation: Optional[str] = None):
        if operation:
            message = f"Audit {operation}: {message}"
        super().__init__(
            message=message,
            code=PayrollErrorCodes.AUDIT_LOG_ERROR,
            status_code=500
        )


class AuditExportError(AuditLogError):
    """Error during audit log export"""
    def __init__(self, message: str, export_format: Optional[str] = None):
        if export_format:
            message = f"Export to {export_format}: {message}"
        super().__init__(
            message=message,
            operation="export"
        )


class DatabaseError(PayrollException):
    """Database operation error"""
    def __init__(self, message: str, operation: Optional[str] = None, details: Optional[List[ErrorDetail]] = None):
        if operation:
            message = f"Database {operation}: {message}"
        super().__init__(
            message=message,
            code=PayrollErrorCodes.DATABASE_ERROR,
            details=details,
            status_code=500
        )


class ConcurrencyError(PayrollException):
    """Concurrency/locking error"""
    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} {identifier} is locked by another operation",
            code=PayrollErrorCodes.RESOURCE_LOCKED,
            status_code=409
        )