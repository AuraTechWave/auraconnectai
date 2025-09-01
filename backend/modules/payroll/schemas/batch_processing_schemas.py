# backend/modules/payroll/schemas/batch_processing_schemas.py

"""
Batch processing schemas for payroll API v1.

Provides request/response models for batch payroll operations
with job tracking and status monitoring.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


class CalculationOptions(BaseModel):
    """Options for payroll calculation processing."""

    include_bonuses: bool = Field(
        True, description="Include bonus calculations in payroll"
    )
    include_commissions: bool = Field(
        True, description="Include commission calculations in payroll"
    )
    include_overtime: bool = Field(True, description="Calculate overtime pay")
    include_deductions: bool = Field(True, description="Apply all deductions")
    force_recalculate: bool = Field(
        False, description="Force recalculation even if payroll exists"
    )
    use_cached_tax_rates: bool = Field(
        True, description="Use cached tax rates for performance"
    )


class BatchPayrollRequest(BaseModel):
    """Request schema for batch payroll processing."""

    employee_ids: Optional[List[int]] = Field(
        None,
        description="List of employee IDs to process. None means all active employees",
    )
    pay_period_start: date = Field(..., description="Start date of the pay period")
    pay_period_end: date = Field(..., description="End date of the pay period")
    calculation_options: Optional[CalculationOptions] = Field(
        None, description="Optional calculation settings"
    )
    notification_emails: Optional[List[str]] = Field(
        None, description="Email addresses to notify on completion"
    )
    priority: str = Field(
        "normal",
        pattern="^(low|normal|high|urgent)$",
        description="Processing priority",
    )

    @field_validator("pay_period_end")
    @classmethod
    def validate_period_end(cls, v, info):
        if "pay_period_start" in info.data and v <= info.data["pay_period_start"]:
            raise ValueError("pay_period_end must be after pay_period_start")
        return v

    @field_validator("employee_ids")
    @classmethod
    def validate_employee_ids(cls, v):
        if v is not None and len(v) == 0:
            raise ValueError("employee_ids cannot be an empty list")
        if v is not None and len(set(v)) != len(v):
            raise ValueError("employee_ids cannot contain duplicates")
        return v


class BatchPayrollResponse(BaseModel):
    """Response schema for batch payroll initiation."""

    job_id: str = Field(..., description="Unique identifier for the batch job")
    status: str = Field(..., description="Current job status")
    message: str = Field(..., description="Status message")
    employee_count: Optional[int] = Field(
        None, description="Number of employees to process"
    )
    estimated_completion_time: Optional[datetime] = Field(
        None, description="Estimated time of completion"
    )
    tracking_url: Optional[str] = Field(None, description="URL to track job progress")


class BatchJobStatus(BaseModel):
    """Status information for a batch job."""

    job_id: str = Field(..., description="Batch job identifier")
    status: str = Field(
        ...,
        description="Current job status (pending, processing, completed, failed, cancelled)",
    )
    progress: float = Field(..., ge=0, le=100, description="Progress percentage")
    started_at: datetime = Field(..., description="Job start time")
    completed_at: Optional[datetime] = Field(None, description="Job completion time")
    total_employees: int = Field(..., description="Total employees to process")
    processed_employees: int = Field(..., description="Number of employees processed")
    successful_count: int = Field(..., description="Number of successful calculations")
    failed_count: int = Field(..., description="Number of failed calculations")
    error_message: Optional[str] = Field(
        None, description="Error message if job failed"
    )
    estimated_time_remaining: Optional[int] = Field(
        None, description="Estimated seconds remaining"
    )


class EmployeePayrollResult(BaseModel):
    """Individual employee payroll result."""

    employee_id: int = Field(..., description="Employee ID")
    employee_name: str = Field(..., description="Employee full name")
    success: bool = Field(..., description="Whether payroll calculation succeeded")
    gross_amount: Decimal = Field(..., description="Calculated gross pay")
    net_amount: Decimal = Field(..., description="Calculated net pay")
    total_deductions: Decimal = Field(..., description="Total deductions applied")
    payment_id: Optional[int] = Field(None, description="Generated payment record ID")
    error_message: Optional[str] = Field(
        None, description="Error message if calculation failed"
    )
    processing_time: float = Field(..., description="Processing time in seconds")

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class BatchJobDetail(BaseModel):
    """Detailed information about a batch job."""

    job_id: str = Field(..., description="Batch job identifier")
    status: str = Field(..., description="Current job status")
    started_at: datetime = Field(..., description="Job start time")
    completed_at: Optional[datetime] = Field(None, description="Job completion time")
    request_parameters: Dict[str, Any] = Field(
        ..., description="Original request parameters"
    )
    summary: Dict[str, Any] = Field(..., description="Summary statistics")
    employee_results: Optional[List[EmployeePayrollResult]] = Field(
        None, description="Individual employee results (if requested)"
    )
    error_details: Optional[str] = Field(None, description="Detailed error information")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional job metadata"
    )


class BatchJobHistoryItem(BaseModel):
    """History item for batch job listing."""

    job_id: str = Field(..., description="Batch job identifier")
    status: str = Field(..., description="Job status")
    started_at: datetime = Field(..., description="Job start time")
    completed_at: Optional[datetime] = Field(None, description="Job completion time")
    employee_count: int = Field(..., description="Number of employees processed")
    successful: int = Field(..., description="Number of successful calculations")
    failed: int = Field(..., description="Number of failed calculations")
    total_gross: Optional[Decimal] = Field(
        None, description="Total gross pay calculated"
    )
    total_net: Optional[Decimal] = Field(None, description="Total net pay calculated")
    created_by: Optional[str] = Field(None, description="User who created the job")

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class BatchJobHistoryResponse(BaseModel):
    """Response for batch job history listing."""

    total: int = Field(..., description="Total number of jobs")
    limit: int = Field(..., description="Results per page")
    offset: int = Field(..., description="Results offset")
    jobs: List[BatchJobHistoryItem] = Field(..., description="List of batch jobs")
    filters_applied: Optional[Dict[str, Any]] = Field(
        None, description="Active filters"
    )


class BatchProcessingError(BaseModel):
    """Error details for batch processing."""

    employee_id: int = Field(..., description="Employee ID that failed")
    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error details"
    )
    occurred_at: datetime = Field(..., description="When the error occurred")


class BatchCancellationRequest(BaseModel):
    """Request to cancel a batch job."""

    reason: Optional[str] = Field(None, description="Reason for cancellation")
    notify: bool = Field(True, description="Send notifications about cancellation")


class BatchCancellationResponse(BaseModel):
    """Response for batch job cancellation."""

    job_id: str = Field(..., description="Cancelled job ID")
    status: str = Field(..., description="New job status")
    cancelled_at: datetime = Field(..., description="Cancellation timestamp")
    cancelled_by: str = Field(..., description="User who cancelled the job")
    employees_affected: int = Field(
        ..., description="Number of employees not processed"
    )


# Export all schemas
__all__ = [
    "CalculationOptions",
    "BatchPayrollRequest",
    "BatchPayrollResponse",
    "BatchJobStatus",
    "EmployeePayrollResult",
    "BatchJobDetail",
    "BatchJobHistoryItem",
    "BatchJobHistoryResponse",
    "BatchProcessingError",
    "BatchCancellationRequest",
    "BatchCancellationResponse",
]
