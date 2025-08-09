"""create_pos_tables

Revision ID: 87855e9897a9
Revises: 0002_create_orders_tables
Create Date: 2025-07-24 06:55:39.015082

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '87855e9897a9'
down_revision: Union[str, None] = '0002_create_orders_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'pos_integrations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('vendor', sa.String(), nullable=False),
        sa.Column('credentials', sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column('connected_on', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )
    
    op.create_index('ix_pos_integrations_id', 'pos_integrations', ['id'])
    op.create_index('ix_pos_integrations_vendor', 'pos_integrations', ['vendor'])
    op.create_index('ix_pos_integrations_status', 'pos_integrations', ['status'])
    
    op.create_table(
        'pos_sync_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('integration_id', sa.Integer(), sa.ForeignKey('pos_integrations.id'), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id'), nullable=True),
        sa.Column('attempt_count', sa.Integer(), nullable=False, default=1),
        sa.Column('synced_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )
    
    op.create_index('ix_pos_sync_logs_id', 'pos_sync_logs', ['id'])
    op.create_index('ix_pos_sync_logs_integration_id', 'pos_sync_logs', ['integration_id'])
    op.create_index('ix_pos_sync_logs_type', 'pos_sync_logs', ['type'])
    op.create_index('ix_pos_sync_logs_status', 'pos_sync_logs', ['status'])
    op.create_index('ix_pos_sync_logs_order_id', 'pos_sync_logs', ['order_id'])


def downgrade() -> None:
    op.drop_index('ix_pos_sync_logs_order_id', 'pos_sync_logs')
    op.drop_index('ix_pos_sync_logs_status', 'pos_sync_logs')
    op.drop_index('ix_pos_sync_logs_type', 'pos_sync_logs')
    op.drop_index('ix_pos_sync_logs_integration_id', 'pos_sync_logs')
    op.drop_index('ix_pos_sync_logs_id', 'pos_sync_logs')
    op.drop_table('pos_sync_logs')
    op.drop_index('ix_pos_integrations_status', 'pos_integrations')
    op.drop_index('ix_pos_integrations_vendor', 'pos_integrations')
    op.drop_index('ix_pos_integrations_id', 'pos_integrations')
    op.drop_table('pos_integrations')
