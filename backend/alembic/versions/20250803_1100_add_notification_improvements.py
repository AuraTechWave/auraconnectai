"""Add notification improvements - config tables and indexes

Revision ID: add_notification_improvements
Revises: add_order_tracking_tables
Create Date: 2025-08-03 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_notification_improvements'
down_revision = 'add_order_tracking_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Create enum types for notification config
    op.execute("""
        CREATE TYPE notificationchannelstatus AS ENUM (
            'active', 'inactive', 'maintenance', 'failed'
        )
    """)
    
    op.execute("""
        CREATE TYPE notificationretrystrategy AS ENUM (
            'exponential_backoff', 'linear_backoff', 'fixed_delay', 'no_retry'
        )
    """)

    # Create notification_channel_configs table
    op.create_table(
        'notification_channel_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('channel_name', sa.String(50), nullable=False),
        sa.Column('channel_type', sa.String(20), nullable=False),
        sa.Column('status', postgresql.ENUM('active', 'inactive', 'maintenance', 'failed',
                                           name='notificationchannelstatus', create_type=False), 
                  nullable=False, server_default='active'),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('maintenance_message', sa.Text(), nullable=True),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('retry_strategy', postgresql.ENUM('exponential_backoff', 'linear_backoff', 
                                                    'fixed_delay', 'no_retry',
                                                    name='notificationretrystrategy', create_type=False),
                  nullable=False, server_default='exponential_backoff'),
        sa.Column('max_retry_attempts', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('initial_retry_delay_seconds', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('max_retry_delay_seconds', sa.Integer(), nullable=False, server_default='3600'),
        sa.Column('retry_backoff_multiplier', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('rate_limit_per_minute', sa.Integer(), nullable=True),
        sa.Column('rate_limit_per_hour', sa.Integer(), nullable=True),
        sa.Column('rate_limit_per_day', sa.Integer(), nullable=True),
        sa.Column('priority_threshold', sa.String(20), nullable=True),
        sa.Column('last_health_check', sa.DateTime(), nullable=True),
        sa.Column('health_check_status', sa.String(20), nullable=True),
        sa.Column('health_check_message', sa.Text(), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('auto_disable_after_failures', sa.Integer(), nullable=True, server_default='10'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('channel_name'),
        sa.CheckConstraint('max_retry_attempts >= 0', name='check_max_retry_attempts'),
        sa.CheckConstraint('initial_retry_delay_seconds > 0', name='check_initial_delay'),
        sa.CheckConstraint('retry_backoff_multiplier >= 1', name='check_backoff_multiplier')
    )
    op.create_index('idx_notification_channel_status', 'notification_channel_configs', 
                    ['channel_type', 'status'])

    # Create notification_retry_queue table
    op.create_table(
        'notification_retry_queue',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('notification_id', sa.Integer(), nullable=False),
        sa.Column('channel_name', sa.String(50), nullable=False),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('next_retry_at', sa.DateTime(), nullable=False),
        sa.Column('last_retry_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('recipient', sa.String(), nullable=False),
        sa.Column('subject', sa.String(), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('is_abandoned', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('abandoned_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_retry_queue_next_attempt', 'notification_retry_queue', 
                    ['next_retry_at', 'is_abandoned'])
    op.create_index('idx_retry_queue_notification', 'notification_retry_queue', 
                    ['notification_id', 'channel_name'])

    # Create notification_channel_stats table
    op.create_table(
        'notification_channel_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('channel_name', sa.String(50), nullable=False),
        sa.Column('stat_date', sa.DateTime(), nullable=False),
        sa.Column('stat_hour', sa.Integer(), nullable=False),
        sa.Column('total_sent', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_delivered', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_retried', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_delivery_time_ms', sa.Integer(), nullable=True),
        sa.Column('p95_delivery_time_ms', sa.Integer(), nullable=True),
        sa.Column('p99_delivery_time_ms', sa.Integer(), nullable=True),
        sa.Column('error_breakdown', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('channel_name', 'stat_date', 'stat_hour', name='uq_channel_stats_hour')
    )
    op.create_index('idx_channel_stats_lookup', 'notification_channel_stats', 
                    ['channel_name', 'stat_date'])

    # Add GIN indexes on JSONB columns for efficient queries
    op.execute("""
        CREATE INDEX idx_order_tracking_events_metadata_gin 
        ON order_tracking_events USING GIN (metadata);
    """)
    
    op.execute("""
        CREATE INDEX idx_order_notifications_metadata_gin 
        ON order_notifications USING GIN (metadata);
    """)
    
    op.execute("""
        CREATE INDEX idx_notification_channel_configs_config_gin 
        ON notification_channel_configs USING GIN (config);
    """)
    
    op.execute("""
        CREATE INDEX idx_notification_retry_queue_metadata_gin 
        ON notification_retry_queue USING GIN (metadata);
    """)
    
    op.execute("""
        CREATE INDEX idx_notification_channel_stats_error_gin 
        ON notification_channel_stats USING GIN (error_breakdown);
    """)

    # Insert default channel configurations
    op.execute("""
        INSERT INTO notification_channel_configs (
            channel_name, channel_type, status, is_enabled, config, description, 
            created_at, updated_at
        ) VALUES 
        ('email_primary', 'email', 'active', true, 
         '{"provider": "smtp", "smtp_host": "localhost", "smtp_port": 587, "from_address": "noreply@auraconnect.ai"}'::jsonb,
         'Primary email notification channel', NOW(), NOW()),
         
        ('sms_twilio', 'sms', 'inactive', false,
         '{"provider": "twilio", "account_sid": "", "auth_token": "", "from_number": ""}'::jsonb,
         'Twilio SMS notification channel', NOW(), NOW()),
         
        ('push_firebase', 'push', 'inactive', false,
         '{"provider": "firebase", "fcm_server_key": "", "project_id": ""}'::jsonb,
         'Firebase Cloud Messaging for Android push notifications', NOW(), NOW()),
         
        ('push_apns', 'push', 'inactive', false,
         '{"provider": "apns", "cert_path": "", "key_path": "", "topic": "", "environment": "development"}'::jsonb,
         'Apple Push Notification Service for iOS', NOW(), NOW()),
         
        ('webhook_internal', 'webhook', 'active', true,
         '{"url": "http://localhost:8000/internal/webhook", "timeout_seconds": 30, "retry_on_failure": true}'::jsonb,
         'Internal webhook for system events', NOW(), NOW())
    """)


def downgrade():
    # Drop indexes first
    op.execute("DROP INDEX IF EXISTS idx_notification_channel_stats_error_gin")
    op.execute("DROP INDEX IF EXISTS idx_notification_retry_queue_metadata_gin")
    op.execute("DROP INDEX IF EXISTS idx_notification_channel_configs_config_gin")
    op.execute("DROP INDEX IF EXISTS idx_order_notifications_metadata_gin")
    op.execute("DROP INDEX IF EXISTS idx_order_tracking_events_metadata_gin")
    
    # Drop tables
    op.drop_index('idx_channel_stats_lookup', table_name='notification_channel_stats')
    op.drop_table('notification_channel_stats')
    
    op.drop_index('idx_retry_queue_notification', table_name='notification_retry_queue')
    op.drop_index('idx_retry_queue_next_attempt', table_name='notification_retry_queue')
    op.drop_table('notification_retry_queue')
    
    op.drop_index('idx_notification_channel_status', table_name='notification_channel_configs')
    op.drop_table('notification_channel_configs')
    
    # Drop enum types
    op.execute('DROP TYPE notificationretrystrategy')
    op.execute('DROP TYPE notificationchannelstatus')