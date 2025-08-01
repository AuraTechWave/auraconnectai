from sqlalchemy.orm import Session
from modules.staff.models.payroll_models import Payroll, Payslip
from datetime import datetime


class PayslipService:
    def __init__(self, db: Session):
        self.db = db

    async def generate_payslip(self, payroll_id: int) -> Payslip:
        payroll = self.db.query(Payroll).filter(
            Payroll.id == payroll_id).first()
        if not payroll:
            raise ValueError(f"Payroll with ID {payroll_id} not found")

        payslip = Payslip(
            payroll_id=payroll_id,
            pdf_url=f"/payslips/{payroll_id}.pdf",
            issued_at=datetime.utcnow()
        )

        self.db.add(payslip)
        self.db.commit()
        self.db.refresh(payslip)

        return payslip

    async def get_payslips_for_staff(self, staff_id: int):
        return self.db.query(Payslip).join(Payroll).filter(
            Payroll.staff_id == staff_id).all()
