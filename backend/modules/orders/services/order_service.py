from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, UploadFile
from typing import List, Optional
from datetime import datetime
from ..models.order_models import (
    Order, OrderItem, Tag, Category, OrderAttachment
)
from ..schemas.order_schemas import (
    OrderUpdate, OrderOut, OrderItemUpdate, RuleValidationResult,
    DelayFulfillmentRequest, TagCreate, TagOut, CategoryCreate, CategoryOut,
    CustomerNotesUpdate, OrderAttachmentOut, SpecialInstructionBase
)
from ..enums.order_enums import (OrderStatus, MultiItemRuleType,
                                 FraudCheckStatus)
from .inventory_service import deduct_inventory
from .fraud_service import perform_fraud_check
from backend.core.file_service import file_service
import re


def serialize_instructions_to_notes(
        instructions: List[SpecialInstructionBase]) -> str:
    """Convert structured instructions to formatted notes text"""
    if not instructions:
        return ""

    instruction_texts = []
    for instruction in instructions:
        priority_prefix = (f"[P{instruction.priority}] "
                           if instruction.priority else "")
        station_prefix = (f"[{instruction.target_station}] "
                          if instruction.target_station else "")
        instruction_text = (
            f"{priority_prefix}{station_prefix}"
            f"{instruction.instruction_type.value.upper()}: "
            f"{instruction.description}"
        )
        instruction_texts.append(instruction_text)

    return " | ".join(instruction_texts)


def parse_notes_to_instructions(notes: str) -> List[dict]:
    """Parse formatted notes back to structured instructions"""
    if not notes:
        return []

    instructions = []
    parts = [part.strip() for part in notes.split(" | ")]

    for part in parts:
        if not re.search(r'[A-Z]+:', part):
            continue

        priority = None
        target_station = None

        priority_match = re.search(r'\[P(\d+)\]', part)
        if priority_match:
            priority = int(priority_match.group(1))
            part = re.sub(r'\[P\d+\]\s*', '', part)

        station_match = re.search(r'\[([A-Z_]+)\]', part)
        if station_match:
            target_station = station_match.group(1)
            part = re.sub(r'\[[A-Z_]+\]\s*', '', part)

        type_match = re.search(r'([A-Z_]+):\s*(.+)', part)
        if type_match:
            instruction_type = type_match.group(1).lower()
            description = type_match.group(2).strip()

            instructions.append({
                "instruction_type": instruction_type,
                "description": description,
                "priority": priority,
                "target_station": target_station
            })

    return instructions

