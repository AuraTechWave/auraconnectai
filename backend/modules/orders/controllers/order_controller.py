from sqlalchemy.orm import Session
from typing import List, Optional
from ..services.order_service import (
    update_order_service, get_order_by_id as get_order_service,
    get_orders_service
)
from ..schemas.order_schemas import OrderUpdate, OrderOut


async def update_order(order_id: int, order_data: OrderUpdate, db: Session):
    return await update_order_service(order_id, order_data, db)


async def get_order_by_id(db: Session, order_id: int):
    return await get_order_service(db, order_id)


async def list_orders(
    db: Session,
    status: Optional[str] = None,
    staff_id: Optional[int] = None,
    table_no: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
    include_items: bool = False
) -> List[OrderOut]:
    orders = await get_orders_service(
        db, status, staff_id, table_no, limit, offset, include_items
    )
    return [OrderOut.from_orm(order) for order in orders]
