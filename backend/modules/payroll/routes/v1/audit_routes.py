# backend/modules/payroll/routes/v1/audit_routes.py

"""
Audit trail endpoints for payroll operations.

Provides endpoints for tracking and querying payroll-related
audit events for compliance and security.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Optional
from datetime import datetime, date, timedelta
import json

from .....core.database import get_db
from .....core.auth import require_payroll_access, get_current_user, User
from ...models.payroll_audit import PayrollAuditLog
from ...schemas.audit_schemas import (
    AuditLogEntry,
    AuditLogFilter,
    AuditLogResponse,
    AuditEventType,
    AuditSummaryResponse,
    AuditExportRequest,
    AuditExportResponse
)
from ...schemas.error_schemas import ErrorResponse, PayrollErrorCodes

router = APIRouter()


@router.get("/logs", response_model=AuditLogResponse)
async def get_audit_logs(
    # Time filters
    start_date: Optional[date] = Query(None, description="Start date for audit logs"),
    end_date: Optional[date] = Query(None, description="End date for audit logs"),
    
    # Entity filters
    event_type: Optional[AuditEventType] = Query(None, description="Filter by event type"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    entity_id: Optional[int] = Query(None, description="Filter by entity ID"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    
    # Pagination
    limit: int = Query(50, ge=1, le=500, description="Number of records per page"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    
    # Sorting
    sort_by: str = Query("timestamp", description="Field to sort by"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_access)
):
    """
    Get audit logs for payroll operations.
    
    ## Query Parameters
    - **start_date**: Filter logs from this date
    - **end_date**: Filter logs until this date
    - **event_type**: Filter by specific event type
    - **entity_type**: Filter by entity type (payment, tax_rule, etc.)
    - **entity_id**: Filter by specific entity ID
    - **user_id**: Filter by user who performed action
    - **limit**: Number of records per page
    - **offset**: Number of records to skip
    - **sort_by**: Field to sort by
    - **sort_order**: Sort order (asc/desc)
    
    ## Response
    Returns paginated list of audit log entries.
    
    ## Permissions
    Requires payroll access permissions.
    """
    # Build query
    query = db.query(PayrollAuditLog)
    
    # Apply filters
    if start_date:
        query = query.filter(PayrollAuditLog.timestamp >= start_date)
    
    if end_date:
        # Add one day to include the entire end date
        query = query.filter(PayrollAuditLog.timestamp < end_date + timedelta(days=1))
    
    if event_type:
        query = query.filter(PayrollAuditLog.event_type == event_type)
    
    if entity_type:
        query = query.filter(PayrollAuditLog.entity_type == entity_type)
    
    if entity_id:
        query = query.filter(PayrollAuditLog.entity_id == entity_id)
    
    if user_id:
        query = query.filter(PayrollAuditLog.user_id == user_id)
    
    # Multi-tenant filtering
    if hasattr(current_user, 'tenant_id'):
        query = query.filter(PayrollAuditLog.tenant_id == current_user.tenant_id)
    
    # Get total count
    total_count = query.count()
    
    # Apply sorting
    if sort_by == "timestamp":
        order_field = PayrollAuditLog.timestamp
    elif sort_by == "event_type":
        order_field = PayrollAuditLog.event_type
    elif sort_by == "user_id":
        order_field = PayrollAuditLog.user_id
    else:
        order_field = PayrollAuditLog.timestamp
    
    if sort_order == "desc":
        query = query.order_by(order_field.desc())
    else:
        query = query.order_by(order_field.asc())
    
    # Apply pagination
    logs = query.limit(limit).offset(offset).all()
    
    # Convert to response models
    log_entries = [
        AuditLogEntry(
            id=log.id,
            timestamp=log.timestamp,
            event_type=log.event_type,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            user_id=log.user_id,
            user_email=log.user_email,
            ip_address=log.ip_address,
            action=log.action,
            old_values=log.old_values,
            new_values=log.new_values,
            metadata=log.metadata
        )
        for log in logs
    ]
    
    return AuditLogResponse(
        total=total_count,
        limit=limit,
        offset=offset,
        logs=log_entries
    )


@router.get("/logs/{log_id}", response_model=AuditLogEntry)
async def get_audit_log_detail(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_access)
):
    """
    Get detailed information for a specific audit log entry.
    
    ## Path Parameters
    - **log_id**: ID of the audit log entry
    
    ## Response
    Returns detailed audit log information.
    """
    log = db.query(PayrollAuditLog).filter(
        PayrollAuditLog.id == log_id
    ).first()
    
    if not log:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="NotFound",
                message=f"Audit log {log_id} not found",
                code=PayrollErrorCodes.RECORD_NOT_FOUND
            ).dict()
        )
    
    # Check tenant access
    if hasattr(current_user, 'tenant_id') and log.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=403,
            detail=ErrorResponse(
                error="AccessDenied",
                message="You don't have access to this audit log",
                code=PayrollErrorCodes.INSUFFICIENT_PERMISSIONS
            ).dict()
        )
    
    return AuditLogEntry(
        id=log.id,
        timestamp=log.timestamp,
        event_type=log.event_type,
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        user_id=log.user_id,
        user_email=log.user_email,
        ip_address=log.ip_address,
        action=log.action,
        old_values=log.old_values,
        new_values=log.new_values,
        metadata=log.metadata
    )


@router.get("/summary", response_model=AuditSummaryResponse)
async def get_audit_summary(
    start_date: date = Query(..., description="Start date for summary"),
    end_date: date = Query(..., description="End date for summary"),
    group_by: str = Query("event_type", regex="^(event_type|user|entity_type|day)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_access)
):
    """
    Get summary statistics for audit logs.
    
    ## Query Parameters
    - **start_date**: Start date for summary
    - **end_date**: End date for summary
    - **group_by**: Group results by (event_type, user, entity_type, day)
    
    ## Response
    Returns aggregated audit statistics.
    """
    # Build base query
    query = db.query(
        func.count(PayrollAuditLog.id).label('count')
    ).filter(
        PayrollAuditLog.timestamp >= start_date,
        PayrollAuditLog.timestamp < end_date + timedelta(days=1)
    )
    
    # Multi-tenant filtering
    if hasattr(current_user, 'tenant_id'):
        query = query.filter(PayrollAuditLog.tenant_id == current_user.tenant_id)
    
    # Apply grouping
    if group_by == "event_type":
        query = query.add_columns(
            PayrollAuditLog.event_type.label('group_key')
        ).group_by(PayrollAuditLog.event_type)
    elif group_by == "user":
        query = query.add_columns(
            PayrollAuditLog.user_email.label('group_key')
        ).group_by(PayrollAuditLog.user_email)
    elif group_by == "entity_type":
        query = query.add_columns(
            PayrollAuditLog.entity_type.label('group_key')
        ).group_by(PayrollAuditLog.entity_type)
    elif group_by == "day":
        query = query.add_columns(
            func.date(PayrollAuditLog.timestamp).label('group_key')
        ).group_by(func.date(PayrollAuditLog.timestamp))
    
    results = query.all()
    
    # Get total count
    total_query = db.query(func.count(PayrollAuditLog.id)).filter(
        PayrollAuditLog.timestamp >= start_date,
        PayrollAuditLog.timestamp < end_date + timedelta(days=1)
    )
    
    if hasattr(current_user, 'tenant_id'):
        total_query = total_query.filter(PayrollAuditLog.tenant_id == current_user.tenant_id)
    
    total_events = total_query.scalar() or 0
    
    # Format summary data
    summary_data = [
        {
            "group": str(result.group_key),
            "count": result.count,
            "percentage": (result.count / total_events * 100) if total_events > 0 else 0
        }
        for result in results
    ]
    
    # Get most active users
    top_users_query = db.query(
        PayrollAuditLog.user_email,
        func.count(PayrollAuditLog.id).label('action_count')
    ).filter(
        PayrollAuditLog.timestamp >= start_date,
        PayrollAuditLog.timestamp < end_date + timedelta(days=1)
    )
    
    if hasattr(current_user, 'tenant_id'):
        top_users_query = top_users_query.filter(
            PayrollAuditLog.tenant_id == current_user.tenant_id
        )
    
    top_users = top_users_query.group_by(
        PayrollAuditLog.user_email
    ).order_by(
        func.count(PayrollAuditLog.id).desc()
    ).limit(10).all()
    
    return AuditSummaryResponse(
        start_date=start_date,
        end_date=end_date,
        total_events=total_events,
        group_by=group_by,
        summary_data=summary_data,
        top_users=[
            {"user": user.user_email, "actions": user.action_count}
            for user in top_users
        ]
    )


@router.post("/export", response_model=AuditExportResponse)
async def export_audit_logs(
    export_request: AuditExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_access)
):
    """
    Export audit logs in specified format.
    
    ## Request Body
    - **format**: Export format (csv, json, pdf)
    - **filters**: Filter criteria for export
    - **include_metadata**: Include full metadata in export
    
    ## Response
    Returns export job information.
    """
    # Validate date range
    if export_request.filters.end_date:
        date_diff = export_request.filters.end_date - export_request.filters.start_date
        if date_diff.days > 365:
            raise HTTPException(
                status_code=422,
                detail=ErrorResponse(
                    error="ValidationError",
                    message="Export date range cannot exceed 365 days",
                    code=PayrollErrorCodes.INVALID_DATE_RANGE
                ).dict()
            )
    
    # In a real implementation, this would queue an export job
    # For now, return a mock response
    export_id = f"audit-export-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    
    return AuditExportResponse(
        export_id=export_id,
        status="processing",
        format=export_request.format,
        created_at=datetime.utcnow(),
        download_url=None,
        expires_at=None
    )


@router.get("/compliance/report")
async def get_compliance_report(
    report_type: str = Query(
        ...,
        regex="^(access|changes|sensitive|all)$",
        description="Type of compliance report"
    ),
    start_date: date = Query(..., description="Report start date"),
    end_date: date = Query(..., description="Report end date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_access)
):
    """
    Generate compliance report from audit logs.
    
    ## Query Parameters
    - **report_type**: Type of report (access, changes, sensitive, all)
    - **start_date**: Report start date
    - **end_date**: Report end date
    
    ## Response
    Returns compliance report data.
    """
    report_data = {
        "report_type": report_type,
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        },
        "generated_at": datetime.utcnow().isoformat(),
        "generated_by": current_user.email
    }
    
    # Build queries based on report type
    base_filter = and_(
        PayrollAuditLog.timestamp >= start_date,
        PayrollAuditLog.timestamp < end_date + timedelta(days=1)
    )
    
    if hasattr(current_user, 'tenant_id'):
        base_filter = and_(
            base_filter,
            PayrollAuditLog.tenant_id == current_user.tenant_id
        )
    
    if report_type in ["access", "all"]:
        # Access report - login/logout events
        access_events = db.query(
            func.count(PayrollAuditLog.id)
        ).filter(
            base_filter,
            PayrollAuditLog.event_type.in_([
                AuditEventType.USER_LOGIN,
                AuditEventType.USER_LOGOUT,
                AuditEventType.ACCESS_DENIED
            ])
        ).scalar() or 0
        
        report_data["access_summary"] = {
            "total_access_events": access_events,
            "unique_users": db.query(
                func.count(func.distinct(PayrollAuditLog.user_id))
            ).filter(base_filter).scalar() or 0
        }
    
    if report_type in ["changes", "all"]:
        # Changes report - data modifications
        change_events = db.query(
            PayrollAuditLog.entity_type,
            func.count(PayrollAuditLog.id).label('count')
        ).filter(
            base_filter,
            PayrollAuditLog.event_type.in_([
                AuditEventType.PAYROLL_CALCULATED,
                AuditEventType.PAYMENT_CREATED,
                AuditEventType.TAX_RULE_UPDATED,
                AuditEventType.CONFIGURATION_CHANGED
            ])
        ).group_by(PayrollAuditLog.entity_type).all()
        
        report_data["changes_summary"] = [
            {"entity": event.entity_type, "changes": event.count}
            for event in change_events
        ]
    
    if report_type in ["sensitive", "all"]:
        # Sensitive operations report
        sensitive_events = db.query(
            func.count(PayrollAuditLog.id)
        ).filter(
            base_filter,
            PayrollAuditLog.event_type.in_([
                AuditEventType.PAYMENT_APPROVED,
                AuditEventType.EXPORT_GENERATED,
                AuditEventType.BATCH_PROCESSED,
                AuditEventType.CONFIGURATION_CHANGED
            ])
        ).scalar() or 0
        
        report_data["sensitive_operations"] = {
            "total_sensitive_events": sensitive_events,
            "export_operations": db.query(
                func.count(PayrollAuditLog.id)
            ).filter(
                base_filter,
                PayrollAuditLog.event_type == AuditEventType.EXPORT_GENERATED
            ).scalar() or 0
        }
    
    return report_data