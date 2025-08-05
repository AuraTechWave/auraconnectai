# backend/modules/inventory/tests/test_waste_tracking.py

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.inventory_models import Inventory, InventoryAdjustment, AdjustmentType, WasteReason
from core.inventory_schemas import WasteEventCreate, WasteEventResponse
from core.auth import User


class TestWasteTracking:
    """Test suite for waste tracking endpoints"""
    
    @pytest.fixture
    def sample_inventory_item(self, db: Session) -> Inventory:
        """Create a sample inventory item for testing"""
        item = Inventory(
            item_name="Tomatoes",
            description="Fresh Roma tomatoes",
            sku="PROD-001",
            category="Produce",
            quantity=100.0,
            unit="lbs",
            threshold=20.0,
            cost_per_unit=2.50,
            vendor_id=1,
            storage_location="Walk-in Cooler A",
            storage_temperature="refrigerated",
            perishable=True,
            track_expiration=True,
            is_active=True,
            created_by=1
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item
    
    @pytest.fixture
    def auth_headers(self, test_user: User) -> dict:
        """Get authorization headers for test user"""
        return {"Authorization": f"Bearer {test_user.token}"}
    
    def test_create_valid_waste_event(self, client: TestClient, sample_inventory_item: Inventory, auth_headers: dict):
        """Test creating a valid waste event"""
        waste_data = {
            "inventory_id": sample_inventory_item.id,
            "quantity": 5.0,
            "waste_reason": WasteReason.EXPIRED.value,
            "batch_number": "BATCH-2024-001",
            "location": "Walk-in Cooler A",
            "witnessed_by": "John Doe"
        }
        
        response = client.post(
            f"/api/v1/inventory/{sample_inventory_item.id}/waste",
            json=waste_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["inventory_id"] == sample_inventory_item.id
        assert data["quantity_wasted"] == 5.0
        assert data["waste_reason"] == WasteReason.EXPIRED.value
        assert data["total_cost"] == 5.0 * 2.50  # quantity * cost_per_unit
        assert data["witnessed_by"] == "John Doe"
    
    def test_create_waste_event_with_other_reason(self, client: TestClient, sample_inventory_item: Inventory, auth_headers: dict):
        """Test creating waste event with OTHER reason requiring custom description"""
        waste_data = {
            "inventory_id": sample_inventory_item.id,
            "quantity": 3.0,
            "waste_reason": WasteReason.OTHER.value,
            "custom_reason": "Power outage caused temperature excursion beyond safe limits",
            "temperature_at_waste": 55.0,
            "location": "Walk-in Cooler A"
        }
        
        response = client.post(
            f"/api/v1/inventory/{sample_inventory_item.id}/waste",
            json=waste_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["waste_reason"] == WasteReason.OTHER.value
        assert data["custom_reason"] == "Power outage caused temperature excursion beyond safe limits"
    
    def test_create_waste_event_invalid_quantity(self, client: TestClient, sample_inventory_item: Inventory, auth_headers: dict):
        """Test validation for negative or zero quantity"""
        # Test zero quantity
        waste_data = {
            "inventory_id": sample_inventory_item.id,
            "quantity": 0,
            "waste_reason": WasteReason.DAMAGED.value
        }
        
        response = client.post(
            f"/api/v1/inventory/{sample_inventory_item.id}/waste",
            json=waste_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422
        assert "greater than 0" in response.json()["detail"][0]["msg"]
        
        # Test negative quantity
        waste_data["quantity"] = -5.0
        response = client.post(
            f"/api/v1/inventory/{sample_inventory_item.id}/waste",
            json=waste_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422
    
    def test_create_waste_event_exceeds_available_quantity(self, client: TestClient, sample_inventory_item: Inventory, auth_headers: dict):
        """Test validation when waste quantity exceeds available stock"""
        waste_data = {
            "inventory_id": sample_inventory_item.id,
            "quantity": 150.0,  # More than the 100.0 available
            "waste_reason": WasteReason.SPILLAGE.value
        }
        
        response = client.post(
            f"/api/v1/inventory/{sample_inventory_item.id}/waste",
            json=waste_data,
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "Cannot waste 150.0 lbs. Only 100.0 lbs available" in response.json()["detail"]
    
    def test_create_waste_event_nonexistent_item(self, client: TestClient, auth_headers: dict):
        """Test 404 error when inventory item doesn't exist"""
        waste_data = {
            "inventory_id": 99999,
            "quantity": 5.0,
            "waste_reason": WasteReason.EXPIRED.value
        }
        
        response = client.post(
            "/api/v1/inventory/99999/waste",
            json=waste_data,
            headers=auth_headers
        )
        
        assert response.status_code == 404
        assert "Inventory item with ID 99999 not found" in response.json()["detail"]
    
    def test_create_waste_event_mismatched_inventory_id(self, client: TestClient, sample_inventory_item: Inventory, auth_headers: dict):
        """Test validation when request body inventory_id doesn't match path parameter"""
        waste_data = {
            "inventory_id": sample_inventory_item.id + 1,  # Different ID
            "quantity": 5.0,
            "waste_reason": WasteReason.DAMAGED.value
        }
        
        response = client.post(
            f"/api/v1/inventory/{sample_inventory_item.id}/waste",
            json=waste_data,
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "Inventory ID in request body doesn't match path parameter" in response.json()["detail"]
    
    def test_create_waste_event_other_reason_missing_custom(self, client: TestClient, sample_inventory_item: Inventory, auth_headers: dict):
        """Test validation when OTHER reason is selected but custom_reason is missing"""
        waste_data = {
            "inventory_id": sample_inventory_item.id,
            "quantity": 5.0,
            "waste_reason": WasteReason.OTHER.value
            # Missing custom_reason
        }
        
        response = client.post(
            f"/api/v1/inventory/{sample_inventory_item.id}/waste",
            json=waste_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422
        assert "Custom reason is required when waste_reason is OTHER" in str(response.json()["detail"])
    
    def test_get_waste_history(self, client: TestClient, sample_inventory_item: Inventory, auth_headers: dict, db: Session):
        """Test retrieving waste history for an inventory item"""
        # Create some waste events
        for i in range(3):
            waste_data = {
                "inventory_id": sample_inventory_item.id,
                "quantity": 2.0,
                "waste_reason": WasteReason.EXPIRED.value if i % 2 == 0 else WasteReason.DAMAGED.value,
                "location": f"Location {i}"
            }
            client.post(
                f"/api/v1/inventory/{sample_inventory_item.id}/waste",
                json=waste_data,
                headers=auth_headers
            )
        
        # Get waste history
        response = client.get(
            f"/api/v1/inventory/{sample_inventory_item.id}/waste",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert all(event["inventory_id"] == sample_inventory_item.id for event in data)
        assert data[0]["created_at"] > data[1]["created_at"]  # Should be ordered by date desc
    
    def test_get_waste_history_with_filters(self, client: TestClient, sample_inventory_item: Inventory, auth_headers: dict):
        """Test filtering waste history by date and reason"""
        # Create waste events
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        
        # Create yesterday's waste
        waste_data = {
            "inventory_id": sample_inventory_item.id,
            "quantity": 3.0,
            "waste_reason": WasteReason.EXPIRED.value
        }
        client.post(
            f"/api/v1/inventory/{sample_inventory_item.id}/waste",
            json=waste_data,
            headers=auth_headers
        )
        
        # Get filtered history
        response = client.get(
            f"/api/v1/inventory/{sample_inventory_item.id}/waste",
            params={
                "start_date": today.isoformat(),
                "waste_reason": WasteReason.EXPIRED.value
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert all(event["waste_reason"] == WasteReason.EXPIRED.value for event in data)
    
    def test_get_waste_history_nonexistent_item(self, client: TestClient, auth_headers: dict):
        """Test 404 error when getting history for non-existent item"""
        response = client.get(
            "/api/v1/inventory/99999/waste",
            headers=auth_headers
        )
        
        assert response.status_code == 404
        assert "Inventory item with ID 99999 not found" in response.json()["detail"]
    
    def test_waste_event_updates_inventory_quantity(self, client: TestClient, sample_inventory_item: Inventory, auth_headers: dict, db: Session):
        """Test that waste events properly reduce inventory quantity"""
        initial_quantity = sample_inventory_item.quantity
        waste_quantity = 10.0
        
        waste_data = {
            "inventory_id": sample_inventory_item.id,
            "quantity": waste_quantity,
            "waste_reason": WasteReason.SPILLAGE.value
        }
        
        response = client.post(
            f"/api/v1/inventory/{sample_inventory_item.id}/waste",
            json=waste_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        
        # Check inventory quantity was reduced
        db.refresh(sample_inventory_item)
        assert sample_inventory_item.quantity == initial_quantity - waste_quantity
    
    def test_waste_event_creates_audit_trail(self, client: TestClient, sample_inventory_item: Inventory, auth_headers: dict, db: Session):
        """Test that waste events create proper audit trail in adjustments table"""
        waste_data = {
            "inventory_id": sample_inventory_item.id,
            "quantity": 5.0,
            "waste_reason": WasteReason.CONTAMINATED.value,
            "witnessed_by": "Jane Smith",
            "temperature_at_waste": 72.5,
            "batch_number": "BATCH-123"
        }
        
        response = client.post(
            f"/api/v1/inventory/{sample_inventory_item.id}/waste",
            json=waste_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        
        # Check adjustment was created
        adjustment = db.query(InventoryAdjustment).filter(
            InventoryAdjustment.inventory_id == sample_inventory_item.id,
            InventoryAdjustment.adjustment_type == AdjustmentType.WASTE
        ).first()
        
        assert adjustment is not None
        assert adjustment.quantity_change == -5.0
        assert "contaminated" in adjustment.reason.lower()
        assert "Witnessed by: Jane Smith" in adjustment.notes
        assert "Temperature: 72.5°F" in adjustment.notes
        assert "Batch: BATCH-123" in adjustment.notes
        assert adjustment.reference_type == "waste_event"
    
    def test_concurrent_waste_events(self, client: TestClient, sample_inventory_item: Inventory, auth_headers: dict):
        """Test handling of concurrent waste events to ensure no over-wasting"""
        # This test would ideally use threading or async to simulate concurrent requests
        # For now, we'll just ensure sequential requests respect quantity limits
        
        # First waste event
        waste_data = {
            "inventory_id": sample_inventory_item.id,
            "quantity": 95.0,
            "waste_reason": WasteReason.EXPIRED.value
        }
        response1 = client.post(
            f"/api/v1/inventory/{sample_inventory_item.id}/waste",
            json=waste_data,
            headers=auth_headers
        )
        assert response1.status_code == 201
        
        # Second waste event should fail (only 5.0 left)
        waste_data["quantity"] = 10.0
        response2 = client.post(
            f"/api/v1/inventory/{sample_inventory_item.id}/waste",
            json=waste_data,
            headers=auth_headers
        )
        assert response2.status_code == 400
        assert "Only 5.0 lbs available" in response2.json()["detail"]
    
    def test_waste_event_pagination(self, client: TestClient, sample_inventory_item: Inventory, auth_headers: dict):
        """Test pagination of waste history"""
        # Create 10 waste events
        for i in range(10):
            waste_data = {
                "inventory_id": sample_inventory_item.id,
                "quantity": 1.0,
                "waste_reason": WasteReason.SPILLAGE.value
            }
            client.post(
                f"/api/v1/inventory/{sample_inventory_item.id}/waste",
                json=waste_data,
                headers=auth_headers
            )
        
        # Get first page
        response = client.get(
            f"/api/v1/inventory/{sample_inventory_item.id}/waste",
            params={"limit": 5, "offset": 0},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert len(response.json()) == 5
        
        # Get second page
        response = client.get(
            f"/api/v1/inventory/{sample_inventory_item.id}/waste",
            params={"limit": 5, "offset": 5},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert len(response.json()) == 5