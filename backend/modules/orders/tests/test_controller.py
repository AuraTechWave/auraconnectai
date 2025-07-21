import pytest
from unittest.mock import AsyncMock, patch
from backend.modules.orders.controllers.order_controller import (
    update_order, get_order_by_id, list_orders
)
from backend.modules.orders.schemas.order_schemas import OrderUpdate, OrderOut
from backend.modules.orders.enums.order_enums import OrderStatus
from datetime import datetime


class TestOrderController:

    @pytest.mark.asyncio
    @patch('backend.modules.orders.controllers.'
           'order_controller.update_order_service')
    async def test_update_order_delegates_to_service(self, mock_service,
                                                     db_session):
        """Test that update_order properly delegates to service layer."""
        mock_service.return_value = {"message": "success", "data": {"id": 1}}
        order_data = OrderUpdate(status=OrderStatus.IN_PROGRESS)

        result = await update_order(1, order_data, db_session)

        mock_service.assert_called_once_with(1, order_data, db_session)
        assert result["message"] == "success"

    @pytest.mark.asyncio
    @patch('backend.modules.orders.controllers.'
           'order_controller.get_order_service')
    async def test_get_order_by_id_delegates_to_service(self, mock_service,
                                                        db_session):
        """Test that get_order_by_id properly delegates to service."""
        mock_order = AsyncMock()
        mock_order.id = 1
        mock_service.return_value = mock_order

        result = await get_order_by_id(db_session, 1)

        mock_service.assert_called_once_with(db_session, 1)
        assert result.id == 1

    @pytest.mark.asyncio
    @patch('backend.modules.orders.controllers.'
           'order_controller.get_orders_service')
    async def test_list_orders_delegates_to_service(self, mock_service,
                                                    db_session):
        """Test that list_orders properly delegates to service layer."""
        mock_orders = [AsyncMock(), AsyncMock()]
        mock_orders[0].id = 1
        mock_orders[0].staff_id = 1
        mock_orders[0].status = OrderStatus.PENDING.value
        mock_orders[0].table_no = 5
        mock_orders[0].created_at = datetime.utcnow()
        mock_orders[0].updated_at = datetime.utcnow()
        mock_orders[0].deleted_at = None
        mock_orders[0].order_items = []

        mock_orders[1].id = 2
        mock_orders[1].staff_id = 2
        mock_orders[1].status = OrderStatus.IN_PROGRESS.value
        mock_orders[1].table_no = 3
        mock_orders[1].created_at = datetime.utcnow()
        mock_orders[1].updated_at = datetime.utcnow()
        mock_orders[1].deleted_at = None
        mock_orders[1].order_items = []

        mock_service.return_value = mock_orders

        result = await list_orders(db_session, status="pending",
                                   staff_id=1, limit=10)

        mock_service.assert_called_once_with(
            db_session, "pending", 1, None, 10, 0, False
        )
        assert len(result) == 2
        assert all(isinstance(order, OrderOut) for order in result)

    @pytest.mark.asyncio
    @patch('backend.modules.orders.controllers.'
           'order_controller.get_orders_service')
    async def test_list_orders_with_all_parameters(self, mock_service,
                                                   db_session):
        """Test list_orders with all optional parameters."""
        mock_service.return_value = []

        await list_orders(
            db_session,
            status="in_progress",
            staff_id=2,
            table_no=5,
            limit=50,
            offset=10,
            include_items=True
        )

        mock_service.assert_called_once_with(
            db_session, "in_progress", 2, 5, 50, 10, True
        )
