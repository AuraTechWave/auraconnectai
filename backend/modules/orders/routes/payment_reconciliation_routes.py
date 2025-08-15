from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
import logging
from core.database import get_db
from ..controllers.payment_reconciliation_controller import (
    create_reconciliation,
    get_reconciliation_by_id,
    update_reconciliation,
    list_reconciliations,
    reconcile_payments,
    resolve_discrepancy,
    get_metrics,
    auto_reconcile,
    handle_webhook,
)
from ..schemas.payment_reconciliation_schemas import (
    PaymentReconciliationCreate,
    PaymentReconciliationUpdate,
    PaymentReconciliationOut,
    ReconciliationRequest,
    ReconciliationResponse,
    ReconciliationFilter,
    ResolutionRequest,
    ReconciliationMetrics,
    AutoReconcileResponse,
    PaymentWebhookData,
    WebhookResponse,
)
from ..enums.payment_enums import ReconciliationStatus, DiscrepancyType
from ..models.payment_reconciliation_models import PaymentReconciliation
from ..models.order_models import Order

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payment-reconciliation", tags=["Payment Reconciliation"])


@router.post("/", response_model=PaymentReconciliationOut)
async def create_payment_reconciliation(
    reconciliation_data: PaymentReconciliationCreate, db: Session = Depends(get_db)
):
    return await create_reconciliation(reconciliation_data, db)


@router.get("/{reconciliation_id}", response_model=PaymentReconciliationOut)
async def get_payment_reconciliation(
    reconciliation_id: int, db: Session = Depends(get_db)
):
    return await get_reconciliation_by_id(reconciliation_id, db)


@router.put("/{reconciliation_id}", response_model=PaymentReconciliationOut)
async def update_payment_reconciliation(
    reconciliation_id: int,
    update_data: PaymentReconciliationUpdate,
    db: Session = Depends(get_db),
):
    return await update_reconciliation(reconciliation_id, update_data, db)


@router.get("/", response_model=List[PaymentReconciliationOut])
async def get_payment_reconciliations(
    reconciliation_status: Optional[ReconciliationStatus] = Query(None),
    discrepancy_type: Optional[DiscrepancyType] = Query(None),
    order_id: Optional[int] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    filters = ReconciliationFilter(
        reconciliation_status=reconciliation_status,
        discrepancy_type=discrepancy_type,
        order_id=order_id,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )
    return await list_reconciliations(filters, db)


@router.post("/reconcile", response_model=ReconciliationResponse)
async def perform_payment_reconciliation(
    request: ReconciliationRequest, db: Session = Depends(get_db)
):
    return await reconcile_payments(request, db)


@router.post("/{reconciliation_id}/resolve", response_model=PaymentReconciliationOut)
async def resolve_payment_discrepancy(
    reconciliation_id: int,
    resolution_data: ResolutionRequest,
    db: Session = Depends(get_db),
):
    return await resolve_discrepancy(reconciliation_id, resolution_data, db)


@router.get("/metrics", response_model=ReconciliationMetrics)
async def get_reconciliation_metrics(db: Session = Depends(get_db)):
    """
    Get reconciliation metrics for dashboard insights.

    Returns comprehensive metrics including:
    - Total reconciliations processed
    - Success rates and counts by status
    - Common discrepancy types
    """
    return await get_metrics(db)


@router.post("/auto-reconcile", response_model=AutoReconcileResponse)
async def auto_reconcile_pending(db: Session = Depends(get_db)):
    """
    Automatically reconcile pending reconciliations.

    Uses enhanced matching logic to automatically match
    pending reconciliations with high confidence scores.
    """
    return await auto_reconcile(db)


@router.post("/webhook/payment-received", response_model=WebhookResponse)
async def handle_payment_webhook(
    payment_data: PaymentWebhookData, db: Session = Depends(get_db)
):
    """
    Handle real-time payment notification webhooks.

    Automatically creates reconciliation records when
    payments are received from external POS systems.
    """
    return await handle_webhook(payment_data, db)


@router.get("/analytics/reconciliation-summary")
async def get_reconciliation_summary(
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Get reconciliation analytics and KPIs.

    Returns detailed analytics including counts, totals, and variances
    grouped by reconciliation status for the specified date range.
    """
    from sqlalchemy import func

    query = db.query(
        PaymentReconciliation.reconciliation_status,
        func.count(PaymentReconciliation.id).label("count"),
        func.sum(PaymentReconciliation.amount_expected).label("total_expected"),
        func.sum(PaymentReconciliation.amount_received).label("total_received"),
    ).group_by(PaymentReconciliation.reconciliation_status)

    if from_date:
        query = query.filter(PaymentReconciliation.created_at >= from_date)
    if to_date:
        query = query.filter(PaymentReconciliation.created_at <= to_date)

    results = query.all()

    summary = {}
    for result in results:
        total_expected = float(result.total_expected or 0)
        total_received = float(result.total_received or 0)
        summary[result.reconciliation_status] = {
            "count": result.count,
            "total_expected": total_expected,
            "total_received": total_received,
            "variance": total_received - total_expected,
        }

    return summary


@router.post("/webhooks/pos-payment")
async def handle_pos_payment_webhook(payment_data: dict, db: Session = Depends(get_db)):
    """
    Handle real-time payment notifications from POS.

    Processes incoming payment webhooks and automatically creates
    reconciliation records with proper status detection.
    """
    try:
        order_reference = payment_data.get("order_reference")
        amount = Decimal(str(payment_data.get("amount", 0)))
        payment_reference = payment_data.get("payment_reference")

        if not order_reference or not payment_reference:
            logger.warning("Webhook: Missing required fields")
            return {"status": "missing_fields"}

        order = db.query(Order).filter(Order.id == order_reference).first()
        if not order:
            logger.warning(f"Webhook: Order {order_reference} not found")
            return {"status": "order_not_found"}

        order_total = sum(
            float(item.price) * item.quantity for item in order.order_items
        )
        expected_amount = Decimal(str(order_total))

        amount_diff = abs(amount - expected_amount)
        if amount_diff <= Decimal("0.01"):
            status = ReconciliationStatus.MATCHED
            discrepancy_type = None
            discrepancy_details = None
        else:
            status = ReconciliationStatus.DISCREPANCY
            discrepancy_type = DiscrepancyType.AMOUNT_MISMATCH
            discrepancy_details = f"Expected: ${expected_amount}, Received: ${amount}"

        reconciliation_data = PaymentReconciliationCreate(
            order_id=order.id,
            external_payment_reference=payment_reference,
            amount_expected=expected_amount,
            amount_received=amount,
            reconciliation_status=status,
            discrepancy_type=discrepancy_type,
            discrepancy_details=discrepancy_details,
        )

        await create_reconciliation(reconciliation_data, db)

        return {"status": "processed"}

    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")
