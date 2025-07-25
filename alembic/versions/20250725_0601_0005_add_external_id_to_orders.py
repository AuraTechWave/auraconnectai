"""add_external_id_to_orders

Revision ID: 20250725_0601_0005
Revises: 20250724_1715_0004_add_order_tags_categories
Create Date: 2025-07-25 06:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20250725_0601_0005'
down_revision: Union[str, None] = '20250724_1715_0004_add_order_tags_categories'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('external_id', sa.String(), nullable=True))
    
    op.create_index('ix_orders_external_id', 'orders', ['external_id'])


def downgrade() -> None:
    op.drop_index('ix_orders_external_id', 'orders')
    
    op.drop_column('orders', 'external_id')
