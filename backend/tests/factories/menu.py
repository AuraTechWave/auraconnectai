# backend/tests/factories/menu.py

import factory
from factory import Faker, Sequence, LazyFunction, LazyAttribute, SubFactory
import random
from .base import BaseFactory
from .auth import UserFactory
from modules.menu.models.menu_models import MenuItem, Category, MenuItemStatus


class CategoryFactory(BaseFactory):
    """Factory for creating menu categories."""
    
    class Meta:
        model = Category
    
    id = Sequence(lambda n: n + 1)
    name = factory.Iterator(["Appetizers", "Main Courses", "Desserts", "Beverages", "Sides"])
    description = Faker("sentence")
    is_active = True
    display_order = Sequence(lambda n: n)
    created_by = LazyAttribute(lambda obj: UserFactory().id)


class MenuItemFactory(BaseFactory):
    """Factory for creating menu items."""
    
    class Meta:
        model = MenuItem
    
    id = Sequence(lambda n: n + 1)
    name = Faker("catch_phrase")
    description = Faker("sentence")
    price = LazyFunction(lambda: round(random.uniform(5.0, 50.0), 2))
    
    # Category relationship
    category = SubFactory(CategoryFactory)
    category_id = LazyAttribute(lambda obj: obj.category.id)
    
    # Status and flags
    status = MenuItemStatus.ACTIVE
    is_active = True
    is_available = True
    
    # Display
    display_order = Sequence(lambda n: n)
    image_url = Faker("image_url")
    
    # Metadata
    preparation_time = LazyFunction(lambda: random.randint(5, 30))
    calories = LazyFunction(lambda: random.randint(100, 800))
    
    # User tracking
    created_by = LazyAttribute(lambda obj: obj.category.created_by if obj.category else UserFactory().id)