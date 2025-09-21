"""Legacy menu model aliases and enums.

Several parts of the codebase still import ``modules.menu.models.menu_models``
for historic ORM classes. The canonical models were moved to
``core.menu_models``; this module simply re-exports them and provides
small helper enums expected by tests and older modules.
"""

from enum import Enum
from decimal import Decimal
from typing import Optional

from core.menu_models import (
    MenuItem as CoreMenuItem,
    MenuCategory as CoreMenuCategory,
    ModifierGroup,
    Modifier,
    MenuItemModifier,
    MenuItemInventory,
)


class MenuItemStatus(str, Enum):
    """Basic lifecycle statuses for menu items."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


# Backwards compatible aliases
MenuItem = CoreMenuItem
Category = CoreMenuCategory
Product = CoreMenuItem

__all__ = [
    "MenuItem",
    "Category",
    "MenuItemStatus",
    "Product",
    "ModifierGroup",
    "Modifier",
    "MenuItemModifier",
    "MenuItemInventory",
]
