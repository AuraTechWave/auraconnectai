"""Add reward system enums

Revision ID: 006a_reward_enums
Revises: 005_add_customer_system
Create Date: 2024-12-19 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '006a_reward_enums'
down_revision = '005_add_customer_system'
branch_labels = None
depends_on = None


def upgrade():
    # Create reward type enum
    reward_type_enum = sa.Enum(
        'points_discount', 'percentage_discount', 'fixed_discount', 'free_item',
        'free_delivery', 'bonus_points', 'cashback', 'gift_card', 'tier_upgrade', 'custom',
        name='rewardtype',
        create_type=False
    )
    reward_type_enum.create(op.get_bind(), checkfirst=True)
    
    # Create reward status enum
    reward_status_enum = sa.Enum(
        'available', 'reserved', 'redeemed', 'expired', 'revoked', 'pending',
        name='rewardstatus',
        create_type=False
    )
    reward_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create trigger type enum
    trigger_type_enum = sa.Enum(
        'order_complete', 'points_earned', 'tier_upgrade', 'birthday', 'anniversary',
        'referral_success', 'milestone', 'manual', 'scheduled', 'conditional',
        name='triggertype',
        create_type=False
    )
    trigger_type_enum.create(op.get_bind(), checkfirst=True)


def downgrade():
    # Drop enums
    sa.Enum(name='triggertype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='rewardstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='rewardtype').drop(op.get_bind(), checkfirst=True)