# backend/modules/payroll/tests/e2e/conftest.py

"""
Shared fixtures for e2e tests.
"""

import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, MagicMock

from ...models.payroll_configuration import StaffPayPolicy
from ....staff.models.staff import Staff
from ....staff.models.timesheet import Timesheet


@pytest.fixture
def mock_db():
    """Create mock database session."""
    db = MagicMock()
    db.commit = Mock()
    db.add = Mock()
    db.refresh = Mock()
    db.flush = Mock()
    return db


@pytest.fixture
def sample_company_setup():
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
def sample_employees():
    """Create diverse set of test employees."""
    return create_sample_employees()


@pytest.fixture
def sample_timesheets(sample_employees, sample_company_setup):
    """Create timesheets for the pay period."""
    return create_sample_timesheets(sample_employees, sample_company_setup)


@pytest.fixture
def sample_pay_policies(sample_employees):
    """Create pay policies for employees."""
    return create_sample_pay_policies(sample_employees)


def create_sample_employees():
    """Create standard set of test employees."""
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


def create_sample_timesheets(employees, company_setup):
    """Create standard timesheet data."""
    timesheets = []
    start_date = company_setup["pay_period_start"]
    
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


def create_sample_pay_policies(employees):
    """Create standard pay policies."""
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