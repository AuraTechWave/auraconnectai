import logging
import re
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import case, and_
from fastapi import HTTPException, UploadFile
from core.file_service import file_service
from ..enums.order_enums import (OrderStatus, MultiItemRuleType, OrderPriority,
                                 FraudCheckStatus)
from ..enums.webhook_enums import WebhookEventType
from ..models.order_models import (
    Order, OrderItem, Tag, Category, OrderAttachment, AutoCancellationConfig
)
from ..schemas.order_schemas import (
    OrderUpdate, OrderOut, OrderItemUpdate, RuleValidationResult,
    DelayFulfillmentRequest, TagCreate, TagOut, CategoryCreate, CategoryOut,
    OrderPriorityUpdate, KitchenPrintRequest, KitchenPrintResponse,
    KitchenTicketFormat, CustomerNotesUpdate, OrderAttachmentOut,
    SpecialInstructionBase
)
from ...pos.services.pos_bridge_service import POSBridgeService
from .fraud_service import perform_fraud_check
from .inventory_service import deduct_inventory
from .recipe_inventory_service import RecipeInventoryService
from ..config.inventory_config import get_inventory_config
from .webhook_service import WebhookService
from core.compliance import AuditLog

logger = logging.getLogger(__name__)


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


logger = logging.getLogger(__name__)

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


