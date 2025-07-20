from sqlalchemy.orm import Session
from ..services.order_service import update_order_service, get_order_by_id as get_order_service
from ..schemas.order_schemas import OrderUpdate


async def update_order(order_id: int, order_data: OrderUpdate, db: Session):
    return await update_order_service(order_id, order_data, db)


def get_order_by_id(db: Session, order_id: int):
    return get_order_service(db, order_id)
