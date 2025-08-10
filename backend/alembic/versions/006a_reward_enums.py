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
    # Get database connection
    connection = op.get_bind()
    
    # Check and create rewardtype enum
    result = connection.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'rewardtype'"
    ))
    if not result.fetchone():
        connection.execute(sa.text("""
            CREATE TYPE rewardtype AS ENUM ('points_discount', 'percentage_discount', 'fixed_discount', 'free_item',
                'free_delivery', 'bonus_points', 'cashback', 'gift_card', 'tier_upgrade', 'custom')
        """))
    
    # Check and create rewardstatus enum
    result = connection.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'rewardstatus'"
    ))
    if not result.fetchone():
        connection.execute(sa.text("""
            CREATE TYPE rewardstatus AS ENUM ('available', 'reserved', 'redeemed', 'expired', 'revoked', 'pending')
        """))
    
    # Check and create triggertype enum
    result = connection.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'triggertype'"
    ))
    if not result.fetchone():
        connection.execute(sa.text("""
            CREATE TYPE triggertype AS ENUM ('order_complete', 'points_earned', 'tier_upgrade', 'birthday', 'anniversary',
                'referral_success', 'milestone', 'manual', 'scheduled', 'conditional')
        """))


def downgrade():
    # Drop enums
    sa.Enum(name='triggertype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='rewardstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='rewardtype').drop(op.get_bind(), checkfirst=True)