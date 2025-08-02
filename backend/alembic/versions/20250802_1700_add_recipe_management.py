"""Add recipe management tables

Revision ID: add_recipe_management
Revises: add_staff_scheduling
Create Date: 2025-08-02 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_recipe_management'
down_revision = 'add_staff_scheduling'
branch_labels = None
depends_on = None


def upgrade():
    # Create recipe enums
    op.execute("""
        CREATE TYPE recipestatus AS ENUM ('draft', 'active', 'inactive', 'archived');
        CREATE TYPE recipecomplexity AS ENUM ('simple', 'moderate', 'complex', 'expert');
        CREATE TYPE unittype AS ENUM (
            'g', 'kg', 'oz', 'lb',
            'ml', 'l', 'tsp', 'tbsp', 'cup', 'fl_oz', 'pt', 'qt', 'gal',
            'piece', 'dozen',
            'custom'
        );
    """)
    
    # Create recipes table
    op.create_table('recipes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('menu_item_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, default=1),
        sa.Column('status', sa.Enum('draft', 'active', 'inactive', 'archived', name='recipestatus'), nullable=False, default='draft'),
        
        # Recipe details
        sa.Column('yield_quantity', sa.Float(), nullable=False, default=1.0),
        sa.Column('yield_unit', sa.String(50), nullable=True),
        sa.Column('portion_size', sa.Float(), nullable=True),
        sa.Column('portion_unit', sa.String(50), nullable=True),
        
        # Preparation details
        sa.Column('prep_time_minutes', sa.Integer(), nullable=True),
        sa.Column('cook_time_minutes', sa.Integer(), nullable=True),
        sa.Column('total_time_minutes', sa.Integer(), nullable=True),
        sa.Column('complexity', sa.Enum('simple', 'moderate', 'complex', 'expert', name='recipecomplexity'), nullable=False, default='simple'),
        
        # Instructions and notes
        sa.Column('instructions', sa.JSON(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('allergen_notes', sa.Text(), nullable=True),
        
        # Cost calculations
        sa.Column('total_cost', sa.Float(), nullable=True),
        sa.Column('food_cost_percentage', sa.Float(), nullable=True),
        sa.Column('last_cost_update', sa.DateTime(), nullable=True),
        
        # Quality and consistency
        sa.Column('quality_standards', sa.JSON(), nullable=True),
        sa.Column('plating_instructions', sa.Text(), nullable=True),
        sa.Column('image_urls', sa.JSON(), nullable=True),
        
        # Metadata
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        
        sa.ForeignKeyConstraint(['menu_item_id'], ['menu_items.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('menu_item_id', name='_menu_item_recipe_uc')
    )
    op.create_index('ix_recipes_id', 'recipes', ['id'])
    op.create_index('ix_recipes_menu_item_id', 'recipes', ['menu_item_id'])
    op.create_index('ix_recipes_name', 'recipes', ['name'])
    op.create_index('ix_recipes_status', 'recipes', ['status'])
    
    # Create recipe_ingredients table
    op.create_table('recipe_ingredients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recipe_id', sa.Integer(), nullable=False),
        sa.Column('inventory_id', sa.Integer(), nullable=False),
        
        # Quantity and unit
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit', sa.Enum(
            'g', 'kg', 'oz', 'lb',
            'ml', 'l', 'tsp', 'tbsp', 'cup', 'fl_oz', 'pt', 'qt', 'gal',
            'piece', 'dozen', 'custom',
            name='unittype'
        ), nullable=False),
        sa.Column('custom_unit', sa.String(50), nullable=True),
        
        # Preparation notes
        sa.Column('preparation', sa.String(200), nullable=True),
        sa.Column('is_optional', sa.Boolean(), nullable=False, default=False),
        
        # Cost tracking
        sa.Column('unit_cost', sa.Float(), nullable=True),
        sa.Column('total_cost', sa.Float(), nullable=True),
        
        # Display order
        sa.Column('display_order', sa.Integer(), nullable=False, default=0),
        
        # Notes
        sa.Column('notes', sa.Text(), nullable=True),
        
        # Metadata
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        
        sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ),
        sa.ForeignKeyConstraint(['inventory_id'], ['inventory.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('recipe_id', 'inventory_id', name='_recipe_inventory_uc')
    )
    op.create_index('ix_recipe_ingredients_recipe_id', 'recipe_ingredients', ['recipe_id'])
    op.create_index('ix_recipe_ingredients_inventory_id', 'recipe_ingredients', ['inventory_id'])
    
    # Create recipe_sub_recipes table
    op.create_table('recipe_sub_recipes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('parent_recipe_id', sa.Integer(), nullable=False),
        sa.Column('sub_recipe_id', sa.Integer(), nullable=False),
        
        # Quantity of sub-recipe needed
        sa.Column('quantity', sa.Float(), nullable=False, default=1.0),
        sa.Column('unit', sa.String(50), nullable=True),
        
        # Display order
        sa.Column('display_order', sa.Integer(), nullable=False, default=0),
        
        # Notes
        sa.Column('notes', sa.Text(), nullable=True),
        
        # Metadata
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        
        sa.ForeignKeyConstraint(['parent_recipe_id'], ['recipes.id'], ),
        sa.ForeignKeyConstraint(['sub_recipe_id'], ['recipes.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('parent_recipe_id', 'sub_recipe_id', name='_parent_sub_recipe_uc')
    )
    op.create_index('ix_recipe_sub_recipes_parent_recipe_id', 'recipe_sub_recipes', ['parent_recipe_id'])
    op.create_index('ix_recipe_sub_recipes_sub_recipe_id', 'recipe_sub_recipes', ['sub_recipe_id'])
    
    # Create recipe_history table
    op.create_table('recipe_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recipe_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        
        # What changed
        sa.Column('change_type', sa.String(50), nullable=False),
        sa.Column('change_summary', sa.Text(), nullable=False),
        
        # Snapshot of recipe data
        sa.Column('recipe_snapshot', sa.JSON(), nullable=False),
        sa.Column('ingredients_snapshot', sa.JSON(), nullable=False),
        
        # Cost at time of change
        sa.Column('total_cost', sa.Float(), nullable=True),
        sa.Column('food_cost_percentage', sa.Float(), nullable=True),
        
        # Who made the change
        sa.Column('changed_by', sa.Integer(), nullable=False),
        sa.Column('change_reason', sa.Text(), nullable=True),
        
        # Approval if required
        sa.Column('requires_approval', sa.Boolean(), nullable=False, default=False),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        
        # Metadata
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        
        sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_recipe_history_recipe_id', 'recipe_history', ['recipe_id'])
    op.create_index('ix_recipe_history_version', 'recipe_history', ['version'])
    op.create_index('ix_recipe_history_change_type', 'recipe_history', ['change_type'])
    
    # Create recipe_nutrition table
    op.create_table('recipe_nutrition',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recipe_id', sa.Integer(), nullable=False),
        
        # Basic nutrition per serving
        sa.Column('calories', sa.Float(), nullable=True),
        sa.Column('total_fat', sa.Float(), nullable=True),
        sa.Column('saturated_fat', sa.Float(), nullable=True),
        sa.Column('trans_fat', sa.Float(), nullable=True),
        sa.Column('cholesterol', sa.Float(), nullable=True),
        sa.Column('sodium', sa.Float(), nullable=True),
        sa.Column('total_carbohydrates', sa.Float(), nullable=True),
        sa.Column('dietary_fiber', sa.Float(), nullable=True),
        sa.Column('sugars', sa.Float(), nullable=True),
        sa.Column('protein', sa.Float(), nullable=True),
        
        # Vitamins and minerals (as % of daily value)
        sa.Column('vitamin_a', sa.Float(), nullable=True),
        sa.Column('vitamin_c', sa.Float(), nullable=True),
        sa.Column('calcium', sa.Float(), nullable=True),
        sa.Column('iron', sa.Float(), nullable=True),
        
        # Additional nutrition facts
        sa.Column('additional_nutrients', sa.JSON(), nullable=True),
        
        # Calculation method
        sa.Column('calculation_method', sa.String(50), nullable=True),
        sa.Column('last_calculated', sa.DateTime(), nullable=True),
        
        # Metadata
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('verified_by', sa.Integer(), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        
        sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('recipe_id', name='_recipe_nutrition_uc')
    )
    op.create_index('ix_recipe_nutrition_recipe_id', 'recipe_nutrition', ['recipe_id'])
    
    # Add composite indexes for common queries
    op.create_index('ix_recipes_status_active', 'recipes', ['status', 'is_active'])
    op.create_index('ix_recipe_ingredients_recipe_active', 'recipe_ingredients', ['recipe_id', 'is_active'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_recipe_ingredients_recipe_active', table_name='recipe_ingredients')
    op.drop_index('ix_recipes_status_active', table_name='recipes')
    
    op.drop_index('ix_recipe_nutrition_recipe_id', table_name='recipe_nutrition')
    op.drop_index('ix_recipe_history_change_type', table_name='recipe_history')
    op.drop_index('ix_recipe_history_version', table_name='recipe_history')
    op.drop_index('ix_recipe_history_recipe_id', table_name='recipe_history')
    op.drop_index('ix_recipe_sub_recipes_sub_recipe_id', table_name='recipe_sub_recipes')
    op.drop_index('ix_recipe_sub_recipes_parent_recipe_id', table_name='recipe_sub_recipes')
    op.drop_index('ix_recipe_ingredients_inventory_id', table_name='recipe_ingredients')
    op.drop_index('ix_recipe_ingredients_recipe_id', table_name='recipe_ingredients')
    op.drop_index('ix_recipes_status', table_name='recipes')
    op.drop_index('ix_recipes_name', table_name='recipes')
    op.drop_index('ix_recipes_menu_item_id', table_name='recipes')
    op.drop_index('ix_recipes_id', table_name='recipes')
    
    # Drop tables
    op.drop_table('recipe_nutrition')
    op.drop_table('recipe_history')
    op.drop_table('recipe_sub_recipes')
    op.drop_table('recipe_ingredients')
    op.drop_table('recipes')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS unittype')
    op.execute('DROP TYPE IF EXISTS recipecomplexity')
    op.execute('DROP TYPE IF EXISTS recipestatus')