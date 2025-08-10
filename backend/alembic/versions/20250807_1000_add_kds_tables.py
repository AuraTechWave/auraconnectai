"""Add Kitchen Display System (KDS) tables

Revision ID: 20250807_1000
Revises: 20250806_1500_add_inventory_deduction_tracking
Create Date: 2025-08-07 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250807_1000_add_kds_tables'
down_revision = 'add_inventory_deduction_tracking'
branch_labels = None
depends_on = None


def upgrade():
    # Create enum types with existence checks
    connection = op.get_bind()
    
    # Check and create stationtype enum
    connection.execute(sa.text("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type t
                JOIN pg_namespace n ON t.typnamespace = n.oid
                WHERE t.typname = 'stationtype'
                AND n.nspname = current_schema()
                AND t.typtype = 'e'
            ) THEN
                CREATE TYPE stationtype AS ENUM ('grill', 'fry', 'saute', 'salad', 'dessert', 'beverage', 'expo', 'prep', 'pizza', 'sandwich', 'sushi', 'bar');
            END IF;
        END$$;
    """))
    
    # Check and create stationstatus enum
    connection.execute(sa.text("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type t
                JOIN pg_namespace n ON t.typnamespace = n.oid
                WHERE t.typname = 'stationstatus'
                AND n.nspname = current_schema()
                AND t.typtype = 'e'
            ) THEN
                CREATE TYPE stationstatus AS ENUM ('active', 'inactive', 'busy', 'offline', 'maintenance');
            END IF;
        END$$;
    """))
    
    # Check and create displaystatus enum
    connection.execute(sa.text("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type t
                JOIN pg_namespace n ON t.typnamespace = n.oid
                WHERE t.typname = 'displaystatus'
                AND n.nspname = current_schema()
                AND t.typtype = 'e'
            ) THEN
                CREATE TYPE displaystatus AS ENUM ('pending', 'in_progress', 'ready', 'recalled', 'completed', 'cancelled');
            END IF;
        END$$;
    """))

    # Create kitchen_stations table
    op.create_table('kitchen_stations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('station_type', postgresql.ENUM('grill', 'fry', 'saute', 'salad', 'dessert', 'beverage', 'expo', 'prep', 'pizza', 'sandwich', 'sushi', 'bar', name='stationtype'), nullable=False),
        sa.Column('status', postgresql.ENUM('active', 'inactive', 'busy', 'offline', 'maintenance', name='stationstatus'), nullable=True),
        sa.Column('display_name', sa.String(length=100), nullable=True),
        sa.Column('color_code', sa.String(length=7), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('max_active_items', sa.Integer(), nullable=True),
        sa.Column('prep_time_multiplier', sa.Float(), nullable=True),
        sa.Column('warning_time_minutes', sa.Integer(), nullable=True),
        sa.Column('critical_time_minutes', sa.Integer(), nullable=True),
        sa.Column('current_staff_id', sa.Integer(), nullable=True),
        sa.Column('staff_assigned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('features', sa.JSON(), nullable=True),
        sa.Column('printer_id', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['current_staff_id'], ['staff_members.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('idx_station_type_status', 'kitchen_stations', ['station_type', 'status'], unique=False)
    op.create_index(op.f('ix_kitchen_stations_station_type'), 'kitchen_stations', ['station_type'], unique=False)
    op.create_index(op.f('ix_kitchen_stations_status'), 'kitchen_stations', ['status'], unique=False)

    # Create kitchen_displays table
    op.create_table('kitchen_displays',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('station_id', sa.Integer(), nullable=False),
        sa.Column('display_number', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=100), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('last_heartbeat', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('layout_mode', sa.String(length=20), nullable=True),
        sa.Column('items_per_page', sa.Integer(), nullable=True),
        sa.Column('auto_clear_completed', sa.Boolean(), nullable=True),
        sa.Column('auto_clear_delay_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['station_id'], ['kitchen_stations.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('station_id', 'display_number', name='uq_station_display_number')
    )

    # Create station_assignments table
    op.create_table('station_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('station_id', sa.Integer(), nullable=False),
        sa.Column('category_name', sa.String(length=100), nullable=True),
        sa.Column('tag_name', sa.String(length=100), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('is_primary', sa.Boolean(), nullable=True),
        sa.Column('prep_time_override', sa.Integer(), nullable=True),
        sa.Column('conditions', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['station_id'], ['kitchen_stations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_assignment_category', 'station_assignments', ['category_name'], unique=False)
    op.create_index('idx_assignment_tag', 'station_assignments', ['tag_name'], unique=False)

    # Create menu_item_stations table
    op.create_table('menu_item_stations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('menu_item_id', sa.Integer(), nullable=False),
        sa.Column('station_id', sa.Integer(), nullable=False),
        sa.Column('is_primary', sa.Boolean(), nullable=True),
        sa.Column('sequence', sa.Integer(), nullable=True),
        sa.Column('prep_time_minutes', sa.Integer(), nullable=False),
        sa.Column('station_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['station_id'], ['kitchen_stations.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('menu_item_id', 'station_id', 'sequence', name='uq_menu_item_station_seq')
    )
    op.create_index(op.f('ix_menu_item_stations_menu_item_id'), 'menu_item_stations', ['menu_item_id'], unique=False)

    # Create kds_order_items table
    op.create_table('kds_order_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_item_id', sa.Integer(), nullable=False),
        sa.Column('station_id', sa.Integer(), nullable=False),
        sa.Column('display_name', sa.String(length=200), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('modifiers', sa.JSON(), nullable=True),
        sa.Column('special_instructions', sa.Text(), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'in_progress', 'ready', 'recalled', 'completed', 'cancelled', name='displaystatus'), nullable=True),
        sa.Column('sequence_number', sa.Integer(), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('target_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('course_number', sa.Integer(), nullable=True),
        sa.Column('fire_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_by_id', sa.Integer(), nullable=True),
        sa.Column('completed_by_id', sa.Integer(), nullable=True),
        sa.Column('recall_count', sa.Integer(), nullable=True),
        sa.Column('last_recalled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('recall_reason', sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(['completed_by_id'], ['staff_members.id'], ),
        sa.ForeignKeyConstraint(['order_item_id'], ['order_items.id'], ),
        sa.ForeignKeyConstraint(['started_by_id'], ['staff_members.id'], ),
        sa.ForeignKeyConstraint(['station_id'], ['kitchen_stations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_kds_order_item_priority', 'kds_order_items', ['station_id', 'priority', 'received_at'], unique=False)
    op.create_index('idx_kds_order_item_received', 'kds_order_items', ['station_id', 'received_at'], unique=False)
    op.create_index('idx_kds_order_item_status', 'kds_order_items', ['station_id', 'status'], unique=False)
    op.create_index(op.f('ix_kds_order_items_status'), 'kds_order_items', ['status'], unique=False)

    # Add default values for existing columns
    op.execute("UPDATE kitchen_stations SET priority = 0 WHERE priority IS NULL")
    op.execute("UPDATE kitchen_stations SET max_active_items = 10 WHERE max_active_items IS NULL")
    op.execute("UPDATE kitchen_stations SET prep_time_multiplier = 1.0 WHERE prep_time_multiplier IS NULL")
    op.execute("UPDATE kitchen_stations SET warning_time_minutes = 5 WHERE warning_time_minutes IS NULL")
    op.execute("UPDATE kitchen_stations SET critical_time_minutes = 10 WHERE critical_time_minutes IS NULL")
    op.execute("UPDATE kitchen_stations SET features = '[]'::json WHERE features IS NULL")
    op.execute("UPDATE kitchen_stations SET status = 'active' WHERE status IS NULL")
    
    op.execute("UPDATE kitchen_displays SET display_number = 1 WHERE display_number IS NULL")
    op.execute("UPDATE kitchen_displays SET is_active = true WHERE is_active IS NULL")
    op.execute("UPDATE kitchen_displays SET layout_mode = 'grid' WHERE layout_mode IS NULL")
    op.execute("UPDATE kitchen_displays SET items_per_page = 6 WHERE items_per_page IS NULL")
    op.execute("UPDATE kitchen_displays SET auto_clear_completed = true WHERE auto_clear_completed IS NULL")
    op.execute("UPDATE kitchen_displays SET auto_clear_delay_seconds = 30 WHERE auto_clear_delay_seconds IS NULL")
    
    op.execute("UPDATE station_assignments SET priority = 0 WHERE priority IS NULL")
    op.execute("UPDATE station_assignments SET is_primary = true WHERE is_primary IS NULL")
    op.execute("UPDATE station_assignments SET conditions = '{}'::json WHERE conditions IS NULL")
    
    op.execute("UPDATE menu_item_stations SET is_primary = true WHERE is_primary IS NULL")
    op.execute("UPDATE menu_item_stations SET sequence = 0 WHERE sequence IS NULL")
    
    op.execute("UPDATE kds_order_items SET modifiers = '[]'::json WHERE modifiers IS NULL")
    op.execute("UPDATE kds_order_items SET status = 'pending' WHERE status IS NULL")
    op.execute("UPDATE kds_order_items SET priority = 0 WHERE priority IS NULL")
    op.execute("UPDATE kds_order_items SET course_number = 1 WHERE course_number IS NULL")
    op.execute("UPDATE kds_order_items SET recall_count = 0 WHERE recall_count IS NULL")


def downgrade():
    # Drop tables in reverse order
    op.drop_index(op.f('ix_kds_order_items_status'), table_name='kds_order_items')
    op.drop_index('idx_kds_order_item_status', table_name='kds_order_items')
    op.drop_index('idx_kds_order_item_received', table_name='kds_order_items')
    op.drop_index('idx_kds_order_item_priority', table_name='kds_order_items')
    op.drop_table('kds_order_items')
    
    op.drop_index(op.f('ix_menu_item_stations_menu_item_id'), table_name='menu_item_stations')
    op.drop_table('menu_item_stations')
    
    op.drop_index('idx_assignment_tag', table_name='station_assignments')
    op.drop_index('idx_assignment_category', table_name='station_assignments')
    op.drop_table('station_assignments')
    
    op.drop_table('kitchen_displays')
    
    op.drop_index(op.f('ix_kitchen_stations_status'), table_name='kitchen_stations')
    op.drop_index(op.f('ix_kitchen_stations_station_type'), table_name='kitchen_stations')
    op.drop_index('idx_station_type_status', table_name='kitchen_stations')
    op.drop_table('kitchen_stations')
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS displaystatus")
    op.execute("DROP TYPE IF EXISTS stationstatus")
    op.execute("DROP TYPE IF EXISTS stationtype")