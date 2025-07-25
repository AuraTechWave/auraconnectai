from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Numeric, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from backend.core.database import Base
from backend.core.mixins import TimestampMixin
from ..enums.payroll_enums import PaymentStatus


class PayrollTaxRule(Base, TimestampMixin):
    __tablename__ = "payroll_tax_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    region = Column(String, nullable=False, index=True)
    tax_type = Column(String, nullable=False)
    rate = Column(Numeric(10, 4), nullable=False)
    effective_date = Column(DateTime, nullable=False)
    expiry_date = Column(DateTime, nullable=True)


class PayrollPolicy(Base, TimestampMixin):
    __tablename__ = "payroll_policies"
    
    id = Column(Integer, primary_key=True, index=True)
    policy_name = Column(String, nullable=False, index=True)
    basic_pay = Column(Numeric(10, 2), nullable=False)
    allowances = Column(JSONB, nullable=True)
    deductions = Column(JSONB, nullable=True)
    effective_date = Column(DateTime, nullable=False)


class EmployeePayment(Base, TimestampMixin):
    __tablename__ = "employee_payments"
    
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff_members.id"), nullable=False, index=True)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    gross_earnings = Column(Numeric(10, 2), nullable=False)
    deductions_total = Column(Numeric(10, 2), nullable=False)
    taxes_total = Column(Numeric(10, 2), nullable=False)
    net_pay = Column(Numeric(10, 2), nullable=False)
    status = Column(SQLEnum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
    processed_at = Column(DateTime, nullable=True)
    
    staff_member = relationship("StaffMember")
