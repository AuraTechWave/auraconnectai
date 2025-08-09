"""Add attachment metadata fields

Revision ID: 20250725_0550_0006
Revises: 20250725_0539_0005
Create Date: 2025-07-25 05:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250725_0550_0006'
down_revision = '20250725_0539_0005'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('order_attachments', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('order_attachments', sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('order_attachments', sa.Column('uploaded_by', sa.Integer(), nullable=True))
    
    op.create_foreign_key(
        'fk_order_attachments_uploaded_by',
        'order_attachments', 'users',
        ['uploaded_by'], ['id']
    )


def downgrade():
    op.drop_constraint('fk_order_attachments_uploaded_by', 'order_attachments', type_='foreignkey')
    op.drop_column('order_attachments', 'uploaded_by')
    op.drop_column('order_attachments', 'is_public')
    op.drop_column('order_attachments', 'description')
