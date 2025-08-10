"""Add menu sync tables

Revision ID: 004_add_menu_sync_tables
Revises: 003
Create Date: 2023-12-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004_add_menu_sync_tables'
down_revision = '87855e9897a9'
branch_labels = None
depends_on = None


def upgrade():
    # Create enum types with existence checks
    connection = op.get_bind()
    
    # Check and create syncdirection enum
    result = connection.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'syncdirection'"
    ))
    if not result.fetchone():
        connection.execute(sa.text("""
            CREATE TYPE syncdirection AS ENUM ('push', 'pull', 'bidirectional')
        """))
    
    # Check and create syncstatus enum
    result = connection.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'syncstatus'"
    ))
    if not result.fetchone():
        connection.execute(sa.text("""
            CREATE TYPE syncstatus AS ENUM ('pending', 'in_progress', 'success', 'error', 'conflict', 'cancelled')
        """))
    
    # Check and create conflictresolution enum
    result = connection.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'conflictresolution'"
    ))
    if not result.fetchone():
        connection.execute(sa.text("""
            CREATE TYPE conflictresolution AS ENUM ('manual', 'pos_wins', 'aura_wins', 'latest_wins')
        """))

    # POS Menu Mappings table
    op.create_table('pos_menu_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pos_integration_id', sa.Integer(), nullable=False),
        sa.Column('pos_vendor', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('aura_entity_id', sa.Integer(), nullable=False),
        sa.Column('pos_entity_id', sa.String(length=255), nullable=False),
        sa.Column('pos_entity_data', sa.JSON(), nullable=True),
        sa.Column('sync_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('sync_direction', postgresql.ENUM('push', 'pull', 'bidirectional', name='syncdirection', create_type=False), nullable=False, default='bidirectional'),
        sa.Column('conflict_resolution', postgresql.ENUM('manual', 'pos_wins', 'aura_wins', 'latest_wins', name='conflictresolution', create_type=False), nullable=False, default='manual'),
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.Column('last_sync_direction', postgresql.ENUM('push', 'pull', 'bidirectional', name='syncdirection', create_type=False), nullable=True),
        sa.Column('aura_last_modified', sa.DateTime(), nullable=True),
        sa.Column('pos_last_modified', sa.DateTime(), nullable=True),
        sa.Column('sync_hash', sa.String(length=64), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['pos_integration_id'], ['pos_integrations.id'], ),
    )
    
    # Create indexes for pos_menu_mappings
    op.create_index('ix_pos_menu_mappings_entity', 'pos_menu_mappings', ['entity_type', 'aura_entity_id'])
    op.create_index('ix_pos_menu_mappings_pos_entity', 'pos_menu_mappings', ['pos_vendor', 'pos_entity_id'])
    op.create_index('ix_pos_menu_mappings_sync_status', 'pos_menu_mappings', ['sync_enabled', 'is_active'])
    op.create_index('ix_pos_menu_mappings_id', 'pos_menu_mappings', ['id'])

    # Menu Sync Jobs table
    op.create_table('menu_sync_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column('pos_integration_id', sa.Integer(), nullable=False),
        sa.Column('sync_direction', postgresql.ENUM('push', 'pull', 'bidirectional', name='syncdirection', create_type=False), nullable=False),
        sa.Column('entity_types', sa.JSON(), nullable=True),
        sa.Column('entity_ids', sa.JSON(), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'in_progress', 'success', 'error', 'conflict', 'cancelled', name='syncstatus', create_type=False), nullable=False, default='pending'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(), nullable=True),
        sa.Column('total_entities', sa.Integer(), nullable=False, default=0),
        sa.Column('processed_entities', sa.Integer(), nullable=False, default=0),
        sa.Column('successful_entities', sa.Integer(), nullable=False, default=0),
        sa.Column('failed_entities', sa.Integer(), nullable=False, default=0),
        sa.Column('conflicts_detected', sa.Integer(), nullable=False, default=0),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', sa.JSON(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, default=0),
        sa.Column('max_retries', sa.Integer(), nullable=False, default=3),
        sa.Column('triggered_by', sa.String(length=50), nullable=True),
        sa.Column('triggered_by_id', sa.Integer(), nullable=True),
        sa.Column('job_config', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['pos_integration_id'], ['pos_integrations.id'], ),
    )
    
    # Indexes for menu_sync_jobs
    op.create_index('ix_menu_sync_jobs_job_id', 'menu_sync_jobs', ['job_id'])
    op.create_index('ix_menu_sync_jobs_id', 'menu_sync_jobs', ['id'])

    # Menu Sync Logs table
    op.create_table('menu_sync_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sync_job_id', sa.Integer(), nullable=False),
        sa.Column('mapping_id', sa.Integer(), nullable=True),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('aura_entity_id', sa.Integer(), nullable=True),
        sa.Column('pos_entity_id', sa.String(length=255), nullable=True),
        sa.Column('operation', sa.String(length=50), nullable=False),
        sa.Column('sync_direction', postgresql.ENUM('push', 'pull', 'bidirectional', name='syncdirection', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'in_progress', 'success', 'error', 'conflict', 'cancelled', name='syncstatus', create_type=False), nullable=False),
        sa.Column('aura_data_before', sa.JSON(), nullable=True),
        sa.Column('aura_data_after', sa.JSON(), nullable=True),
        sa.Column('pos_data_before', sa.JSON(), nullable=True),
        sa.Column('pos_data_after', sa.JSON(), nullable=True),
        sa.Column('changes_detected', sa.JSON(), nullable=True),
        sa.Column('conflict_type', sa.String(length=100), nullable=True),
        sa.Column('conflict_resolution', postgresql.ENUM('manual', 'pos_wins', 'aura_wins', 'latest_wins', name='conflictresolution', create_type=False), nullable=True),
        sa.Column('conflict_resolved_by', sa.Integer(), nullable=True),
        sa.Column('conflict_resolved_at', sa.DateTime(), nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(length=50), nullable=True),
        sa.Column('debug_info', sa.JSON(), nullable=True),
        sa.Column('menu_version_id', sa.Integer(), nullable=True),
        sa.Column('version_created', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['sync_job_id'], ['menu_sync_jobs.id'], ),
        sa.ForeignKeyConstraint(['mapping_id'], ['pos_menu_mappings.id'], ),
        sa.ForeignKeyConstraint(['menu_version_id'], ['menu_versions.id'], ),
    )
    
    # Indexes for menu_sync_logs
    op.create_index('ix_menu_sync_logs_job_status', 'menu_sync_logs', ['sync_job_id', 'status'])
    op.create_index('ix_menu_sync_logs_entity', 'menu_sync_logs', ['entity_type', 'aura_entity_id'])
    op.create_index('ix_menu_sync_logs_conflict', 'menu_sync_logs', ['status', 'conflict_type'])
    op.create_index('ix_menu_sync_logs_time', 'menu_sync_logs', ['created_at'])
    op.create_index('ix_menu_sync_logs_id', 'menu_sync_logs', ['id'])

    # Menu Sync Conflicts table
    op.create_table('menu_sync_conflicts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conflict_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column('sync_job_id', sa.Integer(), nullable=False),
        sa.Column('sync_log_id', sa.Integer(), nullable=False),
        sa.Column('mapping_id', sa.Integer(), nullable=True),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('aura_entity_id', sa.Integer(), nullable=True),
        sa.Column('pos_entity_id', sa.String(length=255), nullable=True),
        sa.Column('conflict_type', sa.String(length=100), nullable=False),
        sa.Column('conflict_description', sa.Text(), nullable=True),
        sa.Column('severity', sa.String(length=20), nullable=False, default='medium'),
        sa.Column('aura_current_data', sa.JSON(), nullable=True),
        sa.Column('pos_current_data', sa.JSON(), nullable=True),
        sa.Column('conflicting_fields', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, default='unresolved'),
        sa.Column('resolution_strategy', postgresql.ENUM('manual', 'pos_wins', 'aura_wins', 'latest_wins', name='conflictresolution', create_type=False), nullable=True),
        sa.Column('resolved_by', sa.Integer(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('auto_resolvable', sa.Boolean(), nullable=False, default=False),
        sa.Column('priority', sa.Integer(), nullable=False, default=5),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['sync_job_id'], ['menu_sync_jobs.id'], ),
        sa.ForeignKeyConstraint(['sync_log_id'], ['menu_sync_logs.id'], ),
        sa.ForeignKeyConstraint(['mapping_id'], ['pos_menu_mappings.id'], ),
    )
    
    # Indexes for menu_sync_conflicts
    op.create_index('ix_menu_sync_conflicts_conflict_id', 'menu_sync_conflicts', ['conflict_id'])
    op.create_index('ix_menu_sync_conflicts_unresolved', 'menu_sync_conflicts', ['status', 'severity'])
    op.create_index('ix_menu_sync_conflicts_entity', 'menu_sync_conflicts', ['entity_type', 'aura_entity_id'])
    op.create_index('ix_menu_sync_conflicts_priority', 'menu_sync_conflicts', ['priority', 'created_at'])
    op.create_index('ix_menu_sync_conflicts_id', 'menu_sync_conflicts', ['id'])

    # Menu Sync Configs table
    op.create_table('menu_sync_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pos_integration_id', sa.Integer(), nullable=False, unique=True),
        sa.Column('sync_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('default_sync_direction', postgresql.ENUM('push', 'pull', 'bidirectional', name='syncdirection', create_type=False), nullable=False, default='bidirectional'),
        sa.Column('default_conflict_resolution', postgresql.ENUM('manual', 'pos_wins', 'aura_wins', 'latest_wins', name='conflictresolution', create_type=False), nullable=False, default='manual'),
        sa.Column('auto_sync_enabled', sa.Boolean(), nullable=False, default=False),
        sa.Column('sync_frequency_minutes', sa.Integer(), nullable=True),
        sa.Column('sync_time_windows', sa.JSON(), nullable=True),
        sa.Column('max_concurrent_jobs', sa.Integer(), nullable=False, default=1),
        sa.Column('sync_categories', sa.Boolean(), nullable=False, default=True),
        sa.Column('sync_items', sa.Boolean(), nullable=False, default=True),
        sa.Column('sync_modifiers', sa.Boolean(), nullable=False, default=True),
        sa.Column('sync_pricing', sa.Boolean(), nullable=False, default=True),
        sa.Column('sync_availability', sa.Boolean(), nullable=False, default=True),
        sa.Column('create_missing_categories', sa.Boolean(), nullable=False, default=True),
        sa.Column('preserve_aura_customizations', sa.Boolean(), nullable=False, default=True),
        sa.Column('backup_before_sync', sa.Boolean(), nullable=False, default=True),
        sa.Column('max_batch_size', sa.Integer(), nullable=False, default=100),
        sa.Column('create_version_on_pull', sa.Boolean(), nullable=False, default=True),
        sa.Column('version_name_template', sa.String(length=200), nullable=True),
        sa.Column('notify_on_conflicts', sa.Boolean(), nullable=False, default=True),
        sa.Column('notify_on_errors', sa.Boolean(), nullable=False, default=True),
        sa.Column('notification_emails', sa.JSON(), nullable=True),
        sa.Column('field_mappings', sa.JSON(), nullable=True),
        sa.Column('transformation_rules', sa.JSON(), nullable=True),
        sa.Column('validation_rules', sa.JSON(), nullable=True),
        sa.Column('rate_limit_requests', sa.Integer(), nullable=True),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, default=30),
        sa.Column('retry_failed_operations', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['pos_integration_id'], ['pos_integrations.id'], ),
    )
    
    op.create_index('ix_menu_sync_configs_id', 'menu_sync_configs', ['id'])

    # Menu Sync Statistics table
    op.create_table('menu_sync_statistics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pos_integration_id', sa.Integer(), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('period_type', sa.String(length=20), nullable=False),
        sa.Column('total_jobs', sa.Integer(), nullable=False, default=0),
        sa.Column('successful_jobs', sa.Integer(), nullable=False, default=0),
        sa.Column('failed_jobs', sa.Integer(), nullable=False, default=0),
        sa.Column('avg_job_duration_seconds', sa.Float(), nullable=True),
        sa.Column('total_entities_synced', sa.Integer(), nullable=False, default=0),
        sa.Column('categories_synced', sa.Integer(), nullable=False, default=0),
        sa.Column('items_synced', sa.Integer(), nullable=False, default=0),
        sa.Column('modifiers_synced', sa.Integer(), nullable=False, default=0),
        sa.Column('push_operations', sa.Integer(), nullable=False, default=0),
        sa.Column('pull_operations', sa.Integer(), nullable=False, default=0),
        sa.Column('total_conflicts', sa.Integer(), nullable=False, default=0),
        sa.Column('resolved_conflicts', sa.Integer(), nullable=False, default=0),
        sa.Column('unresolved_conflicts', sa.Integer(), nullable=False, default=0),
        sa.Column('avg_sync_time_per_entity_ms', sa.Float(), nullable=True),
        sa.Column('success_rate_percentage', sa.Float(), nullable=True),
        sa.Column('error_rate_percentage', sa.Float(), nullable=True),
        sa.Column('data_consistency_score', sa.Float(), nullable=True),
        sa.Column('last_successful_full_sync', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['pos_integration_id'], ['pos_integrations.id'], ),
    )
    
    # Indexes for menu_sync_statistics
    op.create_index('ix_menu_sync_stats_period', 'menu_sync_statistics', ['pos_integration_id', 'period_type', 'period_end'])
    op.create_index('ix_menu_sync_stats_performance', 'menu_sync_statistics', ['success_rate_percentage', 'error_rate_percentage'])
    op.create_index('ix_menu_sync_statistics_id', 'menu_sync_statistics', ['id'])


def downgrade():
    # Drop tables in reverse order
    op.drop_table('menu_sync_statistics')
    op.drop_table('menu_sync_configs')
    op.drop_table('menu_sync_conflicts')
    op.drop_table('menu_sync_logs')
    op.drop_table('menu_sync_jobs')
    op.drop_table('pos_menu_mappings')
    
    # Drop enum types
    op.execute('DROP TYPE IF EXISTS conflictresolution')
    op.execute('DROP TYPE IF EXISTS syncstatus')
    op.execute('DROP TYPE IF EXISTS syncdirection')