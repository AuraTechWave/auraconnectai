"""Add order sync tables

Revision ID: 20250730_1000_add_order_sync_tables
Revises: 20250729_1900_add_feedback_and_reviews_tables
Create Date: 2025-07-30 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250730_1000_add_order_sync_tables'
down_revision = '20250729_1900_add_feedback_and_reviews_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Create sync status enum
    sync_status_enum = postgresql.ENUM(
        'pending', 'in_progress', 'synced', 'failed', 'conflict', 'retry',
        name='sync_status',
        create_type=True
    )
    
    sync_direction_enum = postgresql.ENUM(
        'local_to_remote', 'remote_to_local', 'bidirectional',
        name='sync_direction',
        create_type=True
    )
    
    # Create order_sync_status table
    op.create_table(
        'order_sync_status',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('sync_status', sync_status_enum, nullable=False, server_default='pending'),
        sa.Column('sync_direction', sync_direction_enum, nullable=False, server_default='local_to_remote'),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_attempt_at', sa.DateTime(), nullable=True),
        sa.Column('next_retry_at', sa.DateTime(), nullable=True),
        sa.Column('synced_at', sa.DateTime(), nullable=True),
        sa.Column('sync_duration_ms', sa.Integer(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('conflict_detected_at', sa.DateTime(), nullable=True),
        sa.Column('conflict_resolution', sa.String(50), nullable=True),
        sa.Column('conflict_data', postgresql.JSONB(), nullable=True),
        sa.Column('remote_id', sa.String(255), nullable=True),
        sa.Column('remote_system', sa.String(50), nullable=True),
        sa.Column('remote_version', sa.Integer(), nullable=True),
        sa.Column('local_checksum', sa.String(64), nullable=True),
        sa.Column('remote_checksum', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.UniqueConstraint('order_id', name='uq_order_sync_status')
    )
    op.create_index('idx_sync_status_pending', 'order_sync_status', ['sync_status', 'next_retry_at'])
    op.create_index('idx_sync_status_order', 'order_sync_status', ['order_id', 'sync_status'])
    op.create_index('idx_order_sync_status_order_id', 'order_sync_status', ['order_id'])
    op.create_index('idx_order_sync_status_remote_id', 'order_sync_status', ['remote_id'])
    op.create_index('idx_order_sync_status_sync_status', 'order_sync_status', ['sync_status'])
    op.create_index('idx_order_sync_status_next_retry_at', 'order_sync_status', ['next_retry_at'])
    
    # Create sync_batches table
    op.create_table(
        'sync_batches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('batch_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('batch_type', sa.String(50), nullable=False),
        sa.Column('batch_size', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('started_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('total_orders', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('successful_syncs', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_syncs', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('conflict_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_sync_time_ms', sa.Numeric(10, 2), nullable=True),
        sa.Column('max_sync_time_ms', sa.Integer(), nullable=True),
        sa.Column('min_sync_time_ms', sa.Integer(), nullable=True),
        sa.Column('error_summary', postgresql.JSONB(), nullable=True),
        sa.Column('initiated_by', sa.String(50), nullable=True),
        sa.Column('pos_terminal_id', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_sync_batches_batch_id', 'sync_batches', ['batch_id'], unique=True)
    
    # Create sync_logs table
    op.create_table(
        'sync_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=True),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('operation', sa.String(50), nullable=False),
        sa.Column('sync_direction', sync_direction_enum, nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('data_before', postgresql.JSONB(), nullable=True),
        sa.Column('data_after', postgresql.JSONB(), nullable=True),
        sa.Column('changes_made', postgresql.JSONB(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('error_details', postgresql.JSONB(), nullable=True),
        sa.Column('remote_response', postgresql.JSONB(), nullable=True),
        sa.Column('http_status_code', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['batch_id'], ['sync_batches.id'], ),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], )
    )
    op.create_index('idx_sync_log_batch_status', 'sync_logs', ['batch_id', 'status'])
    op.create_index('idx_sync_log_order_time', 'sync_logs', ['order_id', 'started_at'])
    op.create_index('idx_sync_logs_batch_id', 'sync_logs', ['batch_id'])
    op.create_index('idx_sync_logs_order_id', 'sync_logs', ['order_id'])
    
    # Create sync_configurations table
    op.create_table(
        'sync_configurations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('config_key', sa.String(100), nullable=False),
        sa.Column('config_value', postgresql.JSONB(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['updated_by'], ['staff_members.id'], )
    )
    op.create_index('idx_sync_configurations_config_key', 'sync_configurations', ['config_key'], unique=True)
    
    # Create sync_conflicts table
    op.create_table(
        'sync_conflicts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('conflict_type', sa.String(50), nullable=False),
        sa.Column('detected_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('local_data', postgresql.JSONB(), nullable=False),
        sa.Column('remote_data', postgresql.JSONB(), nullable=False),
        sa.Column('differences', postgresql.JSONB(), nullable=True),
        sa.Column('resolution_status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('resolution_method', sa.String(50), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by', sa.Integer(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('final_data', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.ForeignKeyConstraint(['resolved_by'], ['staff_members.id'], )
    )
    op.create_index('idx_conflict_status', 'sync_conflicts', ['resolution_status', 'detected_at'])
    op.create_index('idx_conflict_order', 'sync_conflicts', ['order_id', 'resolution_status'])
    op.create_index('idx_sync_conflicts_order_id', 'sync_conflicts', ['order_id'])
    
    # Add sync columns to orders table
    op.add_column('orders', sa.Column('is_synced', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('orders', sa.Column('last_sync_at', sa.DateTime(), nullable=True))
    op.add_column('orders', sa.Column('sync_version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('orders', sa.Column('offline_created', sa.Boolean(), nullable=False, server_default='false'))
    
    # Create indexes on order sync columns
    op.create_index('idx_orders_is_synced', 'orders', ['is_synced'])
    
    # Insert default sync configurations
    op.execute("""
        INSERT INTO sync_configurations (config_key, config_value, description) VALUES
        ('sync_enabled', 'true', 'Enable or disable automatic order synchronization'),
        ('sync_interval_minutes', '10', 'Interval in minutes between automatic sync runs'),
        ('max_retry_attempts', '3', 'Maximum number of retry attempts for failed syncs'),
        ('retry_backoff_multiplier', '2', 'Exponential backoff multiplier for retries'),
        ('batch_size', '50', 'Number of orders to sync in each batch'),
        ('conflict_resolution_mode', '"manual"', 'How to handle sync conflicts (auto or manual)'),
        ('conflict_resolution_strategy', '"local_wins"', 'Default strategy for auto conflict resolution'),
        ('sync_log_retention_days', '30', 'Number of days to retain sync logs')
    """)


def downgrade():
    # Drop indexes on orders table
    op.drop_index('idx_orders_is_synced', 'orders')
    
    # Remove sync columns from orders table
    op.drop_column('orders', 'offline_created')
    op.drop_column('orders', 'sync_version')
    op.drop_column('orders', 'last_sync_at')
    op.drop_column('orders', 'is_synced')
    
    # Drop tables
    op.drop_table('sync_conflicts')
    op.drop_table('sync_configurations')
    op.drop_table('sync_logs')
    op.drop_table('sync_batches')
    op.drop_table('order_sync_status')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS sync_status')
    op.execute('DROP TYPE IF EXISTS sync_direction')