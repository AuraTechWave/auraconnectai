"""Add inventory deduction tracking fields

Revision ID: add_inventory_deduction_tracking
Revises: add_equipment_maintenance
Create Date: 2025-08-06 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_inventory_deduction_tracking'
down_revision = 'add_equipment_maintenance'
branch_labels = None
depends_on = None


def upgrade():
    # Add metadata column to inventory_adjustments if not exists
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='inventory_adjustments' 
                AND column_name='metadata'
            ) THEN
                ALTER TABLE inventory_adjustments 
                ADD COLUMN metadata JSONB DEFAULT '{}';
            END IF;
        END $$;
    """)
    
    # Add indexes for better query performance
    # Using raw SQL for CONCURRENTLY option
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_inventory_adjustments_reference 
        ON inventory_adjustments (reference_type, reference_id);
    """)
    
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_inventory_adjustments_created_at 
        ON inventory_adjustments (created_at);
    """)
    
    # Add completed_at and completed_by columns to orders if not exists
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='orders' 
                AND column_name='completed_at'
            ) THEN
                ALTER TABLE orders 
                ADD COLUMN completed_at TIMESTAMP;
            END IF;
            
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='orders' 
                AND column_name='completed_by'
            ) THEN
                ALTER TABLE orders 
                ADD COLUMN completed_by INTEGER REFERENCES users(id);
            END IF;
            
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='orders' 
                AND column_name='cancelled_at'
            ) THEN
                ALTER TABLE orders 
                ADD COLUMN cancelled_at TIMESTAMP;
            END IF;
            
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='orders' 
                AND column_name='cancelled_by'
            ) THEN
                ALTER TABLE orders 
                ADD COLUMN cancelled_by INTEGER REFERENCES users(id);
            END IF;
            
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='orders' 
                AND column_name='cancellation_reason'
            ) THEN
                ALTER TABLE orders 
                ADD COLUMN cancellation_reason TEXT;
            END IF;
        END $$;
    """)
    
    # Create audit log table if not exists
    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            action VARCHAR(255) NOT NULL,
            entity_type VARCHAR(100) NOT NULL,
            entity_id INTEGER NOT NULL,
            user_id INTEGER REFERENCES users(id),
            details JSONB DEFAULT '{}',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Create index on audit logs
    # Using raw SQL for CONCURRENTLY option
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_logs_entity 
        ON audit_logs (entity_type, entity_id);
    """)
    
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_logs_user_timestamp 
        ON audit_logs (user_id, timestamp);
    """)


def downgrade():
    # Remove indexes
    op.drop_index('idx_audit_logs_user_timestamp', table_name='audit_logs', if_exists=True)
    op.drop_index('idx_audit_logs_entity', table_name='audit_logs', if_exists=True)
    op.drop_index('idx_inventory_adjustments_created_at', table_name='inventory_adjustments', if_exists=True)
    op.drop_index('idx_inventory_adjustments_reference', table_name='inventory_adjustments', if_exists=True)
    
    # Drop audit logs table
    op.drop_table('audit_logs', if_exists=True)
    
    # Remove columns from orders
    op.drop_column('orders', 'cancellation_reason', if_exists=True)
    op.drop_column('orders', 'cancelled_by', if_exists=True)
    op.drop_column('orders', 'cancelled_at', if_exists=True)
    op.drop_column('orders', 'completed_by', if_exists=True)
    op.drop_column('orders', 'completed_at', if_exists=True)
    
    # Remove metadata column from inventory_adjustments
    op.drop_column('inventory_adjustments', 'metadata', if_exists=True)