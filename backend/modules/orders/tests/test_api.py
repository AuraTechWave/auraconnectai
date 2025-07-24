from fastapi import status
from backend.modules.orders.enums.order_enums import OrderStatus, DelayReason
from datetime import datetime


class TestOrderAPI:

    def test_get_orders_empty_list(self, client):
        """Test GET /orders returns empty list when no orders exist."""
        response = client.get("/orders/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_get_orders_with_data(self, client, sample_order):
        """Test GET /orders returns orders when they exist."""
        response = client.get("/orders/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == sample_order.id
        assert data[0]["staff_id"] == sample_order.staff_id
        assert data[0]["status"] == sample_order.status

    def test_get_orders_with_status_filter(self, client, db_session):
        """Test GET /orders with status filter."""
        from backend.modules.orders.models.order_models import Order
        order1 = Order(staff_id=1, status=OrderStatus.PENDING.value)
        order2 = Order(staff_id=2, status=OrderStatus.IN_PROGRESS.value)
        db_session.add_all([order1, order2])
        db_session.commit()

        response = client.get("/orders/?status=pending")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "pending"

    def test_get_orders_with_staff_id_filter(self, client, db_session):
        """Test GET /orders with staff_id filter."""
        from backend.modules.orders.models.order_models import Order
        order1 = Order(staff_id=1, status=OrderStatus.PENDING.value)
        order2 = Order(staff_id=2, status=OrderStatus.PENDING.value)
        db_session.add_all([order1, order2])
        db_session.commit()

        response = client.get("/orders/?staff_id=1")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["staff_id"] == 1

    def test_get_orders_with_table_no_filter(self, client, db_session):
        """Test GET /orders with table_no filter."""
        from backend.modules.orders.models.order_models import Order
        order1 = Order(staff_id=1, table_no=5,
                       status=OrderStatus.PENDING.value)
        order2 = Order(staff_id=2, table_no=3,
                       status=OrderStatus.PENDING.value)
        db_session.add_all([order1, order2])
        db_session.commit()

        response = client.get("/orders/?table_no=5")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["table_no"] == 5

    def test_get_orders_pagination(self, client, db_session):
        """Test GET /orders pagination parameters."""
        from backend.modules.orders.models.order_models import Order
        orders = [Order(staff_id=i, status=OrderStatus.PENDING.value)
                  for i in range(5)]
        db_session.add_all(orders)
        db_session.commit()

        response = client.get("/orders/?limit=2")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 2

        response = client.get("/orders/?limit=2&offset=2")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 2

    def test_get_orders_include_items(self, client, sample_order_with_items):
        """Test GET /orders with include_items parameter."""
        response = client.get("/orders/?include_items=true")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert "order_items" in data[0]
        assert len(data[0]["order_items"]) == 2

    def test_get_order_by_id_success(self, client, sample_order):
        """Test GET /orders/{id} with valid ID."""
        response = client.get(f"/orders/{sample_order.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == sample_order.id
        assert data["staff_id"] == sample_order.staff_id
        assert data["status"] == sample_order.status

    def test_get_order_by_id_not_found(self, client):
        """Test GET /orders/{id} with non-existent ID."""
        response = client.get("/orders/999")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"]

    def test_get_order_by_id_soft_deleted(self, client, sample_order,
                                          db_session):
        """Test GET /orders/{id} with soft-deleted order."""
        from datetime import datetime
        sample_order.deleted_at = datetime.utcnow()
        db_session.commit()

        response = client.get(f"/orders/{sample_order.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_order_status_success(self, client, sample_order):
        """Test PUT /orders/{order_id} with valid status update."""
        update_data = {"status": "in_progress"}
        response = client.put(f"/orders/{sample_order.id}",
                              json=update_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Order updated successfully"
        assert data["data"]["status"] == "in_progress"

    def test_update_order_status_invalid_transition(self, client,
                                                    sample_order):
        """Test PUT /orders/{order_id} with invalid transition."""
        update_data = {"status": "completed"}
        response = client.put(f"/orders/{sample_order.id}",
                              json=update_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid status transition" in response.json()["detail"]

    def test_update_order_items(self, client, sample_order):
        """Test PUT /orders/{order_id} with order items update."""
        update_data = {
            "order_items": [
                {
                    "menu_item_id": 301,
                    "quantity": 2,
                    "price": 18.99,
                    "notes": "Extra cheese"
                },
                {
                    "menu_item_id": 302,
                    "quantity": 1,
                    "price": 7.50
                }
            ]
        }
        response = client.put(f"/orders/{sample_order.id}", json=update_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Order updated successfully"

    def test_update_order_not_found(self, client):
        """Test PUT /orders/{order_id} with non-existent order."""
        update_data = {"status": "in_progress"}
        response = client.put("/orders/999", json=update_data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Order not found" in response.json()["detail"]

    def test_update_order_combined_status_and_items(self, client,
                                                    sample_order):
        """Test PUT /orders/{order_id} updating status and items."""
        update_data = {
            "status": "in_progress",
            "order_items": [
                {
                    "menu_item_id": 401,
                    "quantity": 3,
                    "price": 25.00,
                    "notes": "Well done"
                }
            ]
        }
        response = client.put(f"/orders/{sample_order.id}", json=update_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Order updated successfully"
        assert data["data"]["status"] == "in_progress"

    def test_api_validation_errors(self, client, sample_order):
        """Test API validation with invalid data."""
        update_data = {"status": "invalid_status"}
        response = client.put(f"/orders/{sample_order.id}", json=update_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        update_data = {
            "order_items": [
                {
                    "menu_item_id": "not_an_integer",
                    "quantity": -1,
                    "price": "not_a_number"
                }
            ]
        }
        response = client.put(f"/orders/{sample_order.id}", json=update_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_validate_rules_success(self, client):
        """Test POST /orders/validate-rules with valid data."""
        request_data = {
            "order_items": [
                {"menu_item_id": 104, "quantity": 2, "price": 10.99},
                {"menu_item_id": 105, "quantity": 1, "price": 7.99}
            ],
            "rule_types": ["combo", "bulk_discount"]
        }
        response = client.post("/orders/validate-rules", json=request_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_valid"] is True

    def test_validate_rules_compatibility_failure(self, client):
        """Test POST /orders/validate-rules with incompatible items."""
        request_data = {
            "order_items": [
                {"menu_item_id": 101, "quantity": 1, "price": 12.99},
                {"menu_item_id": 301, "quantity": 1, "price": 15.99}
            ],
            "rule_types": ["compatibility"]
        }
        response = client.post("/orders/validate-rules", json=request_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_valid"] is False
        assert "not compatible" in data["message"]

    def test_validate_rules_validation_error(self, client):
        """Test POST /orders/validate-rules with invalid data."""
        request_data = {
            "order_items": [
                {"menu_item_id": "invalid", "quantity": -1,
                 "price": "not_a_number"}
            ]
        }
        response = client.post("/orders/validate-rules", json=request_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestDelayedFulfillmentAPI:

    def test_delay_order_success(self, client, sample_order):
        """Test POST /orders/{order_id}/delay with valid data."""
        delay_data = {
            "scheduled_fulfillment_time": "2025-12-31T15:30:00",
            "delay_reason": DelayReason.CUSTOMER_REQUEST.value,
            "additional_notes": "Customer requested later delivery"
        }
        
        response = client.post(f"/orders/{sample_order.id}/delay", json=delay_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Order scheduled for delayed fulfillment"
        assert data["data"]["status"] == OrderStatus.DELAYED.value
        assert data["data"]["delay_reason"] == DelayReason.CUSTOMER_REQUEST.value

    def test_delay_order_invalid_status(self, client, sample_order, db_session):
        """Test delaying order with invalid status."""
        sample_order.status = OrderStatus.COMPLETED.value
        db_session.commit()
        
        delay_data = {
            "scheduled_fulfillment_time": "2025-12-31T15:30:00",
            "delay_reason": DelayReason.CUSTOMER_REQUEST.value
        }
        
        response = client.post(f"/orders/{sample_order.id}/delay", json=delay_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cannot delay order" in response.json()["detail"]

    def test_delay_order_past_time(self, client, sample_order):
        """Test delaying order with past time."""
        delay_data = {
            "scheduled_fulfillment_time": "2020-01-01T12:00:00",
            "delay_reason": DelayReason.CUSTOMER_REQUEST.value
        }
        
        response = client.post(f"/orders/{sample_order.id}/delay", json=delay_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "must be in the future" in response.json()["detail"]

    def test_delay_order_not_found(self, client):
        """Test delaying non-existent order."""
        delay_data = {
            "scheduled_fulfillment_time": "2025-12-31T15:30:00",
            "delay_reason": DelayReason.CUSTOMER_REQUEST.value
        }
        
        response = client.post("/orders/999/delay", json=delay_data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Order not found" in response.json()["detail"]

    def test_delay_order_validation_error(self, client, sample_order):
        """Test delay order with invalid data."""
        delay_data = {
            "scheduled_fulfillment_time": "invalid-date",
            "delay_reason": "invalid_reason"
        }
        
        response = client.post(f"/orders/{sample_order.id}/delay", json=delay_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_delayed_orders_empty(self, client):
        """Test GET /orders/delayed returns empty list when no delayed orders exist."""
        response = client.get("/orders/delayed")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_get_delayed_orders_with_data(self, client, db_session):
        """Test GET /orders/delayed returns delayed orders."""
        from backend.modules.orders.models.order_models import Order
        
        order1 = Order(staff_id=1, status=OrderStatus.DELAYED.value,
                      scheduled_fulfillment_time=datetime(2025, 12, 31, 10, 0, 0))
        order2 = Order(staff_id=2, status=OrderStatus.SCHEDULED.value,
                      scheduled_fulfillment_time=datetime(2025, 12, 31, 14, 0, 0))
        order3 = Order(staff_id=3, status=OrderStatus.PENDING.value)
        db_session.add_all([order1, order2, order3])
        db_session.commit()
        
        response = client.get("/orders/delayed")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        assert data[0]["status"] in [OrderStatus.DELAYED.value, OrderStatus.SCHEDULED.value]
        assert data[1]["status"] in [OrderStatus.DELAYED.value, OrderStatus.SCHEDULED.value]

    def test_get_delayed_orders_with_time_filters(self, client, db_session):
        """Test GET /orders/delayed with time range filters."""
        from backend.modules.orders.models.order_models import Order
        
        order1 = Order(staff_id=1, status=OrderStatus.DELAYED.value,
                      scheduled_fulfillment_time=datetime(2025, 12, 31, 10, 0, 0))
        order2 = Order(staff_id=2, status=OrderStatus.SCHEDULED.value,
                      scheduled_fulfillment_time=datetime(2025, 12, 31, 14, 0, 0))
        order3 = Order(staff_id=3, status=OrderStatus.AWAITING_FULFILLMENT.value,
                      scheduled_fulfillment_time=datetime(2025, 12, 31, 18, 0, 0))
        db_session.add_all([order1, order2, order3])
        db_session.commit()
        
        response = client.get("/orders/delayed?from_time=2025-12-31T12:00:00&to_time=2025-12-31T16:00:00")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["scheduled_fulfillment_time"] == "2025-12-31T14:00:00"
