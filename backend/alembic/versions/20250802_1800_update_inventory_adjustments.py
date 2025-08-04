"""Update inventory adjustments for recipe deduction

Revision ID: update_inventory_adjustments
Revises: add_recipe_management
Create Date: 2025-08-02 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'update_inventory_adjustments'
down_revision = 'add_recipe_management'
branch_labels = None
depends_on = None


def upgrade():
    # Add new adjustment types to enum
    op.execute("""
        ALTER TYPE adjustmenttype ADD VALUE IF NOT EXISTS 'consumption';
        ALTER TYPE adjustmenttype ADD VALUE IF NOT EXISTS 'return';
    """)
    
    # Rename quantity_adjusted to quantity_change if needed
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'inventory_adjustments' 
                AND column_name = 'quantity_adjusted'
            ) THEN
                ALTER TABLE inventory_adjustments 
                RENAME COLUMN quantity_adjusted TO quantity_change;
            END IF;
        END $$;
    """)
    
    # Add metadata column if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'inventory_adjustments' 
                AND column_name = 'metadata'
            ) THEN
                ALTER TABLE inventory_adjustments 
                ADD COLUMN metadata JSON;
            END IF;
        END $$;
    """)
    
    # Add performed_by column if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'inventory_adjustments' 
                AND column_name = 'performed_by'
            ) THEN
                ALTER TABLE inventory_adjustments 
                ADD COLUMN performed_by INTEGER;
                
                -- Copy data from created_by to performed_by
                UPDATE inventory_adjustments 
                SET performed_by = created_by 
                WHERE performed_by IS NULL;
                
                -- Make it NOT NULL
                ALTER TABLE inventory_adjustments 
                ALTER COLUMN performed_by SET NOT NULL;
            END IF;
        END $$;
    """)
    
    # Add index on reference_type and reference_id for faster lookups
    op.create_index(
        'ix_inventory_adjustments_reference', 
        'inventory_adjustments', 
        ['reference_type', 'reference_id']
    )


def downgrade():
    # Drop index
    op.drop_index('ix_inventory_adjustments_reference', table_name='inventory_adjustments')
    
    # Note: We cannot remove enum values in PostgreSQL, so we leave them
    # The columns can remain as they don't break backward compatibility