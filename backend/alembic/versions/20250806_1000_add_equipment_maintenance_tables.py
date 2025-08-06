"""Add equipment maintenance tables

Revision ID: add_equipment_maintenance
Revises: 20250804_2100_add_table_layout_tables
Create Date: 2025-08-06 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_equipment_maintenance'
down_revision = '20250804_2100_add_table_layout_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Create equipment status enum
    op.execute("""
        CREATE TYPE equipmentstatus AS ENUM (
            'operational',
            'needs_maintenance',
            'under_maintenance',
            'out_of_service',
            'retired'
        )
    """)
    
    # Create maintenance status enum
    op.execute("""
        CREATE TYPE maintenancestatus AS ENUM (
            'scheduled',
            'in_progress',
            'completed',
            'overdue',
            'cancelled'
        )
    """)
    
    # Create maintenance type enum
    op.execute("""
        CREATE TYPE maintenancetype AS ENUM (
            'preventive',
            'corrective',
            'emergency',
            'inspection',
            'calibration'
        )
    """)
    
    # Create equipment table
    op.create_table(
        'equipment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('equipment_name', sa.String(length=200), nullable=False),
        sa.Column('equipment_type', sa.String(length=100), nullable=False),
        sa.Column('manufacturer', sa.String(length=200), nullable=True),
        sa.Column('model_number', sa.String(length=100), nullable=True),
        sa.Column('serial_number', sa.String(length=100), nullable=True),
        sa.Column('purchase_date', sa.DateTime(), nullable=True),
        sa.Column('warranty_expiry', sa.DateTime(), nullable=True),
        sa.Column('location', sa.String(length=200), nullable=True),
        sa.Column('status', sa.Enum('operational', 'needs_maintenance', 'under_maintenance', 'out_of_service', 'retired', name='equipmentstatus'), nullable=False),
        sa.Column('maintenance_interval_days', sa.Integer(), nullable=True),
        sa.Column('last_maintenance_date', sa.DateTime(), nullable=True),
        sa.Column('next_due_date', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_critical', sa.Boolean(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for equipment table
    op.create_index('idx_equipment_status_next_due', 'equipment', ['status', 'next_due_date'], unique=False)
    op.create_index('idx_equipment_type_status', 'equipment', ['equipment_type', 'status'], unique=False)
    op.create_index(op.f('ix_equipment_equipment_name'), 'equipment', ['equipment_name'], unique=False)
    op.create_index(op.f('ix_equipment_id'), 'equipment', ['id'], unique=False)
    op.create_index(op.f('ix_equipment_next_due_date'), 'equipment', ['next_due_date'], unique=False)
    op.create_index(op.f('ix_equipment_serial_number'), 'equipment', ['serial_number'], unique=True)
    
    # Create maintenance_records table
    op.create_table(
        'maintenance_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('equipment_id', sa.Integer(), nullable=False),
        sa.Column('maintenance_type', sa.Enum('preventive', 'corrective', 'emergency', 'inspection', 'calibration', name='maintenancetype'), nullable=False),
        sa.Column('status', sa.Enum('scheduled', 'in_progress', 'completed', 'overdue', 'cancelled', name='maintenancestatus'), nullable=False),
        sa.Column('scheduled_date', sa.DateTime(), nullable=False),
        sa.Column('date_performed', sa.DateTime(), nullable=True),
        sa.Column('next_due_date', sa.DateTime(), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('performed_by', sa.String(length=200), nullable=True),
        sa.Column('cost', sa.Float(), nullable=True),
        sa.Column('parts_replaced', sa.Text(), nullable=True),
        sa.Column('issues_found', sa.Text(), nullable=True),
        sa.Column('resolution', sa.Text(), nullable=True),
        sa.Column('downtime_hours', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('completed_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['completed_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['equipment_id'], ['equipment.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for maintenance_records table
    op.create_index('idx_maintenance_equipment_status', 'maintenance_records', ['equipment_id', 'status'], unique=False)
    op.create_index('idx_maintenance_status_date', 'maintenance_records', ['status', 'scheduled_date'], unique=False)
    op.create_index('idx_maintenance_type_status', 'maintenance_records', ['maintenance_type', 'status'], unique=False)
    op.create_index(op.f('ix_maintenance_records_equipment_id'), 'maintenance_records', ['equipment_id'], unique=False)
    op.create_index(op.f('ix_maintenance_records_id'), 'maintenance_records', ['id'], unique=False)
    op.create_index(op.f('ix_maintenance_records_status'), 'maintenance_records', ['status'], unique=False)


def downgrade():
    # Drop maintenance_records table and indexes
    op.drop_index(op.f('ix_maintenance_records_status'), table_name='maintenance_records')
    op.drop_index(op.f('ix_maintenance_records_id'), table_name='maintenance_records')
    op.drop_index(op.f('ix_maintenance_records_equipment_id'), table_name='maintenance_records')
    op.drop_index('idx_maintenance_type_status', table_name='maintenance_records')
    op.drop_index('idx_maintenance_status_date', table_name='maintenance_records')
    op.drop_index('idx_maintenance_equipment_status', table_name='maintenance_records')
    op.drop_table('maintenance_records')
    
    # Drop equipment table and indexes
    op.drop_index(op.f('ix_equipment_serial_number'), table_name='equipment')
    op.drop_index(op.f('ix_equipment_next_due_date'), table_name='equipment')
    op.drop_index(op.f('ix_equipment_id'), table_name='equipment')
    op.drop_index(op.f('ix_equipment_equipment_name'), table_name='equipment')
    op.drop_index('idx_equipment_type_status', table_name='equipment')
    op.drop_index('idx_equipment_status_next_due', table_name='equipment')
    op.drop_table('equipment')
    
    # Drop enums
    op.execute('DROP TYPE maintenancetype')
    op.execute('DROP TYPE maintenancestatus')
    op.execute('DROP TYPE equipmentstatus')