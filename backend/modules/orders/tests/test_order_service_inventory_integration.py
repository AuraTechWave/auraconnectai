# backend/modules/orders/tests/test_order_service_inventory_integration.py

import pytest
from datetime import datetime
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock

from core.database import get_test_db
from core.models import User
from core.inventory_models import Inventory, InventoryAdjustment, AdjustmentType
from ..models.order_models import Order, OrderItem
from ..enums.order_enums import OrderStatus
from ..schemas.order_schemas import OrderUpdate
from ..services.order_service import update_order_service
from ..services.recipe_inventory_service import RecipeInventoryService
from ..config.inventory_config import InventoryDeductionConfig
from ...menu.models.menu_models import MenuItem, Category
from ...menu.models.recipe_models import Recipe, RecipeIngredient, RecipeSubRecipe


@pytest.fixture
def mock_config():
    """Mock inventory configuration."""
    config = MagicMock(spec=InventoryDeductionConfig)
    config.USE_RECIPE_BASED_INVENTORY_DEDUCTION = True
    config.DEDUCT_INVENTORY_ON_COMPLETION = False
    config.AUTO_REVERSE_ON_CANCELLATION = True
    config.ALLOW_NEGATIVE_INVENTORY = False
    config.LOW_STOCK_WARNING_THRESHOLD = 20.0
    config.SEND_LOW_STOCK_NOTIFICATIONS = True
    return config


@pytest.fixture
def setup_order_test_data(db: Session):
    """Set up test data for order service integration tests."""
    # Create user
    user = User(id=1, username="testuser", email="test@example.com", is_active=True)
    db.add(user)

    # Category
    category = Category(id=1, name="Main", is_active=True)
    db.add(category)

    # Inventory
    ingredients = [
        Inventory(
            id=1,
            item_name="Base",
            quantity=100.0,
            unit="unit",
            threshold=20.0,
            is_active=True,
        ),
        Inventory(
            id=2,
            item_name="Topping A",
            quantity=50.0,
            unit="unit",
            threshold=10.0,
            is_active=True,
        ),
        Inventory(
            id=3,
            item_name="Topping B",
            quantity=30.0,
            unit="unit",
            threshold=5.0,
            is_active=True,
        ),
    ]
    db.add_all(ingredients)

    # Menu items
    items = [
        MenuItem(id=1, name="Product A", price=15.0, category_id=1, is_active=True),
        MenuItem(id=2, name="Product B", price=20.0, category_id=1, is_active=True),
        MenuItem(id=3, name="Combo", price=30.0, category_id=1, is_active=True),
    ]
    db.add_all(items)

    # Recipes
    recipes = [
        Recipe(id=1, menu_item_id=1, name="Recipe A", status="active", created_by=1),
        Recipe(id=2, menu_item_id=2, name="Recipe B", status="active", created_by=1),
        Recipe(
            id=3, menu_item_id=3, name="Combo Recipe", status="active", created_by=1
        ),
    ]
    db.add_all(recipes)
    db.flush()

    # Recipe ingredients
    recipe_ingredients = [
        # Product A uses Base + Topping A
        RecipeIngredient(
            recipe_id=1, inventory_id=1, quantity=1.0, unit="unit", created_by=1
        ),
        RecipeIngredient(
            recipe_id=1, inventory_id=2, quantity=0.5, unit="unit", created_by=1
        ),
        # Product B uses Base + Topping B
        RecipeIngredient(
            recipe_id=2, inventory_id=1, quantity=1.0, unit="unit", created_by=1
        ),
        RecipeIngredient(
            recipe_id=2, inventory_id=3, quantity=0.3, unit="unit", created_by=1
        ),
        # Combo uses less base directly
        RecipeIngredient(
            recipe_id=3, inventory_id=1, quantity=0.5, unit="unit", created_by=1
        ),
    ]
    db.add_all(recipe_ingredients)

    # Combo includes sub-recipes (Product A + Product B)
    sub_recipes = [
        RecipeSubRecipe(
            parent_recipe_id=3, sub_recipe_id=1, quantity=1.0, created_by=1
        ),
        RecipeSubRecipe(
            parent_recipe_id=3, sub_recipe_id=2, quantity=1.0, created_by=1
        ),
    ]
    db.add_all(sub_recipes)

    db.commit()

    return {
        "user": user,
        "ingredients": ingredients,
        "items": items,
        "recipes": recipes,
    }


