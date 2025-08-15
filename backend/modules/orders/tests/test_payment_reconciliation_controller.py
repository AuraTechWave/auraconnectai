import pytest
from decimal import Decimal
from modules.orders.controllers.payment_reconciliation_controller import (  # noqa: E501
    create_reconciliation,
    get_reconciliation_by_id,
    update_reconciliation,
    list_reconciliations,
    reconcile_payments,
    resolve_discrepancy,
)
from modules.orders.schemas.payment_reconciliation_schemas import (
    PaymentReconciliationCreate,
    PaymentReconciliationUpdate,
    ReconciliationRequest,
    ReconciliationFilter,
    ResolutionRequest,
)
from modules.orders.enums.payment_enums import (
    ReconciliationStatus,
    DiscrepancyType,
    ReconciliationAction,
)


class TestPaymentReconciliationController:

    @pytest.mark.asyncio
    async def test_create_reconciliation(self, db_session, sample_order):
        reconciliation_data = PaymentReconciliationCreate(
            order_id=sample_order.id,
            external_payment_reference="PAY_CTRL_123",
            amount_expected=Decimal("30.00"),
            amount_received=Decimal("30.00"),
            reconciliation_status=ReconciliationStatus.MATCHED,
        )

        result = await create_reconciliation(reconciliation_data, db_session)

        assert result.order_id == sample_order.id
        assert result.external_payment_reference == "PAY_CTRL_123"
        assert result.reconciliation_status == ReconciliationStatus.MATCHED

    @pytest.mark.asyncio
    async def test_get_reconciliation_by_id(self, db_session, sample_order):
        reconciliation_data = PaymentReconciliationCreate(
            order_id=sample_order.id,
            external_payment_reference="PAY_CTRL_456",
            amount_expected=Decimal("25.00"),
            amount_received=Decimal("25.00"),
            reconciliation_status=ReconciliationStatus.MATCHED,
        )

        created = await create_reconciliation(reconciliation_data, db_session)
        result = await get_reconciliation_by_id(created.id, db_session)

        assert result.id == created.id
        assert result.external_payment_reference == "PAY_CTRL_456"

    @pytest.mark.asyncio
    async def test_update_reconciliation(self, db_session, sample_order):
        reconciliation_data = PaymentReconciliationCreate(
            order_id=sample_order.id,
            external_payment_reference="PAY_CTRL_789",
            amount_expected=Decimal("40.00"),
            amount_received=Decimal("35.00"),
            reconciliation_status=ReconciliationStatus.DISCREPANCY,
            discrepancy_type=DiscrepancyType.AMOUNT_MISMATCH,
        )

        created = await create_reconciliation(reconciliation_data, db_session)

        update_data = PaymentReconciliationUpdate(
            reconciliation_status=ReconciliationStatus.RESOLVED,
            reconciliation_action=ReconciliationAction.MANUAL_REVIEW,
        )

        result = await update_reconciliation(created.id, update_data, db_session)

        assert result.reconciliation_status == ReconciliationStatus.RESOLVED
        action = ReconciliationAction.MANUAL_REVIEW
        assert result.reconciliation_action == action

    @pytest.mark.asyncio
    async def test_list_reconciliations(self, db_session, sample_order):
        reconciliation_data = PaymentReconciliationCreate(
            order_id=sample_order.id,
            external_payment_reference="PAY_CTRL_LIST",
            amount_expected=Decimal("20.00"),
            amount_received=Decimal("20.00"),
            reconciliation_status=ReconciliationStatus.MATCHED,
        )

        await create_reconciliation(reconciliation_data, db_session)

        filters = ReconciliationFilter(
            reconciliation_status=ReconciliationStatus.MATCHED
        )

        results = await list_reconciliations(filters, db_session)

        assert len(results) >= 1
        status = ReconciliationStatus.MATCHED
        assert all(r.reconciliation_status == status for r in results)

    @pytest.mark.asyncio
    async def test_reconcile_payments(self, db_session, sample_order):
        request = ReconciliationRequest(
            order_ids=[sample_order.id], amount_threshold=Decimal("0.01")
        )

        result = await reconcile_payments(request, db_session)

        assert result.total_processed == 1
        assert isinstance(result.matched_count, int)
        assert isinstance(result.discrepancy_count, int)
        assert len(result.reconciliations) == 1

    @pytest.mark.asyncio
    async def test_resolve_discrepancy(self, db_session, sample_order):
        reconciliation_data = PaymentReconciliationCreate(
            order_id=sample_order.id,
            external_payment_reference="PAY_CTRL_RESOLVE",
            amount_expected=Decimal("50.00"),
            amount_received=Decimal("45.00"),
            reconciliation_status=ReconciliationStatus.DISCREPANCY,
            discrepancy_type=DiscrepancyType.AMOUNT_MISMATCH,
        )

        created = await create_reconciliation(reconciliation_data, db_session)

        resolution_data = ResolutionRequest(
            reconciliation_action=ReconciliationAction.EXCEPTION_HANDLED,
            resolution_notes="Discount applied",
            resolved_by=1,
        )

        result = await resolve_discrepancy(created.id, resolution_data, db_session)

        assert result.reconciliation_status == ReconciliationStatus.RESOLVED
        action = ReconciliationAction.EXCEPTION_HANDLED
        assert result.reconciliation_action == action
        assert result.resolution_notes == "Discount applied"
