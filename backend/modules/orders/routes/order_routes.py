from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.core.database import get_db
from ..controllers.order_controller import (
    update_order, get_order_by_id, list_orders, list_kitchen_orders,
    validate_order_rules, add_order_tags, remove_order_tag,
    update_order_category, create_new_tag, list_tags,
    create_new_category, list_categories
)
from ..schemas.order_schemas import (
    OrderUpdate, OrderOut, MultiItemRuleRequest, RuleValidationResult,
    OrderTagRequest, OrderCategoryRequest, TagCreate, TagOut,
    CategoryCreate, CategoryOut
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


@router.post("/{order_id}/tags", response_model=dict)
async def add_tags_to_order(
    order_id: int,
    tag_request: OrderTagRequest,
    db: Session = Depends(get_db)
):
    """
    Add tags to an order.
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
    """
    return await update_order_category(order_id, category_request, db)


@router.get("/tags", response_model=List[TagOut])
async def get_tags(
    limit: int = Query(100, ge=1, le=1000,
                       description="Number of tags to return"),
    offset: int = Query(0, ge=0, description="Number of tags to skip"),
    db: Session = Depends(get_db)
):
    """
    Retrieve a list of all tags.
    """
    return await list_tags(db, limit, offset)


@router.post("/tags", response_model=TagOut)
async def create_tag(
    tag_data: TagCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new tag.
    """
    return await create_new_tag(tag_data, db)


@router.get("/categories", response_model=List[CategoryOut])
async def get_categories(
    limit: int = Query(100, ge=1, le=1000,
                       description="Number of categories to return"),
    offset: int = Query(0, ge=0, description="Number of categories to skip"),
    db: Session = Depends(get_db)
):
    """
    Retrieve a list of all categories.
    """
    return await list_categories(db, limit, offset)


@router.post("/categories", response_model=CategoryOut)
async def create_category(
    category_data: CategoryCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new category.
    """
    return await create_new_category(category_data, db)
