"""
Enhanced Pydantic schemas for Phase 4: API & Schemas.

Comprehensive request/response models for payroll and tax API endpoints
that integrate with the Enhanced Payroll Engine (Phase 3) and Tax Services (AUR-276).
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from enum import Enum

from ..enums.staff_enums import StaffRole
from ...payroll.enums.payroll_enums import TaxType


class PayrollRunRequest(BaseModel):
    """Request schema for POST /payrolls/run endpoint."""

    staff_ids: Optional[List[int]] = Field(
        None,
        description="List of staff IDs to process. If None, processes all active staff",
    )
    pay_period_start: date = Field(
        ..., description="Start date of the pay period (YYYY-MM-DD)"
    )
    pay_period_end: date = Field(
        ..., description="End date of the pay period (YYYY-MM-DD)"
    )
    tenant_id: Optional[int] = Field(
        None, description="Tenant ID for multi-tenant environments"
    )
    force_recalculate: bool = Field(
        False,
        description="Force recalculation even if payroll already exists for the period",
    )

    @field_validator("pay_period_end")
    def validate_period_end(cls, v, info):
        if "pay_period_start" in info.data and v <= info.data["pay_period_start"]:
            raise ValueError("pay_period_end must be after pay_period_start")
        return v

    @field_validator("staff_ids")
    def validate_staff_ids(cls, v):
        if v is not None and len(v) == 0:
            raise ValueError("staff_ids cannot be an empty list")
        return v


class PayrollRunResponse(BaseModel):
    """Response schema for POST /payrolls/run endpoint."""

    job_id: str = Field(..., description="Unique identifier for the payroll run job")
    status: str = Field(..., description="Status of the payroll run")
    total_staff: int = Field(..., description="Total number of staff members processed")
    successful_count: int = Field(
        ..., description="Number of successfully processed staff"
    )
    failed_count: int = Field(..., description="Number of failed staff processing")
    pay_period_start: date = Field(..., description="Pay period start date")
    pay_period_end: date = Field(..., description="Pay period end date")
    total_gross_pay: Decimal = Field(..., description="Total gross pay for all staff")
    total_net_pay: Decimal = Field(..., description="Total net pay for all staff")
    total_deductions: Decimal = Field(..., description="Total deductions for all staff")
    processing_errors: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of processing errors with staff_id and error details",
    )
    created_at: datetime = Field(
        ..., description="Timestamp when payroll run was created"
    )

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class StaffPayrollDetail(BaseModel):
    """Detailed payroll information for a single staff member."""

    staff_id: int = Field(..., description="Staff member ID")
    staff_name: str = Field(..., description="Staff member name")
    staff_role: str = Field(..., description="Staff member role")
    pay_period_start: date = Field(..., description="Pay period start date")
    pay_period_end: date = Field(..., description="Pay period end date")

    # Hours breakdown
    regular_hours: Decimal = Field(..., description="Regular hours worked")
    overtime_hours: Decimal = Field(..., description="Overtime hours worked")
    double_time_hours: Decimal = Field(
        Decimal("0.00"), description="Double-time hours worked"
    )
    holiday_hours: Decimal = Field(Decimal("0.00"), description="Holiday hours worked")
    sick_hours: Decimal = Field(Decimal("0.00"), description="Sick hours used")
    vacation_hours: Decimal = Field(Decimal("0.00"), description="Vacation hours used")
    total_hours: Decimal = Field(..., description="Total hours for the pay period")

    # Pay rates
    base_hourly_rate: Decimal = Field(..., description="Base hourly rate")
    overtime_rate: Decimal = Field(..., description="Overtime hourly rate")

    # Earnings breakdown
    regular_pay: Decimal = Field(..., description="Regular pay amount")
    overtime_pay: Decimal = Field(..., description="Overtime pay amount")
    double_time_pay: Decimal = Field(
        Decimal("0.00"), description="Double-time pay amount"
    )
    holiday_pay: Decimal = Field(Decimal("0.00"), description="Holiday pay amount")
    sick_pay: Decimal = Field(Decimal("0.00"), description="Sick pay amount")
    vacation_pay: Decimal = Field(Decimal("0.00"), description="Vacation pay amount")
    bonus: Decimal = Field(Decimal("0.00"), description="Bonus amount")
    commission: Decimal = Field(Decimal("0.00"), description="Commission amount")
    gross_pay: Decimal = Field(..., description="Total gross pay")

    # Tax deductions
    federal_tax: Decimal = Field(..., description="Federal tax deduction")
    state_tax: Decimal = Field(..., description="State tax deduction")
    local_tax: Decimal = Field(Decimal("0.00"), description="Local tax deduction")
    social_security: Decimal = Field(..., description="Social Security deduction")
    medicare: Decimal = Field(..., description="Medicare deduction")
    unemployment: Decimal = Field(
        Decimal("0.00"), description="Unemployment tax deduction"
    )
    total_tax_deductions: Decimal = Field(..., description="Total tax deductions")

    # Benefit deductions
    health_insurance: Decimal = Field(
        Decimal("0.00"), description="Health insurance deduction"
    )
    dental_insurance: Decimal = Field(
        Decimal("0.00"), description="Dental insurance deduction"
    )
    retirement_contribution: Decimal = Field(
        Decimal("0.00"), description="Retirement contribution"
    )
    parking_fee: Decimal = Field(Decimal("0.00"), description="Parking fee deduction")
    total_benefit_deductions: Decimal = Field(
        ..., description="Total benefit deductions"
    )

    # Other deductions
    garnishments: Decimal = Field(Decimal("0.00"), description="Garnishment deductions")
    loan_repayments: Decimal = Field(
        Decimal("0.00"), description="Loan repayment deductions"
    )
    total_other_deductions: Decimal = Field(..., description="Total other deductions")

    # Totals
    total_deductions: Decimal = Field(..., description="Total all deductions")
    net_pay: Decimal = Field(..., description="Net pay amount")

    # Metadata
    processed_at: datetime = Field(..., description="When the payroll was processed")
    payment_id: Optional[int] = Field(
        None, description="Associated EmployeePayment record ID"
    )

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class PayrollSummary(BaseModel):
    """Summary information for payroll retrieval."""

    staff_id: int = Field(..., description="Staff member ID")
    staff_name: str = Field(..., description="Staff member name")
    period: str = Field(..., description="Pay period (YYYY-MM format)")
    gross_pay: Decimal = Field(..., description="Gross pay amount")
    net_pay: Decimal = Field(..., description="Net pay amount")
    total_deductions: Decimal = Field(..., description="Total deductions")
    total_hours: Decimal = Field(..., description="Total hours worked")
    processed_at: datetime = Field(..., description="Processing timestamp")

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class PayrollHistoryResponse(BaseModel):
    """Response schema for GET /payrolls/{staff_id} endpoint."""

    staff_id: int = Field(..., description="Staff member ID")
    staff_name: str = Field(..., description="Staff member name")
    payroll_history: List[PayrollSummary] = Field(
        ..., description="List of payroll records for the staff member"
    )
    total_records: int = Field(..., description="Total number of payroll records")


class TaxRuleInfo(BaseModel):
    """Tax rule information for API responses."""

    rule_id: int = Field(..., description="Tax rule ID")
    tax_type: str = Field(..., description="Type of tax (federal, state, local, etc.)")
    jurisdiction: str = Field(..., description="Tax jurisdiction")
    rate: Decimal = Field(
        ..., description="Tax rate (as decimal, e.g., 0.0825 for 8.25%)"
    )
    description: str = Field(..., description="Human-readable description of the rule")
    effective_date: Optional[date] = Field(
        None, description="Date when rule becomes effective"
    )
    expiry_date: Optional[date] = Field(None, description="Date when rule expires")
    is_active: bool = Field(..., description="Whether the rule is currently active")

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class PayrollRulesResponse(BaseModel):
    """Response schema for GET /payrolls/rules endpoint."""

    location: str = Field(..., description="Location/jurisdiction for the rules")
    total_rules: int = Field(..., description="Total number of tax rules")
    active_rules: int = Field(..., description="Number of currently active rules")
    tax_rules: List[TaxRuleInfo] = Field(..., description="List of tax rules")
    last_updated: datetime = Field(..., description="When rules were last updated")


class PayrollBatchStatus(BaseModel):
    """Status information for batch payroll processing."""

    job_id: str = Field(..., description="Batch job identifier")
    status: str = Field(..., description="Current job status")
    progress: int = Field(..., description="Progress percentage (0-100)")
    total_staff: int = Field(..., description="Total staff to process")
    completed_staff: int = Field(..., description="Number of staff completed")
    failed_staff: int = Field(..., description="Number of staff failed")
    estimated_completion: Optional[datetime] = Field(
        None, description="Estimated completion time"
    )
    error_summary: List[str] = Field(
        default_factory=list, description="Summary of errors encountered"
    )


class PayrollStatsResponse(BaseModel):
    """Response schema for payroll statistics and analytics."""

    period_start: date = Field(..., description="Statistics period start")
    period_end: date = Field(..., description="Statistics period end")
    total_employees: int = Field(..., description="Total employees processed")
    total_gross_pay: Decimal = Field(..., description="Total gross pay")
    total_net_pay: Decimal = Field(..., description="Total net pay")
    total_tax_deductions: Decimal = Field(..., description="Total tax deductions")
    total_benefit_deductions: Decimal = Field(
        ..., description="Total benefit deductions"
    )
    average_hours_per_employee: Decimal = Field(
        ..., description="Average hours per employee"
    )
    average_gross_pay: Decimal = Field(
        ..., description="Average gross pay per employee"
    )

    # Breakdown by categories
    deduction_breakdown: Dict[str, Decimal] = Field(
        ..., description="Breakdown of deductions by category"
    )
    earnings_breakdown: Dict[str, Decimal] = Field(
        ..., description="Breakdown of earnings by type"
    )

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class PayrollErrorResponse(BaseModel):
    """Error response schema for payroll API endpoints."""

    error_code: str = Field(..., description="Specific error code")
    error_message: str = Field(..., description="Human-readable error message")
    error_details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error details"
    )
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    timestamp: datetime = Field(..., description="Error timestamp")


# Request schemas for filtering and querying


class PayrollQueryFilters(BaseModel):
    """Query filters for payroll endpoints."""

    start_date: Optional[date] = Field(None, description="Filter by start date")
    end_date: Optional[date] = Field(None, description="Filter by end date")
    staff_roles: Optional[List[str]] = Field(None, description="Filter by staff roles")
    min_gross_pay: Optional[Decimal] = Field(
        None, description="Minimum gross pay filter"
    )
    max_gross_pay: Optional[Decimal] = Field(
        None, description="Maximum gross pay filter"
    )
    include_inactive: bool = Field(False, description="Include inactive staff members")
    tenant_id: Optional[int] = Field(None, description="Tenant ID filter")


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""

    page: int = Field(1, ge=1, description="Page number (1-based)")
    page_size: int = Field(50, ge=1, le=1000, description="Number of items per page")
    sort_by: Optional[str] = Field("processed_at", description="Field to sort by")
    sort_order: str = Field("desc", pattern="^(asc|desc)$", description="Sort order")


# Authentication and authorization schemas


class AuthToken(BaseModel):
    """Authentication token information."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    scope: Optional[str] = Field(None, description="Token scope")


