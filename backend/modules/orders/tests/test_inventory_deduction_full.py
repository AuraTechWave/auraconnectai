# backend/modules/orders/tests/test_inventory_deduction_full.py

"""
Comprehensive tests for inventory deduction scenarios.
"""

import pytest
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from fastapi import status

from modules.orders.enums.order_enums import OrderStatus
from core.inventory_models import Inventory


class TestInventoryDeductionAPI:
    """Test inventory deduction API endpoints"""

    @pytest.fixture
    def headers(self, auth_token):
        """Auth headers for requests"""
        return {"Authorization": f"Bearer {auth_token}"}

    @pytest.fixture
    def setup_test_data(self, client: TestClient, headers: dict, db_session: Session):
        """Setup test data for inventory deduction tests"""
        # Create inventory items
        inventory_data = [
            {"item_name": "Flour", "quantity": 100, "unit": "kg", "threshold": 20},
            {"item_name": "Cheese", "quantity": 50, "unit": "kg", "threshold": 10},
            {"item_name": "Tomato Sauce", "quantity": 30, "unit": "L", "threshold": 5},
        ]

        inventory_ids = []
        for item in inventory_data:
            response = client.post("/api/v1/inventory", json=item, headers=headers)
            assert response.status_code == status.HTTP_201_CREATED
            inventory_ids.append(response.json()["id"])

        # Create menu item
        menu_item_data = {
            "name": "Margherita Pizza",
            "category_id": 1,
            "price": 12.50,
            "is_available": True,
        }
        response = client.post(
            "/api/v1/menu/items", json=menu_item_data, headers=headers
        )
        assert response.status_code == status.HTTP_201_CREATED
        menu_item_id = response.json()["id"]

        # Create recipe
        recipe_data = {
            "name": "Margherita Pizza Recipe",
            "menu_item_id": menu_item_id,
            "yield_amount": 1,
            "yield_unit": "pizza",
            "ingredients": [
                {"inventory_id": inventory_ids[0], "quantity": 0.3, "unit": "kg"},
                {"inventory_id": inventory_ids[1], "quantity": 0.2, "unit": "kg"},
                {"inventory_id": inventory_ids[2], "quantity": 0.1, "unit": "L"},
            ],
        }
        response = client.post(
            "/api/v1/menu/recipes", json=recipe_data, headers=headers
        )
        assert response.status_code == status.HTTP_201_CREATED

        # Create order
        order_data = {
            "customer_id": 1,
            "items": [{"menu_item_id": menu_item_id, "quantity": 2, "price": 12.50}],
            "total_amount": 25.00,
        }
        response = client.post("/api/v1/orders", json=order_data, headers=headers)
        assert response.status_code == status.HTTP_201_CREATED
        order_id = response.json()["id"]

        return {
            "order_id": order_id,
            "menu_item_id": menu_item_id,
            "inventory_ids": inventory_ids,
        }

    def test_complete_order_with_inventory_deduction(
        self, client: TestClient, headers: dict, setup_test_data: dict
    ):
        """Test completing order with automatic inventory deduction"""
        order_id = setup_test_data["order_id"]

        # Check inventory before
        response = client.get(
            f"/api/v1/inventory/{setup_test_data['inventory_ids'][0]}", headers=headers
        )
        flour_before = response.json()["quantity"]

        # Complete order with inventory deduction
        response = client.post(
            f"/api/v1/orders/{order_id}/complete-with-inventory", headers=headers
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()

        # Verify response
        assert result["success"] is True
        assert result["status"] == "completed"
        assert result["inventory_deducted"] is True
        assert result["inventory_result"]["success"] is True
        assert len(result["inventory_result"]["deducted_items"]) == 3

        # Check inventory after
        response = client.get(
            f"/api/v1/inventory/{setup_test_data['inventory_ids'][0]}", headers=headers
        )
        flour_after = response.json()["quantity"]

        # 2 pizzas * 0.3 kg = 0.6 kg deducted
        assert flour_after == flour_before - 0.6

    def test_cancel_order_with_inventory_reversal(
        self, client: TestClient, headers: dict, setup_test_data: dict
    ):
        """Test cancelling completed order reverses inventory"""
        order_id = setup_test_data["order_id"]

        # First complete the order
        response = client.post(
            f"/api/v1/orders/{order_id}/complete-with-inventory", headers=headers
        )
        assert response.status_code == status.HTTP_200_OK

        # Get inventory after completion
        response = client.get(
            f"/api/v1/inventory/{setup_test_data['inventory_ids'][0]}", headers=headers
        )
        flour_after_completion = response.json()["quantity"]

        # Cancel order with inventory reversal
        cancel_data = {"reason": "Customer cancelled", "reverse_inventory": True}
        response = client.post(
            f"/api/v1/orders/{order_id}/cancel-with-inventory",
            json=cancel_data,
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()

        assert result["success"] is True
        assert result["status"] == "cancelled"
        assert result["inventory_reversed"] is True

        # Check inventory after reversal
        response = client.get(
            f"/api/v1/inventory/{setup_test_data['inventory_ids'][0]}", headers=headers
        )
        flour_after_reversal = response.json()["quantity"]

        # Should be restored
        assert flour_after_reversal > flour_after_completion

    def test_check_inventory_availability(
        self, client: TestClient, headers: dict, setup_test_data: dict
    ):
        """Test checking inventory availability before completion"""
        order_id = setup_test_data["order_id"]

        response = client.get(
            f"/api/v1/orders/{order_id}/inventory-availability", headers=headers
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()

        assert result["can_fulfill"] is True
        assert len(result["impact_preview"]) == 3

        # Check flour impact
        flour_impact = next(
            item for item in result["impact_preview"] if item["item_name"] == "Flour"
        )

        assert flour_impact["required_quantity"] == 0.6
        assert flour_impact["sufficient_stock"] is True

    def test_partial_fulfillment(
        self, client: TestClient, headers: dict, setup_test_data: dict
    ):
        """Test partial order fulfillment"""
        order_id = setup_test_data["order_id"]
        menu_item_id = setup_test_data["menu_item_id"]

        # Fulfill only 1 pizza out of 2
        partial_data = {
            "fulfilled_items": [{"menu_item_id": menu_item_id, "fulfilled_quantity": 1}]
        }

        response = client.post(
            f"/api/v1/orders/{order_id}/partial-fulfillment",
            json=partial_data,
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()

        assert result["success"] is True
        assert len(result["fulfilled_items"]) == 1
        assert result["inventory_result"]["success"] is True

    def test_insufficient_inventory_prevents_completion(
        self,
        client: TestClient,
        headers: dict,
        setup_test_data: dict,
        db_session: Session,
    ):
        """Test order completion fails with insufficient inventory"""
        order_id = setup_test_data["order_id"]

        # Reduce flour quantity to insufficient level
        flour = db_session.query(Inventory).filter_by(item_name="Flour").first()
        flour.quantity = 0.5  # Need 0.6 for 2 pizzas
        db_session.commit()

        # Try to complete order
        response = client.post(
            f"/api/v1/orders/{order_id}/complete-with-inventory", headers=headers
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = response.json()
        assert "Insufficient inventory" in error["detail"]["message"]

    def test_skip_inventory_option(
        self, client: TestClient, headers: dict, setup_test_data: dict
    ):
        """Test completing order with skip inventory option"""
        order_id = setup_test_data["order_id"]

        # Complete with skip_inventory
        request_data = {"skip_inventory": True}
        response = client.post(
            f"/api/v1/orders/{order_id}/complete-with-inventory",
            json=request_data,
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()

        assert result["success"] is True
        assert result["inventory_deducted"] is False
        assert result["inventory_result"] is None

    def test_manual_reversal_admin_only(
        self,
        client: TestClient,
        headers: dict,
        setup_test_data: dict,
        auth_token_manager: str,
    ):
        """Test manual reversal endpoint requires admin access"""
        order_id = setup_test_data["order_id"]

        # First complete the order
        response = client.post(
            f"/api/v1/orders/{order_id}/complete-with-inventory", headers=headers
        )
        assert response.status_code == status.HTTP_200_OK

        # Try to reverse with manager token (non-admin)
        manager_token = auth_token_manager
        manager_headers = {"Authorization": f"Bearer {manager_token}"}

        # Attempt reversal without force (should work for manager)
        response = client.post(
            f"/api/v1/orders/{order_id}/reverse-deduction?reason=Test%20reversal",
            headers=manager_headers,
        )
        assert response.status_code == status.HTTP_200_OK

        # Create new order to test force reversal
        order_data = {
            "customer_id": 1,
            "items": [
                {
                    "menu_item_id": setup_test_data["menu_item_id"],
                    "quantity": 1,
                    "price": 12.50,
                }
            ],
            "total_amount": 12.50,
        }
        response = client.post("/api/v1/orders", json=order_data, headers=headers)
        assert response.status_code == status.HTTP_201_CREATED
        new_order_id = response.json()["id"]

        # Complete the new order
        response = client.post(
            f"/api/v1/orders/{new_order_id}/complete-with-inventory", headers=headers
        )
        assert response.status_code == status.HTTP_200_OK

        # Try force reversal with manager token (should fail)
        response = client.post(
            f"/api/v1/orders/{new_order_id}/reverse-deduction?reason=Force%20test&force=true",
            headers=manager_headers,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # Try force reversal with admin token (should succeed)
        response = client.post(
            f"/api/v1/orders/{new_order_id}/reverse-deduction?reason=Force%20test&force=true",
            headers=headers,  # Admin headers
        )
        assert response.status_code == status.HTTP_200_OK
        result = response.json()

        assert result["success"] is True
        assert len(result["reversed_items"]) > 0

    def test_manual_reversal_behavior(
        self,
        client: TestClient,
        headers: dict,
        setup_test_data: dict,
        db_session: Session,
    ):
        """Test manual reversal endpoint behavior and inventory restoration"""
        order_id = setup_test_data["order_id"]

        # Complete the order first
        response = client.post(
            f"/api/v1/orders/{order_id}/complete-with-inventory", headers=headers
        )
        assert response.status_code == status.HTTP_200_OK

        # Get inventory levels after completion
        response = client.get(
            f"/api/v1/inventory/{setup_test_data['inventory_ids'][0]}", headers=headers
        )
        flour_after_completion = response.json()["quantity"]

        # Manually reverse the deduction
        response = client.post(
            f"/api/v1/orders/{order_id}/reverse-deduction?reason=Manual%20reversal%20test",
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()

        # Verify reversal response
        assert result["success"] is True
        assert len(result["reversed_items"]) == 3  # 3 ingredients
        assert result["total_items_reversed"] == 3

        # Verify flour was reversed
        flour_reversal = next(
            item for item in result["reversed_items"] if item["item_name"] == "Flour"
        )
        assert flour_reversal["quantity_restored"] == 0.6  # 2 pizzas * 0.3 kg

        # Check inventory after reversal
        response = client.get(
            f"/api/v1/inventory/{setup_test_data['inventory_ids'][0]}", headers=headers
        )
        flour_after_reversal = response.json()["quantity"]

        # Should be restored
        assert flour_after_reversal == flour_after_completion + 0.6

        # Try to reverse again (should fail - already reversed)
        response = client.post(
            f"/api/v1/orders/{order_id}/reverse-deduction?reason=Duplicate%20reversal",
            headers=headers,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already been reversed" in response.json()["detail"]
