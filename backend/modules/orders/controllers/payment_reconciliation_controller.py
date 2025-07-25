from sqlalchemy.orm import Session
from typing import List
from typing import Optional
from ..services.payment_reconciliation_service import (
    create_payment_reconciliation, get_payment_reconciliation_by_id,
    update_payment_reconciliation, get_payment_reconciliations,
    perform_payment_reconciliation, resolve_payment_discrepancy,
    get_reconciliation_metrics, auto_reconcile_pending, handle_payment_webhook
)
from ..schemas.payment_reconciliation_schemas import (
    PaymentReconciliationCreate, PaymentReconciliationUpdate,
    PaymentReconciliationOut, ReconciliationRequest, ReconciliationResponse,
    ReconciliationFilter, ResolutionRequest, ReconciliationMetrics,
    AutoReconcileResponse, PaymentWebhookData, WebhookResponse
)


async def create_reconciliation(
    reconciliation_data: PaymentReconciliationCreate,
    db: Session,
    current_user_id: Optional[int] = None
) -> PaymentReconciliationOut:
    return await create_payment_reconciliation(
        db, reconciliation_data, current_user_id
    )


async def get_reconciliation_by_id(
    reconciliation_id: int,
    db: Session
) -> PaymentReconciliationOut:
    return await get_payment_reconciliation_by_id(db, reconciliation_id)


async def update_reconciliation(
    reconciliation_id: int,
    update_data: PaymentReconciliationUpdate,
    db: Session
) -> PaymentReconciliationOut:
    return await update_payment_reconciliation(db, reconciliation_id,
                                               update_data)


async def list_reconciliations(
    filters: ReconciliationFilter,
    db: Session
) -> List[PaymentReconciliationOut]:
    return await get_payment_reconciliations(db, filters)


async def reconcile_payments(
    request: ReconciliationRequest,
    db: Session
) -> ReconciliationResponse:
    return await perform_payment_reconciliation(db, request)


async def resolve_discrepancy(
    reconciliation_id: int,
    resolution_data: ResolutionRequest,
    db: Session
) -> PaymentReconciliationOut:
    return await resolve_payment_discrepancy(
        db, reconciliation_id, resolution_data
    )


async def get_metrics(db: Session) -> ReconciliationMetrics:
    metrics_data = await get_reconciliation_metrics(db)
    return ReconciliationMetrics(**metrics_data)


async def auto_reconcile(db: Session) -> AutoReconcileResponse:
    result = await auto_reconcile_pending(db)
    return AutoReconcileResponse(**result)


async def handle_webhook(
    webhook_data: PaymentWebhookData,
    db: Session
) -> WebhookResponse:
    result = await handle_payment_webhook(db, webhook_data.dict())
    return WebhookResponse(**result)