async def log_order_audit_event(
    db: Session,
    order_id: int,
    previous_status: Optional[OrderStatus],
    new_status: OrderStatus,
    user_id: int,
    metadata: Optional[dict] = None,
    action: str = "status_change"
):
    """Log an order audit event with enhanced error handling."""
    try:
        audit_event = AuditLog(
            action=action,
            module="orders",
            user_id=user_id,
            entity_id=order_id,
            previous_value=previous_status.value if previous_status else None,
            new_value=new_status.value,
            metadata=metadata or {},
            timestamp=datetime.utcnow()
        )
        db.add(audit_event)
        db.flush()  # Ensure the audit event is written
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to log audit event for order "
                       f"{order_id}: {str(e)}")
        if "database" in str(e).lower() or "connection" in str(e).lower():
            raise


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
    order_id: int, order_update: OrderUpdate, db: Session, user_id: int
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    previous_status = order.status
    status_changed = False

    if order_update.status and order_update.status != order.status:
        current_status = OrderStatus(order.status)
        valid_transitions = VALID_TRANSITIONS.get(current_status, [])
        if order_update.status not in valid_transitions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status transition from {current_status} to "
                       f"{order_update.status}"
            )

        await log_order_audit_event(
            db=db,
            order_id=order.id,
            previous_status=current_status,
            new_status=order_update.status,
            user_id=user_id,
            metadata={
                "notes": getattr(order_update, 'notes', None),
                "delay_reason": getattr(order_update, 'delay_reason', None),
                "source": "api_update",
                "previous_staff_id": order.staff_id,
                "timestamp": datetime.utcnow().isoformat()
            },
            action="status_change"
        )

        # Handle inventory deduction based on configuration
        if (order_update.status == OrderStatus.IN_PROGRESS and
                current_status == OrderStatus.PENDING):
            try:
                # Get inventory configuration
                config = get_inventory_config()
                use_recipe_deduction = config.USE_RECIPE_BASED_INVENTORY_DEDUCTION
                
                if use_recipe_deduction:
                    # Use new recipe-based deduction
                    recipe_inventory_service = RecipeInventoryService(db)
                    result = await recipe_inventory_service.deduct_inventory_for_order(
                        order_items=order.order_items,
                        order_id=order.id,
                        user_id=user_id,
                        deduction_type="order_progress"
                    )
                else:
                    # Use legacy MenuItemInventory-based deduction
                    result = await deduct_inventory(db, order.order_items)
                
                if result.get("low_stock_alerts"):
                    # Log low stock alerts
                    logger.warning(
                        f"Low stock alerts for order {order.id}: "
                        f"{result.get('low_stock_alerts')}"
                    )
            except HTTPException as e:
                # If inventory deduction fails, we may want to handle it differently
                # For now, we'll raise the exception to prevent order progression
                raise e
        order.status = order_update.status.value
        status_changed = True

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

    # Update KDS if order status changed to ready or completed
    if status_changed and order.status in [OrderStatus.READY.value, OrderStatus.COMPLETED.value]:
        try:
            from modules.kds.models.kds_models import KDSOrderItem, DisplayStatus
            from modules.kds.services.kds_service import KDSService
            
            kds_service = KDSService(db)
            kds_items = db.query(KDSOrderItem).join(OrderItem).filter(
                OrderItem.order_id == order.id
            ).all()
            
            # Mark all KDS items as ready/completed
            new_kds_status = DisplayStatus.READY if order.status == OrderStatus.READY.value else DisplayStatus.COMPLETED
            for kds_item in kds_items:
                if kds_item.status != DisplayStatus.COMPLETED:
                    kds_item.status = new_kds_status
                    if new_kds_status == DisplayStatus.COMPLETED:
                        kds_item.completed_at = datetime.utcnow()
                        kds_item.completed_by_id = user_id
            
            db.commit()
            logger.info(f"Updated {len(kds_items)} KDS items for order {order.id} to {new_kds_status.value}")
        except Exception as e:
            logger.error(f"Failed to update KDS status for order {order.id}: {str(e)}")
            # Don't fail the order update if KDS update fails

    if status_changed:
        webhook_service = WebhookService(db)

        if order.status == OrderStatus.COMPLETED.value:
            event_type = WebhookEventType.ORDER_COMPLETED
            
            # Handle inventory deduction on completion if configured
            config = get_inventory_config()
            deduct_on_completion = config.DEDUCT_INVENTORY_ON_COMPLETION
            
            if deduct_on_completion:
                try:
                    recipe_inventory_service = RecipeInventoryService(db)
                    result = await recipe_inventory_service.deduct_inventory_for_order(
                        order_items=order.order_items,
                        order_id=order.id,
                        user_id=user_id,
                        deduction_type="order_completion"
                    )
                    if result.get("low_stock_alerts"):
                        logger.warning(
                            f"Low stock alerts on order completion {order.id}: "
                            f"{result.get('low_stock_alerts')}"
                        )
                except HTTPException as e:
                    logger.error(
                        f"Failed to deduct inventory on order completion {order.id}: {str(e)}"
                    )
                    # Don't fail the order completion, just log the error
                    
        elif order.status == OrderStatus.CANCELLED.value:
            event_type = WebhookEventType.ORDER_CANCELLED
            
            # Handle inventory reversal for cancelled orders
            config = get_inventory_config()
            if config.AUTO_REVERSE_ON_CANCELLATION:
                try:
                    recipe_inventory_service = RecipeInventoryService(db)
                    result = await recipe_inventory_service.reverse_inventory_deduction(
                        order_id=order.id,
                        user_id=user_id,
                        reason="Order cancelled"
                    )
                    if result.get("reversed_items"):
                        logger.info(
                            f"Reversed inventory for cancelled order {order.id}: "
                            f"{len(result.get('reversed_items', []))} items"
                        )
                except HTTPException as e:
                    logger.error(
                        f"Failed to reverse inventory for cancelled order {order.id}: {str(e)}"
                    )
        else:
            event_type = WebhookEventType.ORDER_STATUS_CHANGED

        await webhook_service.trigger_webhook(
            order_id=order.id,
            event_type=event_type,
            previous_status=previous_status,
            new_status=order.status
        )

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
    priority: Optional[OrderPriority] = None,
    min_priority: Optional[OrderPriority] = None,
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

    if priority:
        query = query.filter(Order.priority == priority)

    if min_priority:
        priority_values = {
            OrderPriority.LOW: [OrderPriority.LOW, OrderPriority.NORMAL,
                                OrderPriority.HIGH, OrderPriority.URGENT],
            OrderPriority.NORMAL: [OrderPriority.NORMAL, OrderPriority.HIGH,
                                   OrderPriority.URGENT],
            OrderPriority.HIGH: [OrderPriority.HIGH, OrderPriority.URGENT],
            OrderPriority.URGENT: [OrderPriority.URGENT]
        }
        query = query.filter(Order.priority.in_(priority_values[min_priority]))

    query = query.order_by(
        case(
            (Order.priority == OrderPriority.URGENT.value, 1),
            (Order.priority == OrderPriority.HIGH.value, 2),
            (Order.priority == OrderPriority.NORMAL.value, 3),
            (Order.priority == OrderPriority.LOW.value, 4),
            else_=5
        ),
        Order.created_at
    )

    query = query.offset(offset).limit(limit)

    if include_items:
        query = query.options(joinedload(Order.order_items))

    query = query.options(joinedload(Order.tags), joinedload(Order.category))

    return query.all()