class TestOrderServiceInventoryIntegration:
    """Test the integration between order service and inventory deduction."""

    @patch("modules.orders.services.order_service.get_inventory_config")
    async def test_order_status_change_triggers_deduction(
        self, mock_get_config, mock_config, db: Session, setup_order_test_data
    ):
        """Test that changing order status to IN_PROGRESS triggers inventory deduction."""
        mock_get_config.return_value = mock_config

        user = setup_order_test_data["user"]

        # Create order
        order = Order(
            id=1,
            order_number="ORD-001",
            status=OrderStatus.PENDING,
            total_amount=15.0,
            created_by=user.id,
        )
        db.add(order)

        order_item = OrderItem(
            order_id=1, menu_item_id=1, quantity=2, price=15.0  # Product A
        )
        db.add(order_item)
        db.commit()

        # Get initial inventory
        initial_base = db.query(Inventory).filter(Inventory.id == 1).first().quantity
        initial_topping_a = (
            db.query(Inventory).filter(Inventory.id == 2).first().quantity
        )

        # Update status to IN_PROGRESS
        order_update = OrderUpdate(status=OrderStatus.IN_PROGRESS)
        result = await update_order_service(
            order_id=1, order_update=order_update, db=db, user_id=user.id
        )

        # Verify status changed
        assert result["data"].status == OrderStatus.IN_PROGRESS.value

        # Verify inventory was deducted
        db.refresh(db.query(Inventory).filter(Inventory.id == 1).first())
        db.refresh(db.query(Inventory).filter(Inventory.id == 2).first())

        final_base = db.query(Inventory).filter(Inventory.id == 1).first().quantity
        final_topping_a = db.query(Inventory).filter(Inventory.id == 2).first().quantity

        # Product A uses 1 base + 0.5 topping A, ordered 2
        assert final_base == initial_base - 2.0
        assert final_topping_a == initial_topping_a - 1.0

        # Verify adjustments created
        adjustments = (
            db.query(InventoryAdjustment)
            .filter(InventoryAdjustment.reference_type == "order")
            .all()
        )
        assert len(adjustments) == 2

    @patch("modules.orders.services.order_service.get_inventory_config")
    async def test_order_cancellation_reverses_inventory(
        self, mock_get_config, mock_config, db: Session, setup_order_test_data
    ):
        """Test that cancelling an order reverses inventory deductions."""
        mock_get_config.return_value = mock_config

        user = setup_order_test_data["user"]

        # Create and process order
        order = Order(
            id=2,
            order_number="ORD-002",
            status=OrderStatus.PENDING,
            total_amount=20.0,
            created_by=user.id,
        )
        db.add(order)

        order_item = OrderItem(
            order_id=2, menu_item_id=2, quantity=1, price=20.0  # Product B
        )
        db.add(order_item)
        db.commit()

        # Process order
        await update_order_service(
            2, OrderUpdate(status=OrderStatus.IN_PROGRESS), db, user.id
        )

        # Get quantities after deduction
        after_deduction_base = (
            db.query(Inventory).filter(Inventory.id == 1).first().quantity
        )
        after_deduction_topping_b = (
            db.query(Inventory).filter(Inventory.id == 3).first().quantity
        )

        # Cancel order
        await update_order_service(
            2, OrderUpdate(status=OrderStatus.CANCELLED), db, user.id
        )

        # Verify inventory restored
        db.refresh(db.query(Inventory).filter(Inventory.id == 1).first())
        db.refresh(db.query(Inventory).filter(Inventory.id == 3).first())

        final_base = db.query(Inventory).filter(Inventory.id == 1).first().quantity
        final_topping_b = db.query(Inventory).filter(Inventory.id == 3).first().quantity

        # Should be back to original (100 and 30)
        assert final_base == 100.0
        assert final_topping_b == 30.0

        # Verify reversal adjustments
        reversals = (
            db.query(InventoryAdjustment)
            .filter(InventoryAdjustment.adjustment_type == AdjustmentType.RETURN)
            .all()
        )
        assert len(reversals) == 2

    @patch("modules.orders.services.order_service.get_inventory_config")
    async def test_deduct_on_completion_mode(
        self, mock_get_config, db: Session, setup_order_test_data
    ):
        """Test inventory deduction on order completion instead of progress."""
        # Configure to deduct on completion
        config = MagicMock()
        config.USE_RECIPE_BASED_INVENTORY_DEDUCTION = True
        config.DEDUCT_INVENTORY_ON_COMPLETION = True
        config.AUTO_REVERSE_ON_CANCELLATION = True
        mock_get_config.return_value = config

        user = setup_order_test_data["user"]

        # Create order
        order = Order(
            id=3,
            order_number="ORD-003",
            status=OrderStatus.PENDING,
            total_amount=30.0,
            created_by=user.id,
        )
        db.add(order)

        order_item = OrderItem(
            order_id=3,
            menu_item_id=3,  # Combo (with sub-recipes)
            quantity=1,
            price=30.0,
        )
        db.add(order_item)
        db.commit()

        initial_base = db.query(Inventory).filter(Inventory.id == 1).first().quantity

        # Progress through statuses
        for status in [OrderStatus.IN_PROGRESS, OrderStatus.READY, OrderStatus.SERVED]:
            await update_order_service(3, OrderUpdate(status=status), db, user.id)

            # Verify NO deduction yet
            db.refresh(db.query(Inventory).filter(Inventory.id == 1).first())
            assert (
                db.query(Inventory).filter(Inventory.id == 1).first().quantity
                == initial_base
            )

        # Complete order - NOW it should deduct
        await update_order_service(
            3, OrderUpdate(status=OrderStatus.COMPLETED), db, user.id
        )

        # Verify deduction happened
        db.refresh(db.query(Inventory).filter(Inventory.id == 1).first())
        final_base = db.query(Inventory).filter(Inventory.id == 1).first().quantity

        # Combo uses: 0.5 base directly + 1 from Product A + 1 from Product B = 2.5 total
        assert final_base == initial_base - 2.5

    @patch("modules.orders.services.order_service.get_inventory_config")
    async def test_sub_recipe_deduction(
        self, mock_get_config, mock_config, db: Session, setup_order_test_data
    ):
        """Test that sub-recipes are properly handled in deduction."""
        mock_get_config.return_value = mock_config

        user = setup_order_test_data["user"]

        # Order combo item which has sub-recipes
        order = Order(
            id=4,
            order_number="ORD-004",
            status=OrderStatus.PENDING,
            total_amount=60.0,
            created_by=user.id,
        )
        db.add(order)

        order_item = OrderItem(
            order_id=4, menu_item_id=3, quantity=2, price=30.0  # Combo
        )
        db.add(order_item)
        db.commit()

        # Get initial quantities
        initial_base = db.query(Inventory).filter(Inventory.id == 1).first().quantity
        initial_topping_a = (
            db.query(Inventory).filter(Inventory.id == 2).first().quantity
        )
        initial_topping_b = (
            db.query(Inventory).filter(Inventory.id == 3).first().quantity
        )

        # Process order
        await update_order_service(
            4, OrderUpdate(status=OrderStatus.IN_PROGRESS), db, user.id
        )

        # Verify all ingredients from sub-recipes were deducted
        db.refresh(db.query(Inventory).filter(Inventory.id == 1).first())
        db.refresh(db.query(Inventory).filter(Inventory.id == 2).first())
        db.refresh(db.query(Inventory).filter(Inventory.id == 3).first())

        # For 2 combos:
        # Base: 2 * (0.5 direct + 1 from A + 1 from B) = 5.0
        # Topping A: 2 * 0.5 = 1.0
        # Topping B: 2 * 0.3 = 0.6

        assert (
            db.query(Inventory).filter(Inventory.id == 1).first().quantity
            == initial_base - 5.0
        )
        assert (
            db.query(Inventory).filter(Inventory.id == 2).first().quantity
            == initial_topping_a - 1.0
        )
        assert (
            db.query(Inventory).filter(Inventory.id == 3).first().quantity
            == initial_topping_b - 0.6
        )

    @patch("modules.orders.services.order_service.get_inventory_config")
    async def test_insufficient_inventory_blocks_order(
        self, mock_get_config, mock_config, db: Session, setup_order_test_data
    ):
        """Test that insufficient inventory prevents order processing."""
        mock_get_config.return_value = mock_config

        user = setup_order_test_data["user"]

        # Set base inventory very low
        base = db.query(Inventory).filter(Inventory.id == 1).first()
        base.quantity = 0.5  # Not enough for any product
        db.commit()

        # Try to process order
        order = Order(
            id=5,
            order_number="ORD-005",
            status=OrderStatus.PENDING,
            total_amount=15.0,
            created_by=user.id,
        )
        db.add(order)

        order_item = OrderItem(
            order_id=5, menu_item_id=1, quantity=1, price=15.0  # Needs 1 base
        )
        db.add(order_item)
        db.commit()

        # Should fail
        with pytest.raises(Exception) as exc_info:
            await update_order_service(
                5, OrderUpdate(status=OrderStatus.IN_PROGRESS), db, user.id
            )

        # Verify order status unchanged
        db.refresh(order)
        assert order.status == OrderStatus.PENDING

        # Verify no inventory was deducted
        db.refresh(base)
        assert base.quantity == 0.5

    @patch("modules.orders.services.order_service.get_inventory_config")
    @patch("modules.orders.services.order_service.logger")
    async def test_low_stock_warning_logged(
        self,
        mock_logger,
        mock_get_config,
        mock_config,
        db: Session,
        setup_order_test_data,
    ):
        """Test that low stock warnings are properly logged."""
        mock_get_config.return_value = mock_config

        user = setup_order_test_data["user"]

        # Set base inventory just above threshold
        base = db.query(Inventory).filter(Inventory.id == 1).first()
        base.quantity = 21.0  # Threshold is 20
        db.commit()

        # Create order that will trigger low stock
        order = Order(
            id=6,
            order_number="ORD-006",
            status=OrderStatus.PENDING,
            total_amount=15.0,
            created_by=user.id,
        )
        db.add(order)

        order_item = OrderItem(
            order_id=6,
            menu_item_id=1,  # Uses 1 base
            quantity=2,  # Will bring base to 19, below threshold
            price=15.0,
        )
        db.add(order_item)
        db.commit()

        # Process order
        await update_order_service(
            6, OrderUpdate(status=OrderStatus.IN_PROGRESS), db, user.id
        )

        # Verify warning was logged
        mock_logger.warning.assert_called()
        warning_call = mock_logger.warning.call_args[0][0]
        assert "Low stock alerts" in warning_call
        assert "order 6" in warning_call

    async def test_order_workflow_complete_flow(
        self, db: Session, setup_order_test_data
    ):
        """Test complete order workflow from creation to completion."""
        user = setup_order_test_data["user"]

        # Create order
        order = Order(
            id=7,
            order_number="ORD-007",
            status=OrderStatus.PENDING,
            total_amount=35.0,
            created_by=user.id,
        )
        db.add(order)

        # Multiple items
        order_items = [
            OrderItem(order_id=7, menu_item_id=1, quantity=1, price=15.0),
            OrderItem(order_id=7, menu_item_id=2, quantity=1, price=20.0),
        ]
        db.add_all(order_items)
        db.commit()

        # Track inventory through workflow
        initial_base = db.query(Inventory).filter(Inventory.id == 1).first().quantity

        # Progress through all statuses
        statuses = [
            OrderStatus.IN_PROGRESS,
            OrderStatus.READY,
            OrderStatus.SERVED,
            OrderStatus.COMPLETED,
        ]

        for status in statuses:
            await update_order_service(7, OrderUpdate(status=status), db, user.id)
            db.refresh(order)
            assert order.status == status.value

        # Verify final inventory state
        db.refresh(db.query(Inventory).filter(Inventory.id == 1).first())
        final_base = db.query(Inventory).filter(Inventory.id == 1).first().quantity

        # Both products use 1 base each
        assert final_base == initial_base - 2.0

        # Verify complete audit trail
        adjustments = (
            db.query(InventoryAdjustment)
            .filter(InventoryAdjustment.reference_id == "7")
            .all()
        )
        assert len(adjustments) > 0

        for adj in adjustments:
            assert adj.metadata is not None
            assert "order_items" in adj.metadata
            assert "recipes_used" in adj.metadata
