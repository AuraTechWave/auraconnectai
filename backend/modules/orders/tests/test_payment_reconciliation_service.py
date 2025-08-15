import pytest
from fastapi import HTTPException
from decimal import Decimal
from modules.orders.services.payment_reconciliation_service import (
    create_payment_reconciliation,
    get_payment_reconciliation_by_id,
    update_payment_reconciliation,
    get_payment_reconciliations,
    perform_payment_reconciliation,
    resolve_payment_discrepancy,
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
from modules.orders.models.order_models import Order, OrderItem


class TestPaymentReconciliationService:

    @pytest.mark.asyncio
    async def test_create_payment_reconciliation_success(
        self, db_session, sample_order
    ):
        reconciliation_data = PaymentReconciliationCreate(
            order_id=sample_order.id,
            external_payment_reference="PAY_123456",
            amount_expected=Decimal("25.50"),
            amount_received=Decimal("25.50"),
            reconciliation_status=ReconciliationStatus.MATCHED,
        )

        result = await create_payment_reconciliation(db_session, reconciliation_data)

        assert result.order_id == sample_order.id
        assert result.external_payment_reference == "PAY_123456"
        assert result.amount_expected == Decimal("25.50")
        assert result.amount_received == Decimal("25.50")
        assert result.reconciliation_status == ReconciliationStatus.MATCHED

    @pytest.mark.asyncio
    async def test_create_payment_reconciliation_order_not_found(self, db_session):
        reconciliation_data = PaymentReconciliationCreate(
            order_id=999,
            external_payment_reference="PAY_123456",
            amount_expected=Decimal("25.50"),
            amount_received=Decimal("25.50"),
            reconciliation_status=ReconciliationStatus.MATCHED,
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_payment_reconciliation(db_session, reconciliation_data)
        assert exc_info.value.status_code == 404
        assert "Order with id 999 not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_create_payment_reconciliation_duplicate_reference(
        self, db_session, sample_order
    ):
        reconciliation_data = PaymentReconciliationCreate(
            order_id=sample_order.id,
            external_payment_reference="PAY_123456",
            amount_expected=Decimal("25.50"),
            amount_received=Decimal("25.50"),
            reconciliation_status=ReconciliationStatus.MATCHED,
        )

        await create_payment_reconciliation(db_session, reconciliation_data)

        with pytest.raises(HTTPException) as exc_info:
            await create_payment_reconciliation(db_session, reconciliation_data)
        assert exc_info.value.status_code == 400
        assert "already exists" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_payment_reconciliation_by_id_success(
        self, db_session, sample_order
    ):
        reconciliation_data = PaymentReconciliationCreate(
            order_id=sample_order.id,
            external_payment_reference="PAY_123456",
            amount_expected=Decimal("25.50"),
            amount_received=Decimal("25.50"),
            reconciliation_status=ReconciliationStatus.MATCHED,
        )

        created = await create_payment_reconciliation(db_session, reconciliation_data)
        result = await get_payment_reconciliation_by_id(db_session, created.id)

        assert result.id == created.id
        assert result.external_payment_reference == "PAY_123456"

    @pytest.mark.asyncio
    async def test_get_payment_reconciliation_by_id_not_found(self, db_session):
        with pytest.raises(HTTPException) as exc_info:
            await get_payment_reconciliation_by_id(db_session, 999)
        assert exc_info.value.status_code == 404
        detail = "Payment reconciliation with id 999 not found"
        assert detail in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_update_payment_reconciliation_success(
        self, db_session, sample_order
    ):
        reconciliation_data = PaymentReconciliationCreate(
            order_id=sample_order.id,
            external_payment_reference="PAY_123456",
            amount_expected=Decimal("25.50"),
            amount_received=Decimal("20.00"),
            reconciliation_status=ReconciliationStatus.DISCREPANCY,
            discrepancy_type=DiscrepancyType.AMOUNT_MISMATCH,
        )

        created = await create_payment_reconciliation(db_session, reconciliation_data)

        update_data = PaymentReconciliationUpdate(
            reconciliation_status=ReconciliationStatus.RESOLVED,
            reconciliation_action=ReconciliationAction.MANUAL_REVIEW,
            resolution_notes="Resolved by manager",
            resolved_by=1,
        )

        result = await update_payment_reconciliation(
            db_session, created.id, update_data
        )

        assert result.reconciliation_status == ReconciliationStatus.RESOLVED
        action = ReconciliationAction.MANUAL_REVIEW
        assert result.reconciliation_action == action
        assert result.resolution_notes == "Resolved by manager"
        assert result.resolved_by == 1
        assert result.resolved_at is not None

    @pytest.mark.asyncio
    async def test_get_payment_reconciliations_with_filters(
        self, db_session, sample_order
    ):
        reconciliation1 = PaymentReconciliationCreate(
            order_id=sample_order.id,
            external_payment_reference="PAY_111",
            amount_expected=Decimal("25.50"),
            amount_received=Decimal("25.50"),
            reconciliation_status=ReconciliationStatus.MATCHED,
        )

        reconciliation2 = PaymentReconciliationCreate(
            order_id=sample_order.id,
            external_payment_reference="PAY_222",
            amount_expected=Decimal("30.00"),
            amount_received=Decimal("25.00"),
            reconciliation_status=ReconciliationStatus.DISCREPANCY,
            discrepancy_type=DiscrepancyType.AMOUNT_MISMATCH,
        )

        await create_payment_reconciliation(db_session, reconciliation1)
        await create_payment_reconciliation(db_session, reconciliation2)

        filters = ReconciliationFilter(
            reconciliation_status=ReconciliationStatus.DISCREPANCY
        )

        results = await get_payment_reconciliations(db_session, filters)

        assert len(results) == 1
        status = ReconciliationStatus.DISCREPANCY
        assert results[0].reconciliation_status == status

    @pytest.mark.asyncio
    async def test_perform_payment_reconciliation(self, db_session):
        order1 = Order(staff_id=1, status="pending")
        order2 = Order(staff_id=1, status="pending")
        db_session.add_all([order1, order2])
        db_session.commit()

        item1 = OrderItem(
            order_id=order1.id, menu_item_id=101, quantity=2, price=Decimal("12.50")
        )
        item2 = OrderItem(
            order_id=order2.id, menu_item_id=102, quantity=1, price=Decimal("15.00")
        )
        db_session.add_all([item1, item2])
        db_session.commit()

        request = ReconciliationRequest(
            order_ids=[order1.id, order2.id], amount_threshold=Decimal("0.01")
        )

        result = await perform_payment_reconciliation(db_session, request)

        assert result.total_processed == 2
        assert result.matched_count >= 0
        assert result.discrepancy_count >= 0
        assert len(result.reconciliations) == 2

    @pytest.mark.asyncio
    async def test_resolve_payment_discrepancy(self, db_session, sample_order):
        reconciliation_data = PaymentReconciliationCreate(
            order_id=sample_order.id,
            external_payment_reference="PAY_123456",
            amount_expected=Decimal("25.50"),
            amount_received=Decimal("20.00"),
            reconciliation_status=ReconciliationStatus.DISCREPANCY,
            discrepancy_type=DiscrepancyType.AMOUNT_MISMATCH,
        )

        created = await create_payment_reconciliation(db_session, reconciliation_data)

        resolution_data = ResolutionRequest(
            reconciliation_action=ReconciliationAction.EXCEPTION_HANDLED,
            resolution_notes="Customer provided additional payment",
            resolved_by=1,
        )

        result = await resolve_payment_discrepancy(
            db_session, created.id, resolution_data
        )

        assert result.reconciliation_status == ReconciliationStatus.RESOLVED
        action = ReconciliationAction.EXCEPTION_HANDLED
        assert result.reconciliation_action == action
        notes = "Customer provided additional payment"
        assert result.resolution_notes == notes
        assert result.resolved_by == 1
