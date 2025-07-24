from pydantic import BaseModel
from datetime import datetime


class PayrollRequest(BaseModel):
    staff_id: int
    period: str


class PayrollBreakdown(BaseModel):
    hours_worked: float
    hourly_rate: float
    overtime_hours: float
    overtime_rate: float
    gross_earnings: float
    tax_deductions: float
    other_deductions: float
    total_deductions: float


class PayrollResponse(BaseModel):
    staff_id: int
    period: str
    gross_pay: float
    deductions: float
    net_pay: float
    breakdown: PayrollBreakdown
    created_at: datetime

    class Config:
        from_attributes = True


class PayslipOut(BaseModel):
    id: int
    payroll_id: int
    pdf_url: str
    issued_at: datetime

    class Config:
        from_attributes = True
