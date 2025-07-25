import pytest
from fastapi import HTTPException
from backend.modules.orders.services.order_service import (
    get_order_by_id, update_order_service, get_orders_service,
    validate_multi_item_rules, schedule_delayed_fulfillment,
    get_scheduled_orders, process_due_delayed_orders,
    archive_order_service, restore_order_service,
    get_archived_orders_service, update_order_priority_service
)
from backend.modules.orders.schemas.order_schemas import (
    OrderUpdate, OrderItemUpdate, DelayFulfillmentRequest, OrderPriorityUpdate
)
from backend.modules.orders.enums.order_enums import (
    OrderStatus, MultiItemRuleType, DelayReason, OrderPriority
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


class TestDelayedFulfillment:

    @pytest.mark.asyncio
    async def test_schedule_delayed_fulfillment_success(self, db_session,
                                                        sample_order):
        """Test successful order delay scheduling."""
        future_time = datetime(2025, 12, 31, 15, 30, 0)
        delay_data = DelayFulfillmentRequest(
            scheduled_fulfillment_time=future_time,
            delay_reason=DelayReason.CUSTOMER_REQUEST.value,
            additional_notes="Customer requested later delivery"
        )

        result = await schedule_delayed_fulfillment(sample_order.id,
                                                    delay_data, db_session)

        assert result["message"] == "Order scheduled for delayed fulfillment"
        assert result["data"].status == OrderStatus.DELAYED.value
        assert result["data"].scheduled_fulfillment_time == future_time
        expected_reason = DelayReason.CUSTOMER_REQUEST.value
        assert result["data"].delay_reason == expected_reason
        assert result["data"].delay_requested_at is not None

    @pytest.mark.asyncio
    async def test_schedule_delayed_fulfillment_invalid_status(
        self, db_session, sample_order
    ):
        """Test delay scheduling with invalid order status."""
        sample_order.status = OrderStatus.COMPLETED.value
        db_session.commit()

        future_time = datetime(2025, 12, 31, 15, 30, 0)
        delay_data = DelayFulfillmentRequest(
            scheduled_fulfillment_time=future_time,
            delay_reason=DelayReason.CUSTOMER_REQUEST.value
        )

        with pytest.raises(HTTPException) as exc_info:
            await schedule_delayed_fulfillment(sample_order.id, delay_data,
                                               db_session)
        assert exc_info.value.status_code == 400
        assert "Cannot delay order" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_schedule_delayed_fulfillment_past_time(self, db_session,
                                                          sample_order):
        """Test delay scheduling with past time."""
        past_time = datetime(2020, 1, 1, 12, 0, 0)
        delay_data = DelayFulfillmentRequest(
            scheduled_fulfillment_time=past_time,
            delay_reason=DelayReason.CUSTOMER_REQUEST.value
        )

        with pytest.raises(HTTPException) as exc_info:
            await schedule_delayed_fulfillment(sample_order.id, delay_data,
                                               db_session)
        assert exc_info.value.status_code == 400
        assert "must be in the future" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_schedule_delayed_fulfillment_order_not_found(self,
                                                                db_session):
        """Test delay scheduling with non-existent order."""
        future_time = datetime(2025, 12, 31, 15, 30, 0)
        delay_data = DelayFulfillmentRequest(
            scheduled_fulfillment_time=future_time,
            delay_reason=DelayReason.CUSTOMER_REQUEST.value
        )

        with pytest.raises(HTTPException) as exc_info:
            await schedule_delayed_fulfillment(999, delay_data, db_session)
        assert exc_info.value.status_code == 404
        assert "Order not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_scheduled_orders_no_filters(self, db_session):
        """Test getting scheduled orders without filters."""
        order1 = Order(
            staff_id=1, status=OrderStatus.DELAYED.value,
            scheduled_fulfillment_time=datetime(2025, 12, 31, 10, 0, 0)
        )
        order2 = Order(
            staff_id=2, status=OrderStatus.SCHEDULED.value,
            scheduled_fulfillment_time=datetime(2025, 12, 31, 14, 0, 0)
        )
        db_session.add_all([order1, order2])
        db_session.commit()

        orders = await get_scheduled_orders(db_session)
        assert len(orders) == 2
        time_check = (orders[0].scheduled_fulfillment_time <=
                      orders[1].scheduled_fulfillment_time)
        assert time_check

    @pytest.mark.asyncio
    async def test_get_scheduled_orders_with_time_filters(self, db_session):
        """Test getting scheduled orders with time range filters."""
        order1 = Order(
            staff_id=1, status=OrderStatus.DELAYED.value,
            scheduled_fulfillment_time=datetime(2025, 12, 31, 10, 0, 0)
        )
        order2 = Order(
            staff_id=2, status=OrderStatus.SCHEDULED.value,
            scheduled_fulfillment_time=datetime(2025, 12, 31, 14, 0, 0)
        )
        order3 = Order(
            staff_id=3, status=OrderStatus.AWAITING_FULFILLMENT.value,
            scheduled_fulfillment_time=datetime(2025, 12, 31, 18, 0, 0)
        )
        db_session.add_all([order1, order2, order3])
        db_session.commit()

        from_time = datetime(2025, 12, 31, 12, 0, 0)
        to_time = datetime(2025, 12, 31, 16, 0, 0)

        orders = await get_scheduled_orders(db_session, from_time, to_time)
        assert len(orders) == 1
        expected_time = datetime(2025, 12, 31, 14, 0, 0)
        assert orders[0].scheduled_fulfillment_time == expected_time

    @pytest.mark.asyncio
    async def test_process_due_delayed_orders_success(self, db_session):
        """Test processing orders that are due for fulfillment."""
        past_time = datetime(2020, 1, 1, 12, 0, 0)
        future_time = datetime(2025, 12, 31, 15, 0, 0)

        order1 = Order(staff_id=1, status=OrderStatus.SCHEDULED.value,
                       scheduled_fulfillment_time=past_time)
        order2 = Order(staff_id=2, status=OrderStatus.SCHEDULED.value,
                       scheduled_fulfillment_time=future_time)
        order3 = Order(staff_id=3, status=OrderStatus.DELAYED.value,
                       scheduled_fulfillment_time=past_time)
        db_session.add_all([order1, order2, order3])
        db_session.commit()

        result = await process_due_delayed_orders(db_session)

        assert "Processed 1 due orders" in result["message"]
        assert len(result["processed_orders"]) == 1
        expected_status = OrderStatus.AWAITING_FULFILLMENT.value
        assert result["processed_orders"][0].status == expected_status

        db_session.refresh(order1)
        db_session.refresh(order2)
        db_session.refresh(order3)
        assert order1.status == OrderStatus.AWAITING_FULFILLMENT.value
        assert order2.status == OrderStatus.SCHEDULED.value
        assert order3.status == OrderStatus.DELAYED.value

    @pytest.mark.asyncio
    async def test_process_due_delayed_orders_no_due_orders(self, db_session):
        """Test processing when no orders are due."""
        future_time = datetime(2025, 12, 31, 15, 0, 0)

        order = Order(staff_id=1, status=OrderStatus.SCHEDULED.value,
                      scheduled_fulfillment_time=future_time)
        db_session.add(order)
        db_session.commit()

        result = await process_due_delayed_orders(db_session)

        assert "Processed 0 due orders" in result["message"]
        assert len(result["processed_orders"]) == 0


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
        assert ("Only completed or cancelled orders can be archived"
                in exc_info.value.detail)

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


class TestOrderPriority:

    @pytest.mark.asyncio
    async def test_update_order_priority_success(self, db_session, sample_order):
        """Test successful order priority update."""
        priority_data = OrderPriorityUpdate(priority=OrderPriority.HIGH, reason="Rush order")
        result = await update_order_priority_service(sample_order.id, priority_data, db_session)
        
        assert result.message == "Order priority updated to high"
        assert result.order.priority == "high"
        assert result.previous_priority == "normal"
        
        db_session.refresh(sample_order)
        assert sample_order.priority == OrderPriority.HIGH.value
        assert sample_order.priority_updated_at is not None

    @pytest.mark.asyncio
    async def test_update_order_priority_order_not_found(self, db_session):
        """Test priority update with non-existent order ID."""
        priority_data = OrderPriorityUpdate(priority=OrderPriority.URGENT)
        with pytest.raises(HTTPException) as exc_info:
            await update_order_priority_service(999, priority_data, db_session)
        assert exc_info.value.status_code == 404
        assert "Order not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_orders_priority_sorting(self, db_session):
        """Test that orders are sorted by priority correctly."""
        from backend.modules.orders.models.order_models import Order
        
        order_low = Order(staff_id=1, status=OrderStatus.PENDING.value, priority=OrderPriority.LOW.value)
        order_normal = Order(staff_id=1, status=OrderStatus.PENDING.value, priority=OrderPriority.NORMAL.value)
        order_high = Order(staff_id=1, status=OrderStatus.PENDING.value, priority=OrderPriority.HIGH.value)
        order_urgent = Order(staff_id=1, status=OrderStatus.PENDING.value, priority=OrderPriority.URGENT.value)
        
        db_session.add_all([order_low, order_normal, order_high, order_urgent])
        db_session.commit()
        
        orders = await get_orders_service(db_session, limit=10)
        
        priorities = [order.priority for order in orders]
        
        urgent_index = next((i for i, p in enumerate(priorities) if p == OrderPriority.URGENT.value), None)
        high_index = next((i for i, p in enumerate(priorities) if p == OrderPriority.HIGH.value), None)
        normal_index = next((i for i, p in enumerate(priorities) if p == OrderPriority.NORMAL.value), None)
        low_index = next((i for i, p in enumerate(priorities) if p == OrderPriority.LOW.value), None)
        
        if urgent_index is not None and high_index is not None:
            assert urgent_index < high_index
        if high_index is not None and normal_index is not None:
            assert high_index < normal_index
        if normal_index is not None and low_index is not None:
            assert normal_index < low_index
