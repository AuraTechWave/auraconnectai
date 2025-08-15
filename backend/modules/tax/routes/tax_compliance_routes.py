# backend/modules/tax/routes/tax_compliance_routes.py

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
import uuid

from core.database import get_db
from core.auth import require_permission, get_current_tenant

from ..schemas import (
    TaxFilingCreate,
    TaxFilingUpdate,
    TaxFilingSubmit,
    TaxFilingResponse,
    TaxRemittanceCreate,
    TaxRemittanceResponse,
    TaxReportRequest,
    TaxReportResponse,
    TaxComplianceDashboard,
    FilingStatus,
    FilingType,
    TaxAuditLogResponse,
)
from ..services import (
    TaxComplianceService,
    TaxFilingAutomationService,
    AutomationFrequency,
)
from ..models import TaxFiling, TaxAuditLog

router = APIRouter(prefix="/compliance", tags=["Tax Compliance"])


# Filing Management
@router.post("/filings", response_model=TaxFilingResponse)
async def create_filing(
    filing_data: TaxFilingCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.file")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Create a new tax filing"""
    service = TaxComplianceService(db)
    return service.create_filing(filing_data, current_user["id"], tenant_id)


@router.get("/filings", response_model=List[TaxFilingResponse])
async def list_filings(
    jurisdiction_id: Optional[int] = Query(None),
    filing_type: Optional[FilingType] = Query(None),
    status: Optional[FilingStatus] = Query(None),
    period_start: Optional[date] = Query(None),
    period_end: Optional[date] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.view")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """List tax filings with filters"""
    service = TaxComplianceService(db)
    return service.list_filings(
        jurisdiction_id=jurisdiction_id,
        filing_type=filing_type,
        status=status,
        period_start=period_start,
        period_end=period_end,
        tenant_id=tenant_id,
        limit=limit,
        offset=offset,
    )


@router.get("/filings/{filing_id}", response_model=TaxFilingResponse)
async def get_filing(
    filing_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.view")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Get a specific tax filing"""
    service = TaxComplianceService(db)
    return service.get_filing(filing_id, tenant_id)


@router.patch("/filings/{filing_id}", response_model=TaxFilingResponse)
async def update_filing(
    filing_id: int,
    update_data: TaxFilingUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.file")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Update a tax filing"""
    service = TaxComplianceService(db)
    return service.update_filing(filing_id, update_data, current_user["id"], tenant_id)


@router.post("/filings/{filing_id}/submit", response_model=TaxFilingResponse)
async def submit_filing(
    filing_id: int,
    submit_data: TaxFilingSubmit,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.file")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Submit a tax filing"""
    service = TaxComplianceService(db)
    return service.submit_filing(filing_id, submit_data, current_user["id"], tenant_id)


@router.post("/filings/{filing_id}/amend")
async def amend_filing(
    filing_id: int,
    amendment_reason: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.file")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Create an amended filing"""
    # Get original filing
    original = (
        db.query(TaxFiling)
        .filter(TaxFiling.id == filing_id, TaxFiling.tenant_id == tenant_id)
        .first()
    )

    if not original:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Filing {filing_id} not found",
        )

    if original.status not in [FilingStatus.SUBMITTED, FilingStatus.ACCEPTED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only amend submitted or accepted filings",
        )

    # Create amended filing
    service = TaxComplianceService(db)

    # Copy original filing data
    filing_data = TaxFilingCreate(
        internal_reference=f"AMEND-{original.internal_reference}",
        jurisdiction_id=original.jurisdiction_id,
        filing_type=original.filing_type,
        period_start=original.period_start,
        period_end=original.period_end,
        due_date=original.due_date,
        gross_sales=original.gross_sales,
        taxable_sales=original.taxable_sales,
        exempt_sales=original.exempt_sales,
        tax_collected=original.tax_collected,
        form_type=original.form_type,
        notes=f"Amendment of filing {original.filing_number}\nReason: {amendment_reason}",
        line_items=[],  # Would copy line items
        attachments=[],
    )

    amended = service.create_filing(filing_data, current_user["id"], tenant_id)

    # Update amended filing
    db.query(TaxFiling).filter(TaxFiling.id == amended.id).update(
        {
            "is_amended": True,
            "amendment_reason": amendment_reason,
            "original_filing_id": original.id,
        }
    )

    # Mark original as amended
    original.status = FilingStatus.AMENDED

    db.commit()

    return {
        "original_filing_id": filing_id,
        "amended_filing_id": amended.id,
        "message": "Amendment created successfully",
    }


# Remittance Management
@router.post("/remittances")
async def create_remittance(
    remittance_data: TaxRemittanceCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.pay")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Create a tax payment remittance"""
    service = TaxComplianceService(db)
    return service.create_remittance(remittance_data, current_user["id"], tenant_id)


# Compliance Dashboard
@router.get("/dashboard", response_model=TaxComplianceDashboard)
async def get_compliance_dashboard(
    as_of_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.view")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Get tax compliance dashboard"""
    service = TaxComplianceService(db)
    return service.get_compliance_dashboard(tenant_id, as_of_date)


# Reporting
@router.post("/reports", response_model=TaxReportResponse)
async def generate_report(
    report_request: TaxReportRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.report")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Generate a tax report"""
    service = TaxComplianceService(db)
    return service.generate_report(report_request, current_user["id"], tenant_id)


@router.get("/reports/{report_id}/download")
async def download_report(
    report_id: str,
    format: str = Query("pdf", pattern="^(pdf|excel|csv)$"),
    current_user: dict = Depends(require_permission("tax.report")),
):
    """Download a generated report"""
    # TODO: Implement report file download
    return {
        "message": "Report download not yet implemented",
        "report_id": report_id,
        "format": format,
    }


# Automation
@router.post("/automation/schedule")
async def schedule_automation(
    frequency: AutomationFrequency = Query(AutomationFrequency.DAILY),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.admin")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Schedule automated filing generation"""
    automation_service = TaxFilingAutomationService(db)

    # Schedule as background task
    background_tasks.add_task(
        automation_service.schedule_automated_filings, tenant_id, frequency
    )

    return {
        "message": "Automation scheduled",
        "frequency": frequency,
        "status": "pending",
    }


@router.post("/automation/generate/{nexus_id}")
async def generate_automated_filing(
    nexus_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.file")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Generate automated filing for a specific nexus"""
    automation_service = TaxFilingAutomationService(db)

    filing = await automation_service.generate_automated_filing(
        nexus_id, tenant_id, current_user["id"]
    )

    return TaxFilingResponse.model_validate(filing)


@router.post("/automation/submit")
async def auto_submit_filings(
    dry_run: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.admin")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Auto-submit ready filings"""
    automation_service = TaxFilingAutomationService(db)

    result = await automation_service.auto_submit_ready_filings(tenant_id, dry_run)

    return result


@router.post("/automation/reconcile")
async def reconcile_accounts(
    period_start: Optional[date] = Query(None),
    period_end: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.admin")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Reconcile tax accounts with transaction data"""
    automation_service = TaxFilingAutomationService(db)

    result = await automation_service.reconcile_tax_accounts(
        tenant_id, period_start, period_end
    )

    return result


@router.get("/automation/estimated-payments")
async def get_estimated_payments(
    tax_year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.view")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Get estimated tax payment schedule"""
    automation_service = TaxFilingAutomationService(db)

    result = await automation_service.generate_estimated_payments(tenant_id, tax_year)

    return result


# Audit Trail
@router.get("/audit-logs")
async def list_audit_logs(
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.audit")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """List audit logs with filters"""
    query = db.query(TaxAuditLog).filter(TaxAuditLog.tenant_id == tenant_id)

    if entity_type:
        query = query.filter(TaxAuditLog.entity_type == entity_type)

    if entity_id:
        query = query.filter(TaxAuditLog.entity_id == entity_id)

    if event_type:
        query = query.filter(TaxAuditLog.event_type == event_type)

    if user_id:
        query = query.filter(TaxAuditLog.user_id == user_id)

    if date_from:
        query = query.filter(TaxAuditLog.event_timestamp >= date_from)

    if date_to:
        query = query.filter(TaxAuditLog.event_timestamp <= date_to)

    logs = (
        query.order_by(TaxAuditLog.event_timestamp.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    return [TaxAuditLogResponse.model_validate(log) for log in logs]


# Quick Actions
@router.get("/quick-stats")
async def get_quick_stats(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.view")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Get quick tax statistics"""
    today = date.today()

    # Count filings by status
    filing_counts = (
        db.query(TaxFiling.status, db.func.count(TaxFiling.id))
        .filter(TaxFiling.tenant_id == tenant_id)
        .group_by(TaxFiling.status)
        .all()
    )

    # Upcoming deadlines
    upcoming_count = (
        db.query(TaxFiling)
        .filter(
            TaxFiling.tenant_id == tenant_id,
            TaxFiling.status.in_([FilingStatus.DRAFT, FilingStatus.READY]),
            TaxFiling.due_date >= today,
            TaxFiling.due_date <= today + timedelta(days=30),
        )
        .count()
    )

    # Overdue filings
    overdue_count = (
        db.query(TaxFiling)
        .filter(
            TaxFiling.tenant_id == tenant_id,
            TaxFiling.status.in_([FilingStatus.DRAFT, FilingStatus.READY]),
            TaxFiling.due_date < today,
        )
        .count()
    )

    # Total tax liability
    total_liability = (
        db.query(db.func.sum(TaxFiling.total_due))
        .filter(TaxFiling.tenant_id == tenant_id, TaxFiling.status != FilingStatus.PAID)
        .scalar()
        or 0
    )

    return {
        "filing_counts": dict(filing_counts),
        "upcoming_deadlines": upcoming_count,
        "overdue_filings": overdue_count,
        "total_outstanding": float(total_liability),
        "as_of": today,
    }
