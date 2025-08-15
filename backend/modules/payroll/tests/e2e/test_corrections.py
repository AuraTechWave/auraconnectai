# backend/modules/payroll/tests/e2e/test_corrections.py

"""
End-to-end tests for payroll corrections and adjustments.

Tests correction workflows including payment adjustments,
retroactive changes, and error corrections.
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch

from ...services.payroll_service import PayrollService
from ...models.employee_payment import EmployeePayment
from ...enums.payroll_enums import PaymentStatus


class TestPayrollCorrections:
    """Test payroll correction workflows."""

    @pytest.mark.e2e
    async def test_payment_correction_workflow(self, mock_db, sample_employees):
        """Test correcting an incorrect payment."""

        # Create initial payment that needs correction
        original_payment = Mock(spec=EmployeePayment)
        original_payment.id = 100
        original_payment.employee_id = 1
        original_payment.gross_pay = Decimal("4500.00")  # Incorrect amount
        original_payment.net_pay = Decimal("3375.00")
        original_payment.status = PaymentStatus.PENDING

        # Calculate correction amount
        correct_gross = Decimal("4615.38")
        correction_amount = correct_gross - original_payment.gross_pay

        payroll_service = PayrollService(mock_db)

        with patch.object(payroll_service, "create_adjustment") as mock_adjustment:
            mock_adjustment.return_value = Mock(
                adjustment_amount=correction_amount,
                adjustment_type="correction",
                reason="Incorrect salary calculation",
            )

            # Process correction
            corrected_payment = await payroll_service.process_correction(
                original_payment_id=original_payment.id,
                correction_amount=correction_amount,
                reason="Incorrect salary calculation",
            )

        # Verify correction
        assert corrected_payment.gross_pay == correct_gross
        assert corrected_payment.adjustment_amount == correction_amount
        assert corrected_payment.parent_payment_id == original_payment.id

        # Verify original payment marked as corrected
        assert original_payment.status == PaymentStatus.CORRECTED
        assert original_payment.corrected_by_payment_id == corrected_payment.id

    @pytest.mark.e2e
    async def test_retroactive_pay_adjustment(self, mock_db, sample_employees):
        """Test retroactive pay rate changes."""

        employee = sample_employees[0]
        old_rate = Decimal("57.69")  # $120k annually
        new_rate = Decimal("62.50")  # $130k annually
        effective_date = date(2024, 1, 1)

        # Calculate retroactive pay for 2 previous pay periods
        periods_to_adjust = 2
        hours_per_period = Decimal("80.0")  # Standard bi-weekly
        retro_amount = (new_rate - old_rate) * hours_per_period * periods_to_adjust

        payroll_service = PayrollService(mock_db)

        with patch.object(payroll_service, "calculate_retroactive_pay") as mock_retro:
            mock_retro.return_value = {
                "retroactive_gross": retro_amount,
                "retroactive_taxes": retro_amount * Decimal("0.30"),
                "retroactive_net": retro_amount * Decimal("0.70"),
                "affected_periods": periods_to_adjust,
            }

            retro_payment = await payroll_service.process_retroactive_payment(
                employee_id=employee.id,
                old_rate=old_rate,
                new_rate=new_rate,
                effective_date=effective_date,
                current_date=date(2024, 2, 1),
            )

        # Verify retroactive payment
        assert retro_payment["retroactive_gross"] == retro_amount
        assert retro_payment["affected_periods"] == periods_to_adjust
        assert retro_payment["retroactive_net"] > Decimal("0.00")

    @pytest.mark.e2e
    async def test_overpayment_recovery(self, mock_db, sample_employees):
        """Test handling overpayment recovery."""

        employee = sample_employees[1]  # Hourly employee
        overpayment_amount = Decimal("500.00")

        # Create overpayment recovery plan
        recovery_plan = {
            "total_amount": overpayment_amount,
            "installments": 4,  # Recover over 4 pay periods
            "per_period_amount": overpayment_amount / 4,
        }

        payroll_service = PayrollService(mock_db)

        # Process current payroll with recovery deduction
        current_gross = Decimal("2300.00")
        recovery_amount = recovery_plan["per_period_amount"]

        with patch.object(
            payroll_service, "apply_overpayment_recovery"
        ) as mock_recovery:
            mock_recovery.return_value = {
                "gross_pay": current_gross,
                "recovery_deduction": recovery_amount,
                "adjusted_net_pay": current_gross
                - recovery_amount
                - Decimal("575.00"),  # After taxes
            }

            payment = await payroll_service.calculate_payroll(
                employee_id=employee.id,
                pay_period_start=date(2024, 2, 1),
                pay_period_end=date(2024, 2, 14),
                gross_pay=current_gross,
                recovery_plan=recovery_plan,
            )

        # Verify recovery applied
        assert payment.recovery_deduction == recovery_amount
        assert payment.net_pay < (
            current_gross - Decimal("575.00")
        )  # Less than normal net

    @pytest.mark.e2e
    async def test_bulk_correction_workflow(self, mock_db, sample_employees):
        """Test correcting multiple payments in bulk."""

        # Create multiple payments needing correction
        payments_to_correct = []
        for i in range(5):
            payment = Mock(spec=EmployeePayment)
            payment.id = 200 + i
            payment.employee_id = (i % 3) + 1
            payment.gross_pay = Decimal("2000.00")  # All have same incorrect amount
            payment.status = PaymentStatus.PENDING
            payments_to_correct.append(payment)

        payroll_service = PayrollService(mock_db)

        # Process bulk corrections
        corrections = []
        for payment in payments_to_correct:
            # Calculate correct amount based on employee
            if payment.employee_id == 1:
                correct_amount = Decimal("4615.38")
            elif payment.employee_id == 2:
                correct_amount = Decimal("2300.00")
            else:
                correct_amount = Decimal("800.00")

            correction_amount = correct_amount - payment.gross_pay

            with patch.object(payroll_service, "process_correction") as mock_correct:
                mock_correct.return_value = Mock(
                    gross_pay=correct_amount, adjustment_amount=correction_amount
                )

                corrected = await payroll_service.process_correction(
                    original_payment_id=payment.id,
                    correction_amount=correction_amount,
                    reason="Bulk correction - system error",
                )
                corrections.append(corrected)

        # Verify all corrections processed
        assert len(corrections) == 5
        assert all(c.adjustment_amount != Decimal("0.00") for c in corrections)

    @pytest.mark.e2e
    async def test_void_and_reissue_payment(self, mock_db):
        """Test voiding and reissuing a payment."""

        # Original payment to void
        original_payment = Mock(spec=EmployeePayment)
        original_payment.id = 300
        original_payment.employee_id = 1
        original_payment.gross_pay = Decimal("4615.38")
        original_payment.net_pay = Decimal("3461.54")
        original_payment.status = PaymentStatus.PROCESSED
        original_payment.check_number = "12345"

        payroll_service = PayrollService(mock_db)

        # Void original payment
        with patch.object(payroll_service, "void_payment") as mock_void:
            mock_void.return_value = Mock(
                status=PaymentStatus.VOIDED,
                void_date=datetime.utcnow(),
                void_reason="Check lost",
            )

            voided_payment = await payroll_service.void_payment(
                payment_id=original_payment.id,
                reason="Check lost",
                void_date=datetime.utcnow(),
            )

        # Reissue payment
        with patch.object(payroll_service, "reissue_payment") as mock_reissue:
            mock_reissue.return_value = Mock(
                id=301,
                gross_pay=original_payment.gross_pay,
                net_pay=original_payment.net_pay,
                status=PaymentStatus.PENDING,
                parent_payment_id=original_payment.id,
                reissue_reason="Check lost - reissued",
            )

            new_payment = await payroll_service.reissue_payment(
                original_payment_id=original_payment.id,
                reason="Check lost - reissued",
                new_check_number="12346",
            )

        # Verify void and reissue
        assert voided_payment.status == PaymentStatus.VOIDED
        assert new_payment.parent_payment_id == original_payment.id
        assert new_payment.gross_pay == original_payment.gross_pay
