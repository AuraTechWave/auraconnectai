"""Add reward analytics table and set defaults

Revision ID: 006e_reward_analytics
Revises: 006d_loyalty_transactions
Create Date: 2024-12-19 15:20:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '006e_reward_analytics'
down_revision = '006d_loyalty_transactions'
branch_labels = None
depends_on = None


def upgrade():
    # Create reward_analytics table
    op.create_table(
        'reward_analytics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('period_type', sa.String(length=20), nullable=False),
        sa.Column('rewards_issued', sa.Integer(), nullable=True),
        sa.Column('rewards_redeemed', sa.Integer(), nullable=True),
        sa.Column('rewards_expired', sa.Integer(), nullable=True),
        sa.Column('total_discount_value', sa.Float(), nullable=True),
        sa.Column('unique_customers', sa.Integer(), nullable=True),
        sa.Column('redemption_rate', sa.Float(), nullable=True),
        sa.Column('avg_redemption_days', sa.Float(), nullable=True),
        sa.Column('customer_satisfaction_score', sa.Float(), nullable=True),
        sa.Column('revenue_impact', sa.Float(), nullable=True),
        sa.Column('customer_retention_impact', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['template_id'], ['reward_templates.id'], ),
    )
    
    # Create indexes for reward_analytics
    op.create_index('ix_reward_analytics_template_id', 'reward_analytics', ['template_id'])
    op.create_index('ix_reward_analytics_template_period', 'reward_analytics', ['template_id', 'period_start', 'period_end'], unique=True)
    
    # Set default values for existing tables
    op.execute("UPDATE reward_templates SET auto_apply = false WHERE auto_apply IS NULL")
    op.execute("UPDATE reward_templates SET is_active = true WHERE is_active IS NULL")
    op.execute("UPDATE reward_templates SET is_featured = false WHERE is_featured IS NULL")
    op.execute("UPDATE reward_templates SET priority = 0 WHERE priority IS NULL")
    op.execute("UPDATE reward_templates SET total_issued = 0 WHERE total_issued IS NULL")
    op.execute("UPDATE reward_templates SET total_redeemed = 0 WHERE total_redeemed IS NULL")
    op.execute("UPDATE reward_templates SET valid_days = 30 WHERE valid_days IS NULL")
    op.execute("UPDATE reward_templates SET created_at = NOW() WHERE created_at IS NULL")
    op.execute("UPDATE reward_templates SET updated_at = NOW() WHERE updated_at IS NULL")
    
    op.execute("UPDATE customer_rewards_v2 SET status = 'available' WHERE status IS NULL")
    op.execute("UPDATE customer_rewards_v2 SET valid_from = NOW() WHERE valid_from IS NULL")
    op.execute("UPDATE customer_rewards_v2 SET created_at = NOW() WHERE created_at IS NULL")
    op.execute("UPDATE customer_rewards_v2 SET updated_at = NOW() WHERE updated_at IS NULL")
    
    op.execute("UPDATE reward_campaigns SET max_rewards_per_customer = 1 WHERE max_rewards_per_customer IS NULL")
    op.execute("UPDATE reward_campaigns SET is_active = true WHERE is_active IS NULL")
    op.execute("UPDATE reward_campaigns SET is_automated = false WHERE is_automated IS NULL")
    op.execute("UPDATE reward_campaigns SET rewards_distributed = 0 WHERE rewards_distributed IS NULL")
    op.execute("UPDATE reward_campaigns SET created_at = NOW() WHERE created_at IS NULL")
    op.execute("UPDATE reward_campaigns SET updated_at = NOW() WHERE updated_at IS NULL")
    
    op.execute("UPDATE reward_redemptions SET redemption_method = 'manual' WHERE redemption_method IS NULL")
    op.execute("UPDATE reward_redemptions SET created_at = NOW() WHERE created_at IS NULL")
    op.execute("UPDATE reward_redemptions SET updated_at = NOW() WHERE updated_at IS NULL")
    
    op.execute("UPDATE loyalty_points_transactions SET source = 'system' WHERE source IS NULL")
    op.execute("UPDATE loyalty_points_transactions SET is_expired = false WHERE is_expired IS NULL")
    op.execute("UPDATE loyalty_points_transactions SET created_at = NOW() WHERE created_at IS NULL")
    op.execute("UPDATE loyalty_points_transactions SET updated_at = NOW() WHERE updated_at IS NULL")
    
    op.execute("UPDATE reward_analytics SET period_type = 'daily' WHERE period_type IS NULL")
    op.execute("UPDATE reward_analytics SET rewards_issued = 0 WHERE rewards_issued IS NULL")
    op.execute("UPDATE reward_analytics SET rewards_redeemed = 0 WHERE rewards_redeemed IS NULL")
    op.execute("UPDATE reward_analytics SET rewards_expired = 0 WHERE rewards_expired IS NULL")
    op.execute("UPDATE reward_analytics SET total_discount_value = 0.0 WHERE total_discount_value IS NULL")
    op.execute("UPDATE reward_analytics SET unique_customers = 0 WHERE unique_customers IS NULL")
    op.execute("UPDATE reward_analytics SET redemption_rate = 0.0 WHERE redemption_rate IS NULL")
    op.execute("UPDATE reward_analytics SET avg_redemption_days = 0.0 WHERE avg_redemption_days IS NULL")
    op.execute("UPDATE reward_analytics SET revenue_impact = 0.0 WHERE revenue_impact IS NULL")
    op.execute("UPDATE reward_analytics SET created_at = NOW() WHERE created_at IS NULL")
    op.execute("UPDATE reward_analytics SET updated_at = NOW() WHERE updated_at IS NULL")


def downgrade():
    op.drop_table('reward_analytics')