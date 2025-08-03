# backend/modules/orders/exceptions/inventory_exceptions.py

from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class InventoryIssueDetail:
    """Detail about a specific inventory issue"""
    inventory_id: int
    item_name: str
    available_quantity: float
    required_quantity: float
    unit: str
    issue_type: str  # 'insufficient_stock', 'not_found', 'inactive'
    menu_item_id: Optional[int] = None
    menu_item_name: Optional[str] = None


class InventoryDeductionError(Exception):
    """Base exception for all inventory deduction errors"""
    
    def __init__(self, message: str, error_code: str, details: Optional[Dict] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)
    
    def to_dict(self) -> Dict:
        """Convert exception to dictionary for API responses"""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details
        }


class InsufficientInventoryError(InventoryDeductionError):
    """Raised when there's not enough inventory to fulfill the order"""
    
    def __init__(self, items: List[InventoryIssueDetail], order_id: int):
        self.items = items
        self.order_id = order_id
        
        message = f"Insufficient inventory for order {order_id}. {len(items)} item(s) have insufficient stock."
        details = {
            "order_id": order_id,
            "insufficient_items": [
                {
                    "inventory_id": item.inventory_id,
                    "item_name": item.item_name,
                    "available": item.available_quantity,
                    "required": item.required_quantity,
                    "unit": item.unit,
                    "shortage": item.required_quantity - item.available_quantity,
                    "menu_item_id": item.menu_item_id,
                    "menu_item_name": item.menu_item_name
                }
                for item in items
            ]
        }
        
        super().__init__(message, "INSUFFICIENT_INVENTORY", details)


class MissingRecipeError(InventoryDeductionError):
    """Raised when menu items don't have associated recipes"""
    
    def __init__(self, menu_items: List[Dict], order_id: int):
        self.menu_items = menu_items
        self.order_id = order_id
        
        message = f"Missing recipe configuration for {len(menu_items)} menu item(s) in order {order_id}."
        details = {
            "order_id": order_id,
            "items_without_recipes": menu_items,
            "requires_manual_review": True
        }
        
        super().__init__(message, "MISSING_RECIPE_CONFIG", details)


class InventoryNotFoundError(InventoryDeductionError):
    """Raised when referenced inventory items don't exist"""
    
    def __init__(self, inventory_ids: List[int], order_id: int):
        self.inventory_ids = inventory_ids
        self.order_id = order_id
        
        message = f"Inventory items not found: {inventory_ids}"
        details = {
            "order_id": order_id,
            "missing_inventory_ids": inventory_ids,
            "requires_manual_review": True
        }
        
        super().__init__(message, "INVENTORY_NOT_FOUND", details)


class RecipeLoopError(InventoryDeductionError):
    """Raised when recipe contains circular dependencies"""
    
    def __init__(self, recipe_chain: List[int], order_id: int):
        self.recipe_chain = recipe_chain
        self.order_id = order_id
        
        message = f"Circular recipe dependency detected: {' -> '.join(map(str, recipe_chain))}"
        details = {
            "order_id": order_id,
            "recipe_chain": recipe_chain,
            "requires_manual_review": True
        }
        
        super().__init__(message, "RECIPE_CIRCULAR_DEPENDENCY", details)


class InventorySyncError(InventoryDeductionError):
    """Raised when inventory has been synced to external systems and cannot be modified"""
    
    def __init__(self, order_id: int, synced_adjustments: List[int]):
        self.order_id = order_id
        self.synced_adjustments = synced_adjustments
        
        message = f"Cannot modify inventory for order {order_id}. Adjustments have been synced to external systems."
        details = {
            "order_id": order_id,
            "synced_adjustment_ids": synced_adjustments,
            "requires_admin_override": True
        }
        
        super().__init__(message, "INVENTORY_SYNC_LOCKED", details)


class ConcurrentDeductionError(InventoryDeductionError):
    """Raised when concurrent deduction attempts are detected"""
    
    def __init__(self, order_id: int, existing_adjustments: List[int]):
        self.order_id = order_id
        self.existing_adjustments = existing_adjustments
        
        message = f"Concurrent deduction detected for order {order_id}. Inventory has already been deducted."
        details = {
            "order_id": order_id,
            "existing_adjustment_ids": existing_adjustments,
            "action": "skipped_duplicate_deduction"
        }
        
        super().__init__(message, "CONCURRENT_DEDUCTION", details)