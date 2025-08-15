# backend/modules/payroll/routes/v1/audit/compliance_routes.py

"""
Compliance reporting and export endpoints.

Handles compliance reports and audit log exports.
"""

from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any
import uuid

from core.database import get_db
from core.auth import require_payroll_access, get_current_user, User
from ....models.payroll_audit import PayrollAuditLog
from ....schemas.audit_schemas import (
    AuditEventType,
    AuditExportRequest,
    AuditExportResponse,
)
from ....exceptions import AuditExportError, PayrollValidationError
from ..helpers import get_tenant_filter, validate_date_range

router = APIRouter()


@router.get("/report")
async def get_compliance_report(
    report_type: str = Query(
        ...,
        pattern="^(access|changes|sensitive|all)$",
        description="Type of compliance report",
    ),
    start_date: date = Query(..., description="Report start date"),
    end_date: date = Query(..., description="Report end date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_access),
):
    """
    Generate compliance report from audit logs.

    Report types:
    - access: User access and authentication events
    - changes: Data modification events
    - sensitive: Sensitive operations (payments, exports, etc.)
    - all: Comprehensive report
    """
    # Validate date range
    date_validation = validate_date_range(start_date, end_date, max_days=365)
    if not date_validation["valid"]:
        raise PayrollValidationError(date_validation["error"])

    try:
        report_data = {
            "report_type": report_type,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": date_validation["days_in_range"],
            },
            "generated_at": datetime.utcnow().isoformat(),
            "generated_by": current_user.email,
        }

        # Build queries based on report type
        base_filter = and_(
            PayrollAuditLog.timestamp >= start_date,
            PayrollAuditLog.timestamp < end_date + timedelta(days=1),
        )

        tenant_id = get_tenant_filter(current_user)
        if tenant_id:
            base_filter = and_(base_filter, PayrollAuditLog.tenant_id == tenant_id)

        if report_type in ["access", "all"]:
            # Access report - login/logout events
            access_events = (
                db.query(func.count(PayrollAuditLog.id))
                .filter(
                    base_filter,
                    PayrollAuditLog.event_type.in_(
                        [
                            AuditEventType.USER_LOGIN,
                            AuditEventType.USER_LOGOUT,
                            AuditEventType.ACCESS_DENIED,
                        ]
                    ),
                )
                .scalar()
                or 0
            )

            report_data["access_summary"] = {
                "total_access_events": access_events,
                "unique_users": db.query(
                    func.count(func.distinct(PayrollAuditLog.user_id))
                )
                .filter(base_filter)
                .scalar()
                or 0,
                "access_denied_count": db.query(func.count(PayrollAuditLog.id))
                .filter(
                    base_filter,
                    PayrollAuditLog.event_type == AuditEventType.ACCESS_DENIED,
                )
                .scalar()
                or 0,
            }

        if report_type in ["changes", "all"]:
            # Changes report - data modifications
            change_events = (
                db.query(
                    PayrollAuditLog.entity_type,
                    func.count(PayrollAuditLog.id).label("count"),
                )
                .filter(
                    base_filter,
                    PayrollAuditLog.event_type.in_(
                        [
                            AuditEventType.PAYROLL_CALCULATED,
                            AuditEventType.PAYMENT_CREATED,
                            AuditEventType.PAYMENT_UPDATED,
                            AuditEventType.TAX_RULE_UPDATED,
                            AuditEventType.CONFIGURATION_CHANGED,
                        ]
                    ),
                )
                .group_by(PayrollAuditLog.entity_type)
                .all()
            )

            report_data["changes_summary"] = {
                "total_changes": sum(event.count for event in change_events),
                "changes_by_entity": [
                    {"entity": event.entity_type, "count": event.count}
                    for event in change_events
                ],
            }

        if report_type in ["sensitive", "all"]:
            # Sensitive operations report
            sensitive_events = (
                db.query(
                    PayrollAuditLog.event_type,
                    func.count(PayrollAuditLog.id).label("count"),
                )
                .filter(
                    base_filter,
                    PayrollAuditLog.event_type.in_(
                        [
                            AuditEventType.PAYMENT_APPROVED,
                            AuditEventType.PAYMENT_PROCESSED,
                            AuditEventType.EXPORT_GENERATED,
                            AuditEventType.BATCH_PROCESSED,
                            AuditEventType.CONFIGURATION_CHANGED,
                            AuditEventType.TAX_RULE_DELETED,
                        ]
                    ),
                )
                .group_by(PayrollAuditLog.event_type)
                .all()
            )

            report_data["sensitive_operations"] = {
                "total_sensitive_events": sum(
                    event.count for event in sensitive_events
                ),
                "events_by_type": [
                    {"event_type": event.event_type.value, "count": event.count}
                    for event in sensitive_events
                ],
                "export_operations": db.query(func.count(PayrollAuditLog.id))
                .filter(
                    base_filter,
                    PayrollAuditLog.event_type == AuditEventType.EXPORT_GENERATED,
                )
                .scalar()
                or 0,
            }

        # Add recommendations based on findings
        report_data["recommendations"] = generate_compliance_recommendations(
            report_data
        )

        return report_data

    except PayrollValidationError:
        raise
    except Exception as e:
        raise AuditExportError(
            message="Failed to generate compliance report", export_format="report"
        ) from e


