"""Improve payroll database design with foreign keys and enum constraints

Revision ID: 20250125_2045_0010
Revises: 20250725_0730_0008_create_enhanced_payroll_tax_tables
Create Date: 2025-01-25 20:45:00.000000

This migration addresses code review recommendations:
1. Add foreign key constraint for employee_payments.staff_id
2. Update staff status to use proper enum
3. Add server defaults for all numeric fields
4. Improve data consistency and integrity
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250125_2045_0010'
down_revision = '20250725_0730_0008_create_enhanced_payroll_tax_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply database improvements."""
    
    # Create new staff_status enum
    staff_status_enum = postgresql.ENUM(
        'active', 'inactive', 'on_leave', 'terminated', 'suspended',
        name='staffstatus'
    )
    staff_status_enum.create(op.get_bind())
    
    # Update staff_members table to use enum and improve constraints
    op.alter_column(
        'staff_members',
        'status',
        existing_type=sa.String(),
        type_=staff_status_enum,
        existing_nullable=True,
        nullable=False,
        server_default='active'
    )
    
    # Add foreign key constraint for employee_payments.staff_id
    op.create_foreign_key(
        'fk_employee_payments_staff_id',
        'employee_payments',
        'staff_members',
        ['staff_id'],
        ['id'],
        ondelete='RESTRICT'
    )
    
    # Add server defaults for numeric fields in employee_payments
    numeric_fields_with_defaults = [
        ('regular_hours', '0.00'),
        ('overtime_hours', '0.00'),
        ('double_time_hours', '0.00'),
        ('holiday_hours', '0.00'),
        ('regular_pay', '0.00'),
        ('overtime_pay', '0.00'),
        ('double_time_pay', '0.00'),
        ('holiday_pay', '0.00'),
        ('bonus_pay', '0.00'),
        ('commission_pay', '0.00'),
        ('federal_tax', '0.00'),
        ('state_tax', '0.00'),
        ('local_tax', '0.00'),
        ('social_security_tax', '0.00'),
        ('medicare_tax', '0.00'),
        ('insurance_deduction', '0.00'),
        ('retirement_deduction', '0.00'),
        ('other_deductions', '0.00'),
    ]
    
    for field_name, default_value in numeric_fields_with_defaults:
        op.alter_column(
            'employee_payments',
            field_name,
            existing_type=sa.Numeric(12, 2),
            existing_nullable=False,
            server_default=default_value
        )
    
    # Add server defaults for payroll_policies
    policy_defaults = [
        ('overtime_threshold_hours', '40.00'),
        ('overtime_multiplier', '1.5000'),
        ('double_time_multiplier', '2.0000'),
        ('meal_break_threshold_hours', '5.00'),
        ('rest_break_threshold_hours', '4.00'),
        ('holiday_pay_multiplier', '1.5000'),
    ]
    
    for field_name, default_value in policy_defaults:
        op.alter_column(
            'payroll_policies',
            field_name,
            existing_type=sa.Numeric(),
            existing_nullable=False,
            server_default=default_value
        )
    
    # Add currency defaults
    op.alter_column(
        'employee_payments',
        'currency',
        existing_type=sa.String(3),
        existing_nullable=False,
        server_default='USD'
    )
    
    op.alter_column(
        'payroll_policies',
        'currency',
        existing_type=sa.String(3),
        existing_nullable=False,
        server_default='USD'
    )
    
    op.alter_column(
        'payroll_tax_rules',
        'currency',
        existing_type=sa.String(3),
        existing_nullable=False,
        server_default='USD'
    )
    
    # Add boolean defaults
    op.alter_column(
        'payroll_policies',
        'is_active',
        existing_type=sa.Boolean(),
        existing_nullable=False,
        server_default='true'
    )
    
    op.alter_column(
        'payroll_tax_rules',
        'is_active',
        existing_type=sa.Boolean(),
        existing_nullable=False,
        server_default='true'
    )
    
    # Add check constraints for data validation
    op.create_check_constraint(
        'ck_employee_payments_hours_positive',
        'employee_payments',
        'regular_hours >= 0 AND overtime_hours >= 0 AND double_time_hours >= 0 AND holiday_hours >= 0'
    )
    
    op.create_check_constraint(
        'ck_employee_payments_pay_positive',
        'employee_payments',
        'gross_pay >= 0 AND net_pay >= 0 AND total_deductions >= 0'
    )
    
    op.create_check_constraint(
        'ck_employee_payments_period_valid',
        'employee_payments',
        'pay_period_end > pay_period_start'
    )
    
    op.create_check_constraint(
        'ck_payroll_policies_multipliers_valid',
        'payroll_policies',
        'overtime_multiplier >= 1.0 AND double_time_multiplier >= 1.0 AND holiday_pay_multiplier >= 1.0'
    )
    
    op.create_check_constraint(
        'ck_payroll_tax_rules_rate_valid',
        'payroll_tax_rules',
        'rate_percent >= 0 AND rate_percent <= 1'
    )


def downgrade() -> None:
    """Reverse database improvements."""
    
    # Remove check constraints
    op.drop_constraint('ck_payroll_tax_rules_rate_valid', 'payroll_tax_rules')
    op.drop_constraint('ck_payroll_policies_multipliers_valid', 'payroll_policies')
    op.drop_constraint('ck_employee_payments_period_valid', 'employee_payments')
    op.drop_constraint('ck_employee_payments_pay_positive', 'employee_payments')
    op.drop_constraint('ck_employee_payments_hours_positive', 'employee_payments')
    
    # Remove server defaults
    op.alter_column('payroll_tax_rules', 'is_active', server_default=None)
    op.alter_column('payroll_tax_rules', 'currency', server_default=None)
    op.alter_column('payroll_policies', 'is_active', server_default=None)
    op.alter_column('payroll_policies', 'currency', server_default=None)
    op.alter_column('employee_payments', 'currency', server_default=None)
    
    # Remove payroll policy defaults
    policy_fields = [
        'overtime_threshold_hours', 'overtime_multiplier', 'double_time_multiplier',
        'meal_break_threshold_hours', 'rest_break_threshold_hours', 'holiday_pay_multiplier'
    ]
    
    for field_name in policy_fields:
        op.alter_column('payroll_policies', field_name, server_default=None)
    
    # Remove employee payment defaults
    payment_fields = [
        'regular_hours', 'overtime_hours', 'double_time_hours', 'holiday_hours',
        'regular_pay', 'overtime_pay', 'double_time_pay', 'holiday_pay',
        'bonus_pay', 'commission_pay', 'federal_tax', 'state_tax', 'local_tax',
        'social_security_tax', 'medicare_tax', 'insurance_deduction',
        'retirement_deduction', 'other_deductions'
    ]
    
    for field_name in payment_fields:
        op.alter_column('employee_payments', field_name, server_default=None)
    
    # Remove foreign key constraint
    op.drop_constraint('fk_employee_payments_staff_id', 'employee_payments', type_='foreignkey')
    
    # Revert staff status column
    op.alter_column(
        'staff_members',
        'status',
        existing_type=postgresql.ENUM('active', 'inactive', 'on_leave', 'terminated', 'suspended', name='staffstatus'),
        type_=sa.String(),
        existing_nullable=False,
        nullable=True,
        server_default=None
    )
    
    # Drop the enum
    op.execute('DROP TYPE staffstatus')