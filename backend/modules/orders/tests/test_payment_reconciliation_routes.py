from fastapi.testclient import TestClient
from modules.orders.enums.payment_enums import (
    ReconciliationStatus,
    DiscrepancyType,
    ReconciliationAction,
)


class TestPaymentReconciliationRoutes:

    def test_create_payment_reconciliation(self, client: TestClient, sample_order):
        reconciliation_data = {
            "order_id": sample_order.id,
            "external_payment_reference": "PAY_ROUTE_123",
            "amount_expected": "35.50",
            "amount_received": "35.50",
            "reconciliation_status": ReconciliationStatus.MATCHED.value,
        }

        response = client.post("/payment-reconciliation/", json=reconciliation_data)

        assert response.status_code == 200
        data = response.json()
        assert data["order_id"] == sample_order.id
        assert data["external_payment_reference"] == "PAY_ROUTE_123"
        status = ReconciliationStatus.MATCHED.value
        assert data["reconciliation_status"] == status

    def test_get_payment_reconciliation(self, client: TestClient, sample_order):
        reconciliation_data = {
            "order_id": sample_order.id,
            "external_payment_reference": "PAY_ROUTE_456",
            "amount_expected": "25.00",
            "amount_received": "25.00",
            "reconciliation_status": ReconciliationStatus.MATCHED.value,
        }

        create_response = client.post(
            "/payment-reconciliation/", json=reconciliation_data
        )
        reconciliation_id = create_response.json()["id"]

        response = client.get(f"/payment-reconciliation/{reconciliation_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == reconciliation_id
        assert data["external_payment_reference"] == "PAY_ROUTE_456"

    def test_update_payment_reconciliation(self, client: TestClient, sample_order):
        reconciliation_data = {
            "order_id": sample_order.id,
            "external_payment_reference": "PAY_ROUTE_789",
            "amount_expected": "40.00",
            "amount_received": "35.00",
            "reconciliation_status": ReconciliationStatus.DISCREPANCY.value,
            "discrepancy_type": DiscrepancyType.AMOUNT_MISMATCH.value,
        }

        create_response = client.post(
            "/payment-reconciliation/", json=reconciliation_data
        )
        reconciliation_id = create_response.json()["id"]

        update_data = {
            "reconciliation_status": ReconciliationStatus.RESOLVED.value,
            "reconciliation_action": ReconciliationAction.MANUAL_REVIEW.value,
            "resolution_notes": "Resolved by admin",
        }

        url = f"/payment-reconciliation/{reconciliation_id}"
        response = client.put(url, json=update_data)

        assert response.status_code == 200
        data = response.json()
        status = ReconciliationStatus.RESOLVED.value
        assert data["reconciliation_status"] == status
        action = ReconciliationAction.MANUAL_REVIEW.value
        assert data["reconciliation_action"] == action

    def test_get_payment_reconciliations_with_filters(
        self, client: TestClient, sample_order
    ):
        reconciliation_data = {
            "order_id": sample_order.id,
            "external_payment_reference": "PAY_ROUTE_FILTER",
            "amount_expected": "30.00",
            "amount_received": "25.00",
            "reconciliation_status": ReconciliationStatus.DISCREPANCY.value,
            "discrepancy_type": DiscrepancyType.AMOUNT_MISMATCH.value,
        }

        client.post("/payment-reconciliation/", json=reconciliation_data)

        status = ReconciliationStatus.DISCREPANCY.value
        response = client.get(
            "/payment-reconciliation/", params={"reconciliation_status": status}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        expected_status = ReconciliationStatus.DISCREPANCY.value
        assert all(item["reconciliation_status"] == expected_status for item in data)

    def test_perform_payment_reconciliation(self, client: TestClient, sample_order):
        request_data = {"order_ids": [sample_order.id], "amount_threshold": "0.01"}

        response = client.post("/payment-reconciliation/reconcile", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert "total_processed" in data
        assert "matched_count" in data
        assert "discrepancy_count" in data
        assert "reconciliations" in data
        assert data["total_processed"] == 1

    def test_resolve_payment_discrepancy(self, client: TestClient, sample_order):
        reconciliation_data = {
            "order_id": sample_order.id,
            "external_payment_reference": "PAY_ROUTE_RESOLVE",
            "amount_expected": "50.00",
            "amount_received": "45.00",
            "reconciliation_status": ReconciliationStatus.DISCREPANCY.value,
            "discrepancy_type": DiscrepancyType.AMOUNT_MISMATCH.value,
        }

        create_response = client.post(
            "/payment-reconciliation/", json=reconciliation_data
        )
        reconciliation_id = create_response.json()["id"]

        action = ReconciliationAction.EXCEPTION_HANDLED.value
        resolution_data = {
            "reconciliation_action": action,
            "resolution_notes": "Customer discount applied",
            "resolved_by": 1,
        }

        response = client.post(
            f"/payment-reconciliation/{reconciliation_id}/resolve", json=resolution_data
        )

        assert response.status_code == 200
        data = response.json()
        status = ReconciliationStatus.RESOLVED.value
        assert data["reconciliation_status"] == status
        action = ReconciliationAction.EXCEPTION_HANDLED.value
        assert data["reconciliation_action"] == action
        assert data["resolution_notes"] == "Customer discount applied"

    def test_get_payment_reconciliation_not_found(self, client: TestClient):
        response = client.get("/payment-reconciliation/999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_create_payment_reconciliation_invalid_order(self, client: TestClient):
        reconciliation_data = {
            "order_id": 999,
            "external_payment_reference": "PAY_INVALID",
            "amount_expected": "25.00",
            "amount_received": "25.00",
            "reconciliation_status": ReconciliationStatus.MATCHED.value,
        }

        response = client.post("/payment-reconciliation/", json=reconciliation_data)

        assert response.status_code == 404
        assert "Order with id 999 not found" in response.json()["detail"]
