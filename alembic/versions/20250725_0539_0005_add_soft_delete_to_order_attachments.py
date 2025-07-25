"""Add soft delete to order attachments

Revision ID: 20250725_0539_0005
Revises: 20250724_1722_0004
Create Date: 2025-07-25 05:39:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250725_0539_0005'
down_revision = '20250724_1722_0004'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('order_attachments', sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('order_attachments', 'deleted_at')
