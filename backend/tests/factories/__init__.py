# backend/tests/factories/__init__.py

"""
Shared test factories for AuraConnect backend.

These factories provide reusable test data generation for all modules.
"""

from .base import BaseFactory
from .auth import UserFactory, RoleFactory
from .inventory import InventoryFactory, InventoryAdjustmentFactory
from .menu import CategoryFactory, MenuItemFactory
from .recipe import RecipeFactory, RecipeIngredientFactory, RecipeWithIngredientsFactory
from .order import OrderFactory, OrderItemFactory, OrderWithItemsFactory
from .staff import StaffMemberFactory, DepartmentFactory
from .utils import create_restaurant_setup, create_order_scenario

__all__ = [
    # Base
    'BaseFactory',
    
    # Auth
    'UserFactory',
    'RoleFactory',
    
    # Inventory
    'InventoryFactory',
    'InventoryAdjustmentFactory',
    
    # Menu
    'CategoryFactory',
    'MenuItemFactory',
    
    # Recipe
    'RecipeFactory',
    'RecipeIngredientFactory',
    'RecipeWithIngredientsFactory',
    
    # Order
    'OrderFactory',
    'OrderItemFactory',
    'OrderWithItemsFactory',
    
    # Staff
    'StaffMemberFactory',
    'DepartmentFactory',
    
    # Utils
    'create_restaurant_setup',
    'create_order_scenario',
]