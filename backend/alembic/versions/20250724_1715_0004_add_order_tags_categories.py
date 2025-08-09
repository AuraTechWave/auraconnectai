from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0004_add_order_tags_categories'
down_revision = '0003_create_pos_sync_settings'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'tags',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(50), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )
    
    op.create_index('ix_tags_id', 'tags', ['id'])
    op.create_index('ix_tags_name', 'tags', ['name'])
    
    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(50), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )
    
    op.create_index('ix_categories_id', 'categories', ['id'])
    op.create_index('ix_categories_name', 'categories', ['name'])
    
    op.create_table(
        'order_tags',
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id'), primary_key=True),
        sa.Column('tag_id', sa.Integer(), sa.ForeignKey('tags.id'), primary_key=True)
    )
    
    op.add_column('orders', sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id'), nullable=True))
    op.create_index('ix_orders_category_id', 'orders', ['category_id'])

def downgrade():
    op.drop_index('ix_orders_category_id', 'orders')
    op.drop_column('orders', 'category_id')
    op.drop_table('order_tags')
    op.drop_index('ix_categories_name', 'categories')
    op.drop_index('ix_categories_id', 'categories')
    op.drop_table('categories')
    op.drop_index('ix_tags_name', 'tags')
    op.drop_index('ix_tags_id', 'tags')
    op.drop_table('tags')
