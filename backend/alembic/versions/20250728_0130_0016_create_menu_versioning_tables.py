# backend/migrations/20250728_0130_0016_create_menu_versioning_tables.py

"""Create menu versioning tables

Revision ID: 20250728_0130_0016
Revises: 20250130_1500_0016
Create Date: 2025-07-28 01:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250728_0130_0016'
down_revision = '20250130_1500_0016'
branch_labels = None
depends_on = None


def upgrade():
    # Get database connection
    connection = op.get_bind()
    
    # Check and create versiontype enum using DO block
    connection.execute(sa.text("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type t
                JOIN pg_namespace n ON t.typnamespace = n.oid
                WHERE t.typname = 'versiontype'
                AND n.nspname = current_schema()
                AND t.typtype = 'e'
            ) THEN
                CREATE TYPE versiontype AS ENUM ('manual', 'scheduled', 'rollback', 'migration', 'auto_save');
            END IF;
        END$$;
    """))
    
    # Check and create changetype enum using DO block
    connection.execute(sa.text("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type t
                JOIN pg_namespace n ON t.typnamespace = n.oid
                WHERE t.typname = 'changetype'
                AND n.nspname = current_schema()
                AND t.typtype = 'e'
            ) THEN
                CREATE TYPE changetype AS ENUM ('create', 'update', 'delete', 'activate', 'deactivate', 'price_change', 'availability_change', 'category_change', 'modifier_change');
            END IF;
        END$$;
    """))
    
    # Create menu_versions table
    op.create_table('menu_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.String(length=50), nullable=False),
        sa.Column('version_name', sa.String(length=200), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('version_type', postgresql.ENUM('manual', 'scheduled', 'rollback', 'migration', 'auto_save', name='versiontype', create_type=False), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_published', sa.Boolean(), nullable=False),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('scheduled_publish_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('total_items', sa.Integer(), nullable=False),
        sa.Column('total_categories', sa.Integer(), nullable=False),
        sa.Column('total_modifiers', sa.Integer(), nullable=False),
        sa.Column('changes_summary', sa.JSON(), nullable=True),
        sa.Column('parent_version_id', sa.Integer(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['parent_version_id'], ['menu_versions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_menu_versions_id'), 'menu_versions', ['id'], unique=False)
    op.create_index(op.f('ix_menu_versions_version_number'), 'menu_versions', ['version_number'], unique=False)
    
    # Create menu_category_versions table
    op.create_table('menu_category_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('menu_version_id', sa.Integer(), nullable=False),
        sa.Column('original_category_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('parent_category_id', sa.Integer(), nullable=True),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('change_type', postgresql.ENUM('create', 'update', 'delete', 'activate', 'deactivate', 'price_change', 'availability_change', 'category_change', 'modifier_change', name='changetype', create_type=False), nullable=False),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('changed_fields', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['menu_version_id'], ['menu_versions.id'], ),
        sa.ForeignKeyConstraint(['original_category_id'], ['menu_categories.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_menu_category_versions_id'), 'menu_category_versions', ['id'], unique=False)
    
    # Create menu_item_versions table
    op.create_table('menu_item_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('menu_version_id', sa.Integer(), nullable=False),
        sa.Column('original_item_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('sku', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_available', sa.Boolean(), nullable=False),
        sa.Column('availability_start_time', sa.String(length=8), nullable=True),
        sa.Column('availability_end_time', sa.String(length=8), nullable=True),
        sa.Column('calories', sa.Integer(), nullable=True),
        sa.Column('dietary_tags', sa.JSON(), nullable=True),
        sa.Column('allergen_info', sa.JSON(), nullable=True),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.Column('prep_time_minutes', sa.Integer(), nullable=True),
        sa.Column('cooking_instructions', sa.Text(), nullable=True),
        sa.Column('change_type', postgresql.ENUM('create', 'update', 'delete', 'activate', 'deactivate', 'price_change', 'availability_change', 'category_change', 'modifier_change', name='changetype', create_type=False), nullable=False),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('changed_fields', sa.JSON(), nullable=True),
        sa.Column('price_history', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['menu_version_id'], ['menu_versions.id'], ),
        sa.ForeignKeyConstraint(['original_item_id'], ['menu_items.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_menu_item_versions_id'), 'menu_item_versions', ['id'], unique=False)
    
    # Create modifier_group_versions table
    op.create_table('modifier_group_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('menu_version_id', sa.Integer(), nullable=False),
        sa.Column('original_group_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('selection_type', sa.String(length=20), nullable=False),
        sa.Column('is_required', sa.Boolean(), nullable=False),
        sa.Column('min_selections', sa.Integer(), nullable=False),
        sa.Column('max_selections', sa.Integer(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('change_type', postgresql.ENUM('create', 'update', 'delete', 'activate', 'deactivate', 'price_change', 'availability_change', 'category_change', 'modifier_change', name='changetype', create_type=False), nullable=False),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('changed_fields', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['menu_version_id'], ['menu_versions.id'], ),
        sa.ForeignKeyConstraint(['original_group_id'], ['modifier_groups.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_modifier_group_versions_id'), 'modifier_group_versions', ['id'], unique=False)
    
    # Create modifier_versions table
    op.create_table('modifier_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('modifier_group_version_id', sa.Integer(), nullable=False),
        sa.Column('original_modifier_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price_adjustment', sa.Float(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.Column('change_type', postgresql.ENUM('create', 'update', 'delete', 'activate', 'deactivate', 'price_change', 'availability_change', 'category_change', 'modifier_change', name='changetype', create_type=False), nullable=False),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('changed_fields', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['modifier_group_version_id'], ['modifier_group_versions.id'], ),
        sa.ForeignKeyConstraint(['original_modifier_id'], ['modifiers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_modifier_versions_id'), 'modifier_versions', ['id'], unique=False)
    
    # Create menu_item_modifier_versions table
    op.create_table('menu_item_modifier_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('menu_item_version_id', sa.Integer(), nullable=False),
        sa.Column('modifier_group_version_id', sa.Integer(), nullable=False),
        sa.Column('original_association_id', sa.Integer(), nullable=True),
        sa.Column('is_required', sa.Boolean(), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.Column('change_type', postgresql.ENUM('create', 'update', 'delete', 'activate', 'deactivate', 'price_change', 'availability_change', 'category_change', 'modifier_change', name='changetype', create_type=False), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['menu_item_version_id'], ['menu_item_versions.id'], ),
        sa.ForeignKeyConstraint(['modifier_group_version_id'], ['modifier_group_versions.id'], ),
        sa.ForeignKeyConstraint(['original_association_id'], ['menu_item_modifiers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_menu_item_modifier_versions_id'), 'menu_item_modifier_versions', ['id'], unique=False)
    
    # Create menu_audit_logs table
    op.create_table('menu_audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('menu_version_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('entity_name', sa.String(length=200), nullable=True),
        sa.Column('change_type', postgresql.ENUM('create', 'update', 'delete', 'activate', 'deactivate', 'price_change', 'availability_change', 'category_change', 'modifier_change', name='changetype', create_type=False), nullable=False),
        sa.Column('old_values', sa.JSON(), nullable=True),
        sa.Column('new_values', sa.JSON(), nullable=True),
        sa.Column('changed_fields', sa.JSON(), nullable=True),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('user_role', sa.String(length=50), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('session_id', sa.String(length=100), nullable=True),
        sa.Column('batch_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('parent_log_id', sa.Integer(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['menu_version_id'], ['menu_versions.id'], ),
        sa.ForeignKeyConstraint(['parent_log_id'], ['menu_audit_logs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_menu_audit_logs_id'), 'menu_audit_logs', ['id'], unique=False)
    
    # Create menu_version_schedules table
    op.create_table('menu_version_schedules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('menu_version_id', sa.Integer(), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(), nullable=False),
        sa.Column('timezone', sa.String(length=50), nullable=False),
        sa.Column('is_recurring', sa.Boolean(), nullable=False),
        sa.Column('recurrence_pattern', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.Column('execution_result', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('max_retries', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['menu_version_id'], ['menu_versions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_menu_version_schedules_id'), 'menu_version_schedules', ['id'], unique=False)
    
    # Create menu_version_comparisons table
    op.create_table('menu_version_comparisons',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('from_version_id', sa.Integer(), nullable=False),
        sa.Column('to_version_id', sa.Integer(), nullable=False),
        sa.Column('comparison_data', sa.JSON(), nullable=False),
        sa.Column('summary', sa.JSON(), nullable=False),
        sa.Column('generated_by', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['from_version_id'], ['menu_versions.id'], ),
        sa.ForeignKeyConstraint(['to_version_id'], ['menu_versions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_menu_version_comparisons_id'), 'menu_version_comparisons', ['id'], unique=False)
    
    # Set default values for existing columns
    op.execute("ALTER TABLE menu_versions ALTER COLUMN version_type SET DEFAULT 'manual'")
    op.execute("ALTER TABLE menu_versions ALTER COLUMN is_active SET DEFAULT false")
    op.execute("ALTER TABLE menu_versions ALTER COLUMN is_published SET DEFAULT false")
    op.execute("ALTER TABLE menu_versions ALTER COLUMN total_items SET DEFAULT 0")
    op.execute("ALTER TABLE menu_versions ALTER COLUMN total_categories SET DEFAULT 0")
    op.execute("ALTER TABLE menu_versions ALTER COLUMN total_modifiers SET DEFAULT 0")
    
    # Add indexes for performance
    op.create_index('ix_menu_versions_active', 'menu_versions', ['is_active'])
    op.create_index('ix_menu_versions_published', 'menu_versions', ['is_published'])
    op.create_index('ix_menu_versions_created_by', 'menu_versions', ['created_by'])
    op.create_index('ix_menu_audit_logs_entity', 'menu_audit_logs', ['entity_type', 'entity_id'])
    op.create_index('ix_menu_audit_logs_user', 'menu_audit_logs', ['user_id'])
    op.create_index('ix_menu_audit_logs_batch', 'menu_audit_logs', ['batch_id'])
    op.create_index('ix_menu_audit_logs_created_at', 'menu_audit_logs', ['created_at'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_menu_audit_logs_created_at', table_name='menu_audit_logs')
    op.drop_index('ix_menu_audit_logs_batch', table_name='menu_audit_logs')
    op.drop_index('ix_menu_audit_logs_user', table_name='menu_audit_logs')
    op.drop_index('ix_menu_audit_logs_entity', table_name='menu_audit_logs')
    op.drop_index('ix_menu_versions_created_by', table_name='menu_versions')
    op.drop_index('ix_menu_versions_published', table_name='menu_versions')
    op.drop_index('ix_menu_versions_active', table_name='menu_versions')
    
    # Drop tables in reverse order
    op.drop_index(op.f('ix_menu_version_comparisons_id'), table_name='menu_version_comparisons')
    op.drop_table('menu_version_comparisons')
    
    op.drop_index(op.f('ix_menu_version_schedules_id'), table_name='menu_version_schedules')
    op.drop_table('menu_version_schedules')
    
    op.drop_index(op.f('ix_menu_audit_logs_id'), table_name='menu_audit_logs')
    op.drop_table('menu_audit_logs')
    
    op.drop_index(op.f('ix_menu_item_modifier_versions_id'), table_name='menu_item_modifier_versions')
    op.drop_table('menu_item_modifier_versions')
    
    op.drop_index(op.f('ix_modifier_versions_id'), table_name='modifier_versions')
    op.drop_table('modifier_versions')
    
    op.drop_index(op.f('ix_modifier_group_versions_id'), table_name='modifier_group_versions')
    op.drop_table('modifier_group_versions')
    
    op.drop_index(op.f('ix_menu_item_versions_id'), table_name='menu_item_versions')
    op.drop_table('menu_item_versions')
    
    op.drop_index(op.f('ix_menu_category_versions_id'), table_name='menu_category_versions')
    op.drop_table('menu_category_versions')
    
    op.drop_index(op.f('ix_menu_versions_version_number'), table_name='menu_versions')
    op.drop_index(op.f('ix_menu_versions_id'), table_name='menu_versions')
    op.drop_table('menu_versions')
    
    # Drop enum types
    op.execute('DROP TYPE IF EXISTS changetype')
    op.execute('DROP TYPE IF EXISTS versiontype')