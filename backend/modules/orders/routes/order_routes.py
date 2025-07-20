from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.core.database import get_db
from ..controllers.order_controller import update_order
from ..schemas.order_schemas import OrderUpdate

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.put("/{order_id}", response_model=dict)
async def update_existing_order(
    order_id: int,
    order_data: OrderUpdate,
    db: Session = Depends(get_db)
):
    return await update_order(order_id, order_data, db)
