# backend/modules/payroll/schemas/error_schemas.py

"""
Error response schemas for structured error handling.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class ErrorDetail(BaseModel):
    """Detailed error information"""

    field: Optional[str] = None
    message: str
    code: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standardized error response"""

    error: str = Field(..., description="Error type or category")
    message: str = Field(..., description="Human-readable error message")
    code: str = Field(..., description="Machine-readable error code")
    details: Optional[List[ErrorDetail]] = Field(
        None, description="Additional error details"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "Invalid request parameters",
                "code": "PAYROLL_VALIDATION_ERROR",
                "details": [
                    {
                        "field": "gross_amount",
                        "message": "Must be a positive number",
                        "code": "INVALID_AMOUNT",
                    }
                ],
                "timestamp": "2025-01-30T12:00:00Z",
            }
        }


class PayrollErrorCodes:
    """Centralized error codes for payroll module"""

    # Validation errors
    INVALID_AMOUNT = "PAYROLL_INVALID_AMOUNT"
    INVALID_DATE_RANGE = "PAYROLL_INVALID_DATE_RANGE"
    INVALID_EMPLOYEE_ID = "PAYROLL_INVALID_EMPLOYEE_ID"
    INVALID_TAX_LOCATION = "PAYROLL_INVALID_TAX_LOCATION"

    # Business logic errors
    DUPLICATE_PAY_POLICY = "PAYROLL_DUPLICATE_PAY_POLICY"
    NO_PAY_POLICY = "PAYROLL_NO_PAY_POLICY"
    PAYMENT_ALREADY_PROCESSED = "PAYROLL_PAYMENT_ALREADY_PROCESSED"
    INSUFFICIENT_HOURS = "PAYROLL_INSUFFICIENT_HOURS"

    # Tax calculation errors
    TAX_CALCULATION_FAILED = "PAYROLL_TAX_CALCULATION_FAILED"
    NO_TAX_RULES = "PAYROLL_NO_TAX_RULES"
    INVALID_TAX_JURISDICTION = "PAYROLL_INVALID_TAX_JURISDICTION"

    # Configuration errors
    CONFIG_NOT_FOUND = "PAYROLL_CONFIG_NOT_FOUND"
    INVALID_CONFIG_VALUE = "PAYROLL_INVALID_CONFIG_VALUE"

    # Database errors
    DATABASE_ERROR = "PAYROLL_DATABASE_ERROR"
    RECORD_NOT_FOUND = "PAYROLL_RECORD_NOT_FOUND"

    # Permission errors
    UNAUTHORIZED = "PAYROLL_UNAUTHORIZED"
    INSUFFICIENT_PERMISSIONS = "PAYROLL_INSUFFICIENT_PERMISSIONS"

    # Batch processing errors
    BATCH_PROCESSING_ERROR = "PAYROLL_BATCH_PROCESSING_ERROR"
    JOB_NOT_FOUND = "PAYROLL_JOB_NOT_FOUND"
    JOB_CANCELLATION_FAILED = "PAYROLL_JOB_CANCELLATION_FAILED"

    # Webhook errors
    WEBHOOK_ERROR = "PAYROLL_WEBHOOK_ERROR"
    WEBHOOK_DELIVERY_FAILED = "PAYROLL_WEBHOOK_DELIVERY_FAILED"
    WEBHOOK_VALIDATION_ERROR = "PAYROLL_WEBHOOK_VALIDATION_ERROR"
    DUPLICATE_WEBHOOK = "PAYROLL_DUPLICATE_WEBHOOK"

    # Audit errors
    AUDIT_LOG_ERROR = "PAYROLL_AUDIT_LOG_ERROR"
    AUDIT_EXPORT_ERROR = "PAYROLL_AUDIT_EXPORT_ERROR"

    # Concurrency errors
    RESOURCE_LOCKED = "PAYROLL_RESOURCE_LOCKED"

    # Generic errors
    INVALID_DATA_FORMAT = "PAYROLL_INVALID_DATA_FORMAT"
    DUPLICATE_RECORD = "PAYROLL_DUPLICATE_RECORD"
