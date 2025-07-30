"""Create POS analytics tables

Revision ID: 008_pos_analytics
Revises: 007_external_pos_updates
Create Date: 2025-01-30

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '008_pos_analytics'
down_revision = '007_external_pos_updates'
branch_labels = None
depends_on = None


def upgrade():
    # Create POS analytics snapshot table
    op.create_table('pos_analytics_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('snapshot_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('snapshot_hour', sa.Integer(), nullable=False),
        sa.Column('provider_id', sa.Integer(), nullable=True),
        sa.Column('terminal_id', sa.String(length=100), nullable=True),
        sa.Column('total_transactions', sa.Integer(), nullable=False),
        sa.Column('successful_transactions', sa.Integer(), nullable=False),
        sa.Column('failed_transactions', sa.Integer(), nullable=False),
        sa.Column('total_transaction_value', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('average_transaction_value', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('total_syncs', sa.Integer(), nullable=False),
        sa.Column('successful_syncs', sa.Integer(), nullable=False),
        sa.Column('failed_syncs', sa.Integer(), nullable=False),
        sa.Column('average_sync_time_ms', sa.Float(), nullable=False),
        sa.Column('total_webhooks', sa.Integer(), nullable=False),
        sa.Column('successful_webhooks', sa.Integer(), nullable=False),
        sa.Column('failed_webhooks', sa.Integer(), nullable=False),
        sa.Column('average_webhook_processing_time_ms', sa.Float(), nullable=False),
        sa.Column('total_errors', sa.Integer(), nullable=False),
        sa.Column('error_types', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('uptime_percentage', sa.Float(), nullable=False),
        sa.Column('response_time_p50', sa.Float(), nullable=True),
        sa.Column('response_time_p95', sa.Float(), nullable=True),
        sa.Column('response_time_p99', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['provider_id'], ['external_pos_providers.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('snapshot_date', 'snapshot_hour', 'provider_id', 'terminal_id', 
                          name='uq_pos_snapshot_time_provider_terminal')
    )
    op.create_index('idx_pos_snapshot_date_provider', 'pos_analytics_snapshots', 
                     ['snapshot_date', 'provider_id'], unique=False)
    op.create_index('idx_pos_snapshot_terminal', 'pos_analytics_snapshots', 
                     ['terminal_id', 'snapshot_date'], unique=False)
    op.create_index(op.f('ix_pos_analytics_snapshots_snapshot_id'), 'pos_analytics_snapshots', 
                     ['snapshot_id'], unique=True)
    
    # Create POS provider performance table
    op.create_table('pos_provider_performance',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider_id', sa.Integer(), nullable=False),
        sa.Column('measurement_date', sa.Date(), nullable=False),
        sa.Column('total_terminals', sa.Integer(), nullable=False),
        sa.Column('active_terminals', sa.Integer(), nullable=False),
        sa.Column('daily_transactions', sa.Integer(), nullable=False),
        sa.Column('daily_transaction_value', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('daily_syncs', sa.Integer(), nullable=False),
        sa.Column('daily_webhooks', sa.Integer(), nullable=False),
        sa.Column('daily_errors', sa.Integer(), nullable=False),
        sa.Column('overall_success_rate', sa.Float(), nullable=False),
        sa.Column('sync_success_rate', sa.Float(), nullable=False),
        sa.Column('webhook_success_rate', sa.Float(), nullable=False),
        sa.Column('average_response_time_ms', sa.Float(), nullable=False),
        sa.Column('uptime_percentage', sa.Float(), nullable=False),
        sa.Column('top_error_types', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('problematic_terminals', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['provider_id'], ['external_pos_providers.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider_id', 'measurement_date', 
                          name='uq_provider_performance_date')
    )
    op.create_index('idx_provider_performance_date', 'pos_provider_performance', 
                     ['measurement_date', 'provider_id'], unique=False)
    
    # Create POS terminal health table
    op.create_table('pos_terminal_health',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('terminal_id', sa.String(length=100), nullable=False),
        sa.Column('provider_id', sa.Integer(), nullable=False),
        sa.Column('is_online', sa.Boolean(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False),
        sa.Column('health_status', sa.String(length=50), nullable=False),
        sa.Column('recent_transaction_count', sa.Integer(), nullable=False),
        sa.Column('recent_error_count', sa.Integer(), nullable=False),
        sa.Column('recent_sync_failures', sa.Integer(), nullable=False),
        sa.Column('recent_success_rate', sa.Float(), nullable=False),
        sa.Column('error_threshold_exceeded', sa.Boolean(), nullable=False),
        sa.Column('sync_failure_threshold_exceeded', sa.Boolean(), nullable=False),
        sa.Column('offline_duration_minutes', sa.Integer(), nullable=False),
        sa.Column('terminal_name', sa.String(length=200), nullable=True),
        sa.Column('terminal_location', sa.String(length=500), nullable=True),
        sa.Column('terminal_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['provider_id'], ['external_pos_providers.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('terminal_id', 'provider_id', 
                          name='uq_terminal_health_terminal_provider')
    )
    op.create_index('idx_terminal_health_lastseen', 'pos_terminal_health', 
                     ['last_seen_at'], unique=False)
    op.create_index('idx_terminal_health_status', 'pos_terminal_health', 
                     ['health_status', 'provider_id'], unique=False)
    op.create_index(op.f('ix_pos_terminal_health_terminal_id'), 'pos_terminal_health', 
                     ['terminal_id'], unique=False)
    
    # Create POS analytics alerts table
    op.create_table('pos_analytics_alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alert_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('alert_type', sa.String(length=100), nullable=False),
        sa.Column('severity', sa.String(length=50), nullable=False),
        sa.Column('provider_id', sa.Integer(), nullable=True),
        sa.Column('terminal_id', sa.String(length=100), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.String(length=1000), nullable=False),
        sa.Column('metric_value', sa.Float(), nullable=True),
        sa.Column('threshold_value', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('acknowledged', sa.Boolean(), nullable=False),
        sa.Column('acknowledged_by', sa.Integer(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('context_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('notification_sent', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['acknowledged_by'], ['staff_members.id'], ),
        sa.ForeignKeyConstraint(['provider_id'], ['external_pos_providers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_pos_alert_active', 'pos_analytics_alerts', 
                     ['is_active', 'severity'], unique=False)
    op.create_index('idx_pos_alert_provider_time', 'pos_analytics_alerts', 
                     ['provider_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_pos_analytics_alerts_alert_id'), 'pos_analytics_alerts', 
                     ['alert_id'], unique=True)
    op.create_index(op.f('ix_pos_analytics_alerts_alert_type'), 'pos_analytics_alerts', 
                     ['alert_type'], unique=False)
    op.create_index(op.f('ix_pos_analytics_alerts_severity'), 'pos_analytics_alerts', 
                     ['severity'], unique=False)
    op.create_index(op.f('ix_pos_analytics_alerts_terminal_id'), 'pos_analytics_alerts', 
                     ['terminal_id'], unique=False)


def downgrade():
    # Drop all tables in reverse order
    op.drop_index(op.f('ix_pos_analytics_alerts_terminal_id'), table_name='pos_analytics_alerts')
    op.drop_index(op.f('ix_pos_analytics_alerts_severity'), table_name='pos_analytics_alerts')
    op.drop_index(op.f('ix_pos_analytics_alerts_alert_type'), table_name='pos_analytics_alerts')
    op.drop_index(op.f('ix_pos_analytics_alerts_alert_id'), table_name='pos_analytics_alerts')
    op.drop_index('idx_pos_alert_provider_time', table_name='pos_analytics_alerts')
    op.drop_index('idx_pos_alert_active', table_name='pos_analytics_alerts')
    op.drop_table('pos_analytics_alerts')
    
    op.drop_index(op.f('ix_pos_terminal_health_terminal_id'), table_name='pos_terminal_health')
    op.drop_index('idx_terminal_health_status', table_name='pos_terminal_health')
    op.drop_index('idx_terminal_health_lastseen', table_name='pos_terminal_health')
    op.drop_table('pos_terminal_health')
    
    op.drop_index('idx_provider_performance_date', table_name='pos_provider_performance')
    op.drop_table('pos_provider_performance')
    
    op.drop_index(op.f('ix_pos_analytics_snapshots_snapshot_id'), table_name='pos_analytics_snapshots')
    op.drop_index('idx_pos_snapshot_terminal', table_name='pos_analytics_snapshots')
    op.drop_index('idx_pos_snapshot_date_provider', table_name='pos_analytics_snapshots')
    op.drop_table('pos_analytics_snapshots')