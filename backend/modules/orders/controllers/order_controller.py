from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from fastapi import HTTPException, UploadFile
from ..services.order_service import (
    update_order_service, get_order_by_id as get_order_service,
    get_orders_service, validate_multi_item_rules,
    create_order_with_fraud_check,
    schedule_delayed_fulfillment, get_scheduled_orders,
    add_tags_to_order, remove_tag_from_order, set_order_category,
    create_tag, get_tags, create_category, get_categories,
    archive_order_service, restore_order_service, get_archived_orders_service,
    update_order_priority_service, get_order_audit_events_service,
    count_order_audit_events_service, generate_kitchen_print_ticket_service,
    update_customer_notes, add_attachment, get_attachments, delete_attachment
)
from ..schemas.order_schemas import (
    OrderUpdate, OrderOut, MultiItemRuleRequest, RuleValidationResult,
    DelayFulfillmentRequest, OrderTagRequest, OrderCategoryRequest,
    TagCreate, TagOut, CategoryCreate, CategoryOut, OrderPriorityUpdate,
    OrderAuditResponse, OrderAuditEvent,
    KitchenPrintRequest, KitchenPrintResponse,
    CustomerNotesUpdate, OrderAttachmentOut, OrderItemUpdate
)
from ..enums.order_enums import OrderStatus, OrderPriority


async def update_order(order_id: int, order_data: OrderUpdate, db: Session,
                       user_id: int):
    return await update_order_service(order_id, order_data, db, user_id)


async def get_order_by_id(db: Session, order_id: int):
    return await get_order_service(db, order_id)


async def list_orders(
    db: Session,
    status: Optional[str] = None,
    staff_id: Optional[int] = None,
    table_no: Optional[int] = None,
    tag_ids: Optional[List[int]] = None,
    category_id: Optional[int] = None,
    priority: Optional[OrderPriority] = None,
    min_priority: Optional[OrderPriority] = None,
    limit: int = 100,
    offset: int = 0,
    include_items: bool = False
) -> List[OrderOut]:
    orders = await get_orders_service(
        db, status=status, staff_id=staff_id, table_no=table_no,
        tag_ids=tag_ids, category_id=category_id, priority=priority,
        min_priority=min_priority, limit=limit, offset=offset,
        include_items=include_items
    )
    return [OrderOut.model_validate(order) for order in orders]


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


async def validate_special_instructions(
    order_items: List[OrderItemUpdate],
    db: Session
) -> dict:
    validation_results = []
    for item in order_items:
        if item.special_instructions:
            if len(item.special_instructions) > 10:
                validation_results.append({
                    "item_id": item.menu_item_id,
                    "error": (f"Too many instructions (max 10), "
                              f"got {len(item.special_instructions)}")
                })

            for instruction in item.special_instructions:
                if not instruction.description.strip():
                    validation_results.append({
                        "item_id": item.menu_item_id,
                        "error": "Instruction description cannot be empty"
                    })

                if (instruction.priority and
                        (instruction.priority < 1 or
                         instruction.priority > 5)):
                    validation_results.append({
                        "item_id": item.menu_item_id,
                        "error": (f"Priority must be between 1-5, "
                                  f"got {instruction.priority}")
                    })

                if (instruction.target_station and
                        len(instruction.target_station) > 50):
                    validation_results.append({
                        "item_id": item.menu_item_id,
                        "error": (f"Station name too long (max 50 chars), "
                                  f"got {len(instruction.target_station)}")
                    })
    return {
        "valid": len(validation_results) == 0,
        "errors": validation_results
    }


