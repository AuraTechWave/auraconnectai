# backend/modules/orders/tests/test_inventory_api_integration.py

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime

from app.main import app
from core.database import get_test_db
from core.auth import create_access_token
from core.models import User, Role
from core.inventory_models import Inventory, InventoryAdjustment
from ..models.order_models import Order, OrderItem, OrderStatus
from ...menu.models.menu_models import MenuItem, Category
from ...menu.models.recipe_models import Recipe, RecipeIngredient


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers(db: Session):
    """Create authentication headers for API requests."""
    # Create manager user
    manager_role = Role(name="manager", description="Manager")
    db.add(manager_role)
    
    user = User(
        id=1,
        username="testmanager",
        email="manager@test.com",
        is_active=True,
        roles=[manager_role]
    )
    db.add(user)
    db.commit()
    
    # Create access token
    token = create_access_token(data={"sub": user.username})
    
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def setup_test_data(db: Session):
    """Set up test data for API integration tests."""
    # Category
    category = Category(id=1, name="Test Category", is_active=True)
    db.add(category)
    
    # Inventory
    inventory_items = [
        Inventory(id=1, item_name="Flour", quantity=50.0, unit="kg", threshold=10.0, is_active=True),
        Inventory(id=2, item_name="Tomatoes", quantity=30.0, unit="kg", threshold=5.0, is_active=True),
        Inventory(id=3, item_name="Cheese", quantity=20.0, unit="kg", threshold=4.0, is_active=True),
    ]
    db.add_all(inventory_items)
    
    # Menu items
    menu_items = [
        MenuItem(id=1, name="Pizza", price=10.0, category_id=1, is_active=True),
        MenuItem(id=2, name="Pasta", price=8.0, category_id=1, is_active=True),
    ]
    db.add_all(menu_items)
    
    # Recipes
    pizza_recipe = Recipe(
        id=1,
        menu_item_id=1,
        name="Pizza Recipe",
        status="active",
        created_by=1
    )
    pasta_recipe = Recipe(
        id=2,
        menu_item_id=2,
        name="Pasta Recipe",
        status="active",
        created_by=1
    )
    db.add_all([pizza_recipe, pasta_recipe])
    db.flush()
    
    # Recipe ingredients
    ingredients = [
        RecipeIngredient(recipe_id=1, inventory_id=1, quantity=0.3, unit="kg", created_by=1),
        RecipeIngredient(recipe_id=1, inventory_id=2, quantity=0.2, unit="kg", created_by=1),
        RecipeIngredient(recipe_id=1, inventory_id=3, quantity=0.15, unit="kg", created_by=1),
        RecipeIngredient(recipe_id=2, inventory_id=1, quantity=0.2, unit="kg", created_by=1),
        RecipeIngredient(recipe_id=2, inventory_id=2, quantity=0.1, unit="kg", created_by=1),
    ]
    db.add_all(ingredients)
    
    db.commit()
    return {"inventory": inventory_items, "menu_items": menu_items}


