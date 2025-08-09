# backend/modules/menu/models/__init__.py

from .recipe_models import (
    Recipe, RecipeIngredient, RecipeSubRecipe, 
    RecipeHistory, RecipeNutrition,
    RecipeStatus, RecipeComplexity, UnitType
)

# Import compatibility layer for tests and legacy imports
from .menu_models import (
    MenuItem, MenuCategory, Category, MenuItemStatus, Product
)

__all__ = [
    'Recipe', 'RecipeIngredient', 'RecipeSubRecipe',
    'RecipeHistory', 'RecipeNutrition',
    'RecipeStatus', 'RecipeComplexity', 'UnitType',
    'MenuItem', 'MenuCategory', 'Category', 'MenuItemStatus', 'Product'
]