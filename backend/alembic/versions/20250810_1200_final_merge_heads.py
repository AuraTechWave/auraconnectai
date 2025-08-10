"""Final merge of all migration heads for documentation PR

Revision ID: 20250810_1200_final_merge_heads
Revises: merge_final_all_heads, 20250810_1000_payroll_tax_tables, 20250807_1100_add_enhanced_reservation_system
Create Date: 2025-08-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250810_1200_final_merge_heads'
down_revision = (
    'merge_final_all_heads',
    '20250810_1000_payroll_tax_tables',
    '20250807_1100_add_enhanced_reservation_system'
)
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge migration - no operations needed
    pass


def downgrade():
    # This is a merge migration - no operations needed
    pass