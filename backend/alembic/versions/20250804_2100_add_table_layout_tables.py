"""Add table layout and management tables

Revision ID: 20250804_2100
Revises: 20250804_2000
Create Date: 2025-08-04 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250804_2100'
down_revision = '20250804_2000'
branch_labels = None
depends_on = None


def upgrade():
    # Create floors table
    op.create_table(
        'floors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('restaurant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=True),
        sa.Column('floor_number', sa.Integer(), server_default='1', nullable=False),
        sa.Column('width', sa.Integer(), server_default='1000', nullable=False),
        sa.Column('height', sa.Integer(), server_default='800', nullable=False),
        sa.Column('background_image', sa.String(length=500), nullable=True),
        sa.Column('grid_size', sa.Integer(), server_default='20', nullable=False),
        sa.Column('status', sa.Enum('active', 'inactive', 'maintenance', name='floorstatus'), nullable=False, server_default='active'),
        sa.Column('is_default', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('max_capacity', sa.Integer(), nullable=True),
        sa.Column('layout_config', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], name='fk_floors_restaurant'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('restaurant_id', 'name', name='uix_floor_restaurant_name')
    )
    op.create_index('ix_floors_restaurant_id', 'floors', ['restaurant_id'])
    op.create_index('ix_floors_status', 'floors', ['status'])

    # Create tables table
    op.create_table(
        'tables',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('restaurant_id', sa.Integer(), nullable=False),
        sa.Column('floor_id', sa.Integer(), nullable=False),
        sa.Column('table_number', sa.String(length=20), nullable=False),
        sa.Column('display_name', sa.String(length=50), nullable=True),
        sa.Column('min_capacity', sa.Integer(), server_default='1', nullable=False),
        sa.Column('max_capacity', sa.Integer(), nullable=False),
        sa.Column('preferred_capacity', sa.Integer(), nullable=True),
        sa.Column('position_x', sa.Integer(), server_default='0', nullable=False),
        sa.Column('position_y', sa.Integer(), server_default='0', nullable=False),
        sa.Column('width', sa.Integer(), server_default='100', nullable=False),
        sa.Column('height', sa.Integer(), server_default='100', nullable=False),
        sa.Column('rotation', sa.Integer(), server_default='0', nullable=False),
        sa.Column('shape', sa.Enum('square', 'rectangle', 'circle', 'oval', 'hexagon', 'custom', name='tableshape'), 
                  nullable=False, server_default='rectangle'),
        sa.Column('color', sa.String(length=7), nullable=True),
        sa.Column('status', sa.Enum('available', 'occupied', 'reserved', 'blocked', 'cleaning', 'maintenance', name='tablestatus'), 
                  nullable=False, server_default='available'),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('is_combinable', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('has_power_outlet', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_wheelchair_accessible', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_by_window', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_private', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('section', sa.String(length=50), nullable=True),
        sa.Column('zone', sa.String(length=50), nullable=True),
        sa.Column('server_station', sa.String(length=50), nullable=True),
        sa.Column('qr_code', sa.String(length=200), nullable=True),
        sa.Column('properties', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.CheckConstraint('min_capacity <= max_capacity', name='chk_table_capacity'),
        sa.CheckConstraint('rotation >= 0 AND rotation < 360', name='chk_table_rotation'),
        sa.ForeignKeyConstraint(['floor_id'], ['floors.id'], name='fk_tables_floor'),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], name='fk_tables_restaurant'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('restaurant_id', 'table_number', name='uix_table_restaurant_number')
    )
    op.create_index('ix_tables_restaurant_id', 'tables', ['restaurant_id'])
    op.create_index('ix_tables_floor_id', 'tables', ['floor_id'])
    op.create_index('ix_tables_status', 'tables', ['status'])
    op.create_index('ix_tables_section', 'tables', ['section'])

    # Create table_sessions table
    op.create_table(
        'table_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('restaurant_id', sa.Integer(), nullable=False),
        sa.Column('table_id', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('guest_count', sa.Integer(), nullable=False),
        sa.Column('guest_name', sa.String(length=100), nullable=True),
        sa.Column('guest_phone', sa.String(length=20), nullable=True),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('server_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name='fk_sessions_order'),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], name='fk_sessions_restaurant'),
        sa.ForeignKeyConstraint(['server_id'], ['staff.id'], name='fk_sessions_server'),
        sa.ForeignKeyConstraint(['table_id'], ['tables.id'], name='fk_sessions_table'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_table_sessions_restaurant_id', 'table_sessions', ['restaurant_id'])
    op.create_index('ix_table_sessions_table_id', 'table_sessions', ['table_id'])
    op.create_index('ix_table_sessions_start_time', 'table_sessions', ['start_time'])
    op.create_index('ix_table_sessions_end_time', 'table_sessions', ['end_time'])

    # Create table_combinations table
    op.create_table(
        'table_combinations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('table_id', sa.Integer(), nullable=False),
        sa.Column('is_primary', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['table_sessions.id'], name='fk_combinations_session'),
        sa.ForeignKeyConstraint(['table_id'], ['tables.id'], name='fk_combinations_table'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id', 'table_id', name='uix_combination_session_table')
    )
    op.create_index('ix_table_combinations_session_id', 'table_combinations', ['session_id'])

    # Create table_reservations table
    op.create_table(
        'table_reservations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('restaurant_id', sa.Integer(), nullable=False),
        sa.Column('table_id', sa.Integer(), nullable=True),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('reservation_code', sa.String(length=20), nullable=False),
        sa.Column('reservation_date', sa.DateTime(), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), server_default='120', nullable=False),
        sa.Column('guest_count', sa.Integer(), nullable=False),
        sa.Column('guest_name', sa.String(length=100), nullable=False),
        sa.Column('guest_phone', sa.String(length=20), nullable=False),
        sa.Column('guest_email', sa.String(length=100), nullable=True),
        sa.Column('special_requests', sa.String(length=500), nullable=True),
        sa.Column('occasion', sa.String(length=50), nullable=True),
        sa.Column('status', sa.Enum('pending', 'confirmed', 'seated', 'completed', 'cancelled', 'no_show', name='reservationstatus'), 
                  nullable=False, server_default='pending'),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('seated_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('cancellation_reason', sa.String(length=200), nullable=True),
        sa.Column('table_preferences', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('deposit_amount', sa.DECIMAL(precision=10, scale=2), nullable=True),
        sa.Column('deposit_paid', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('reminder_sent', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('reminder_sent_at', sa.DateTime(), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.CheckConstraint('guest_count > 0', name='chk_reservation_guest_count'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], name='fk_reservations_customer'),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], name='fk_reservations_restaurant'),
        sa.ForeignKeyConstraint(['table_id'], ['tables.id'], name='fk_reservations_table'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reservation_code', name='uix_reservation_code')
    )
    op.create_index('ix_table_reservations_restaurant_id', 'table_reservations', ['restaurant_id'])
    op.create_index('ix_table_reservations_reservation_date', 'table_reservations', ['reservation_date'])
    op.create_index('ix_table_reservations_status', 'table_reservations', ['status'])
    op.create_index('ix_table_reservations_customer_id', 'table_reservations', ['customer_id'])

    # Create table_layouts table
    op.create_table(
        'table_layouts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('restaurant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('layout_data', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('active_days', sa.JSON(), nullable=True),
        sa.Column('active_from_time', sa.String(length=5), nullable=True),
        sa.Column('active_to_time', sa.String(length=5), nullable=True),
        sa.Column('event_date', sa.DateTime(), nullable=True),
        sa.Column('event_name', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], name='fk_layouts_restaurant'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('restaurant_id', 'name', name='uix_layout_restaurant_name')
    )
    op.create_index('ix_table_layouts_restaurant_id', 'table_layouts', ['restaurant_id'])
    op.create_index('ix_table_layouts_is_active', 'table_layouts', ['is_active'])

    # Create table_state_logs table
    op.create_table(
        'table_state_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('restaurant_id', sa.Integer(), nullable=False),
        sa.Column('table_id', sa.Integer(), nullable=False),
        sa.Column('previous_status', sa.Enum('available', 'occupied', 'reserved', 'blocked', 'cleaning', 'maintenance', name='tablestatus'), 
                  nullable=True),
        sa.Column('new_status', sa.Enum('available', 'occupied', 'reserved', 'blocked', 'cleaning', 'maintenance', name='tablestatus'), 
                  nullable=False),
        sa.Column('changed_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('changed_by_id', sa.Integer(), nullable=True),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('reservation_id', sa.Integer(), nullable=True),
        sa.Column('reason', sa.String(length=200), nullable=True),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['changed_by_id'], ['staff.id'], name='fk_state_logs_changed_by'),
        sa.ForeignKeyConstraint(['reservation_id'], ['table_reservations.id'], name='fk_state_logs_reservation'),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], name='fk_state_logs_restaurant'),
        sa.ForeignKeyConstraint(['session_id'], ['table_sessions.id'], name='fk_state_logs_session'),
        sa.ForeignKeyConstraint(['table_id'], ['tables.id'], name='fk_state_logs_table'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_table_state_logs_restaurant_id', 'table_state_logs', ['restaurant_id'])
    op.create_index('ix_table_state_logs_table_id', 'table_state_logs', ['table_id'])
    op.create_index('ix_table_state_logs_changed_at', 'table_state_logs', ['changed_at'])

    # Create triggers for updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    for table in ['floors', 'tables', 'table_sessions', 'table_combinations', 
                  'table_reservations', 'table_layouts', 'table_state_logs']:
        op.execute(f"""
            CREATE TRIGGER update_{table}_updated_at BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)


def downgrade():
    # Drop triggers
    for table in ['floors', 'tables', 'table_sessions', 'table_combinations', 
                  'table_reservations', 'table_layouts', 'table_state_logs']:
        op.execute(f"DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};")
    
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")
    
    # Drop tables
    op.drop_table('table_state_logs')
    op.drop_table('table_layouts')
    op.drop_table('table_reservations')
    op.drop_table('table_combinations')
    op.drop_table('table_sessions')
    op.drop_table('tables')
    op.drop_table('floors')
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS floorstatus;")
    op.execute("DROP TYPE IF EXISTS tablestatus;")
    op.execute("DROP TYPE IF EXISTS tableshape;")
    op.execute("DROP TYPE IF EXISTS reservationstatus;")