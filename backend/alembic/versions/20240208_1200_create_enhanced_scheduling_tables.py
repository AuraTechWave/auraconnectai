"""Create enhanced scheduling tables

Revision ID: create_enhanced_scheduling
Revises: add_staff_scheduling
Create Date: 2024-02-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'create_enhanced_scheduling'
down_revision = 'add_staff_scheduling'
branch_labels = None
depends_on = None


def upgrade():
    # Create new enums for enhanced scheduling
    op.execute("""
        CREATE TYPE shiftstatus AS ENUM ('draft', 'scheduled', 'published', 'in_progress', 'completed', 'cancelled');
        CREATE TYPE shifttype AS ENUM ('regular', 'overtime', 'training', 'meeting', 'break_cover');
        CREATE TYPE recurrencetype AS ENUM ('none', 'daily', 'weekly', 'biweekly', 'monthly', 'custom');
        CREATE TYPE dayofweek AS ENUM ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday');
        CREATE TYPE breaktype AS ENUM ('meal', 'rest', 'personal');
        CREATE TYPE swapstatus AS ENUM ('pending', 'approved', 'rejected', 'cancelled', 'expired');
    """)
    
    # Create enhanced_shifts table (replacing scheduled_shifts)
    op.create_table('enhanced_shifts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('staff_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=True),
        sa.Column('location_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('shift_type', sa.Enum('regular', 'overtime', 'training', 'meeting', 'break_cover', name='shifttype'), nullable=True),
        sa.Column('status', sa.Enum('draft', 'scheduled', 'published', 'in_progress', 'completed', 'cancelled', name='shiftstatus'), nullable=True),
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
    
    # Create indexes for enhanced_shifts
    op.create_index('ix_enhanced_shifts_id', 'enhanced_shifts', ['id'])
    op.create_index('ix_enhanced_shifts_date', 'enhanced_shifts', ['date'])
    op.create_index('ix_enhanced_shifts_location_id', 'enhanced_shifts', ['location_id'])
    op.create_index('ix_enhanced_shifts_staff_id', 'enhanced_shifts', ['staff_id'])
    op.create_index('ix_enhanced_shifts_status', 'enhanced_shifts', ['status'])
    op.create_index('ix_enhanced_shifts_staff_date', 'enhanced_shifts', ['staff_id', 'date'])
    op.create_index('ix_enhanced_shifts_location_date', 'enhanced_shifts', ['location_id', 'date'])
    
    # Update shift_templates to match the model
    op.add_column('shift_templates', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('shift_templates', sa.Column('role_id', sa.Integer(), nullable=True))
    op.add_column('shift_templates', sa.Column('recurrence_type', sa.Enum('none', 'daily', 'weekly', 'biweekly', 'monthly', 'custom', name='recurrencetype'), nullable=True))
    op.add_column('shift_templates', sa.Column('recurrence_days', sa.JSON(), nullable=True))
    op.add_column('shift_templates', sa.Column('preferred_staff', sa.Integer(), nullable=True))
    op.add_column('shift_templates', sa.Column('estimated_hourly_rate', sa.Float(), nullable=True))
    op.create_foreign_key(None, 'shift_templates', 'roles', ['role_id'], ['id'])
    
    # Create shift_breaks table
    op.create_table('shift_breaks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shift_id', sa.Integer(), nullable=False),
        sa.Column('break_type', sa.Enum('meal', 'rest', 'personal', name='breaktype'), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('is_paid', sa.Boolean(), nullable=True),
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
        sa.Column('is_mandatory', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['template_id'], ['shift_templates.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_shift_requirements_template_id', 'shift_requirements', ['template_id'])
    
    # Create shift_swaps table (replacing shift_swap_requests)
    op.create_table('shift_swaps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('from_shift_id', sa.Integer(), nullable=False),
        sa.Column('to_shift_id', sa.Integer(), nullable=True),
        sa.Column('from_staff_id', sa.Integer(), nullable=False),
        sa.Column('to_staff_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', 'cancelled', 'expired', name='swapstatus'), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('manager_notes', sa.Text(), nullable=True),
        sa.Column('requested_at', sa.DateTime(), nullable=False),
        sa.Column('approved_by_id', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['approved_by_id'], ['staff_members.id'], ),
        sa.ForeignKeyConstraint(['from_shift_id'], ['enhanced_shifts.id'], ),
        sa.ForeignKeyConstraint(['from_staff_id'], ['staff_members.id'], ),
        sa.ForeignKeyConstraint(['to_shift_id'], ['enhanced_shifts.id'], ),
        sa.ForeignKeyConstraint(['to_staff_id'], ['staff_members.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_shift_swaps_from_shift_id', 'shift_swaps', ['from_shift_id'])
    op.create_index('ix_shift_swaps_status', 'shift_swaps', ['status'])
    
    # Create schedule_publications table
    op.create_table('schedule_publications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('location_id', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('published_by_id', sa.Integer(), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=False),
        sa.Column('published_shift_count', sa.Integer(), nullable=True),
        sa.Column('notification_sent', sa.Boolean(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['published_by_id'], ['staff_members.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_schedule_publications_location_id', 'schedule_publications', ['location_id'])
    op.create_index('ix_schedule_publications_published_at', 'schedule_publications', ['published_at'])
    
    # Update staff_availability to match the model
    op.execute("""
        ALTER TABLE staff_availability 
        ALTER COLUMN status TYPE availabilitystatus 
        USING status::text::availabilitystatus
    """)
    op.add_column('staff_availability', sa.Column('specific_date', sa.Date(), nullable=True))
    op.add_column('staff_availability', sa.Column('reason', sa.Text(), nullable=True))
    
    # Add recurrence_patterns column if not exists
    op.execute("""
        DO $$ 
        BEGIN 
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='staff_availability' AND column_name='recurrence_pattern') THEN
                ALTER TABLE staff_availability ADD COLUMN recurrence_pattern TEXT;
            END IF;
        END $$;
    """)


def downgrade():
    # Drop indexes
    op.drop_index('ix_schedule_publications_published_at', table_name='schedule_publications')
    op.drop_index('ix_schedule_publications_location_id', table_name='schedule_publications')
    op.drop_index('ix_shift_swaps_status', table_name='shift_swaps')
    op.drop_index('ix_shift_swaps_from_shift_id', table_name='shift_swaps')
    op.drop_index('ix_shift_requirements_template_id', table_name='shift_requirements')
    op.drop_index('ix_shift_breaks_shift_id', table_name='shift_breaks')
    op.drop_index('ix_enhanced_shifts_location_date', table_name='enhanced_shifts')
    op.drop_index('ix_enhanced_shifts_staff_date', table_name='enhanced_shifts')
    op.drop_index('ix_enhanced_shifts_status', table_name='enhanced_shifts')
    op.drop_index('ix_enhanced_shifts_staff_id', table_name='enhanced_shifts')
    op.drop_index('ix_enhanced_shifts_location_id', table_name='enhanced_shifts')
    op.drop_index('ix_enhanced_shifts_date', table_name='enhanced_shifts')
    op.drop_index('ix_enhanced_shifts_id', table_name='enhanced_shifts')
    
    # Drop tables
    op.drop_table('schedule_publications')
    op.drop_table('shift_swaps')
    op.drop_table('shift_requirements')
    op.drop_table('shift_breaks')
    op.drop_table('enhanced_shifts')
    
    # Remove columns from existing tables
    op.drop_column('staff_availability', 'recurrence_pattern')
    op.drop_column('staff_availability', 'reason')
    op.drop_column('staff_availability', 'specific_date')
    
    op.drop_constraint(None, 'shift_templates', type_='foreignkey')
    op.drop_column('shift_templates', 'estimated_hourly_rate')
    op.drop_column('shift_templates', 'preferred_staff')
    op.drop_column('shift_templates', 'recurrence_days')
    op.drop_column('shift_templates', 'recurrence_type')
    op.drop_column('shift_templates', 'role_id')
    op.drop_column('shift_templates', 'description')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS swapstatus')
    op.execute('DROP TYPE IF EXISTS breaktype')
    op.execute('DROP TYPE IF EXISTS dayofweek')
    op.execute('DROP TYPE IF EXISTS recurrencetype')
    op.execute('DROP TYPE IF EXISTS shifttype')
    op.execute('DROP TYPE IF EXISTS shiftstatus')