from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.core.database import get_db
from ..controllers.order_controller import update_order, get_order_by_id
from ..schemas.order_schemas import OrderUpdate, OrderOut

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get("/{id}", response_model=OrderOut)
async def get_order(id: int, db: Session = Depends(get_db)):
    return await get_order_by_id(db, id)


@router.put("/{order_id}", response_model=dict)
async def update_existing_order(
    order_id: int,
    order_data: OrderUpdate,
    db: Session = Depends(get_db)
):
    return await update_order(order_id, order_data, db)
