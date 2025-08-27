"""
API routes for order splitting functionality.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.decorators import handle_api_errors
from core.auth import get_current_user
from core.rbac_models import RBACUser as User
from ..schemas.order_split_schemas import (
    OrderSplitRequest,
    OrderSplitResponse,
    PaymentSplitRequest,
    SplitOrderSummary,
    SplitPaymentDetail,
    PaymentStatus,
    BulkSplitRequest,
    SplitValidationResponse,
    MergeSplitRequest,
)
from ..services.order_split_service import OrderSplitService

router = APIRouter(prefix="/api/v1/orders", tags=["order-splits"])


@router.post("/{order_id}/split/validate", response_model=SplitValidationResponse)
@handle_api_errors
async def validate_order_split(
    order_id: int,
    split_request: OrderSplitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Validate if an order can be split as requested.

    This endpoint checks:
    - Order exists and is in a splittable state
    - Requested items exist and have sufficient quantities
    - Calculates estimated totals for the split

    Returns validation result with warnings if any.
    """
    service = OrderSplitService(db)
    return service.validate_split_request(order_id, split_request)


@router.post("/{order_id}/split", response_model=OrderSplitResponse)
@handle_api_errors
async def split_order(
    order_id: int,
    split_request: OrderSplitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Split an order into multiple orders.

    Supports three types of splits:
    - TICKET: Split for different kitchen tickets/stations
    - DELIVERY: Split for separate deliveries
    - PAYMENT: Split for payment purposes

    Creates new orders with the specified items and maintains
    relationships to the parent order.
    """
    service = OrderSplitService(db)
    return service.split_order(order_id, split_request, current_user.id)


# Bulk split endpoint removed - to be implemented in future release


@router.get("/{order_id}/splits", response_model=SplitOrderSummary)
@handle_api_errors
async def get_order_splits(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get summary of all splits for an order.

    Returns:
    - List of all split orders
    - Payment split details
    - Total amounts and payment status
    """
    service = OrderSplitService(db)
    return service.get_split_summary(order_id)


@router.post("/{order_id}/split/payment", response_model=OrderSplitResponse)
@handle_api_errors
async def split_order_payment(
    order_id: int,
    payment_request: PaymentSplitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Split payment for an order among multiple parties.

    Creates separate payment records for each split with:
    - Amount to be paid
    - Customer responsible
    - Payment method (optional)
    """
    # Use the payment-specific split method
    service = OrderSplitService(db)
    return service.split_order_for_payment(order_id, payment_request, current_user.id)


@router.put("/splits/payment/{payment_id}", response_model=SplitPaymentDetail)
@handle_api_errors
async def update_split_payment(
    payment_id: int,
    payment_status: PaymentStatus,
    payment_reference: str = Query(None, description="Payment reference number"),
    payment_method: str = Query(None, description="Payment method used"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update payment status for a split order.

    Updates the payment record with:
    - New payment status
    - Payment reference (if provided)
    - Payment method (if provided)
    """
    service = OrderSplitService(db)
    return service.update_split_payment(
        payment_id, payment_status, payment_reference, payment_method
    )


@router.post("/splits/merge", response_model=OrderSplitResponse)
@handle_api_errors
async def merge_split_orders(
    merge_request: MergeSplitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Merge split orders back together.

    Can either:
    - Merge back to the original parent order
    - Create a new merged order

    All items from split orders are consolidated.
    """
    service = OrderSplitService(db)
    return service.merge_split_orders(merge_request, current_user.id)


@router.get("/splits/by-table/{table_no}", response_model=List[SplitOrderSummary])
@handle_api_errors
async def get_table_splits(
    table_no: int,
    include_completed: bool = Query(False, description="Include completed splits"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all active splits for a table.

    Useful for:
    - Viewing all split checks at a table
    - Managing payment collection
    - Consolidating orders
    """
    from ..models.order_models import Order, OrderSplit
    from ..enums.order_enums import OrderStatus

    # Get all orders for the table
    query = db.query(Order).filter(
        Order.table_no == table_no, Order.deleted_at.is_(None)
    )

    if not include_completed:
        query = query.filter(
            ~Order.status.in_([OrderStatus.COMPLETED, OrderStatus.CANCELLED])
        )

    orders = query.all()

    # Get split summaries for parent orders
    service = OrderSplitService(db)
    summaries = []

    for order in orders:
        # Check if this order has splits
        has_splits = (
            db.query(OrderSplit).filter(OrderSplit.parent_order_id == order.id).first()
        )

        if has_splits:
            summary = service.get_split_summary(order.id)
            summaries.append(summary)

    return summaries


# KDS split endpoint removed - to be implemented with KDS module integration


@router.get("/{order_id}/splits/tracking")
@handle_api_errors
async def get_split_tracking(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get comprehensive tracking information for split orders.

    Returns:
    - Parent order information
    - All split orders grouped by type
    - Status summary across all splits
    - Payment collection progress
    """
    service = OrderSplitService(db)
    return service.get_split_tracking(order_id)


@router.put("/splits/{split_order_id}/status")
@handle_api_errors
async def update_split_status(
    split_order_id: int,
    new_status: str,
    notes: str = Query(None, description="Notes about the status change"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update the status of a split order.

    Tracks status changes in metadata for audit trail.
    """
    from ..enums.order_enums import OrderStatus

    # Validate status
    try:
        status_enum = OrderStatus(new_status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status: {new_status}",
        )

    service = OrderSplitService(db)
    return service.update_split_status(
        split_order_id, status_enum, current_user.id, notes
    )
