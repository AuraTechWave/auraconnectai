"""Add customer rewards table

Revision ID: 006c_customer_rewards
Revises: 006b_reward_templates
Create Date: 2024-12-19 15:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006c_customer_rewards'
down_revision = '006b_reward_templates'
branch_labels = None
depends_on = None


def upgrade():
    # Get enum types
    reward_type_enum = sa.Enum(name='rewardtype')
    reward_status_enum = sa.Enum(name='rewardstatus')
    
    # Create customer_rewards_v2 table
    op.create_table(
        'customer_rewards_v2',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=False),
        sa.Column('reward_type', reward_type_enum, nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('value', sa.Float(), nullable=True),
        sa.Column('percentage', sa.Float(), nullable=True),
        sa.Column('points_cost', sa.Integer(), nullable=True),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('status', reward_status_enum, nullable=False),
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


def downgrade():
    op.drop_table('customer_rewards_v2')