from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from backend.core.database import Base
from backend.core.mixins import TimestampMixin


class TaxRule(Base, TimestampMixin):
    __tablename__ = "payroll_tax_rules"

    id = Column(Integer, primary_key=True, index=True)
    rule_name = Column(String(100), nullable=False, index=True)
    location = Column(String(100), nullable=False, index=True)
    tax_type = Column(String(50), nullable=False)  # federal, state, local, social_security, medicare
    rate_percent = Column(Numeric(5, 4), nullable=False)
    max_taxable_amount = Column(Numeric(10, 2), nullable=True)
    min_taxable_amount = Column(Numeric(10, 2), nullable=True)
    employee_portion = Column(Numeric(5, 4), nullable=True)
    employer_portion = Column(Numeric(5, 4), nullable=True)
    effective_date = Column(DateTime, nullable=False)
    expiry_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


class PayrollPolicy(Base, TimestampMixin):
    __tablename__ = "payroll_policies"

    id = Column(Integer, primary_key=True, index=True)
    policy_name = Column(String(100), nullable=False, index=True)
    location = Column(String(100), nullable=False, index=True)
    pay_frequency = Column(String(20), nullable=False)  # weekly, biweekly, monthly, semimonthly
    overtime_threshold_hours = Column(Numeric(4, 2), default=40.00, nullable=False)
    overtime_multiplier = Column(Numeric(3, 2), default=1.50, nullable=False)
    double_time_threshold_hours = Column(Numeric(4, 2), nullable=True)
    double_time_multiplier = Column(Numeric(3, 2), default=2.00, nullable=True)
    pay_period_start_day = Column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    minimum_wage = Column(Numeric(8, 2), nullable=False)
    meal_break_threshold_hours = Column(Numeric(4, 2), default=5.00, nullable=True)
    rest_break_threshold_hours = Column(Numeric(4, 2), default=4.00, nullable=True)
    holiday_pay_multiplier = Column(Numeric(3, 2), default=1.50, nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    employee_payments = relationship("EmployeePayment", back_populates="payroll_policy")


class EmployeePayment(Base, TimestampMixin):
    __tablename__ = "employee_payments"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, nullable=False, index=True)  # Reference to staff member
    payroll_policy_id = Column(Integer, ForeignKey("payroll_policies.id"), nullable=False)
    pay_period_start = Column(DateTime, nullable=False)
    pay_period_end = Column(DateTime, nullable=False)
    pay_date = Column(DateTime, nullable=False)
    
    # Hours worked
    regular_hours = Column(Numeric(6, 2), default=0.00, nullable=False)
    overtime_hours = Column(Numeric(6, 2), default=0.00, nullable=False)
    double_time_hours = Column(Numeric(6, 2), default=0.00, nullable=False)
    holiday_hours = Column(Numeric(6, 2), default=0.00, nullable=False)
    
    # Pay rates
    regular_rate = Column(Numeric(8, 2), nullable=False)
    overtime_rate = Column(Numeric(8, 2), nullable=True)
    double_time_rate = Column(Numeric(8, 2), nullable=True)
    holiday_rate = Column(Numeric(8, 2), nullable=True)
    
    # Gross pay calculations
    regular_pay = Column(Numeric(10, 2), default=0.00, nullable=False)
    overtime_pay = Column(Numeric(10, 2), default=0.00, nullable=False)
    double_time_pay = Column(Numeric(10, 2), default=0.00, nullable=False)
    holiday_pay = Column(Numeric(10, 2), default=0.00, nullable=False)
    bonus_pay = Column(Numeric(10, 2), default=0.00, nullable=False)
    commission_pay = Column(Numeric(10, 2), default=0.00, nullable=False)
    gross_pay = Column(Numeric(10, 2), nullable=False)
    
    # Tax deductions
    federal_tax = Column(Numeric(10, 2), default=0.00, nullable=False)
    state_tax = Column(Numeric(10, 2), default=0.00, nullable=False)
    local_tax = Column(Numeric(10, 2), default=0.00, nullable=False)
    social_security_tax = Column(Numeric(10, 2), default=0.00, nullable=False)
    medicare_tax = Column(Numeric(10, 2), default=0.00, nullable=False)
    
    # Other deductions
    insurance_deduction = Column(Numeric(10, 2), default=0.00, nullable=False)
    retirement_deduction = Column(Numeric(10, 2), default=0.00, nullable=False)
    other_deductions = Column(Numeric(10, 2), default=0.00, nullable=False)
    total_deductions = Column(Numeric(10, 2), nullable=False)
    
    # Net pay
    net_pay = Column(Numeric(10, 2), nullable=False)
    
    # Status and metadata
    payment_status = Column(String(20), default="pending", nullable=False)  # pending, processed, paid, cancelled
    payment_method = Column(String(30), nullable=True)  # direct_deposit, check, cash
    notes = Column(Text, nullable=True)
    processed_by = Column(String(100), nullable=True)
    processed_at = Column(DateTime, nullable=True)

    # Relationships
    payroll_policy = relationship("PayrollPolicy", back_populates="employee_payments")