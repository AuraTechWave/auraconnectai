# backend/modules/orders/tests/test_inventory_factory_example.py

import pytest
from sqlalchemy.orm import Session

from tests.factories import (
    UserFactory,
    RoleFactory,
    OrderWithItemsFactory,
    RecipeWithIngredientsFactory,
    InventoryFactory,
    create_restaurant_setup,
    create_order_scenario,
)
from ..services.order_service import update_order_service
from ..schemas.order_schemas import OrderUpdate
from ..models.order_models import OrderStatus
from core.inventory_models import Inventory


@pytest.mark.integration
class TestInventoryWithFactories:
    """Example tests using factories instead of hardcoded data."""

    def test_order_deduction_with_factories(self, db: Session):
        """Test order processing using factory-generated data."""
        # Create test setup
        setup = create_restaurant_setup(num_menu_items=3, num_inventory_items=5)

        # Create user
        manager_role = RoleFactory(name="manager")
        user = UserFactory(roles=[manager_role])

        # Create order with factory
        order = create_order_scenario(user=user, num_items=2)

        # Get initial inventory quantities
        initial_quantities = {}
        for inv_item in setup["inventory_items"]:
            db.refresh(inv_item)
            initial_quantities[inv_item.id] = inv_item.quantity

        # Process order
        order_update = OrderUpdate(status=OrderStatus.IN_PROGRESS)
        result = update_order_service(
            order_id=order.id, order_update=order_update, db=db, user_id=user.id
        )

        # Verify deductions occurred
        deductions_found = False
        for inv_item in setup["inventory_items"]:
            db.refresh(inv_item)
            if inv_item.quantity < initial_quantities[inv_item.id]:
                deductions_found = True
                break

        assert deductions_found, "No inventory deductions found"
        assert result["data"].status == OrderStatus.IN_PROGRESS.value

    def test_concurrent_orders_with_factories(self, db: Session):
        """Test concurrent orders using factory data."""
        # Create limited inventory
        scarce_item = InventoryFactory(
            item_name="Scarce Resource", quantity=5.0, unit="piece"
        )

        # Create recipe that uses this item
        recipe = RecipeWithIngredientsFactory(
            ingredients=[{"inventory_item": scarce_item, "quantity": 3.0}]
        )

        # Create multiple orders for the same item
        orders = []
        user = UserFactory()

        for i in range(3):
            order = OrderWithItemsFactory(
                created_by=user, items=[{"menu_item": recipe.menu_item, "quantity": 1}]
            )
            orders.append(order)

        # Process orders
        successful = 0
        failed = 0

        for order in orders:
            try:
                update_order_service(
                    order_id=order.id,
                    order_update=OrderUpdate(status=OrderStatus.IN_PROGRESS),
                    db=db,
                    user_id=user.id,
                )
                successful += 1
            except Exception:
                failed += 1

        # Only one order should succeed (5 units / 3 per order)
        assert successful == 1
        assert failed == 2

        # Verify inventory depleted
        db.refresh(scarce_item)
        assert scarce_item.quantity == 2.0  # 5 - 3

    def test_recipe_with_random_ingredients(self, db: Session):
        """Test recipe processing with randomly generated ingredients."""
        # Let factory create random setup
        recipe = RecipeWithIngredientsFactory()

        # Verify recipe has ingredients
        assert len(recipe.ingredients) > 0

        # Create order
        order = OrderWithItemsFactory(
            items=[{"menu_item": recipe.menu_item, "quantity": 1}]
        )

        # Process and verify
        initial_quantities = {
            ing.inventory_item.id: ing.inventory_item.quantity
            for ing in recipe.ingredients
        }

        update_order_service(
            order_id=order.id,
            order_update=OrderUpdate(status=OrderStatus.IN_PROGRESS),
            db=db,
            user_id=order.created_by.id,
        )

        # Check deductions
        for ing in recipe.ingredients:
            db.refresh(ing.inventory_item)
            expected = initial_quantities[ing.inventory_item.id] - ing.quantity
            assert ing.inventory_item.quantity == pytest.approx(expected, rel=1e-3)
