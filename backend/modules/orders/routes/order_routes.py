from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.core.database import get_db
from ..controllers.order_controller import (
    update_order, get_order_by_id, list_orders, list_kitchen_orders,
    validate_order_rules, create_order_with_validation
)
from ..controllers.fraud_controller import (
    check_order_fraud, list_fraud_alerts, resolve_alert
)
from ..schemas.order_schemas import (
    OrderUpdate, OrderOut, MultiItemRuleRequest, RuleValidationResult,
    FraudCheckRequest, FraudCheckResponse, FraudAlertOut
)
from ..enums.order_enums import CheckpointType, FraudRiskLevel

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
    resolved: Optional[bool] = Query(None, description="Filter by resolution status"),
    severity: Optional[FraudRiskLevel] = Query(None, description="Filter by severity level"),
    limit: int = Query(100, ge=1, le=1000, description="Number of alerts to return"),
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
