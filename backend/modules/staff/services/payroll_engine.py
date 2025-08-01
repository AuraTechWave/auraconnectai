from sqlalchemy.orm import Session
from modules.staff.models.attendance_models import AttendanceLog
from modules.staff.models.staff_models import StaffMember
from modules.staff.schemas.payroll_schemas import PayrollBreakdown
from datetime import datetime
from typing import Tuple


class PayrollEngine:
    def __init__(self, db: Session):
        self.db = db

    async def calculate_hours_for_period(self, staff_id: int,
                                         period: str) -> Tuple[float, float]:
        year, month = period.split("-")
        start_date = datetime(int(year), int(month), 1)
        if int(month) == 12:
            end_date = datetime(int(year) + 1, 1, 1)
        else:
            end_date = datetime(int(year), int(month) + 1, 1)

        attendance_logs = self.db.query(AttendanceLog).filter(
            AttendanceLog.staff_id == staff_id,
            AttendanceLog.check_in >= start_date,
            AttendanceLog.check_in < end_date,
            AttendanceLog.check_out.isnot(None)
        ).all()

        total_hours = 0.0
        for log in attendance_logs:
            if log.check_out and log.check_in:
                hours = (log.check_out - log.check_in).total_seconds() / 3600
                total_hours += hours

        regular_hours = min(total_hours, 160.0)
        overtime_hours = max(0.0, total_hours - 160.0)

        return regular_hours, overtime_hours

    async def calculate_payroll(self, staff_id: int, period: str) -> dict:
        staff = self.db.query(StaffMember).filter(
            StaffMember.id == staff_id).first()
        if not staff:
            raise ValueError(f"Staff member with ID {staff_id} not found")

        regular_hours, overtime_hours = await self.calculate_hours_for_period(
            staff_id, period)

        hourly_rate = 15.0
        overtime_rate = hourly_rate * 1.5

        regular_pay = regular_hours * hourly_rate
        overtime_pay = overtime_hours * overtime_rate
        gross_pay = regular_pay + overtime_pay

        tax_rate = 0.20
        tax_deductions = gross_pay * tax_rate
        other_deductions = 0.0
        total_deductions = tax_deductions + other_deductions

        net_pay = gross_pay - total_deductions

        breakdown = PayrollBreakdown(
            hours_worked=regular_hours,
            hourly_rate=hourly_rate,
            overtime_hours=overtime_hours,
            overtime_rate=overtime_rate,
            gross_earnings=gross_pay,
            tax_deductions=tax_deductions,
            other_deductions=other_deductions,
            total_deductions=total_deductions
        )

        return {
            "staff_id": staff_id,
            "period": period,
            "gross_pay": gross_pay,
            "deductions": total_deductions,
            "net_pay": net_pay,
            "breakdown": breakdown
        }
