# backend/modules/orders/routes/inventory_impact_routes.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict

from core.database import get_db
from core.auth import get_current_user, User

from ..services.recipe_inventory_service import RecipeInventoryService
from ..services.order_service import get_order_by_id
from ..schemas.order_item_schemas import OrderItemCreate


router = APIRouter(prefix="/inventory-impact", tags=["Inventory Impact"])


@router.get("/order/{order_id}/preview")
async def preview_order_inventory_impact(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Preview the inventory impact of fulfilling an order without making changes.
    
    Shows:
    - Which ingredients will be consumed
    - Current vs projected stock levels
    - Warnings for insufficient stock
    - Low stock alerts
    """
    await check_permissions(current_user, "orders", "read")
    
    # Get the order
    order = await get_order_by_id(db, order_id)
    
    # Get inventory impact preview
    recipe_inventory_service = RecipeInventoryService(db)
    preview = await recipe_inventory_service.get_inventory_impact_preview(
        order_items=order.order_items
    )
    
    return {
        "order_id": order_id,
        "order_status": order.status,
        "can_fulfill": preview["can_fulfill"],
        "impact_preview": preview["impact_preview"],
        "warnings": preview["warnings"],
        "total_ingredients_affected": len(preview["impact_preview"])
    }


@router.post("/preview")
async def preview_items_inventory_impact(
    items: List[OrderItemCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Preview the inventory impact of a list of menu items without creating an order.
    
    Useful for:
    - Checking availability before order creation
    - Planning large catering orders
    - Inventory management decisions
    """
    await check_permissions(current_user, "orders", "read")
    
    # Convert OrderItemCreate to order item-like objects
    class PreviewOrderItem:
        def __init__(self, menu_item_id, quantity):
            self.menu_item_id = menu_item_id
            self.quantity = quantity
    
    preview_items = [
        PreviewOrderItem(menu_item_id=item.menu_item_id, quantity=item.quantity)
        for item in items
    ]
    
    # Get inventory impact preview
    recipe_inventory_service = RecipeInventoryService(db)
    preview = await recipe_inventory_service.get_inventory_impact_preview(
        order_items=preview_items
    )
    
    return {
        "items_count": len(items),
        "can_fulfill": preview["can_fulfill"],
        "impact_preview": preview["impact_preview"],
        "warnings": preview["warnings"],
        "total_ingredients_affected": len(preview["impact_preview"])
    }


@router.post("/order/{order_id}/partial-fulfillment")
async def handle_partial_order_fulfillment(
    order_id: int,
    fulfilled_items: List[Dict[str, float]],  # [{"menu_item_id": 1, "fulfilled_quantity": 2.5}]
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Handle inventory deduction for partially fulfilled orders.
    
    Used when:
    - Some items are out of stock
    - Customer modifies order during preparation
    - Kitchen can only prepare partial quantities
    """
    # Require manager role for partial fulfillment operations
    await check_permissions(current_user, "orders", "update")
    if not any(role.name in ["manager", "admin"] for role in current_user.roles):
        raise HTTPException(
            status_code=403,
            detail="Only managers and admins can perform partial fulfillment operations"
        )
    
    # Verify order exists and is in appropriate status
    order = await get_order_by_id(db, order_id)
    
    allowed_statuses = ["IN_PROGRESS", "IN_KITCHEN", "READY"]
    if order.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Order must be in {allowed_statuses} status for partial fulfillment"
        )
    
    # Process partial fulfillment
    recipe_inventory_service = RecipeInventoryService(db)
    result = await recipe_inventory_service.handle_partial_fulfillment(
        order_items=fulfilled_items,
        order_id=order_id,
        user_id=current_user.id
    )
    
    return {
        "order_id": order_id,
        "success": result["success"],
        "deducted_items": result["deducted_items"],
        "low_stock_alerts": result.get("low_stock_alerts", []),
        "total_ingredients_deducted": result["total_items_deducted"]
    }


@router.post("/order/{order_id}/reverse-deduction")
async def reverse_order_inventory_deduction(
    order_id: int,
    reason: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Reverse inventory deductions for an order.
    
    Used when:
    - Order is cancelled after inventory deduction
    - Mistake in order processing
    - Customer returns items
    """
    # Require manager role for inventory reversal operations
    await check_permissions(current_user, "orders", "update")
    if not any(role.name in ["manager", "admin"] for role in current_user.roles):
        raise HTTPException(
            status_code=403,
            detail="Only managers and admins can reverse inventory deductions"
        )
    
    # Verify order exists
    order = await get_order_by_id(db, order_id)
    
    # Process reversal
    recipe_inventory_service = RecipeInventoryService(db)
    result = await recipe_inventory_service.reverse_inventory_deduction(
        order_id=order_id,
        user_id=current_user.id,
        reason=reason
    )
    
    return {
        "order_id": order_id,
        "success": result["success"],
        "reversed_items": result["reversed_items"],
        "total_items_reversed": result["total_items_reversed"],
        "reversal_reason": reason
    }