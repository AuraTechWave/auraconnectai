import logging
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException
from typing import List, Dict, Any
from datetime import datetime
from decimal import Decimal
from ..models.payment_reconciliation_models import PaymentReconciliation
from ..models.order_models import Order
from ..schemas.payment_reconciliation_schemas import (
    PaymentReconciliationCreate, PaymentReconciliationUpdate,
    PaymentReconciliationOut, ReconciliationRequest, ReconciliationResponse,
    ReconciliationFilter, ResolutionRequest
)
from ..enums.payment_enums import ReconciliationStatus, DiscrepancyType

logger = logging.getLogger(__name__)


async def create_payment_reconciliation(
    db: Session,
    reconciliation_data: PaymentReconciliationCreate
) -> PaymentReconciliationOut:
    order = db.query(Order).filter(
        Order.id == reconciliation_data.order_id
    ).first()
    if not order:
        raise HTTPException(
            status_code=404,
            detail=f"Order with id {reconciliation_data.order_id} not found"
        )

    existing = db.query(PaymentReconciliation).filter(
        PaymentReconciliation.external_payment_reference ==
        reconciliation_data.external_payment_reference
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Payment reconciliation with reference "
                   f"{reconciliation_data.external_payment_reference} "
                   f"already exists"
        )

    reconciliation = PaymentReconciliation(
        order_id=reconciliation_data.order_id,
        external_payment_reference=reconciliation_data.external_payment_reference,  # noqa: E501
        amount_expected=reconciliation_data.amount_expected,
        amount_received=reconciliation_data.amount_received,
        reconciliation_status=reconciliation_data.reconciliation_status.value,
        discrepancy_type=reconciliation_data.discrepancy_type.value if reconciliation_data.discrepancy_type else None,  # noqa: E501
        discrepancy_details=reconciliation_data.discrepancy_details
    )

    db.add(reconciliation)
    db.commit()
    db.refresh(reconciliation)

    return PaymentReconciliationOut.model_validate(reconciliation)


async def get_payment_reconciliation_by_id(
    db: Session,
    reconciliation_id: int
) -> PaymentReconciliationOut:
    reconciliation = db.query(PaymentReconciliation).filter(
        PaymentReconciliation.id == reconciliation_id
    ).first()

    if not reconciliation:
        raise HTTPException(
            status_code=404,
            detail=f"Payment reconciliation with id {reconciliation_id} "
                   f"not found"
        )

    return PaymentReconciliationOut.model_validate(reconciliation)


async def update_payment_reconciliation(
    db: Session,
    reconciliation_id: int,
    update_data: PaymentReconciliationUpdate
) -> PaymentReconciliationOut:
    reconciliation = db.query(PaymentReconciliation).filter(
        PaymentReconciliation.id == reconciliation_id
    ).first()

    if not reconciliation:
        raise HTTPException(
            status_code=404,
            detail=f"Payment reconciliation with id {reconciliation_id} "
                   f"not found"
        )

    update_dict = update_data.model_dump(exclude_unset=True)

    for field, value in update_dict.items():
        if hasattr(reconciliation, field):
            enum_fields = ['reconciliation_status', 'discrepancy_type',
                           'reconciliation_action']
            if field in enum_fields:
                setattr(reconciliation, field,
                        value.value if value else None)
            else:
                setattr(reconciliation, field, value)

    if update_data.reconciliation_status == ReconciliationStatus.RESOLVED:
        reconciliation.resolved_at = datetime.utcnow()

    db.commit()
    db.refresh(reconciliation)

    return PaymentReconciliationOut.model_validate(reconciliation)


