"""Fix customer lifetime_value initialization

Revision ID: fix_customer_lifetime_value
Revises: 20250812_enhance_shift_swap_workflow
Create Date: 2025-08-14

This migration initializes lifetime_value for existing customers who have
null values, setting it equal to their total_spent to ensure data consistency.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision = 'fix_customer_lifetime_value'
down_revision = '20250812_enhance_shift_swap_workflow'
branch_labels = None
depends_on = None


def upgrade():
    """
    Initialize lifetime_value for existing customers where it's null.
    Set it equal to total_spent to represent no refunds have been processed yet.
    """
    # Update customers with null lifetime_value
    op.execute(
        text("""
            UPDATE customers 
            SET lifetime_value = COALESCE(total_spent, 0.0)
            WHERE lifetime_value IS NULL
        """)
    )
    
    # Fix any existing data inconsistencies where lifetime_value > total_spent
    op.execute(
        text("""
            UPDATE customers
            SET lifetime_value = total_spent
            WHERE lifetime_value > total_spent
        """)
    )
    
    # Add a check constraint to ensure lifetime_value is never greater than total_spent
    # (refunds can only decrease lifetime_value)
    op.create_check_constraint(
        'ck_lifetime_value_not_greater_than_total_spent',
        'customers',
        'lifetime_value <= total_spent'
    )


def downgrade():
    """
    Remove the check constraint.
    Note: We don't revert the data changes as they represent valid business logic.
    """
    op.drop_constraint('ck_lifetime_value_not_greater_than_total_spent', 'customers')