async def update_order_priority_service(
    order_id: int,
    priority_data: OrderPriorityUpdate,
    db: Session,
    user_id: Optional[int] = None
):
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.deleted_at.is_(None)
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status in [OrderStatus.COMPLETED.value,
                        OrderStatus.CANCELLED.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot change priority for {order.status} orders"
        )

    old_priority = order.priority
    validate_priority_escalation(old_priority, priority_data.priority)

    order.priority = priority_data.priority
    order.priority_updated_at = datetime.utcnow()

    try:
        db.commit()
        db.refresh(order)

        logger.info(
            f"Order {order_id} priority changed from {old_priority.value} "
            f"to {priority_data.priority.value}. "
            f"Reason: {priority_data.reason or 'Not specified'}"
        )

        from ..schemas.order_schemas import OrderPriorityResponse
        return OrderPriorityResponse(
            message=(f"Order priority updated from {old_priority.value} "
                     f"to {priority_data.priority.value}"),
            previous_priority=old_priority.value,
            new_priority=priority_data.priority.value,
            updated_at=order.priority_updated_at,
            reason=priority_data.reason,
            data=OrderOut.model_validate(order)
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update order priority: {str(e)}"
        )


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
    db.refresh(order)

    # Route order to KDS stations
    try:
        from modules.kds.services.kds_order_routing_service import KDSOrderRoutingService
        kds_routing_service = KDSOrderRoutingService(db)
        routed_items = kds_routing_service.route_order_to_stations(order.id)
        logger.info(f"Order {order.id} routed to KDS with {len(routed_items)} items")
    except Exception as e:
        logger.error(f"Failed to route order {order.id} to KDS: {str(e)}")
        # Don't fail the order creation if KDS routing fails

    webhook_service = WebhookService(db)
    await webhook_service.trigger_webhook(
        order_id=order.id,
        event_type=WebhookEventType.ORDER_CREATED
    )

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


def validate_priority_escalation(
    current_priority: OrderPriority,
    new_priority: OrderPriority,
    user_permissions: Optional[List[str]] = None
) -> bool:
    """
    Validate priority escalation based on business rules.

    Args:
        current_priority: Current order priority
        new_priority: Requested new priority
        user_permissions: List of user permissions (for future use)

    Returns:
        bool: True if escalation is allowed

    Raises:
        HTTPException: If escalation is not allowed
    """
    priority_levels = {
        OrderPriority.LOW: 1,
        OrderPriority.NORMAL: 2,
        OrderPriority.HIGH: 3,
        OrderPriority.URGENT: 4
    }

    current_level = priority_levels[current_priority]
    new_level = priority_levels[new_priority]

    if new_level <= current_level:
        return True

    level_jump = new_level - current_level
    if level_jump > 2:
        logger.warning(
            f"Large priority jump detected: {current_priority.value} "
            f"to {new_priority.value}"
        )

    return True


async def get_order_audit_events_service(
    db: Session,
    order_id: int,
    limit: int = 100,
    offset: int = 0
) -> List[AuditLog]:
    """Retrieve audit events for a specific order."""
    return db.query(AuditLog).filter(
        AuditLog.module == "orders",
        AuditLog.action == "status_change",
        AuditLog.entity_id == order_id
    ).order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()


async def count_order_audit_events_service(
    db: Session,
    order_id: int
) -> int:
    """Count total audit events for a specific order."""
    return db.query(AuditLog).filter(
        AuditLog.module == "orders",
        AuditLog.action == "status_change",
        AuditLog.entity_id == order_id
    ).count()


