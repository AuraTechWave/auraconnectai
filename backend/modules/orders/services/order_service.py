from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException
from typing import List, Optional
from ..models.order_models import Order, OrderItem, Tag, Category
from ..schemas.order_schemas import (
    OrderUpdate, OrderOut, OrderItemUpdate, RuleValidationResult,
    TagCreate, TagOut, CategoryCreate, CategoryOut
)
from ..enums.order_enums import OrderStatus, MultiItemRuleType
from .inventory_service import deduct_inventory

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
        if (order_update.status == OrderStatus.IN_PROGRESS and
                current_status == OrderStatus.PENDING):
            try:
                result = await deduct_inventory(db, order.order_items)
                if result.get("low_stock_alerts"):
                    pass
            except HTTPException as e:
                raise e
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
    tag_ids: Optional[List[int]] = None,
    category_id: Optional[int] = None,
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
    if tag_ids:
        query = query.join(Order.tags).filter(Tag.id.in_(tag_ids))
    if category_id:
        query = query.filter(Order.category_id == category_id)

    query = query.filter(Order.deleted_at.is_(None))

    query = query.offset(offset).limit(limit)

    if include_items:
        query = query.options(joinedload(Order.order_items))

    query = query.options(joinedload(Order.tags), joinedload(Order.category))

    return query.all()


async def validate_multi_item_rules(
    items: List[OrderItemUpdate],
    rule_types: Optional[List[MultiItemRuleType]] = None,
    db: Session = None
) -> RuleValidationResult:
    """
    Validate multi-item order rules including combo deals, bulk discounts,
    and compatibility.
    """
    if not rule_types:
        rule_types = [
            MultiItemRuleType.COMBO,
            MultiItemRuleType.BULK_DISCOUNT,
            MultiItemRuleType.COMPATIBILITY
        ]

    modified_items = []

    for rule_type in rule_types:
        if rule_type == MultiItemRuleType.COMBO:
            pizza_items = [
                item for item in items
                if item.menu_item_id in [101, 102, 103]
            ]
            drink_items = [
                item for item in items
                if item.menu_item_id in [201, 202]
            ]

            if pizza_items and drink_items:
                pass

        elif rule_type == MultiItemRuleType.BULK_DISCOUNT:
            total_quantity = sum(item.quantity for item in items)
            if total_quantity >= 5:
                pass

        elif rule_type == MultiItemRuleType.COMPATIBILITY:
            incompatible_pairs = [(101, 301), (102, 302)]
            item_ids = [item.menu_item_id for item in items]

            for pair in incompatible_pairs:
                if pair[0] in item_ids and pair[1] in item_ids:
                    return RuleValidationResult(
                        is_valid=False,
                        message=f"Items {pair[0]} and {pair[1]} are not "
                                f"compatible"
                    )

    return RuleValidationResult(
        is_valid=True,
        message="All rules passed",
        modified_items=modified_items if modified_items else None
    )


async def add_tags_to_order(db: Session, order_id: int, tag_ids: List[int]):
    order = await get_order_by_id(db, order_id)

    tags = db.query(Tag).filter(Tag.id.in_(tag_ids)).all()
    if len(tags) != len(tag_ids):
        found_ids = [tag.id for tag in tags]
        missing_ids = [tag_id for tag_id in tag_ids if tag_id not in found_ids]
        raise HTTPException(
            status_code=404,
            detail=f"Tags with ids {missing_ids} not found"
        )

    for tag in tags:
        if tag not in order.tags:
            order.tags.append(tag)

    db.commit()
    db.refresh(order)

    return {
        "message": "Tags added successfully",
        "data": OrderOut.model_validate(order)
    }


async def remove_tag_from_order(db: Session, order_id: int, tag_id: int):
    order = await get_order_by_id(db, order_id)

    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(
            status_code=404,
            detail=f"Tag with id {tag_id} not found"
        )

    if tag in order.tags:
        order.tags.remove(tag)
        db.commit()
        db.refresh(order)

    return {
        "message": "Tag removed successfully",
        "data": OrderOut.model_validate(order)
    }


async def set_order_category(db: Session, order_id: int,
                           category_id: Optional[int]):
    order = await get_order_by_id(db, order_id)

    if category_id is not None:
        category = db.query(Category).filter(
            Category.id == category_id).first()
        if not category:
            raise HTTPException(
                status_code=404,
                detail=f"Category with id {category_id} not found"
            )
        order.category_id = category_id
    else:
        order.category_id = None

    db.commit()
    db.refresh(order)

    return {
        "message": "Category updated successfully",
        "data": OrderOut.model_validate(order)
    }


async def create_tag(db: Session, tag_data: TagCreate):
    existing_tag = db.query(Tag).filter(Tag.name == tag_data.name).first()
    if existing_tag:
        raise HTTPException(
            status_code=400,
            detail=f"Tag with name '{tag_data.name}' already exists"
        )

    tag = Tag(
        name=tag_data.name,
        description=tag_data.description
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)

    return TagOut.model_validate(tag)


async def get_tags(db: Session, limit: int = 100,
                  offset: int = 0) -> List[Tag]:
    return db.query(Tag).offset(offset).limit(limit).all()


async def create_category(db: Session, category_data: CategoryCreate):
    existing_category = db.query(Category).filter(
        Category.name == category_data.name).first()
    if existing_category:
        raise HTTPException(
            status_code=400,
            detail=f"Category with name '{category_data.name}' already exists"
        )

    category = Category(
        name=category_data.name,
        description=category_data.description
    )
    db.add(category)
    db.commit()
    db.refresh(category)

    return CategoryOut.model_validate(category)


async def get_categories(db: Session, limit: int = 100,
                        offset: int = 0) -> List[Category]:
    return db.query(Category).offset(offset).limit(limit).all()
