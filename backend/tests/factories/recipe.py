# backend/tests/factories/recipe.py

import factory
from factory import Faker, Sequence, LazyFunction, LazyAttribute, SubFactory
import random
from .base import BaseFactory
from .auth import UserFactory
from .menu import MenuItemFactory
from .inventory import InventoryFactory
from modules.menu.models.recipe_models import Recipe, RecipeIngredient, RecipeStatus


class RecipeFactory(BaseFactory):
    """Factory for creating recipes."""
    
    class Meta:
        model = Recipe
    
    id = Sequence(lambda n: n + 1)
    
    # Menu item relationship
    menu_item = SubFactory(MenuItemFactory)
    menu_item_id = LazyAttribute(lambda obj: obj.menu_item.id)
    
    # Recipe details
    name = LazyAttribute(lambda obj: f"Recipe for {obj.menu_item.name}")
    status = RecipeStatus.ACTIVE
    version = 1
    
    # Yield information
    yield_quantity = LazyFunction(lambda: round(random.uniform(1.0, 4.0), 1))
    yield_unit = factory.Iterator(["portion", "serving", "piece", "batch"])
    
    # Time information
    prep_time_minutes = LazyFunction(lambda: random.randint(5, 30))
    cook_time_minutes = LazyFunction(lambda: random.randint(10, 60))
    total_time_minutes = LazyAttribute(
        lambda obj: (obj.prep_time_minutes or 0) + (obj.cook_time_minutes or 0)
    )
    
    # Other details
    complexity = factory.Iterator(["simple", "moderate", "complex", "expert"])
    instructions = LazyFunction(lambda: [f"Step {i+1}" for i in range(random.randint(3, 8))])
    notes = Faker("sentence")
    
    # User tracking
    created_by = LazyAttribute(lambda obj: obj.menu_item.created_by if obj.menu_item else UserFactory().id)
    is_active = True


class RecipeIngredientFactory(BaseFactory):
    """Factory for creating recipe ingredients."""
    
    class Meta:
        model = RecipeIngredient
    
    id = Sequence(lambda n: n + 1)
    
    # Relationships
    recipe = SubFactory(RecipeFactory)
    recipe_id = LazyAttribute(lambda obj: obj.recipe.id)
    inventory_item = SubFactory(InventoryFactory)
    inventory_id = LazyAttribute(lambda obj: obj.inventory_item.id)
    
    # Quantity
    quantity = LazyFunction(lambda: round(random.uniform(0.1, 2.0), 2))
    unit = LazyAttribute(lambda obj: obj.inventory_item.unit if obj.inventory_item else "unit")
    
    # Additional details
    preparation = factory.Iterator([None, "diced", "sliced", "chopped", "minced", "grated"])
    is_optional = False
    display_order = Sequence(lambda n: n)
    notes = None
    
    # User tracking
    created_by = LazyAttribute(lambda obj: obj.recipe.created_by if obj.recipe else UserFactory().id)
    is_active = True


class RecipeWithIngredientsFactory(RecipeFactory):
    """Factory for creating recipes with ingredients."""
    
    @factory.post_generation
    def ingredients(self, create, extracted, **kwargs):
        if not create:
            return
        
        if extracted:
            # Use provided ingredients
            for ingredient_data in extracted:
                if isinstance(ingredient_data, dict):
                    RecipeIngredientFactory(
                        recipe=self,
                        created_by=self.created_by,
                        **ingredient_data
                    )
                else:
                    # Assume it's an inventory item
                    RecipeIngredientFactory(
                        recipe=self,
                        inventory_item=ingredient_data,
                        created_by=self.created_by
                    )
        else:
            # Create 2-4 random ingredients
            num_ingredients = random.randint(2, 4)
            for i in range(num_ingredients):
                RecipeIngredientFactory(
                    recipe=self,
                    display_order=i,
                    created_by=self.created_by
                )