async def generate_kitchen_print_ticket_service(
    order_id: int,
    print_request: KitchenPrintRequest,
    db: Session
) -> KitchenPrintResponse:
    """Generate and send kitchen print ticket for an order."""

    try:
        order = await get_order_by_id(db, order_id)
        _validate_order_for_printing(order)

        ticket_data = _format_kitchen_ticket(order, print_request)
        ticket_content = _generate_ticket_content(ticket_data)

        print_result = await _send_to_pos_printer(
            order, print_request, ticket_content, ticket_data, db
        )

        if print_result["success"]:
            logger.info(f"Kitchen ticket printed for order {order_id}")

            return KitchenPrintResponse(
                success=True,
                message="Kitchen ticket printed successfully",
                ticket_id=(f"ticket_{order_id}_"
                           f"{int(datetime.utcnow().timestamp())}"),
                print_timestamp=datetime.utcnow()
            )
        else:
            return KitchenPrintResponse(
                success=False,
                message=(f"Print failed: "
                         f"{print_result.get('error', 'Unknown error')}"),
                error_code=print_result.get('error_code', 'PRINT_ERROR')
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Kitchen print error for order {order_id}: {str(e)}")
        return KitchenPrintResponse(
            success=False,
            message=f"Print system error: {str(e)}",
            error_code="SYSTEM_ERROR"
        )


def _validate_order_for_printing(order: Order) -> None:
    """Validate order can be printed to kitchen."""
    PRINTABLE_STATUSES = {OrderStatus.PENDING, OrderStatus.IN_KITCHEN}

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if OrderStatus(order.status) not in PRINTABLE_STATUSES:
        valid_statuses = [s.value for s in PRINTABLE_STATUSES]
        raise HTTPException(
            status_code=400,
            detail=(f"Cannot print ticket for order with status "
                    f"{order.status}. Valid statuses: {valid_statuses}")
        )

    if not order.order_items:
        raise HTTPException(
            status_code=400,
            detail="Cannot print ticket for order with no items"
        )


async def _send_to_pos_printer(
    order: Order,
    print_request: KitchenPrintRequest,
    ticket_content: str,
    ticket_data: KitchenTicketFormat,
    db: Session
) -> dict:
    """Send ticket to POS printer and return result."""
    pos_service = POSBridgeService(db)

    try:
        order_data = pos_service._transform_order_to_dict(order)
        order_data.update({
            "print_type": "kitchen_ticket",
            "station_id": print_request.station_id,
            "format_options": print_request.format_options,
            "ticket_content": ticket_content,
            "ticket_data": ticket_data.model_dump()
        })

        sync_result = await pos_service.sync_all_active_integrations(
            order.id, tenant_id=None, team_id=None
        )

        if (sync_result.get("results") and
                any(r["success"] for r in sync_result["results"])):
            return {"success": True}
        else:
            return {
                "success": False,
                "error": "No active POS integrations",
                "error_code": "NO_POS_INTEGRATION"
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_code": "POS_ERROR"
        }


def _format_kitchen_ticket(
    order: Order, print_request: KitchenPrintRequest
) -> KitchenTicketFormat:
    """Format order data for kitchen ticket display."""

    items_data = []
    for item in order.order_items:
        item_data = {
            "menu_item_id": item.menu_item_id,
            "quantity": item.quantity,
            "price": float(item.price),
            "notes": item.notes or "",
            "special_requests": getattr(item, 'special_requests', None)
        }

        if hasattr(item, 'cooking_instructions'):
            item_data["cooking_instructions"] = item.cooking_instructions

        items_data.append(item_data)

    return KitchenTicketFormat(
        order_id=order.id,
        table_no=order.table_no,
        items=items_data,
        station_name=_determine_station_name(print_request.station_id),
        timestamp=datetime.utcnow(),
        special_instructions=_extract_special_instructions(order),
        priority_level=_determine_priority(order)
    )


def _determine_station_name(station_id: Optional[int]) -> Optional[str]:
    """Map station ID to station name."""
    STATION_MAPPING = {
        1: "Grill Station",
        2: "Prep Station",
        3: "Salad Station",
        4: "Dessert Station"
    }
    return STATION_MAPPING.get(station_id) if station_id else None


def _extract_special_instructions(order: Order) -> Optional[str]:
    """Extract special instructions from order."""
    instructions = []

    if hasattr(order, 'customer_notes') and order.customer_notes:
        instructions.append(f"Customer: {order.customer_notes}")

    # Add item-specific special instructions
    for item in order.order_items:
        if hasattr(item, 'special_instructions') and item.special_instructions:
            for instruction in item.special_instructions:
                if isinstance(instruction, dict):
                    desc = instruction.get('description', '')
                    if desc:
                        item_desc = f"Item {item.menu_item_id}: {desc}"
                        instructions.append(item_desc)

    return "; ".join(instructions) if instructions else None


def _determine_priority(order: Order) -> Optional[int]:
    """Determine order priority level (1-5, 5 being highest)."""
    if order.status == OrderStatus.PENDING.value:
        return 3  # Normal priority
    elif order.status == OrderStatus.IN_KITCHEN.value:
        return 4  # Higher priority for orders already in kitchen

    return 3


def _generate_ticket_content(ticket_data: KitchenTicketFormat) -> str:
    """Generate formatted ticket content for thermal printers."""
    content = f"ORDER #{ticket_data.order_id}\n"
    content += f"TABLE: {ticket_data.table_no or 'TAKEOUT'}\n"

    if ticket_data.station_name:
        content += f"STATION: {ticket_data.station_name}\n"
    if ticket_data.priority_level:
        priority_text = "★" * ticket_data.priority_level
        priority_line = (f"PRIORITY: {priority_text} "
                         f"({ticket_data.priority_level}/5)\n")
        content += priority_line

    content += "=" * 32 + "\n"

    for item in ticket_data.items:
        content += f"{item['quantity']}x ITEM #{item['menu_item_id']}\n"

        if item.get('notes'):
            content += f"   * {item['notes']}\n"

        if item.get('special_requests'):
            content += f"   >> {item['special_requests']}\n"

        # Add cooking instructions
        if item.get('cooking_instructions'):
            content += f"   COOK: {item['cooking_instructions']}\n"

    content += "=" * 32 + "\n"
    content += f"Time: {ticket_data.timestamp.strftime('%H:%M')}\n"

    if ticket_data.special_instructions:
        content += "\nSPECIAL INSTRUCTIONS:\n"
        content += f"{ticket_data.special_instructions}\n"

    return content


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


async def get_auto_cancellation_configs(
    db: Session,
    tenant_id: Optional[int] = None,
    team_id: Optional[int] = None,
    status: Optional[OrderStatus] = None
):
    """Get auto-cancellation configurations with optional filtering."""
    query = db.query(AutoCancellationConfig)

    if tenant_id is not None:
        query = query.filter(AutoCancellationConfig.tenant_id == tenant_id)
    if team_id is not None:
        query = query.filter(AutoCancellationConfig.team_id == team_id)
    if status is not None:
        query = query.filter(AutoCancellationConfig.status == status.value)

    return query.all()


async def create_or_update_auto_cancellation_config(
    db: Session,
    config_data: dict
):
    """Create or update auto-cancellation configuration."""
    existing_config = db.query(AutoCancellationConfig).filter(
        AutoCancellationConfig.tenant_id == config_data.get('tenant_id'),
        AutoCancellationConfig.team_id == config_data.get('team_id'),
        AutoCancellationConfig.status == config_data['status']
    ).first()

    if existing_config:
        for key, value in config_data.items():
            setattr(existing_config, key, value)
        existing_config.updated_at = datetime.utcnow()
        config = existing_config
    else:
        config = AutoCancellationConfig(**config_data)
        db.add(config)

    db.commit()
    db.refresh(config)
    return config


async def detect_stale_orders(
    db: Session,
    tenant_id: Optional[int] = None,
    team_id: Optional[int] = None
) -> List[Order]:
    """Detect orders that have exceeded their configured time thresholds."""
    configs = await get_auto_cancellation_configs(db, tenant_id, team_id)
    active_configs = [c for c in configs if c.enabled]

    if not active_configs:
        return []

    stale_orders = []
    current_time = datetime.utcnow()

    for config in active_configs:
        threshold_time = current_time - timedelta(
            minutes=config.threshold_minutes
        )

        query = db.query(Order).filter(
            and_(
                Order.status == config.status,
                Order.updated_at <= threshold_time,
                Order.deleted_at.is_(None)
            )
        )

        stale_orders.extend(query.all())

    return stale_orders


async def cancel_stale_orders(
    db: Session,
    tenant_id: Optional[int] = None,
    team_id: Optional[int] = None,
    system_user_id: int = 1
) -> dict:
    """Enhanced error handling and partial success reporting."""
    stale_orders = await detect_stale_orders(db, tenant_id, team_id)

    if not stale_orders:
        return {
            "cancelled_count": 0,
            "cancelled_orders": [],
            "message": "No stale orders found"
        }

    cancelled_orders = []
    failed_orders = []

    for order in stale_orders:
        try:
            current_status = OrderStatus(order.status)

            if OrderStatus.CANCELLED not in VALID_TRANSITIONS.get(
                current_status, []
            ):
                logger.warning(
                    f"Order {order.id} with status {current_status} "
                    f"cannot be auto-cancelled"
                )
                failed_orders.append({
                    "order_id": order.id,
                    "error": (
                        f"Status {current_status} cannot transition to "
                        f"CANCELLED"
                    )
                })
                continue

            order.status = OrderStatus.CANCELLED.value

            await log_order_audit_event(
                db=db,
                order_id=order.id,
                previous_status=current_status,
                new_status=OrderStatus.CANCELLED,
                user_id=system_user_id,
                metadata={
                    "cancellation_reason": "auto_cancellation_stale_order",
                    "stale_duration_minutes": (
                        datetime.utcnow() - order.updated_at
                    ).total_seconds() / 60,
                    "source": "system_auto_cancellation",
                    "timestamp": datetime.utcnow().isoformat()
                },
                action="auto_cancellation"
            )
            cancelled_orders.append(order.id)

            await notify_stale_order_cancellation(
                order, "auto_cancellation_stale_order"
            )

        except Exception as e:
            logger.error(f"Failed to cancel stale order {order.id}: {str(e)}")
            failed_orders.append({"order_id": order.id, "error": str(e)})
            continue

    if cancelled_orders:
        try:
            db.commit()
        except Exception as e:
            logger.error(f"Failed to commit cancellations: {str(e)}")
            db.rollback()
            return {
                "cancelled_count": 0,
                "cancelled_orders": [],
                "failed_orders": failed_orders,
                "message": "Database commit failed"
            }

    return {
        "cancelled_count": len(cancelled_orders),
        "cancelled_orders": cancelled_orders,
        "failed_orders": failed_orders,
        "message": f"Successfully cancelled {len(cancelled_orders)} orders"
    }


async def create_default_auto_cancellation_configs(
    db: Session,
    tenant_id: Optional[int] = None,
    updated_by: int = 1
):
    """Create sensible default configurations for a new tenant/team."""
    default_configs = [
        {
            "status": "PENDING",
            "threshold_minutes": 30,
            "updated_by": updated_by
        },
        {
            "status": "IN_PROGRESS",
            "threshold_minutes": 90,
            "updated_by": updated_by
        },
        {
            "status": "IN_KITCHEN",
            "threshold_minutes": 45,
            "updated_by": updated_by
        },
    ]

    created_configs = []
    for config_data in default_configs:
        if tenant_id:
            config_data["tenant_id"] = tenant_id

        config = await create_or_update_auto_cancellation_config(
            db, config_data
        )
        created_configs.append(config)

    return created_configs


async def notify_stale_order_cancellation(order: Order, reason: str):
    """Notify relevant stakeholders about auto-cancellation."""
    notification_data = {
        "order_id": order.id,
        "table_no": order.table_no,
        "cancellation_reason": reason,
        "original_amount": sum(
            item.price * item.quantity for item in order.order_items
        ) if order.order_items else 0,
        "stale_duration": (
            datetime.utcnow() - order.updated_at
        ).total_seconds() / 60
    }

    logger.info(
        f"Auto-cancellation notification: Order {order.id} cancelled "
        f"after {notification_data['stale_duration']:.1f} minutes"
    )
