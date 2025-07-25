import logging
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from fastapi import HTTPException
from typing import List, Dict, Any, Optional
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
from ...pos.interfaces.payment_provider import MockPOSProvider

logger = logging.getLogger(__name__)


async def create_payment_reconciliation(
    db: Session,
    reconciliation_data: PaymentReconciliationCreate,
    current_user_id: Optional[int] = None
) -> PaymentReconciliationOut:
    order = db.query(Order).filter(
        Order.id == reconciliation_data.order_id
    ).first()
    if not order:
        raise HTTPException(
            status_code=404,
            detail=f"Order {reconciliation_data.order_id} not found"
        )

    if hasattr(order, 'status') and order.status in ['CANCELLED', 'REFUNDED']:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reconcile {order.status} orders"
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

    amount_diff = abs(reconciliation_data.amount_expected -
                      reconciliation_data.amount_received)
    if amount_diff > Decimal('0.01'):  # More than 1 cent difference
        reconciliation_data.reconciliation_status = (
            ReconciliationStatus.DISCREPANCY
        )
        reconciliation_data.discrepancy_type = (
            DiscrepancyType.AMOUNT_MISMATCH
        )
        if not reconciliation_data.discrepancy_details:
            reconciliation_data.discrepancy_details = (
                f"Amount difference: ${amount_diff}"
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

        best_match = None
        best_score = 0.0

        for payment in pos_payments:
            score = calculate_match_score(order, payment, order_total)
            if score > best_score and score >= 0.5:
                best_score = score
                best_match = payment

        matching_payment = best_match

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


def calculate_match_score(order: Order, payment: Dict[str, Any],
                          order_total: float) -> float:
    """Calculate matching score between order and payment."""
    score = 0.0

    if payment.get('order_reference') == str(order.id):
        score += 0.5

    amount_diff = abs(payment.get('amount', 0) - order_total)
    if amount_diff == 0:
        score += 0.3
    elif amount_diff <= 1.0:
        score += 0.2
    elif amount_diff <= 5.0:
        score += 0.1

    payment_time = payment.get('timestamp')
    if payment_time and hasattr(order, 'created_at'):
        time_diff = abs((payment_time - order.created_at).total_seconds())
        if time_diff <= 3600:
            score += 0.2
        elif time_diff <= 7200:
            score += 0.1

    return score


async def _get_pos_payments(db: Session,
                            orders: List[Order]) -> List[Dict[str, Any]]:
    """Get payments from POS system using provider interface."""
    provider = MockPOSProvider({})
    order_ids = [order.id for order in orders]
    return await provider.get_payments(order_ids=order_ids)


async def get_reconciliation_metrics(db: Session) -> Dict[str, Any]:
    """Get reconciliation metrics for dashboard."""
    total_reconciled = db.query(PaymentReconciliation).count()

    matched_count = db.query(PaymentReconciliation).filter(
        PaymentReconciliation.reconciliation_status ==
        ReconciliationStatus.MATCHED.value
    ).count()

    discrepancy_count = db.query(PaymentReconciliation).filter(
        PaymentReconciliation.reconciliation_status ==
        ReconciliationStatus.DISCREPANCY.value
    ).count()

    resolved_count = db.query(PaymentReconciliation).filter(
        PaymentReconciliation.reconciliation_status ==
        ReconciliationStatus.RESOLVED.value
    ).count()

    success_rate = ((matched_count + resolved_count) / total_reconciled *
                    100 if total_reconciled > 0 else 0)

    discrepancy_types = db.query(
        PaymentReconciliation.discrepancy_type,
        func.count(PaymentReconciliation.id).label('count')
    ).filter(
        PaymentReconciliation.discrepancy_type.isnot(None)
    ).group_by(
        PaymentReconciliation.discrepancy_type
    ).order_by(
        func.count(PaymentReconciliation.id).desc()
    ).limit(5).all()

    return {
        'total_reconciled': total_reconciled,
        'matched_count': matched_count,
        'discrepancy_count': discrepancy_count,
        'resolved_count': resolved_count,
        'success_rate': round(success_rate, 2),
        'common_discrepancy_types': [
            {'type': dt[0], 'count': dt[1]} for dt in discrepancy_types
        ]
    }


async def auto_reconcile_pending(db: Session) -> Dict[str, Any]:
    """Automatically reconcile pending reconciliations."""
    pending_reconciliations = db.query(PaymentReconciliation).filter(
        PaymentReconciliation.reconciliation_status ==
        ReconciliationStatus.PENDING.value
    ).all()

    processed = 0
    matched = 0

    for reconciliation in pending_reconciliations:
        provider = MockPOSProvider({})
        payments = await provider.get_payments(
            order_ids=[reconciliation.order_id]
        )

        order = db.query(Order).filter(
            Order.id == reconciliation.order_id
        ).first()

        if order and payments:
            order_total = sum(float(item.price) * item.quantity
                              for item in order.order_items)

            best_match = None
            best_score = 0.0

            for payment in payments:
                score = calculate_match_score(order, payment, order_total)
                if score > best_score and score >= 0.7:
                    best_score = score
                    best_match = payment

            if best_match:
                status = ReconciliationStatus.MATCHED.value
                reconciliation.reconciliation_status = status
                amount = Decimal(str(best_match['amount']))
                reconciliation.amount_received = amount
                ref = best_match['reference']
                reconciliation.external_payment_reference = ref
                matched += 1

        processed += 1

    db.commit()

    return {
        'total_processed': processed,
        'auto_matched': matched,
        'remaining_pending': processed - matched
    }


async def handle_payment_webhook(db: Session,
                                 payment_data: Dict[str, Any]
                                 ) -> Dict[str, Any]:
    """Handle incoming payment webhook notification."""
    try:
        payment_reference = payment_data.get('reference')
        order_reference = payment_data.get('order_reference')
        amount = Decimal(str(payment_data.get('amount', 0)))

        if not payment_reference or not order_reference:
            raise HTTPException(
                status_code=400,
                detail="Missing required payment reference or order reference"
            )

        order = db.query(Order).filter(
            Order.id == int(order_reference)
        ).first()

        if not order:
            raise HTTPException(
                status_code=404,
                detail=f"Order {order_reference} not found"
            )

        existing = db.query(PaymentReconciliation).filter(
            PaymentReconciliation.external_payment_reference ==
            payment_reference
        ).first()

        if existing:
            return {
                'status': 'already_exists',
                'reconciliation_id': existing.id,
                'message': f"Reconciliation for payment {payment_reference} "
                          f"already exists"
            }

        order_total = sum(float(item.price) * item.quantity
                          for item in order.order_items)
        expected_amount = Decimal(str(order_total))

        amount_diff = abs(float(amount - expected_amount))
        if amount_diff <= 0.01:
            status = ReconciliationStatus.MATCHED
            discrepancy_type = None
            discrepancy_details = None
        else:
            status = ReconciliationStatus.DISCREPANCY
            discrepancy_type = DiscrepancyType.AMOUNT_MISMATCH
            details = f"Expected: ${expected_amount}, Received: ${amount}"
            discrepancy_details = details

        reconciliation_data = PaymentReconciliationCreate(
            order_id=order.id,
            external_payment_reference=payment_reference,
            amount_expected=expected_amount,
            amount_received=amount,
            reconciliation_status=status,
            discrepancy_type=discrepancy_type,
            discrepancy_details=discrepancy_details
        )

        reconciliation = await create_payment_reconciliation(
            db, reconciliation_data)

        return {
            'status': 'created',
            'reconciliation_id': reconciliation.id,
            'reconciliation_status': status.value,
            'message': f"Reconciliation created for payment "
                      f"{payment_reference}"
        }

    except Exception as e:
        logger.error(f"Error handling payment webhook: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing payment webhook: {str(e)}"
        )
