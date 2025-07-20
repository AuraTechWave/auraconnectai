from sqlalchemy.orm import Session
from ..services.order_service import get_order_by_id as get_order_service

def get_order_by_id(db: Session, order_id: int):
    return get_order_service(db, order_id)
