from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_create_orders_tables'
down_revision = '0001_create_staff_tables'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('staff_id', sa.Integer(), sa.ForeignKey('staff_members.id'), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True)
    )
    
    op.create_index('ix_orders_staff_id', 'orders', ['staff_id'])
    op.create_index('ix_orders_status', 'orders', ['status'])
    
    op.create_table(
        'order_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id'), nullable=False),
        sa.Column('menu_item_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('price', sa.Numeric(10, 2), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )
    
    op.create_index('ix_order_items_order_id', 'order_items', ['order_id'])

def downgrade():
    op.drop_index('ix_order_items_order_id', 'order_items')
    op.drop_table('order_items')
    op.drop_index('ix_orders_status', 'orders')
    op.drop_index('ix_orders_staff_id', 'orders')
    op.drop_table('orders')
