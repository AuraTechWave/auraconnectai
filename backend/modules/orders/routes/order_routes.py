from fastapi import APIRouter, Depends, Query, UploadFile, File, Path, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from core.database import get_db
from ..controllers.order_controller import (
    update_order, get_order_by_id, list_orders, list_kitchen_orders,
    validate_order_rules, validate_special_instructions,
    delay_order_fulfillment, get_delayed_orders,
    add_order_tags, remove_order_tag, update_order_category,
    create_new_tag, list_tags, create_new_category, list_categories,
    archive_order, restore_order, list_archived_orders, update_order_priority,
    get_order_audit_trail, update_order_notes, upload_order_attachment,
    list_order_attachments, remove_order_attachment
)
from ..services.order_service import get_orders_service
from ..controllers.fraud_controller import (
    check_order_fraud, list_fraud_alerts, resolve_alert
)
from ..schemas.order_schemas import (
    OrderUpdate, OrderOut, MultiItemRuleRequest, RuleValidationResult,
    DelayFulfillmentRequest, OrderTagRequest, OrderCategoryRequest,
    TagCreate, TagOut, CategoryCreate, CategoryOut, OrderPriorityUpdate,
    OrderPriorityResponse, OrderAuditResponse, FraudCheckRequest,
    FraudCheckResponse, CustomerNotesUpdate, OrderAttachmentOut,
    AttachmentResponse, OrderItemUpdate, AutoCancellationConfigCreate,
    AutoCancellationConfigOut, StaleCancellationResponse
)
from ..models.order_models import Order
from ..enums.order_enums import (
    OrderStatus, OrderPriority, CheckpointType, FraudRiskLevel
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
    user_id: int,
    db: Session = Depends(get_db)
):
    return await update_order(order_id, order_data, db, user_id)


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


@router.post("/validate-special-instructions")
async def validate_special_instructions_endpoint(
    order_items: List[OrderItemUpdate],
    db: Session = Depends(get_db)
):
    """
    Validate special instructions for order items including priority ranges
    and instruction type validation.
    """
    return await validate_special_instructions(order_items, db)


@router.post("/{order_id}/fraud-check", response_model=FraudCheckResponse)
async def perform_order_fraud_check(
    order_id: int,
    checkpoint_types: Optional[List[CheckpointType]] = None,
    force_recheck: bool = False,
    db: Session = Depends(get_db)
):
    """
    Perform fraud detection check on a specific order.

    - **order_id**: ID of the order to check
    - **checkpoint_types**: Specific types of checks to perform
    - **force_recheck**: Force recheck even if recently checked
    """
    fraud_request = FraudCheckRequest(
        order_id=order_id,
        checkpoint_types=checkpoint_types,
        force_recheck=force_recheck
    )
    return await check_order_fraud(fraud_request, db)


@router.get("/fraud-alerts", response_model=List[dict])
async def get_fraud_alerts(
    resolved: Optional[bool] = Query(
        None, description="Filter by resolution status"),
    severity: Optional[FraudRiskLevel] = Query(
        None, description="Filter by severity level"),
    limit: int = Query(100, ge=1, le=1000,
                       description="Number of alerts to return"),
    offset: int = Query(0, ge=0, description="Number of alerts to skip"),
    db: Session = Depends(get_db)
):
    """
    Retrieve fraud alerts with optional filtering.

    - **resolved**: Filter by resolution status
    - **severity**: Filter by severity level (low, medium, high, critical)
    - **limit**: Maximum number of alerts to return
    - **offset**: Number of alerts to skip for pagination
    """
    return await list_fraud_alerts(db, resolved, severity, limit, offset)


@router.put("/fraud-alerts/{alert_id}/resolve", response_model=dict)
async def resolve_fraud_alert(
    alert_id: int,
    db: Session = Depends(get_db)
):
    """
    Resolve a fraud alert by marking it as handled.

    - **alert_id**: ID of the alert to resolve
    """
    return await resolve_alert(db, alert_id)


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
    - **description**: Optional description of the tag
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


@router.put("/{order_id}/priority", response_model=OrderPriorityResponse)
async def update_priority(
    order_id: int = Path(..., gt=0, description="Order ID to update"),
    priority_data: OrderPriorityUpdate = Body(
        ..., description="Priority update data"),
    db: Session = Depends(get_db)
):
    """
    Update the priority of an order.

    Priority levels (highest to lowest):
    - URGENT: Critical orders requiring immediate attention
    - HIGH: Important orders that should be prioritized
    - NORMAL: Standard priority (default)
    - LOW: Orders that can wait if needed

    **Notes:**
    - Cannot change priority for completed or cancelled orders
    - Priority changes are logged with timestamps
    - Kitchen display will reflect new priority immediately
    """
    return await update_order_priority(order_id, priority_data, db)


