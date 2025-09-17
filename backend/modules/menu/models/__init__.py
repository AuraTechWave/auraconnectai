# backend/modules/menu/models/__init__.py

from .recipe_models import (
    Recipe,
    RecipeIngredient,
    RecipeSubRecipe,
    RecipeHistory,
    RecipeNutrition,
    RecipeStatus,
    RecipeComplexity,
    UnitType,
)
# Re-export commonly used core menu models for backward compatibility
try:
    from core.menu_models import MenuItem, MenuCategory  # type: ignore
except Exception:
    # If core models are unavailable at import time, skip re-export to avoid hard failure
    MenuItem = None  # type: ignore
    MenuCategory = None  # type: ignore

__all__ = [
    "Recipe",
    "RecipeIngredient",
    "RecipeSubRecipe",
    "RecipeHistory",
    "RecipeNutrition",
    "RecipeStatus",
    "RecipeComplexity",
    "UnitType",
    "MenuItem",
    "MenuCategory",
]
