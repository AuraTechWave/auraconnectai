from sqlalchemy.orm import Session
from modules.staff.models.payroll_models import Payroll
from modules.staff.services.payroll_engine import PayrollEngine
from modules.staff.services.payslip_service import PayslipService
from modules.staff.schemas.payroll_schemas import PayrollResponse
from datetime import datetime


async def calculate_payroll(staff_id: int, period: str,
                            db: Session) -> PayrollResponse:
    payroll_engine = PayrollEngine(db)
    payslip_service = PayslipService(db)

    payroll_data = await payroll_engine.calculate_payroll(staff_id, period)

    existing_payroll = db.query(Payroll).filter(
        Payroll.staff_id == staff_id,
        Payroll.period == period
    ).first()

    if existing_payroll:
        existing_payroll.gross_pay = payroll_data["gross_pay"]
        existing_payroll.deductions = payroll_data["deductions"]
        existing_payroll.net_pay = payroll_data["net_pay"]
        existing_payroll.updated_at = datetime.utcnow()
        db.commit()
        payroll = existing_payroll
    else:
        payroll = Payroll(
            staff_id=staff_id,
            period=period,
            gross_pay=payroll_data["gross_pay"],
            deductions=payroll_data["deductions"],
            net_pay=payroll_data["net_pay"]
        )
        db.add(payroll)
        db.commit()
        db.refresh(payroll)

    await payslip_service.generate_payslip(payroll.id)

    return PayrollResponse(
        staff_id=payroll_data["staff_id"],
        period=payroll_data["period"],
        gross_pay=payroll_data["gross_pay"],
        deductions=payroll_data["deductions"],
        net_pay=payroll_data["net_pay"],
        breakdown=payroll_data["breakdown"],
        created_at=payroll.created_at
    )
