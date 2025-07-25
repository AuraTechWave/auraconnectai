"""create_enhanced_payroll_tax_tables

Revision ID: 20250725_0730_0008
Revises: 20250725_0700_0007
Create Date: 2025-07-25 07:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20250725_0730_0008'
down_revision: Union[str, None] = '20250725_0601_0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    payment_status_enum = sa.Enum('PENDING', 'CALCULATED', 'APPROVED', 'PROCESSED', 'PAID', 'CANCELLED', 'FAILED', name='paymentstatus')
    pay_frequency_enum = sa.Enum('WEEKLY', 'BIWEEKLY', 'SEMIMONTHLY', 'MONTHLY', name='payfrequency')
    tax_type_enum = sa.Enum('FEDERAL', 'STATE', 'LOCAL', 'SOCIAL_SECURITY', 'MEDICARE', 'UNEMPLOYMENT', 'DISABILITY', 'WORKERS_COMP', name='taxtype')
    payment_method_enum = sa.Enum('DIRECT_DEPOSIT', 'CHECK', 'CASH', 'DIGITAL_WALLET', name='paymentmethod')
    
    payment_status_enum.create(op.get_bind())
    pay_frequency_enum.create(op.get_bind())
    tax_type_enum.create(op.get_bind())
    payment_method_enum.create(op.get_bind())

    # Create enhanced payroll_tax_rules table
    op.create_table(
        'payroll_tax_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rule_name', sa.String(100), nullable=False),
        sa.Column('location', sa.String(100), nullable=False),
        sa.Column('tax_type', tax_type_enum, nullable=False),
        sa.Column('rate_percent', sa.Numeric(5, 4), nullable=False),
        sa.Column('max_taxable_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('min_taxable_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('employee_portion', sa.Numeric(5, 4), nullable=True),
        sa.Column('employer_portion', sa.Numeric(5, 4), nullable=True),
        sa.Column('currency', sa.String(3), nullable=False, server_default='USD'),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('effective_date', sa.DateTime(), nullable=False),
        sa.Column('expiry_date', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payroll_tax_rules_id'), 'payroll_tax_rules', ['id'], unique=False)
    op.create_index(op.f('ix_payroll_tax_rules_rule_name'), 'payroll_tax_rules', ['rule_name'], unique=False)
    op.create_index(op.f('ix_payroll_tax_rules_location'), 'payroll_tax_rules', ['location'], unique=False)

    # Create enhanced payroll_policies table
    op.create_table(
        'payroll_policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('policy_name', sa.String(100), nullable=False),
        sa.Column('location', sa.String(100), nullable=False),
        sa.Column('pay_frequency', pay_frequency_enum, nullable=False),
        sa.Column('overtime_threshold_hours', sa.Numeric(6, 2), nullable=False, server_default='40.00'),
        sa.Column('overtime_multiplier', sa.Numeric(5, 4), nullable=False, server_default='1.5000'),
        sa.Column('double_time_threshold_hours', sa.Numeric(6, 2), nullable=True),
        sa.Column('double_time_multiplier', sa.Numeric(5, 4), nullable=True, server_default='2.0000'),
        sa.Column('pay_period_start_day', sa.Integer(), nullable=False),
        sa.Column('minimum_wage', sa.Numeric(8, 2), nullable=False),
        sa.Column('meal_break_threshold_hours', sa.Numeric(6, 2), nullable=True, server_default='5.00'),
        sa.Column('rest_break_threshold_hours', sa.Numeric(6, 2), nullable=True, server_default='4.00'),
        sa.Column('holiday_pay_multiplier', sa.Numeric(5, 4), nullable=True, server_default='1.5000'),
        sa.Column('currency', sa.String(3), nullable=False, server_default='USD'),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payroll_policies_id'), 'payroll_policies', ['id'], unique=False)
    op.create_index(op.f('ix_payroll_policies_policy_name'), 'payroll_policies', ['policy_name'], unique=False)
    op.create_index(op.f('ix_payroll_policies_location'), 'payroll_policies', ['location'], unique=False)
    op.create_index('ix_payroll_policies_location_active', 'payroll_policies', ['location', 'is_active'])
    op.create_index('ix_payroll_policies_tenant_location', 'payroll_policies', ['tenant_id', 'location'])

    # Create enhanced employee_payments table
    op.create_table(
        'employee_payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('staff_id', sa.Integer(), nullable=False),
        sa.Column('payroll_policy_id', sa.Integer(), nullable=False),
        sa.Column('pay_period_start', sa.DateTime(), nullable=False),
        sa.Column('pay_period_end', sa.DateTime(), nullable=False),
        sa.Column('pay_date', sa.DateTime(), nullable=False),
        sa.Column('regular_hours', sa.Numeric(6, 2), nullable=False, server_default='0.00'),
        sa.Column('overtime_hours', sa.Numeric(6, 2), nullable=False, server_default='0.00'),
        sa.Column('double_time_hours', sa.Numeric(6, 2), nullable=False, server_default='0.00'),
        sa.Column('holiday_hours', sa.Numeric(6, 2), nullable=False, server_default='0.00'),
        sa.Column('regular_rate', sa.Numeric(10, 4), nullable=False),
        sa.Column('overtime_rate', sa.Numeric(10, 4), nullable=True),
        sa.Column('double_time_rate', sa.Numeric(10, 4), nullable=True),
        sa.Column('holiday_rate', sa.Numeric(10, 4), nullable=True),
        sa.Column('regular_pay', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('overtime_pay', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('double_time_pay', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('holiday_pay', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('bonus_pay', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('commission_pay', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('gross_pay', sa.Numeric(12, 2), nullable=False),
        sa.Column('federal_tax', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('state_tax', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('local_tax', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('social_security_tax', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('medicare_tax', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('insurance_deduction', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('retirement_deduction', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('other_deductions', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('total_deductions', sa.Numeric(12, 2), nullable=False),
        sa.Column('net_pay', sa.Numeric(12, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='USD'),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('payment_status', payment_status_enum, nullable=False, server_default='PENDING'),
        sa.Column('payment_method', payment_method_enum, nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('processed_by', sa.String(100), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['payroll_policy_id'], ['payroll_policies.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('staff_id', 'pay_period_start', 'pay_period_end', name='uq_employee_payment_period')
    )
    op.create_index(op.f('ix_employee_payments_id'), 'employee_payments', ['id'], unique=False)
    op.create_index(op.f('ix_employee_payments_staff_id'), 'employee_payments', ['staff_id'], unique=False)
    op.create_index('ix_employee_payments_staff_period', 'employee_payments', ['staff_id', 'pay_period_start', 'pay_period_end'])
    op.create_index('ix_employee_payments_pay_date', 'employee_payments', ['pay_date'])
    op.create_index('ix_employee_payments_status', 'employee_payments', ['payment_status'])
    op.create_index('ix_employee_payments_tenant_staff', 'employee_payments', ['tenant_id', 'staff_id'])

    # Create employee_payment_tax_applications table
    op.create_table(
        'employee_payment_tax_applications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_payment_id', sa.Integer(), nullable=False),
        sa.Column('tax_rule_id', sa.Integer(), nullable=False),
        sa.Column('taxable_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('calculated_tax', sa.Numeric(12, 2), nullable=False),
        sa.Column('effective_rate', sa.Numeric(5, 4), nullable=False),
        sa.Column('calculation_date', sa.DateTime(), nullable=False),
        sa.Column('calculation_method', sa.String(50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['employee_payment_id'], ['employee_payments.id'], ),
        sa.ForeignKeyConstraint(['tax_rule_id'], ['payroll_tax_rules.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('employee_payment_id', 'tax_rule_id', name='uq_payment_tax_rule')
    )
    op.create_index(op.f('ix_employee_payment_tax_applications_id'), 'employee_payment_tax_applications', ['id'], unique=False)
    op.create_index('ix_tax_applications_payment_id', 'employee_payment_tax_applications', ['employee_payment_id'])
    op.create_index('ix_tax_applications_tax_rule_id', 'employee_payment_tax_applications', ['tax_rule_id'])
    op.create_index('ix_tax_applications_calculation_date', 'employee_payment_tax_applications', ['calculation_date'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('employee_payment_tax_applications')
    op.drop_table('employee_payments')
    op.drop_table('payroll_policies')
    op.drop_table('payroll_tax_rules')
    
    # Drop enum types
    sa.Enum(name='paymentmethod').drop(op.get_bind())
    sa.Enum(name='taxtype').drop(op.get_bind())
    sa.Enum(name='payfrequency').drop(op.get_bind())
    sa.Enum(name='paymentstatus').drop(op.get_bind())