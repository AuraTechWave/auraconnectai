"""Add comprehensive rewards engine system

Revision ID: 006_add_rewards_engine
Revises: 005_add_customer_system
Create Date: 2024-12-19 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006_add_rewards_engine'
down_revision = '005_add_customer_system'
branch_labels = None
depends_on = None


def upgrade():
    # Get database connection
    connection = op.get_bind()
    
    # Check and create triggertype enum using DO block
    connection.execute(sa.text("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type t
                JOIN pg_namespace n ON t.typnamespace = n.oid
                WHERE t.typname = 'triggertype'
                AND n.nspname = current_schema()
                AND t.typtype = 'e'
            ) THEN
                CREATE TYPE triggertype AS ENUM ('order_complete', 'points_earned', 'tier_upgrade', 'birthday', 'anniversary', 'referral_success', 'milestone', 'manual', 'scheduled', 'conditional');
            END IF;
        END$$;
    """))
    
    # Create reward_templates table
    op.create_table(
        'reward_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('reward_type', sa.Enum('points_discount', 'percentage_discount', 'fixed_discount', 'free_item', 'free_delivery', 'bonus_points', 'cashback', 'gift_card', 'tier_upgrade', 'custom', name='rewardtype', create_type=False), nullable=False),
        sa.Column('value', sa.Float(), nullable=True),
        sa.Column('percentage', sa.Float(), nullable=True),
        sa.Column('points_cost', sa.Integer(), nullable=True),
        sa.Column('item_id', sa.Integer(), nullable=True),
        sa.Column('category_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('min_order_amount', sa.Float(), nullable=True),
        sa.Column('max_discount_amount', sa.Float(), nullable=True),
        sa.Column('max_uses_per_customer', sa.Integer(), nullable=True),
        sa.Column('max_uses_total', sa.Integer(), nullable=True),
        sa.Column('valid_days', sa.Integer(), nullable=False),
        sa.Column('valid_from_date', sa.DateTime(), nullable=True),
        sa.Column('valid_until_date', sa.DateTime(), nullable=True),
        sa.Column('eligible_tiers', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('trigger_type', sa.Enum('order_complete', 'points_earned', 'tier_upgrade', 'birthday', 'anniversary', 'referral_success', 'milestone', 'manual', 'scheduled', 'conditional', name='triggertype', create_type=False), nullable=False),
        sa.Column('trigger_conditions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('auto_apply', sa.Boolean(), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('subtitle', sa.String(length=300), nullable=True),
        sa.Column('terms_and_conditions', sa.Text(), nullable=True),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('icon', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_featured', sa.Boolean(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('total_issued', sa.Integer(), nullable=True),
        sa.Column('total_redeemed', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('valid_days > 0', name='valid_days_positive'),
        sa.CheckConstraint('points_cost >= 0 OR points_cost IS NULL', name='points_cost_non_negative'),
        sa.CheckConstraint('value >= 0 OR value IS NULL', name='value_non_negative'),
        sa.CheckConstraint('percentage >= 0 AND percentage <= 100 OR percentage IS NULL', name='percentage_valid_range'),
    )
    
    # Create indexes for reward_templates
    op.create_index('ix_reward_templates_name', 'reward_templates', ['name'], unique=True)
    op.create_index('ix_reward_templates_reward_type', 'reward_templates', ['reward_type'])
    op.create_index('ix_reward_templates_trigger_type', 'reward_templates', ['trigger_type'])
    op.create_index('ix_reward_templates_is_active', 'reward_templates', ['is_active'])
    op.create_index('ix_reward_templates_type_active', 'reward_templates', ['reward_type', 'is_active'])
    op.create_index('ix_reward_templates_trigger', 'reward_templates', ['trigger_type', 'is_active'])
    
    # Create customer_rewards_v2 table
    op.create_table(
        'customer_rewards_v2',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=False),
        sa.Column('reward_type', sa.Enum('points_discount', 'percentage_discount', 'fixed_discount', 'free_item', 'free_delivery', 'bonus_points', 'cashback', 'gift_card', 'tier_upgrade', 'custom', name='rewardtype', create_type=False), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('value', sa.Float(), nullable=True),
        sa.Column('percentage', sa.Float(), nullable=True),
        sa.Column('points_cost', sa.Integer(), nullable=True),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('status', sa.Enum('available', 'reserved', 'redeemed', 'expired', 'revoked', 'pending', name='rewardstatus', create_type=False), nullable=False),
        sa.Column('reserved_at', sa.DateTime(), nullable=True),
        sa.Column('reserved_until', sa.DateTime(), nullable=True),
        sa.Column('redeemed_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_reason', sa.String(length=500), nullable=True),
        sa.Column('valid_from', sa.DateTime(), nullable=False),
        sa.Column('valid_until', sa.DateTime(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('redeemed_amount', sa.Float(), nullable=True),
        sa.Column('issued_by', sa.Integer(), nullable=True),
        sa.Column('trigger_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['template_id'], ['reward_templates.id'], ),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.ForeignKeyConstraint(['issued_by'], ['rbac_users.id'], ),
    )
    
    # Create indexes for customer_rewards_v2
    op.create_index('ix_customer_rewards_v2_customer_id', 'customer_rewards_v2', ['customer_id'])
    op.create_index('ix_customer_rewards_v2_template_id', 'customer_rewards_v2', ['template_id'])
    op.create_index('ix_customer_rewards_v2_code', 'customer_rewards_v2', ['code'], unique=True)
    op.create_index('ix_customer_rewards_v2_status', 'customer_rewards_v2', ['status'])
    op.create_index('ix_customer_rewards_v2_order_id', 'customer_rewards_v2', ['order_id'])
    op.create_index('ix_customer_rewards_v2_customer_status', 'customer_rewards_v2', ['customer_id', 'status'])
    op.create_index('ix_customer_rewards_v2_validity', 'customer_rewards_v2', ['valid_from', 'valid_until'])
    op.create_index('ix_customer_rewards_v2_expiry', 'customer_rewards_v2', ['valid_until', 'status'])
    
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
    
    # Set default values for new columns
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
    # Drop all reward system tables in reverse order
    op.drop_table('reward_analytics')
    op.drop_table('loyalty_points_transactions')
    op.drop_table('reward_redemptions')
    op.drop_table('reward_campaigns')
    op.drop_table('customer_rewards_v2')
    op.drop_table('reward_templates')
    
    # Drop enums
    sa.Enum(name='triggertype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='rewardstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='rewardtype').drop(op.get_bind(), checkfirst=True)