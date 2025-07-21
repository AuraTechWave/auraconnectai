from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.core.database import get_db
from ..controllers.order_controller import update_order
from ..schemas.order_schemas import OrderUpdate
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
            detail=f"Kitchen can only update status to: {', '.join([s.value for s in KITCHEN_ALLOWED_STATUSES])}"
        )
    
    return await update_order(id, order_data, db)