async def get_payment_reconciliations(
    db: Session,
    filters: ReconciliationFilter
) -> List[PaymentReconciliationOut]:
    query = db.query(PaymentReconciliation)

    if filters.reconciliation_status:
        query = query.filter(
            PaymentReconciliation.reconciliation_status ==
            filters.reconciliation_status.value
        )

    if filters.discrepancy_type:
        query = query.filter(
            PaymentReconciliation.discrepancy_type ==
            filters.discrepancy_type.value
        )

    if filters.order_id:
        query = query.filter(
            PaymentReconciliation.order_id == filters.order_id
        )

    if filters.from_date:
        query = query.filter(
            PaymentReconciliation.created_at >= filters.from_date
        )

    if filters.to_date:
        query = query.filter(
            PaymentReconciliation.created_at <= filters.to_date
        )

    query = query.offset(filters.offset).limit(filters.limit)
    query = query.options(joinedload(PaymentReconciliation.order))

    reconciliations = query.all()
    return [PaymentReconciliationOut.model_validate(r)
            for r in reconciliations]


async def perform_payment_reconciliation(
    db: Session,
    request: ReconciliationRequest
) -> ReconciliationResponse:
    matched_count = 0
    discrepancy_count = 0
    reconciliations = []

    orders_query = db.query(Order)
    if request.order_ids:
        orders_query = orders_query.filter(Order.id.in_(request.order_ids))

    orders = orders_query.all()

    pos_payments = await _get_pos_payments(db, orders)

    for order in orders:
        order_total = sum(float(item.price) * item.quantity
                          for item in order.order_items)

        matching_payment = None
        for payment in pos_payments:
            order_ref_match = (payment.get('order_reference') ==
                               str(order.id))
            amount_diff = abs(payment.get('amount', 0) - order_total)
            threshold = float(request.amount_threshold)
            if order_ref_match and amount_diff <= threshold:
                matching_payment = payment
                break

        if matching_payment:
            reconciliation_data = PaymentReconciliationCreate(
                order_id=order.id,
                external_payment_reference=matching_payment['reference'],
                amount_expected=Decimal(str(order_total)),
                amount_received=Decimal(str(matching_payment['amount'])),
                reconciliation_status=ReconciliationStatus.MATCHED
            )
            matched_count += 1
        else:
            timestamp = datetime.utcnow().timestamp()
            ref = f"MISSING_{order.id}_{timestamp}"
            reconciliation_data = PaymentReconciliationCreate(
                order_id=order.id,
                external_payment_reference=ref,
                amount_expected=Decimal(str(order_total)),
                amount_received=Decimal('0'),
                reconciliation_status=ReconciliationStatus.DISCREPANCY,
                discrepancy_type=DiscrepancyType.MISSING_PAYMENT,
                discrepancy_details=f"No matching payment found for "
                                    f"order {order.id}"
            )
            discrepancy_count += 1

        reconciliation = await create_payment_reconciliation(
            db, reconciliation_data
        )
        reconciliations.append(reconciliation)

    return ReconciliationResponse(
        total_processed=len(orders),
        matched_count=matched_count,
        discrepancy_count=discrepancy_count,
        reconciliations=reconciliations
    )


async def resolve_payment_discrepancy(
    db: Session,
    reconciliation_id: int,
    resolution_data: ResolutionRequest
) -> PaymentReconciliationOut:
    update_data = PaymentReconciliationUpdate(
        reconciliation_status=ReconciliationStatus.RESOLVED,
        reconciliation_action=resolution_data.reconciliation_action,
        resolution_notes=resolution_data.resolution_notes,
        resolved_by=resolution_data.resolved_by
    )

    return await update_payment_reconciliation(db, reconciliation_id,
                                               update_data)


async def _get_pos_payments(db: Session, orders: List[Order]) -> List[Dict[str, Any]]:  # noqa: E501
    mock_payments = []
    for order in orders[:len(orders)//2]:
        order_total = sum(float(item.price) * item.quantity
                          for item in order.order_items)
        timestamp = datetime.utcnow().timestamp()
        mock_payments.append({
            'reference': f"POS_{order.id}_{timestamp}",
            'order_reference': str(order.id),
            'amount': order_total,
            'timestamp': datetime.utcnow()
        })

    return mock_payments
