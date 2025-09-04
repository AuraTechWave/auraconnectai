# backend/modules/payroll/schemas/audit_schemas.py

"""
Audit trail schemas for payroll operations.

Defines request/response models for audit logging and
compliance reporting functionality.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from enum import Enum


class AuditEventType(str, Enum):
    """Types of audit events for payroll operations."""

    # Authentication events
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    ACCESS_DENIED = "access.denied"

    # Payroll calculation events
    PAYROLL_CALCULATED = "payroll.calculated"
    PAYROLL_APPROVED = "payroll.approved"
    PAYROLL_REJECTED = "payroll.rejected"

    # Payment events
    PAYMENT_CREATED = "payment.created"
    PAYMENT_UPDATED = "payment.updated"
    PAYMENT_APPROVED = "payment.approved"
    PAYMENT_PROCESSED = "payment.processed"
    PAYMENT_CANCELLED = "payment.cancelled"

    # Tax events
    TAX_RULE_CREATED = "tax_rule.created"
    TAX_RULE_UPDATED = "tax_rule.updated"
    TAX_RULE_DELETED = "tax_rule.deleted"
    TAX_CALCULATION_PERFORMED = "tax.calculated"

    # Configuration events
    CONFIGURATION_CREATED = "config.created"
    CONFIGURATION_CHANGED = "config.changed"
    CONFIGURATION_DELETED = "config.deleted"

    # Batch processing events
    BATCH_STARTED = "batch.started"
    BATCH_COMPLETED = "batch.completed"
    BATCH_FAILED = "batch.failed"
    BATCH_CANCELLED = "batch.cancelled"

    # Export events
    EXPORT_GENERATED = "export.generated"
    EXPORT_DOWNLOADED = "export.downloaded"

    # Employee events
    EMPLOYEE_PAY_UPDATED = "employee.pay_updated"
    EMPLOYEE_DEDUCTION_CHANGED = "employee.deduction_changed"

    # Webhook events
    WEBHOOK_TRIGGERED = "webhook.triggered"
    WEBHOOK_FAILED = "webhook.failed"


class AuditLogEntry(BaseModel):
    """Individual audit log entry."""

    id: int = Field(..., description="Unique audit log ID")
    timestamp: datetime = Field(..., description="When the event occurred")
    event_type: AuditEventType = Field(..., description="Type of audit event")
    entity_type: str = Field(
        ..., description="Type of entity affected (payment, employee, etc.)"
    )
    entity_id: Optional[int] = Field(None, description="ID of the affected entity")
    user_id: int = Field(..., description="ID of user who performed action")
    user_email: str = Field(..., description="Email of user who performed action")
    ip_address: Optional[str] = Field(None, description="IP address of request")
    action: str = Field(..., description="Human-readable description of action")
    old_values: Optional[Dict[str, Any]] = Field(
        None, description="Previous values (for updates)"
    )
    new_values: Optional[Dict[str, Any]] = Field(
        None, description="New values (for updates)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional event metadata"
    )
    session_id: Optional[str] = Field(None, description="Session identifier")
    request_id: Optional[str] = Field(
        None, description="Request identifier for tracing"
    )


class AuditLogFilter(BaseModel):
    """Filter criteria for audit log queries."""

    start_date: date = Field(..., description="Start date for audit logs")
    end_date: Optional[date] = Field(None, description="End date for audit logs")
    event_types: Optional[List[AuditEventType]] = Field(
        None, description="Filter by event types"
    )
    entity_types: Optional[List[str]] = Field(
        None, description="Filter by entity types"
    )
    entity_ids: Optional[List[int]] = Field(
        None, description="Filter by specific entity IDs"
    )
    user_ids: Optional[List[int]] = Field(None, description="Filter by user IDs")
    ip_addresses: Optional[List[str]] = Field(
        None, description="Filter by IP addresses"
    )
    search_text: Optional[str] = Field(
        None, description="Search in action descriptions", max_length=100
    )

    @field_validator("end_date")
    def validate_end_date(cls, v, info):
        if v and "start_date" in info.data and v < info.data["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v


class AuditLogResponse(BaseModel):
    """Response for audit log queries."""

    total: int = Field(..., description="Total number of matching logs")
    limit: int = Field(..., description="Number of logs per page")
    offset: int = Field(..., description="Number of logs skipped")
    logs: List[AuditLogEntry] = Field(..., description="List of audit log entries")
    filters_applied: Optional[Dict[str, Any]] = Field(
        None, description="Active filters summary"
    )


class AuditSummaryResponse(BaseModel):
    """Summary statistics for audit logs."""

    start_date: date = Field(..., description="Summary period start")
    end_date: date = Field(..., description="Summary period end")
    total_events: int = Field(..., description="Total number of events")
    group_by: str = Field(..., description="Grouping field used")
    summary_data: List[Dict[str, Any]] = Field(
        ..., description="Grouped summary statistics"
    )
    top_users: List[Dict[str, Any]] = Field(..., description="Most active users")
    event_distribution: Optional[Dict[str, int]] = Field(
        None, description="Distribution of events by type"
    )


class AuditExportRequest(BaseModel):
    """Request for exporting audit logs."""

    format: str = Field("csv", pattern="^(csv|json|pdf)$", description="Export format")
    filters: AuditLogFilter = Field(..., description="Filter criteria for export")
    include_metadata: bool = Field(False, description="Include full metadata in export")
    include_old_values: bool = Field(
        True, description="Include old values for update events"
    )
    include_new_values: bool = Field(
        True, description="Include new values for update events"
    )
    columns: Optional[List[str]] = Field(
        None, description="Specific columns to include"
    )


class AuditExportResponse(BaseModel):
    """Response for audit log export."""

    export_id: str = Field(..., description="Unique export job ID")
    status: str = Field(..., description="Export status")
    format: str = Field(..., description="Export format")
    created_at: datetime = Field(..., description="Export creation time")
    download_url: Optional[str] = Field(None, description="Download URL when ready")
    expires_at: Optional[datetime] = Field(None, description="URL expiration time")
    record_count: Optional[int] = Field(None, description="Number of records exported")
    file_size_bytes: Optional[int] = Field(None, description="Export file size")


class AuditComplianceReport(BaseModel):
    """Compliance report from audit data."""

    report_id: str = Field(..., description="Unique report ID")
    report_type: str = Field(..., description="Type of compliance report")
    period_start: date = Field(..., description="Report period start")
    period_end: date = Field(..., description="Report period end")
    generated_at: datetime = Field(..., description="Report generation time")
    generated_by: str = Field(..., description="User who generated report")
    summary: Dict[str, Any] = Field(..., description="Report summary data")
    compliance_status: str = Field(..., description="Overall compliance status")
    findings: List[Dict[str, Any]] = Field(
        default_factory=list, description="Compliance findings"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Compliance recommendations"
    )


class AuditRetentionPolicy(BaseModel):
    """Audit log retention policy configuration."""

    retention_days: int = Field(
        365, ge=30, le=2555, description="Days to retain audit logs"
    )
    archive_after_days: Optional[int] = Field(
        None, ge=7, le=365, description="Days before archiving"
    )
    delete_archived_after_days: Optional[int] = Field(
        None, ge=365, le=2555, description="Days to keep archived logs"
    )
    excluded_event_types: List[AuditEventType] = Field(
        default_factory=list, description="Event types to exclude from deletion"
    )
    compliance_mode: bool = Field(
        True, description="Enable compliance mode (stricter retention)"
    )


# Export all schemas
__all__ = [
    "AuditEventType",
    "AuditLogEntry",
    "AuditLogFilter",
    "AuditLogResponse",
    "AuditSummaryResponse",
    "AuditExportRequest",
    "AuditExportResponse",
    "AuditComplianceReport",
    "AuditRetentionPolicy",
]
