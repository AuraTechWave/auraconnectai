"""
Payroll Configuration Models for Production-Ready Business Logic.

Addresses business logic concerns by making all calculations configurable
and database-driven rather than hardcoded.
"""

from sqlalchemy import (
    Column, Integer, String, Numeric, Boolean, DateTime, 
    ForeignKey, Text, JSON, Enum
)
from sqlalchemy.orm import relationship
from backend.core.database import Base
from backend.core.mixins import TimestampMixin
from decimal import Decimal
from enum import Enum as PyEnum


class PayrollConfigurationType(str, PyEnum):
    """Types of payroll configuration settings."""
    BENEFIT_PRORATION = "benefit_proration"
    OVERTIME_RULES = "overtime_rules"
    TAX_APPROXIMATION = "tax_approximation"
    ROLE_RATES = "role_rates"
    JURISDICTION_RULES = "jurisdiction_rules"


class PayrollConfiguration(Base, TimestampMixin):
    """
    Configurable payroll settings that replace hardcoded values.
    
    This table stores all business logic configurations that were previously
    hardcoded, making the system flexible and production-ready.
    """
    __tablename__ = "payroll_configurations"
    
    id = Column(Integer, primary_key=True, index=True)
    config_type = Column(Enum(PayrollConfigurationType), nullable=False, index=True)
    config_key = Column(String(100), nullable=False, index=True)
    config_value = Column(JSON, nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String(100), nullable=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    effective_date = Column(DateTime, nullable=False)
    expiry_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    __table_args__ = (
        {'comment': 'Configurable payroll business logic settings'}
    )


class StaffPayPolicy(Base, TimestampMixin):
    """
    Staff-specific pay policies replacing hardcoded policy logic.
    
    This addresses the concern about get_staff_pay_policy returning static data.
    """
    __tablename__ = "staff_pay_policies"
    
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(
        Integer,
        ForeignKey("staff_members.id"),
        nullable=False,
        index=True
    )
    location = Column(String(100), nullable=False, index=True)
    
    # Pay rates
    base_hourly_rate = Column(Numeric(10, 4), nullable=False)
    overtime_multiplier = Column(Numeric(5, 4), default=Decimal('1.5'), nullable=False)
    double_time_multiplier = Column(Numeric(5, 4), default=Decimal('2.0'), nullable=False)
    
    # Overtime rules - configurable thresholds
    daily_overtime_threshold = Column(Numeric(6, 2), nullable=True)
    weekly_overtime_threshold = Column(Numeric(6, 2), default=Decimal('40.0'), nullable=False)
    
    # Benefit deductions (monthly amounts)
    health_insurance_monthly = Column(Numeric(8, 2), default=Decimal('0.00'), nullable=False)
    dental_insurance_monthly = Column(Numeric(8, 2), default=Decimal('0.00'), nullable=False)
    retirement_contribution_monthly = Column(Numeric(8, 2), default=Decimal('0.00'), nullable=False)
    parking_fee_monthly = Column(Numeric(8, 2), default=Decimal('0.00'), nullable=False)
    
    # Proration settings - configurable factors
    benefit_proration_factor = Column(Numeric(5, 4), nullable=False)
    pay_frequency_factor = Column(Numeric(5, 4), nullable=False)
    
    # Metadata
    effective_date = Column(DateTime, nullable=False)
    expiry_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    tenant_id = Column(Integer, nullable=True, index=True)
    
    # Relationships
    staff_member = relationship("StaffMember", back_populates="pay_policies")
    
    __table_args__ = (
        {'comment': 'Staff-specific pay policies and configurations'}
    )


class OvertimeRule(Base, TimestampMixin):
    """
    Configurable overtime rules for different jurisdictions.
    
    Addresses the concern about flat 40-hour thresholds and jurisdiction-specific rules.
    """
    __tablename__ = "overtime_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    rule_name = Column(String(100), nullable=False)
    jurisdiction = Column(String(100), nullable=False, index=True)
    
    # Daily overtime rules
    daily_threshold_hours = Column(Numeric(6, 2), nullable=True)
    daily_overtime_multiplier = Column(Numeric(5, 4), nullable=True)
    daily_double_time_threshold = Column(Numeric(6, 2), nullable=True)
    daily_double_time_multiplier = Column(Numeric(5, 4), nullable=True)
    
    # Weekly overtime rules
    weekly_threshold_hours = Column(Numeric(6, 2), nullable=True)
    weekly_overtime_multiplier = Column(Numeric(5, 4), nullable=True)
    
    # Consecutive day rules (e.g., 7th consecutive day)
    consecutive_days_threshold = Column(Integer, nullable=True)
    consecutive_days_multiplier = Column(Numeric(5, 4), nullable=True)
    
    # Holiday and special day rules
    holiday_multiplier = Column(Numeric(5, 4), nullable=True)
    sunday_multiplier = Column(Numeric(5, 4), nullable=True)
    
    # Rule precedence (higher number = higher priority)
    precedence = Column(Integer, default=0, nullable=False)
    
    # Metadata
    effective_date = Column(DateTime, nullable=False)
    expiry_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    tenant_id = Column(Integer, nullable=True)
    
    __table_args__ = (
        {'comment': 'Configurable overtime rules by jurisdiction'}
    )


class TaxApproximationRule(Base, TimestampMixin):
    """
    Tax approximation rules for detailed breakdowns when exact values aren't available.
    
    Addresses the concern about hardcoded tax breakdown percentages.
    """
    __tablename__ = "tax_approximation_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    rule_name = Column(String(100), nullable=False)
    jurisdiction = Column(String(100), nullable=False, index=True)
    
    # Approximation percentages for tax breakdown
    federal_tax_percentage = Column(Numeric(5, 4), nullable=False)
    state_tax_percentage = Column(Numeric(5, 4), nullable=False)
    local_tax_percentage = Column(Numeric(5, 4), default=Decimal('0.0'), nullable=False)
    social_security_percentage = Column(Numeric(5, 4), nullable=False)
    medicare_percentage = Column(Numeric(5, 4), nullable=False)
    unemployment_percentage = Column(Numeric(5, 4), default=Decimal('0.0'), nullable=False)
    
    # Total should equal 1.0 for validation
    total_percentage = Column(Numeric(5, 4), nullable=False)
    
    # Metadata
    effective_date = Column(DateTime, nullable=False)
    expiry_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    tenant_id = Column(Integer, nullable=True)
    
    __table_args__ = (
        {'comment': 'Tax breakdown approximation rules when exact values unavailable'}
    )


class RoleBasedPayRate(Base, TimestampMixin):
    """
    Role-based pay rates replacing hardcoded role rate mappings.
    
    Addresses the concern about static role rate data.
    """
    __tablename__ = "role_based_pay_rates"
    
    id = Column(Integer, primary_key=True, index=True)
    role_name = Column(String(50), nullable=False, index=True)
    location = Column(String(100), nullable=False, index=True)
    
    # Pay rate information
    default_hourly_rate = Column(Numeric(10, 4), nullable=False)
    minimum_hourly_rate = Column(Numeric(10, 4), nullable=False)
    maximum_hourly_rate = Column(Numeric(10, 4), nullable=True)
    
    # Experience-based adjustments
    entry_level_rate = Column(Numeric(10, 4), nullable=True)
    experienced_rate = Column(Numeric(10, 4), nullable=True)
    senior_rate = Column(Numeric(10, 4), nullable=True)
    
    # Overtime settings
    overtime_eligible = Column(Boolean, default=True, nullable=False)
    overtime_multiplier = Column(Numeric(5, 4), default=Decimal('1.5'), nullable=False)
    
    # Metadata
    effective_date = Column(DateTime, nullable=False)
    expiry_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    tenant_id = Column(Integer, nullable=True)
    
    __table_args__ = (
        {'comment': 'Role-based default pay rates by location'}
    )


class PayrollJobTracking(Base, TimestampMixin):
    """
    Persistent tracking for batch payroll jobs.
    
    Addresses the concern about in-memory job tracking.
    """
    __tablename__ = "payroll_job_tracking"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(100), unique=True, nullable=False, index=True)
    job_type = Column(String(50), nullable=False)  # 'batch_payroll', 'export', etc.
    
    # Job parameters
    staff_ids = Column(JSON, nullable=True)
    pay_period_start = Column(DateTime, nullable=True)
    pay_period_end = Column(DateTime, nullable=True)
    tenant_id = Column(Integer, nullable=True)
    
    # Status tracking
    status = Column(String(50), default='pending', nullable=False, index=True)
    total_items = Column(Integer, default=0, nullable=False)
    completed_items = Column(Integer, default=0, nullable=False)
    failed_items = Column(Integer, default=0, nullable=False)
    
    # Progress and timing
    progress_percentage = Column(Integer, default=0, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    estimated_completion = Column(DateTime, nullable=True)
    
    # Results and errors
    result_data = Column(JSON, nullable=True)
    error_details = Column(JSON, nullable=True)
    
    # Metadata
    created_by = Column(String(100), nullable=True)
    tenant_id_filter = Column(Integer, nullable=True)
    
    __table_args__ = (
        {'comment': 'Persistent tracking for batch payroll operations'}
    )