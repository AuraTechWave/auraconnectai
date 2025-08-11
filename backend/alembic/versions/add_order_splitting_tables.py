"""add order splitting tables

Revision ID: add_order_splitting
Revises: 
Create Date: 2025-01-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_order_splitting'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create order_splits table
    op.create_table('order_splits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('parent_order_id', sa.Integer(), nullable=False),
        sa.Column('split_order_id', sa.Integer(), nullable=False),
        sa.Column('split_type', sa.String(), nullable=False),
        sa.Column('split_reason', sa.Text(), nullable=True),
        sa.Column('split_by', sa.Integer(), nullable=False),
        sa.Column('split_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['parent_order_id'], ['orders.id'], ),
        sa.ForeignKeyConstraint(['split_order_id'], ['orders.id'], ),
        sa.ForeignKeyConstraint(['split_by'], ['staff_members.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for order_splits
    op.create_index('idx_order_split_parent', 'order_splits', ['parent_order_id'], unique=False)
    op.create_index('idx_order_split_child', 'order_splits', ['split_order_id'], unique=False)
    op.create_index(op.f('ix_order_splits_id'), 'order_splits', ['id'], unique=False)
    
    # Create split_payments table
    op.create_table('split_payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('parent_order_id', sa.Integer(), nullable=False),
        sa.Column('split_order_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('payment_method', sa.String(), nullable=True),
        sa.Column('payment_status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('payment_reference', sa.String(), nullable=True),
        sa.Column('paid_by_customer_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['parent_order_id'], ['orders.id'], ),
        sa.ForeignKeyConstraint(['split_order_id'], ['orders.id'], ),
        sa.ForeignKeyConstraint(['paid_by_customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for split_payments
    op.create_index('idx_split_payment_parent', 'split_payments', ['parent_order_id'], unique=False)
    op.create_index('idx_split_payment_split', 'split_payments', ['split_order_id'], unique=False)
    op.create_index(op.f('ix_split_payments_id'), 'split_payments', ['id'], unique=False)
    op.create_index(op.f('ix_split_payments_payment_status'), 'split_payments', ['payment_status'], unique=False)
    
    # Add check constraint for split types
    op.create_check_constraint(
        'ck_order_splits_split_type',
        'order_splits',
        sa.sql.expression.text("split_type IN ('ticket', 'delivery', 'payment')")
    )
    
    # Add check constraint for payment status
    op.create_check_constraint(
        'ck_split_payments_payment_status',
        'split_payments',
        sa.sql.expression.text("payment_status IN ('pending', 'paid', 'partial', 'failed', 'refunded')")
    )


def downgrade() -> None:
    # Drop check constraints
    op.drop_constraint('ck_split_payments_payment_status', 'split_payments', type_='check')
    op.drop_constraint('ck_order_splits_split_type', 'order_splits', type_='check')
    
    # Drop indexes
    op.drop_index(op.f('ix_split_payments_payment_status'), table_name='split_payments')
    op.drop_index(op.f('ix_split_payments_id'), table_name='split_payments')
    op.drop_index('idx_split_payment_split', table_name='split_payments')
    op.drop_index('idx_split_payment_parent', table_name='split_payments')
    
    op.drop_index(op.f('ix_order_splits_id'), table_name='order_splits')
    op.drop_index('idx_order_split_child', table_name='order_splits')
    op.drop_index('idx_order_split_parent', table_name='order_splits')
    
    # Drop tables
    op.drop_table('split_payments')
    op.drop_table('order_splits')