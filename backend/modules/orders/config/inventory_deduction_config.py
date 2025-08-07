# backend/modules/orders/config/inventory_deduction_config.py

"""
Configuration for inventory deduction behavior.
"""

from typing import Optional
from pydantic import BaseSettings
from enum import Enum


class DeductionTrigger(str, Enum):
    """When to trigger inventory deduction"""
    ORDER_PLACED = "order_placed"
    ORDER_PREPARING = "order_preparing"
    ORDER_COMPLETED = "order_completed"
    ORDER_SERVED = "order_served"


class InventoryDeductionSettings(BaseSettings):
    """Settings for inventory deduction behavior"""
    
    # When to deduct inventory
    DEDUCTION_TRIGGER: DeductionTrigger = DeductionTrigger.ORDER_COMPLETED
    
    # Whether to allow negative inventory
    ALLOW_NEGATIVE_INVENTORY: bool = False
    
    # Whether to deduct for cancelled items
    DEDUCT_CANCELLED_ITEMS: bool = False
    
    # Whether to auto-reverse on cancellation
    AUTO_REVERSE_ON_CANCEL: bool = True
    
    # Alert thresholds (percentage of threshold)
    LOW_STOCK_ALERT_PERCENTAGE: int = 20
    CRITICAL_STOCK_ALERT_PERCENTAGE: int = 10
    
    # Batch processing
    BATCH_DEDUCTION_SIZE: int = 100
    
    # Retry configuration
    MAX_DEDUCTION_RETRIES: int = 3
    RETRY_DELAY_SECONDS: int = 1
    
    # Audit configuration
    ENABLE_DETAILED_AUDIT: bool = True
    AUDIT_RETENTION_DAYS: int = 90
    
    # Performance optimization
    USE_BULK_OPERATIONS: bool = True
    CACHE_RECIPE_LOOKUPS: bool = True
    CACHE_TTL_SECONDS: int = 300
    
    # External sync
    SYNC_TO_EXTERNAL_POS: bool = False
    EXTERNAL_SYNC_TIMEOUT: int = 30
    
    # Feature flags
    ENABLE_PARTIAL_FULFILLMENT: bool = True
    ENABLE_RECIPE_SUBSTITUTIONS: bool = False
    ENABLE_WASTE_TRACKING: bool = True
    
    class Config:
        env_prefix = "INVENTORY_DEDUCTION_"
        case_sensitive = False


# Global instance
_settings: Optional[InventoryDeductionSettings] = None


def get_inventory_deduction_settings() -> InventoryDeductionSettings:
    """Get inventory deduction settings singleton"""
    global _settings
    if _settings is None:
        _settings = InventoryDeductionSettings()
    return _settings


def reset_settings():
    """Reset settings (mainly for testing)"""
    global _settings
    _settings = None