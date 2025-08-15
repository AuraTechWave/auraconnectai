"""Add scheduled_at column to sms_messages table

Revision ID: add_scheduled_at_column
Revises: add_sms_notification_tables
Create Date: 2025-08-15 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_scheduled_at_column'
down_revision = 'add_sms_notification_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Add scheduled_at column to sms_messages table
    op.add_column('sms_messages', 
        sa.Column('scheduled_at', sa.DateTime(), nullable=True)
    )
    
    # Create index for scheduled message queries
    op.create_index('idx_sms_messages_scheduled_at', 'sms_messages', ['scheduled_at'])
    
    # Migrate existing scheduled data from metadata JSON to scheduled_at column
    # This handles any existing scheduled messages that might be in the metadata field
    op.execute("""
        UPDATE sms_messages 
        SET scheduled_at = CAST(metadata->>'scheduled_at' AS timestamp)
        WHERE metadata ? 'scheduled_at' 
        AND metadata->>'scheduled_at' IS NOT NULL
        AND metadata->>'scheduled_at' != '';
    """)


def downgrade():
    # Migrate scheduled_at data back to metadata before dropping column
    op.execute("""
        UPDATE sms_messages 
        SET metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('scheduled_at', scheduled_at::text)
        WHERE scheduled_at IS NOT NULL;
    """)
    
    # Drop index and column
    op.drop_index('idx_sms_messages_scheduled_at', table_name='sms_messages')
    op.drop_column('sms_messages', 'scheduled_at')