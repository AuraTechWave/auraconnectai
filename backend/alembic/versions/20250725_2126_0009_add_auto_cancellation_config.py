"""Add auto cancellation configuration table

Revision ID: 20250725_2126_0009
Revises: 20250725_0730_0008
Create Date: 2025-07-25 21:26:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20250725_2126_0009'
down_revision: Union[str, None] = '20250810_1000_payroll_tax_tables_final'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'auto_cancellation_configs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), nullable=True, index=True),
        sa.Column('team_id', sa.Integer(), nullable=True, index=True),
        sa.Column('status', sa.String(), nullable=False, index=True),
        sa.Column('threshold_minutes', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('updated_by', sa.Integer(), sa.ForeignKey('staff_members.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()'))
    )
    
    op.create_index('idx_auto_cancel_config_unique', 'auto_cancellation_configs', 
                    ['tenant_id', 'team_id', 'status'], unique=True)


def downgrade() -> None:
    op.drop_table('auto_cancellation_configs')
