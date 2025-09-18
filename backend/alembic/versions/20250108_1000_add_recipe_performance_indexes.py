"""Add recipe performance indexes

Revision ID: recipe_performance_indexes
Revises: 20250807_1000
Create Date: 2025-01-08 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'recipe_performance_indexes'
down_revision = '20250807_1000'
branch_labels = None
depends_on = None


def upgrade():
    """Add performance indexes for recipe cost analysis and compliance reporting"""
    
    # Indexes for Recipe table
    op.create_index(
        'idx_recipe_menu_item_active',
        'recipes',
        ['menu_item_id', 'is_active', 'deleted_at'],
        unique=False,
        postgresql_where=sa.text('deleted_at IS NULL')
    )
    
    op.create_index(
        'idx_recipe_status_active',
        'recipes',
        ['status', 'is_active'],
        unique=False
    )
    
    op.create_index(
        'idx_recipe_updated_at',
        'recipes',
        ['updated_at'],
        unique=False
    )
    
    # Indexes for RecipeIngredient table
    op.create_index(
        'idx_recipe_ingredient_recipe_inventory',
        'recipe_ingredients',
        ['recipe_id', 'inventory_id'],
        unique=False
    )
    
    # Indexes for MenuItem table (for compliance queries)
    op.create_index(
        'idx_menu_item_active_category',
        'menu_items',
        ['is_active', 'category', 'deleted_at'],
        unique=False,
        postgresql_where=sa.text('deleted_at IS NULL')
    )
    
    # Indexes for Inventory table (for cost calculations)
    op.create_index(
        'idx_inventory_unit_cost',
        'inventory',
        ['unit_cost'],
        unique=False,
        postgresql_where=sa.text('unit_cost IS NOT NULL')
    )
    
    # Composite index for recipe cost joins
    op.create_index(
        'idx_recipe_cost_calculation',
        'recipes',
        ['id', 'is_active', 'deleted_at'],
        unique=False,
        postgresql_where=sa.text('is_active = TRUE AND deleted_at IS NULL')
    )
    
    # Index for sub-recipe relationships
    op.create_index(
        'idx_recipe_sub_recipe_mapping',
        'recipe_sub_recipes',
        ['recipe_id', 'sub_recipe_id'],
        unique=False
    )
    
    # Create statistics for query optimization (PostgreSQL specific)
    op.execute("""
        CREATE STATISTICS IF NOT EXISTS recipe_menu_item_stats 
        ON menu_item_id, is_active, deleted_at 
        FROM recipes;
    """)
    
    op.execute("""
        CREATE STATISTICS IF NOT EXISTS menu_item_category_stats 
        ON is_active, category, deleted_at 
        FROM menu_items;
    """)


def downgrade():
    """Remove performance indexes"""
    
    # Drop statistics
    op.execute("DROP STATISTICS IF EXISTS recipe_menu_item_stats;")
    op.execute("DROP STATISTICS IF EXISTS menu_item_category_stats;")
    
    # Drop indexes
    op.drop_index('idx_recipe_sub_recipe_mapping', table_name='recipe_sub_recipes')
    op.drop_index('idx_recipe_cost_calculation', table_name='recipes')
    op.drop_index('idx_inventory_unit_cost', table_name='inventory')
    op.drop_index('idx_menu_item_active_category', table_name='menu_items')
    op.drop_index('idx_recipe_ingredient_recipe_inventory', table_name='recipe_ingredients')
    op.drop_index('idx_recipe_updated_at', table_name='recipes')
    op.drop_index('idx_recipe_status_active', table_name='recipes')
    op.drop_index('idx_recipe_menu_item_active', table_name='recipes')