from sqlalchemy.orm import Session
from ..services.order_service import update_order_service
from ..schemas.order_schemas import OrderUpdate


async def update_order(order_id: int, order_data: OrderUpdate, db: Session):
    return await update_order_service(order_id, order_data, db)
