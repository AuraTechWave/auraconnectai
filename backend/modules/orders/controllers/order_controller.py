from sqlalchemy.orm import Session
from typing import List, Optional
from ..services.order_service import (
    update_order_service, get_order_by_id as get_order_service,
    get_orders_service, validate_multi_item_rules, add_tags_to_order,
    remove_tag_from_order, set_order_category, create_tag, get_tags,
    create_category, get_categories
)
from ..schemas.order_schemas import (
    OrderUpdate, OrderOut, MultiItemRuleRequest, RuleValidationResult,
    OrderTagRequest, OrderCategoryRequest, TagCreate, TagOut,
    CategoryCreate, CategoryOut
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
    tag_ids: Optional[List[int]] = None,
    category_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
    include_items: bool = False
) -> List[OrderOut]:
    orders = await get_orders_service(
        db, status=status, staff_id=staff_id, table_no=table_no,
        tag_ids=tag_ids, category_id=category_id,
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


async def add_order_tags(order_id: int, tag_request: OrderTagRequest,
                        db: Session):
    return await add_tags_to_order(db, order_id, tag_request.tag_ids)


async def remove_order_tag(order_id: int, tag_id: int, db: Session):
    return await remove_tag_from_order(db, order_id, tag_id)


async def update_order_category(order_id: int,
                               category_request: OrderCategoryRequest,
                               db: Session):
    return await set_order_category(db, order_id, category_request.category_id)


async def create_new_tag(tag_data: TagCreate, db: Session) -> TagOut:
    return await create_tag(db, tag_data)


async def list_tags(db: Session, limit: int = 100,
                   offset: int = 0) -> List[TagOut]:
    tags = await get_tags(db, limit, offset)
    return [TagOut.model_validate(tag) for tag in tags]


async def create_new_category(category_data: CategoryCreate,
                             db: Session) -> CategoryOut:
    return await create_category(db, category_data)


async def list_categories(db: Session, limit: int = 100,
                         offset: int = 0) -> List[CategoryOut]:
    categories = await get_categories(db, limit, offset)
    return [CategoryOut.model_validate(category) for category in categories]
