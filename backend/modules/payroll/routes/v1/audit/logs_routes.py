# backend/modules/payroll/routes/v1/audit/logs_routes.py

"""
Audit log query and retrieval endpoints.

Handles fetching and filtering audit logs.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date, timedelta

from core.database import get_db
from core.auth import require_payroll_access, get_current_user, User
from ....models.payroll_audit import PayrollAuditLog
from ....schemas.audit_schemas import AuditLogEntry, AuditLogResponse, AuditEventType
from ....exceptions import AuditLogError, PayrollNotFoundError, DatabaseError
from ..helpers import get_tenant_filter

router = APIRouter()


@router.get("/", response_model=AuditLogResponse)
async def get_audit_logs(
    # Time filters
    start_date: Optional[date] = Query(None, description="Start date for audit logs"),
    end_date: Optional[date] = Query(None, description="End date for audit logs"),
    # Entity filters
    event_type: Optional[AuditEventType] = Query(
        None, description="Filter by event type"
    ),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    entity_id: Optional[int] = Query(None, description="Filter by entity ID"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    # Pagination
    limit: int = Query(50, ge=1, le=500, description="Number of records per page"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    # Sorting
    sort_by: str = Query("timestamp", description="Field to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_access),
):
    """
    Get audit logs for payroll operations with filtering and pagination.
    """
    try:
        # Build query
        query = db.query(PayrollAuditLog)

        # Apply filters
        if start_date:
            query = query.filter(PayrollAuditLog.timestamp >= start_date)

        if end_date:
            # Add one day to include the entire end date
            query = query.filter(
                PayrollAuditLog.timestamp < end_date + timedelta(days=1)
            )

        if event_type:
            query = query.filter(PayrollAuditLog.event_type == event_type)

        if entity_type:
            query = query.filter(PayrollAuditLog.entity_type == entity_type)

        if entity_id:
            query = query.filter(PayrollAuditLog.entity_id == entity_id)

        if user_id:
            query = query.filter(PayrollAuditLog.user_id == user_id)

        # Multi-tenant filtering
        tenant_id = get_tenant_filter(current_user)
        if tenant_id:
            query = query.filter(PayrollAuditLog.tenant_id == tenant_id)

        # Get total count
        total_count = query.count()

        # Apply sorting
        sort_fields = {
            "timestamp": PayrollAuditLog.timestamp,
            "event_type": PayrollAuditLog.event_type,
            "user_id": PayrollAuditLog.user_id,
            "entity_type": PayrollAuditLog.entity_type,
        }

        order_field = sort_fields.get(sort_by, PayrollAuditLog.timestamp)

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
                metadata=log.metadata,
            )
            for log in logs
        ]

        return AuditLogResponse(
            total=total_count, limit=limit, offset=offset, logs=log_entries
        )

    except Exception as e:
        raise DatabaseError(
            message="Failed to retrieve audit logs", operation="query"
        ) from e


@router.get("/{log_id}", response_model=AuditLogEntry)
async def get_audit_log_detail(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_access),
):
    """
    Get detailed information for a specific audit log entry.
    """
    try:
        log = db.query(PayrollAuditLog).filter(PayrollAuditLog.id == log_id).first()

        if not log:
            raise PayrollNotFoundError("Audit log", log_id)

        # Check tenant access
        tenant_id = get_tenant_filter(current_user)
        if tenant_id and log.tenant_id != tenant_id:
            raise HTTPException(
                status_code=403, detail="You don't have access to this audit log"
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
            metadata=log.metadata,
        )

    except PayrollNotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise DatabaseError(
            message="Failed to retrieve audit log detail", operation="get"
        ) from e
