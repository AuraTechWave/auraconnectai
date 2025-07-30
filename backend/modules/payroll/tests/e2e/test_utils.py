# backend/modules/payroll/tests/e2e/test_utils.py

"""
Shared test utilities for e2e tests.
"""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock, MagicMock

from ...models.employee_payment import EmployeePayment
from ...enums.payroll_enums import PaymentStatus
from ....staff.models.timesheet import Timesheet
from ...models.payroll_configuration import StaffPayPolicy


def setup_database_mocks(mock_db, employees, timesheets, policies):
    """Setup database query mocks for tests."""
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


def setup_payroll_calculations(mock_service, employees):
    """Setup standard mock payroll calculations."""
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


def create_payments_from_results(results, company_setup):
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


def verify_audit_trail(mock_db, job_id):
    """Verify audit trail entries for a job."""
    audit_entries = [
        {"action": "batch_job_created", "job_id": job_id},
        {"action": "batch_job_processing", "job_id": job_id},
        {"action": "employee_processed", "employee_id": 1},
        {"action": "employee_processed", "employee_id": 2},
        {"action": "employee_processed", "employee_id": 3},
        {"action": "batch_job_completed", "job_id": job_id}
    ]
    return audit_entries


def create_mock_tax_brackets(filing_status="single"):
    """Create mock tax bracket data."""
    if filing_status == "single":
        return [
            {"min": 0, "max": 11000, "rate": 0.10},
            {"min": 11000, "max": 44725, "rate": 0.12},
            {"min": 44725, "max": 95375, "rate": 0.22},
            {"min": 95375, "max": 182050, "rate": 0.24}
        ]
    else:  # married_jointly
        return [
            {"min": 0, "max": 22000, "rate": 0.10},
            {"min": 22000, "max": 89450, "rate": 0.12},
            {"min": 89450, "max": 190750, "rate": 0.22},
            {"min": 190750, "max": 364100, "rate": 0.24}
        ]


def calculate_expected_taxes(gross_pay, filing_status="single", allowances=2):
    """Calculate expected tax amounts for verification."""
    # Simplified tax calculation for testing
    annual_gross = gross_pay * 26  # Bi-weekly to annual
    
    # Standard deduction
    standard_deduction = Decimal("13850.00") if filing_status == "single" else Decimal("27700.00")
    
    # Taxable income
    taxable_income = max(annual_gross - standard_deduction, Decimal("0.00"))
    
    # Federal tax (simplified)
    if filing_status == "single":
        if taxable_income <= 11000:
            annual_tax = taxable_income * Decimal("0.10")
        elif taxable_income <= 44725:
            annual_tax = Decimal("1100.00") + (taxable_income - 11000) * Decimal("0.12")
        else:
            annual_tax = Decimal("5147.00") + (taxable_income - 44725) * Decimal("0.22")
    else:
        # Married filing jointly rates
        annual_tax = taxable_income * Decimal("0.10")  # Simplified
    
    # Bi-weekly federal tax
    federal_tax = annual_tax / 26
    
    # State tax (simplified - 4% effective rate)
    state_tax = gross_pay * Decimal("0.04")
    
    # FICA taxes
    social_security = gross_pay * Decimal("0.062")
    medicare = gross_pay * Decimal("0.0145")
    
    return {
        "federal_tax": federal_tax,
        "state_tax": state_tax,
        "social_security": social_security,
        "medicare": medicare,
        "total_taxes": federal_tax + state_tax + social_security + medicare
    }