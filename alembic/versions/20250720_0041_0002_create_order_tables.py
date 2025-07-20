from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_create_order_tables'
down_revision = '0001_create_staff_tables'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('table_no', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer()),
        sa.Column('status', sa.String(), default='pending'),
        sa.Column('created_at', sa.DateTime())
    )

    op.create_table(
        'order_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id'), nullable=False),
        sa.Column('item_name', sa.String(), nullable=False),
        sa.Column('station', sa.String()),
        sa.Column('status', sa.String(), default='pending'),
        sa.Column('started_at', sa.DateTime()),
        sa.Column('completed_at', sa.DateTime())
    )

def downgrade():
    op.drop_table('order_items')
    op.drop_table('orders')
