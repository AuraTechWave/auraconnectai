"""Add health monitoring tables

Revision ID: add_health_monitoring_tables
Revises: add_settings_ui_enhancements
Create Date: 2025-01-18 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_health_monitoring_tables'
down_revision = 'add_settings_ui_enhancements'
branch_labels = None
depends_on = None


def upgrade():
    """Add health monitoring tables"""
    
    # Create health_metrics table
    op.create_table('health_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('metric_name', sa.String(length=100), nullable=False),
        sa.Column('metric_type', sa.String(length=50), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_health_metrics_name_created', 'health_metrics', ['metric_name', 'created_at'])
    op.create_index('idx_health_metrics_type', 'health_metrics', ['metric_type'])
    
    # Create system_health table
    op.create_table('system_health',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('component', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('response_time_ms', sa.Float(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('last_checked', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_system_health_component', 'system_health', ['component'])
    op.create_index('idx_system_health_status', 'system_health', ['status'])
    
    # Create error_logs table
    op.create_table('error_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('error_type', sa.String(length=100), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('stack_trace', sa.Text(), nullable=True),
        sa.Column('endpoint', sa.String(length=200), nullable=True),
        sa.Column('method', sa.String(length=10), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('restaurant_id', sa.Integer(), nullable=True),
        sa.Column('request_id', sa.String(length=100), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('resolved', sa.Boolean(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_error_logs_created', 'error_logs', ['created_at'])
    op.create_index('idx_error_logs_type', 'error_logs', ['error_type'])
    op.create_index('idx_error_logs_endpoint', 'error_logs', ['endpoint'])
    op.create_index('idx_error_logs_resolved', 'error_logs', ['resolved'])
    
    # Create performance_metrics table
    op.create_table('performance_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('endpoint', sa.String(length=200), nullable=False),
        sa.Column('method', sa.String(length=10), nullable=False),
        sa.Column('response_time_ms', sa.Float(), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('request_size_bytes', sa.Integer(), nullable=True),
        sa.Column('response_size_bytes', sa.Integer(), nullable=True),
        sa.Column('cpu_usage_percent', sa.Float(), nullable=True),
        sa.Column('memory_usage_mb', sa.Float(), nullable=True),
        sa.Column('db_query_count', sa.Integer(), nullable=True),
        sa.Column('db_query_time_ms', sa.Float(), nullable=True),
        sa.Column('cache_hits', sa.Integer(), nullable=True),
        sa.Column('cache_misses', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('restaurant_id', sa.Integer(), nullable=True),
        sa.Column('request_id', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_performance_endpoint_created', 'performance_metrics', ['endpoint', 'created_at'])
    op.create_index('idx_performance_method', 'performance_metrics', ['method'])
    op.create_index('idx_performance_status', 'performance_metrics', ['status_code'])
    
    # Create alerts table
    op.create_table('alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('component', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('threshold_value', sa.Float(), nullable=True),
        sa.Column('actual_value', sa.Float(), nullable=True),
        sa.Column('triggered_at', sa.DateTime(), nullable=False),
        sa.Column('acknowledged', sa.Boolean(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('acknowledged_by', sa.Integer(), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_alerts_type_triggered', 'alerts', ['alert_type', 'triggered_at'])
    op.create_index('idx_alerts_severity', 'alerts', ['severity'])
    op.create_index('idx_alerts_acknowledged', 'alerts', ['acknowledged'])
    op.create_index('idx_alerts_resolved', 'alerts', ['resolved'])


def downgrade():
    """Remove health monitoring tables"""
    
    # Drop indexes and tables in reverse order
    op.drop_index('idx_alerts_resolved', 'alerts')
    op.drop_index('idx_alerts_acknowledged', 'alerts')
    op.drop_index('idx_alerts_severity', 'alerts')
    op.drop_index('idx_alerts_type_triggered', 'alerts')
    op.drop_table('alerts')
    
    op.drop_index('idx_performance_status', 'performance_metrics')
    op.drop_index('idx_performance_method', 'performance_metrics')
    op.drop_index('idx_performance_endpoint_created', 'performance_metrics')
    op.drop_table('performance_metrics')
    
    op.drop_index('idx_error_logs_resolved', 'error_logs')
    op.drop_index('idx_error_logs_endpoint', 'error_logs')
    op.drop_index('idx_error_logs_type', 'error_logs')
    op.drop_index('idx_error_logs_created', 'error_logs')
    op.drop_table('error_logs')
    
    op.drop_index('idx_system_health_status', 'system_health')
    op.drop_index('idx_system_health_component', 'system_health')
    op.drop_table('system_health')
    
    op.drop_index('idx_health_metrics_type', 'health_metrics')
    op.drop_index('idx_health_metrics_name_created', 'health_metrics')
    op.drop_table('health_metrics')