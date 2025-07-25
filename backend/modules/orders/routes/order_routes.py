from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from backend.core.database import get_db
from ..controllers.order_controller import (
    update_order, get_order_by_id, list_orders, list_kitchen_orders,
    validate_order_rules, delay_order_fulfillment, get_delayed_orders
)
from ..schemas.order_schemas import (
    OrderUpdate, OrderOut, MultiItemRuleRequest, RuleValidationResult,
    DelayFulfillmentRequest
)

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get("/", response_model=List[OrderOut])
async def get_orders(
    status: Optional[str] = Query(
        None, description="Filter by order status"
    ),
    staff_id: Optional[int] = Query(
        None, description="Filter by staff member ID"
    ),
    table_no: Optional[int] = Query(
        None, description="Filter by table number"
    ),
    limit: int = Query(
        100, ge=1, le=1000, description="Number of orders to return"
    ),
    offset: int = Query(0, ge=0, description="Number of orders to skip"),
    include_items: bool = Query(
        False, description="Include order items in response"
    ),
    db: Session = Depends(get_db)
):
    """
    Retrieve a list of orders with optional filtering and pagination.

    - **status**: Filter by order status (pending, in_progress, etc.)
    - **staff_id**: Filter by staff member ID
    - **table_no**: Filter by table number
    - **limit**: Maximum number of orders to return (1-1000)
    - **offset**: Number of orders to skip for pagination
    - **include_items**: Whether to include order items in the response
    """
    return await list_orders(
        db, status, staff_id, table_no, limit, offset, include_items
    )


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


@router.get("/kitchen", response_model=List[OrderOut])
async def get_kitchen_orders(
    limit: int = Query(100, ge=1, le=1000,
                       description="Number of orders to return"),
    offset: int = Query(0, ge=0, description="Number of orders to skip"),
    db: Session = Depends(get_db)
):
    """
    Retrieve a list of active kitchen orders (new or preparing).
    Used for the BOH dashboard.

    - **limit**: Maximum number of orders to return (1-1000)
    - **offset**: Number of orders to skip for pagination
    """
    return await list_kitchen_orders(db, limit, offset)


@router.post("/validate-rules", response_model=RuleValidationResult)
async def validate_rules(
    rule_request: MultiItemRuleRequest,
    db: Session = Depends(get_db)
):
    """
    Validate multi-item order rules including combo deals, bulk discounts,
    and compatibility restrictions.
    """
    return await validate_order_rules(rule_request, db)


@router.post("/{order_id}/delay", response_model=dict)
async def delay_order(
    order_id: int,
    delay_data: DelayFulfillmentRequest,
    db: Session = Depends(get_db)
):
    """
    Schedule an order for delayed fulfillment at a specified time.

    - **order_id**: ID of the order to delay
    - **scheduled_fulfillment_time**: When the order should be fulfilled
    - **delay_reason**: Optional reason for the delay
    - **additional_notes**: Optional additional notes about the delay
    """
    return await delay_order_fulfillment(order_id, delay_data, db)


@router.get("/delayed", response_model=List[OrderOut])
async def get_delayed_orders_endpoint(
    from_time: Optional[datetime] = Query(
        None, description="Filter orders scheduled from this time"
    ),
    to_time: Optional[datetime] = Query(
        None, description="Filter orders scheduled until this time"
    ),
    db: Session = Depends(get_db)
):
    """
    Retrieve orders scheduled for delayed fulfillment within a time range.

    - **from_time**: Optional start time filter
    - **to_time**: Optional end time filter
    """
    orders = await get_delayed_orders(db, from_time, to_time)
    return [OrderOut.model_validate(order) for order in orders]
