from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException
from typing import List, Optional
from ..models.order_models import Order, OrderItem
from ..schemas.order_schemas import OrderUpdate, OrderOut
from ..enums.order_enums import OrderStatus

VALID_TRANSITIONS = {
    OrderStatus.PENDING: [OrderStatus.IN_PROGRESS, OrderStatus.CANCELLED],
    OrderStatus.IN_PROGRESS: [OrderStatus.IN_KITCHEN, OrderStatus.CANCELLED],
    OrderStatus.IN_KITCHEN: [OrderStatus.READY, OrderStatus.CANCELLED],
    OrderStatus.READY: [OrderStatus.SERVED],
    OrderStatus.SERVED: [OrderStatus.COMPLETED],
    OrderStatus.COMPLETED: [],
    OrderStatus.CANCELLED: []
}


async def get_order_by_id(db: Session, order_id: int):
    order = db.query(Order).options(joinedload(Order.order_items)).filter(
        Order.id == order_id, Order.deleted_at.is_(None)
    ).first()

    if not order:
        raise HTTPException(
            status_code=404,
            detail=f"Order with id {order_id} not found"
        )

    return order


async def update_order_service(
    order_id: int, order_update: OrderUpdate, db: Session
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order_update.status and order_update.status != order.status:
        current_status = OrderStatus(order.status)
        valid_transitions = VALID_TRANSITIONS.get(current_status, [])
        if order_update.status not in valid_transitions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status transition from {current_status} to "
                       f"{order_update.status}"
            )
        order.status = order_update.status.value

    if order_update.order_items is not None:
        db.query(OrderItem).filter(OrderItem.order_id == order_id).delete()

        for item_data in order_update.order_items:
            new_item = OrderItem(
                order_id=order_id,
                menu_item_id=item_data.menu_item_id,
                quantity=item_data.quantity,
                price=item_data.price,
                notes=item_data.notes
            )
            db.add(new_item)

    db.commit()
    db.refresh(order)

    return {
        "message": "Order updated successfully",
        "data": OrderOut.model_validate(order)
    }


async def get_orders_service(
    db: Session,
    status: Optional[str] = None,
    statuses: Optional[List[str]] = None,
    staff_id: Optional[int] = None,
    table_no: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
    include_items: bool = False
) -> List[Order]:
    query = db.query(Order)

    if status:
        query = query.filter(Order.status == status)
    elif statuses:
        query = query.filter(Order.status.in_(statuses))
    if staff_id:
        query = query.filter(Order.staff_id == staff_id)
    if table_no:
        query = query.filter(Order.table_no == table_no)

    query = query.filter(Order.deleted_at.is_(None))

    query = query.offset(offset).limit(limit)

    if include_items:
        query = query.options(joinedload(Order.order_items))

    return query.all()
