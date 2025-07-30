# backend/modules/tax/services/tax_filing_automation_service.py

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import List, Dict, Optional, Tuple, Any
from datetime import date, datetime, timedelta
from decimal import Decimal
import logging
import uuid
from collections import defaultdict
import asyncio
from enum import Enum

from ..models import (
    TaxJurisdiction, TaxFiling, TaxFilingLineItem,
    TaxNexus, FilingStatus, FilingType
)
from ..schemas.tax_compliance_schemas import (
    TaxFilingCreate, TaxFilingLineItemCreate,
    TaxFilingSubmit
)
from .tax_compliance_service import TaxComplianceService

logger = logging.getLogger(__name__)


class AutomationFrequency(str, Enum):
    """Automation frequency options"""
    DAILY = "daily"
    WEEKLY = "weekly" 
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ON_DEMAND = "on_demand"


class TaxFilingAutomationService:
    """Service for automating tax filing processes"""
    
    def __init__(self, db: Session):
        self.db = db
        self.compliance_service = TaxComplianceService(db)
        self._automation_tasks = {}
    
    async def schedule_automated_filings(
        self,
        tenant_id: Optional[int] = None,
        frequency: AutomationFrequency = AutomationFrequency.DAILY
    ) -> Dict[str, Any]:
        """Schedule automated filing generation based on nexus requirements"""
        try:
            # Get all active nexus jurisdictions
            nexus_list = self.db.query(TaxNexus).filter(
                TaxNexus.is_active == True,
                TaxNexus.requires_filing == True,
                TaxNexus.tenant_id == tenant_id
            ).all()
            
            scheduled_count = 0
            errors = []
            
            for nexus in nexus_list:
                try:
                    # Check if filing is due
                    if self._is_filing_due(nexus, frequency):
                        # Schedule filing generation
                        task_id = await self._schedule_filing_task(
                            nexus, tenant_id
                        )
                        
                        if task_id:
                            scheduled_count += 1
                            
                            # Update nexus next filing date
                            nexus.next_filing_date = self._calculate_next_filing_date(
                                nexus
                            )
                
                except Exception as e:
                    errors.append({
                        "nexus_id": nexus.id,
                        "jurisdiction": nexus.jurisdiction.name,
                        "error": str(e)
                    })
            
            if scheduled_count > 0:
                self.db.commit()
            
            return {
                "scheduled_count": scheduled_count,
                "total_nexus": len(nexus_list),
                "errors": errors,
                "next_run": self._get_next_run_time(frequency)
            }
            
        except Exception as e:
            logger.error(f"Error scheduling automated filings: {str(e)}")
            raise
    
    async def generate_automated_filing(
        self,
        nexus_id: int,
        tenant_id: Optional[int] = None,
        user_id: str = "system"
    ) -> TaxFiling:
        """Generate an automated tax filing for a nexus"""
        try:
            # Get nexus details
            nexus = self.db.query(TaxNexus).filter(
                TaxNexus.id == nexus_id,
                TaxNexus.tenant_id == tenant_id
            ).first()
            
            if not nexus:
                raise ValueError(f"Nexus {nexus_id} not found")
            
            # Determine filing period
            period_end = self._get_period_end_date(nexus)
            period_start = self._get_period_start_date(nexus, period_end)
            
            # Check if filing already exists
            existing = self.db.query(TaxFiling).filter(
                TaxFiling.jurisdiction_id == nexus.jurisdiction_id,
                TaxFiling.period_start == period_start,
                TaxFiling.period_end == period_end,
                TaxFiling.tenant_id == tenant_id
            ).first()
            
            if existing:
                logger.info(
                    f"Filing already exists for {nexus.jurisdiction.name} "
                    f"period {period_start} to {period_end}"
                )
                return existing
            
            # Collect transaction data
            transaction_data = await self._collect_transaction_data(
                nexus.jurisdiction_id,
                period_start,
                period_end,
                tenant_id
            )
            
            # Generate filing
            filing_data = TaxFilingCreate(
                internal_reference=self._generate_internal_reference(nexus, period_end),
                jurisdiction_id=nexus.jurisdiction_id,
                filing_type=self._determine_filing_type(nexus),
                period_start=period_start,
                period_end=period_end,
                due_date=self._calculate_due_date(nexus, period_end),
                gross_sales=transaction_data["gross_sales"],
                taxable_sales=transaction_data["taxable_sales"],
                exempt_sales=transaction_data["exempt_sales"],
                tax_collected=transaction_data["tax_collected"],
                form_type=self._get_form_type(nexus),
                notes="Generated automatically by tax automation system",
                line_items=self._generate_line_items(transaction_data),
                attachments=[]
            )
            
            # Create filing
            filing_response = self.compliance_service.create_filing(
                filing_data, user_id, tenant_id
            )
            
            # Get the filing object
            filing = self.db.query(TaxFiling).filter(
                TaxFiling.id == filing_response.id
            ).first()
            
            # Validate filing data
            validation_result = await self._validate_filing_data(filing)
            
            if validation_result["is_valid"]:
                # Mark as ready if validation passes
                filing.status = FilingStatus.READY
                self.db.commit()
            else:
                # Add validation warnings to notes
                filing.notes += f"\n\nValidation warnings: {validation_result['warnings']}"
                self.db.commit()
            
            logger.info(
                f"Generated automated filing {filing.filing_id} for "
                f"{nexus.jurisdiction.name}"
            )
            
            return filing
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error generating automated filing: {str(e)}")
            raise
    
    async def auto_submit_ready_filings(
        self,
        tenant_id: Optional[int] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Automatically submit ready filings"""
        try:
            # Get all ready filings
            ready_filings = self.db.query(TaxFiling).filter(
                TaxFiling.status == FilingStatus.READY,
                TaxFiling.tenant_id == tenant_id
            ).all()
            
            submitted_count = 0
            errors = []
            
            for filing in ready_filings:
                try:
                    # Check if auto-submit is enabled for this jurisdiction
                    if not self._is_auto_submit_enabled(filing.jurisdiction_id, tenant_id):
                        continue
                    
                    # Validate one more time before submission
                    validation_result = await self._validate_filing_data(filing)
                    
                    if not validation_result["is_valid"]:
                        errors.append({
                            "filing_id": filing.id,
                            "error": "Validation failed",
                            "details": validation_result["errors"]
                        })
                        continue
                    
                    if not dry_run:
                        # Submit filing
                        submit_data = TaxFilingSubmit(
                            prepared_by="Tax Automation System",
                            reviewed_by="Auto-Review",
                            approved_by="Auto-Approval",
                            submission_method="electronic_auto"
                        )
                        
                        # Call external API or submission service
                        submission_result = await self._submit_to_tax_authority(
                            filing, submit_data
                        )
                        
                        if submission_result["success"]:
                            # Update filing status
                            self.compliance_service.submit_filing(
                                filing.id,
                                submit_data,
                                "system",
                                tenant_id
                            )
                            
                            submitted_count += 1
                        else:
                            errors.append({
                                "filing_id": filing.id,
                                "error": "Submission failed",
                                "details": submission_result["error"]
                            })
                    else:
                        # Dry run - just count
                        submitted_count += 1
                        
                except Exception as e:
                    errors.append({
                        "filing_id": filing.id,
                        "error": str(e)
                    })
            
            return {
                "ready_count": len(ready_filings),
                "submitted_count": submitted_count,
                "errors": errors,
                "dry_run": dry_run
            }
            
        except Exception as e:
            logger.error(f"Error auto-submitting filings: {str(e)}")
            raise
    
    async def reconcile_tax_accounts(
        self,
        tenant_id: Optional[int] = None,
        period_start: Optional[date] = None,
        period_end: Optional[date] = None
    ) -> Dict[str, Any]:
        """Reconcile tax accounts with transaction data"""
        try:
            if not period_end:
                period_end = date.today()
            if not period_start:
                period_start = period_end - timedelta(days=90)
            
            # Get all filings in period
            filings = self.db.query(TaxFiling).filter(
                TaxFiling.tenant_id == tenant_id,
                TaxFiling.period_start >= period_start,
                TaxFiling.period_end <= period_end
            ).all()
            
            reconciliation_results = []
            total_discrepancies = Decimal("0")
            
            for filing in filings:
                # Get actual transaction data
                actual_data = await self._collect_transaction_data(
                    filing.jurisdiction_id,
                    filing.period_start,
                    filing.period_end,
                    tenant_id
                )
                
                # Compare with filed amounts
                discrepancies = self._calculate_discrepancies(
                    filing, actual_data
                )
                
                if discrepancies["total_discrepancy"] != Decimal("0"):
                    reconciliation_results.append({
                        "filing_id": filing.id,
                        "jurisdiction": filing.jurisdiction.name,
                        "period": f"{filing.period_start} to {filing.period_end}",
                        "discrepancies": discrepancies,
                        "action_required": self._determine_reconciliation_action(
                            discrepancies
                        )
                    })
                    
                    total_discrepancies += abs(discrepancies["total_discrepancy"])
            
            return {
                "period": f"{period_start} to {period_end}",
                "filings_reviewed": len(filings),
                "discrepancies_found": len(reconciliation_results),
                "total_discrepancy_amount": float(total_discrepancies),
                "reconciliation_details": reconciliation_results
            }
            
        except Exception as e:
            logger.error(f"Error reconciling tax accounts: {str(e)}")
            raise
    
    async def generate_estimated_payments(
        self,
        tenant_id: Optional[int] = None,
        tax_year: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate estimated tax payment schedule"""
        try:
            if not tax_year:
                tax_year = date.today().year
            
            # Get jurisdictions requiring estimated payments
            jurisdictions = self.db.query(TaxJurisdiction).filter(
                TaxJurisdiction.is_active == True,
                TaxJurisdiction.filing_frequency.in_(["quarterly", "monthly"]),
                TaxJurisdiction.tenant_id == tenant_id
            ).all()
            
            payment_schedule = []
            total_estimated = Decimal("0")
            
            for jurisdiction in jurisdictions:
                # Calculate estimated tax based on previous year
                previous_year_tax = self._calculate_previous_year_tax(
                    jurisdiction.id, tax_year - 1, tenant_id
                )
                
                # Apply safe harbor rules (110% of previous year)
                estimated_annual = previous_year_tax * Decimal("1.1")
                
                # Generate payment schedule
                if jurisdiction.filing_frequency == "quarterly":
                    quarterly_amount = estimated_annual / 4
                    
                    for quarter in range(1, 5):
                        due_date = self._get_estimated_payment_due_date(
                            tax_year, quarter
                        )
                        
                        payment_schedule.append({
                            "jurisdiction": jurisdiction.name,
                            "jurisdiction_id": jurisdiction.id,
                            "tax_year": tax_year,
                            "period": f"Q{quarter}",
                            "due_date": due_date,
                            "estimated_amount": float(quarterly_amount),
                            "based_on": "110% safe harbor"
                        })
                        
                        total_estimated += quarterly_amount
                
                elif jurisdiction.filing_frequency == "monthly":
                    monthly_amount = estimated_annual / 12
                    
                    for month in range(1, 13):
                        due_date = date(tax_year, month, jurisdiction.filing_due_day or 15)
                        
                        payment_schedule.append({
                            "jurisdiction": jurisdiction.name,
                            "jurisdiction_id": jurisdiction.id,
                            "tax_year": tax_year,
                            "period": f"Month {month}",
                            "due_date": due_date,
                            "estimated_amount": float(monthly_amount),
                            "based_on": "110% safe harbor"
                        })
                        
                        total_estimated += monthly_amount
            
            return {
                "tax_year": tax_year,
                "total_jurisdictions": len(jurisdictions),
                "total_estimated_tax": float(total_estimated),
                "payment_count": len(payment_schedule),
                "payment_schedule": sorted(payment_schedule, key=lambda x: x["due_date"])
            }
            
        except Exception as e:
            logger.error(f"Error generating estimated payments: {str(e)}")
            raise
    
    # Helper methods
    def _is_filing_due(
        self,
        nexus: TaxNexus,
        frequency: AutomationFrequency
    ) -> bool:
        """Check if a filing is due for a nexus"""
        if not nexus.filing_frequency:
            return False
        
        today = date.today()
        
        # Check next filing date
        if nexus.next_filing_date and nexus.next_filing_date > today:
            return False
        
        # Check based on frequency
        if frequency == AutomationFrequency.DAILY:
            # Check if any filing is due today or overdue
            return nexus.next_filing_date <= today if nexus.next_filing_date else True
        
        elif frequency == AutomationFrequency.WEEKLY:
            # Check if filing is due within next week
            week_ahead = today + timedelta(days=7)
            return nexus.next_filing_date <= week_ahead if nexus.next_filing_date else True
        
        elif frequency == AutomationFrequency.MONTHLY:
            # Check if it's time for monthly filing
            if nexus.filing_frequency == "monthly":
                return today.day >= (nexus.jurisdiction.filing_due_day or 15) - 5
        
        return False
    
    async def _schedule_filing_task(
        self,
        nexus: TaxNexus,
        tenant_id: Optional[int]
    ) -> Optional[str]:
        """Schedule a filing generation task"""
        try:
            task_id = str(uuid.uuid4())
            
            # In production, this would use a task queue like Celery
            # For now, we'll use asyncio
            task = asyncio.create_task(
                self.generate_automated_filing(
                    nexus.id, tenant_id, "system"
                )
            )
            
            self._automation_tasks[task_id] = task
            
            return task_id
            
        except Exception as e:
            logger.error(f"Error scheduling filing task: {str(e)}")
            return None
    
    def _calculate_next_filing_date(self, nexus: TaxNexus) -> date:
        """Calculate next filing date based on frequency"""
        today = date.today()
        
        if nexus.filing_frequency == "monthly":
            # Next month, same day
            next_month = today.replace(day=1) + timedelta(days=32)
            due_day = nexus.jurisdiction.filing_due_day or 20
            return next_month.replace(day=min(due_day, 28))
        
        elif nexus.filing_frequency == "quarterly":
            # Next quarter
            current_quarter = (today.month - 1) // 3
            next_quarter_month = ((current_quarter + 1) * 3) + 1
            
            if next_quarter_month > 12:
                next_quarter_month = 1
                year = today.year + 1
            else:
                year = today.year
            
            return date(year, next_quarter_month, nexus.jurisdiction.filing_due_day or 20)
        
        elif nexus.filing_frequency == "annually":
            # Next year, same date
            return today.replace(year=today.year + 1)
        
        return today + timedelta(days=30)
    
    def _get_period_end_date(self, nexus: TaxNexus) -> date:
        """Get period end date for filing"""
        today = date.today()
        
        if nexus.filing_frequency == "monthly":
            # End of previous month
            first_day = today.replace(day=1)
            return first_day - timedelta(days=1)
        
        elif nexus.filing_frequency == "quarterly":
            # End of previous quarter
            current_quarter = (today.month - 1) // 3
            quarter_end_month = current_quarter * 3
            
            if quarter_end_month == 0:
                quarter_end_month = 12
                year = today.year - 1
            else:
                year = today.year
            
            # Get last day of quarter
            if quarter_end_month in [3, 6, 9]:
                day = 30
            elif quarter_end_month == 12:
                day = 31
            
            return date(year, quarter_end_month, day)
        
        return today - timedelta(days=1)
    
    def _get_period_start_date(self, nexus: TaxNexus, period_end: date) -> date:
        """Get period start date based on end date and frequency"""
        if nexus.filing_frequency == "monthly":
            return period_end.replace(day=1)
        
        elif nexus.filing_frequency == "quarterly":
            # Start of quarter
            quarter_month = period_end.month
            if quarter_month in [3, 6, 9, 12]:
                start_month = quarter_month - 2
                return date(period_end.year, start_month, 1)
        
        elif nexus.filing_frequency == "annually":
            return date(period_end.year, 1, 1)
        
        # Default to month
        return period_end.replace(day=1)
    
    async def _collect_transaction_data(
        self,
        jurisdiction_id: int,
        period_start: date,
        period_end: date,
        tenant_id: Optional[int]
    ) -> Dict[str, Decimal]:
        """Collect transaction data for filing period"""
        # This would integrate with order/transaction system
        # For now, return mock data
        
        # In production, this would query actual transaction data
        # filtered by jurisdiction, date range, and tenant
        
        return {
            "gross_sales": Decimal("50000.00"),
            "taxable_sales": Decimal("45000.00"),
            "exempt_sales": Decimal("5000.00"),
            "tax_collected": Decimal("3375.00"),  # 7.5% of taxable
            "transaction_count": 250,
            "by_category": {
                "general": Decimal("30000.00"),
                "food": Decimal("10000.00"),
                "services": Decimal("5000.00")
            }
        }
    
    def _determine_filing_type(self, nexus: TaxNexus) -> FilingType:
        """Determine filing type based on nexus"""
        # Map jurisdiction type to filing type
        jurisdiction = nexus.jurisdiction
        
        if jurisdiction.jurisdiction_type in ["state", "city", "county"]:
            return FilingType.SALES_TAX
        elif nexus.nexus_type == "payroll":
            return FilingType.PAYROLL_TAX
        else:
            return FilingType.SALES_TAX  # Default
    
    def _calculate_due_date(self, nexus: TaxNexus, period_end: date) -> date:
        """Calculate filing due date"""
        jurisdiction = nexus.jurisdiction
        
        # Add grace period based on filing frequency
        if nexus.filing_frequency == "monthly":
            days_after = jurisdiction.filing_due_day or 20
            due_month = period_end + timedelta(days=32)
            return due_month.replace(day=1) + timedelta(days=days_after - 1)
        
        elif nexus.filing_frequency == "quarterly":
            # Usually due 1 month after quarter end
            return period_end + timedelta(days=30)
        
        # Default
        return period_end + timedelta(days=20)
    
    def _generate_internal_reference(self, nexus: TaxNexus, period_end: date) -> str:
        """Generate internal reference number"""
        return f"AUTO-{nexus.jurisdiction.code}-{period_end.strftime('%Y%m')}-{uuid.uuid4().hex[:6]}"
    
    def _get_form_type(self, nexus: TaxNexus) -> str:
        """Get tax form type for jurisdiction"""
        # This would map to actual form numbers
        # For example: "CA-BOE-401", "NY-ST-100", etc.
        return f"{nexus.jurisdiction.code}-SALES-{nexus.filing_frequency.upper()}"
    
    def _generate_line_items(
        self,
        transaction_data: Dict[str, Any]
    ) -> List[TaxFilingLineItemCreate]:
        """Generate line items from transaction data"""
        line_items = []
        line_number = 1
        
        # Create line items by category
        for category, amount in transaction_data.get("by_category", {}).items():
            if amount > 0:
                line_items.append(TaxFilingLineItemCreate(
                    line_number=str(line_number),
                    description=f"Taxable sales - {category}",
                    tax_category=category,
                    gross_amount=amount,
                    deductions=Decimal("0"),
                    exemptions=Decimal("0"),
                    taxable_amount=amount,
                    tax_rate=Decimal("7.5"),  # Would get actual rate
                    tax_amount=amount * Decimal("0.075"),
                    product_category=category,
                    transaction_count=int(transaction_data["transaction_count"] * 
                                         (amount / transaction_data["gross_sales"]))
                ))
                line_number += 1
        
        # Add exempt sales line if any
        if transaction_data["exempt_sales"] > 0:
            line_items.append(TaxFilingLineItemCreate(
                line_number=str(line_number),
                description="Exempt sales",
                tax_category="exempt",
                gross_amount=transaction_data["exempt_sales"],
                deductions=Decimal("0"),
                exemptions=transaction_data["exempt_sales"],
                taxable_amount=Decimal("0"),
                tax_rate=Decimal("0"),
                tax_amount=Decimal("0")
            ))
        
        return line_items
    
    async def _validate_filing_data(self, filing: TaxFiling) -> Dict[str, Any]:
        """Validate filing data before submission"""
        errors = []
        warnings = []
        
        # Check required fields
        if not filing.filing_number and filing.status != FilingStatus.DRAFT:
            errors.append("Filing number is required")
        
        # Check amounts
        if filing.gross_sales < filing.taxable_sales:
            errors.append("Gross sales cannot be less than taxable sales")
        
        if filing.tax_due <= 0 and filing.taxable_sales > 0:
            warnings.append("Tax due is zero despite taxable sales")
        
        # Check line items total
        line_items_total = sum(
            item.tax_amount for item in filing.line_items
        )
        
        if abs(line_items_total - filing.tax_due) > Decimal("0.01"):
            errors.append(
                f"Line items total ({line_items_total}) does not match "
                f"tax due ({filing.tax_due})"
            )
        
        # Check for required attachments
        # This would check jurisdiction-specific requirements
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def _is_auto_submit_enabled(
        self,
        jurisdiction_id: int,
        tenant_id: Optional[int]
    ) -> bool:
        """Check if auto-submit is enabled for jurisdiction"""
        # This would check configuration settings
        # For now, return False for safety
        return False
    
    async def _submit_to_tax_authority(
        self,
        filing: TaxFiling,
        submit_data: TaxFilingSubmit
    ) -> Dict[str, Any]:
        """Submit filing to tax authority API"""
        try:
            # This would integrate with actual tax authority APIs
            # For example: state tax portals, IRS MeF, etc.
            
            # Mock successful submission
            return {
                "success": True,
                "confirmation_number": f"CONF-{uuid.uuid4().hex[:10].upper()}",
                "submitted_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _calculate_discrepancies(
        self,
        filing: TaxFiling,
        actual_data: Dict[str, Decimal]
    ) -> Dict[str, Any]:
        """Calculate discrepancies between filed and actual amounts"""
        discrepancies = {}
        
        # Compare each field
        fields_to_compare = [
            ("gross_sales", "gross_sales"),
            ("taxable_sales", "taxable_sales"),
            ("exempt_sales", "exempt_sales"),
            ("tax_collected", "tax_collected")
        ]
        
        total_discrepancy = Decimal("0")
        
        for filing_field, data_field in fields_to_compare:
            filed_amount = getattr(filing, filing_field) or Decimal("0")
            actual_amount = actual_data.get(data_field, Decimal("0"))
            
            discrepancy = actual_amount - filed_amount
            
            if discrepancy != Decimal("0"):
                discrepancies[filing_field] = {
                    "filed": float(filed_amount),
                    "actual": float(actual_amount),
                    "discrepancy": float(discrepancy),
                    "percentage": float(
                        (discrepancy / filed_amount * 100)
                        if filed_amount > 0 else 0
                    )
                }
                
                total_discrepancy += discrepancy
        
        discrepancies["total_discrepancy"] = total_discrepancy
        
        return discrepancies
    
    def _determine_reconciliation_action(
        self,
        discrepancies: Dict[str, Any]
    ) -> str:
        """Determine required action based on discrepancies"""
        total = abs(discrepancies["total_discrepancy"])
        
        if total < Decimal("100"):
            return "No action required - immaterial difference"
        elif total < Decimal("1000"):
            return "Monitor - may require adjustment in next filing"
        else:
            return "Amendment required - material difference"
    
    def _calculate_previous_year_tax(
        self,
        jurisdiction_id: int,
        year: int,
        tenant_id: Optional[int]
    ) -> Decimal:
        """Calculate total tax for previous year"""
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        
        filings = self.db.query(TaxFiling).filter(
            TaxFiling.jurisdiction_id == jurisdiction_id,
            TaxFiling.tenant_id == tenant_id,
            TaxFiling.period_start >= start_date,
            TaxFiling.period_end <= end_date,
            TaxFiling.status.in_([FilingStatus.SUBMITTED, FilingStatus.ACCEPTED, FilingStatus.PAID])
        ).all()
        
        return sum(f.tax_due for f in filings)
    
    def _get_estimated_payment_due_date(
        self,
        year: int,
        quarter: int
    ) -> date:
        """Get estimated payment due date for quarter"""
        # Standard quarterly due dates
        due_dates = {
            1: date(year, 4, 15),
            2: date(year, 6, 15),
            3: date(year, 9, 15),
            4: date(year + 1, 1, 15)
        }
        
        return due_dates.get(quarter, date(year, 1, 15))
    
    def _get_next_run_time(self, frequency: AutomationFrequency) -> datetime:
        """Get next scheduled run time"""
        now = datetime.now()
        
        if frequency == AutomationFrequency.DAILY:
            # Next day at 2 AM
            next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
        
        elif frequency == AutomationFrequency.WEEKLY:
            # Next Monday at 2 AM
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0 and now.hour >= 2:
                days_until_monday = 7
            next_run = now + timedelta(days=days_until_monday)
            next_run = next_run.replace(hour=2, minute=0, second=0, microsecond=0)
        
        elif frequency == AutomationFrequency.MONTHLY:
            # First day of next month at 2 AM
            if now.month == 12:
                next_run = now.replace(year=now.year + 1, month=1, day=1)
            else:
                next_run = now.replace(month=now.month + 1, day=1)
            next_run = next_run.replace(hour=2, minute=0, second=0, microsecond=0)
        
        else:
            next_run = now + timedelta(hours=1)
        
        return next_run