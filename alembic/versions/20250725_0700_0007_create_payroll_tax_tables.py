"""create_payroll_tax_tables

Revision ID: 20250725_0700_0007
Revises: 20250725_0601_0005
Create Date: 2025-07-25 07:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20250725_0700_0007'
down_revision: Union[str, None] = '20250725_0601_0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create payroll_tax_rules table
    op.create_table(
        'payroll_tax_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rule_name', sa.String(100), nullable=False),
        sa.Column('location', sa.String(100), nullable=False),
        sa.Column('tax_type', sa.String(50), nullable=False),
        sa.Column('rate_percent', sa.Numeric(5, 4), nullable=False),
        sa.Column('max_taxable_amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('min_taxable_amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('employee_portion', sa.Numeric(5, 4), nullable=True),
        sa.Column('employer_portion', sa.Numeric(5, 4), nullable=True),
        sa.Column('effective_date', sa.DateTime(), nullable=False),
        sa.Column('expiry_date', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payroll_tax_rules_id'), 'payroll_tax_rules', ['id'], unique=False)
    op.create_index(op.f('ix_payroll_tax_rules_rule_name'), 'payroll_tax_rules', ['rule_name'], unique=False)
    op.create_index(op.f('ix_payroll_tax_rules_location'), 'payroll_tax_rules', ['location'], unique=False)

    # Create payroll_policies table
    op.create_table(
        'payroll_policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('policy_name', sa.String(100), nullable=False),
        sa.Column('location', sa.String(100), nullable=False),
        sa.Column('pay_frequency', sa.String(20), nullable=False),
        sa.Column('overtime_threshold_hours', sa.Numeric(4, 2), nullable=False),
        sa.Column('overtime_multiplier', sa.Numeric(3, 2), nullable=False),
        sa.Column('double_time_threshold_hours', sa.Numeric(4, 2), nullable=True),
        sa.Column('double_time_multiplier', sa.Numeric(3, 2), nullable=True),
        sa.Column('pay_period_start_day', sa.Integer(), nullable=False),
        sa.Column('minimum_wage', sa.Numeric(8, 2), nullable=False),
        sa.Column('meal_break_threshold_hours', sa.Numeric(4, 2), nullable=True),
        sa.Column('rest_break_threshold_hours', sa.Numeric(4, 2), nullable=True),
        sa.Column('holiday_pay_multiplier', sa.Numeric(3, 2), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payroll_policies_id'), 'payroll_policies', ['id'], unique=False)
    op.create_index(op.f('ix_payroll_policies_policy_name'), 'payroll_policies', ['policy_name'], unique=False)
    op.create_index(op.f('ix_payroll_policies_location'), 'payroll_policies', ['location'], unique=False)

    # Create employee_payments table
    op.create_table(
        'employee_payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('staff_id', sa.Integer(), nullable=False),
        sa.Column('payroll_policy_id', sa.Integer(), nullable=False),
        sa.Column('pay_period_start', sa.DateTime(), nullable=False),
        sa.Column('pay_period_end', sa.DateTime(), nullable=False),
        sa.Column('pay_date', sa.DateTime(), nullable=False),
        sa.Column('regular_hours', sa.Numeric(6, 2), nullable=False),
        sa.Column('overtime_hours', sa.Numeric(6, 2), nullable=False),
        sa.Column('double_time_hours', sa.Numeric(6, 2), nullable=False),
        sa.Column('holiday_hours', sa.Numeric(6, 2), nullable=False),
        sa.Column('regular_rate', sa.Numeric(8, 2), nullable=False),
        sa.Column('overtime_rate', sa.Numeric(8, 2), nullable=True),
        sa.Column('double_time_rate', sa.Numeric(8, 2), nullable=True),
        sa.Column('holiday_rate', sa.Numeric(8, 2), nullable=True),
        sa.Column('regular_pay', sa.Numeric(10, 2), nullable=False),
        sa.Column('overtime_pay', sa.Numeric(10, 2), nullable=False),
        sa.Column('double_time_pay', sa.Numeric(10, 2), nullable=False),
        sa.Column('holiday_pay', sa.Numeric(10, 2), nullable=False),
        sa.Column('bonus_pay', sa.Numeric(10, 2), nullable=False),
        sa.Column('commission_pay', sa.Numeric(10, 2), nullable=False),
        sa.Column('gross_pay', sa.Numeric(10, 2), nullable=False),
        sa.Column('federal_tax', sa.Numeric(10, 2), nullable=False),
        sa.Column('state_tax', sa.Numeric(10, 2), nullable=False),
        sa.Column('local_tax', sa.Numeric(10, 2), nullable=False),
        sa.Column('social_security_tax', sa.Numeric(10, 2), nullable=False),
        sa.Column('medicare_tax', sa.Numeric(10, 2), nullable=False),
        sa.Column('insurance_deduction', sa.Numeric(10, 2), nullable=False),
        sa.Column('retirement_deduction', sa.Numeric(10, 2), nullable=False),
        sa.Column('other_deductions', sa.Numeric(10, 2), nullable=False),
        sa.Column('total_deductions', sa.Numeric(10, 2), nullable=False),
        sa.Column('net_pay', sa.Numeric(10, 2), nullable=False),
        sa.Column('payment_status', sa.String(20), nullable=False),
        sa.Column('payment_method', sa.String(30), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('processed_by', sa.String(100), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['payroll_policy_id'], ['payroll_policies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_employee_payments_id'), 'employee_payments', ['id'], unique=False)
    op.create_index(op.f('ix_employee_payments_staff_id'), 'employee_payments', ['staff_id'], unique=False)


def downgrade() -> None:
    # Drop employee_payments table
    op.drop_index(op.f('ix_employee_payments_staff_id'), table_name='employee_payments')
    op.drop_index(op.f('ix_employee_payments_id'), table_name='employee_payments')
    op.drop_table('employee_payments')
    
    # Drop payroll_policies table
    op.drop_index(op.f('ix_payroll_policies_location'), table_name='payroll_policies')
    op.drop_index(op.f('ix_payroll_policies_policy_name'), table_name='payroll_policies')
    op.drop_index(op.f('ix_payroll_policies_id'), table_name='payroll_policies')
    op.drop_table('payroll_policies')
    
    # Drop payroll_tax_rules table
    op.drop_index(op.f('ix_payroll_tax_rules_location'), table_name='payroll_tax_rules')
    op.drop_index(op.f('ix_payroll_tax_rules_rule_name'), table_name='payroll_tax_rules')
    op.drop_index(op.f('ix_payroll_tax_rules_id'), table_name='payroll_tax_rules')
    op.drop_table('payroll_tax_rules')