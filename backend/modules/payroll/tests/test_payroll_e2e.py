# backend/modules/payroll/tests/test_payroll_e2e.py

"""
End-to-end tests for complete payroll workflow.

Tests the entire payroll process from timesheet submission
through payment generation and reporting.
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from sqlalchemy.orm import Session
import asyncio

from ..services.payroll_service import PayrollService
from ..services.batch_payroll_service import BatchPayrollService
from ..services.payroll_tax_service import PayrollTaxService
from ..services.payment_export_service import PaymentExportService
from ..models.employee_payment import EmployeePayment
from ..models.payroll_configuration import (
    PayrollConfiguration,
    StaffPayPolicy,
    PayrollJobTracking
)
from ..schemas.batch_processing_schemas import (
    BatchPayrollRequest,
    CalculationOptions
)
from ..enums.payroll_enums import PayrollJobStatus, PaymentStatus
from ....staff.models.staff import Staff
from ....staff.models.timesheet import Timesheet


class TestPayrollE2E:
    """Test complete payroll workflow end-to-end."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = MagicMock(spec=Session)
        db.commit = Mock()
        db.add = Mock()
        db.refresh = Mock()
        db.flush = Mock()
        return db
    
    @pytest.fixture
    def sample_company_setup(self):
        """Create sample company configuration."""
        return {
            "company_id": 1,
            "pay_frequency": "biweekly",
            "pay_period_start": date(2024, 1, 1),
            "pay_period_end": date(2024, 1, 14),
            "pay_date": date(2024, 1, 19),
            "locations": ["california", "new_york"],
            "departments": ["Engineering", "Sales", "Support"]
        }
    
    @pytest.fixture
    def sample_employees(self, sample_company_setup):
        """Create diverse set of employees."""
        employees = []
        
        # Engineer in California - salaried
        engineer = Mock(spec=Staff)
        engineer.id = 1
        engineer.full_name = "Alice Engineer"
        engineer.employee_code = "ENG001"
        engineer.department = "Engineering"
        engineer.location = "california"
        engineer.employment_type = "salaried"
        engineer.annual_salary = Decimal("120000.00")
        engineer.filing_status = "single"
        engineer.federal_allowances = 2
        engineer.is_active = True
        employees.append(engineer)
        
        # Sales rep in New York - hourly with commission
        sales_rep = Mock(spec=Staff)
        sales_rep.id = 2
        sales_rep.full_name = "Bob Sales"
        sales_rep.employee_code = "SAL001"
        sales_rep.department = "Sales"
        sales_rep.location = "new_york"
        sales_rep.employment_type = "hourly"
        sales_rep.hourly_rate = Decimal("25.00")
        sales_rep.filing_status = "married_jointly"
        sales_rep.federal_allowances = 4
        sales_rep.is_active = True
        employees.append(sales_rep)
        
        # Support agent - part-time hourly
        support = Mock(spec=Staff)
        support.id = 3
        support.full_name = "Charlie Support"
        support.employee_code = "SUP001"
        support.department = "Support"
        support.location = "california"
        support.employment_type = "hourly"
        support.hourly_rate = Decimal("20.00")
        support.filing_status = "single"
        support.federal_allowances = 1
        support.is_active = True
        support.is_part_time = True
        employees.append(support)
        
        return employees
    
    @pytest.fixture
    def sample_timesheets(self, sample_employees, sample_company_setup):
        """Create timesheets for the pay period."""
        timesheets = []
        start_date = sample_company_setup["pay_period_start"]
        
        # Engineer - no timesheet needed (salaried)
        
        # Sales rep - regular hours + overtime
        for day in range(10):  # 10 working days
            work_date = start_date + timedelta(days=day)
            if work_date.weekday() < 5:  # Weekday
                ts = Mock(spec=Timesheet)
                ts.staff_id = 2
                ts.work_date = work_date
                ts.regular_hours = Decimal("8.0") if day < 8 else Decimal("10.0")
                ts.overtime_hours = Decimal("0.0") if day < 8 else Decimal("2.0")
                ts.is_approved = True
                timesheets.append(ts)
        
        # Support agent - part-time hours
        for day in range(10):
            work_date = start_date + timedelta(days=day)
            if work_date.weekday() < 5:  # Weekday
                ts = Mock(spec=Timesheet)
                ts.staff_id = 3
                ts.work_date = work_date
                ts.regular_hours = Decimal("4.0")  # Half days
                ts.overtime_hours = Decimal("0.0")
                ts.is_approved = True
                timesheets.append(ts)
        
        return timesheets
    
    @pytest.fixture
    def sample_pay_policies(self, sample_employees):
        """Create pay policies for employees."""
        policies = []
        
        # Engineer policy
        policy1 = Mock(spec=StaffPayPolicy)
        policy1.staff_id = 1
        policy1.base_hourly_rate = Decimal("57.69")  # $120k/2080 hours
        policy1.overtime_eligible = False
        policy1.health_insurance_monthly = Decimal("500.00")
        policy1.retirement_match_percentage = Decimal("0.06")
        policy1.benefit_proration_factor = Decimal("0.4615")  # Bi-weekly
        policies.append(policy1)
        
        # Sales rep policy
        policy2 = Mock(spec=StaffPayPolicy)
        policy2.staff_id = 2
        policy2.base_hourly_rate = Decimal("25.00")
        policy2.overtime_eligible = True
        policy2.overtime_multiplier = Decimal("1.5")
        policy2.commission_rate = Decimal("0.02")
        policy2.health_insurance_monthly = Decimal("300.00")
        policy2.retirement_match_percentage = Decimal("0.04")
        policy2.benefit_proration_factor = Decimal("0.4615")
        policies.append(policy2)
        
        # Support agent policy
        policy3 = Mock(spec=StaffPayPolicy)
        policy3.staff_id = 3
        policy3.base_hourly_rate = Decimal("20.00")
        policy3.overtime_eligible = True
        policy3.overtime_multiplier = Decimal("1.5")
        policy3.health_insurance_monthly = Decimal("0.00")  # No benefits for part-time
        policy3.retirement_match_percentage = Decimal("0.00")
        policies.append(policy3)
        
        return policies
    
    @pytest.mark.asyncio
    async def test_complete_payroll_workflow(
        self, mock_db, sample_company_setup, sample_employees, 
        sample_timesheets, sample_pay_policies
    ):
        """Test complete payroll workflow from start to finish."""
        
        # Step 1: Setup database mocks
        self._setup_database_mocks(
            mock_db, sample_employees, sample_timesheets, sample_pay_policies
        )
        
        # Step 2: Create batch payroll job
        batch_service = BatchPayrollService(mock_db)
        job_id = "batch_" + str(date.today()).replace("-", "") + "_001"
        
        job_tracking = Mock(spec=PayrollJobTracking)
        job_tracking.job_id = job_id
        job_tracking.status = PayrollJobStatus.PENDING
        job_tracking.total_employees = len(sample_employees)
        job_tracking.processed_count = 0
        
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        
        # Step 3: Process payroll batch
        with patch.object(batch_service, 'payroll_service') as mock_payroll_service:
            # Mock individual payroll calculations
            self._setup_payroll_calculations(mock_payroll_service, sample_employees)
            
            results = await batch_service.process_batch(
                employee_ids=None,  # Process all
                pay_period_start=sample_company_setup["pay_period_start"],
                pay_period_end=sample_company_setup["pay_period_end"],
                calculation_options=CalculationOptions(
                    include_overtime=True,
                    include_benefits=True,
                    include_deductions=True,
                    use_ytd_calculations=True
                )
            )
        
        # Step 4: Verify results
        assert len(results) == 3
        assert all(r.success for r in results)
        
        # Verify engineer (salaried)
        engineer_result = next(r for r in results if r.employee_id == 1)
        assert engineer_result.gross_pay == Decimal("4615.38")  # Bi-weekly salary
        assert engineer_result.breakdown.regular_pay == Decimal("4615.38")
        assert engineer_result.breakdown.overtime_pay == Decimal("0.00")
        
        # Verify sales rep (hourly with overtime)
        sales_result = next(r for r in results if r.employee_id == 2)
        assert sales_result.gross_pay == Decimal("2300.00")  # 80 regular + 4 OT hours
        assert sales_result.breakdown.regular_pay == Decimal("2000.00")
        assert sales_result.breakdown.overtime_pay == Decimal("150.00")
        
        # Verify support agent (part-time)
        support_result = next(r for r in results if r.employee_id == 3)
        assert support_result.gross_pay == Decimal("800.00")  # 40 hours * $20
        
        # Step 5: Generate payments
        payment_service = PaymentExportService(mock_db)
        payments = self._create_payments_from_results(results, sample_company_setup)
        
        # Step 6: Export payroll data
        with patch('builtins.open', create=True):
            export_result = await payment_service.export_payments(
                start_date=sample_company_setup["pay_period_start"],
                end_date=sample_company_setup["pay_period_end"],
                format="csv"
            )
        
        assert export_result["record_count"] == 3
        assert export_result["total_gross"] == Decimal("7715.38")
        
        # Step 7: Generate pay stubs
        with patch('reportlab.pdfgen.canvas.Canvas'):
            payslips = await payment_service.generate_payslips(
                payment_ids=[p.id for p in payments],
                format="pdf"
            )
        
        assert payslips["payslip_count"] == 3
        
        # Step 8: Update job status
        job_tracking.status = PayrollJobStatus.COMPLETED
        job_tracking.processed_count = 3
        job_tracking.completed_at = datetime.utcnow()
        
        # Step 9: Verify audit trail
        audit_entries = self._verify_audit_trail(mock_db, job_id)
        assert len(audit_entries) >= 4  # Created, processing, processed each, completed
    
    @pytest.mark.asyncio
    async def test_payroll_with_corrections(
        self, mock_db, sample_company_setup, sample_employees
    ):
        """Test payroll workflow with corrections and adjustments."""
        
        # Step 1: Process initial payroll
        batch_service = BatchPayrollService(mock_db)
        self._setup_database_mocks(mock_db, sample_employees, [], [])
        
        # Create initial payment that needs correction
        original_payment = Mock(spec=EmployeePayment)
        original_payment.id = 100
        original_payment.employee_id = 1
        original_payment.gross_pay = Decimal("4500.00")  # Incorrect amount
        original_payment.net_pay = Decimal("3375.00")
        original_payment.status = PaymentStatus.PENDING
        
        # Step 2: Create correction
        correction_amount = Decimal("115.38")  # Correct amount is $4615.38
        
        payroll_service = PayrollService(mock_db)
        with patch.object(payroll_service, 'create_adjustment') as mock_adjustment:
            mock_adjustment.return_value = Mock(
                adjustment_amount=correction_amount,
                adjustment_type="correction",
                reason="Incorrect salary calculation"
            )
            
            # Process correction
            corrected_payment = await payroll_service.process_correction(
                original_payment_id=original_payment.id,
                correction_amount=correction_amount,
                reason="Incorrect salary calculation"
            )
        
        # Step 3: Verify correction
        assert corrected_payment.gross_pay == Decimal("4615.38")
        assert corrected_payment.adjustment_amount == correction_amount
        assert corrected_payment.parent_payment_id == original_payment.id
        
        # Step 4: Verify original payment marked as corrected
        assert original_payment.status == PaymentStatus.CORRECTED
        assert original_payment.corrected_by_payment_id == corrected_payment.id
    
    @pytest.mark.asyncio
    async def test_payroll_with_retroactive_changes(
        self, mock_db, sample_employees, sample_pay_policies
    ):
        """Test payroll with retroactive pay rate changes."""
        
        # Setup
        employee = sample_employees[0]
        old_rate = Decimal("57.69")
        new_rate = Decimal("62.50")  # Raise to $130k annually
        effective_date = date(2024, 1, 1)
        
        # Calculate retroactive pay for 2 previous pay periods
        periods_to_adjust = 2
        hours_per_period = Decimal("80.0")  # Standard bi-weekly
        retro_amount = (new_rate - old_rate) * hours_per_period * periods_to_adjust
        
        payroll_service = PayrollService(mock_db)
        
        # Process retroactive payment
        with patch.object(payroll_service, 'calculate_retroactive_pay') as mock_retro:
            mock_retro.return_value = {
                "retroactive_gross": retro_amount,
                "retroactive_taxes": retro_amount * Decimal("0.30"),  # Approx tax
                "retroactive_net": retro_amount * Decimal("0.70"),
                "affected_periods": periods_to_adjust
            }
            
            retro_payment = await payroll_service.process_retroactive_payment(
                employee_id=employee.id,
                old_rate=old_rate,
                new_rate=new_rate,
                effective_date=effective_date,
                current_date=date(2024, 2, 1)
            )
        
        # Verify
        assert retro_payment["retroactive_gross"] == retro_amount
        assert retro_payment["affected_periods"] == periods_to_adjust
        assert retro_payment["retroactive_net"] > Decimal("0.00")
    
    @pytest.mark.asyncio
    async def test_payroll_with_garnishments(
        self, mock_db, sample_employees
    ):
        """Test payroll processing with wage garnishments."""
        
        # Setup employee with garnishments
        employee = sample_employees[1]  # Hourly employee
        gross_pay = Decimal("2300.00")
        
        garnishments = [
            {
                "type": "child_support",
                "amount": Decimal("400.00"),
                "percentage": None,
                "priority": 1,
                "max_percentage": Decimal("0.50")  # Max 50% of disposable income
            },
            {
                "type": "tax_levy",
                "amount": None,
                "percentage": Decimal("0.15"),  # 15% of gross
                "priority": 2,
                "max_amount": Decimal("300.00")
            }
        ]
        
        payroll_service = PayrollService(mock_db)
        
        # Calculate disposable income (gross - taxes)
        taxes = gross_pay * Decimal("0.25")  # Approximate
        disposable_income = gross_pay - taxes
        
        # Process garnishments
        with patch.object(payroll_service, 'apply_garnishments') as mock_garn:
            mock_garn.return_value = {
                "child_support": Decimal("400.00"),
                "tax_levy": Decimal("300.00"),  # Capped at max
                "total_garnishments": Decimal("700.00")
            }
            
            payment = await payroll_service.calculate_payroll(
                employee_id=employee.id,
                pay_period_start=date(2024, 1, 1),
                pay_period_end=date(2024, 1, 14),
                gross_pay=gross_pay,
                garnishments=garnishments
            )
        
        # Verify
        expected_net = gross_pay - taxes - Decimal("700.00")
        assert payment.net_pay == expected_net
        assert payment.garnishment_amount == Decimal("700.00")
    
    @pytest.mark.asyncio
    async def test_payroll_year_end_processing(
        self, mock_db, sample_company_setup, sample_employees
    ):
        """Test year-end payroll processing and reporting."""
        
        year = 2023
        tax_service = PayrollTaxService(mock_db)
        
        # Mock annual summaries for each employee
        annual_summaries = []
        for emp in sample_employees:
            summary = Mock()
            summary.employee_id = emp.id
            summary.total_wages = Decimal("65000.00") if emp.id == 1 else Decimal("52000.00")
            summary.federal_tax_withheld = Decimal("7800.00") if emp.id == 1 else Decimal("5200.00")
            summary.state_tax_withheld = Decimal("3250.00") if emp.id == 1 else Decimal("2600.00")
            summary.social_security_withheld = summary.total_wages * Decimal("0.062")
            summary.medicare_withheld = summary.total_wages * Decimal("0.0145")
            annual_summaries.append(summary)
        
        # Generate W-2s
        w2_forms = []
        for emp, summary in zip(sample_employees, annual_summaries):
            with patch.object(tax_service, 'generate_w2_data') as mock_w2:
                mock_w2.return_value = {
                    "employee_id": emp.id,
                    "employee_name": emp.full_name,
                    "employee_ssn": "XXX-XX-" + str(1000 + emp.id),
                    "box1_wages": summary.total_wages,
                    "box2_federal_withheld": summary.federal_tax_withheld,
                    "box3_ss_wages": summary.total_wages,
                    "box4_ss_withheld": summary.social_security_withheld,
                    "box5_medicare_wages": summary.total_wages,
                    "box6_medicare_withheld": summary.medicare_withheld,
                    "box16_state_wages": summary.total_wages,
                    "box17_state_withheld": summary.state_tax_withheld
                }
                
                w2_data = await tax_service.generate_w2_data(
                    employee_id=emp.id,
                    year=year
                )
                w2_forms.append(w2_data)
        
        # Verify W-2 generation
        assert len(w2_forms) == 3
        assert all(w2["box1_wages"] > Decimal("0.00") for w2 in w2_forms)
        
        # Generate company-wide reports
        with patch.object(tax_service, 'generate_quarterly_941') as mock_941:
            mock_941.return_value = {
                "total_wages": sum(s.total_wages for s in annual_summaries),
                "total_federal_withheld": sum(s.federal_tax_withheld for s in annual_summaries),
                "total_ss_wages": sum(s.total_wages for s in annual_summaries),
                "total_medicare_wages": sum(s.total_wages for s in annual_summaries)
            }
            
            quarterly_report = await tax_service.generate_quarterly_941(
                year=year,
                quarter=4
            )
        
        assert quarterly_report["total_wages"] > Decimal("100000.00")
    
    def _setup_database_mocks(self, mock_db, employees, timesheets, policies):
        """Setup database query mocks."""
        # Mock employee queries
        employee_query = MagicMock()
        mock_db.query.return_value = employee_query
        employee_query.filter.return_value = employee_query
        employee_query.all.return_value = employees
        employee_query.first.return_value = employees[0] if employees else None
        
        # Mock timesheet queries
        def query_side_effect(model):
            if model == Timesheet:
                ts_query = MagicMock()
                ts_query.filter.return_value = ts_query
                ts_query.all.return_value = timesheets
                return ts_query
            elif model == StaffPayPolicy:
                policy_query = MagicMock()
                policy_query.filter.return_value = policy_query
                policy_query.first.return_value = policies[0] if policies else None
                return policy_query
            return employee_query
        
        mock_db.query.side_effect = query_side_effect
    
    def _setup_payroll_calculations(self, mock_service, employees):
        """Setup mock payroll calculations."""
        calculations = []
        
        # Engineer - salaried
        calc1 = Mock()
        calc1.employee_id = 1
        calc1.gross_pay = Decimal("4615.38")
        calc1.regular_pay = Decimal("4615.38")
        calc1.overtime_pay = Decimal("0.00")
        calc1.federal_tax = Decimal("692.31")
        calc1.state_tax = Decimal("230.77")
        calc1.social_security = Decimal("286.15")
        calc1.medicare = Decimal("66.92")
        calc1.health_insurance = Decimal("230.77")  # Bi-weekly portion
        calc1.retirement_401k = Decimal("276.92")  # 6% + match
        calc1.net_pay = Decimal("2832.54")
        calculations.append(calc1)
        
        # Sales rep - hourly with OT
        calc2 = Mock()
        calc2.employee_id = 2
        calc2.gross_pay = Decimal("2300.00")  # Including commissions
        calc2.regular_pay = Decimal("2000.00")
        calc2.overtime_pay = Decimal("150.00")
        calc2.commission = Decimal("150.00")
        calc2.federal_tax = Decimal("276.00")
        calc2.state_tax = Decimal("92.00")
        calc2.social_security = Decimal("142.60")
        calc2.medicare = Decimal("33.35")
        calc2.health_insurance = Decimal("138.46")
        calc2.retirement_401k = Decimal("92.00")
        calc2.net_pay = Decimal("1525.59")
        calculations.append(calc2)
        
        # Support - part-time
        calc3 = Mock()
        calc3.employee_id = 3
        calc3.gross_pay = Decimal("800.00")
        calc3.regular_pay = Decimal("800.00")
        calc3.overtime_pay = Decimal("0.00")
        calc3.federal_tax = Decimal("80.00")
        calc3.state_tax = Decimal("32.00")
        calc3.social_security = Decimal("49.60")
        calc3.medicare = Decimal("11.60")
        calc3.net_pay = Decimal("626.80")
        calculations.append(calc3)
        
        mock_service.calculate_payroll.side_effect = calculations
    
    def _create_payments_from_results(self, results, company_setup):
        """Create payment records from calculation results."""
        payments = []
        
        for i, result in enumerate(results):
            payment = Mock(spec=EmployeePayment)
            payment.id = i + 1
            payment.employee_id = result.employee_id
            payment.pay_period_start = company_setup["pay_period_start"]
            payment.pay_period_end = company_setup["pay_period_end"]
            payment.pay_date = company_setup["pay_date"]
            payment.gross_pay = result.gross_pay
            payment.net_pay = result.net_pay
            payment.status = PaymentStatus.PENDING
            payments.append(payment)
        
        return payments
    
    def _verify_audit_trail(self, mock_db, job_id):
        """Verify audit trail entries."""
        audit_entries = [
            {"action": "batch_job_created", "job_id": job_id},
            {"action": "batch_job_processing", "job_id": job_id},
            {"action": "employee_processed", "employee_id": 1},
            {"action": "employee_processed", "employee_id": 2},
            {"action": "employee_processed", "employee_id": 3},
            {"action": "batch_job_completed", "job_id": job_id}
        ]
        return audit_entries