@router.get("/queue", response_model=List[OrderOut])
async def get_kitchen_queue(
    priority_filter: Optional[OrderPriority] = Query(
        None, description="Filter by minimum priority"),
    db: Session = Depends(get_db)
):
    """Get kitchen queue sorted by priority."""
    from ..enums.order_enums import OrderStatus

    kitchen_statuses = [OrderStatus.PENDING.value,
                        OrderStatus.IN_PROGRESS.value]

    orders = await get_orders_service(
        db=db,
        status=None,
        min_priority=priority_filter,
        include_items=True,
        limit=50
    )

    kitchen_orders = [order for order in orders
                      if order.status in kitchen_statuses]
    return kitchen_orders


@router.get("/analytics/priority-distribution")
async def get_priority_distribution(
    date_from: Optional[datetime] = Query(
        None, description="Start date for analysis"),
    date_to: Optional[datetime] = Query(
        None, description="End date for analysis"),
    db: Session = Depends(get_db)
):
    """Get distribution of orders by priority level."""
    from sqlalchemy import func

    query = db.query(
        Order.priority,
        func.count(Order.id).label('count')
    ).group_by(Order.priority)

    if date_from:
        query = query.filter(Order.created_at >= date_from)
    if date_to:
        query = query.filter(Order.created_at <= date_to)

    results = query.all()
    return {
        (row.priority.value if hasattr(row.priority, 'value')
         else str(row.priority)): row.count
        for row in results
    }


@router.get("/{order_id}/audit", response_model=OrderAuditResponse)
async def get_order_audit_history(
    order_id: int,
    limit: int = Query(100, ge=1, le=1000,
                       description="Number of audit events to return"),
    offset: int = Query(0, ge=0, description="Number of audit events to skip"),
    db: Session = Depends(get_db)
):
    """
    Retrieve audit trail for a specific order showing all status changes.

    - **order_id**: ID of the order to get audit history for
    - **limit**: Maximum number of audit events to return (1-1000)
    - **offset**: Number of audit events to skip for pagination
    """
    return await get_order_audit_trail(db, order_id, limit, offset)


@router.put("/{order_id}/notes", response_model=dict)
async def update_notes(
    order_id: int,
    notes_update: CustomerNotesUpdate,
    db: Session = Depends(get_db)
):
    """
    Update customer notes for an order.
    - **order_id**: ID of the order to update
    - **customer_notes**: New customer notes text (can be null to clear notes)
    """
    return await update_order_notes(order_id, notes_update, db)


@router.post("/{order_id}/attachments", response_model=AttachmentResponse)
async def upload_attachment(
    order_id: int,
    file: UploadFile = File(...),
    description: Optional[str] = None,
    is_public: bool = False,
    db: Session = Depends(get_db)
):
    """
    Upload a file attachment to an order.
    - **order_id**: ID of the order to attach the file to
    - **file**: File to upload (supports common document and image formats)
    """
    result = await upload_order_attachment(
        order_id, file, db, description, is_public
    )
    return AttachmentResponse(
        success=True,
        message=result["message"],
        data=result["data"]
    )


@router.get("/{order_id}/attachments", response_model=List[OrderAttachmentOut])
async def get_attachments(
    order_id: int,
    db: Session = Depends(get_db)
):
    """
    Get all attachments for an order.
    - **order_id**: ID of the order to get attachments for
    """
    return await list_order_attachments(order_id, db)


