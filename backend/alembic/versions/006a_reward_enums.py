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


def downgrade():
    # Drop enums
    sa.Enum(name='triggertype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='rewardstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='rewardtype').drop(op.get_bind(), checkfirst=True)