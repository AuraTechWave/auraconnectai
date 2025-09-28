# backend/modules/orders/routes/order_inventory_routes.py

"""
API routes for order inventory integration.
Handles order completion with automatic inventory deduction.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import get_current_user, User
from core.permissions import Permission, check_permission

from ..services.order_inventory_integration import OrderInventoryIntegrationService
from ..schemas.inventory_integration_schemas import (
    OrderCompleteRequest,
    OrderCompleteResponse,
    OrderCancelRequest,
    OrderCancelResponse,
    PartialFulfillmentRequest,
    PartialFulfillmentResponse,
    InventoryAvailabilityResponse,
)

router = APIRouter(prefix="/orders", tags=["Order Inventory Integration"])


@router.post(
    "/{order_id}/complete-with-inventory", response_model=OrderCompleteResponse
)
async def complete_order_with_inventory(
    order_id: int,
    request: Optional[OrderCompleteRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Complete an order and automatically deduct inventory based on recipes.

    This endpoint:
    - Updates order status to COMPLETED
    - Deducts inventory based on menu item recipes
    - Creates audit logs for all deductions
    - Handles insufficient inventory gracefully
    - Supports optional inventory skip for special cases
    """
    check_permission(current_user, Permission.ORDER_UPDATE)

    service = OrderInventoryIntegrationService(db)

    # Extract options from request
    skip_inventory = request.skip_inventory if request else False
    force_deduction = request.force_deduction if request else False

    try:
        result = await service.complete_order_with_inventory(
            order_id=order_id,
            user_id=current_user.id,
            force_deduction=force_deduction,
            skip_inventory=skip_inventory,
        )

        return OrderCompleteResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete order: {str(e)}",
        )


@router.post("/{order_id}/cancel-with-inventory", response_model=OrderCancelResponse)
async def cancel_order_with_inventory(
    order_id: int,
    request: OrderCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cancel an order with optional inventory reversal.

    This endpoint:
    - Updates order status to CANCELLED
    - Reverses inventory deductions if order was completed
    - Creates audit logs for all reversals
    - Supports forced cancellation for special cases
    """
    check_permission(current_user, Permission.ORDER_UPDATE)

    service = OrderInventoryIntegrationService(db)

    try:
        result = await service.handle_order_cancellation(
            order_id=order_id,
            user_id=current_user.id,
            reason=request.reason,
            reverse_inventory=request.reverse_inventory,
        )

        return OrderCancelResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel order: {str(e)}",
        )


@router.post(
    "/{order_id}/partial-fulfillment", response_model=PartialFulfillmentResponse
)
async def handle_partial_fulfillment(
    order_id: int,
    request: PartialFulfillmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Handle partial order fulfillment with proportional inventory deduction.

    This endpoint:
    - Deducts inventory only for fulfilled items
    - Tracks partial fulfillments in order metadata
    - Maintains audit trail for each partial fulfillment
    - Validates order is in appropriate status
    """
    check_permission(current_user, Permission.ORDER_UPDATE)

    service = OrderInventoryIntegrationService(db)

    try:
        result = await service.handle_partial_fulfillment(
            order_id=order_id,
            fulfilled_items=request.fulfilled_items,
            user_id=current_user.id,
        )

        return PartialFulfillmentResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process partial fulfillment: {str(e)}",
        )


@router.get(
    "/{order_id}/inventory-availability", response_model=InventoryAvailabilityResponse
)
async def check_inventory_availability(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Check if an order can be fulfilled with current inventory levels.

    This endpoint:
    - Calculates required ingredients based on recipes
    - Checks current inventory levels
    - Returns detailed availability status
    - Identifies items with insufficient stock
    """
    check_permission(current_user, Permission.ORDER_VIEW)

    service = OrderInventoryIntegrationService(db)

    try:
        result = await service.validate_inventory_availability(order_id=order_id)
        return InventoryAvailabilityResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check inventory availability: {str(e)}",
        )


@router.post("/{order_id}/reverse-deduction")
async def reverse_inventory_deduction(
    order_id: int,
    reason: str = Query(..., description="Reason for reversal"),
    force: bool = Query(
        False, description="Force reversal even if synced to external systems"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually reverse inventory deductions for an order.

    This endpoint:
    - Reverses all inventory deductions for the order
    - Creates reversal audit logs
    - Checks for external system sync before reversal
    - Requires admin permission for force reversal
    """
    check_permission(current_user, Permission.ORDER_UPDATE)

    # Force reversal requires admin permission
    if force:
        check_permission(current_user, Permission.ADMIN_ACCESS)

    from ..services.recipe_inventory_service import RecipeInventoryService

    service = RecipeInventoryService(db)

    try:
        result = await service.reverse_inventory_deduction(
            order_id=order_id, user_id=current_user.id, reason=reason, force=force
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reverse inventory deduction: {str(e)}",
        )
