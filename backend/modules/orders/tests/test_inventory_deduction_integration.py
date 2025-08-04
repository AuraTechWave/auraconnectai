# backend/modules/orders/tests/test_inventory_deduction_integration.py

import pytest
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException

from core.database import get_test_db
from core.auth import create_access_token
from core.models import User, Role
from core.inventory_models import Inventory, InventoryAdjustment, AdjustmentType
from ..models.order_models import Order, OrderItem, OrderStatus
from ..schemas.order_schemas import OrderCreate, OrderUpdate, OrderItemCreate
from ..services.order_service import update_order_service
from ..services.recipe_inventory_service import RecipeInventoryService
from ...menu.models.menu_models import MenuItem, MenuItemStatus, Category
from ...menu.models.recipe_models import Recipe, RecipeIngredient, RecipeSubRecipe, RecipeStatus


@pytest.fixture
def test_user(db: Session):
    """Create a test user with manager role."""
    # Create roles
    staff_role = Role(name="staff", description="Staff role")
    manager_role = Role(name="manager", description="Manager role")
    db.add_all([staff_role, manager_role])
    db.flush()
    
    # Create user
    user = User(
        id=1,
        username="testmanager",
        email="manager@test.com",
        is_active=True,
        roles=[manager_role]
    )
    db.add(user)
    db.commit()
    
    return user


@pytest.fixture
def setup_restaurant_data(db: Session):
    """Set up comprehensive restaurant data for integration testing."""
    # Create category
    category = Category(
        id=1,
        name="Pizzas",
        description="Our delicious pizzas",
        is_active=True
    )
    db.add(category)
    
    # Create inventory items
    inventory_items = [
        Inventory(
            id=1,
            item_name="Pizza Dough",
            quantity=100.0,
            unit="piece",
            threshold=20.0,
            cost_per_unit=0.50,
            is_active=True
        ),
        Inventory(
            id=2,
            item_name="Tomato Sauce",
            quantity=50.0,
            unit="liter",
            threshold=10.0,
            cost_per_unit=2.00,
            is_active=True
        ),
        Inventory(
            id=3,
            item_name="Mozzarella Cheese",
            quantity=40.0,
            unit="kg",
            threshold=8.0,
            cost_per_unit=8.00,
            is_active=True
        ),
        Inventory(
            id=4,
            item_name="Pepperoni",
            quantity=25.0,
            unit="kg",
            threshold=5.0,
            cost_per_unit=12.00,
            is_active=True
        ),
        Inventory(
            id=5,
            item_name="Basil",
            quantity=5.0,
            unit="kg",
            threshold=1.0,
            cost_per_unit=20.00,
            is_active=True
        ),
        Inventory(
            id=6,
            item_name="Olive Oil",
            quantity=20.0,
            unit="liter",
            threshold=4.0,
            cost_per_unit=10.00,
            is_active=True
        )
    ]
    db.add_all(inventory_items)
    
    # Create menu items
    menu_items = [
        MenuItem(
            id=1,
            name="Margherita Pizza",
            description="Classic Italian pizza",
            price=12.99,
            category_id=1,
            status=MenuItemStatus.ACTIVE,
            is_active=True
        ),
        MenuItem(
            id=2,
            name="Pepperoni Pizza",
            description="Pizza with pepperoni",
            price=14.99,
            category_id=1,
            status=MenuItemStatus.ACTIVE,
            is_active=True
        ),
        MenuItem(
            id=3,
            name="Garlic Bread",
            description="Bread with garlic and herbs",
            price=5.99,
            category_id=1,
            status=MenuItemStatus.ACTIVE,
            is_active=True
        )
    ]
    db.add_all(menu_items)
    db.flush()
    
    # Create recipes
    # Margherita Pizza Recipe
    margherita_recipe = Recipe(
        id=1,
        menu_item_id=1,
        name="Margherita Pizza Recipe",
        status=RecipeStatus.ACTIVE,
        yield_quantity=1,
        yield_unit="pizza",
        created_by=1
    )
    db.add(margherita_recipe)
    
    # Pepperoni Pizza Recipe
    pepperoni_recipe = Recipe(
        id=2,
        menu_item_id=2,
        name="Pepperoni Pizza Recipe",
        status=RecipeStatus.ACTIVE,
        yield_quantity=1,
        yield_unit="pizza",
        created_by=1
    )
    db.add(pepperoni_recipe)
    
    # Garlic Bread Recipe
    garlic_bread_recipe = Recipe(
        id=3,
        menu_item_id=3,
        name="Garlic Bread Recipe",
        status=RecipeStatus.ACTIVE,
        yield_quantity=1,
        yield_unit="portion",
        created_by=1
    )
    db.add(garlic_bread_recipe)
    
    db.flush()
    
    # Add ingredients to recipes
    # Margherita ingredients
    margherita_ingredients = [
        RecipeIngredient(recipe_id=1, inventory_id=1, quantity=1, unit="piece", created_by=1),  # Dough
        RecipeIngredient(recipe_id=1, inventory_id=2, quantity=0.15, unit="liter", created_by=1),  # Sauce
        RecipeIngredient(recipe_id=1, inventory_id=3, quantity=0.2, unit="kg", created_by=1),  # Cheese
        RecipeIngredient(recipe_id=1, inventory_id=5, quantity=0.01, unit="kg", created_by=1),  # Basil
    ]
    
    # Pepperoni ingredients (shares dough, sauce, cheese with Margherita)
    pepperoni_ingredients = [
        RecipeIngredient(recipe_id=2, inventory_id=1, quantity=1, unit="piece", created_by=1),  # Dough
        RecipeIngredient(recipe_id=2, inventory_id=2, quantity=0.15, unit="liter", created_by=1),  # Sauce
        RecipeIngredient(recipe_id=2, inventory_id=3, quantity=0.25, unit="kg", created_by=1),  # More cheese
        RecipeIngredient(recipe_id=2, inventory_id=4, quantity=0.1, unit="kg", created_by=1),  # Pepperoni
    ]
    
    # Garlic bread ingredients (shares dough with pizzas)
    garlic_bread_ingredients = [
        RecipeIngredient(recipe_id=3, inventory_id=1, quantity=0.5, unit="piece", created_by=1),  # Half dough
        RecipeIngredient(recipe_id=3, inventory_id=6, quantity=0.05, unit="liter", created_by=1),  # Olive oil
        RecipeIngredient(recipe_id=3, inventory_id=5, quantity=0.005, unit="kg", created_by=1),  # Basil
    ]
    
    db.add_all(margherita_ingredients + pepperoni_ingredients + garlic_bread_ingredients)
    db.commit()
    
    return {
        "inventory_items": inventory_items,
        "menu_items": menu_items,
        "recipes": [margherita_recipe, pepperoni_recipe, garlic_bread_recipe]
    }