@router.delete("/attachments/{attachment_id}", response_model=dict)
async def delete_attachment(
    attachment_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a specific attachment.
    - **attachment_id**: ID of the attachment to delete
    """
    return await remove_order_attachment(attachment_id, db)


@router.get(
    "/auto-cancellation/configs",
    response_model=List[AutoCancellationConfigOut]
)
async def get_auto_cancellation_configs(
    tenant_id: Optional[int] = Query(
        None, description="Filter by tenant ID"
    ),
    team_id: Optional[int] = Query(
        None, description="Filter by team ID"
    ),
    status: Optional[OrderStatus] = Query(
        None, description="Filter by order status"
    ),
    db: Session = Depends(get_db)
):
    """
    Get auto-cancellation configurations with optional filtering.

    - **tenant_id**: Filter by tenant ID
    - **team_id**: Filter by team ID
    - **status**: Filter by order status
    """
    from ..controllers.order_controller import (
        get_auto_cancellation_configs_controller
    )
    configs = await get_auto_cancellation_configs_controller(
        db, tenant_id, team_id, status
    )
    return [
        AutoCancellationConfigOut.model_validate(config) for config in configs
    ]


@router.post(
    "/auto-cancellation/configs", response_model=AutoCancellationConfigOut
)
async def create_auto_cancellation_config(
    config_data: AutoCancellationConfigCreate,
    db: Session = Depends(get_db)
):
    """
    Create or update auto-cancellation configuration.

    - **status**: Order status to configure (PENDING, IN_PROGRESS, IN_KITCHEN)
    - **threshold_minutes**: Time threshold in minutes before cancellation
    - **enabled**: Whether auto-cancellation is enabled for this config
    - **tenant_id**: Optional tenant ID for multi-tenant setups
    - **team_id**: Optional team ID for team-specific configurations
    """
    from ..controllers.order_controller import (
        create_auto_cancellation_config_controller
    )
    config = await create_auto_cancellation_config_controller(
        config_data.dict(), db
    )
    return AutoCancellationConfigOut.model_validate(config)


@router.post(
    "/auto-cancellation/trigger", response_model=StaleCancellationResponse
)
async def trigger_stale_order_cancellation(
    tenant_id: Optional[int] = Query(
        None, description="Filter by tenant ID"
    ),
    team_id: Optional[int] = Query(
        None, description="Filter by team ID"
    ),
    system_user_id: int = Query(
        1, description="System user ID for audit logging"
    ),
    db: Session = Depends(get_db)
):
    """
    Manually trigger the stale order cancellation process.

    This endpoint allows manual execution of the auto-cancellation logic,
    useful for testing or immediate execution outside of scheduled runs.

    - **tenant_id**: Optional tenant ID filter
    - **team_id**: Optional team ID filter
    - **system_user_id**: User ID to use for audit logging (defaults to 1)
    """
    from ..controllers.order_controller import (
        trigger_stale_order_cancellation_controller
    )
    return await trigger_stale_order_cancellation_controller(
        db, tenant_id, team_id, system_user_id
    )


@router.get("/auto-cancellation/stale-orders", response_model=List[OrderOut])
async def detect_stale_orders(
    tenant_id: Optional[int] = Query(
        None, description="Filter by tenant ID"
    ),
    team_id: Optional[int] = Query(
        None, description="Filter by team ID"
    ),
    db: Session = Depends(get_db)
):
    """
    Detect stale orders without cancelling them.

    This endpoint identifies orders that would be cancelled by the
    auto-cancellation process without actually cancelling them.
    Useful for monitoring and testing.

    - **tenant_id**: Optional tenant ID filter
    - **team_id**: Optional team ID filter
    """
    from ..controllers.order_controller import detect_stale_orders_controller
    return await detect_stale_orders_controller(db, tenant_id, team_id)


@router.post(
    "/auto-cancellation/scheduled-run",
    response_model=StaleCancellationResponse
)
async def scheduled_auto_cancellation(
    tenant_id: Optional[int] = Query(
        None, description="Filter by tenant ID"
    ),
    team_id: Optional[int] = Query(
        None, description="Filter by team ID"
    ),
    system_user_id: int = Query(
        1, description="System user ID for audit logging"
    ),
    db: Session = Depends(get_db)
):
    """
    Endpoint for scheduled auto-cancellation execution.

    This endpoint is designed to be called by external schedulers or cron jobs
    to automatically cancel stale orders based on configured thresholds.

    - **tenant_id**: Optional tenant ID filter
    - **team_id**: Optional team ID filter
    - **system_user_id**: User ID to use for audit logging (defaults to 1)
    """
    from ..services.auto_cancellation_scheduler import (
        AutoCancellationScheduler
    )
    scheduler = AutoCancellationScheduler(db)
    return await scheduler.run_auto_cancellation(
        tenant_id, team_id, system_user_id
    )


@router.post("/auto-cancellation/create-defaults")
async def create_default_auto_cancellation_configs(
    tenant_id: Optional[int] = Query(None),
    updated_by: int = Query(1),
    db: Session = Depends(get_db)
):
    """Create default auto-cancellation configurations."""
    from ..controllers.order_controller import (
        create_default_configs_controller
    )
    configs = await create_default_configs_controller(
        db, tenant_id, updated_by
    )
    return {
        "message": f"Created {len(configs)} default configurations",
        "configs": [
            AutoCancellationConfigOut.model_validate(c) for c in configs
        ]
    }


@router.get("/auto-cancellation/metrics")
async def get_auto_cancellation_metrics(
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db)
):
    """Get auto-cancellation metrics and statistics."""
    from sqlalchemy import func
    from core.compliance import AuditLog

    query = db.query(
        func.count(AuditLog.id).label('total_cancellations'),
        func.date(AuditLog.timestamp).label('date')
    ).filter(
        AuditLog.action == 'auto_cancellation',
        AuditLog.module == 'orders'
    ).group_by(func.date(AuditLog.timestamp))

    if from_date:
        query = query.filter(AuditLog.timestamp >= from_date)
    if to_date:
        query = query.filter(AuditLog.timestamp <= to_date)

    results = query.all()

    return {
        "total_auto_cancelled": sum(r.total_cancellations for r in results),
        "daily_breakdown": [
            {"date": r.date.isoformat(), "count": r.total_cancellations}
            for r in results
        ]
    }
