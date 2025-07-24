import pytest
from fastapi import HTTPException
from backend.modules.orders.services.inventory_service import (
    get_inventory_by_id, deduct_inventory, check_low_stock,
    get_inventory_service
)
from backend.modules.orders.models.inventory_models import Inventory
from backend.modules.orders.models.order_models import OrderItem
from datetime import datetime


class TestInventoryService:

    @pytest.mark.asyncio
    async def test_get_inventory_by_id_success(self, db_session,
                                               sample_inventory):
        result = await get_inventory_by_id(db_session, sample_inventory.id)
        assert result.id == sample_inventory.id
        assert result.item_name == sample_inventory.item_name
        assert result.quantity == sample_inventory.quantity

    @pytest.mark.asyncio
    async def test_get_inventory_by_id_not_found(self, db_session):
        with pytest.raises(HTTPException) as exc_info:
            await get_inventory_by_id(db_session, 999)
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_inventory_by_id_soft_deleted(self, db_session,
                                                    sample_inventory):
        sample_inventory.deleted_at = datetime.utcnow()
        db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            await get_inventory_by_id(db_session, sample_inventory.id)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_deduct_inventory_success(self, db_session,
                                            sample_inventory_with_mapping):
        inventory, mapping = sample_inventory_with_mapping
        initial_quantity = inventory.quantity

        order_item = OrderItem(
            order_id=1,
            menu_item_id=mapping.menu_item_id,
            quantity=2,
            price=10.0
        )

        result = await deduct_inventory(db_session, [order_item])

        assert result["success"] is True
        db_session.refresh(inventory)
        expected_quantity = (initial_quantity -
                             (mapping.quantity_needed * order_item.quantity))
        assert inventory.quantity == expected_quantity

    @pytest.mark.asyncio
    async def test_deduct_inventory_insufficient_stock(
            self, db_session, sample_inventory_with_mapping):
        inventory, mapping = sample_inventory_with_mapping
        inventory.quantity = 1.0
        db_session.commit()

        order_item = OrderItem(
            order_id=1,
            menu_item_id=mapping.menu_item_id,
            quantity=10,
            price=10.0
        )

        with pytest.raises(HTTPException) as exc_info:
            await deduct_inventory(db_session, [order_item])
        assert exc_info.value.status_code == 400
        assert "Insufficient inventory" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_deduct_inventory_low_stock_alert(
            self, db_session, sample_inventory_with_mapping):
        inventory, mapping = sample_inventory_with_mapping
        inventory.quantity = 10.0
        inventory.threshold = 8.0
        db_session.commit()

        order_item = OrderItem(
            order_id=1,
            menu_item_id=mapping.menu_item_id,
            quantity=1,
            price=10.0
        )

        result = await deduct_inventory(db_session, [order_item])

        assert result["success"] is True
        assert len(result["low_stock_alerts"]) == 1
        assert (result["low_stock_alerts"][0]["item_name"] ==
                inventory.item_name)

    @pytest.mark.asyncio
    async def test_check_low_stock(self, db_session):
        inventory1 = Inventory(
            item_name="Low Stock Item",
            quantity=5.0,
            unit="kg",
            threshold=10.0
        )
        inventory2 = Inventory(
            item_name="Normal Stock Item",
            quantity=20.0,
            unit="kg",
            threshold=10.0
        )
        db_session.add_all([inventory1, inventory2])
        db_session.commit()

        low_stock_items = await check_low_stock(db_session)

        assert len(low_stock_items) == 1
        assert low_stock_items[0]["item_name"] == "Low Stock Item"

    @pytest.mark.asyncio
    async def test_get_inventory_service_pagination(self,
                                                    db_session):
        inventories = [
            Inventory(item_name=f"Item {i}", quantity=10.0, unit="kg", threshold=5.0)
            for i in range(5)
        ]
        db_session.add_all(inventories)
        db_session.commit()

        page1 = await get_inventory_service(db_session, limit=2, offset=0)
        page2 = await get_inventory_service(db_session, limit=2, offset=2)

        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0].id != page2[0].id