class TestInventoryImpactAPI:
    """Test the inventory impact API endpoints."""
    
    def test_preview_order_inventory_impact(self, client: TestClient, db: Session, auth_headers, setup_test_data):
        """Test previewing inventory impact for an order."""
        # Create an order
        order = Order(
            id=1,
            order_number="TEST-001",
            status=OrderStatus.PENDING,
            total_amount=20.0
        )
        db.add(order)
        
        order_items = [
            OrderItem(order_id=1, menu_item_id=1, quantity=2, price=10.0),
            OrderItem(order_id=1, menu_item_id=2, quantity=1, price=8.0),
        ]
        db.add_all(order_items)
        db.commit()
        
        # Preview impact
        response = client.get(
            f"/inventory-impact/order/{order.id}/preview",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["order_id"] == 1
        assert data["can_fulfill"] is True
        assert len(data["impact_preview"]) == 3  # 3 inventory items affected
        
        # Check flour impact (used by both items)
        flour_impact = next(i for i in data["impact_preview"] if i["inventory_id"] == 1)
        assert flour_impact["current_quantity"] == 50.0
        assert flour_impact["required_quantity"] == 0.8  # (0.3 * 2) + (0.2 * 1)
        assert flour_impact["new_quantity"] == 49.2
        assert flour_impact["sufficient_stock"] is True
    
    def test_preview_items_inventory_impact(self, client: TestClient, auth_headers, setup_test_data):
        """Test previewing impact for items without creating an order."""
        # Request body with items
        items_data = [
            {"menu_item_id": 1, "quantity": 3},
            {"menu_item_id": 2, "quantity": 2},
        ]
        
        response = client.post(
            "/inventory-impact/preview",
            json=items_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["items_count"] == 2
        assert data["can_fulfill"] is True
        assert data["total_ingredients_affected"] == 3
        
        # Verify calculations
        flour_impact = next(i for i in data["impact_preview"] if i["item_name"] == "Flour")
        # 3 pizzas (0.3kg each) + 2 pastas (0.2kg each) = 0.9 + 0.4 = 1.3kg
        assert flour_impact["required_quantity"] == 1.3
    
    def test_partial_fulfillment_endpoint(self, client: TestClient, db: Session, auth_headers, setup_test_data):
        """Test the partial fulfillment endpoint."""
        # Create and process an order first
        order = Order(
            id=2,
            order_number="TEST-002",
            status=OrderStatus.IN_PROGRESS,
            total_amount=30.0
        )
        db.add(order)
        
        order_items = [
            OrderItem(order_id=2, menu_item_id=1, quantity=3, price=10.0),
        ]
        db.add_all(order_items)
        db.commit()
        
        # Partial fulfillment - only 2 pizzas instead of 3
        fulfillment_data = [
            {"menu_item_id": 1, "fulfilled_quantity": 2}
        ]
        
        response = client.post(
            f"/inventory-impact/order/{order.id}/partial-fulfillment",
            json=fulfillment_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["order_id"] == 2
        assert len(data["deducted_items"]) == 3  # 3 ingredients
        
        # Verify flour was deducted for only 2 pizzas
        flour_deduction = next(d for d in data["deducted_items"] if d["inventory_id"] == 1)
        assert flour_deduction["quantity_deducted"] == 0.6  # 0.3 * 2
    
    def test_reverse_deduction_endpoint(self, client: TestClient, db: Session, auth_headers, setup_test_data):
        """Test the inventory reversal endpoint."""
        # First, deduct some inventory by creating adjustments
        order_id = 3
        adjustments = [
            InventoryAdjustment(
                inventory_id=1,
                adjustment_type="consumption",
                quantity_before=50.0,
                quantity_change=-1.0,
                quantity_after=49.0,
                unit="kg",
                reason=f"Order #{order_id} - order_progress",
                reference_type="order",
                reference_id=str(order_id),
                performed_by=1
            )
        ]
        db.add_all(adjustments)
        
        # Update inventory
        flour = db.query(Inventory).filter(Inventory.id == 1).first()
        flour.quantity = 49.0
        db.commit()
        
        # Reverse the deduction
        response = client.post(
            f"/inventory-impact/order/{order_id}/reverse-deduction",
            json={"reason": "Order cancelled by customer"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["order_id"] == 3
        assert len(data["reversed_items"]) == 1
        assert data["reversal_reason"] == "Order cancelled by customer"
        
        # Verify inventory was restored
        db.refresh(flour)
        assert flour.quantity == 50.0
    
    def test_insufficient_stock_preview(self, client: TestClient, db: Session, auth_headers, setup_test_data):
        """Test preview when stock is insufficient."""
        # Set cheese very low
        cheese = db.query(Inventory).filter(Inventory.id == 3).first()
        cheese.quantity = 0.1  # Not enough for even 1 pizza
        db.commit()
        
        # Try to preview order
        items_data = [
            {"menu_item_id": 1, "quantity": 1}  # Pizza needs 0.15kg cheese
        ]
        
        response = client.post(
            "/inventory-impact/preview",
            json=items_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["can_fulfill"] is False
        
        # Find cheese in impact preview
        cheese_impact = next(i for i in data["impact_preview"] if i["inventory_id"] == 3)
        assert cheese_impact["sufficient_stock"] is False
        assert cheese_impact["current_quantity"] == 0.1
        assert cheese_impact["required_quantity"] == 0.15
        assert cheese_impact["new_quantity"] == -0.05  # Would go negative
    
    def test_unauthorized_access(self, client: TestClient, setup_test_data):
        """Test that endpoints require authentication."""
        # Try without auth header
        response = client.get("/inventory-impact/order/1/preview")
        assert response.status_code == 401
        
        response = client.post("/inventory-impact/preview", json=[])
        assert response.status_code == 401
        
        response = client.post("/inventory-impact/order/1/partial-fulfillment", json=[])
        assert response.status_code == 401
        
        response = client.post("/inventory-impact/order/1/reverse-deduction", json={"reason": "test"})
        assert response.status_code == 401
    
    def test_non_manager_access_restriction(self, client: TestClient, db: Session):
        """Test that certain endpoints require manager role."""
        # Create regular staff user
        staff_role = Role(name="staff", description="Staff")
        db.add(staff_role)
        
        staff_user = User(
            id=2,
            username="teststaff",
            email="staff@test.com",
            is_active=True,
            roles=[staff_role]
        )
        db.add(staff_user)
        db.commit()
        
        # Create staff token
        staff_token = create_access_token(data={"sub": staff_user.username})
        staff_headers = {"Authorization": f"Bearer {staff_token}"}
        
        # Staff can preview
        response = client.post(
            "/inventory-impact/preview",
            json=[{"menu_item_id": 1, "quantity": 1}],
            headers=staff_headers
        )
        assert response.status_code == 200  # Allowed
        
        # But staff cannot do partial fulfillment
        response = client.post(
            "/inventory-impact/order/1/partial-fulfillment",
            json=[],
            headers=staff_headers
        )
        assert response.status_code == 403
        assert "Only managers and admins" in response.json()["detail"]
        
        # And cannot reverse deductions
        response = client.post(
            "/inventory-impact/order/1/reverse-deduction",
            json={"reason": "test"},
            headers=staff_headers
        )
        assert response.status_code == 403
        assert "Only managers and admins" in response.json()["detail"]
    
    def test_low_stock_detection_in_preview(self, client: TestClient, db: Session, auth_headers, setup_test_data):
        """Test that low stock warnings are included in preview."""
        # Set flour close to threshold
        flour = db.query(Inventory).filter(Inventory.id == 1).first()
        flour.quantity = 10.5  # Threshold is 10.0
        db.commit()
        
        # Preview order that will bring it below threshold
        items_data = [
            {"menu_item_id": 1, "quantity": 2}  # Will use 0.6kg flour
        ]
        
        response = client.post(
            "/inventory-impact/preview",
            json=items_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Find flour impact
        flour_impact = next(i for i in data["impact_preview"] if i["inventory_id"] == 1)
        assert flour_impact["new_quantity"] == 9.9  # Below threshold of 10
        assert flour_impact["will_be_low_stock"] is True
    
    def test_complex_order_modification_flow(self, client: TestClient, db: Session, auth_headers, setup_test_data):
        """Test a complex flow with order modifications."""
        # Create initial order
        order = Order(
            id=10,
            order_number="TEST-010",
            status=OrderStatus.PENDING,
            total_amount=10.0
        )
        db.add(order)
        
        order_item = OrderItem(order_id=10, menu_item_id=1, quantity=1, price=10.0)
        db.add(order_item)
        db.commit()
        
        # Preview initial impact
        response = client.get(f"/inventory-impact/order/10/preview", headers=auth_headers)
        assert response.status_code == 200
        initial_data = response.json()
        assert initial_data["can_fulfill"] is True
        
        # Process order (this would normally trigger deduction)
        order.status = OrderStatus.IN_PROGRESS
        db.commit()
        
        # Now add another item to the order
        new_item = OrderItem(order_id=10, menu_item_id=2, quantity=1, price=8.0)
        db.add(new_item)
        order.total_amount = 18.0
        db.commit()
        
        # Preview again - should show combined impact
        response = client.get(f"/inventory-impact/order/10/preview", headers=auth_headers)
        assert response.status_code == 200
        updated_data = response.json()
        
        # Should show impact for both items
        flour_impact = next(i for i in updated_data["impact_preview"] if i["inventory_id"] == 1)
        assert flour_impact["required_quantity"] == 0.5  # 0.3 (pizza) + 0.2 (pasta)