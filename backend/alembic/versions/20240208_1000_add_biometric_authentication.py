"""Add biometric authentication tables

Revision ID: add_biometric_auth
Revises: 0016
Create Date: 2024-02-08 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_biometric_auth'
down_revision = '0016'
branch_labels = None
depends_on = None


def upgrade():
    # Create attendance_enums
    op.execute("""
        CREATE TYPE checkinmethod AS ENUM (
            'manual', 'QR', 'faceID', 'fingerprint', 'pin', 'rfid'
        );
        CREATE TYPE attendancestatus AS ENUM (
            'checked_in', 'checked_out', 'break', 'absent', 'late', 'early_out'
        );
    """)
    
    # Create staff_biometrics table
    op.create_table('staff_biometrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('staff_id', sa.Integer(), nullable=False),
        sa.Column('fingerprint_template', sa.LargeBinary(), nullable=True),
        sa.Column('fingerprint_hash', sa.String(), nullable=True),
        sa.Column('fingerprint_hash_prefix', sa.String(8), nullable=True),
        sa.Column('fingerprint_enrolled_at', sa.DateTime(), nullable=True),
        sa.Column('face_template', sa.LargeBinary(), nullable=True),
        sa.Column('face_hash', sa.String(), nullable=True),
        sa.Column('face_hash_prefix', sa.String(8), nullable=True),
        sa.Column('face_enrolled_at', sa.DateTime(), nullable=True),
        sa.Column('pin_hash', sa.String(), nullable=True),
        sa.Column('pin_updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_fingerprint_enabled', sa.Boolean(), nullable=True, default=False),
        sa.Column('is_face_enabled', sa.Boolean(), nullable=True, default=False),
        sa.Column('is_pin_enabled', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['staff_id'], ['staff_members.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('staff_id')
    )
    
    # Create indexes
    op.create_index('ix_staff_biometrics_id', 'staff_biometrics', ['id'])
    op.create_index('ix_staff_biometrics_staff_id', 'staff_biometrics', ['staff_id'])
    op.create_index('ix_staff_biometrics_fingerprint_hash', 'staff_biometrics', ['fingerprint_hash'])
    op.create_index('ix_staff_biometrics_fingerprint_hash_prefix', 'staff_biometrics', ['fingerprint_hash_prefix'])
    op.create_index('ix_staff_biometrics_face_hash', 'staff_biometrics', ['face_hash'])
    op.create_index('ix_staff_biometrics_face_hash_prefix', 'staff_biometrics', ['face_hash_prefix'])
    
    # Update attendance_logs table
    op.add_column('attendance_logs', sa.Column('method', sa.Enum('manual', 'QR', 'faceID', 'fingerprint', 'pin', 'rfid', name='checkinmethod'), nullable=True))
    op.add_column('attendance_logs', sa.Column('status', sa.Enum('checked_in', 'checked_out', 'break', 'absent', 'late', 'early_out', name='attendancestatus'), nullable=True))
    op.add_column('attendance_logs', sa.Column('location_lat', sa.Float(), nullable=True))
    op.add_column('attendance_logs', sa.Column('location_lng', sa.Float(), nullable=True))
    op.add_column('attendance_logs', sa.Column('device_id', sa.String(), nullable=True))
    
    # Create indexes for attendance_logs
    op.create_index('ix_attendance_logs_staff_id', 'attendance_logs', ['staff_id'])
    op.create_index('ix_attendance_logs_check_in', 'attendance_logs', ['check_in'])
    op.create_index('ix_attendance_logs_check_out', 'attendance_logs', ['check_out'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_attendance_logs_check_out', table_name='attendance_logs')
    op.drop_index('ix_attendance_logs_check_in', table_name='attendance_logs')
    op.drop_index('ix_attendance_logs_staff_id', table_name='attendance_logs')
    
    # Remove columns from attendance_logs
    op.drop_column('attendance_logs', 'device_id')
    op.drop_column('attendance_logs', 'location_lng')
    op.drop_column('attendance_logs', 'location_lat')
    op.drop_column('attendance_logs', 'status')
    op.drop_column('attendance_logs', 'method')
    
    # Drop biometrics table and indexes
    op.drop_index('ix_staff_biometrics_face_hash_prefix', table_name='staff_biometrics')
    op.drop_index('ix_staff_biometrics_face_hash', table_name='staff_biometrics')
    op.drop_index('ix_staff_biometrics_fingerprint_hash_prefix', table_name='staff_biometrics')
    op.drop_index('ix_staff_biometrics_fingerprint_hash', table_name='staff_biometrics')
    op.drop_index('ix_staff_biometrics_staff_id', table_name='staff_biometrics')
    op.drop_index('ix_staff_biometrics_id', table_name='staff_biometrics')
    op.drop_table('staff_biometrics')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS attendancestatus')
    op.execute('DROP TYPE IF EXISTS checkinmethod')