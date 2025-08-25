"""Create POS migration tables

Revision ID: pos_migration_001
Revises: 
Create Date: 2025-08-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'pos_migration_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create pos_migration_jobs table
    op.create_table(
        'pos_migration_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_name', sa.String(length=255), nullable=False),
        sa.Column('source_provider', sa.String(length=50), nullable=False),
        sa.Column('target_provider', sa.String(length=50), nullable=True),
        sa.Column('restaurant_id', sa.Integer(), nullable=False),
        
        # Authentication & Connection
        sa.Column('source_credentials', sa.JSON(), nullable=False),
        sa.Column('source_api_endpoint', sa.String(length=500), nullable=True),
        
        # Migration Configuration
        sa.Column('entities_to_migrate', sa.JSON(), nullable=False),
        sa.Column('mapping_rules', sa.JSON(), nullable=True),
        sa.Column('transformation_rules', sa.JSON(), nullable=True),
        sa.Column('validation_rules', sa.JSON(), nullable=True),
        
        # Status & Progress
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('progress_percentage', sa.Float(), nullable=True),
        sa.Column('current_entity', sa.String(length=50), nullable=True),
        sa.Column('entities_completed', sa.JSON(), nullable=True),
        
        # Statistics
        sa.Column('total_records', sa.Integer(), nullable=True),
        sa.Column('records_processed', sa.Integer(), nullable=True),
        sa.Column('records_succeeded', sa.Integer(), nullable=True),
        sa.Column('records_failed', sa.Integer(), nullable=True),
        sa.Column('records_skipped', sa.Integer(), nullable=True),
        
        # Timing
        sa.Column('scheduled_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('estimated_completion', sa.DateTime(), nullable=True),
        
        # Error Handling
        sa.Column('error_count', sa.Integer(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('error_details', sa.JSON(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('max_retries', sa.Integer(), nullable=True),
        
        # Audit & Compliance
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('approval_notes', sa.Text(), nullable=True),
        sa.Column('compliance_checks', sa.JSON(), nullable=True),
        
        # Performance
        sa.Column('batch_size', sa.Integer(), nullable=True),
        sa.Column('rate_limit', sa.Integer(), nullable=True),
        sa.Column('parallel_workers', sa.Integer(), nullable=True),
        
        # Rollback Support
        sa.Column('rollback_enabled', sa.Boolean(), nullable=True),
        sa.Column('rollback_checkpoint', sa.JSON(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_migration_status_restaurant', 'pos_migration_jobs', ['status', 'restaurant_id'])
    op.create_index('idx_migration_created_at', 'pos_migration_jobs', ['created_at'])
    
    # Add check constraint
    op.create_check_constraint(
        'ck_progress_percentage',
        'pos_migration_jobs',
        'progress_percentage >= 0 AND progress_percentage <= 100'
    )
    
    # Create pos_data_mappings table
    op.create_table(
        'pos_data_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('migration_job_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        
        # Mapping Configuration
        sa.Column('source_field', sa.String(length=255), nullable=False),
        sa.Column('target_field', sa.String(length=255), nullable=False),
        sa.Column('transformation_function', sa.String(length=100), nullable=True),
        sa.Column('default_value', sa.String(length=500), nullable=True),
        
        # AI Assistance
        sa.Column('ai_suggested', sa.Boolean(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('user_approved', sa.Boolean(), nullable=True),
        
        # Validation
        sa.Column('is_required', sa.Boolean(), nullable=True),
        sa.Column('validation_regex', sa.String(length=500), nullable=True),
        sa.Column('data_type', sa.String(length=50), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        
        sa.ForeignKeyConstraint(['migration_job_id'], ['pos_migration_jobs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create unique constraint and index
    op.create_unique_constraint('uq_mapping', 'pos_data_mappings', ['migration_job_id', 'entity_type', 'source_field'])
    op.create_index('idx_mapping_entity', 'pos_data_mappings', ['migration_job_id', 'entity_type'])
    
    # Create pos_migration_logs table
    op.create_table(
        'pos_migration_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('migration_job_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Log Details
        sa.Column('log_level', sa.String(length=20), nullable=True),
        sa.Column('entity_type', sa.String(length=50), nullable=True),
        sa.Column('entity_id', sa.String(length=255), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=True),
        
        # Message & Data
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('source_data', sa.JSON(), nullable=True),
        sa.Column('transformed_data', sa.JSON(), nullable=True),
        
        # Error Information
        sa.Column('error_type', sa.String(length=100), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('stack_trace', sa.Text(), nullable=True),
        
        # Performance Metrics
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('memory_usage_mb', sa.Float(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        
        sa.ForeignKeyConstraint(['migration_job_id'], ['pos_migration_jobs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_log_job_level', 'pos_migration_logs', ['migration_job_id', 'log_level'])
    op.create_index('idx_log_created', 'pos_migration_logs', ['created_at'])
    
    # Create pos_validation_results table
    op.create_table(
        'pos_validation_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('migration_job_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Validation Context
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.String(length=255), nullable=True),
        sa.Column('validation_type', sa.String(length=100), nullable=True),
        
        # Results
        sa.Column('is_valid', sa.Boolean(), nullable=False),
        sa.Column('validation_errors', sa.JSON(), nullable=True),
        sa.Column('warnings', sa.JSON(), nullable=True),
        
        # Data Snapshot
        sa.Column('validated_data', sa.JSON(), nullable=True),
        sa.Column('expected_values', sa.JSON(), nullable=True),
        sa.Column('actual_values', sa.JSON(), nullable=True),
        
        # Remediation
        sa.Column('auto_fixed', sa.Boolean(), nullable=True),
        sa.Column('fix_applied', sa.JSON(), nullable=True),
        sa.Column('manual_review_required', sa.Boolean(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        
        sa.ForeignKeyConstraint(['migration_job_id'], ['pos_migration_jobs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_validation_job_type', 'pos_validation_results', ['migration_job_id', 'entity_type'])
    op.create_index('idx_validation_invalid', 'pos_validation_results', ['migration_job_id', 'is_valid'])
    
    # Create pos_migration_templates table
    op.create_table(
        'pos_migration_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_name', sa.String(length=255), nullable=False),
        sa.Column('source_provider', sa.String(length=50), nullable=False),
        sa.Column('target_provider', sa.String(length=50), nullable=True),
        sa.Column('restaurant_id', sa.Integer(), nullable=True),
        
        # Template Configuration
        sa.Column('default_mappings', sa.JSON(), nullable=False),
        sa.Column('transformation_rules', sa.JSON(), nullable=True),
        sa.Column('validation_rules', sa.JSON(), nullable=True),
        sa.Column('recommended_batch_size', sa.Integer(), nullable=True),
        
        # Metadata
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('version', sa.String(length=20), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=True),
        sa.Column('success_rate', sa.Float(), nullable=True),
        
        # Best Practices
        sa.Column('common_issues', sa.JSON(), nullable=True),
        sa.Column('resolution_steps', sa.JSON(), nullable=True),
        sa.Column('performance_tips', sa.JSON(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('template_name')
    )
    
    # Create index
    op.create_index('idx_template_provider', 'pos_migration_templates', ['source_provider', 'target_provider'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('idx_template_provider', table_name='pos_migration_templates')
    op.drop_table('pos_migration_templates')
    
    op.drop_index('idx_validation_invalid', table_name='pos_validation_results')
    op.drop_index('idx_validation_job_type', table_name='pos_validation_results')
    op.drop_table('pos_validation_results')
    
    op.drop_index('idx_log_created', table_name='pos_migration_logs')
    op.drop_index('idx_log_job_level', table_name='pos_migration_logs')
    op.drop_table('pos_migration_logs')
    
    op.drop_index('idx_mapping_entity', table_name='pos_data_mappings')
    op.drop_constraint('uq_mapping', 'pos_data_mappings', type_='unique')
    op.drop_table('pos_data_mappings')
    
    op.drop_constraint('ck_progress_percentage', 'pos_migration_jobs', type_='check')
    op.drop_index('idx_migration_created_at', table_name='pos_migration_jobs')
    op.drop_index('idx_migration_status_restaurant', table_name='pos_migration_jobs')
    op.drop_table('pos_migration_jobs')