async def create_order_with_validation(
    order_data: dict,
    db: Session,
    skip_fraud_check: bool = False
):
    return await create_order_with_fraud_check(
        db,
        order_data,
        perform_fraud_validation=not skip_fraud_check
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


async def archive_order(order_id: int, db: Session):
    return await archive_order_service(db, order_id)


async def restore_order(order_id: int, db: Session):
    return await restore_order_service(db, order_id)


async def list_archived_orders(
    db: Session,
    staff_id: Optional[int] = None,
    table_no: Optional[int] = None,
    limit: int = 100,
    offset: int = 0
) -> List[OrderOut]:
    orders = await get_archived_orders_service(
        db, staff_id=staff_id, table_no=table_no,
        limit=limit, offset=offset
    )
    return [OrderOut.model_validate(order) for order in orders]


async def update_order_priority(
    order_id: int,
    priority_data: OrderPriorityUpdate,
    db: Session
):
    return await update_order_priority_service(order_id, priority_data, db)


async def get_order_audit_trail(
    db: Session,
    order_id: int,
    limit: int = 100,
    offset: int = 0
) -> OrderAuditResponse:
    """Get audit trail for a specific order with enhanced error handling."""
    order = await get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    events_data = await get_order_audit_events_service(db, order_id, limit,
                                                       offset)
    total_count = await count_order_audit_events_service(db, order_id)

    events = []
    for event in events_data:
        try:
            previous_status = None
            if event.previous_value:
                try:
                    previous_status = OrderStatus(event.previous_value)
                except ValueError:
                    previous_status = None

            new_status = OrderStatus(event.new_value)
            events.append(OrderAuditEvent(
                id=event.id,
                order_id=event.entity_id,
                action=event.action,
                previous_status=previous_status,
                new_status=new_status,
                user_id=event.user_id,
                timestamp=event.timestamp,
                metadata=event.audit_metadata or {}
            ))
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Skipping malformed audit record "
                           f"{event.id}: {str(e)}")
            continue
    has_more = len(events) < total_count
    return OrderAuditResponse(events=events, total_count=total_count,
                              has_more=has_more)


async def generate_kitchen_print_ticket(
    order_id: int,
    print_request: KitchenPrintRequest,
    db: Session
) -> KitchenPrintResponse:
    return await generate_kitchen_print_ticket_service(
        order_id, print_request, db
    )


async def update_order_notes(
    order_id: int, notes_update: CustomerNotesUpdate, db: Session
):
    return await update_customer_notes(order_id, notes_update, db)


async def upload_order_attachment(
    order_id: int,
    file: UploadFile,
    db: Session,
    description: Optional[str] = None,
    is_public: bool = False
):
    return await add_attachment(order_id, file, db, description, is_public)


async def list_order_attachments(
    order_id: int, db: Session
) -> List[OrderAttachmentOut]:
    return await get_attachments(order_id, db)


async def remove_order_attachment(attachment_id: int, db: Session):
    return await delete_attachment(attachment_id, db)


async def get_auto_cancellation_configs_controller(
    db: Session,
    tenant_id: Optional[int] = None,
    team_id: Optional[int] = None,
    status: Optional[OrderStatus] = None
):
    """Get auto-cancellation configurations."""
    from ..services.order_service import get_auto_cancellation_configs
    return await get_auto_cancellation_configs(db, tenant_id, team_id, status)


async def create_auto_cancellation_config_controller(
    config_data: dict, db: Session
):
    """Create or update auto-cancellation configuration."""
    from ..services.order_service import (
        create_or_update_auto_cancellation_config
    )
    return await create_or_update_auto_cancellation_config(db, config_data)


async def trigger_stale_order_cancellation_controller(
    db: Session,
    tenant_id: Optional[int] = None,
    team_id: Optional[int] = None,
    system_user_id: int = 1
):
    """Manually trigger stale order cancellation process."""
    from ..services.order_service import cancel_stale_orders
    return await cancel_stale_orders(db, tenant_id, team_id, system_user_id)


async def detect_stale_orders_controller(
    db: Session,
    tenant_id: Optional[int] = None,
    team_id: Optional[int] = None
):
    """Detect stale orders without cancelling them."""
    from ..services.order_service import detect_stale_orders
    orders = await detect_stale_orders(db, tenant_id, team_id)
    return [OrderOut.model_validate(order) for order in orders]
