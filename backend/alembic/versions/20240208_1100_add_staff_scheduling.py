"""Add staff scheduling tables

Revision ID: add_staff_scheduling
Revises: add_biometric_auth
Create Date: 2024-02-08 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_staff_scheduling'
down_revision = 'add_biometric_auth'
branch_labels = None
depends_on = None


def upgrade():
    # Create scheduling enums
    op.execute("""
        CREATE TYPE shifttype AS ENUM ('morning', 'afternoon', 'evening', 'night', 'custom');
        CREATE TYPE shiftstatus AS ENUM ('scheduled', 'published', 'in_progress', 'completed', 'cancelled');
        CREATE TYPE availabilitystatus AS ENUM ('available', 'unavailable', 'limited');
        CREATE TYPE swaprequeststatus AS ENUM ('pending', 'approved', 'rejected', 'cancelled');
    """)
    
    # Create shift_templates table
    op.create_table('shift_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('restaurant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('type', sa.Enum('morning', 'afternoon', 'evening', 'night', 'custom', name='shifttype'), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('break_duration', sa.Integer(), nullable=True),
        sa.Column('min_staff', sa.Integer(), nullable=True),
        sa.Column('max_staff', sa.Integer(), nullable=True),
        sa.Column('color', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_shift_templates_id', 'shift_templates', ['id'])
    op.create_index('ix_shift_templates_restaurant_id', 'shift_templates', ['restaurant_id'])
    
    # Create scheduled_shifts table
    op.create_table('scheduled_shifts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('restaurant_id', sa.Integer(), nullable=False),
        sa.Column('staff_id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('actual_start', sa.DateTime(), nullable=True),
        sa.Column('actual_end', sa.DateTime(), nullable=True),
        sa.Column('break_duration', sa.Integer(), nullable=True),
        sa.Column('status', sa.Enum('scheduled', 'published', 'in_progress', 'completed', 'cancelled', name='shiftstatus'), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ),
        sa.ForeignKeyConstraint(['staff_id'], ['staff_members.id'], ),
        sa.ForeignKeyConstraint(['template_id'], ['shift_templates.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scheduled_shifts_id', 'scheduled_shifts', ['id'])
    op.create_index('ix_scheduled_shifts_date', 'scheduled_shifts', ['date'])
    op.create_index('ix_scheduled_shifts_restaurant_id', 'scheduled_shifts', ['restaurant_id'])
    op.create_index('ix_scheduled_shifts_staff_id', 'scheduled_shifts', ['staff_id'])
    
    # Create staff_availability table
    op.create_table('staff_availability',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('staff_id', sa.Integer(), nullable=False),
        sa.Column('day_of_week', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=True),
        sa.Column('end_time', sa.Time(), nullable=True),
        sa.Column('status', sa.Enum('available', 'unavailable', 'limited', name='availabilitystatus'), nullable=False),
        sa.Column('effective_from', sa.Date(), nullable=True),
        sa.Column('effective_until', sa.Date(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['staff_id'], ['staff_members.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_staff_availability_id', 'staff_availability', ['id'])
    op.create_index('ix_staff_availability_staff_id', 'staff_availability', ['staff_id'])
    
    # Create time_off_requests table
    op.create_table('time_off_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('staff_id', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('reason', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['staff_id'], ['staff_members.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_time_off_requests_id', 'time_off_requests', ['id'])
    op.create_index('ix_time_off_requests_staff_id', 'time_off_requests', ['staff_id'])
    op.create_index('ix_time_off_requests_start_date', 'time_off_requests', ['start_date'])
    
    # Create shift_swap_requests table
    op.create_table('shift_swap_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shift_id', sa.Integer(), nullable=False),
        sa.Column('requester_id', sa.Integer(), nullable=False),
        sa.Column('target_staff_id', sa.Integer(), nullable=True),
        sa.Column('reason', sa.String(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', 'cancelled', name='swaprequeststatus'), nullable=False),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['requester_id'], ['staff_members.id'], ),
        sa.ForeignKeyConstraint(['shift_id'], ['scheduled_shifts.id'], ),
        sa.ForeignKeyConstraint(['target_staff_id'], ['staff_members.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_shift_swap_requests_id', 'shift_swap_requests', ['id'])
    op.create_index('ix_shift_swap_requests_shift_id', 'shift_swap_requests', ['shift_id'])
    
    # Add scheduling-related columns to staff_members if they don't exist
    op.execute("""
        DO $$ 
        BEGIN 
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='staff_members' AND column_name='max_hours_per_week') THEN
                ALTER TABLE staff_members ADD COLUMN max_hours_per_week INTEGER;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='staff_members' AND column_name='min_hours_per_week') THEN
                ALTER TABLE staff_members ADD COLUMN min_hours_per_week INTEGER;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='staff_members' AND column_name='preferred_shifts') THEN
                ALTER TABLE staff_members ADD COLUMN preferred_shifts TEXT;
            END IF;
        END $$;
    """)


def downgrade():
    # Drop indexes
    op.drop_index('ix_shift_swap_requests_shift_id', table_name='shift_swap_requests')
    op.drop_index('ix_shift_swap_requests_id', table_name='shift_swap_requests')
    op.drop_index('ix_time_off_requests_start_date', table_name='time_off_requests')
    op.drop_index('ix_time_off_requests_staff_id', table_name='time_off_requests')
    op.drop_index('ix_time_off_requests_id', table_name='time_off_requests')
    op.drop_index('ix_staff_availability_staff_id', table_name='staff_availability')
    op.drop_index('ix_staff_availability_id', table_name='staff_availability')
    op.drop_index('ix_scheduled_shifts_staff_id', table_name='scheduled_shifts')
    op.drop_index('ix_scheduled_shifts_restaurant_id', table_name='scheduled_shifts')
    op.drop_index('ix_scheduled_shifts_date', table_name='scheduled_shifts')
    op.drop_index('ix_scheduled_shifts_id', table_name='scheduled_shifts')
    op.drop_index('ix_shift_templates_restaurant_id', table_name='shift_templates')
    op.drop_index('ix_shift_templates_id', table_name='shift_templates')
    
    # Drop tables
    op.drop_table('shift_swap_requests')
    op.drop_table('time_off_requests')
    op.drop_table('staff_availability')
    op.drop_table('scheduled_shifts')
    op.drop_table('shift_templates')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS swaprequeststatus')
    op.execute('DROP TYPE IF EXISTS availabilitystatus')
    op.execute('DROP TYPE IF EXISTS shiftstatus')
    op.execute('DROP TYPE IF EXISTS shifttype')
    
    # Remove columns from staff_members
    op.execute("""
        ALTER TABLE staff_members 
        DROP COLUMN IF EXISTS max_hours_per_week,
        DROP COLUMN IF EXISTS min_hours_per_week,
        DROP COLUMN IF EXISTS preferred_shifts;
    """)