from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, DateTime, Boolean, Text, Enum, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from backend.core.database import Base
from backend.core.mixins import TimestampMixin
from backend.modules.payroll.enums import PaymentStatus, PayFrequency, TaxType, PaymentMethod


class TaxRule(Base, TimestampMixin):
    __tablename__ = "payroll_tax_rules"

    id = Column(Integer, primary_key=True, index=True)
    rule_name = Column(String(100), nullable=False, index=True)
    location = Column(String(100), nullable=False, index=True)
    tax_type = Column(Enum(TaxType), nullable=False)
    rate_percent = Column(Numeric(5, 4), nullable=False)
    max_taxable_amount = Column(Numeric(12, 2), nullable=True)
    min_taxable_amount = Column(Numeric(12, 2), nullable=True)
    employee_portion = Column(Numeric(5, 4), nullable=True)
    employer_portion = Column(Numeric(5, 4), nullable=True)
    currency = Column(String(3), default='USD', nullable=False)
    tenant_id = Column(Integer, nullable=True)
    effective_date = Column(DateTime, nullable=False)
    expiry_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    tax_applications = relationship("EmployeePaymentTaxApplication", back_populates="tax_rule")


class PayrollPolicy(Base, TimestampMixin):
    __tablename__ = "payroll_policies"

    id = Column(Integer, primary_key=True, index=True)
    policy_name = Column(String(100), nullable=False, index=True)
    location = Column(String(100), nullable=False, index=True)
    pay_frequency = Column(Enum(PayFrequency), nullable=False)
    overtime_threshold_hours = Column(Numeric(6, 2), default=40.00, nullable=False)
    overtime_multiplier = Column(Numeric(5, 4), default=1.5000, nullable=False)
    double_time_threshold_hours = Column(Numeric(6, 2), nullable=True)
    double_time_multiplier = Column(Numeric(5, 4), default=2.0000, nullable=True)
    pay_period_start_day = Column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    minimum_wage = Column(Numeric(8, 2), nullable=False)
    meal_break_threshold_hours = Column(Numeric(6, 2), default=5.00, nullable=True)
    rest_break_threshold_hours = Column(Numeric(6, 2), default=4.00, nullable=True)
    holiday_pay_multiplier = Column(Numeric(5, 4), default=1.5000, nullable=True)
    currency = Column(String(3), default='USD', nullable=False)
    tenant_id = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    employee_payments = relationship("EmployeePayment", back_populates="payroll_policy")
    
    __table_args__ = (
        Index('ix_payroll_policies_location_active', 'location', 'is_active'),
        Index('ix_payroll_policies_tenant_location', 'tenant_id', 'location'),
    )


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
    regular_rate = Column(Numeric(10, 4), nullable=False)
    overtime_rate = Column(Numeric(10, 4), nullable=True)
    double_time_rate = Column(Numeric(10, 4), nullable=True)
    holiday_rate = Column(Numeric(10, 4), nullable=True)
    
    # Gross pay calculations
    regular_pay = Column(Numeric(12, 2), default=0.00, nullable=False)
    overtime_pay = Column(Numeric(12, 2), default=0.00, nullable=False)
    double_time_pay = Column(Numeric(12, 2), default=0.00, nullable=False)
    holiday_pay = Column(Numeric(12, 2), default=0.00, nullable=False)
    bonus_pay = Column(Numeric(12, 2), default=0.00, nullable=False)
    commission_pay = Column(Numeric(12, 2), default=0.00, nullable=False)
    gross_pay = Column(Numeric(12, 2), nullable=False)
    
    # Tax deductions
    federal_tax = Column(Numeric(12, 2), default=0.00, nullable=False)
    state_tax = Column(Numeric(12, 2), default=0.00, nullable=False)
    local_tax = Column(Numeric(12, 2), default=0.00, nullable=False)
    social_security_tax = Column(Numeric(12, 2), default=0.00, nullable=False)
    medicare_tax = Column(Numeric(12, 2), default=0.00, nullable=False)
    
    # Other deductions
    insurance_deduction = Column(Numeric(12, 2), default=0.00, nullable=False)
    retirement_deduction = Column(Numeric(12, 2), default=0.00, nullable=False)
    other_deductions = Column(Numeric(12, 2), default=0.00, nullable=False)
    total_deductions = Column(Numeric(12, 2), nullable=False)
    
    # Net pay
    net_pay = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default='USD', nullable=False)
    tenant_id = Column(Integer, nullable=True)
    
    # Status and metadata
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    payment_method = Column(Enum(PaymentMethod), nullable=True)
    notes = Column(Text, nullable=True)
    processed_by = Column(String(100), nullable=True)
    processed_at = Column(DateTime, nullable=True)

    # Relationships
    payroll_policy = relationship("PayrollPolicy", back_populates="employee_payments")
    tax_applications = relationship("EmployeePaymentTaxApplication", back_populates="employee_payment")
    
    __table_args__ = (
        UniqueConstraint('staff_id', 'pay_period_start', 'pay_period_end', name='uq_employee_payment_period'),
        Index('ix_employee_payments_staff_period', 'staff_id', 'pay_period_start', 'pay_period_end'),
        Index('ix_employee_payments_pay_date', 'pay_date'),
        Index('ix_employee_payments_status', 'payment_status'),
        Index('ix_employee_payments_tenant_staff', 'tenant_id', 'staff_id'),
    )


class EmployeePaymentTaxApplication(Base, TimestampMixin):
    __tablename__ = "employee_payment_tax_applications"

    id = Column(Integer, primary_key=True, index=True)
    employee_payment_id = Column(
        Integer,
        ForeignKey("employee_payments.id"),
        nullable=False
    )
    tax_rule_id = Column(
        Integer,
        ForeignKey("payroll_tax_rules.id"),
        nullable=False
    )

    # Tax calculation details
    taxable_amount = Column(Numeric(12, 2), nullable=False)
    calculated_tax = Column(Numeric(12, 2), nullable=False)
    effective_rate = Column(Numeric(5, 4), nullable=False)

    # Audit information
    calculation_date = Column(DateTime, nullable=False)
    calculation_method = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    employee_payment = relationship(
        "EmployeePayment",
        back_populates="tax_applications"
    )
    tax_rule = relationship("TaxRule", back_populates="tax_applications")

    __table_args__ = (
        UniqueConstraint(
            'employee_payment_id',
            'tax_rule_id',
            name='uq_payment_tax_rule'
        ),
        Index('ix_tax_applications_payment_id', 'employee_payment_id'),
        Index('ix_tax_applications_tax_rule_id', 'tax_rule_id'),
        Index('ix_tax_applications_calculation_date', 'calculation_date'),
    )
