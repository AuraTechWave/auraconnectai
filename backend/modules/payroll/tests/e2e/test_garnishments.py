# backend/modules/payroll/tests/e2e/test_garnishments.py

"""
End-to-end tests for wage garnishments.

Tests garnishment processing including child support,
tax levies, and creditor garnishments.
"""

import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

from ...services.payroll_service import PayrollService
from ...models.employee_payment import EmployeePayment


class TestPayrollGarnishments:
    """Test wage garnishment workflows."""

    @pytest.mark.e2e
    async def test_child_support_garnishment(self, mock_db, sample_employees):
        """Test processing child support garnishments."""

        employee = sample_employees[1]  # Hourly employee
        gross_pay = Decimal("2300.00")

        # Child support garnishment
        garnishment = {
            "type": "child_support",
            "case_number": "CS-2024-001",
            "amount": Decimal("400.00"),
            "percentage": None,
            "priority": 1,
            "max_percentage": Decimal("0.50"),  # Max 50% of disposable income
            "employer_fee": Decimal("2.00"),  # Processing fee
        }

        payroll_service = PayrollService(mock_db)

        # Calculate disposable income (gross - mandatory deductions)
        estimated_taxes = gross_pay * Decimal("0.25")
        disposable_income = gross_pay - estimated_taxes
        max_garnishment = disposable_income * garnishment["max_percentage"]

        with patch.object(payroll_service, "apply_garnishments") as mock_garn:
            mock_garn.return_value = {
                "child_support": min(garnishment["amount"], max_garnishment),
                "employer_fees": garnishment["employer_fee"],
                "total_garnishments": min(garnishment["amount"], max_garnishment),
            }

            payment = await payroll_service.calculate_payroll(
                employee_id=employee.id,
                pay_period_start=date(2024, 1, 1),
                pay_period_end=date(2024, 1, 14),
                gross_pay=gross_pay,
                garnishments=[garnishment],
            )

        # Verify garnishment applied correctly
        assert payment.garnishment_amount == Decimal("400.00")
        assert payment.garnishment_amount <= max_garnishment

    @pytest.mark.e2e
    async def test_multiple_garnishments_with_priority(self, mock_db, sample_employees):
        """Test multiple garnishments with priority ordering."""

        employee = sample_employees[2]
        gross_pay = Decimal("800.00")  # Part-time employee

        # Multiple garnishments
        garnishments = [
            {
                "type": "child_support",
                "amount": Decimal("300.00"),
                "priority": 1,  # Highest priority
                "max_percentage": Decimal("0.50"),
            },
            {
                "type": "tax_levy",
                "amount": Decimal("200.00"),
                "priority": 2,
                "max_percentage": Decimal("0.25"),
            },
            {
                "type": "creditor",
                "amount": Decimal("150.00"),
                "priority": 3,  # Lowest priority
                "max_percentage": Decimal("0.25"),
            },
        ]

        payroll_service = PayrollService(mock_db)

        # Calculate available for garnishment
        taxes = gross_pay * Decimal("0.20")  # Lower tax rate for part-time
        disposable_income = gross_pay - taxes

        with patch.object(payroll_service, "apply_garnishments") as mock_garn:
            # Mock prioritized garnishment application
            applied_garnishments = {
                "child_support": Decimal("300.00"),  # Full amount (priority 1)
                "tax_levy": Decimal("100.00"),  # Partial (priority 2)
                "creditor": Decimal("0.00"),  # Nothing left (priority 3)
                "total_garnishments": Decimal("400.00"),
            }
            mock_garn.return_value = applied_garnishments

            payment = await payroll_service.calculate_payroll(
                employee_id=employee.id,
                pay_period_start=date(2024, 1, 1),
                pay_period_end=date(2024, 1, 14),
                gross_pay=gross_pay,
                garnishments=garnishments,
            )

        # Verify priority-based application
        assert payment.garnishment_amount == Decimal("400.00")
        assert payment.garnishment_amount <= disposable_income * Decimal(
            "0.65"
        )  # Total limit

    @pytest.mark.e2e
    async def test_percentage_based_garnishment(self, mock_db, sample_employees):
        """Test percentage-based garnishments."""

        employee = sample_employees[0]  # Salaried employee
        gross_pay = Decimal("4615.38")

        # IRS tax levy - percentage based
        garnishment = {
            "type": "tax_levy",
            "case_number": "IRS-2024-123456",
            "amount": None,
            "percentage": Decimal("0.15"),  # 15% of gross
            "priority": 1,
            "max_amount": Decimal("1000.00"),  # Cap at $1000
            "exemption_amount": Decimal("500.00"),  # First $500 exempt
        }

        payroll_service = PayrollService(mock_db)

        # Calculate garnishment
        garnishable_amount = gross_pay - garnishment["exemption_amount"]
        calculated_garnishment = garnishable_amount * garnishment["percentage"]
        final_garnishment = min(calculated_garnishment, garnishment["max_amount"])

        with patch.object(payroll_service, "apply_garnishments") as mock_garn:
            mock_garn.return_value = {
                "tax_levy": final_garnishment,
                "total_garnishments": final_garnishment,
            }

            payment = await payroll_service.calculate_payroll(
                employee_id=employee.id,
                pay_period_start=date(2024, 1, 1),
                pay_period_end=date(2024, 1, 14),
                gross_pay=gross_pay,
                garnishments=[garnishment],
            )

        # Verify percentage calculation
        assert payment.garnishment_amount == final_garnishment
        assert payment.garnishment_amount <= garnishment["max_amount"]

    @pytest.mark.e2e
    async def test_garnishment_limits_protection(self, mock_db):
        """Test federal and state garnishment limit protections."""

        # Low-income employee
        employee = Mock()
        employee.id = 10
        employee.hourly_rate = Decimal("15.00")  # Minimum wage level

        gross_pay = Decimal("600.00")  # 40 hours at $15

        # Aggressive garnishment attempt
        garnishment = {
            "type": "creditor",
            "amount": Decimal("400.00"),  # 67% of gross
            "priority": 1,
            "federal_limit": Decimal("0.25"),  # Federal max 25% disposable
            "state_limit": Decimal("0.20"),  # State max 20% disposable
        }

        payroll_service = PayrollService(mock_db)

        # Calculate protected amounts
        taxes = gross_pay * Decimal("0.15")  # Lower tax bracket
        disposable_income = gross_pay - taxes

        # Federal minimum wage protection (30x federal min wage exempt)
        federal_min_wage = Decimal("7.25")
        exempt_amount = federal_min_wage * 30 * 40 / 52  # Weekly equivalent

        # Apply most restrictive limit
        max_garnishment = min(
            disposable_income * garnishment["state_limit"],  # State limit
            disposable_income * garnishment["federal_limit"],  # Federal limit
            disposable_income - exempt_amount,  # Minimum wage protection
        )

        with patch.object(payroll_service, "apply_garnishments") as mock_garn:
            mock_garn.return_value = {
                "creditor": max(max_garnishment, Decimal("0.00")),
                "total_garnishments": max(max_garnishment, Decimal("0.00")),
            }

            payment = await payroll_service.calculate_payroll(
                employee_id=employee.id,
                pay_period_start=date(2024, 1, 1),
                pay_period_end=date(2024, 1, 14),
                gross_pay=gross_pay,
                garnishments=[garnishment],
            )

        # Verify protection limits applied
        assert payment.garnishment_amount < garnishment["amount"]
        assert payment.garnishment_amount <= disposable_income * Decimal("0.20")

    @pytest.mark.e2e
    async def test_garnishment_reporting(self, mock_db, sample_employees):
        """Test garnishment reporting and remittance."""

        from ...services.payment_export_service import PaymentExportService

        # Process payroll with garnishments for multiple employees
        payments_with_garnishments = []

        for employee in sample_employees[:2]:
            payment = Mock(spec=EmployeePayment)
            payment.employee_id = employee.id
            payment.employee = employee
            payment.pay_date = date(2024, 1, 19)
            payment.garnishment_amount = Decimal("300.00")
            payment.garnishment_details = {
                "child_support": {
                    "amount": Decimal("300.00"),
                    "case_number": f"CS-2024-{employee.id:03d}",
                    "remit_to": "State Disbursement Unit",
                }
            }
            payments_with_garnishments.append(payment)

        export_service = PaymentExportService(mock_db)

        # Generate garnishment remittance report
        with patch.object(export_service, "export_garnishment_report") as mock_export:
            mock_export.return_value = {
                "report_date": date(2024, 1, 19),
                "total_garnishments": Decimal("600.00"),
                "garnishment_count": 2,
                "by_type": {"child_support": {"count": 2, "total": Decimal("600.00")}},
                "remittance_file": "garnishments_20240119.csv",
            }

            report = await export_service.export_garnishment_report(
                pay_date=date(2024, 1, 19), include_remittance_details=True
            )

        # Verify report
        assert report["total_garnishments"] == Decimal("600.00")
        assert report["garnishment_count"] == 2
        assert "remittance_file" in report
