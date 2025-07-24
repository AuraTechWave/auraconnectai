import pytest
from fastapi import HTTPException
from backend.modules.orders.services.order_service import (
    get_order_by_id, update_order_service, get_orders_service,
    validate_multi_item_rules, archive_order_service, restore_order_service,
    get_archived_orders_service
)
from backend.modules.orders.schemas.order_schemas import (
    OrderUpdate, OrderItemUpdate
)
from backend.modules.orders.enums.order_enums import (
    OrderStatus, MultiItemRuleType
)
from backend.modules.orders.models.order_models import Order
from datetime import datetime


class TestOrderService:

    @pytest.mark.asyncio
    async def test_get_order_by_id_success(self, db_session, sample_order):
        """Test successful order retrieval by ID."""
        result = await get_order_by_id(db_session, sample_order.id)
        assert result.id == sample_order.id
        assert result.staff_id == sample_order.staff_id
        assert result.status == sample_order.status

    @pytest.mark.asyncio
    async def test_get_order_by_id_not_found(self, db_session):
        """Test order retrieval with non-existent ID."""
        with pytest.raises(HTTPException) as exc_info:
            await get_order_by_id(db_session, 999)
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_order_by_id_soft_deleted(self, db_session,
                                                sample_order):
        """Test that soft-deleted orders are not returned."""
        sample_order.deleted_at = datetime.utcnow()
        db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            await get_order_by_id(db_session, sample_order.id)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_order_status_valid_transition(self, db_session,
                                                        sample_order):
        """Test valid status transition."""
        update_data = OrderUpdate(status=OrderStatus.IN_PROGRESS)
        result = await update_order_service(
            sample_order.id, update_data, db_session)

        assert result["message"] == "Order updated successfully"
        assert result["data"].status == OrderStatus.IN_PROGRESS.value

    @pytest.mark.asyncio
    async def test_update_order_status_invalid_transition(self, db_session,
                                                          sample_order):
        """Test invalid status transition."""
        update_data = OrderUpdate(status=OrderStatus.COMPLETED)

        with pytest.raises(HTTPException) as exc_info:
            await update_order_service(sample_order.id, update_data,
                                       db_session)
        assert exc_info.value.status_code == 400
        assert "Invalid status transition" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_update_order_items(self, db_session, sample_order):
        """Test updating order items."""
        new_items = [
            OrderItemUpdate(menu_item_id=201, quantity=3, price=12.99,
                            notes="Medium rare"),
            OrderItemUpdate(menu_item_id=202, quantity=1, price=5.50)
        ]
        update_data = OrderUpdate(order_items=new_items)

        await update_order_service(sample_order.id, update_data, db_session)

        updated_order = db_session.query(Order).filter(
            Order.id == sample_order.id).first()
        assert len(updated_order.order_items) == 2
        assert updated_order.order_items[0].menu_item_id == 201
        assert updated_order.order_items[1].menu_item_id == 202

    @pytest.mark.asyncio
    async def test_get_orders_no_filters(self, db_session, sample_order):
        """Test getting orders without filters."""
        orders = await get_orders_service(db_session)
        assert len(orders) == 1
        assert orders[0].id == sample_order.id

    @pytest.mark.asyncio
    async def test_get_orders_filter_by_status(self, db_session):
        """Test filtering orders by status."""
        order1 = Order(staff_id=1, status=OrderStatus.PENDING.value)
        order2 = Order(staff_id=2, status=OrderStatus.IN_PROGRESS.value)
        db_session.add_all([order1, order2])
        db_session.commit()

        pending_orders = await get_orders_service(
            db_session, status=OrderStatus.PENDING.value)
        assert len(pending_orders) == 1
        assert pending_orders[0].status == OrderStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_get_orders_filter_by_staff_id(self, db_session):
        """Test filtering orders by staff ID."""
        order1 = Order(staff_id=1, status=OrderStatus.PENDING.value)
        order2 = Order(staff_id=2, status=OrderStatus.PENDING.value)
        db_session.add_all([order1, order2])
        db_session.commit()

        staff_orders = await get_orders_service(db_session, staff_id=1)
        assert len(staff_orders) == 1
        assert staff_orders[0].staff_id == 1

    @pytest.mark.asyncio
    async def test_get_orders_pagination(self, db_session):
        """Test order pagination."""
        orders = [Order(staff_id=i, status=OrderStatus.PENDING.value)
                  for i in range(5)]
        db_session.add_all(orders)
        db_session.commit()

        page1 = await get_orders_service(db_session, limit=2, offset=0)
        page2 = await get_orders_service(db_session, limit=2, offset=2)

        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0].id != page2[0].id

    @pytest.mark.asyncio
    async def test_get_orders_exclude_soft_deleted(self, db_session,
                                                   sample_order):
        """Test that soft-deleted orders are excluded."""
        sample_order.deleted_at = datetime.utcnow()
        db_session.commit()

        orders = await get_orders_service(db_session)
        assert len(orders) == 0


