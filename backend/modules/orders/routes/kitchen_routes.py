from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.database import get_db
from ..controllers.order_controller import (
    update_order, generate_kitchen_print_ticket
)
from ..schemas.order_schemas import (
    OrderUpdate, KitchenPrintRequest, KitchenPrintResponse
)
from ..enums.order_enums import OrderStatus

router = APIRouter(prefix="/kitchen/orders", tags=["Kitchen"])

KITCHEN_ALLOWED_STATUSES = {
    OrderStatus.READY,
    OrderStatus.SERVED,
    OrderStatus.COMPLETED
}


@router.put("/{id}/status", response_model=dict)
async def update_order_status(
    id: int,
    order_data: OrderUpdate,
    db: Session = Depends(get_db)
):
    """
    Update order status from kitchen perspective.

    Only allows updates to 'ready', 'served', or 'completed' statuses.
    Reuses existing order update logic with kitchen-specific validation.
    """
    if order_data.status and order_data.status not in KITCHEN_ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Kitchen can only update status to: "
                   f"{', '.join([s.value for s in KITCHEN_ALLOWED_STATUSES])}"
        )

    return await update_order(id, order_data, db)


@router.post("/{id}/print", response_model=KitchenPrintResponse)
async def print_kitchen_ticket(
    id: int,
    print_request: KitchenPrintRequest,
    db: Session = Depends(get_db)
):
    """
    Generate and print kitchen ticket for an order.

    Validates order is in appropriate status and routes to POS for printing.
    """
    return await generate_kitchen_print_ticket(id, print_request, db)
