# backend/modules/orders/migrations/add_order_discount_fields.py

"""Add discount fields to orders table

Revision ID: add_order_discount_fields
Revises: 
Create Date: 2024-07-29 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = 'add_order_discount_fields'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add discount-related fields to orders table"""
    
    # Add discount fields to orders table
    op.add_column('orders', sa.Column('subtotal', sa.Numeric(10, 2), nullable=True))
    op.add_column('orders', sa.Column('discount_amount', sa.Numeric(10, 2), nullable=True, default=0.0))
    op.add_column('orders', sa.Column('tax_amount', sa.Numeric(10, 2), nullable=True, default=0.0))
    op.add_column('orders', sa.Column('total_amount', sa.Numeric(10, 2), nullable=True))
    op.add_column('orders', sa.Column('final_amount', sa.Numeric(10, 2), nullable=True))
    
    # Add promotion tracking fields
    op.add_column('orders', sa.Column('promotions_applied', JSONB, nullable=True))
    op.add_column('orders', sa.Column('coupons_used', JSONB, nullable=True))
    op.add_column('orders', sa.Column('discount_breakdown', JSONB, nullable=True))
    
    # Add referral tracking
    op.add_column('orders', sa.Column('referral_code_used', sa.String(50), nullable=True))
    op.add_column('orders', sa.Column('is_referral_qualifying', sa.Boolean, nullable=True, default=False))
    
    # Create index on referral code for faster lookups
    op.create_index('idx_orders_referral_code', 'orders', ['referral_code_used'])
    
    # Add index on discount amount for analytics
    op.create_index('idx_orders_discount_amount', 'orders', ['discount_amount'])


def downgrade():
    """Remove discount-related fields from orders table"""
    
    # Drop indexes
    op.drop_index('idx_orders_discount_amount')
    op.drop_index('idx_orders_referral_code')
    
    # Remove columns
    op.drop_column('orders', 'is_referral_qualifying')
    op.drop_column('orders', 'referral_code_used')
    op.drop_column('orders', 'discount_breakdown')
    op.drop_column('orders', 'coupons_used')
    op.drop_column('orders', 'promotions_applied')
    op.drop_column('orders', 'final_amount')
    op.drop_column('orders', 'total_amount')
    op.drop_column('orders', 'tax_amount')
    op.drop_column('orders', 'discount_amount')
    op.drop_column('orders', 'subtotal')