@router.post("/export", response_model=AuditExportResponse)
async def export_audit_logs(
    export_request: AuditExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_access),
):
    """
    Export audit logs in specified format.

    Queues an export job and returns job information.
    """
    # Validate date range
    if export_request.filters.end_date:
        date_validation = validate_date_range(
            export_request.filters.start_date,
            export_request.filters.end_date,
            max_days=365,
        )
        if not date_validation["valid"]:
            raise PayrollValidationError(date_validation["error"])

    try:
        # Create export job ID
        export_id = f"audit-export-{uuid.uuid4()}"

        # Queue export task (in production, use Celery or similar)
        background_tasks.add_task(
            process_audit_export,
            export_id,
            export_request,
            current_user.id,
            get_tenant_filter(current_user),
        )

        return AuditExportResponse(
            export_id=export_id,
            status="processing",
            format=export_request.format,
            created_at=datetime.utcnow(),
            download_url=None,
            expires_at=None,
        )

    except PayrollValidationError:
        raise
    except Exception as e:
        raise AuditExportError(
            message="Failed to initiate audit export",
            export_format=export_request.format,
        ) from e


def generate_compliance_recommendations(report_data: dict) -> list:
    """
    Generate recommendations based on compliance report findings.
    """
    recommendations = []

    # Check access patterns
    if "access_summary" in report_data:
        if report_data["access_summary"].get("access_denied_count", 0) > 10:
            recommendations.append(
                "High number of access denied events detected. Review user permissions."
            )

    # Check sensitive operations
    if "sensitive_operations" in report_data:
        if report_data["sensitive_operations"].get("export_operations", 0) > 100:
            recommendations.append(
                "High volume of data exports. Consider implementing export approval workflow."
            )

    # Check changes
    if "changes_summary" in report_data:
        if report_data["changes_summary"].get("total_changes", 0) > 1000:
            recommendations.append(
                "High volume of data changes. Ensure all changes are reviewed regularly."
            )

    if not recommendations:
        recommendations.append("No significant compliance concerns identified.")

    return recommendations


async def process_audit_export(
    export_id: str,
    export_request: AuditExportRequest,
    user_id: int,
    tenant_id: Optional[int],
):
    """
    Process audit log export in background.

    In production, this would:
    1. Query audit logs based on filters
    2. Format data according to export format
    3. Upload to storage
    4. Send notification with download link
    """
    # This is a placeholder for the actual export logic
    # In production, implement actual export processing
    pass
