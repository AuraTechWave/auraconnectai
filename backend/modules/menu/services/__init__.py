# backend/modules/menu/services/__init__.py

from .recipe_service import RecipeService
from .recommendation_service import MenuRecommendationService

__all__ = ["RecipeService"]
__all__.append("MenuRecommendationService")
