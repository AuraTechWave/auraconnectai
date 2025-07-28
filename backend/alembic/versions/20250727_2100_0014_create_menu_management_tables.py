"""Create menu management tables

Revision ID: 20250727_2100_0014
Revises: 20250727_2000_0013
Create Date: 2025-07-27 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250727_2100_0014'
down_revision = '20250727_2000_0013'
branch_labels = None
depends_on = None


def upgrade():
    # Create menu_categories table
    op.create_table('menu_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('parent_category_id', sa.Integer(), nullable=True),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['parent_category_id'], ['menu_categories.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_menu_categories_id'), 'menu_categories', ['id'], unique=False)
    op.create_index(op.f('ix_menu_categories_name'), 'menu_categories', ['name'], unique=False)

    # Create menu_items table
    op.create_table('menu_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('sku', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_available', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('availability_start_time', sa.String(length=8), nullable=True),
        sa.Column('availability_end_time', sa.String(length=8), nullable=True),
        sa.Column('calories', sa.Integer(), nullable=True),
        sa.Column('allergens', sa.JSON(), nullable=True),
        sa.Column('dietary_tags', sa.JSON(), nullable=True),
        sa.Column('prep_time_minutes', sa.Integer(), nullable=True),
        sa.Column('serving_size', sa.String(length=50), nullable=True),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('images', sa.JSON(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['category_id'], ['menu_categories.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_menu_items_id'), 'menu_items', ['id'], unique=False)
    op.create_index(op.f('ix_menu_items_name'), 'menu_items', ['name'], unique=False)
    op.create_index(op.f('ix_menu_items_sku'), 'menu_items', ['sku'], unique=True)

    # Create modifier_groups table
    op.create_table('modifier_groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('selection_type', sa.String(length=20), nullable=False, server_default='single'),
        sa.Column('min_selections', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_selections', sa.Integer(), nullable=True),
        sa.Column('is_required', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_modifier_groups_id'), 'modifier_groups', ['id'], unique=False)
    op.create_index(op.f('ix_modifier_groups_name'), 'modifier_groups', ['name'], unique=False)

    # Create modifiers table
    op.create_table('modifiers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('modifier_group_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price_adjustment', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('price_type', sa.String(length=20), nullable=False, server_default='fixed'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_available', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['modifier_group_id'], ['modifier_groups.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_modifiers_id'), 'modifiers', ['id'], unique=False)
    op.create_index(op.f('ix_modifiers_name'), 'modifiers', ['name'], unique=False)

    # Create menu_item_modifiers table
    op.create_table('menu_item_modifiers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('menu_item_id', sa.Integer(), nullable=False),
        sa.Column('modifier_group_id', sa.Integer(), nullable=False),
        sa.Column('is_required', sa.Boolean(), nullable=True),
        sa.Column('min_selections', sa.Integer(), nullable=True),
        sa.Column('max_selections', sa.Integer(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['menu_item_id'], ['menu_items.id'], ),
        sa.ForeignKeyConstraint(['modifier_group_id'], ['modifier_groups.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_menu_item_modifiers_id'), 'menu_item_modifiers', ['id'], unique=False)

    # Update existing inventory table with new fields
    op.add_column('inventory', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('inventory', sa.Column('sku', sa.String(length=50), nullable=True))
    op.add_column('inventory', sa.Column('reorder_quantity', sa.Float(), nullable=True))
    op.add_column('inventory', sa.Column('cost_per_unit', sa.Float(), nullable=True))
    op.add_column('inventory', sa.Column('last_purchase_price', sa.Float(), nullable=True))
    op.add_column('inventory', sa.Column('vendor_item_code', sa.String(length=100), nullable=True))
    op.add_column('inventory', sa.Column('storage_location', sa.String(length=100), nullable=True))
    op.add_column('inventory', sa.Column('expiration_days', sa.Integer(), nullable=True))
    op.add_column('inventory', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
    
    # Create unique index for inventory SKU
    op.create_index(op.f('ix_inventory_sku'), 'inventory', ['sku'], unique=True)

    # Update existing menu_item_inventory table
    op.add_column('menu_item_inventory', sa.Column('unit', sa.String(length=20), nullable=True))
    op.add_column('menu_item_inventory', sa.Column('created_by', sa.Integer(), nullable=True))
    op.add_column('menu_item_inventory', sa.Column('deleted_at', sa.DateTime(), nullable=True))

    # Add foreign key constraint for menu_item_inventory if it doesn't exist
    try:
        op.create_foreign_key(None, 'menu_item_inventory', 'menu_items', ['menu_item_id'], ['id'])
    except:
        pass  # Constraint might already exist

    # Create indexes for better performance
    op.create_index('idx_menu_items_category_active', 'menu_items', ['category_id', 'is_active'])
    op.create_index('idx_menu_items_available', 'menu_items', ['is_available'])
    op.create_index('idx_menu_categories_active', 'menu_categories', ['is_active'])
    op.create_index('idx_modifiers_group_active', 'modifiers', ['modifier_group_id', 'is_active'])
    op.create_index('idx_inventory_active_threshold', 'inventory', ['is_active', 'threshold'])


def downgrade():
    # Drop indexes
    op.drop_index('idx_inventory_active_threshold', table_name='inventory')
    op.drop_index('idx_modifiers_group_active', table_name='modifiers')
    op.drop_index('idx_menu_categories_active', table_name='menu_categories')
    op.drop_index('idx_menu_items_available', table_name='menu_items')
    op.drop_index('idx_menu_items_category_active', table_name='menu_items')

    # Remove added columns from existing tables
    op.drop_column('menu_item_inventory', 'deleted_at')
    op.drop_column('menu_item_inventory', 'created_by')
    op.drop_column('menu_item_inventory', 'unit')
    
    op.drop_index(op.f('ix_inventory_sku'), table_name='inventory')
    op.drop_column('inventory', 'is_active')
    op.drop_column('inventory', 'expiration_days')
    op.drop_column('inventory', 'storage_location')
    op.drop_column('inventory', 'vendor_item_code')
    op.drop_column('inventory', 'last_purchase_price')
    op.drop_column('inventory', 'cost_per_unit')
    op.drop_column('inventory', 'reorder_quantity')
    op.drop_column('inventory', 'sku')
    op.drop_column('inventory', 'description')

    # Drop new tables
    op.drop_table('menu_item_modifiers')
    op.drop_table('modifiers')
    op.drop_table('modifier_groups')
    op.drop_table('menu_items')
    op.drop_table('menu_categories')