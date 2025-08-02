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
    # Create scheduling enums matching the code exactly
    op.execute("""
        CREATE TYPE shiftstatus AS ENUM ('draft', 'published', 'in_progress', 'completed', 'cancelled');
        CREATE TYPE shifttype AS ENUM ('regular', 'overtime', 'holiday', 'training', 'meeting');
        CREATE TYPE recurrencetype AS ENUM ('none', 'daily', 'weekly', 'biweekly', 'monthly');
        CREATE TYPE availabilitystatus AS ENUM ('available', 'unavailable', 'preferred', 'limited');
        CREATE TYPE swapstatus AS ENUM ('pending', 'approved', 'rejected', 'cancelled');
        CREATE TYPE breaktype AS ENUM ('meal', 'rest', 'paid', 'unpaid');
    """)
    
    # Create shift_templates table
    op.create_table('shift_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('role_id', sa.Integer(), nullable=True),
        sa.Column('location_id', sa.Integer(), nullable=True),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('recurrence_type', sa.Enum('none', 'daily', 'weekly', 'biweekly', 'monthly', name='recurrencetype'), nullable=True),
        sa.Column('recurrence_days', sa.JSON(), nullable=True),
        sa.Column('min_staff', sa.Integer(), nullable=True, default=1),
        sa.Column('max_staff', sa.Integer(), nullable=True),
        sa.Column('preferred_staff', sa.Integer(), nullable=True),
        sa.Column('estimated_hourly_rate', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_shift_templates_id', 'shift_templates', ['id'])
    op.create_index('ix_shift_templates_location_id', 'shift_templates', ['location_id'])
    op.create_index('ix_shift_templates_is_active', 'shift_templates', ['is_active'])
    
    # Create enhanced_shifts table (main shift table)
    op.create_table('enhanced_shifts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('staff_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=True),
        sa.Column('location_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('shift_type', sa.Enum('regular', 'overtime', 'holiday', 'training', 'meeting', name='shifttype'), nullable=True, default='regular'),
        sa.Column('status', sa.Enum('draft', 'published', 'in_progress', 'completed', 'cancelled', name='shiftstatus'), nullable=True, default='draft'),
        sa.Column('template_id', sa.Integer(), nullable=True),
        sa.Column('hourly_rate', sa.Float(), nullable=True),
        sa.Column('estimated_cost', sa.Float(), nullable=True),
        sa.Column('actual_cost', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('color', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint('end_time > start_time', name='check_shift_times'),
        sa.ForeignKeyConstraint(['created_by_id'], ['staff_members.id'], ),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
        sa.ForeignKeyConstraint(['staff_id'], ['staff_members.id'], ),
        sa.ForeignKeyConstraint(['template_id'], ['shift_templates.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_enhanced_shifts_id', 'enhanced_shifts', ['id'])
    op.create_index('ix_enhanced_shifts_date', 'enhanced_shifts', ['date'])
    op.create_index('ix_enhanced_shifts_location_id', 'enhanced_shifts', ['location_id'])
    op.create_index('ix_enhanced_shifts_staff_id', 'enhanced_shifts', ['staff_id'])
    op.create_index('ix_enhanced_shifts_status', 'enhanced_shifts', ['status'])
    op.create_index('ix_enhanced_shifts_staff_date', 'enhanced_shifts', ['staff_id', 'date'])
    op.create_index('ix_enhanced_shifts_location_date', 'enhanced_shifts', ['location_id', 'date'])
    
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
    
    # Create shift_swaps table
    op.create_table('shift_swaps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('requester_id', sa.Integer(), nullable=False),
        sa.Column('from_shift_id', sa.Integer(), nullable=False),
        sa.Column('to_shift_id', sa.Integer(), nullable=True),
        sa.Column('to_staff_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', 'cancelled', name='swapstatus'), nullable=False, default='pending'),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('manager_notes', sa.Text(), nullable=True),
        sa.Column('requested_at', sa.DateTime(), nullable=False),
        sa.Column('approved_by_id', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['approved_by_id'], ['staff_members.id'], ),
        sa.ForeignKeyConstraint(['requester_id'], ['staff_members.id'], ),
        sa.ForeignKeyConstraint(['from_shift_id'], ['enhanced_shifts.id'], ),
        sa.ForeignKeyConstraint(['to_shift_id'], ['enhanced_shifts.id'], ),
        sa.ForeignKeyConstraint(['to_staff_id'], ['staff_members.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_shift_swaps_from_shift_id', 'shift_swaps', ['from_shift_id'])
    op.create_index('ix_shift_swaps_status', 'shift_swaps', ['status'])
    
    # Create shift_breaks table
    op.create_table('shift_breaks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shift_id', sa.Integer(), nullable=False),
        sa.Column('break_type', sa.Enum('meal', 'rest', 'paid', 'unpaid', name='breaktype'), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('is_paid', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['shift_id'], ['enhanced_shifts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_shift_breaks_shift_id', 'shift_breaks', ['shift_id'])
    
    # Create shift_requirements table
    op.create_table('shift_requirements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=False),
        sa.Column('skill_id', sa.Integer(), nullable=True),
        sa.Column('certification_id', sa.Integer(), nullable=True),
        sa.Column('minimum_experience_months', sa.Integer(), nullable=True),
        sa.Column('is_mandatory', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['template_id'], ['shift_templates.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_shift_requirements_template_id', 'shift_requirements', ['template_id'])
    
    # Create schedule_publications table
    op.create_table('schedule_publications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('location_id', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('published_by_id', sa.Integer(), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=False),
        sa.Column('published_shift_count', sa.Integer(), nullable=True),
        sa.Column('notification_sent', sa.Boolean(), nullable=True, default=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['published_by_id'], ['staff_members.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_schedule_publications_location_id', 'schedule_publications', ['location_id'])
    op.create_index('ix_schedule_publications_published_at', 'schedule_publications', ['published_at'])
    
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
    op.drop_index('ix_schedule_publications_published_at', table_name='schedule_publications')
    op.drop_index('ix_schedule_publications_location_id', table_name='schedule_publications')
    op.drop_index('ix_shift_requirements_template_id', table_name='shift_requirements')
    op.drop_index('ix_shift_breaks_shift_id', table_name='shift_breaks')
    op.drop_index('ix_shift_swaps_status', table_name='shift_swaps')
    op.drop_index('ix_shift_swaps_from_shift_id', table_name='shift_swaps')
    op.drop_index('ix_time_off_requests_start_date', table_name='time_off_requests')
    op.drop_index('ix_time_off_requests_staff_id', table_name='time_off_requests')
    op.drop_index('ix_time_off_requests_id', table_name='time_off_requests')
    op.drop_index('ix_staff_availability_staff_id', table_name='staff_availability')
    op.drop_index('ix_staff_availability_id', table_name='staff_availability')
    op.drop_index('ix_enhanced_shifts_location_date', table_name='enhanced_shifts')
    op.drop_index('ix_enhanced_shifts_staff_date', table_name='enhanced_shifts')
    op.drop_index('ix_enhanced_shifts_status', table_name='enhanced_shifts')
    op.drop_index('ix_enhanced_shifts_staff_id', table_name='enhanced_shifts')
    op.drop_index('ix_enhanced_shifts_location_id', table_name='enhanced_shifts')
    op.drop_index('ix_enhanced_shifts_date', table_name='enhanced_shifts')
    op.drop_index('ix_enhanced_shifts_id', table_name='enhanced_shifts')
    op.drop_index('ix_shift_templates_is_active', table_name='shift_templates')
    op.drop_index('ix_shift_templates_location_id', table_name='shift_templates')
    op.drop_index('ix_shift_templates_id', table_name='shift_templates')
    
    # Drop tables
    op.drop_table('schedule_publications')
    op.drop_table('shift_requirements')
    op.drop_table('shift_breaks')
    op.drop_table('shift_swaps')
    op.drop_table('time_off_requests')
    op.drop_table('staff_availability')
    op.drop_table('enhanced_shifts')
    op.drop_table('shift_templates')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS breaktype')
    op.execute('DROP TYPE IF EXISTS swapstatus')
    op.execute('DROP TYPE IF EXISTS availabilitystatus')
    op.execute('DROP TYPE IF EXISTS recurrencetype')
    op.execute('DROP TYPE IF EXISTS shifttype')
    op.execute('DROP TYPE IF EXISTS shiftstatus')
    
    # Remove columns from staff_members
    op.execute("""
        ALTER TABLE staff_members 
        DROP COLUMN IF EXISTS max_hours_per_week,
        DROP COLUMN IF EXISTS min_hours_per_week,
        DROP COLUMN IF EXISTS preferred_shifts;
    """)