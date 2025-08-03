# backend/modules/orders/tests/factories.py

import factory
from factory import Faker, SubFactory, Sequence, LazyFunction
from factory.alchemy import SQLAlchemyModelFactory
from datetime import datetime
import random

from core.database import get_test_db
from core.models import User, Role
from core.inventory_models import Inventory, InventoryAdjustment
from ..models.order_models import Order, OrderItem, OrderStatus
from ...menu.models.menu_models import MenuItem, Category, MenuItemStatus
from ...menu.models.recipe_models import Recipe, RecipeIngredient, RecipeStatus


class BaseFactory(SQLAlchemyModelFactory):
    """Base factory with session management."""
    
    class Meta:
        abstract = True
        sqlalchemy_session_persistence = "commit"
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override to use test database session."""
        if cls._meta.sqlalchemy_session is None:
            cls._meta.sqlalchemy_session = next(get_test_db())
        return super()._create(model_class, *args, **kwargs)


class RoleFactory(BaseFactory):
    """Factory for creating roles."""
    
    class Meta:
        model = Role
    
    id = Sequence(lambda n: n + 1)
    name = factory.Iterator(["staff", "manager", "admin"])
    description = LazyFunction(lambda: f"Test role")


class UserFactory(BaseFactory):
    """Factory for creating users."""
    
    class Meta:
        model = User
    
    id = Sequence(lambda n: n + 1)
    username = Faker("user_name")
    email = Faker("email")
    is_active = True
    
    @factory.post_generation
    def roles(self, create, extracted, **kwargs):
        if not create:
            return
        
        if extracted:
            for role in extracted:
                self.roles.append(role)
        else:
            # Default to staff role
            self.roles.append(RoleFactory(name="staff"))


class CategoryFactory(BaseFactory):
    """Factory for creating menu categories."""
    
    class Meta:
        model = Category
    
    id = Sequence(lambda n: n + 1)
    name = Faker("word")
    description = Faker("sentence")
    is_active = True
    display_order = Sequence(lambda n: n)


class MenuItemFactory(BaseFactory):
    """Factory for creating menu items."""
    
    class Meta:
        model = MenuItem
    
    id = Sequence(lambda n: n + 1)
    name = Faker("catch_phrase")
    description = Faker("sentence")
    price = LazyFunction(lambda: round(random.uniform(5.0, 50.0), 2))
    category = SubFactory(CategoryFactory)
    category_id = factory.SelfAttribute("category.id")
    status = MenuItemStatus.ACTIVE
    is_active = True
    display_order = Sequence(lambda n: n)


class InventoryFactory(BaseFactory):
    """Factory for creating inventory items."""
    
    class Meta:
        model = Inventory
    
    id = Sequence(lambda n: n + 1)
    item_name = Faker("word")
    quantity = LazyFunction(lambda: round(random.uniform(10.0, 100.0), 2))
    unit = factory.Iterator(["kg", "liter", "piece", "dozen"])
    threshold = LazyFunction(lambda: round(random.uniform(5.0, 20.0), 2))
    cost_per_unit = LazyFunction(lambda: round(random.uniform(1.0, 20.0), 2))
    is_active = True


class RecipeFactory(BaseFactory):
    """Factory for creating recipes."""
    
    class Meta:
        model = Recipe
    
    id = Sequence(lambda n: n + 1)
    menu_item = SubFactory(MenuItemFactory)
    menu_item_id = factory.SelfAttribute("menu_item.id")
    name = LazyFunction(lambda: f"Recipe {random.randint(1000, 9999)}")
    status = RecipeStatus.ACTIVE
    yield_quantity = 1.0
    yield_unit = "portion"
    prep_time_minutes = LazyFunction(lambda: random.randint(5, 30))
    cook_time_minutes = LazyFunction(lambda: random.randint(10, 60))
    total_time_minutes = factory.LazyAttribute(
        lambda obj: (obj.prep_time_minutes or 0) + (obj.cook_time_minutes or 0)
    )
    created_by = 1
    is_active = True


class RecipeIngredientFactory(BaseFactory):
    """Factory for creating recipe ingredients."""
    
    class Meta:
        model = RecipeIngredient
    
    id = Sequence(lambda n: n + 1)
    recipe = SubFactory(RecipeFactory)
    recipe_id = factory.SelfAttribute("recipe.id")
    inventory_item = SubFactory(InventoryFactory)
    inventory_id = factory.SelfAttribute("inventory_item.id")
    quantity = LazyFunction(lambda: round(random.uniform(0.1, 2.0), 2))
    unit = factory.SelfAttribute("inventory_item.unit")
    created_by = 1
    is_active = True


class OrderFactory(BaseFactory):
    """Factory for creating orders."""
    
    class Meta:
        model = Order
    
    id = Sequence(lambda n: n + 1)
    order_number = LazyFunction(lambda: f"ORD-{random.randint(10000, 99999)}")
    status = OrderStatus.PENDING
    total_amount = LazyFunction(lambda: round(random.uniform(10.0, 200.0), 2))
    created_by = SubFactory(UserFactory)
    staff_id = factory.SelfAttribute("created_by.id")
    table_no = LazyFunction(lambda: random.randint(1, 20))


class OrderItemFactory(BaseFactory):
    """Factory for creating order items."""
    
    class Meta:
        model = OrderItem
    
    id = Sequence(lambda n: n + 1)
    order = SubFactory(OrderFactory)
    order_id = factory.SelfAttribute("order.id")
    menu_item = SubFactory(MenuItemFactory)
    menu_item_id = factory.SelfAttribute("menu_item.id")
    quantity = LazyFunction(lambda: random.randint(1, 5))
    price = factory.SelfAttribute("menu_item.price")
    notes = Faker("sentence")


# Composite factories for complete test setups

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
                        **ingredient_data
                    )
                else:
                    # Assume it's an inventory item
                    RecipeIngredientFactory(
                        recipe=self,
                        inventory_item=ingredient_data
                    )
        else:
            # Create 3 random ingredients
            for _ in range(3):
                RecipeIngredientFactory(recipe=self)


class OrderWithItemsFactory(OrderFactory):
    """Factory for creating orders with items."""
    
    @factory.post_generation
    def items(self, create, extracted, **kwargs):
        if not create:
            return
        
        if extracted:
            # Use provided items
            for item_data in extracted:
                if isinstance(item_data, dict):
                    OrderItemFactory(
                        order=self,
                        **item_data
                    )
                else:
                    # Assume it's a menu item
                    OrderItemFactory(
                        order=self,
                        menu_item=item_data
                    )
        else:
            # Create 2 random items
            for _ in range(2):
                OrderItemFactory(order=self)
        
        # Update total amount
        total = sum(item.price * item.quantity for item in self.order_items)
        self.total_amount = total


# Utility functions for common test scenarios

def create_restaurant_setup(num_menu_items=5, num_inventory_items=10):
    """Create a complete restaurant setup for testing."""
    # Create categories
    categories = [
        CategoryFactory(name="Appetizers"),
        CategoryFactory(name="Main Courses"),
        CategoryFactory(name="Desserts"),
    ]
    
    # Create inventory items
    inventory_items = [
        InventoryFactory(item_name=f"Ingredient {i}")
        for i in range(num_inventory_items)
    ]
    
    # Create menu items with recipes
    menu_items = []
    for i in range(num_menu_items):
        category = random.choice(categories)
        menu_item = MenuItemFactory(
            name=f"Dish {i + 1}",
            category=category
        )
        
        # Create recipe with random ingredients
        recipe = RecipeWithIngredientsFactory(
            menu_item=menu_item,
            ingredients=[
                {
                    "inventory_item": random.choice(inventory_items),
                    "quantity": round(random.uniform(0.1, 1.0), 2)
                }
                for _ in range(random.randint(2, 4))
            ]
        )
        
        menu_items.append(menu_item)
    
    return {
        "categories": categories,
        "inventory_items": inventory_items,
        "menu_items": menu_items
    }


def create_order_scenario(user=None, num_items=2):
    """Create an order with items ready for testing."""
    if not user:
        user = UserFactory(roles=[RoleFactory(name="staff")])
    
    # Get or create menu items with recipes
    menu_items = []
    for _ in range(num_items):
        menu_item = MenuItemFactory()
        RecipeWithIngredientsFactory(menu_item=menu_item)
        menu_items.append(menu_item)
    
    # Create order
    order = OrderWithItemsFactory(
        created_by=user,
        items=[
            {"menu_item": item, "quantity": random.randint(1, 3)}
            for item in menu_items
        ]
    )
    
    return order