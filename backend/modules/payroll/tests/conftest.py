# backend/modules/payroll/tests/conftest.py

"""
Pytest fixtures and factories for payroll module tests.

Provides reusable test data and mock objects for consistent testing.
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock
import random
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session

from ..models.employee_payment import EmployeePayment, PaymentStatus
from ..models.payroll_configuration import (
    PayrollConfiguration,
    StaffPayPolicy,
    OvertimeRule,
    TaxBreakdownApproximation,
    RoleBasedPayRate,
    PayrollJobTracking,
    PayrollConfigurationType
)
from ..enums.payroll_enums import PayrollJobStatus, PayFrequency
from ..schemas.batch_processing_schemas import (
    EmployeePayrollResult,
    PayrollBreakdown,
    CalculationOptions
)
from ....staff.models.staff import Staff
from ....staff.models.timesheet import Timesheet


# Database fixtures
@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock(spec=Session)
    session.add = Mock()
    session.commit = Mock()
    session.refresh = Mock()
    session.flush = Mock()
    session.rollback = Mock()
    session.close = Mock()
    
    # Setup query mock
    query = MagicMock()
    session.query = Mock(return_value=query)
    query.filter = Mock(return_value=query)
    query.filter_by = Mock(return_value=query)
    query.order_by = Mock(return_value=query)
    query.limit = Mock(return_value=query)
    query.offset = Mock(return_value=query)
    query.all = Mock(return_value=[])
    query.first = Mock(return_value=None)
    query.count = Mock(return_value=0)
    
    return session


# Employee factories
@pytest.fixture
def employee_factory():
    """Factory for creating test employees."""
    def create_employee(
        id: int = None,
        name: str = None,
        employee_code: str = None,
        department: str = "Engineering",
        location: str = "california",
        employment_type: str = "salaried",
        annual_salary: Optional[Decimal] = None,
        hourly_rate: Optional[Decimal] = None,
        filing_status: str = "single",
        federal_allowances: int = 2,
        **kwargs
    ) -> Mock:
        employee = Mock(spec=Staff)
        employee.id = id or random.randint(1000, 9999)
        employee.full_name = name or f"Test Employee {employee.id}"
        employee.employee_code = employee_code or f"EMP{str(employee.id).zfill(6)}"
        employee.department = department
        employee.location = location
        employee.employment_type = employment_type
        
        if employment_type == "salaried":
            employee.annual_salary = annual_salary or Decimal("75000.00")
            employee.hourly_rate = None
        else:
            employee.hourly_rate = hourly_rate or Decimal("35.00")
            employee.annual_salary = None
        
        employee.filing_status = filing_status
        employee.federal_allowances = federal_allowances
        employee.state_allowances = 1
        employee.is_active = kwargs.get('is_active', True)
        employee.hire_date = kwargs.get('hire_date', date(2020, 1, 1))
        employee.email = kwargs.get('email', f"employee{employee.id}@example.com")
        
        # Tax settings
        employee.is_exempt_federal = kwargs.get('is_exempt_federal', False)
        employee.is_exempt_state = kwargs.get('is_exempt_state', False)
        employee.is_exempt_fica = kwargs.get('is_exempt_fica', False)
        employee.additional_federal_withholding = kwargs.get('additional_federal_withholding', Decimal("0.00"))
        employee.additional_state_withholding = kwargs.get('additional_state_withholding', Decimal("0.00"))
        
        # Benefits
        employee.health_insurance_plan = kwargs.get('health_insurance_plan', "standard")
        employee.retirement_contribution_percentage = kwargs.get('retirement_contribution_percentage', Decimal("0.06"))
        
        # Set any additional attributes
        for key, value in kwargs.items():
            if not hasattr(employee, key):
                setattr(employee, key, value)
        
        return employee
    
    return create_employee


# Timesheet factories
@pytest.fixture
def timesheet_factory():
    """Factory for creating test timesheets."""
    def create_timesheet(
        staff_id: int,
        work_date: date,
        regular_hours: Decimal = Decimal("8.0"),
        overtime_hours: Decimal = Decimal("0.0"),
        is_approved: bool = True,
        **kwargs
    ) -> Mock:
        timesheet = Mock(spec=Timesheet)
        timesheet.id = kwargs.get('id', random.randint(10000, 99999))
        timesheet.staff_id = staff_id
        timesheet.work_date = work_date
        timesheet.regular_hours = regular_hours
        timesheet.overtime_hours = overtime_hours
        timesheet.total_hours = regular_hours + overtime_hours
        timesheet.is_approved = is_approved
        timesheet.approved_by = kwargs.get('approved_by', 1) if is_approved else None
        timesheet.approved_at = kwargs.get('approved_at', datetime.utcnow()) if is_approved else None
        timesheet.notes = kwargs.get('notes', None)
        
        return timesheet
    
    return create_timesheet


# Payment factories
@pytest.fixture
def payment_factory():
    """Factory for creating test payments."""
    def create_payment(
        employee_id: int,
        pay_period_start: date,
        pay_period_end: date,
        gross_pay: Decimal = Decimal("2500.00"),
        net_pay: Optional[Decimal] = None,
        status: PaymentStatus = PaymentStatus.PENDING,
        **kwargs
    ) -> Mock:
        payment = Mock(spec=EmployeePayment)
        payment.id = kwargs.get('id', random.randint(100000, 999999))
        payment.employee_id = employee_id
        payment.pay_period_start = pay_period_start
        payment.pay_period_end = pay_period_end
        payment.pay_date = kwargs.get('pay_date', pay_period_end + timedelta(days=5))
        
        # Pay amounts
        payment.regular_hours = kwargs.get('regular_hours', Decimal("80.0"))
        payment.overtime_hours = kwargs.get('overtime_hours', Decimal("0.0"))
        payment.regular_pay = kwargs.get('regular_pay', gross_pay * Decimal("0.9"))
        payment.overtime_pay = kwargs.get('overtime_pay', gross_pay * Decimal("0.1"))
        payment.gross_pay = gross_pay
        
        # Taxes
        payment.federal_tax = kwargs.get('federal_tax', gross_pay * Decimal("0.15"))
        payment.state_tax = kwargs.get('state_tax', gross_pay * Decimal("0.05"))
        payment.local_tax = kwargs.get('local_tax', Decimal("0.00"))
        payment.social_security = kwargs.get('social_security', gross_pay * Decimal("0.062"))
        payment.medicare = kwargs.get('medicare', gross_pay * Decimal("0.0145"))
        
        # Deductions
        payment.health_insurance = kwargs.get('health_insurance', Decimal("200.00"))
        payment.retirement_401k = kwargs.get('retirement_401k', gross_pay * Decimal("0.06"))
        payment.garnishment_amount = kwargs.get('garnishment_amount', Decimal("0.00"))
        
        # Calculate net pay if not provided
        if net_pay is None:
            total_deductions = (
                payment.federal_tax + payment.state_tax + payment.local_tax +
                payment.social_security + payment.medicare + payment.health_insurance +
                payment.retirement_401k + payment.garnishment_amount
            )
            payment.net_pay = gross_pay - total_deductions
        else:
            payment.net_pay = net_pay
        
        payment.status = status
        payment.created_at = kwargs.get('created_at', datetime.utcnow())
        payment.updated_at = kwargs.get('updated_at', datetime.utcnow())
        
        return payment
    
    return create_payment


# Configuration factories
@pytest.fixture
def pay_policy_factory():
    """Factory for creating staff pay policies."""
    def create_pay_policy(
        staff_id: int,
        base_hourly_rate: Decimal = Decimal("25.00"),
        effective_date: date = date.today(),
        **kwargs
    ) -> Mock:
        policy = Mock(spec=StaffPayPolicy)
        policy.id = kwargs.get('id', random.randint(1000, 9999))
        policy.staff_id = staff_id
        policy.base_hourly_rate = base_hourly_rate
        policy.overtime_eligible = kwargs.get('overtime_eligible', True)
        policy.overtime_multiplier = kwargs.get('overtime_multiplier', Decimal("1.5"))
        policy.double_time_multiplier = kwargs.get('double_time_multiplier', Decimal("2.0"))
        
        # Benefits
        policy.health_insurance_monthly = kwargs.get('health_insurance_monthly', Decimal("400.00"))
        policy.dental_insurance_monthly = kwargs.get('dental_insurance_monthly', Decimal("50.00"))
        policy.vision_insurance_monthly = kwargs.get('vision_insurance_monthly', Decimal("20.00"))
        policy.life_insurance_monthly = kwargs.get('life_insurance_monthly', Decimal("30.00"))
        policy.retirement_match_percentage = kwargs.get('retirement_match_percentage', Decimal("0.04"))
        
        # Proration
        policy.benefit_proration_factor = kwargs.get('benefit_proration_factor', Decimal("0.4615"))  # Bi-weekly
        
        policy.effective_date = effective_date
        policy.expiry_date = kwargs.get('expiry_date', None)
        policy.is_active = kwargs.get('is_active', True)
        
        return policy
    
    return create_pay_policy


@pytest.fixture
def overtime_rule_factory():
    """Factory for creating overtime rules."""
    def create_overtime_rule(
        jurisdiction: str = "california",
        daily_threshold: Decimal = Decimal("8.0"),
        weekly_threshold: Decimal = Decimal("40.0"),
        **kwargs
    ) -> Mock:
        rule = Mock(spec=OvertimeRule)
        rule.id = kwargs.get('id', random.randint(100, 999))
        rule.jurisdiction = jurisdiction
        rule.daily_threshold_hours = daily_threshold
        rule.daily_overtime_multiplier = kwargs.get('daily_overtime_multiplier', Decimal("1.5"))
        rule.weekly_threshold_hours = weekly_threshold
        rule.weekly_overtime_multiplier = kwargs.get('weekly_overtime_multiplier', Decimal("1.5"))
        rule.double_time_daily_threshold = kwargs.get('double_time_daily_threshold', Decimal("12.0"))
        rule.double_time_multiplier = kwargs.get('double_time_multiplier', Decimal("2.0"))
        rule.precedence = kwargs.get('precedence', 1)
        rule.is_active = kwargs.get('is_active', True)
        
        return rule
    
    return create_overtime_rule


# Batch processing fixtures
@pytest.fixture
def batch_job_factory():
    """Factory for creating batch processing jobs."""
    def create_batch_job(
        job_id: str = None,
        status: PayrollJobStatus = PayrollJobStatus.PENDING,
        total_employees: int = 100,
        **kwargs
    ) -> Mock:
        job = Mock(spec=PayrollJobTracking)
        job.id = kwargs.get('id', random.randint(1000, 9999))
        job.job_id = job_id or f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        job.job_type = kwargs.get('job_type', 'batch_payroll')
        job.status = status
        job.total_employees = total_employees
        job.processed_count = kwargs.get('processed_count', 0)
        job.success_count = kwargs.get('success_count', 0)
        job.failure_count = kwargs.get('failure_count', 0)
        job.created_at = kwargs.get('created_at', datetime.utcnow())
        job.started_at = kwargs.get('started_at', None)
        job.completed_at = kwargs.get('completed_at', None)
        job.created_by = kwargs.get('created_by', 1)
        job.parameters = kwargs.get('parameters', {})
        job.error_details = kwargs.get('error_details', [])
        job.result_summary = kwargs.get('result_summary', {})
        
        return job
    
    return create_batch_job


# Sample data fixtures
@pytest.fixture
def sample_pay_period():
    """Standard bi-weekly pay period."""
    return {
        "start": date(2024, 1, 1),
        "end": date(2024, 1, 14),
        "pay_date": date(2024, 1, 19)
    }


@pytest.fixture
def sample_calculation_options():
    """Standard calculation options."""
    return CalculationOptions(
        include_overtime=True,
        include_benefits=True,
        include_deductions=True,
        use_ytd_calculations=True,
        prorate_benefits=False
    )


@pytest.fixture
def sample_payroll_breakdown():
    """Sample payroll breakdown."""
    return PayrollBreakdown(
        regular_pay=Decimal("2000.00"),
        overtime_pay=Decimal("300.00"),
        gross_pay=Decimal("2300.00"),
        federal_tax=Decimal("345.00"),
        state_tax=Decimal("115.00"),
        local_tax=Decimal("0.00"),
        social_security=Decimal("142.60"),
        medicare=Decimal("33.35"),
        health_insurance=Decimal("200.00"),
        dental_insurance=Decimal("25.00"),
        vision_insurance=Decimal("10.00"),
        retirement_401k=Decimal("138.00"),
        retirement_match=Decimal("92.00"),
        total_deductions=Decimal("1008.95"),
        net_pay=Decimal("1291.05"),
        ytd_gross=Decimal("4600.00"),
        ytd_net=Decimal("2582.10"),
        ytd_federal_tax=Decimal("690.00"),
        ytd_state_tax=Decimal("230.00"),
        ytd_social_security=Decimal("285.20"),
        ytd_medicare=Decimal("66.70")
    )


# Tax configuration fixtures
@pytest.fixture
def tax_brackets_2024():
    """2024 federal tax brackets."""
    return {
        "single": [
            {"min": 0, "max": 11000, "rate": 0.10},
            {"min": 11000, "max": 44725, "rate": 0.12},
            {"min": 44725, "max": 95375, "rate": 0.22},
            {"min": 95375, "max": 182050, "rate": 0.24},
            {"min": 182050, "max": 231250, "rate": 0.32},
            {"min": 231250, "max": 578125, "rate": 0.35},
            {"min": 578125, "max": None, "rate": 0.37}
        ],
        "married_jointly": [
            {"min": 0, "max": 22000, "rate": 0.10},
            {"min": 22000, "max": 89450, "rate": 0.12},
            {"min": 89450, "max": 190750, "rate": 0.22},
            {"min": 190750, "max": 364100, "rate": 0.24},
            {"min": 364100, "max": 462500, "rate": 0.32},
            {"min": 462500, "max": 693750, "rate": 0.35},
            {"min": 693750, "max": None, "rate": 0.37}
        ]
    }


@pytest.fixture
def california_tax_brackets():
    """California state tax brackets."""
    return [
        {"min": 0, "max": 10412, "rate": 0.01},
        {"min": 10412, "max": 24684, "rate": 0.02},
        {"min": 24684, "max": 38959, "rate": 0.04},
        {"min": 38959, "max": 54081, "rate": 0.06},
        {"min": 54081, "max": 68350, "rate": 0.08},
        {"min": 68350, "max": 349137, "rate": 0.093},
        {"min": 349137, "max": 418961, "rate": 0.103},
        {"min": 418961, "max": 698271, "rate": 0.113},
        {"min": 698271, "max": None, "rate": 0.123}
    ]


# Utility fixtures
@pytest.fixture
def create_test_data(
    mock_db_session,
    employee_factory,
    timesheet_factory,
    pay_policy_factory,
    sample_pay_period
):
    """Create a complete set of test data."""
    def _create(num_employees: int = 5) -> Dict[str, Any]:
        employees = []
        timesheets = []
        pay_policies = []
        
        for i in range(num_employees):
            # Create employee
            emp_type = "salaried" if i % 2 == 0 else "hourly"
            employee = employee_factory(
                id=i + 1,
                name=f"Test Employee {i + 1}",
                employment_type=emp_type,
                department=random.choice(["Engineering", "Sales", "Support"]),
                location=random.choice(["california", "new_york", "texas"])
            )
            employees.append(employee)
            
            # Create pay policy
            policy = pay_policy_factory(
                staff_id=employee.id,
                base_hourly_rate=employee.hourly_rate or Decimal(str(employee.annual_salary / 2080))
            )
            pay_policies.append(policy)
            
            # Create timesheets for hourly employees
            if emp_type == "hourly":
                for day in range(10):  # 10 working days
                    work_date = sample_pay_period["start"] + timedelta(days=day)
                    if work_date.weekday() < 5:  # Weekday
                        ts = timesheet_factory(
                            staff_id=employee.id,
                            work_date=work_date,
                            regular_hours=Decimal("8.0"),
                            overtime_hours=Decimal("2.0") if day == 0 else Decimal("0.0")
                        )
                        timesheets.append(ts)
        
        return {
            "employees": employees,
            "timesheets": timesheets,
            "pay_policies": pay_policies,
            "pay_period": sample_pay_period
        }
    
    return _create