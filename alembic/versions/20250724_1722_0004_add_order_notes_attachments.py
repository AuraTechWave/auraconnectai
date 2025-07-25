"""add_order_notes_attachments

Revision ID: 0004_add_order_notes_attachments
Revises: 0003_create_payroll_tables
Create Date: 2025-07-24 17:22:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0004_add_order_notes_attachments'
down_revision = '0003_create_payroll_tables'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('orders', sa.Column('customer_notes', sa.Text(), nullable=True))
    
    op.create_table(
        'order_attachments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id'), nullable=False),
        sa.Column('file_name', sa.String(), nullable=False),
        sa.Column('file_url', sa.String(), nullable=False),
        sa.Column('file_type', sa.String(), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )
    
    op.create_index('ix_order_attachments_id', 'order_attachments', ['id'])
    op.create_index('ix_order_attachments_order_id', 'order_attachments', ['order_id'])

def downgrade():
    op.drop_index('ix_order_attachments_order_id', 'order_attachments')
    op.drop_index('ix_order_attachments_id', 'order_attachments')
    
    op.drop_table('order_attachments')
    
    op.drop_column('orders', 'customer_notes')
