# backend/modules/menu/models/menu_models.py

"""
Menu models compatibility layer.

This module provides compatibility for test files that expect
menu models to be in modules.menu.models.menu_models.
"""

from enum import Enum
from core.menu_models import MenuItem as CoreMenuItem, MenuCategory as CoreMenuCategory

# Export core models
MenuItem = CoreMenuItem
Category = CoreMenuCategory
MenuCategory = CoreMenuCategory

# Define MenuItemStatus enum for tests
class MenuItemStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"
    DRAFT = "draft"

# For analytics tests that expect Product
Product = MenuItem