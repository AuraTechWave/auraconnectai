"""Menu models package exposing recipe and core menu entities.

Historically this package provided ORM models for both recipes and menu
items. Most of the canonical implementations now live in
``core.menu_models``; this module re-exports them so existing imports
continue to function.
"""

from core.menu_models import (  # type: ignore F401
    MenuItem,
    MenuCategory,
    ModifierGroup,
    Modifier,
    MenuItemModifier,
    MenuItemInventory,
)
from .recipe_models import (  # type: ignore F401
    Recipe,
    RecipeIngredient,
    RecipeSubRecipe,
    RecipeHistory,
    RecipeNutrition,
    RecipeStatus,
    RecipeComplexity,
    UnitType,
)

# Backwards compatible aliases used by several modules and tests
Category = MenuCategory
Product = MenuItem

__all__ = [
    "MenuItem",
    "MenuCategory",
    "ModifierGroup",
    "Modifier",
    "MenuItemModifier",
    "MenuItemInventory",
    "Category",
    "Product",
    "Recipe",
    "RecipeIngredient",
    "RecipeSubRecipe",
    "RecipeHistory",
    "RecipeNutrition",
    "RecipeStatus",
    "RecipeComplexity",
    "UnitType",
]
