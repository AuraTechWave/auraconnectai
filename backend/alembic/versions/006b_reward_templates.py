"""Add reward templates table

Revision ID: 006b_reward_templates
Revises: 006a_reward_enums
Create Date: 2024-12-19 15:05:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006b_reward_templates'
down_revision = '006a_reward_enums'
branch_labels = None
depends_on = None


def upgrade():
    
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


def downgrade():
    op.drop_table('reward_templates')