class UserPermissions(BaseModel):
    """User permissions for payroll operations."""

    can_run_payroll: bool = Field(..., description="Can execute payroll runs")
    can_view_all_payroll: bool = Field(..., description="Can view all staff payroll")
    can_view_own_payroll: bool = Field(..., description="Can view own payroll only")
    can_view_tax_rules: bool = Field(..., description="Can view tax rules")
    can_modify_tax_rules: bool = Field(..., description="Can modify tax rules")
    tenant_ids: List[int] = Field(..., description="Accessible tenant IDs")


# Webhook and notification schemas


class PayrollWebhookPayload(BaseModel):
    """Webhook payload for payroll events."""

    event_type: str = Field(..., description="Type of payroll event")
    event_id: str = Field(..., description="Unique event identifier")
    timestamp: datetime = Field(..., description="Event timestamp")
    tenant_id: Optional[int] = Field(None, description="Tenant ID")
    data: Dict[str, Any] = Field(..., description="Event-specific data")


class PayrollNotificationPreferences(BaseModel):
    """User notification preferences for payroll events."""

    email_on_completion: bool = Field(True, description="Email when payroll completes")
    email_on_errors: bool = Field(True, description="Email when payroll has errors")
    webhook_url: Optional[str] = Field(
        None, description="Webhook URL for notifications"
    )
    slack_channel: Optional[str] = Field(
        None, description="Slack channel for notifications"
    )


# Export and reporting schemas


class PayrollExportRequest(BaseModel):
    """Request schema for payroll data export."""

    format: str = Field("csv", pattern="^(csv|xlsx|pdf)$", description="Export format")
    pay_period_start: date = Field(..., description="Export period start")
    pay_period_end: date = Field(..., description="Export period end")
    staff_ids: Optional[List[int]] = Field(
        None, description="Specific staff IDs to export"
    )
    include_details: bool = Field(True, description="Include detailed breakdown")
    tenant_id: Optional[int] = Field(None, description="Tenant ID filter")


class PayrollExportResponse(BaseModel):
    """Response schema for payroll export requests."""

    export_id: str = Field(..., description="Export job identifier")
    status: str = Field(..., description="Export status")
    download_url: Optional[str] = Field(None, description="Download URL when ready")
    expires_at: Optional[datetime] = Field(None, description="URL expiration time")
    created_at: datetime = Field(..., description="Export creation time")
