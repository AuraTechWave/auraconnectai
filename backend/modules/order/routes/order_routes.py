from fastapi import APIRouter
from backend.modules.order.controllers.order_controller import (
    create_order,
)
from backend.modules.order.schemas.order_schemas import OrderCreate, OrderOut

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("/", response_model=OrderOut)
async def create_new_order(order_data: OrderCreate):
    return await create_order(order_data)
