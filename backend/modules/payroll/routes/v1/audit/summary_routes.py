# backend/modules/payroll/routes/v1/audit/summary_routes.py

"""
Audit summary and analytics endpoints.

Provides aggregated statistics and summaries for audit data.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import date, timedelta

from ......core.database import get_db
from ......core.auth import require_payroll_access, get_current_user, User
from ....models.payroll_audit import PayrollAuditLog
from ....schemas.audit_schemas import AuditSummaryResponse
from ....exceptions import DatabaseError, PayrollValidationError
from ..helpers import get_tenant_filter, validate_date_range

router = APIRouter()


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
    
    Groups audit events by the specified field and returns counts and percentages.
    """
    # Validate date range
    date_validation = validate_date_range(start_date, end_date, max_days=365)
    if not date_validation["valid"]:
        raise PayrollValidationError(date_validation["error"])
    
    try:
        # Build base query
        query = db.query(
            func.count(PayrollAuditLog.id).label('count')
        ).filter(
            PayrollAuditLog.timestamp >= start_date,
            PayrollAuditLog.timestamp < end_date + timedelta(days=1)
        )
        
        # Multi-tenant filtering
        tenant_id = get_tenant_filter(current_user)
        if tenant_id:
            query = query.filter(PayrollAuditLog.tenant_id == tenant_id)
        
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
        
        if tenant_id:
            total_query = total_query.filter(PayrollAuditLog.tenant_id == tenant_id)
        
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
        
        if tenant_id:
            top_users_query = top_users_query.filter(
                PayrollAuditLog.tenant_id == tenant_id
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
        
    except PayrollValidationError:
        raise
    except Exception as e:
        raise DatabaseError(
            message="Failed to generate audit summary",
            operation="aggregate"
        ) from e