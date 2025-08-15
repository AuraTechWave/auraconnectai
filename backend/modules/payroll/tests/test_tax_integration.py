# backend/modules/payroll/tests/test_tax_integration.py

"""
Integration tests for tax calculations.

Tests the integration between payroll and tax modules,
ensuring accurate tax calculations across different scenarios.
"""

import pytest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from ..services.payroll_tax_service import PayrollTaxService
from ..services.payroll_tax_engine import PayrollTaxEngine
from ..models.payroll_configuration import TaxBreakdownApproximation
from ....tax.models.tax_models import TaxBracket, TaxRate, TaxExemption, TaxFilingStatus
from ....staff.models.staff import Staff


class TestTaxIntegration:
    """Test tax calculation integration."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def tax_service(self, mock_db):
        """Create tax service instance."""
        return PayrollTaxService(mock_db)

    @pytest.fixture
    def tax_engine(self, mock_db):
        """Create tax engine instance."""
        return PayrollTaxEngine(mock_db)

    @pytest.fixture
    def sample_employee(self):
        """Create sample employee with tax details."""
        employee = Mock(spec=Staff)
        employee.id = 1
        employee.full_name = "John Doe"
        employee.location = "california"
        employee.filing_status = "single"
        employee.federal_allowances = 2
        employee.state_allowances = 1
        employee.additional_federal_withholding = Decimal("50.00")
        employee.additional_state_withholding = Decimal("0.00")
        employee.is_exempt_federal = False
        employee.is_exempt_state = False
        employee.is_exempt_fica = False
        return employee

    @pytest.fixture
    def federal_tax_brackets(self):
        """Create federal tax brackets for 2024."""
        brackets = [
            Mock(
                min_income=Decimal("0"),
                max_income=Decimal("11000"),
                tax_rate=Decimal("0.10"),
                filing_status="single",
            ),
            Mock(
                min_income=Decimal("11000"),
                max_income=Decimal("44725"),
                tax_rate=Decimal("0.12"),
                filing_status="single",
            ),
            Mock(
                min_income=Decimal("44725"),
                max_income=Decimal("95375"),
                tax_rate=Decimal("0.22"),
                filing_status="single",
            ),
            Mock(
                min_income=Decimal("95375"),
                max_income=Decimal("182050"),
                tax_rate=Decimal("0.24"),
                filing_status="single",
            ),
        ]
        return brackets

    @pytest.fixture
    def state_tax_brackets(self):
        """Create California state tax brackets."""
        brackets = [
            Mock(
                min_income=Decimal("0"),
                max_income=Decimal("10412"),
                tax_rate=Decimal("0.01"),
                filing_status="single",
            ),
            Mock(
                min_income=Decimal("10412"),
                max_income=Decimal("24684"),
                tax_rate=Decimal("0.02"),
                filing_status="single",
            ),
            Mock(
                min_income=Decimal("24684"),
                max_income=Decimal("38959"),
                tax_rate=Decimal("0.04"),
                filing_status="single",
            ),
            Mock(
                min_income=Decimal("38959"),
                max_income=Decimal("54081"),
                tax_rate=Decimal("0.06"),
                filing_status="single",
            ),
        ]
        return brackets

    @pytest.mark.asyncio
    async def test_calculate_federal_tax_single_filer(
        self, tax_engine, mock_db, sample_employee, federal_tax_brackets
    ):
        """Test federal tax calculation for single filer."""
        # Setup
        gross_pay = Decimal("2500.00")  # Bi-weekly
        annual_income = gross_pay * 26  # $65,000 annual

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = federal_tax_brackets

        # Standard deduction for 2024
        mock_query.first.return_value = Mock(
            standard_deduction=Decimal("13850.00"),
            personal_exemption=Decimal("0.00"),  # No personal exemption after TCJA
        )

        # Execute
        federal_tax = await tax_engine.calculate_federal_tax(
            gross_pay=gross_pay,
            employee=sample_employee,
            pay_frequency="biweekly",
            ytd_income=Decimal("0.00"),
        )

        # Verify
        # Expected calculation:
        # Annual income: $65,000
        # Less standard deduction: $13,850
        # Taxable income: $51,150
        # Tax: 10% on first $11,000 + 12% on next $33,725 + 22% on remaining $6,425
        # Annual tax: $1,100 + $4,047 + $1,413.50 = $6,560.50
        # Bi-weekly: $6,560.50 / 26 = $252.33
        # Plus additional withholding: $50.00
        # Total: ~$302.33

        assert federal_tax > Decimal("300.00")
        assert federal_tax < Decimal("305.00")

    @pytest.mark.asyncio
    async def test_calculate_state_tax_california(
        self, tax_engine, mock_db, sample_employee, state_tax_brackets
    ):
        """Test California state tax calculation."""
        # Setup
        gross_pay = Decimal("2500.00")  # Bi-weekly

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = state_tax_brackets

        # California standard deduction
        mock_query.first.return_value = Mock(
            standard_deduction=Decimal("5363.00"), personal_exemption=Decimal("154.00")
        )

        # Execute
        state_tax = await tax_engine.calculate_state_tax(
            gross_pay=gross_pay,
            employee=sample_employee,
            state="california",
            pay_frequency="biweekly",
        )

        # Verify
        # California has lower rates than federal
        assert state_tax > Decimal("50.00")
        assert state_tax < Decimal("150.00")

    @pytest.mark.asyncio
    async def test_calculate_fica_taxes(self, tax_engine, sample_employee):
        """Test FICA tax calculations (Social Security and Medicare)."""
        # Setup
        gross_pay = Decimal("2500.00")
        ytd_income = Decimal("50000.00")

        # Execute
        fica_taxes = await tax_engine.calculate_fica_taxes(
            gross_pay=gross_pay, ytd_income=ytd_income, employee=sample_employee
        )

        # Verify
        # Social Security: 6.2% of gross (up to wage base)
        expected_ss = gross_pay * Decimal("0.062")
        assert fica_taxes["social_security"] == expected_ss

        # Medicare: 1.45% of gross
        expected_medicare = gross_pay * Decimal("0.0145")
        assert fica_taxes["medicare"] == expected_medicare

        # No additional Medicare tax yet (threshold is $200k)
        assert fica_taxes["additional_medicare"] == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_calculate_fica_with_wage_base_limit(
        self, tax_engine, sample_employee
    ):
        """Test FICA with Social Security wage base limit."""
        # Setup - near wage base limit
        gross_pay = Decimal("5000.00")
        ytd_income = Decimal("165000.00")  # Near 2024 limit of $168,600

        # Execute
        fica_taxes = await tax_engine.calculate_fica_taxes(
            gross_pay=gross_pay, ytd_income=ytd_income, employee=sample_employee
        )

        # Verify
        # Only $3,600 subject to Social Security
        remaining_wage_base = Decimal("168600.00") - ytd_income
        expected_ss = remaining_wage_base * Decimal("0.062")
        assert fica_taxes["social_security"] == expected_ss

        # Full Medicare applies
        assert fica_taxes["medicare"] == gross_pay * Decimal("0.0145")

    @pytest.mark.asyncio
    async def test_calculate_additional_medicare_tax(self, tax_engine, sample_employee):
        """Test additional Medicare tax for high earners."""
        # Setup - high income
        gross_pay = Decimal("10000.00")
        ytd_income = Decimal("195000.00")  # Will exceed $200k threshold

        # Execute
        fica_taxes = await tax_engine.calculate_fica_taxes(
            gross_pay=gross_pay, ytd_income=ytd_income, employee=sample_employee
        )

        # Verify
        # Regular Medicare: 1.45%
        assert fica_taxes["medicare"] == gross_pay * Decimal("0.0145")

        # Additional Medicare: 0.9% on amount over $200k
        new_total = ytd_income + gross_pay  # $205,000
        excess = new_total - Decimal("200000.00")  # $5,000
        expected_additional = excess * Decimal("0.009")
        assert fica_taxes["additional_medicare"] == expected_additional

    @pytest.mark.asyncio
    async def test_calculate_local_taxes(self, tax_engine, mock_db):
        """Test local tax calculations."""
        # Setup
        gross_pay = Decimal("2500.00")

        # Mock local tax rates
        local_rates = [
            Mock(
                jurisdiction="new_york_city",
                tax_type="income",
                rate=Decimal("0.03078"),  # NYC resident rate
                is_percentage=True,
            )
        ]

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = local_rates

        # Execute
        local_tax = await tax_engine.calculate_local_taxes(
            gross_pay=gross_pay, location="new_york_city"
        )

        # Verify
        expected_tax = gross_pay * Decimal("0.03078")
        assert abs(local_tax - expected_tax) < Decimal("0.01")

    @pytest.mark.asyncio
    async def test_tax_calculation_with_exemptions(
        self, tax_service, mock_db, sample_employee
    ):
        """Test tax calculation with various exemptions."""
        # Setup
        sample_employee.is_exempt_federal = True
        sample_employee.is_exempt_fica = True

        gross_pay = Decimal("2500.00")

        # Execute
        tax_breakdown = await tax_service.calculate_all_taxes(
            gross_pay=gross_pay, employee=sample_employee, pay_frequency="biweekly"
        )

        # Verify
        assert tax_breakdown["federal_tax"] == Decimal("0.00")
        assert tax_breakdown["social_security"] == Decimal("0.00")
        assert tax_breakdown["medicare"] == Decimal("0.00")
        # State tax still applies unless specifically exempt
        assert tax_breakdown["state_tax"] > Decimal("0.00")

    @pytest.mark.asyncio
    async def test_tax_calculation_married_filing_jointly(
        self, tax_engine, mock_db, federal_tax_brackets
    ):
        """Test tax calculation for married filing jointly."""
        # Setup
        employee = Mock()
        employee.filing_status = "married_jointly"
        employee.federal_allowances = 4
        employee.additional_federal_withholding = Decimal("0.00")

        gross_pay = Decimal("3500.00")

        # Mock married brackets (higher thresholds)
        married_brackets = [
            Mock(
                min_income=Decimal("0"),
                max_income=Decimal("22000"),
                tax_rate=Decimal("0.10"),
                filing_status="married_jointly",
            ),
            Mock(
                min_income=Decimal("22000"),
                max_income=Decimal("89450"),
                tax_rate=Decimal("0.12"),
                filing_status="married_jointly",
            ),
        ]

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = married_brackets

        # Married standard deduction
        mock_query.first.return_value = Mock(
            standard_deduction=Decimal("27700.00"), personal_exemption=Decimal("0.00")
        )

        # Execute
        federal_tax = await tax_engine.calculate_federal_tax(
            gross_pay=gross_pay, employee=employee, pay_frequency="biweekly"
        )

        # Verify - should be less than single filer
        assert federal_tax < Decimal("400.00")

    @pytest.mark.asyncio
    async def test_quarterly_tax_summary(self, tax_service, mock_db):
        """Test quarterly tax summary calculation."""
        # Setup
        employee_id = 1
        year = 2024
        quarter = 1

        # Mock payment records
        payments = []
        for i in range(6):  # 6 bi-weekly payments in Q1
            payment = Mock()
            payment.pay_date = date(2024, 1, 15) + (i * 14)
            payment.gross_pay = Decimal("2500.00")
            payment.federal_tax = Decimal("300.00")
            payment.state_tax = Decimal("100.00")
            payment.social_security = Decimal("155.00")
            payment.medicare = Decimal("36.25")
            payments.append(payment)

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = payments

        # Execute
        summary = await tax_service.get_quarterly_tax_summary(
            employee_id=employee_id, year=year, quarter=quarter
        )

        # Verify
        assert summary["total_gross"] == Decimal("15000.00")
        assert summary["total_federal"] == Decimal("1800.00")
        assert summary["total_state"] == Decimal("600.00")
        assert summary["total_fica"] == Decimal("1147.50")

    @pytest.mark.asyncio
    async def test_year_end_tax_forms(self, tax_service, mock_db):
        """Test year-end tax form generation (W-2)."""
        # Setup
        employee_id = 1
        year = 2023

        # Mock annual totals
        annual_summary = Mock()
        annual_summary.total_wages = Decimal("65000.00")
        annual_summary.federal_tax_withheld = Decimal("7800.00")
        annual_summary.social_security_wages = Decimal("65000.00")
        annual_summary.social_security_withheld = Decimal("4030.00")
        annual_summary.medicare_wages = Decimal("65000.00")
        annual_summary.medicare_withheld = Decimal("942.50")
        annual_summary.state_wages = Decimal("65000.00")
        annual_summary.state_tax_withheld = Decimal("2600.00")

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = annual_summary

        # Execute
        w2_data = await tax_service.generate_w2_data(employee_id=employee_id, year=year)

        # Verify
        assert w2_data["box1_wages"] == Decimal("65000.00")
        assert w2_data["box2_federal_withheld"] == Decimal("7800.00")
        assert w2_data["box3_ss_wages"] == Decimal("65000.00")
        assert w2_data["box4_ss_withheld"] == Decimal("4030.00")
        assert w2_data["box5_medicare_wages"] == Decimal("65000.00")
        assert w2_data["box6_medicare_withheld"] == Decimal("942.50")

    @pytest.mark.asyncio
    async def test_tax_calculation_with_pretax_deductions(
        self, tax_service, mock_db, sample_employee
    ):
        """Test tax calculation with pre-tax deductions."""
        # Setup
        gross_pay = Decimal("3000.00")
        pretax_deductions = {
            "retirement_401k": Decimal("300.00"),  # 10% contribution
            "health_insurance": Decimal("150.00"),
            "fsa": Decimal("100.00"),
        }

        # Execute
        tax_breakdown = await tax_service.calculate_all_taxes(
            gross_pay=gross_pay,
            employee=sample_employee,
            pretax_deductions=pretax_deductions,
            pay_frequency="biweekly",
        )

        # Verify
        # Taxes calculated on reduced amount
        taxable_income = gross_pay - sum(pretax_deductions.values())
        assert tax_breakdown["taxable_income"] == taxable_income
        # Federal tax should be less due to reduced taxable income
        assert tax_breakdown["federal_tax"] < Decimal("300.00")

    @pytest.mark.asyncio
    async def test_multi_state_tax_calculation(
        self, tax_service, mock_db, sample_employee
    ):
        """Test tax calculation for employee working in multiple states."""
        # Setup
        sample_employee.work_states = {
            "california": Decimal("0.6"),  # 60% of time
            "nevada": Decimal("0.4"),  # 40% of time (no state tax)
        }

        gross_pay = Decimal("3000.00")

        # Execute
        tax_breakdown = await tax_service.calculate_multi_state_taxes(
            gross_pay=gross_pay,
            employee=sample_employee,
            work_allocation=sample_employee.work_states,
        )

        # Verify
        # Only CA portion taxed for state
        ca_taxable = gross_pay * Decimal("0.6")
        assert tax_breakdown["california_tax"] > Decimal("0.00")
        assert tax_breakdown["nevada_tax"] == Decimal("0.00")
        assert tax_breakdown["total_state_tax"] == tax_breakdown["california_tax"]
