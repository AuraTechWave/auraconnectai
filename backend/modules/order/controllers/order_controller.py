from backend.modules.order.services.order_service import (
    create_order_service
)
from backend.modules.order.schemas.order_schemas import OrderCreate


async def create_order(order_data: OrderCreate):
    return await create_order_service(order_data)
