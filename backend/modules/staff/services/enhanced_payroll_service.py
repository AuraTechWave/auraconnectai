"""
Enhanced Payroll Service for Phase 3 - High-level payroll operations.

This service orchestrates the enhanced payroll engine and integrates with
existing payroll models and payment processing.
"""

from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from datetime import datetime, date
from decimal import Decimal

from .enhanced_payroll_engine import EnhancedPayrollEngine
from ..models.payroll_models import Payroll
from ..schemas.payroll_schemas import PayrollResponse, PayrollBreakdown
from ...payroll.models.payroll_models import EmployeePayment


class EnhancedPayrollService:
    """
    Enhanced payroll service that provides high-level payroll operations
    integrating with tax services and comprehensive calculation engine.
    """

    def __init__(self, db: Session):
        self.db = db
        self.engine = EnhancedPayrollEngine(db)

    async def process_payroll_for_staff(
        self,
        staff_id: int,
        pay_period_start: date,
        pay_period_end: date,
        tenant_id: Optional[int] = None,
    ) -> PayrollResponse:
        """
        Process comprehensive payroll for a single staff member.

        Args:
            staff_id: Staff member ID
            pay_period_start: Pay period start date
            pay_period_end: Pay period end date
            tenant_id: Tenant ID for multi-tenant support

        Returns:
            PayrollResponse with comprehensive payroll details
        """
        # Calculate comprehensive payroll
        payroll_calc = await self.engine.compute_comprehensive_payroll(
            staff_id=staff_id,
            pay_period_start=pay_period_start,
            pay_period_end=pay_period_end,
            tenant_id=tenant_id,
        )

        # Create or update Payroll record
        period_str = f"{pay_period_start.strftime('%Y-%m')}"
        payroll_record = await self._create_or_update_payroll_record(
            staff_id=staff_id, period=period_str, payroll_calc=payroll_calc
        )

        # Create EmployeePayment record for tax tracking
        employee_payment = await self.engine.create_employee_payment_record(
            payroll_calculation=payroll_calc, tenant_id=tenant_id
        )

        # Create detailed breakdown for response
        breakdown = self._create_payroll_breakdown(payroll_calc)

        return PayrollResponse(
            staff_id=staff_id,
            period=period_str,
            gross_pay=float(payroll_calc["gross_pay"]),
            deductions=float(payroll_calc["total_deductions"]),
            net_pay=float(payroll_calc["net_pay"]),
            breakdown=breakdown,
            created_at=payroll_record.created_at,
        )

    async def process_payroll_batch(
        self,
        staff_ids: List[int],
        pay_period_start: date,
        pay_period_end: date,
        tenant_id: Optional[int] = None,
    ) -> List[PayrollResponse]:
        """
        Process payroll for multiple staff members in batch.

        Args:
            staff_ids: List of staff member IDs
            pay_period_start: Pay period start date
            pay_period_end: Pay period end date
            tenant_id: Tenant ID for multi-tenant support

        Returns:
            List of PayrollResponse objects
        """
        results = []
        errors = []

        for staff_id in staff_ids:
            try:
                payroll_response = await self.process_payroll_for_staff(
                    staff_id=staff_id,
                    pay_period_start=pay_period_start,
                    pay_period_end=pay_period_end,
                    tenant_id=tenant_id,
                )
                results.append(payroll_response)
            except Exception as e:
                errors.append({"staff_id": staff_id, "error": str(e)})

        # Log errors if any occurred
        if errors:
            print(f"Payroll batch processing errors: {errors}")

        return results

    async def get_payroll_summary(
        self,
        pay_period_start: date,
        pay_period_end: date,
        tenant_id: Optional[int] = None,
    ) -> Dict:
        """
        Get payroll summary for a pay period across all staff.

        Args:
            pay_period_start: Pay period start date
            pay_period_end: Pay period end date
            tenant_id: Tenant ID for multi-tenant support

        Returns:
            Dictionary with payroll summary information
        """
        # Get all EmployeePayment records for the period
        query = self.db.query(EmployeePayment).filter(
            EmployeePayment.pay_period_start >= pay_period_start,
            EmployeePayment.pay_period_end <= pay_period_end,
        )

        if tenant_id:
            query = query.filter(EmployeePayment.tenant_id == tenant_id)

        payments = query.all()

        if not payments:
            return {
                "total_employees": 0,
                "total_gross_pay": Decimal("0.00"),
                "total_net_pay": Decimal("0.00"),
                "total_deductions": Decimal("0.00"),
                "total_tax_deductions": Decimal("0.00"),
                "total_benefit_deductions": Decimal("0.00"),
                "average_hours_per_employee": Decimal("0.00"),
            }

        # Calculate summary statistics
        total_employees = len(payments)
        total_gross_pay = sum(p.gross_amount for p in payments)
        total_net_pay = sum(p.net_amount for p in payments)
        total_deductions = total_gross_pay - total_net_pay

        total_tax_deductions = sum(
            (p.federal_tax_amount or Decimal("0"))
            + (p.state_tax_amount or Decimal("0"))
            + (p.local_tax_amount or Decimal("0"))
            + (p.social_security_amount or Decimal("0"))
            + (p.medicare_amount or Decimal("0"))
            for p in payments
        )

        total_benefit_deductions = sum(
            (p.health_insurance_amount or Decimal("0"))
            + (p.retirement_amount or Decimal("0"))
            + (p.other_deductions_amount or Decimal("0"))
            for p in payments
        )

        total_hours = sum(
            (p.regular_hours or Decimal("0")) + (p.overtime_hours or Decimal("0"))
            for p in payments
        )
        average_hours = (
            total_hours / total_employees if total_employees > 0 else Decimal("0")
        )

        return {
            "total_employees": total_employees,
            "total_gross_pay": total_gross_pay,
            "total_net_pay": total_net_pay,
            "total_deductions": total_deductions,
            "total_tax_deductions": total_tax_deductions,
            "total_benefit_deductions": total_benefit_deductions,
            "average_hours_per_employee": average_hours.quantize(Decimal("0.01")),
            "pay_period_start": pay_period_start,
            "pay_period_end": pay_period_end,
        }

    async def _create_or_update_payroll_record(
        self, staff_id: int, period: str, payroll_calc: Dict
    ) -> Payroll:
        """
        Create or update a Payroll record with calculation results.

        Args:
            staff_id: Staff member ID
            period: Pay period string
            payroll_calc: Payroll calculation results

        Returns:
            Created or updated Payroll record
        """
        existing_payroll = (
            self.db.query(Payroll)
            .filter(Payroll.staff_id == staff_id, Payroll.period == period)
            .first()
        )

        gross_pay = float(payroll_calc["gross_pay"])
        total_deductions = float(payroll_calc["total_deductions"])
        net_pay = float(payroll_calc["net_pay"])

        if existing_payroll:
            existing_payroll.gross_pay = gross_pay
            existing_payroll.deductions = total_deductions
            existing_payroll.net_pay = net_pay
            existing_payroll.updated_at = datetime.utcnow()
            self.db.commit()
            return existing_payroll
        else:
            payroll = Payroll(
                staff_id=staff_id,
                period=period,
                gross_pay=gross_pay,
                deductions=total_deductions,
                net_pay=net_pay,
            )
            self.db.add(payroll)
            self.db.commit()
            self.db.refresh(payroll)
            return payroll

    def _create_payroll_breakdown(self, payroll_calc: Dict) -> PayrollBreakdown:
        """
        Create PayrollBreakdown from comprehensive payroll calculation.

        Args:
            payroll_calc: Payroll calculation results

        Returns:
            PayrollBreakdown object
        """
        hours = payroll_calc["hours_breakdown"]
        earnings = payroll_calc["earnings_breakdown"]
        deductions = payroll_calc["deductions_breakdown"]
        policy = payroll_calc["policy"]

        return PayrollBreakdown(
            hours_worked=float(hours.regular_hours),
            hourly_rate=float(policy.base_hourly_rate),
            overtime_hours=float(hours.overtime_hours),
            overtime_rate=float(policy.base_hourly_rate * policy.overtime_multiplier),
            gross_earnings=float(earnings.gross_pay),
            tax_deductions=float(deductions.total_tax_deductions),
            other_deductions=float(
                deductions.total_benefit_deductions + deductions.total_other_deductions
            ),
            total_deductions=float(deductions.total_deductions),
        )

    async def get_employee_payment_history(
        self, staff_id: int, limit: int = 10, tenant_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Get payment history for a staff member.

        Args:
            staff_id: Staff member ID
            limit: Maximum number of records to return
            tenant_id: Tenant ID for multi-tenant support

        Returns:
            List of payment history dictionaries
        """
        query = (
            self.db.query(EmployeePayment)
            .filter(EmployeePayment.employee_id == staff_id)
            .order_by(EmployeePayment.pay_period_end.desc())
        )

        if tenant_id:
            query = query.filter(EmployeePayment.tenant_id == tenant_id)

        payments = query.limit(limit).all()

        return [
            {
                "id": payment.id,
                "pay_period_start": payment.pay_period_start,
                "pay_period_end": payment.pay_period_end,
                "gross_amount": payment.gross_amount,
                "net_amount": payment.net_amount,
                "regular_hours": payment.regular_hours,
                "overtime_hours": payment.overtime_hours,
                "processed_at": payment.processed_at,
            }
            for payment in payments
        ]

    async def recalculate_payroll(
        self,
        staff_id: int,
        pay_period_start: date,
        pay_period_end: date,
        tenant_id: Optional[int] = None,
    ) -> PayrollResponse:
        """
        Recalculate payroll for a staff member and period.
        Useful when attendance records are updated or policies change.

        Args:
            staff_id: Staff member ID
            pay_period_start: Pay period start date
            pay_period_end: Pay period end date
            tenant_id: Tenant ID for multi-tenant support

        Returns:
            Updated PayrollResponse
        """
        # Delete existing EmployeePayment record if it exists
        existing_payment = (
            self.db.query(EmployeePayment)
            .filter(
                EmployeePayment.employee_id == staff_id,
                EmployeePayment.pay_period_start == pay_period_start,
                EmployeePayment.pay_period_end == pay_period_end,
            )
            .first()
        )

        if existing_payment:
            self.db.delete(existing_payment)
            self.db.commit()

        # Recalculate payroll
        return await self.process_payroll_for_staff(
            staff_id=staff_id,
            pay_period_start=pay_period_start,
            pay_period_end=pay_period_end,
            tenant_id=tenant_id,
        )
