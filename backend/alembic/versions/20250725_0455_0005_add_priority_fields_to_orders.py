"""Add priority fields to orders table

Revision ID: 0005_add_priority_fields_to_orders
Revises: 0004_add_order_tags_categories
Create Date: 2025-07-25 04:55:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0005_add_priority_fields_to_orders'
down_revision = '0004_add_order_tags_categories'
branch_labels = None
depends_on = None

def upgrade():
    priority_enum = postgresql.ENUM('low', 'normal', 'high', 'urgent', name='orderpriority')
    priority_enum.create(op.get_bind())
    
    op.add_column('orders', sa.Column(
        'priority', 
        priority_enum,
        nullable=False, 
        server_default='normal'
    ))
    op.add_column('orders', sa.Column(
        'priority_updated_at', 
        sa.DateTime(timezone=True), 
        nullable=True
    ))
    
    op.create_index('ix_orders_priority', 'orders', ['priority'])
    op.create_index('ix_orders_priority_status', 'orders', ['priority', 'status'])

def downgrade():
    op.drop_index('ix_orders_priority_status', 'orders')
    op.drop_index('ix_orders_priority', 'orders')
    op.drop_column('orders', 'priority_updated_at')
    op.drop_column('orders', 'priority')
    
    op.execute('DROP TYPE IF EXISTS orderpriority')
