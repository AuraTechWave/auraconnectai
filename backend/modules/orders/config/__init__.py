# backend/modules/orders/config/__init__.py

from .inventory_config import InventoryDeductionConfig, get_inventory_config

__all__ = ["InventoryDeductionConfig", "get_inventory_config"]
