"""Add loyalty points transactions and supporting tables

Revision ID: 006d_loyalty_transactions
Revises: 006c_customer_rewards
Create Date: 2024-12-19 15:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006d_loyalty_transactions'
down_revision = '006c_customer_rewards'
branch_labels = None
depends_on = None


def upgrade():
    # Create reward_campaigns table
    op.create_table(
        'reward_campaigns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('template_id', sa.Integer(), nullable=False),
        sa.Column('target_criteria', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('target_tiers', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('target_segments', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=False),
        sa.Column('max_rewards_total', sa.Integer(), nullable=True),
        sa.Column('max_rewards_per_customer', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_automated', sa.Boolean(), nullable=True),
        sa.Column('rewards_distributed', sa.Integer(), nullable=True),
        sa.Column('target_audience_size', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['template_id'], ['reward_templates.id'], ),
    )
    
    # Create indexes for reward_campaigns
    op.create_index('ix_reward_campaigns_name', 'reward_campaigns', ['name'], unique=True)
    op.create_index('ix_reward_campaigns_template_id', 'reward_campaigns', ['template_id'])
    op.create_index('ix_reward_campaigns_is_active', 'reward_campaigns', ['is_active'])
    op.create_index('ix_reward_campaigns_dates', 'reward_campaigns', ['start_date', 'end_date'])
    
    # Create reward_redemptions table
    op.create_table(
        'reward_redemptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reward_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('original_order_amount', sa.Float(), nullable=False),
        sa.Column('discount_applied', sa.Float(), nullable=False),
        sa.Column('final_order_amount', sa.Float(), nullable=False),
        sa.Column('redemption_method', sa.String(length=50), nullable=False),
        sa.Column('pos_terminal_id', sa.String(length=50), nullable=True),
        sa.Column('staff_member_id', sa.Integer(), nullable=True),
        sa.Column('redemption_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['reward_id'], ['customer_rewards_v2.id'], ),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.ForeignKeyConstraint(['staff_member_id'], ['staff_members.id'], ),
    )
    
    # Create indexes for reward_redemptions
    op.create_index('ix_reward_redemptions_reward_id', 'reward_redemptions', ['reward_id'])
    op.create_index('ix_reward_redemptions_customer_id', 'reward_redemptions', ['customer_id'])
    op.create_index('ix_reward_redemptions_order_id', 'reward_redemptions', ['order_id'])
    
    # Create loyalty_points_transactions table
    op.create_table(
        'loyalty_points_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('transaction_type', sa.String(length=50), nullable=False),
        sa.Column('points_change', sa.Integer(), nullable=False),
        sa.Column('points_balance_before', sa.Integer(), nullable=False),
        sa.Column('points_balance_after', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=200), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('reward_id', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('reference_id', sa.String(length=100), nullable=True),
        sa.Column('staff_member_id', sa.Integer(), nullable=True),
        sa.Column('transaction_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_expired', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.ForeignKeyConstraint(['reward_id'], ['customer_rewards_v2.id'], ),
        sa.ForeignKeyConstraint(['staff_member_id'], ['staff_members.id'], ),
    )
    
    # Create indexes for loyalty_points_transactions
    op.create_index('ix_loyalty_points_transactions_customer_id', 'loyalty_points_transactions', ['customer_id'])
    op.create_index('ix_loyalty_points_transactions_transaction_type', 'loyalty_points_transactions', ['transaction_type'])
    op.create_index('ix_loyalty_points_transactions_order_id', 'loyalty_points_transactions', ['order_id'])
    op.create_index('ix_loyalty_points_transactions_customer_type', 'loyalty_points_transactions', ['customer_id', 'transaction_type'])
    op.create_index('ix_loyalty_points_transactions_date', 'loyalty_points_transactions', ['created_at'])
    op.create_index('ix_loyalty_points_transactions_expiry', 'loyalty_points_transactions', ['expires_at', 'is_expired'])


def downgrade():
    op.drop_table('loyalty_points_transactions')
    op.drop_table('reward_redemptions')
    op.drop_table('reward_campaigns')