"""create_payroll_module_tables

Revision ID: 20250725_1730_0007
Revises: 20250725_0601_0005
Create Date: 2025-07-25 17:30:28.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '20250725_1730_0007'
down_revision: Union[str, None] = '20250725_0601_0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'payroll_tax_rules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('region', sa.String(), nullable=False, index=True),
        sa.Column('tax_type', sa.String(), nullable=False),
        sa.Column('rate', sa.Numeric(10, 4), nullable=False),
        sa.Column('effective_date', sa.DateTime(), nullable=False),
        sa.Column('expiry_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )
    
    op.create_table(
        'payroll_policies',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('policy_name', sa.String(), nullable=False, index=True),
        sa.Column('basic_pay', sa.Numeric(10, 2), nullable=False),
        sa.Column('allowances', JSONB, nullable=True),
        sa.Column('deductions', JSONB, nullable=True),
        sa.Column('effective_date', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )
    
    op.create_table(
        'employee_payments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('staff_id', sa.Integer(), sa.ForeignKey('staff_members.id'), nullable=False, index=True),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('gross_earnings', sa.Numeric(10, 2), nullable=False),
        sa.Column('deductions_total', sa.Numeric(10, 2), nullable=False),
        sa.Column('taxes_total', sa.Numeric(10, 2), nullable=False),
        sa.Column('net_pay', sa.Numeric(10, 2), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )


def downgrade() -> None:
    op.drop_table('employee_payments')
    op.drop_table('payroll_policies')
    op.drop_table('payroll_tax_rules')
