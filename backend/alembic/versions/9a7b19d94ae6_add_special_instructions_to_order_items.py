"""add_special_instructions_to_order_items

Revision ID: 9a7b19d94ae6
Revises: 87855e9897a9
Create Date: 2025-07-25 05:50:08.816713

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a7b19d94ae6'
down_revision: Union[str, None] = '87855e9897a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('order_items', 
        sa.Column('special_instructions', sa.dialects.postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('order_items', 'special_instructions')
