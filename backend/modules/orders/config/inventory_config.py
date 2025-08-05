# backend/modules/orders/config/inventory_config.py

from pydantic_settings import BaseSettings
from typing import Optional


class InventoryDeductionConfig(BaseSettings):
    """
    Configuration for inventory deduction behavior.
    
    These settings control how and when inventory is deducted during order processing.
    """
    
    # Use recipe-based deduction (True) or legacy MenuItemInventory (False)
    USE_RECIPE_BASED_INVENTORY_DEDUCTION: bool = True
    
    # When to deduct inventory
    # False = Deduct when order moves to IN_PROGRESS (default, kitchen starts preparing)
    # True = Deduct when order is COMPLETED (after customer receives)
    DEDUCT_INVENTORY_ON_COMPLETION: bool = False
    
    # Allow partial fulfillment of orders when some ingredients are unavailable
    ALLOW_PARTIAL_FULFILLMENT: bool = True
    
    # Automatically reverse deductions when orders are cancelled
    AUTO_REVERSE_ON_CANCELLATION: bool = True
    
    # Warn but don't block orders when inventory is low
    ALLOW_NEGATIVE_INVENTORY: bool = False
    
    # Threshold percentage for low stock warnings (0-100)
    LOW_STOCK_WARNING_THRESHOLD: float = 20.0
    
    # Send notifications for low stock alerts
    SEND_LOW_STOCK_NOTIFICATIONS: bool = True
    
    # Create audit logs for all inventory adjustments
    ENABLE_INVENTORY_AUDIT_TRAIL: bool = True
    
    # Cache recipe calculations for performance (minutes)
    RECIPE_CACHE_TTL_MINUTES: int = 5
    
    # Maximum depth for sub-recipe recursion (prevent infinite loops)
    MAX_SUB_RECIPE_DEPTH: int = 5
    
    class Config:
        env_prefix = "INVENTORY_"
        case_sensitive = False


# Global instance
inventory_config = InventoryDeductionConfig()


def get_inventory_config() -> InventoryDeductionConfig:
    """Get the inventory deduction configuration."""
    return inventory_config