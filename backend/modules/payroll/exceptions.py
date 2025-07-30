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