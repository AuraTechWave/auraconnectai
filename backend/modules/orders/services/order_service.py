from sqlalchemy.orm import Session
from fastapi import HTTPException
from ..models.order_models import Order, OrderItem
from ..schemas.order_schemas import OrderUpdate
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


async def update_order_service(order_id: int, order_update: OrderUpdate, db: Session):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order_update.status and order_update.status != order.status:
        current_status = OrderStatus(order.status)
        if order_update.status not in VALID_TRANSITIONS.get(current_status, []):
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
        "data": order
    }
