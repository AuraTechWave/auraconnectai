from fastapi import status
from backend.modules.orders.models.inventory_models import Inventory


class TestInventoryAPI:

    def test_get_inventory_empty_list(self, client):
        response = client.get("/inventory/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_get_inventory_with_items(self, client, db_session):
        inventory1 = Inventory(item_name="Item 1", quantity=10.0,
                               unit="kg", threshold=5.0)
        inventory2 = Inventory(item_name="Item 2", quantity=20.0,
                               unit="pieces", threshold=10.0)
        db_session.add_all([inventory1, inventory2])
        db_session.commit()

        response = client.get("/inventory/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

    def test_get_inventory_pagination(self, client, db_session):
        inventories = [
            Inventory(item_name=f"Item {i}", quantity=10.0,
                      unit="kg", threshold=5.0)
            for i in range(5)
        ]
        db_session.add_all(inventories)
        db_session.commit()

        response = client.get("/inventory/?limit=2")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

    def test_get_inventory_by_id_success(self, client, sample_inventory):
        response = client.get(
            f"/inventory/{sample_inventory.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == sample_inventory.id
        assert data["item_name"] == sample_inventory.item_name

    def test_get_inventory_by_id_not_found(self, client):
        response = client.get("/inventory/999")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_inventory_by_id_soft_deleted(self, client,
                                              db_session,
                                              sample_inventory):
        from datetime import datetime
        sample_inventory.deleted_at = datetime.utcnow()
        db_session.commit()

        response = client.get(
            f"/inventory/{sample_inventory.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_inventory_success(self, client, sample_inventory):
        update_data = {
            "quantity": 25.0,
            "threshold": 8.0
        }

        response = client.put(
            f"/inventory/{sample_inventory.id}", json=update_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Inventory updated successfully"

    def test_update_inventory_not_found(self, client):
        update_data = {
            "quantity": 25.0
        }

        response = client.put("/inventory/999", json=update_data)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_low_stock_alerts(self, client, db_session):
        inventory1 = Inventory(
            item_name="Low Stock Item",
            quantity=3.0,
            unit="kg",
            threshold=5.0
        )
        inventory2 = Inventory(
            item_name="Normal Stock Item",
            quantity=15.0,
            unit="kg",
            threshold=5.0
        )
        db_session.add_all([inventory1, inventory2])
        db_session.commit()

        response = client.get("/inventory/alerts/low-stock")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["item_name"] == "Low Stock Item"

    def test_get_low_stock_alerts_empty(self, client, db_session):
        inventory = Inventory(
            item_name="Normal Stock Item",
            quantity=15.0,
            unit="kg",
            threshold=5.0
        )
        db_session.add(inventory)
        db_session.commit()

        response = client.get("/inventory/alerts/low-stock")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 0
