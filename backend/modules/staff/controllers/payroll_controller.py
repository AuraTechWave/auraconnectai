from sqlalchemy.orm import Session
from backend.modules.staff.services.payroll_service import calculate_payroll
from backend.modules.staff.schemas.payroll_schemas import PayrollRequest, PayrollResponse


async def process_payroll(request: PayrollRequest, db: Session) -> PayrollResponse:
    return await calculate_payroll(request.staff_id, request.period, db)


async def get_payroll_history(staff_id: int, db: Session):
    from backend.modules.staff.models.payroll_models import Payroll
    payrolls = db.query(Payroll).filter(Payroll.staff_id == staff_id).all()
    return payrolls
