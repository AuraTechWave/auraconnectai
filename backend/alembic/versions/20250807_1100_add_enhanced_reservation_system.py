"""Add enhanced reservation system with waitlist

Revision ID: 20250807_1100_add_enhanced_reservation_system
Revises: 20250807_1000_add_kds_tables
Create Date: 2025-08-07 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250807_1100_add_enhanced_reservation_system'
down_revision = '20250807_1000_add_kds_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Create enum types with existence checks
    connection = op.get_bind()
    
    # Check and create reservationstatus enum
    connection.execute(sa.text("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type t
                JOIN pg_namespace n ON t.typnamespace = n.oid
                WHERE t.typname = 'reservationstatus'
                AND n.nspname = current_schema()
                AND t.typtype = 'e'
            ) THEN
                CREATE TYPE reservationstatus AS ENUM ('pending', 'confirmed', 'seated', 'completed', 'cancelled', 'no_show', 'waitlist_converted');
            END IF;
        END$$;
    """))
    
    # Check and create waitliststatus enum
    connection.execute(sa.text("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type t
                JOIN pg_namespace n ON t.typnamespace = n.oid
                WHERE t.typname = 'waitliststatus'
                AND n.nspname = current_schema()
                AND t.typtype = 'e'
            ) THEN
                CREATE TYPE waitliststatus AS ENUM ('waiting', 'notified', 'confirmed', 'converted', 'expired', 'cancelled');
            END IF;
        END$$;
    """))
    
    # Check and create notificationmethod enum
    connection.execute(sa.text("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type t
                JOIN pg_namespace n ON t.typnamespace = n.oid
                WHERE t.typname = 'notificationmethod'
                AND n.nspname = current_schema()
                AND t.typtype = 'e'
            ) THEN
                CREATE TYPE notificationmethod AS ENUM ('email', 'sms', 'both', 'none');
            END IF;
        END$$;
    """))
    
    # Check and create auditaction enum
    connection.execute(sa.text("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type t
                JOIN pg_namespace n ON t.typnamespace = n.oid
                WHERE t.typname = 'auditaction'
                AND n.nspname = current_schema()
                AND t.typtype = 'e'
            ) THEN
                CREATE TYPE auditaction AS ENUM ('created', 'updated', 'cancelled', 'confirmed', 'seated', 'completed', 'no_show', 'manual_override', 'table_changed', 'promoted_from_waitlist', 'notification_sent', 'reminder_sent');
            END IF;
        END$$;
    """))
    
    # Update existing reservations table with new columns
    op.execute("""
        ALTER TABLE reservations 
        ADD COLUMN IF NOT EXISTS duration_minutes INTEGER DEFAULT 90,
        ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT 'website',
        ADD COLUMN IF NOT EXISTS table_ids JSONB DEFAULT '[]'::jsonb,
        ADD COLUMN IF NOT EXISTS dietary_restrictions JSONB DEFAULT '[]'::jsonb,
        ADD COLUMN IF NOT EXISTS occasion VARCHAR(100),
        ADD COLUMN IF NOT EXISTS notification_method notificationmethod DEFAULT 'email',
        ADD COLUMN IF NOT EXISTS reminder_sent BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS reminder_sent_at TIMESTAMP WITH TIME ZONE,
        ADD COLUMN IF NOT EXISTS waitlist_id INTEGER,
        ADD COLUMN IF NOT EXISTS converted_from_waitlist BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMP WITH TIME ZONE,
        ADD COLUMN IF NOT EXISTS cancellation_reason TEXT,
        ADD COLUMN IF NOT EXISTS cancelled_by VARCHAR(50),
        ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMP WITH TIME ZONE,
        ADD COLUMN IF NOT EXISTS seated_at TIMESTAMP WITH TIME ZONE,
        ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE
    """)
    
    # Create waitlist table
    op.create_table('waitlist_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('requested_date', sa.Date(), nullable=False),
        sa.Column('requested_time_start', sa.Time(), nullable=False),
        sa.Column('requested_time_end', sa.Time(), nullable=False),
        sa.Column('party_size', sa.Integer(), nullable=False),
        sa.Column('flexible_date', sa.Boolean(), default=False),
        sa.Column('flexible_time', sa.Boolean(), default=False),
        sa.Column('alternative_dates', sa.JSON(), default=list),
        sa.Column('status', postgresql.ENUM('waiting', 'notified', 'confirmed', 'converted', 'expired', 'cancelled', name='waitliststatus'), nullable=False),
        sa.Column('position', sa.Integer()),
        sa.Column('notification_method', postgresql.ENUM('email', 'sms', 'both', 'none', name='notificationmethod'), default='email'),
        sa.Column('notified_at', sa.DateTime(timezone=True)),
        sa.Column('notification_expires_at', sa.DateTime(timezone=True)),
        sa.Column('confirmed_at', sa.DateTime(timezone=True)),
        sa.Column('special_requests', sa.Text()),
        sa.Column('priority', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
        sa.Column('expires_at', sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create reservation settings table
    op.create_table('reservation_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('restaurant_id', sa.Integer(), default=1),
        sa.Column('advance_booking_days', sa.Integer(), default=90),
        sa.Column('min_advance_hours', sa.Integer(), default=2),
        sa.Column('max_party_size', sa.Integer(), default=20),
        sa.Column('min_party_size', sa.Integer(), default=1),
        sa.Column('slot_duration_minutes', sa.Integer(), default=15),
        sa.Column('default_reservation_duration', sa.Integer(), default=90),
        sa.Column('operating_hours', sa.JSON(), default={}),
        sa.Column('total_capacity', sa.Integer(), default=100),
        sa.Column('buffer_percentage', sa.Float(), default=0.1),
        sa.Column('waitlist_enabled', sa.Boolean(), default=True),
        sa.Column('waitlist_notification_window', sa.Integer(), default=30),
        sa.Column('waitlist_auto_expire_hours', sa.Integer(), default=24),
        sa.Column('require_confirmation', sa.Boolean(), default=True),
        sa.Column('confirmation_required_hours', sa.Integer(), default=24),
        sa.Column('auto_cancel_unconfirmed', sa.Boolean(), default=False),
        sa.Column('send_reminders', sa.Boolean(), default=True),
        sa.Column('reminder_hours_before', sa.Integer(), default=24),
        sa.Column('track_no_shows', sa.Boolean(), default=True),
        sa.Column('no_show_threshold', sa.Integer(), default=3),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create table configuration table
    op.create_table('table_configurations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('table_number', sa.String(20), nullable=False, unique=True),
        sa.Column('section', sa.String(50)),
        sa.Column('min_capacity', sa.Integer(), nullable=False),
        sa.Column('max_capacity', sa.Integer(), nullable=False),
        sa.Column('preferred_capacity', sa.Integer()),
        sa.Column('is_combinable', sa.Boolean(), default=True),
        sa.Column('combine_with', sa.JSON(), default=list),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('available_for_reservation', sa.Boolean(), default=True),
        sa.Column('priority', sa.Integer(), default=0),
        sa.Column('features', sa.JSON(), default=list),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create special dates table
    op.create_table('special_dates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False, unique=True),
        sa.Column('name', sa.String(100)),
        sa.Column('is_closed', sa.Boolean(), default=False),
        sa.Column('special_hours', sa.JSON()),
        sa.Column('min_party_size', sa.Integer()),
        sa.Column('max_party_size', sa.Integer()),
        sa.Column('require_deposit', sa.Boolean(), default=False),
        sa.Column('deposit_amount', sa.Float()),
        sa.Column('capacity_modifier', sa.Float(), default=1.0),
        sa.Column('special_menu', sa.Boolean(), default=False),
        sa.Column('price_modifier', sa.Float(), default=1.0),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add foreign key constraint for waitlist_id in reservations
    op.execute("""
        ALTER TABLE reservations 
        ADD CONSTRAINT fk_reservations_waitlist 
        FOREIGN KEY (waitlist_id) REFERENCES waitlist_entries(id)
    """)
    
    # Create indexes for performance
    op.create_index('idx_waitlist_date_status', 'waitlist_entries', ['requested_date', 'status'])
    op.create_index('idx_waitlist_customer_status', 'waitlist_entries', ['customer_id', 'status'])
    op.create_index('idx_reservation_date_time', 'reservations', ['reservation_date', 'reservation_time'])
    op.create_index('idx_reservation_customer_date', 'reservations', ['customer_id', 'reservation_date'])
    op.create_index('idx_reservation_status_date', 'reservations', ['status', 'reservation_date'])
    op.create_index('idx_special_dates_date', 'special_dates', ['date'])
    
    # Insert default reservation settings
    op.execute("""
        INSERT INTO reservation_settings (
            restaurant_id,
            operating_hours
        ) VALUES (
            1,
            '{
                "monday": {"open": "11:00", "close": "22:00"},
                "tuesday": {"open": "11:00", "close": "22:00"},
                "wednesday": {"open": "11:00", "close": "22:00"},
                "thursday": {"open": "11:00", "close": "22:00"},
                "friday": {"open": "11:00", "close": "23:00"},
                "saturday": {"open": "10:00", "close": "23:00"},
                "sunday": {"open": "10:00", "close": "21:00"}
            }'::jsonb
        )
    """)
    
    # Add sample table configurations
    op.execute("""
        INSERT INTO table_configurations (table_number, section, min_capacity, max_capacity, preferred_capacity, features)
        VALUES 
        ('1', 'main', 2, 4, 2, '["window"]'),
        ('2', 'main', 2, 4, 2, '["window"]'),
        ('3', 'main', 4, 6, 4, '[]'),
        ('4', 'main', 4, 6, 4, '[]'),
        ('5', 'main', 2, 4, 2, '["booth"]'),
        ('6', 'main', 2, 4, 2, '["booth"]'),
        ('7', 'main', 6, 8, 6, '["round"]'),
        ('8', 'main', 6, 8, 6, '["round"]'),
        ('P1', 'patio', 2, 4, 2, '["outdoor", "umbrella"]'),
        ('P2', 'patio', 2, 4, 2, '["outdoor", "umbrella"]'),
        ('P3', 'patio', 4, 6, 4, '["outdoor", "heater"]'),
        ('P4', 'patio', 4, 6, 4, '["outdoor", "heater"]'),
        ('B1', 'bar', 1, 2, 1, '["bar", "high-top"]'),
        ('B2', 'bar', 1, 2, 1, '["bar", "high-top"]'),
        ('B3', 'bar', 1, 2, 1, '["bar", "high-top"]'),
        ('B4', 'bar', 1, 2, 1, '["bar", "high-top"]'),
        ('PR1', 'private', 8, 12, 10, '["private", "av-equipped"]'),
        ('PR2', 'private', 12, 20, 16, '["private", "av-equipped"]')
    """)
    
    # Add audit tracking columns to reservations table
    op.execute("""
        ALTER TABLE reservations 
        ADD COLUMN IF NOT EXISTS created_by INTEGER,
        ADD COLUMN IF NOT EXISTS updated_by INTEGER,
        ADD COLUMN IF NOT EXISTS confirmed_by INTEGER,
        ADD COLUMN IF NOT EXISTS seated_by INTEGER,
        ADD COLUMN IF NOT EXISTS completed_by INTEGER,
        ADD CONSTRAINT fk_reservations_created_by FOREIGN KEY (created_by) REFERENCES users(id),
        ADD CONSTRAINT fk_reservations_updated_by FOREIGN KEY (updated_by) REFERENCES users(id),
        ADD CONSTRAINT fk_reservations_confirmed_by FOREIGN KEY (confirmed_by) REFERENCES users(id),
        ADD CONSTRAINT fk_reservations_seated_by FOREIGN KEY (seated_by) REFERENCES users(id),
        ADD CONSTRAINT fk_reservations_completed_by FOREIGN KEY (completed_by) REFERENCES users(id)
    """)
    
    # Create reservation audit log table
    op.create_table('reservation_audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reservation_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('user_id', sa.Integer()),
        sa.Column('user_type', sa.String(20)),
        sa.Column('user_ip', sa.String(45)),
        sa.Column('user_agent', sa.String(255)),
        sa.Column('field_changes', sa.JSON()),
        sa.Column('reason', sa.Text()),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('metadata', sa.JSON()),
        sa.ForeignKeyConstraint(['reservation_id'], ['reservations.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create waitlist audit log table
    op.create_table('waitlist_audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('waitlist_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('user_id', sa.Integer()),
        sa.Column('user_type', sa.String(20)),
        sa.Column('field_changes', sa.JSON()),
        sa.Column('reason', sa.Text()),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('metadata', sa.JSON()),
        sa.ForeignKeyConstraint(['waitlist_id'], ['waitlist_entries.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create scheduled reminders table
    op.create_table('scheduled_reminders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reservation_id', sa.Integer(), nullable=False),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reminder_type', sa.String(50)),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('sent_at', sa.DateTime(timezone=True)),
        sa.Column('metadata', sa.JSON()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['reservation_id'], ['reservations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for audit tables
    op.create_index('idx_reservation_audit_reservation_id', 'reservation_audit_logs', ['reservation_id'])
    op.create_index('idx_reservation_audit_user_id', 'reservation_audit_logs', ['user_id'])
    op.create_index('idx_reservation_audit_timestamp', 'reservation_audit_logs', ['timestamp'])
    op.create_index('idx_reservation_audit_action', 'reservation_audit_logs', ['action'])
    op.create_index('idx_waitlist_audit_waitlist_id', 'waitlist_audit_logs', ['waitlist_id'])
    op.create_index('idx_waitlist_audit_timestamp', 'waitlist_audit_logs', ['timestamp'])
    op.create_index('idx_scheduled_reminders_status_scheduled', 'scheduled_reminders', ['status', 'scheduled_for'])
    
    # Add requested indexes for performance
    op.create_index('idx_reservation_table_id', 'reservations', ['table_ids'])
    op.create_index('idx_table_configurations_table_number', 'table_configurations', ['table_number'])


def downgrade():
    # Drop new indexes
    op.drop_index('idx_table_configurations_table_number', table_name='table_configurations')
    op.drop_index('idx_reservation_table_id', table_name='reservations')
    op.drop_index('idx_scheduled_reminders_status_scheduled', table_name='scheduled_reminders')
    op.drop_index('idx_waitlist_audit_timestamp', table_name='waitlist_audit_logs')
    op.drop_index('idx_waitlist_audit_waitlist_id', table_name='waitlist_audit_logs')
    op.drop_index('idx_reservation_audit_action', table_name='reservation_audit_logs')
    op.drop_index('idx_reservation_audit_timestamp', table_name='reservation_audit_logs')
    op.drop_index('idx_reservation_audit_user_id', table_name='reservation_audit_logs')
    op.drop_index('idx_reservation_audit_reservation_id', table_name='reservation_audit_logs')
    
    # Drop original indexes
    op.drop_index('idx_special_dates_date', table_name='special_dates')
    op.drop_index('idx_reservation_status_date', table_name='reservations')
    op.drop_index('idx_reservation_customer_date', table_name='reservations')
    op.drop_index('idx_reservation_date_time', table_name='reservations')
    op.drop_index('idx_waitlist_customer_status', table_name='waitlist_entries')
    op.drop_index('idx_waitlist_date_status', table_name='waitlist_entries')
    
    # Drop audit tables
    op.drop_table('scheduled_reminders')
    op.drop_table('waitlist_audit_logs')
    op.drop_table('reservation_audit_logs')
    
    # Drop foreign key constraints
    op.execute("""
        ALTER TABLE reservations 
        DROP CONSTRAINT IF EXISTS fk_reservations_completed_by,
        DROP CONSTRAINT IF EXISTS fk_reservations_seated_by,
        DROP CONSTRAINT IF EXISTS fk_reservations_confirmed_by,
        DROP CONSTRAINT IF EXISTS fk_reservations_updated_by,
        DROP CONSTRAINT IF EXISTS fk_reservations_created_by,
        DROP CONSTRAINT IF EXISTS fk_reservations_waitlist
    """)
    
    # Drop new columns from reservations
    op.execute("""
        ALTER TABLE reservations 
        DROP COLUMN IF EXISTS duration_minutes,
        DROP COLUMN IF EXISTS source,
        DROP COLUMN IF EXISTS table_ids,
        DROP COLUMN IF EXISTS dietary_restrictions,
        DROP COLUMN IF EXISTS occasion,
        DROP COLUMN IF EXISTS notification_method,
        DROP COLUMN IF EXISTS reminder_sent,
        DROP COLUMN IF EXISTS reminder_sent_at,
        DROP COLUMN IF EXISTS waitlist_id,
        DROP COLUMN IF EXISTS converted_from_waitlist,
        DROP COLUMN IF EXISTS cancelled_at,
        DROP COLUMN IF EXISTS cancellation_reason,
        DROP COLUMN IF EXISTS cancelled_by,
        DROP COLUMN IF EXISTS confirmed_at,
        DROP COLUMN IF EXISTS seated_at,
        DROP COLUMN IF EXISTS completed_at,
        DROP COLUMN IF EXISTS created_by,
        DROP COLUMN IF EXISTS updated_by,
        DROP COLUMN IF EXISTS confirmed_by,
        DROP COLUMN IF EXISTS seated_by,
        DROP COLUMN IF EXISTS completed_by
    """)
    
    # Drop tables
    op.drop_table('special_dates')
    op.drop_table('table_configurations')
    op.drop_table('reservation_settings')
    op.drop_table('waitlist_entries')
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS auditaction")
    op.execute("DROP TYPE IF EXISTS notificationmethod")
    op.execute("DROP TYPE IF EXISTS waitliststatus")
    op.execute("DROP TYPE IF EXISTS reservationstatus")