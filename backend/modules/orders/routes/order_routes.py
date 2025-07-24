from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.core.database import get_db
from ..controllers.order_controller import (
    update_order, get_order_by_id, list_orders, list_kitchen_orders,
    validate_order_rules, archive_order, restore_order, list_archived_orders
)
from ..schemas.order_schemas import (
    OrderUpdate, OrderOut, MultiItemRuleRequest, RuleValidationResult
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


@router.post("/{order_id}/archive", response_model=dict)
async def archive_order_endpoint(
    order_id: int,
    db: Session = Depends(get_db)
):
    """
    Archive a completed or cancelled order.

    Only orders with status 'completed' or 'cancelled' can be archived.
    Archived orders are excluded from regular order listings by default.
    """
    return await archive_order(order_id, db)


@router.post("/{order_id}/restore", response_model=dict)
async def restore_order_endpoint(
    order_id: int,
    db: Session = Depends(get_db)
):
    """
    Restore an archived order back to completed status.

    Only orders with status 'archived' can be restored.
    """
    return await restore_order(order_id, db)


@router.get("/archived", response_model=List[OrderOut])
async def get_archived_orders_endpoint(
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
    db: Session = Depends(get_db)
):
    """
    Retrieve archived orders with optional filtering and pagination.

    - **staff_id**: Filter by staff member ID
    - **table_no**: Filter by table number
    - **limit**: Maximum number of orders to return (1-1000)
    - **offset**: Number of orders to skip for pagination
    """
    return await list_archived_orders(
        db, staff_id, table_no, limit, offset
    )
