"""create core models

Revision ID: create_core_models_20250111
Revises: 
Create Date: 2025-01-11 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'create_core_models_20250111'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create restaurants table
    op.create_table('restaurants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('legal_name', sa.String(length=200), nullable=True),
        sa.Column('brand_name', sa.String(length=200), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('website', sa.String(length=500), nullable=True),
        sa.Column('address_line1', sa.String(length=255), nullable=False),
        sa.Column('address_line2', sa.String(length=255), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('state', sa.String(length=50), nullable=False),
        sa.Column('postal_code', sa.String(length=20), nullable=False),
        sa.Column('country', sa.String(length=2), nullable=False),
        sa.Column('tax_id', sa.String(length=50), nullable=True),
        sa.Column('business_license', sa.String(length=100), nullable=True),
        sa.Column('timezone', sa.String(length=50), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('status', sa.Enum('ACTIVE', 'INACTIVE', 'SUSPENDED', 'PENDING', 'CLOSED', 
                                    name='restaurantstatus'), nullable=False),
        sa.Column('operating_hours', sa.JSON(), nullable=True),
        sa.Column('features', sa.JSON(), nullable=True),
        sa.Column('subscription_tier', sa.String(length=50), nullable=True),
        sa.Column('subscription_valid_until', sa.DateTime(), nullable=True),
        sa.Column('settings', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index(op.f('ix_restaurants_id'), 'restaurants', ['id'], unique=False)
    op.create_index(op.f('ix_restaurants_status'), 'restaurants', ['status'], unique=False)

    # Create locations table
    op.create_table('locations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('restaurant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('location_type', sa.Enum('RESTAURANT', 'KITCHEN', 'WAREHOUSE', 'OFFICE', 'OTHER', 
                                          name='locationtype'), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=True),
        sa.Column('address_line1', sa.String(length=255), nullable=True),
        sa.Column('address_line2', sa.String(length=255), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=50), nullable=True),
        sa.Column('postal_code', sa.String(length=20), nullable=True),
        sa.Column('country', sa.String(length=2), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('manager_name', sa.String(length=200), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_primary', sa.Boolean(), nullable=True),
        sa.Column('seating_capacity', sa.Integer(), nullable=True),
        sa.Column('parking_spaces', sa.Integer(), nullable=True),
        sa.Column('features', sa.JSON(), nullable=True),
        sa.Column('operating_hours', sa.JSON(), nullable=True),
        sa.Column('settings', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_locations_id'), 'locations', ['id'], unique=False)
    op.create_index(op.f('ix_locations_restaurant_id'), 'locations', ['restaurant_id'], unique=False)

    # Check if floors table already exists (it might have been created by tables module)
    # If it doesn't exist, create it
    conn = op.get_bind()
    result = conn.execute(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'floors')"
    )
    floors_exists = result.scalar()
    
    if not floors_exists:
        op.create_table('floors',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('restaurant_id', sa.Integer(), nullable=False),
            sa.Column('location_id', sa.Integer(), nullable=True),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('display_name', sa.String(length=100), nullable=True),
            sa.Column('floor_number', sa.Integer(), nullable=True),
            sa.Column('width', sa.Integer(), nullable=False),
            sa.Column('height', sa.Integer(), nullable=False),
            sa.Column('background_image', sa.String(length=500), nullable=True),
            sa.Column('grid_size', sa.Integer(), nullable=True),
            sa.Column('status', sa.Enum('ACTIVE', 'INACTIVE', 'MAINTENANCE', name='floorstatus'), nullable=True),
            sa.Column('is_default', sa.Boolean(), nullable=True),
            sa.Column('max_capacity', sa.Integer(), nullable=True),
            sa.Column('allows_reservations', sa.Boolean(), nullable=True),
            sa.Column('service_charge_percent', sa.DECIMAL(precision=5, scale=2), nullable=True),
            sa.Column('layout_config', sa.JSON(), nullable=True),
            sa.Column('features', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ),
            sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('restaurant_id', 'name', name='uix_floor_restaurant_name')
        )
        op.create_index(op.f('ix_floors_id'), 'floors', ['id'], unique=False)
        op.create_index(op.f('ix_floors_restaurant_id'), 'floors', ['restaurant_id'], unique=False)
    else:
        # If floors table exists, we might need to add missing columns
        # Add location_id column if it doesn't exist
        try:
            op.add_column('floors', sa.Column('location_id', sa.Integer(), nullable=True))
            op.create_foreign_key('fk_floors_location_id', 'floors', 'locations', ['location_id'], ['id'])
        except:
            pass  # Column might already exist
        
        # Add other columns that might be missing
        columns_to_add = [
            ('allows_reservations', sa.Boolean(), True),
            ('service_charge_percent', sa.DECIMAL(precision=5, scale=2), None),
            ('features', sa.JSON(), {})
        ]
        
        for col_name, col_type, default_val in columns_to_add:
            try:
                op.add_column('floors', sa.Column(col_name, col_type, nullable=True, default=default_val))
            except:
                pass  # Column might already exist

    # Insert default restaurant for development/testing
    op.execute("""
        INSERT INTO restaurants (
            name, legal_name, email, phone, 
            address_line1, city, state, postal_code, country,
            timezone, currency, status,
            operating_hours, features, settings,
            subscription_tier, created_at
        ) VALUES (
            'Demo Restaurant', 'Demo Restaurant LLC', 'demo@auraconnect.ai', '+1234567890',
            '123 Main Street', 'New York', 'NY', '10001', 'US',
            'America/New_York', 'USD', 'ACTIVE',
            '{"monday": {"open": "09:00", "close": "22:00"}, "tuesday": {"open": "09:00", "close": "22:00"}, 
              "wednesday": {"open": "09:00", "close": "22:00"}, "thursday": {"open": "09:00", "close": "22:00"}, 
              "friday": {"open": "09:00", "close": "23:00"}, "saturday": {"open": "09:00", "close": "23:00"}, 
              "sunday": {"open": "10:00", "close": "21:00"}}',
            '{"pos_integration": true, "online_ordering": true, "table_management": true}',
            '{"theme": "modern", "language": "en"}',
            'premium', NOW()
        ) ON CONFLICT (email) DO NOTHING;
    """)

    # Insert default location
    op.execute("""
        INSERT INTO locations (
            restaurant_id, name, location_type, code, is_active, is_primary,
            address_line1, city, state, postal_code, country,
            seating_capacity, created_at
        ) 
        SELECT 
            id, 'Main Dining Room', 'RESTAURANT', 'MAIN', true, true,
            address_line1, city, state, postal_code, country,
            100, NOW()
        FROM restaurants 
        WHERE email = 'demo@auraconnect.ai'
        LIMIT 1;
    """)

    # Insert default floor
    op.execute("""
        INSERT INTO floors (
            restaurant_id, name, display_name, floor_number,
            width, height, grid_size, status, is_default,
            max_capacity, allows_reservations, created_at
        )
        SELECT 
            id, 'Main Floor', 'Main Dining Area', 1,
            1000, 800, 20, 'ACTIVE', true,
            100, true, NOW()
        FROM restaurants 
        WHERE email = 'demo@auraconnect.ai'
        ON CONFLICT (restaurant_id, name) DO NOTHING;
    """)


def downgrade():
    # Drop tables in reverse order due to foreign key constraints
    op.drop_index(op.f('ix_floors_restaurant_id'), table_name='floors')
    op.drop_index(op.f('ix_floors_id'), table_name='floors')
    op.drop_table('floors')
    
    op.drop_index(op.f('ix_locations_restaurant_id'), table_name='locations')
    op.drop_index(op.f('ix_locations_id'), table_name='locations')
    op.drop_table('locations')
    
    op.drop_index(op.f('ix_restaurants_status'), table_name='restaurants')
    op.drop_index(op.f('ix_restaurants_id'), table_name='restaurants')
    op.drop_table('restaurants')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS floorstatus')
    op.execute('DROP TYPE IF EXISTS locationtype')
    op.execute('DROP TYPE IF EXISTS restaurantstatus')