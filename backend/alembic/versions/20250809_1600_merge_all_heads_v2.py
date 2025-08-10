"""Merge all migration heads (v2)

Revision ID: merge_all_heads_v2
Revises: merge_all_heads, 20250725_0730_0008_v2, 20250125_2045_0010
Create Date: 2025-08-09 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'merge_all_heads_v2'
down_revision = (
    'merge_all_heads',
    '20250725_0730_0008_v3',
    '20250125_2045_0010'
)
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge migration, no operations needed
    pass


def downgrade():
    # This is a merge migration, no operations needed
    pass