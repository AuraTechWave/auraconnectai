from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from backend.core.database import get_db
from ..controllers.order_controller import (
    update_order, get_order_by_id, list_orders, list_kitchen_orders,
    validate_order_rules, delay_order_fulfillment, get_delayed_orders,
    add_order_tags, remove_order_tag, update_order_category,
    create_new_tag, list_tags, create_new_category, list_categories,
    archive_order, restore_order, list_archived_orders, update_order_priority
)
from ..schemas.order_schemas import (
    OrderUpdate, OrderOut, MultiItemRuleRequest, RuleValidationResult,
    DelayFulfillmentRequest, OrderTagRequest, OrderCategoryRequest,
    TagCreate, TagOut, CategoryCreate, CategoryOut, OrderPriorityUpdate
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
    tag_ids: Optional[List[int]] = Query(
        None, description="Filter by tag IDs"
    ),
    category_id: Optional[int] = Query(
        None, description="Filter by category ID"
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
    - **tag_ids**: Filter by tag IDs
    - **category_id**: Filter by category ID
    - **limit**: Maximum number of orders to return (1-1000)
    - **offset**: Number of orders to skip for pagination
    - **include_items**: Whether to include order items in the response
    """
    return await list_orders(
        db, status, staff_id, table_no, tag_ids, category_id, limit,
        offset, include_items
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


@router.post("/{order_id}/tags", response_model=dict)
async def add_tags_to_order(
    order_id: int,
    tag_request: OrderTagRequest,
    db: Session = Depends(get_db)
):
    """
    Add tags to an order.

    - **order_id**: ID of the order to add tags to
    - **tag_ids**: List of tag IDs to add to the order
    """
    return await add_order_tags(order_id, tag_request, db)


@router.delete("/{order_id}/tags/{tag_id}", response_model=dict)
async def remove_tag_from_order(
    order_id: int,
    tag_id: int,
    db: Session = Depends(get_db)
):
    """
    Remove a tag from an order.

    - **order_id**: ID of the order to remove tag from
    - **tag_id**: ID of the tag to remove
    """
    return await remove_order_tag(order_id, tag_id, db)


@router.put("/{order_id}/category", response_model=dict)
async def set_order_category(
    order_id: int,
    category_request: OrderCategoryRequest,
    db: Session = Depends(get_db)
):
    """
    Set or update the category of an order.

    - **order_id**: ID of the order to update
    - **category_id**: ID of the category to set (null to remove category)
    """
    return await update_order_category(order_id, category_request, db)


@router.post("/tags", response_model=TagOut)
async def create_tag(
    tag_data: TagCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new tag.

    - **name**: Name of the tag (must be unique)
    - **description**: Optional description of the tag
    """
    return await create_new_tag(tag_data, db)


@router.get("/tags", response_model=List[TagOut])
async def get_tags(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Retrieve all tags with pagination.

    - **limit**: Maximum number of tags to return (1-1000)
    - **offset**: Number of tags to skip for pagination
    """
    tags = await list_tags(db, limit, offset)
    return [TagOut.model_validate(tag) for tag in tags]


@router.post("/categories", response_model=CategoryOut)
async def create_category(
    category_data: CategoryCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new category.

    - **name**: Name of the category (must be unique)
    - **description**: Optional description of the category
    """
    return await create_new_category(category_data, db)


@router.get("/categories", response_model=List[CategoryOut])
async def get_categories(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Retrieve all categories with pagination.

    - **limit**: Maximum number of categories to return (1-1000)
    - **offset**: Number of categories to skip for pagination
    """
    categories = await list_categories(db, limit, offset)
    return [CategoryOut.model_validate(category) for category in categories]


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


@router.put("/{order_id}/priority", response_model=dict)
async def update_priority(
    order_id: int,
    priority_data: OrderPriorityUpdate,
    db: Session = Depends(get_db)
):
    """
    Update the priority of an order.
    
    - **order_id**: ID of the order to update
    - **priority_data**: New priority information with optional reason
    """
    return await update_order_priority(order_id, priority_data, db)
