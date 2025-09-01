# backend/modules/orders/schemas/inventory_integration_schemas.py

"""
Schemas for order inventory integration endpoints.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


# Request schemas
class OrderCompleteRequest(BaseModel):
    """Request to complete an order with inventory options"""

    skip_inventory: bool = Field(
        default=False, description="Skip inventory deduction (for special cases)"
    )
    force_deduction: bool = Field(
        default=False, description="Force deduction even if inventory is insufficient"
    )
    reason: Optional[str] = Field(
        None,
        min_length=1,
        max_length=500,
        description="Optional reason for the completion",
    )


class OrderCancelRequest(BaseModel):
    """Request to cancel an order"""

    reason: str = Field(
        ..., min_length=1, max_length=500, description="Reason for cancellation"
    )
    reverse_inventory: bool = Field(
        default=True, description="Whether to reverse inventory deductions"
    )


class FulfilledItem(BaseModel):
    """Item that has been fulfilled"""

    menu_item_id: int = Field(..., gt=0)
    fulfilled_quantity: int = Field(..., gt=0)

    @field_validator("fulfilled_quantity")
    @classmethod
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError("Fulfilled quantity must be positive")
        return v


class PartialFulfillmentRequest(BaseModel):
    """Request for partial order fulfillment"""

    fulfilled_items: List[FulfilledItem] = Field(
        ..., min_items=1, description="List of items that have been fulfilled"
    )
    reason: Optional[str] = Field(
        None,
        min_length=1,
        max_length=500,
        description="Optional reason for the partial fulfillment",
    )


# Response schemas
class DeductedItem(BaseModel):
    """Information about a deducted inventory item"""

    inventory_id: int
    item_name: str
    quantity_deducted: float
    unit: str
    new_quantity: float


class LowStockAlert(BaseModel):
    """Low stock alert information"""

    inventory_id: int
    item_name: str
    current_quantity: float
    threshold: float
    unit: str


class InventoryDeductionResult(BaseModel):
    """Result of inventory deduction operation"""

    success: bool
    deducted_items: List[DeductedItem]
    low_stock_alerts: List[LowStockAlert]
    items_without_recipes: List[Dict[str, Any]]
    total_items_deducted: int


class OrderCompleteResponse(BaseModel):
    """Response for order completion with inventory"""

    success: bool
    order_id: int
    status: str
    completed_at: datetime
    inventory_deducted: bool
    inventory_result: Optional[InventoryDeductionResult]
    message: Optional[str] = None


class ReversedItem(BaseModel):
    """Information about a reversed inventory item"""

    inventory_id: int
    item_name: str
    quantity_restored: float
    unit: str
    new_quantity: float


class InventoryReversalResult(BaseModel):
    """Result of inventory reversal operation"""

    success: bool
    reversed_items: List[ReversedItem]
    total_items_reversed: int


class OrderCancelResponse(BaseModel):
    """Response for order cancellation with inventory"""

    success: bool
    order_id: int
    status: str
    cancelled_at: datetime
    inventory_reversed: bool
    reversal_result: Optional[InventoryReversalResult]
    message: Optional[str] = None


class PartialFulfillmentResponse(BaseModel):
    """Response for partial fulfillment"""

    success: bool
    order_id: int
    fulfilled_items: List[FulfilledItem]
    inventory_result: InventoryDeductionResult


class InventoryImpactItem(BaseModel):
    """Impact preview for a single inventory item"""

    inventory_id: int
    item_name: str
    current_quantity: float
    required_quantity: float
    new_quantity: float
    unit: str
    sufficient_stock: bool
    will_be_low_stock: bool
    recipes_using: List[Dict[str, Any]]


class InventoryAvailabilityResponse(BaseModel):
    """Response for inventory availability check"""

    can_fulfill: bool
    impact_preview: List[InventoryImpactItem]
    warnings: List[str]
    message: Optional[str] = None


# Update order schemas to include these in exports
__all__ = [
    "OrderCompleteRequest",
    "OrderCompleteResponse",
    "OrderCancelRequest",
    "OrderCancelResponse",
    "PartialFulfillmentRequest",
    "PartialFulfillmentResponse",
    "InventoryAvailabilityResponse",
    "DeductedItem",
    "LowStockAlert",
    "InventoryDeductionResult",
    "ReversedItem",
    "InventoryReversalResult",
    "InventoryImpactItem",
    "FulfilledItem",
]
