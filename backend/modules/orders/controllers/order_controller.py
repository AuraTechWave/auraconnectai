from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from ..services.order_service import (
    update_order_service, get_order_by_id as get_order_service,
    get_orders_service, validate_multi_item_rules,
    schedule_delayed_fulfillment, get_scheduled_orders
)
from ..schemas.order_schemas import (
    OrderUpdate, OrderOut, MultiItemRuleRequest, RuleValidationResult,
    DelayFulfillmentRequest
)
from ..enums.order_enums import OrderStatus


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
        db, status=status, staff_id=staff_id, table_no=table_no,
        limit=limit, offset=offset, include_items=include_items
    )
    return [OrderOut.from_orm(order) for order in orders]


async def list_kitchen_orders(
    db: Session,
    limit: int = 100,
    offset: int = 0
) -> List[OrderOut]:
    kitchen_statuses = [OrderStatus.PENDING.value,
                        OrderStatus.IN_KITCHEN.value]
    orders = await get_orders_service(
        db, statuses=kitchen_statuses, limit=limit, offset=offset,
        include_items=True
    )
    return [OrderOut.model_validate(order) for order in orders]


async def validate_order_rules(
    rule_request: MultiItemRuleRequest,
    db: Session
) -> RuleValidationResult:
    return await validate_multi_item_rules(
        rule_request.order_items,
        rule_request.rule_types,
        db
    )


async def delay_order_fulfillment(
    order_id: int, delay_data: DelayFulfillmentRequest, db: Session
):
    """
    Schedule an order for delayed fulfillment.
    """
    return await schedule_delayed_fulfillment(order_id, delay_data, db)


async def get_delayed_orders(
    db: Session,
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None
):
    """
    Retrieve orders scheduled for delayed fulfillment.
    """
    return await get_scheduled_orders(db, from_time, to_time)
