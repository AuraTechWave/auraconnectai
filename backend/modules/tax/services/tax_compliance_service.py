# backend/modules/tax/services/tax_compliance_service.py

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import List, Dict, Optional, Tuple, Any
from datetime import date, datetime, timedelta
from decimal import Decimal
import logging
import uuid
from collections import defaultdict

from ..models import (
    TaxJurisdiction, TaxFiling, TaxFilingLineItem,
    TaxRemittance, TaxAuditLog, TaxReportTemplate,
    FilingStatus, FilingType
)
from ..schemas.tax_compliance_schemas import (
    TaxFilingCreate, TaxFilingUpdate, TaxFilingSubmit,
    TaxFilingResponse, TaxRemittanceCreate,
    TaxReportRequest, TaxReportResponse,
    TaxComplianceDashboard, TaxComplianceStatus,
    TaxAuditLogCreate
)

logger = logging.getLogger(__name__)


class TaxComplianceService:
    """Service for tax compliance management"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # Filing Management
    def create_filing(
        self,
        filing_data: TaxFilingCreate,
        user_id: str,
        tenant_id: Optional[int] = None
    ) -> TaxFilingResponse:
        """Create a new tax filing"""
        try:
            # Check for duplicate filing
            existing = self.db.query(TaxFiling).filter(
                TaxFiling.jurisdiction_id == filing_data.jurisdiction_id,
                TaxFiling.filing_type == filing_data.filing_type,
                TaxFiling.period_start == filing_data.period_start,
                TaxFiling.period_end == filing_data.period_end,
                TaxFiling.tenant_id == tenant_id
            ).first()
            
            if existing and existing.status != FilingStatus.DRAFT:
                raise ValueError(
                    f"Filing already exists for this period: {existing.filing_id}"
                )
            
            # Create filing
            filing = TaxFiling(
                filing_id=uuid.uuid4(),
                internal_reference=filing_data.internal_reference,
                jurisdiction_id=filing_data.jurisdiction_id,
                filing_type=filing_data.filing_type,
                period_start=filing_data.period_start,
                period_end=filing_data.period_end,
                due_date=filing_data.due_date,
                status=FilingStatus.DRAFT,
                gross_sales=filing_data.gross_sales,
                taxable_sales=filing_data.taxable_sales,
                exempt_sales=filing_data.exempt_sales,
                tax_collected=filing_data.tax_collected,
                tax_due=Decimal("0"),  # Will be calculated
                penalties=Decimal("0"),
                interest=Decimal("0"),
                total_due=Decimal("0"),  # Will be calculated
                form_type=filing_data.form_type,
                notes=filing_data.notes,
                attachments=filing_data.attachments,
                tenant_id=tenant_id
            )
            
            self.db.add(filing)
            self.db.flush()
            
            # Add line items
            for item_data in filing_data.line_items:
                line_item = TaxFilingLineItem(
                    filing_id=filing.id,
                    **item_data.model_dump()
                )
                self.db.add(line_item)
            
            # Calculate totals
            self._calculate_filing_totals(filing)
            
            # Create audit log
            self._create_audit_log(
                event_type="filing",
                event_subtype="create",
                entity_type="filing",
                entity_id=str(filing.filing_id),
                filing_id=filing.id,
                user_id=user_id,
                action="create",
                amount_after=filing.total_due,
                tenant_id=tenant_id
            )
            
            self.db.commit()
            self.db.refresh(filing)
            
            return TaxFilingResponse.model_validate(filing)
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating filing: {str(e)}")
            raise
    
    def update_filing(
        self,
        filing_id: int,
        update_data: TaxFilingUpdate,
        user_id: str,
        tenant_id: Optional[int] = None
    ) -> TaxFilingResponse:
        """Update an existing tax filing"""
        try:
            filing = self.db.query(TaxFiling).filter(
                TaxFiling.id == filing_id,
                TaxFiling.tenant_id == tenant_id
            ).first()
            
            if not filing:
                raise ValueError(f"Filing {filing_id} not found")
            
            if filing.status not in [FilingStatus.DRAFT, FilingStatus.READY]:
                raise ValueError(
                    f"Cannot update filing with status {filing.status}"
                )
            
            # Track changes for audit
            changes = {}
            amount_before = filing.total_due
            
            # Update fields
            for field, value in update_data.model_dump(exclude_unset=True).items():
                if hasattr(filing, field) and getattr(filing, field) != value:
                    changes[field] = {
                        "before": getattr(filing, field),
                        "after": value
                    }
                    setattr(filing, field, value)
            
            # Recalculate totals if amounts changed
            if any(field in changes for field in [
                "gross_sales", "taxable_sales", "exempt_sales",
                "tax_collected", "tax_due", "penalties", "interest"
            ]):
                self._calculate_filing_totals(filing)
            
            # Create audit log
            self._create_audit_log(
                event_type="filing",
                event_subtype="update",
                entity_type="filing",
                entity_id=str(filing.filing_id),
                filing_id=filing.id,
                user_id=user_id,
                action="update",
                changes=changes,
                amount_before=amount_before,
                amount_after=filing.total_due,
                tenant_id=tenant_id
            )
            
            self.db.commit()
            self.db.refresh(filing)
            
            return TaxFilingResponse.model_validate(filing)
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating filing: {str(e)}")
            raise
    
    def submit_filing(
        self,
        filing_id: int,
        submit_data: TaxFilingSubmit,
        user_id: str,
        tenant_id: Optional[int] = None
    ) -> TaxFilingResponse:
        """Submit a tax filing"""
        try:
            filing = self.db.query(TaxFiling).filter(
                TaxFiling.id == filing_id,
                TaxFiling.tenant_id == tenant_id
            ).first()
            
            if not filing:
                raise ValueError(f"Filing {filing_id} not found")
            
            if filing.status != FilingStatus.READY:
                raise ValueError(
                    f"Filing must be in READY status to submit (current: {filing.status})"
                )
            
            # Update filing
            filing.status = FilingStatus.SUBMITTED
            filing.filed_date = datetime.utcnow()
            filing.prepared_by = submit_data.prepared_by
            filing.prepared_date = datetime.utcnow()
            
            if submit_data.reviewed_by:
                filing.reviewed_by = submit_data.reviewed_by
                filing.reviewed_date = datetime.utcnow()
            
            if submit_data.approved_by:
                filing.approved_by = submit_data.approved_by
                filing.approved_date = datetime.utcnow()
            
            # Generate filing number (would integrate with tax authority)
            filing.filing_number = self._generate_filing_number(filing)
            
            # Create audit log
            self._create_audit_log(
                event_type="filing",
                event_subtype="submit",
                entity_type="filing",
                entity_id=str(filing.filing_id),
                filing_id=filing.id,
                user_id=user_id,
                action="submit",
                metadata={
                    "submission_method": submit_data.submission_method,
                    "prepared_by": submit_data.prepared_by
                },
                tenant_id=tenant_id
            )
            
            self.db.commit()
            self.db.refresh(filing)
            
            # TODO: Integrate with external tax filing systems
            
            return TaxFilingResponse.model_validate(filing)
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error submitting filing: {str(e)}")
            raise
    
    def get_filing(
        self,
        filing_id: int,
        tenant_id: Optional[int] = None
    ) -> TaxFilingResponse:
        """Get a specific tax filing"""
        filing = self.db.query(TaxFiling).filter(
            TaxFiling.id == filing_id,
            TaxFiling.tenant_id == tenant_id
        ).first()
        
        if not filing:
            raise ValueError(f"Filing {filing_id} not found")
        
        return TaxFilingResponse.model_validate(filing)
    
    def list_filings(
        self,
        jurisdiction_id: Optional[int] = None,
        filing_type: Optional[FilingType] = None,
        status: Optional[FilingStatus] = None,
        period_start: Optional[date] = None,
        period_end: Optional[date] = None,
        tenant_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[TaxFilingResponse]:
        """List tax filings with filters"""
        query = self.db.query(TaxFiling)
        
        if tenant_id:
            query = query.filter(TaxFiling.tenant_id == tenant_id)
        
        if jurisdiction_id:
            query = query.filter(TaxFiling.jurisdiction_id == jurisdiction_id)
        
        if filing_type:
            query = query.filter(TaxFiling.filing_type == filing_type)
        
        if status:
            query = query.filter(TaxFiling.status == status)
        
        if period_start:
            query = query.filter(TaxFiling.period_end >= period_start)
        
        if period_end:
            query = query.filter(TaxFiling.period_start <= period_end)
        
        filings = query.order_by(
            TaxFiling.due_date.desc()
        ).limit(limit).offset(offset).all()
        
        return [TaxFilingResponse.model_validate(f) for f in filings]
    
    # Remittance Management
    def create_remittance(
        self,
        remittance_data: TaxRemittanceCreate,
        user_id: str,
        tenant_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create a tax payment remittance"""
        try:
            # Verify all referenced filings exist
            filings = self.db.query(TaxFiling).filter(
                TaxFiling.id.in_(remittance_data.filing_references),
                TaxFiling.tenant_id == tenant_id
            ).all()
            
            if len(filings) != len(remittance_data.filing_references):
                raise ValueError("One or more referenced filings not found")
            
            # Create remittance
            remittance = TaxRemittance(
                remittance_id=uuid.uuid4(),
                payment_date=remittance_data.payment_date,
                payment_method=remittance_data.payment_method,
                payment_reference=remittance_data.payment_reference,
                payment_amount=remittance_data.payment_amount,
                currency=remittance_data.currency,
                filing_references=remittance_data.filing_references,
                bank_account_last4=remittance_data.bank_account_last4,
                bank_name=remittance_data.bank_name,
                notes=remittance_data.notes,
                status="pending",
                tenant_id=tenant_id
            )
            
            self.db.add(remittance)
            
            # Update filing payment status
            for filing in filings:
                filing.payment_status = "pending"
                filing.payment_reference = remittance_data.payment_reference
            
            # Create audit log
            self._create_audit_log(
                event_type="payment",
                event_subtype="remittance",
                entity_type="remittance",
                entity_id=str(remittance.remittance_id),
                user_id=user_id,
                action="create",
                amount_after=remittance_data.payment_amount,
                metadata={
                    "filing_count": len(filings),
                    "payment_method": remittance_data.payment_method
                },
                tenant_id=tenant_id
            )
            
            self.db.commit()
            self.db.refresh(remittance)
            
            return {
                "remittance_id": remittance.remittance_id,
                "status": remittance.status,
                "filings_updated": len(filings)
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating remittance: {str(e)}")
            raise
    
    # Compliance Dashboard
    def get_compliance_dashboard(
        self,
        tenant_id: Optional[int] = None,
        as_of_date: Optional[date] = None
    ) -> TaxComplianceDashboard:
        """Get comprehensive tax compliance dashboard"""
        if not as_of_date:
            as_of_date = date.today()
        
        # Get all active jurisdictions
        jurisdictions = self.db.query(TaxJurisdiction).filter(
            TaxJurisdiction.is_active == True,
            TaxJurisdiction.tenant_id == tenant_id
        ).all()
        
        # Initialize metrics
        compliance_statuses = []
        total_liability = Decimal("0")
        total_paid = Decimal("0")
        upcoming_deadlines = []
        overdue_filings = []
        recent_filings = []
        alerts = []
        
        # Analyze each jurisdiction
        for jurisdiction in jurisdictions:
            status = self._analyze_jurisdiction_compliance(
                jurisdiction, as_of_date, tenant_id
            )
            compliance_statuses.append(status)
            
            total_liability += status.total_liability
            total_paid += status.total_paid
        
        # Get upcoming deadlines (next 30 days)
        upcoming = self.db.query(TaxFiling).filter(
            TaxFiling.tenant_id == tenant_id,
            TaxFiling.status.in_([FilingStatus.DRAFT, FilingStatus.READY]),
            TaxFiling.due_date >= as_of_date,
            TaxFiling.due_date <= as_of_date + timedelta(days=30)
        ).order_by(TaxFiling.due_date).limit(10).all()
        
        for filing in upcoming:
            upcoming_deadlines.append({
                "filing_id": filing.id,
                "jurisdiction": filing.jurisdiction.name,
                "filing_type": filing.filing_type,
                "due_date": filing.due_date,
                "days_until_due": (filing.due_date - as_of_date).days
            })
        
        # Get overdue filings
        overdue = self.db.query(TaxFiling).filter(
            TaxFiling.tenant_id == tenant_id,
            TaxFiling.status.in_([FilingStatus.DRAFT, FilingStatus.READY]),
            TaxFiling.due_date < as_of_date
        ).all()
        
        for filing in overdue:
            overdue_filings.append({
                "filing_id": filing.id,
                "jurisdiction": filing.jurisdiction.name,
                "filing_type": filing.filing_type,
                "due_date": filing.due_date,
                "days_overdue": (as_of_date - filing.due_date).days,
                "estimated_penalties": self._estimate_penalties(filing, as_of_date)
            })
            
            # Add alert
            alerts.append({
                "severity": "high",
                "type": "overdue_filing",
                "message": f"Filing overdue for {filing.jurisdiction.name} - {filing.filing_type}",
                "filing_id": filing.id
            })
        
        # Get recent filings (last 30 days)
        recent = self.db.query(TaxFiling).filter(
            TaxFiling.tenant_id == tenant_id,
            TaxFiling.filed_date >= as_of_date - timedelta(days=30)
        ).order_by(TaxFiling.filed_date.desc()).limit(10).all()
        
        for filing in recent:
            recent_filings.append({
                "filing_id": filing.id,
                "jurisdiction": filing.jurisdiction.name,
                "filing_type": filing.filing_type,
                "filed_date": filing.filed_date,
                "status": filing.status,
                "total_amount": filing.total_due
            })
        
        # Calculate overall metrics
        total_jurisdictions = len(jurisdictions)
        compliant_jurisdictions = sum(
            1 for s in compliance_statuses
            if s.current_period_status == "compliant"
        )
        at_risk_jurisdictions = sum(
            1 for s in compliance_statuses
            if s.risk_level in ["high", "critical"]
        )
        
        overall_compliance_score = (
            sum(s.compliance_score for s in compliance_statuses) / total_jurisdictions
            if total_jurisdictions > 0 else 0
        )
        
        overall_risk_level = self._calculate_overall_risk_level(
            compliance_statuses
        )
        
        # Generate recommendations
        recommendations = self._generate_compliance_recommendations(
            compliance_statuses, upcoming_deadlines, overdue_filings
        )
        
        return TaxComplianceDashboard(
            as_of_date=datetime.combine(as_of_date, datetime.min.time()),
            overall_compliance_score=overall_compliance_score,
            overall_risk_level=overall_risk_level,
            total_jurisdictions=total_jurisdictions,
            compliant_jurisdictions=compliant_jurisdictions,
            at_risk_jurisdictions=at_risk_jurisdictions,
            upcoming_deadlines=upcoming_deadlines,
            overdue_filings=overdue_filings,
            recent_filings=recent_filings,
            total_tax_liability=total_liability,
            total_tax_paid=total_paid,
            outstanding_balance=total_liability - total_paid,
            compliance_by_jurisdiction=compliance_statuses,
            alerts=alerts,
            recommendations=recommendations
        )
    
    # Reporting
    def generate_report(
        self,
        report_request: TaxReportRequest,
        user_id: str,
        tenant_id: Optional[int] = None
    ) -> TaxReportResponse:
        """Generate tax report"""
        try:
            report_id = uuid.uuid4()
            
            # Get template if specified
            template = None
            if report_request.template_id:
                template = self.db.query(TaxReportTemplate).filter(
                    TaxReportTemplate.template_id == report_request.template_id,
                    TaxReportTemplate.tenant_id == tenant_id
                ).first()
            
            # Build base query
            query = self.db.query(TaxFiling).filter(
                TaxFiling.tenant_id == tenant_id,
                TaxFiling.period_start >= report_request.period_start,
                TaxFiling.period_end <= report_request.period_end
            )
            
            # Apply filters
            if report_request.jurisdiction_ids:
                query = query.filter(
                    TaxFiling.jurisdiction_id.in_(report_request.jurisdiction_ids)
                )
            
            if report_request.filing_types:
                query = query.filter(
                    TaxFiling.filing_type.in_(report_request.filing_types)
                )
            
            if report_request.filters:
                # Apply additional filters
                pass
            
            filings = query.all()
            
            # Generate report data
            summary = self._generate_report_summary(filings)
            details = None
            trends = None
            
            if report_request.include_details:
                details = self._generate_report_details(filings, report_request)
            
            if report_request.include_trends:
                trends = self._generate_report_trends(filings, tenant_id)
            
            # Create audit log
            self._create_audit_log(
                event_type="report",
                event_subtype="generate",
                entity_type="report",
                entity_id=str(report_id),
                user_id=user_id,
                action="generate",
                metadata={
                    "report_type": report_request.report_type,
                    "period": f"{report_request.period_start} to {report_request.period_end}",
                    "record_count": len(filings)
                },
                tenant_id=tenant_id
            )
            
            # Generate output file if needed
            download_url = None
            if report_request.output_format != "json":
                download_url = self._generate_report_file(
                    report_id,
                    report_request.output_format,
                    summary,
                    details,
                    trends
                )
            
            return TaxReportResponse(
                report_id=report_id,
                report_type=report_request.report_type,
                generated_at=datetime.utcnow(),
                generated_by=user_id,
                period_start=report_request.period_start,
                period_end=report_request.period_end,
                summary=summary,
                details=details,
                trends=trends,
                total_records=len(filings),
                filters_applied=report_request.filters or {},
                download_url=download_url,
                expires_at=datetime.utcnow() + timedelta(days=7) if download_url else None
            )
            
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            raise
    
    # Helper methods
    def _calculate_filing_totals(self, filing: TaxFiling):
        """Calculate total amounts for a filing"""
        # Sum line items
        line_items = self.db.query(TaxFilingLineItem).filter(
            TaxFilingLineItem.filing_id == filing.id
        ).all()
        
        if line_items:
            filing.tax_due = sum(item.tax_amount for item in line_items)
        else:
            # Simple calculation if no line items
            if filing.taxable_sales and filing.tax_collected:
                filing.tax_due = filing.tax_collected
            else:
                filing.tax_due = Decimal("0")
        
        # Calculate total due
        filing.total_due = (
            filing.tax_due + filing.penalties + filing.interest
        )
    
    def _generate_filing_number(self, filing: TaxFiling) -> str:
        """Generate filing number"""
        # Format: JUR-TYPE-YYYY-MM-NNNN
        year_month = filing.period_end.strftime("%Y-%m")
        
        # Get next sequence number
        last_filing = self.db.query(TaxFiling).filter(
            TaxFiling.jurisdiction_id == filing.jurisdiction_id,
            TaxFiling.filing_type == filing.filing_type,
            func.date_trunc('month', TaxFiling.period_end) == 
            func.date_trunc('month', filing.period_end)
        ).order_by(TaxFiling.id.desc()).first()
        
        sequence = 1
        if last_filing and last_filing.filing_number:
            try:
                sequence = int(last_filing.filing_number.split('-')[-1]) + 1
            except:
                pass
        
        return f"{filing.jurisdiction.code}-{filing.filing_type.value}-{year_month}-{sequence:04d}"
    
    def _analyze_jurisdiction_compliance(
        self,
        jurisdiction: TaxJurisdiction,
        as_of_date: date,
        tenant_id: Optional[int]
    ) -> TaxComplianceStatus:
        """Analyze compliance status for a jurisdiction"""
        # Get current period filings
        current_period_start = as_of_date.replace(day=1)
        
        filings = self.db.query(TaxFiling).filter(
            TaxFiling.jurisdiction_id == jurisdiction.id,
            TaxFiling.tenant_id == tenant_id,
            TaxFiling.period_start >= current_period_start - timedelta(days=365)
        ).all()
        
        # Calculate metrics
        total_liability = sum(f.total_due for f in filings)
        total_paid = sum(
            f.total_due for f in filings
            if f.status == FilingStatus.PAID
        )
        
        pending_count = sum(
            1 for f in filings
            if f.status in [FilingStatus.DRAFT, FilingStatus.READY]
            and f.due_date >= as_of_date
        )
        
        overdue_count = sum(
            1 for f in filings
            if f.status in [FilingStatus.DRAFT, FilingStatus.READY]
            and f.due_date < as_of_date
        )
        
        # Determine current period status
        current_filing = next(
            (f for f in filings if f.period_start >= current_period_start),
            None
        )
        
        if not current_filing:
            current_status = "pending"
        elif current_filing.status == FilingStatus.PAID:
            current_status = "compliant"
        elif current_filing.due_date < as_of_date:
            current_status = "overdue"
        else:
            current_status = "pending"
        
        # Calculate compliance score
        compliance_score = 100.0
        if overdue_count > 0:
            compliance_score -= overdue_count * 20
        if pending_count > 3:
            compliance_score -= 10
        
        compliance_score = max(0, min(100, compliance_score))
        
        # Determine risk level
        if overdue_count > 2 or compliance_score < 50:
            risk_level = "critical"
        elif overdue_count > 0 or compliance_score < 70:
            risk_level = "high"
        elif pending_count > 2 or compliance_score < 85:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        # Get last and next filing dates
        last_filing = max(
            (f for f in filings if f.filed_date),
            key=lambda f: f.filed_date,
            default=None
        )
        
        next_filing = min(
            (f for f in filings if f.status != FilingStatus.PAID),
            key=lambda f: f.due_date,
            default=None
        )
        
        # Generate alerts
        alerts = []
        if overdue_count > 0:
            alerts.append({
                "type": "overdue",
                "count": overdue_count,
                "message": f"{overdue_count} overdue filing(s)"
            })
        
        return TaxComplianceStatus(
            jurisdiction_id=jurisdiction.id,
            jurisdiction_name=jurisdiction.name,
            filing_type=FilingType.SALES_TAX,  # Default, should be dynamic
            current_period_status=current_status,
            last_filing_date=last_filing.filed_date.date() if last_filing else None,
            next_filing_due=next_filing.due_date if next_filing else None,
            filings_pending=pending_count,
            filings_overdue=overdue_count,
            total_liability=total_liability,
            total_paid=total_paid,
            outstanding_balance=total_liability - total_paid,
            compliance_score=compliance_score,
            risk_level=risk_level,
            alerts=alerts
        )
    
    def _estimate_penalties(
        self,
        filing: TaxFiling,
        as_of_date: date
    ) -> Decimal:
        """Estimate penalties for overdue filing"""
        if filing.due_date >= as_of_date:
            return Decimal("0")
        
        days_overdue = (as_of_date - filing.due_date).days
        
        # Simple penalty calculation (5% + 0.5% per month)
        base_penalty = filing.tax_due * Decimal("0.05")
        monthly_penalty = filing.tax_due * Decimal("0.005") * (days_overdue // 30)
        
        # Cap at 25%
        max_penalty = filing.tax_due * Decimal("0.25")
        
        return min(base_penalty + monthly_penalty, max_penalty)
    
    def _calculate_overall_risk_level(
        self,
        compliance_statuses: List[TaxComplianceStatus]
    ) -> str:
        """Calculate overall risk level"""
        if not compliance_statuses:
            return "low"
        
        critical_count = sum(1 for s in compliance_statuses if s.risk_level == "critical")
        high_count = sum(1 for s in compliance_statuses if s.risk_level == "high")
        
        if critical_count > 0:
            return "critical"
        elif high_count > 2:
            return "high"
        elif high_count > 0:
            return "medium"
        else:
            return "low"
    
    def _generate_compliance_recommendations(
        self,
        compliance_statuses: List[TaxComplianceStatus],
        upcoming_deadlines: List[Dict],
        overdue_filings: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Generate compliance recommendations"""
        recommendations = []
        
        # Overdue filing recommendations
        if overdue_filings:
            recommendations.append({
                "priority": "high",
                "category": "overdue_filings",
                "title": "Address Overdue Filings",
                "description": f"You have {len(overdue_filings)} overdue filing(s) that require immediate attention",
                "action_items": [
                    "Complete and submit overdue filings immediately",
                    "Calculate and prepare for penalty payments",
                    "Consider filing for penalty abatement if applicable"
                ]
            })
        
        # Upcoming deadline recommendations
        critical_deadlines = [
            d for d in upcoming_deadlines
            if d["days_until_due"] <= 7
        ]
        
        if critical_deadlines:
            recommendations.append({
                "priority": "high",
                "category": "upcoming_deadlines",
                "title": "Prepare for Upcoming Deadlines",
                "description": f"{len(critical_deadlines)} filing(s) due within 7 days",
                "action_items": [
                    "Gather necessary documentation",
                    "Complete draft filings",
                    "Schedule review and approval"
                ]
            })
        
        # High-risk jurisdiction recommendations
        high_risk_jurisdictions = [
            s for s in compliance_statuses
            if s.risk_level in ["high", "critical"]
        ]
        
        if high_risk_jurisdictions:
            recommendations.append({
                "priority": "medium",
                "category": "risk_management",
                "title": "Improve Compliance in High-Risk Jurisdictions",
                "description": f"{len(high_risk_jurisdictions)} jurisdiction(s) require attention",
                "action_items": [
                    "Review filing procedures for these jurisdictions",
                    "Consider automation or outsourcing",
                    "Implement additional compliance controls"
                ]
            })
        
        return recommendations
    
    def _generate_report_summary(
        self,
        filings: List[TaxFiling]
    ) -> Dict[str, Any]:
        """Generate report summary"""
        return {
            "total_filings": len(filings),
            "by_status": defaultdict(int, {
                status: sum(1 for f in filings if f.status == status)
                for status in FilingStatus
            }),
            "total_tax_due": sum(f.tax_due for f in filings),
            "total_penalties": sum(f.penalties for f in filings),
            "total_interest": sum(f.interest for f in filings),
            "total_amount": sum(f.total_due for f in filings),
            "total_paid": sum(
                f.total_due for f in filings
                if f.status == FilingStatus.PAID
            )
        }
    
    def _generate_report_details(
        self,
        filings: List[TaxFiling],
        request: TaxReportRequest
    ) -> List[Dict[str, Any]]:
        """Generate report details"""
        details = []
        
        for filing in filings:
            detail = {
                "filing_id": filing.id,
                "jurisdiction": filing.jurisdiction.name,
                "filing_type": filing.filing_type.value,
                "period": f"{filing.period_start} to {filing.period_end}",
                "status": filing.status.value,
                "tax_due": float(filing.tax_due),
                "total_due": float(filing.total_due),
                "filed_date": filing.filed_date.isoformat() if filing.filed_date else None
            }
            
            # Add line items if requested
            if request.include_details:
                detail["line_items"] = [
                    {
                        "line_number": item.line_number,
                        "description": item.description,
                        "taxable_amount": float(item.taxable_amount),
                        "tax_amount": float(item.tax_amount)
                    }
                    for item in filing.line_items
                ]
            
            details.append(detail)
        
        return details
    
    def _generate_report_trends(
        self,
        filings: List[TaxFiling],
        tenant_id: Optional[int]
    ) -> Dict[str, Any]:
        """Generate trend analysis"""
        # Group filings by month
        monthly_data = defaultdict(lambda: {
            "count": 0,
            "tax_due": Decimal("0"),
            "total_due": Decimal("0")
        })
        
        for filing in filings:
            month_key = filing.period_end.strftime("%Y-%m")
            monthly_data[month_key]["count"] += 1
            monthly_data[month_key]["tax_due"] += filing.tax_due
            monthly_data[month_key]["total_due"] += filing.total_due
        
        return {
            "monthly_trends": [
                {
                    "month": month,
                    "filing_count": data["count"],
                    "tax_due": float(data["tax_due"]),
                    "total_due": float(data["total_due"])
                }
                for month, data in sorted(monthly_data.items())
            ],
            "year_over_year": self._calculate_year_over_year(filings),
            "compliance_trends": self._calculate_compliance_trends(filings)
        }
    
    def _calculate_year_over_year(
        self,
        filings: List[TaxFiling]
    ) -> Dict[str, Any]:
        """Calculate year-over-year trends"""
        current_year = date.today().year
        last_year = current_year - 1
        
        current_year_filings = [
            f for f in filings
            if f.period_end.year == current_year
        ]
        
        last_year_filings = [
            f for f in filings
            if f.period_end.year == last_year
        ]
        
        current_total = sum(f.total_due for f in current_year_filings)
        last_total = sum(f.total_due for f in last_year_filings)
        
        if last_total > 0:
            change_percent = ((current_total - last_total) / last_total * 100)
        else:
            change_percent = 0
        
        return {
            "current_year_total": float(current_total),
            "last_year_total": float(last_total),
            "change_percent": float(change_percent)
        }
    
    def _calculate_compliance_trends(
        self,
        filings: List[TaxFiling]
    ) -> Dict[str, Any]:
        """Calculate compliance trends"""
        on_time_count = sum(
            1 for f in filings
            if f.filed_date and f.filed_date.date() <= f.due_date
        )
        
        late_count = sum(
            1 for f in filings
            if f.filed_date and f.filed_date.date() > f.due_date
        )
        
        pending_count = sum(
            1 for f in filings
            if f.status in [FilingStatus.DRAFT, FilingStatus.READY]
        )
        
        return {
            "on_time_filings": on_time_count,
            "late_filings": late_count,
            "pending_filings": pending_count,
            "compliance_rate": (
                on_time_count / (on_time_count + late_count) * 100
                if (on_time_count + late_count) > 0 else 0
            )
        }
    
    def _generate_report_file(
        self,
        report_id: uuid.UUID,
        output_format: str,
        summary: Dict,
        details: Optional[List],
        trends: Optional[Dict]
    ) -> str:
        """Generate report file in requested format"""
        # TODO: Implement file generation (PDF, Excel, CSV)
        # For now, return a mock URL
        return f"/api/tax/reports/{report_id}/download.{output_format}"
    
    def _create_audit_log(
        self,
        event_type: str,
        event_subtype: Optional[str],
        entity_type: str,
        entity_id: str,
        user_id: str,
        action: str,
        filing_id: Optional[int] = None,
        changes: Optional[Dict] = None,
        amount_before: Optional[Decimal] = None,
        amount_after: Optional[Decimal] = None,
        metadata: Optional[Dict] = None,
        tenant_id: Optional[int] = None
    ):
        """Create audit log entry"""
        try:
            tax_impact = None
            if amount_before is not None and amount_after is not None:
                tax_impact = amount_after - amount_before
            
            audit_log = TaxAuditLog(
                audit_id=uuid.uuid4(),
                event_type=event_type,
                event_subtype=event_subtype,
                event_timestamp=datetime.utcnow(),
                entity_type=entity_type,
                entity_id=entity_id,
                filing_id=filing_id,
                user_id=user_id,
                user_name=user_id,  # Would lookup actual name
                action=action,
                changes=changes,
                amount_before=amount_before,
                amount_after=amount_after,
                tax_impact=tax_impact,
                metadata=metadata,
                tenant_id=tenant_id
            )
            
            self.db.add(audit_log)
            
        except Exception as e:
            logger.warning(f"Failed to create audit log: {str(e)}")