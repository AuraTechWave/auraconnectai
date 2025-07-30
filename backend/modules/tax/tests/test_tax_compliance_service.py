# backend/modules/tax/tests/test_tax_compliance_service.py

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid

from backend.core.database import Base
from backend.modules.tax.models import (
    TaxJurisdiction, TaxFiling, TaxFilingLineItem,
    FilingStatus, FilingType
)
from backend.modules.tax.schemas import (
    TaxFilingCreate, TaxFilingUpdate, TaxFilingSubmit,
    TaxFilingLineItemCreate, TaxRemittanceCreate,
    TaxReportRequest
)
from backend.modules.tax.services import TaxComplianceService


class TestTaxComplianceService:
    """Test suite for tax compliance service"""
    
    @pytest.fixture
    def test_db(self):
        """Create test database"""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        yield db
        
        db.close()
        Base.metadata.drop_all(bind=engine)
    
    @pytest.fixture
    def sample_jurisdiction(self, test_db):
        """Create sample jurisdiction"""
        jurisdiction = TaxJurisdiction(
            jurisdiction_id=uuid.uuid4(),
            name="California",
            code="CA",
            jurisdiction_type="state",
            country_code="US",
            state_code="CA",
            filing_frequency="monthly",
            filing_due_day=20,
            is_active=True,
            effective_date=date(2020, 1, 1),
            tenant_id=1
        )
        test_db.add(jurisdiction)
        test_db.commit()
        return jurisdiction
    
    def test_create_filing(self, test_db, sample_jurisdiction):
        """Test creating a tax filing"""
        service = TaxComplianceService(test_db)
        
        filing_data = TaxFilingCreate(
            internal_reference="TEST-2025-01",
            jurisdiction_id=sample_jurisdiction.id,
            filing_type=FilingType.SALES_TAX,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
            due_date=date(2025, 2, 20),
            gross_sales=Decimal("100000.00"),
            taxable_sales=Decimal("90000.00"),
            exempt_sales=Decimal("10000.00"),
            tax_collected=Decimal("7200.00"),
            form_type="CA-SALES-MONTHLY",
            line_items=[
                TaxFilingLineItemCreate(
                    line_number="1",
                    description="Taxable sales",
                    gross_amount=Decimal("90000.00"),
                    taxable_amount=Decimal("90000.00"),
                    tax_rate=Decimal("8.0"),
                    tax_amount=Decimal("7200.00")
                )
            ]
        )
        
        filing = service.create_filing(filing_data, "test_user", 1)
        
        assert filing.id is not None
        assert filing.filing_id is not None
        assert filing.status == FilingStatus.DRAFT
        assert filing.tax_due == Decimal("7200.00")
        assert filing.total_due == Decimal("7200.00")
        assert len(filing.line_items) == 1
    
    def test_update_filing(self, test_db, sample_jurisdiction):
        """Test updating a tax filing"""
        service = TaxComplianceService(test_db)
        
        # Create filing
        filing_data = TaxFilingCreate(
            internal_reference="TEST-2025-02",
            jurisdiction_id=sample_jurisdiction.id,
            filing_type=FilingType.SALES_TAX,
            period_start=date(2025, 2, 1),
            period_end=date(2025, 2, 28),
            due_date=date(2025, 3, 20),
            gross_sales=Decimal("80000.00"),
            taxable_sales=Decimal("75000.00"),
            exempt_sales=Decimal("5000.00"),
            tax_collected=Decimal("6000.00")
        )
        
        filing = service.create_filing(filing_data, "test_user", 1)
        
        # Update filing
        update_data = TaxFilingUpdate(
            gross_sales=Decimal("85000.00"),
            taxable_sales=Decimal("80000.00"),
            tax_collected=Decimal("6400.00"),
            notes="Updated after review"
        )
        
        updated = service.update_filing(filing.id, update_data, "test_user", 1)
        
        assert updated.gross_sales == Decimal("85000.00")
        assert updated.taxable_sales == Decimal("80000.00")
        assert updated.tax_collected == Decimal("6400.00")
        assert "Updated after review" in updated.notes
    
    def test_submit_filing(self, test_db, sample_jurisdiction):
        """Test submitting a tax filing"""
        service = TaxComplianceService(test_db)
        
        # Create and prepare filing
        filing_data = TaxFilingCreate(
            internal_reference="TEST-2025-03",
            jurisdiction_id=sample_jurisdiction.id,
            filing_type=FilingType.SALES_TAX,
            period_start=date(2025, 3, 1),
            period_end=date(2025, 3, 31),
            due_date=date(2025, 4, 20),
            gross_sales=Decimal("120000.00"),
            taxable_sales=Decimal("110000.00"),
            exempt_sales=Decimal("10000.00"),
            tax_collected=Decimal("8800.00")
        )
        
        filing = service.create_filing(filing_data, "test_user", 1)
        
        # Mark as ready
        service.update_filing(
            filing.id,
            TaxFilingUpdate(status=FilingStatus.READY),
            "test_user",
            1
        )
        
        # Submit filing
        submit_data = TaxFilingSubmit(
            prepared_by="John Doe",
            reviewed_by="Jane Smith",
            approved_by="Bob Johnson"
        )
        
        submitted = service.submit_filing(filing.id, submit_data, "test_user", 1)
        
        assert submitted.status == FilingStatus.SUBMITTED
        assert submitted.filed_date is not None
        assert submitted.filing_number is not None
        assert submitted.prepared_by == "John Doe"
    
    def test_compliance_dashboard(self, test_db, sample_jurisdiction):
        """Test compliance dashboard generation"""
        service = TaxComplianceService(test_db)
        
        # Create multiple filings with different statuses
        today = date.today()
        
        # Past filing - paid
        past_filing = TaxFiling(
            filing_id=uuid.uuid4(),
            internal_reference="PAST-001",
            jurisdiction_id=sample_jurisdiction.id,
            filing_type=FilingType.SALES_TAX,
            period_start=today - timedelta(days=60),
            period_end=today - timedelta(days=30),
            due_date=today - timedelta(days=10),
            status=FilingStatus.PAID,
            tax_due=Decimal("5000.00"),
            total_due=Decimal("5000.00"),
            tenant_id=1
        )
        test_db.add(past_filing)
        
        # Current filing - draft
        current_filing = TaxFiling(
            filing_id=uuid.uuid4(),
            internal_reference="CURRENT-001",
            jurisdiction_id=sample_jurisdiction.id,
            filing_type=FilingType.SALES_TAX,
            period_start=today.replace(day=1),
            period_end=today,
            due_date=today + timedelta(days=20),
            status=FilingStatus.DRAFT,
            tax_due=Decimal("6000.00"),
            total_due=Decimal("6000.00"),
            tenant_id=1
        )
        test_db.add(current_filing)
        
        # Overdue filing
        overdue_filing = TaxFiling(
            filing_id=uuid.uuid4(),
            internal_reference="OVERDUE-001",
            jurisdiction_id=sample_jurisdiction.id,
            filing_type=FilingType.SALES_TAX,
            period_start=today - timedelta(days=90),
            period_end=today - timedelta(days=60),
            due_date=today - timedelta(days=40),
            status=FilingStatus.DRAFT,
            tax_due=Decimal("4000.00"),
            total_due=Decimal("4000.00"),
            tenant_id=1
        )
        test_db.add(overdue_filing)
        
        test_db.commit()
        
        # Get dashboard
        dashboard = service.get_compliance_dashboard(1, today)
        
        assert dashboard.total_jurisdictions == 1
        assert dashboard.upcoming_deadlines[0]["filing_id"] == current_filing.id
        assert len(dashboard.overdue_filings) == 1
        assert dashboard.overdue_filings[0]["filing_id"] == overdue_filing.id
        assert dashboard.total_tax_liability == Decimal("10000.00")  # Current + Overdue
        assert dashboard.total_tax_paid == Decimal("5000.00")  # Past paid
        assert dashboard.outstanding_balance == Decimal("5000.00")
    
    def test_remittance_creation(self, test_db, sample_jurisdiction):
        """Test creating tax remittance"""
        service = TaxComplianceService(test_db)
        
        # Create filings to pay
        filing1 = TaxFiling(
            filing_id=uuid.uuid4(),
            internal_reference="PAY-001",
            jurisdiction_id=sample_jurisdiction.id,
            filing_type=FilingType.SALES_TAX,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
            due_date=date(2025, 2, 20),
            status=FilingStatus.SUBMITTED,
            tax_due=Decimal("3000.00"),
            total_due=Decimal("3000.00"),
            tenant_id=1
        )
        test_db.add(filing1)
        
        filing2 = TaxFiling(
            filing_id=uuid.uuid4(),
            internal_reference="PAY-002",
            jurisdiction_id=sample_jurisdiction.id,
            filing_type=FilingType.SALES_TAX,
            period_start=date(2025, 2, 1),
            period_end=date(2025, 2, 28),
            due_date=date(2025, 3, 20),
            status=FilingStatus.SUBMITTED,
            tax_due=Decimal("2000.00"),
            total_due=Decimal("2000.00"),
            tenant_id=1
        )
        test_db.add(filing2)
        test_db.commit()
        
        # Create remittance
        remittance_data = TaxRemittanceCreate(
            payment_date=date.today(),
            payment_method="ach",
            payment_reference="ACH-12345",
            payment_amount=Decimal("5000.00"),
            filing_references=[filing1.id, filing2.id],
            bank_account_last4="1234",
            bank_name="Test Bank"
        )
        
        result = service.create_remittance(remittance_data, "test_user", 1)
        
        assert result["remittance_id"] is not None
        assert result["filings_updated"] == 2
        assert result["status"] == "pending"
    
    def test_report_generation(self, test_db, sample_jurisdiction):
        """Test tax report generation"""
        service = TaxComplianceService(test_db)
        
        # Create sample filings
        for i in range(3):
            filing = TaxFiling(
                filing_id=uuid.uuid4(),
                internal_reference=f"REPORT-{i:03d}",
                jurisdiction_id=sample_jurisdiction.id,
                filing_type=FilingType.SALES_TAX,
                period_start=date(2025, i+1, 1),
                period_end=date(2025, i+1, 28),
                due_date=date(2025, i+2, 20),
                status=FilingStatus.PAID,
                gross_sales=Decimal(f"{50000 + i*10000}.00"),
                taxable_sales=Decimal(f"{45000 + i*9000}.00"),
                tax_due=Decimal(f"{3600 + i*720}.00"),
                total_due=Decimal(f"{3600 + i*720}.00"),
                tenant_id=1
            )
            test_db.add(filing)
        test_db.commit()
        
        # Generate report
        report_request = TaxReportRequest(
            report_type="summary",
            period_start=date(2025, 1, 1),
            period_end=date(2025, 3, 31),
            include_details=True,
            include_trends=True
        )
        
        report = service.generate_report(report_request, "test_user", 1)
        
        assert report.report_id is not None
        assert report.total_records == 3
        assert report.summary["total_filings"] == 3
        assert report.summary["total_tax_due"] == Decimal("12240.00")  # Sum of all tax
        assert len(report.details) == 3
        assert report.trends is not None
    
    def test_filing_validation(self, test_db, sample_jurisdiction):
        """Test filing data validation"""
        service = TaxComplianceService(test_db)
        
        # Test invalid date range
        with pytest.raises(ValueError):
            TaxFilingCreate(
                internal_reference="INVALID-001",
                jurisdiction_id=sample_jurisdiction.id,
                filing_type=FilingType.SALES_TAX,
                period_start=date(2025, 2, 1),
                period_end=date(2025, 1, 31),  # End before start
                due_date=date(2025, 3, 20),
                gross_sales=Decimal("100000.00"),
                taxable_sales=Decimal("90000.00"),
                exempt_sales=Decimal("10000.00"),
                tax_collected=Decimal("7200.00")
            )
    
    def test_duplicate_filing_prevention(self, test_db, sample_jurisdiction):
        """Test that duplicate filings are prevented"""
        service = TaxComplianceService(test_db)
        
        filing_data = TaxFilingCreate(
            internal_reference="DUP-001",
            jurisdiction_id=sample_jurisdiction.id,
            filing_type=FilingType.SALES_TAX,
            period_start=date(2025, 4, 1),
            period_end=date(2025, 4, 30),
            due_date=date(2025, 5, 20),
            gross_sales=Decimal("100000.00"),
            taxable_sales=Decimal("90000.00"),
            exempt_sales=Decimal("10000.00"),
            tax_collected=Decimal("7200.00")
        )
        
        # Create first filing
        filing1 = service.create_filing(filing_data, "test_user", 1)
        
        # Mark as submitted
        service.update_filing(
            filing1.id,
            TaxFilingUpdate(status=FilingStatus.SUBMITTED),
            "test_user",
            1
        )
        
        # Try to create duplicate
        filing_data.internal_reference = "DUP-002"  # Different reference
        
        with pytest.raises(ValueError, match="Filing already exists"):
            service.create_filing(filing_data, "test_user", 1)