VALID_TRANSITIONS = {
    OrderStatus.PENDING: [
        OrderStatus.IN_PROGRESS, OrderStatus.CANCELLED, OrderStatus.DELAYED
    ],
    OrderStatus.IN_PROGRESS: [
        OrderStatus.IN_KITCHEN, OrderStatus.CANCELLED, OrderStatus.DELAYED
    ],
    OrderStatus.IN_KITCHEN: [OrderStatus.READY, OrderStatus.CANCELLED],
    OrderStatus.READY: [OrderStatus.SERVED],
    OrderStatus.SERVED: [OrderStatus.COMPLETED],
    OrderStatus.COMPLETED: [OrderStatus.ARCHIVED],
    OrderStatus.CANCELLED: [OrderStatus.ARCHIVED],
    OrderStatus.DELAYED: [OrderStatus.SCHEDULED, OrderStatus.CANCELLED],
    OrderStatus.SCHEDULED: [
        OrderStatus.AWAITING_FULFILLMENT, OrderStatus.CANCELLED
    ],
    OrderStatus.AWAITING_FULFILLMENT: [
        OrderStatus.PENDING, OrderStatus.CANCELLED
    ],
    OrderStatus.ARCHIVED: [OrderStatus.COMPLETED]
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
        existing_items = {item.menu_item_id: item
                          for item in order.order_items}

        db.query(OrderItem).filter(OrderItem.order_id == order_id).delete()

        for item_data in order_update.order_items:
            existing_item = existing_items.get(item_data.menu_item_id)
            existing_notes = existing_item.notes if existing_item else ""
            processed_notes = item_data.notes or existing_notes or ""

            special_instructions_json = None
            if item_data.special_instructions:
                special_instructions_json = [
                    instr.dict() for instr in item_data.special_instructions
                ]
                structured_notes = serialize_instructions_to_notes(
                    item_data.special_instructions)
                processed_notes = (f"{processed_notes} | {structured_notes}"
                                   if processed_notes else structured_notes)

            new_item = OrderItem(
                order_id=order_id,
                menu_item_id=item_data.menu_item_id,
                quantity=item_data.quantity,
                price=item_data.price,
                notes=processed_notes,
                special_instructions=special_instructions_json
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
    include_items: bool = False,
    include_archived: bool = False
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

    if not include_archived:
        query = query.filter(Order.status != OrderStatus.ARCHIVED.value)

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


async def create_order_with_fraud_check(
    db: Session,
    order_data: dict,
    perform_fraud_validation: bool = True
):
    order = Order(**order_data)
    db.add(order)
    db.flush()

    if perform_fraud_validation:
        fraud_result = await perform_fraud_check(
            db, order.id, force_recheck=True)

        if fraud_result.status == FraudCheckStatus.FAILED:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"Order blocked due to fraud detection. "
                       f"Risk level: {fraud_result.risk_level.value}"
            )
        elif fraud_result.status == FraudCheckStatus.MANUAL_REVIEW:
            order.status = "pending_review"

    db.commit()
    return order


async def schedule_delayed_fulfillment(
    order_id: int, delay_data: DelayFulfillmentRequest, db: Session
):
    """
    Schedule an order for delayed fulfillment at a specified time.
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    current_status = OrderStatus(order.status)
    if OrderStatus.DELAYED not in VALID_TRANSITIONS.get(current_status, []):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delay order with status {current_status}"
        )

    if delay_data.scheduled_fulfillment_time <= datetime.utcnow():
        raise HTTPException(
            status_code=400,
            detail="Scheduled fulfillment time must be in the future"
        )

    order.status = OrderStatus.DELAYED.value
    order.scheduled_fulfillment_time = delay_data.scheduled_fulfillment_time
    order.delay_reason = delay_data.delay_reason
    order.delay_requested_at = datetime.utcnow()

    db.commit()
    db.refresh(order)

    return {
        "message": "Order scheduled for delayed fulfillment",
        "data": OrderOut.model_validate(order)
    }


async def get_scheduled_orders(
    db: Session,
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None
):
    """
    Retrieve orders scheduled for fulfillment within a time range.
    """
    query = db.query(Order).filter(
        Order.status.in_([
            OrderStatus.DELAYED.value,
            OrderStatus.SCHEDULED.value,
            OrderStatus.AWAITING_FULFILLMENT.value
        ]),
        Order.deleted_at.is_(None)
    )

    if from_time:
        query = query.filter(Order.scheduled_fulfillment_time >= from_time)
    if to_time:
        query = query.filter(Order.scheduled_fulfillment_time <= to_time)

    query = query.order_by(Order.scheduled_fulfillment_time)

    return query.all()


async def process_due_delayed_orders(db: Session):
    """
    Process orders that are due for fulfillment based on their scheduled time.
    """
    current_time = datetime.utcnow()

    due_orders = db.query(Order).filter(
        Order.status == OrderStatus.SCHEDULED.value,
        Order.scheduled_fulfillment_time <= current_time,
        Order.deleted_at.is_(None)
    ).all()

    processed_orders = []

    for order in due_orders:
        order.status = OrderStatus.AWAITING_FULFILLMENT.value
        processed_orders.append(order)

    if processed_orders:
        db.commit()
        for order in processed_orders:
            db.refresh(order)

    return {
        "message": f"Processed {len(processed_orders)} due orders",
        "processed_orders": [
            OrderOut.model_validate(order) for order in processed_orders
        ]
    }


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


async def archive_order_service(db: Session, order_id: int):
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.deleted_at.is_(None)
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    current_status = OrderStatus(order.status)
    if current_status not in [OrderStatus.COMPLETED, OrderStatus.CANCELLED]:
        raise HTTPException(
            status_code=400,
            detail=f"Only completed or cancelled orders can be archived. "
                   f"Current status: {current_status}"
        )

    order.status = OrderStatus.ARCHIVED.value
    db.commit()
    db.refresh(order)

    return {
        "message": "Order archived successfully",
        "data": OrderOut.model_validate(order)
    }


async def restore_order_service(db: Session, order_id: int):
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.deleted_at.is_(None)
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if OrderStatus(order.status) != OrderStatus.ARCHIVED:
        raise HTTPException(
            status_code=400,
            detail="Only archived orders can be restored"
        )

    order.status = OrderStatus.COMPLETED.value
    db.commit()
    db.refresh(order)

    return {
        "message": "Order restored successfully",
        "data": OrderOut.model_validate(order)
    }


async def get_archived_orders_service(
    db: Session,
    staff_id: Optional[int] = None,
    table_no: Optional[int] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Order]:
    query = db.query(Order).filter(
        Order.status == OrderStatus.ARCHIVED.value,
        Order.deleted_at.is_(None)
    )

    if staff_id:
        query = query.filter(Order.staff_id == staff_id)
    if table_no:
        query = query.filter(Order.table_no == table_no)

    query = query.offset(offset).limit(limit)
    query = query.options(joinedload(Order.order_items))

    return query.all()


async def update_customer_notes(
    order_id: int, notes_update: CustomerNotesUpdate, db: Session
):
    order = db.query(Order).options(
        joinedload(Order.attachments),
        joinedload(Order.tags),
        joinedload(Order.category)
    ).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.customer_notes = notes_update.customer_notes
    db.commit()
    db.refresh(order)

    return {
        "message": "Customer notes updated successfully",
        "data": OrderOut.model_validate(order)
    }


async def add_attachment(
    order_id: int,
    file: UploadFile,
    db: Session,
    description: Optional[str] = None,
    is_public: bool = False
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    try:
        file_data = await file_service.upload_file(file, folder="orders")

        attachment = OrderAttachment(
            order_id=order_id,
            file_name=file_data["file_name"],
            file_url=file_data["file_url"],
            file_type=file_data["file_type"],
            file_size=file_data["file_size"],
            description=description,
            is_public=is_public
        )
        db.add(attachment)
        db.commit()
        db.refresh(attachment)

        return {
            "message": "Attachment uploaded successfully",
            "data": OrderAttachmentOut.model_validate(attachment)
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add attachment: {str(e)}"
        )


async def get_attachments(order_id: int,
                          db: Session) -> List[OrderAttachmentOut]:
    order = db.query(Order).options(joinedload(Order.attachments)).filter(
        Order.id == order_id
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    attachments = db.query(OrderAttachment).filter(
        OrderAttachment.order_id == order_id,
        OrderAttachment.deleted_at.is_(None)
    ).all()

    return [OrderAttachmentOut.model_validate(attachment)
            for attachment in attachments]


async def delete_attachment(attachment_id: int, db: Session):
    attachment = db.query(OrderAttachment).filter(
        OrderAttachment.id == attachment_id,
        OrderAttachment.deleted_at.is_(None)
    ).first()

    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    try:
        file_service.delete_file(attachment.file_url)

        attachment.deleted_at = datetime.utcnow()
        db.commit()

        return {
            "message": "Attachment deleted successfully",
            "data": {"id": attachment_id}
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete attachment: {str(e)}"
        )
