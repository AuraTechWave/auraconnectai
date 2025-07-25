"""create_audit_logs_table

Revision ID: 20250725_0454_0005
Revises: 20250724_1715_0004
Create Date: 2025-07-25 04:54:40.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20250725_0454_0005'
down_revision = '0004_add_order_tags_categories'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('module', sa.String(50), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('previous_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True)
    )
    
    op.create_index('ix_audit_logs_id', 'audit_logs', ['id'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_module', 'audit_logs', ['module'])
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_entity_id', 'audit_logs', ['entity_id'])
    op.create_index('ix_audit_logs_timestamp', 'audit_logs', ['timestamp'])
    
    op.create_index('ix_audit_logs_module_entity', 'audit_logs', ['module', 'entity_id'])
    op.create_index('ix_audit_logs_entity_timestamp', 'audit_logs', ['entity_id', 'timestamp'])


def downgrade() -> None:
    op.drop_index('ix_audit_logs_entity_timestamp', 'audit_logs')
    op.drop_index('ix_audit_logs_module_entity', 'audit_logs')
    op.drop_index('ix_audit_logs_timestamp', 'audit_logs')
    op.drop_index('ix_audit_logs_entity_id', 'audit_logs')
    op.drop_index('ix_audit_logs_user_id', 'audit_logs')
    op.drop_index('ix_audit_logs_module', 'audit_logs')
    op.drop_index('ix_audit_logs_action', 'audit_logs')
    op.drop_index('ix_audit_logs_id', 'audit_logs')
    op.drop_table('audit_logs')
