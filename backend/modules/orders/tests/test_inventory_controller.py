import pytest
from unittest.mock import AsyncMock, patch
from backend.modules.orders.controllers.inventory_controller import (
    get_inventory_by_id, check_low_stock, list_inventory, update_inventory
)
from backend.modules.orders.schemas.inventory_schemas import InventoryOut, InventoryUpdate
from datetime import datetime


class TestInventoryController:

    @pytest.mark.asyncio
    @patch('backend.modules.orders.controllers.'
           'inventory_controller.get_inventory_service')
    async def test_get_inventory_by_id_delegates_to_service(self, mock_service, db_session):
        mock_inventory = AsyncMock()
        mock_inventory.id = 1
        mock_service.return_value = mock_inventory

        result = await get_inventory_by_id(db_session, 1)

        mock_service.assert_called_once_with(db_session, 1)
        assert result.id == 1

    @pytest.mark.asyncio
    @patch('backend.modules.orders.controllers.'
           'inventory_controller.check_low_stock_service')
    async def test_check_low_stock_delegates_to_service(self, mock_service, db_session):
        mock_alerts = [{"item_name": "Test Item", "current_quantity": 5.0}]
        mock_service.return_value = mock_alerts

        result = await check_low_stock(db_session)

        mock_service.assert_called_once_with(db_session)
        assert result == mock_alerts

    @pytest.mark.asyncio
    @patch('backend.modules.orders.controllers.'
           'inventory_controller.list_inventory_service')
    async def test_list_inventory_delegates_to_service(self, mock_service, db_session):
        mock_inventories = [AsyncMock(), AsyncMock()]
        mock_inventories[0].id = 1
        mock_inventories[0].item_name = "Item 1"
        mock_inventories[0].quantity = 10.0
        mock_inventories[0].unit = "kg"
        mock_inventories[0].threshold = 5.0
        mock_inventories[0].vendor_id = None
        mock_inventories[0].created_at = datetime.utcnow()
        mock_inventories[0].updated_at = datetime.utcnow()
        mock_inventories[0].deleted_at = None

        mock_inventories[1].id = 2
        mock_inventories[1].item_name = "Item 2"
        mock_inventories[1].quantity = 20.0
        mock_inventories[1].unit = "pieces"
        mock_inventories[1].threshold = 10.0
        mock_inventories[1].vendor_id = None
        mock_inventories[1].created_at = datetime.utcnow()
        mock_inventories[1].updated_at = datetime.utcnow()
        mock_inventories[1].deleted_at = None

        mock_service.return_value = mock_inventories

        result = await list_inventory(db_session, limit=10, offset=0)

        mock_service.assert_called_once_with(db_session, 10, 0)
        assert len(result) == 2
        assert all(isinstance(item, InventoryOut) for item in result)

    @pytest.mark.asyncio
    @patch('backend.modules.orders.controllers.'
           'inventory_controller.update_inventory_service')
    async def test_update_inventory_delegates_to_service(self, mock_service, db_session):
        mock_service.return_value = {"message": "success", "data": {"id": 1}}
        inventory_data = InventoryUpdate(quantity=15.0)

        result = await update_inventory(1, inventory_data, db_session)

        mock_service.assert_called_once_with(1, inventory_data, db_session)
        assert result["message"] == "success"