@pytest.mark.integration
@pytest.mark.db
class TestOrderInventoryIntegration:
    """Integration tests for the complete order-to-inventory flow."""
    
    @pytest.mark.slow
    async def test_place_order_verify_ingredient_deduction(self, db: Session, setup_restaurant_data, test_user):
        """Test placing an order and verifying correct ingredient deduction."""
        # Get initial inventory quantities
        initial_dough = db.query(Inventory).filter(Inventory.id == 1).first().quantity  # 100
        initial_sauce = db.query(Inventory).filter(Inventory.id == 2).first().quantity  # 50
        initial_cheese = db.query(Inventory).filter(Inventory.id == 3).first().quantity  # 40
        initial_basil = db.query(Inventory).filter(Inventory.id == 5).first().quantity  # 5
        
        # Create an order with 2 Margherita pizzas
        order = Order(
            id=1,
            order_number="ORD-001",
            status=OrderStatus.PENDING,
            total_amount=25.98,
            created_by=test_user.id
        )
        db.add(order)
        db.flush()
        
        # Add order items
        order_items = [
            OrderItem(
                order_id=1,
                menu_item_id=1,  # Margherita Pizza
                quantity=2,
                price=12.99
            )
        ]
        db.add_all(order_items)
        db.commit()
        
        # Update order status to IN_PROGRESS (triggers deduction)
        order_update = OrderUpdate(status=OrderStatus.IN_PROGRESS)
        result = await update_order_service(
            order_id=1,
            order_update=order_update,
            db=db,
            user_id=test_user.id
        )
        
        # Verify order was updated
        assert result["data"].status == OrderStatus.IN_PROGRESS.value
        
        # Verify inventory was deducted correctly
        db.refresh(db.query(Inventory).filter(Inventory.id == 1).first())
        db.refresh(db.query(Inventory).filter(Inventory.id == 2).first())
        db.refresh(db.query(Inventory).filter(Inventory.id == 3).first())
        db.refresh(db.query(Inventory).filter(Inventory.id == 5).first())
        
        # Expected deductions for 2 Margherita pizzas:
        # - Dough: 2 * 1 = 2 pieces
        # - Sauce: 2 * 0.15 = 0.3 liters
        # - Cheese: 2 * 0.2 = 0.4 kg
        # - Basil: 2 * 0.01 = 0.02 kg
        
        final_dough = db.query(Inventory).filter(Inventory.id == 1).first().quantity
        final_sauce = db.query(Inventory).filter(Inventory.id == 2).first().quantity
        final_cheese = db.query(Inventory).filter(Inventory.id == 3).first().quantity
        final_basil = db.query(Inventory).filter(Inventory.id == 5).first().quantity
        
        assert final_dough == initial_dough - 2
        assert final_sauce == initial_sauce - 0.3
        assert final_cheese == initial_cheese - 0.4
        assert final_basil == pytest.approx(initial_basil - 0.02, rel=1e-3)
        
        # Verify inventory adjustments were created
        adjustments = db.query(InventoryAdjustment).filter(
            InventoryAdjustment.reference_type == "order",
            InventoryAdjustment.reference_id == "1"
        ).all()
        
        assert len(adjustments) == 4  # One for each ingredient
        
        # Verify adjustment details
        dough_adjustment = next(a for a in adjustments if a.inventory_id == 1)
        assert dough_adjustment.adjustment_type == AdjustmentType.CONSUMPTION
        assert dough_adjustment.quantity_change == -2
        assert dough_adjustment.reason == "Order #1 - order_progress"
    
    async def test_cancel_order_ensure_inventory_rollback(self, db: Session, setup_restaurant_data, test_user):
        """Test cancelling an order and ensuring inventory is rolled back."""
        # Create and process an order first
        order = Order(
            id=2,
            order_number="ORD-002",
            status=OrderStatus.PENDING,
            total_amount=14.99,
            created_by=test_user.id
        )
        db.add(order)
        
        order_item = OrderItem(
            order_id=2,
            menu_item_id=2,  # Pepperoni Pizza
            quantity=1,
            price=14.99
        )
        db.add(order_item)
        db.commit()
        
        # Get initial quantities
        initial_dough = db.query(Inventory).filter(Inventory.id == 1).first().quantity
        initial_pepperoni = db.query(Inventory).filter(Inventory.id == 4).first().quantity
        
        # Move to IN_PROGRESS (deducts inventory)
        order_update = OrderUpdate(status=OrderStatus.IN_PROGRESS)
        await update_order_service(
            order_id=2,
            order_update=order_update,
            db=db,
            user_id=test_user.id
        )
        
        # Verify deduction happened
        db.refresh(db.query(Inventory).filter(Inventory.id == 1).first())
        db.refresh(db.query(Inventory).filter(Inventory.id == 4).first())
        
        after_deduction_dough = db.query(Inventory).filter(Inventory.id == 1).first().quantity
        after_deduction_pepperoni = db.query(Inventory).filter(Inventory.id == 4).first().quantity
        
        assert after_deduction_dough == initial_dough - 1
        assert after_deduction_pepperoni == initial_pepperoni - 0.1
        
        # Now cancel the order
        cancel_update = OrderUpdate(status=OrderStatus.CANCELLED)
        await update_order_service(
            order_id=2,
            order_update=cancel_update,
            db=db,
            user_id=test_user.id
        )
        
        # Verify inventory was rolled back
        db.refresh(db.query(Inventory).filter(Inventory.id == 1).first())
        db.refresh(db.query(Inventory).filter(Inventory.id == 4).first())
        
        final_dough = db.query(Inventory).filter(Inventory.id == 1).first().quantity
        final_pepperoni = db.query(Inventory).filter(Inventory.id == 4).first().quantity
        
        assert final_dough == initial_dough  # Should be restored
        assert final_pepperoni == pytest.approx(initial_pepperoni, rel=1e-3)  # Should be restored
        
        # Verify reversal adjustments were created
        reversal_adjustments = db.query(InventoryAdjustment).filter(
            InventoryAdjustment.reference_type == "order_reversal",
            InventoryAdjustment.reference_id == "2"
        ).all()
        
        assert len(reversal_adjustments) == 4  # One reversal for each ingredient
        
        # Verify reversal details
        dough_reversal = next(a for a in reversal_adjustments if a.inventory_id == 1)
        assert dough_reversal.adjustment_type == AdjustmentType.RETURN
        assert dough_reversal.quantity_change == 1  # Positive for return
        assert "Order cancelled" in dough_reversal.reason
    
    @pytest.mark.slow
    async def test_multiple_items_shared_ingredients(self, db: Session, setup_restaurant_data, test_user):
        """Test order with multiple menu items that share ingredients."""
        # Create order with mixed items that share ingredients
        order = Order(
            id=3,
            order_number="ORD-003",
            status=OrderStatus.PENDING,
            total_amount=33.97,  # 1 Margherita + 1 Pepperoni + 1 Garlic Bread
            created_by=test_user.id
        )
        db.add(order)
        db.flush()
        
        # Add multiple order items
        order_items = [
            OrderItem(order_id=3, menu_item_id=1, quantity=1, price=12.99),  # Margherita
            OrderItem(order_id=3, menu_item_id=2, quantity=1, price=14.99),  # Pepperoni
            OrderItem(order_id=3, menu_item_id=3, quantity=1, price=5.99),   # Garlic Bread
        ]
        db.add_all(order_items)
        db.commit()
        
        # Get initial quantities for shared ingredients
        initial_dough = db.query(Inventory).filter(Inventory.id == 1).first().quantity
        initial_sauce = db.query(Inventory).filter(Inventory.id == 2).first().quantity
        initial_cheese = db.query(Inventory).filter(Inventory.id == 3).first().quantity
        initial_basil = db.query(Inventory).filter(Inventory.id == 5).first().quantity
        
        # Process the order
        order_update = OrderUpdate(status=OrderStatus.IN_PROGRESS)
        await update_order_service(
            order_id=3,
            order_update=order_update,
            db=db,
            user_id=test_user.id
        )
        
        # Verify combined deductions for shared ingredients
        db.refresh(db.query(Inventory).filter(Inventory.id == 1).first())
        db.refresh(db.query(Inventory).filter(Inventory.id == 2).first())
        db.refresh(db.query(Inventory).filter(Inventory.id == 3).first())
        db.refresh(db.query(Inventory).filter(Inventory.id == 5).first())
        
        final_dough = db.query(Inventory).filter(Inventory.id == 1).first().quantity
        final_sauce = db.query(Inventory).filter(Inventory.id == 2).first().quantity
        final_cheese = db.query(Inventory).filter(Inventory.id == 3).first().quantity
        final_basil = db.query(Inventory).filter(Inventory.id == 5).first().quantity
        
        # Expected deductions:
        # Dough: 1 (Margherita) + 1 (Pepperoni) + 0.5 (Garlic Bread) = 2.5
        # Sauce: 0.15 (Margherita) + 0.15 (Pepperoni) = 0.3
        # Cheese: 0.2 (Margherita) + 0.25 (Pepperoni) = 0.45
        # Basil: 0.01 (Margherita) + 0.005 (Garlic Bread) = 0.015
        
        assert final_dough == initial_dough - 2.5
        assert final_sauce == initial_sauce - 0.3
        assert final_cheese == initial_cheese - 0.45
        assert final_basil == pytest.approx(initial_basil - 0.015, rel=1e-3)
        
        # Verify adjustments show correct aggregated quantities
        adjustments = db.query(InventoryAdjustment).filter(
            InventoryAdjustment.reference_type == "order",
            InventoryAdjustment.reference_id == "3"
        ).all()
        
        # Should have adjustments for each unique ingredient used
        assert len(adjustments) == 6  # Dough, Sauce, Cheese, Pepperoni, Basil, Olive Oil
        
        # Check metadata shows which recipes contributed
        dough_adjustment = next(a for a in adjustments if a.inventory_id == 1)
        assert len(dough_adjustment.metadata["recipes"]) == 3  # Used in 3 recipes
    
    async def test_insufficient_inventory_handling(self, db: Session, setup_restaurant_data, test_user):
        """Test handling of orders when inventory is insufficient."""
        # Set cheese inventory very low
        cheese = db.query(Inventory).filter(Inventory.id == 3).first()
        cheese.quantity = 0.1  # Not enough for any pizza
        db.commit()
        
        # Try to create an order
        order = Order(
            id=4,
            order_number="ORD-004",
            status=OrderStatus.PENDING,
            total_amount=12.99,
            created_by=test_user.id
        )
        db.add(order)
        
        order_item = OrderItem(
            order_id=4,
            menu_item_id=1,  # Margherita (needs 0.2 kg cheese)
            quantity=1,
            price=12.99
        )
        db.add(order_item)
        db.commit()
        
        # Try to process the order - should fail
        order_update = OrderUpdate(status=OrderStatus.IN_PROGRESS)
        
        with pytest.raises(HTTPException) as exc_info:
            await update_order_service(
                order_id=4,
                order_update=order_update,
                db=db,
                user_id=test_user.id
            )
        
        # Verify the error
        assert exc_info.value.status_code == 400
        assert "Insufficient inventory" in str(exc_info.value.detail)
        
        # Verify order status didn't change
        db.refresh(order)
        assert order.status == OrderStatus.PENDING
        
        # Verify no inventory was deducted
        db.refresh(cheese)
        assert cheese.quantity == 0.1  # Unchanged
    
    async def test_low_stock_alert_generation(self, db: Session, setup_restaurant_data, test_user):
        """Test that low stock alerts are generated when threshold is reached."""
        # Set basil inventory close to threshold
        basil = db.query(Inventory).filter(Inventory.id == 5).first()
        basil.quantity = 1.02  # Just above threshold of 1.0
        db.commit()
        
        # Create order that will trigger low stock
        order = Order(
            id=5,
            order_number="ORD-005",
            status=OrderStatus.PENDING,
            total_amount=12.99,
            created_by=test_user.id
        )
        db.add(order)
        
        order_item = OrderItem(
            order_id=5,
            menu_item_id=1,  # Margherita (uses 0.01 kg basil)
            quantity=2,  # Will use 0.02 kg, bringing basil to 1.0
            price=12.99
        )
        db.add(order_item)
        db.commit()
        
        # Process the order
        order_update = OrderUpdate(status=OrderStatus.IN_PROGRESS)
        result = await update_order_service(
            order_id=5,
            order_update=order_update,
            db=db,
            user_id=test_user.id
        )
        
        # Order should succeed
        assert result["data"].status == OrderStatus.IN_PROGRESS.value
        
        # Check basil is at threshold
        db.refresh(basil)
        assert basil.quantity == 1.0  # Exactly at threshold
        
        # In a real system, this would trigger notifications
        # For now, we can verify the service detected low stock
        recipe_service = RecipeInventoryService(db)
        preview = await recipe_service.get_inventory_impact_preview([order_item])
        
        basil_impact = next(
            item for item in preview["impact_preview"] 
            if item["inventory_id"] == 5
        )
        assert basil_impact["will_be_low_stock"] is True
    
    async def test_order_completion_deduction_mode(self, db: Session, setup_restaurant_data, test_user, monkeypatch):
        """Test inventory deduction on order completion instead of progress."""
        # Mock the config to deduct on completion
        from ..config.inventory_config import get_inventory_config
        
        class MockConfig:
            USE_RECIPE_BASED_INVENTORY_DEDUCTION = True
            DEDUCT_INVENTORY_ON_COMPLETION = True
            AUTO_REVERSE_ON_CANCELLATION = True
        
        monkeypatch.setattr("modules.orders.services.order_service.get_inventory_config", lambda: MockConfig())
        
        # Create order
        order = Order(
            id=6,
            order_number="ORD-006",
            status=OrderStatus.PENDING,
            total_amount=5.99,
            created_by=test_user.id
        )
        db.add(order)
        
        order_item = OrderItem(
            order_id=6,
            menu_item_id=3,  # Garlic Bread
            quantity=1,
            price=5.99
        )
        db.add(order_item)
        db.commit()
        
        initial_dough = db.query(Inventory).filter(Inventory.id == 1).first().quantity
        
        # Move to IN_PROGRESS - should NOT deduct yet
        order_update = OrderUpdate(status=OrderStatus.IN_PROGRESS)
        await update_order_service(
            order_id=6,
            order_update=order_update,
            db=db,
            user_id=test_user.id
        )
        
        # Verify no deduction yet
        db.refresh(db.query(Inventory).filter(Inventory.id == 1).first())
        assert db.query(Inventory).filter(Inventory.id == 1).first().quantity == initial_dough
        
        # Complete the order - NOW it should deduct
        complete_update = OrderUpdate(status=OrderStatus.COMPLETED)
        await update_order_service(
            order_id=6,
            order_update=complete_update,
            db=db,
            user_id=test_user.id
        )
        
        # Verify deduction happened on completion
        db.refresh(db.query(Inventory).filter(Inventory.id == 1).first())
        final_dough = db.query(Inventory).filter(Inventory.id == 1).first().quantity
        assert final_dough == initial_dough - 0.5  # Garlic bread uses 0.5 dough
    
    @pytest.mark.slow
    async def test_complex_order_flow_with_modifications(self, db: Session, setup_restaurant_data, test_user):
        """Test a complex order flow with modifications and status changes."""
        # Create initial order
        order = Order(
            id=7,
            order_number="ORD-007",
            status=OrderStatus.PENDING,
            total_amount=27.98,
            created_by=test_user.id
        )
        db.add(order)
        
        # Initial items
        order_items = [
            OrderItem(order_id=7, menu_item_id=1, quantity=2, price=12.99)  # 2 Margherita
        ]
        db.add_all(order_items)
        db.commit()
        
        initial_dough = db.query(Inventory).filter(Inventory.id == 1).first().quantity
        
        # Start processing
        order_update = OrderUpdate(status=OrderStatus.IN_PROGRESS)
        await update_order_service(7, order_update, db, test_user.id)
        
        # Verify initial deduction
        db.refresh(db.query(Inventory).filter(Inventory.id == 1).first())
        assert db.query(Inventory).filter(Inventory.id == 1).first().quantity == initial_dough - 2
        
        # Now modify the order (add another item)
        # In real system, this might require special handling
        new_item = OrderItem(order_id=7, menu_item_id=3, quantity=1, price=5.99)
        db.add(new_item)
        order.total_amount += 5.99
        db.commit()
        
        # The new item hasn't been deducted yet
        # This demonstrates a limitation - modifications after IN_PROGRESS need special handling
        
        # Move through remaining statuses
        for status in [OrderStatus.READY, OrderStatus.SERVED, OrderStatus.COMPLETED]:
            status_update = OrderUpdate(status=status)
            await update_order_service(7, status_update, db, test_user.id)
        
        # Verify final status
        db.refresh(order)
        assert order.status == OrderStatus.COMPLETED
    
    @pytest.mark.slow
    @pytest.mark.concurrent
    async def test_concurrent_orders_shared_inventory(self, db: Session, setup_restaurant_data, test_user):
        """Test handling of concurrent orders competing for limited shared inventory."""
        # Set dough inventory low - only enough for 3 pizzas
        dough = db.query(Inventory).filter(Inventory.id == 1).first()
        dough.quantity = 3.0
        db.commit()
        
        # Create two orders that together would exceed available dough
        orders_data = [
            {"id": 8, "number": "ORD-008", "menu_item_id": 1, "quantity": 2},  # Needs 2 dough
            {"id": 9, "number": "ORD-009", "menu_item_id": 2, "quantity": 2},  # Needs 2 dough
        ]
        
        successful_orders = []
        failed_orders = []
        
        for order_data in orders_data:
            try:
                # Create order
                order = Order(
                    id=order_data["id"],
                    order_number=order_data["number"],
                    status=OrderStatus.PENDING,
                    total_amount=25.98,
                    created_by=test_user.id
                )
                db.add(order)
                
                order_item = OrderItem(
                    order_id=order_data["id"],
                    menu_item_id=order_data["menu_item_id"],
                    quantity=order_data["quantity"],
                    price=12.99
                )
                db.add(order_item)
                db.commit()
                
                # Try to process
                order_update = OrderUpdate(status=OrderStatus.IN_PROGRESS)
                await update_order_service(
                    order_data["id"],
                    order_update,
                    db,
                    test_user.id
                )
                successful_orders.append(order_data["id"])
                
            except HTTPException:
                failed_orders.append(order_data["id"])
                db.rollback()
        
        # One order should succeed, one should fail
        assert len(successful_orders) == 1
        assert len(failed_orders) == 1
        
        # Verify remaining dough
        db.refresh(dough)
        assert dough.quantity == 1.0  # 3 - 2 = 1