class TestMultiItemRules:

    @pytest.mark.asyncio
    async def test_combo_rule_validation_success(self):
        """Test successful combo rule validation."""
        items = [
            OrderItemUpdate(menu_item_id=101, quantity=1, price=12.99),
            OrderItemUpdate(menu_item_id=201, quantity=1, price=3.99)
        ]
        result = await validate_multi_item_rules(
            items, [MultiItemRuleType.COMBO]
        )
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_bulk_discount_rule_validation(self):
        """Test bulk discount rule validation."""
        items = [
            OrderItemUpdate(menu_item_id=101, quantity=3, price=12.99),
            OrderItemUpdate(menu_item_id=102, quantity=2, price=8.99)
        ]
        result = await validate_multi_item_rules(
            items, [MultiItemRuleType.BULK_DISCOUNT]
        )
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_compatibility_rule_failure(self):
        """Test compatibility rule validation failure."""
        items = [
            OrderItemUpdate(menu_item_id=101, quantity=1, price=12.99),
            OrderItemUpdate(menu_item_id=301, quantity=1, price=15.99)
        ]
        result = await validate_multi_item_rules(
            items, [MultiItemRuleType.COMPATIBILITY]
        )
        assert result.is_valid is False
        assert "not compatible" in result.message

    @pytest.mark.asyncio
    async def test_all_rules_validation(self):
        """Test validation with all rule types."""
        items = [
            OrderItemUpdate(menu_item_id=104, quantity=2, price=10.99),
            OrderItemUpdate(menu_item_id=105, quantity=1, price=7.99)
        ]
        result = await validate_multi_item_rules(items)
        assert result.is_valid is True


class TestArchiveService:

    @pytest.mark.asyncio
    async def test_archive_completed_order_success(self, db_session):
        """Test successful archiving of completed order."""
        order = Order(staff_id=1, status=OrderStatus.COMPLETED.value)
        db_session.add(order)
        db_session.commit()

        result = await archive_order_service(db_session, order.id)
        
        assert result["message"] == "Order archived successfully"
        assert result["data"].status == OrderStatus.ARCHIVED.value

    @pytest.mark.asyncio
    async def test_archive_cancelled_order_success(self, db_session):
        """Test successful archiving of cancelled order."""
        order = Order(staff_id=1, status=OrderStatus.CANCELLED.value)
        db_session.add(order)
        db_session.commit()

        result = await archive_order_service(db_session, order.id)
        
        assert result["message"] == "Order archived successfully"
        assert result["data"].status == OrderStatus.ARCHIVED.value

    @pytest.mark.asyncio
    async def test_archive_pending_order_failure(self, db_session):
        """Test that pending orders cannot be archived."""
        order = Order(staff_id=1, status=OrderStatus.PENDING.value)
        db_session.add(order)
        db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            await archive_order_service(db_session, order.id)
        
        assert exc_info.value.status_code == 400
        assert "Only completed or cancelled orders can be archived" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_restore_archived_order_success(self, db_session):
        """Test successful restoration of archived order."""
        order = Order(staff_id=1, status=OrderStatus.ARCHIVED.value)
        db_session.add(order)
        db_session.commit()

        result = await restore_order_service(db_session, order.id)
        
        assert result["message"] == "Order restored successfully"
        assert result["data"].status == OrderStatus.COMPLETED.value

    @pytest.mark.asyncio
    async def test_restore_non_archived_order_failure(self, db_session):
        """Test that non-archived orders cannot be restored."""
        order = Order(staff_id=1, status=OrderStatus.COMPLETED.value)
        db_session.add(order)
        db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            await restore_order_service(db_session, order.id)
        
        assert exc_info.value.status_code == 400
        assert "Only archived orders can be restored" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_archived_orders_filtering(self, db_session):
        """Test filtering of archived orders."""
        archived_order = Order(staff_id=1, status=OrderStatus.ARCHIVED.value)
        completed_order = Order(staff_id=1, status=OrderStatus.COMPLETED.value)
        db_session.add_all([archived_order, completed_order])
        db_session.commit()

        archived_orders = await get_archived_orders_service(db_session)
        
        assert len(archived_orders) == 1
        assert archived_orders[0].status == OrderStatus.ARCHIVED.value

    @pytest.mark.asyncio
    async def test_get_orders_excludes_archived_by_default(self, db_session):
        """Test that regular order queries exclude archived orders."""
        archived_order = Order(staff_id=1, status=OrderStatus.ARCHIVED.value)
        completed_order = Order(staff_id=1, status=OrderStatus.COMPLETED.value)
        db_session.add_all([archived_order, completed_order])
        db_session.commit()

        orders = await get_orders_service(db_session)
        
        assert len(orders) == 1
        assert orders[0].status == OrderStatus.COMPLETED.value
