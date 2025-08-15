# backend/modules/orders/tests/test_recipe_inventory_service.py

import pytest
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List

from core.database import get_test_db
from core.inventory_models import Inventory, InventoryAdjustment, AdjustmentType
from ..models.order_models import Order, OrderItem
from ..enums.order_enums import OrderStatus
from ...menu.models.recipe_models import (
    Recipe,
    RecipeIngredient,
    RecipeSubRecipe,
    RecipeStatus,
)
from ...menu.models.menu_models import MenuItem, MenuItemStatus
from ..services.recipe_inventory_service import RecipeInventoryService


@pytest.fixture
def db_session():
    """Provide a test database session."""
    db = next(get_test_db())
    yield db
    db.rollback()
    db.close()


@pytest.fixture
def sample_inventory_items(db_session: Session):
    """Create sample inventory items for testing."""
    items = [
        Inventory(
            id=1,
            item_name="Tomatoes",
            quantity=50.0,
            unit="kg",
            threshold=10.0,
            cost_per_unit=2.5,
            is_active=True,
        ),
        Inventory(
            id=2,
            item_name="Cheese",
            quantity=20.0,
            unit="kg",
            threshold=5.0,
            cost_per_unit=8.0,
            is_active=True,
        ),
        Inventory(
            id=3,
            item_name="Pizza Dough",
            quantity=30.0,
            unit="piece",
            threshold=10.0,
            cost_per_unit=1.5,
            is_active=True,
        ),
        Inventory(
            id=4,
            item_name="Basil",
            quantity=5.0,
            unit="kg",
            threshold=1.0,
            cost_per_unit=15.0,
            is_active=True,
        ),
    ]

    for item in items:
        db_session.add(item)
    db_session.commit()

    return items


@pytest.fixture
def sample_menu_items(db_session: Session):
    """Create sample menu items."""
    items = [
        MenuItem(
            id=1,
            name="Margherita Pizza",
            price=12.99,
            status=MenuItemStatus.ACTIVE,
            is_active=True,
        ),
        MenuItem(
            id=2,
            name="Pepperoni Pizza",
            price=14.99,
            status=MenuItemStatus.ACTIVE,
            is_active=True,
        ),
        MenuItem(
            id=3,
            name="Pizza Sauce",
            price=3.99,
            status=MenuItemStatus.ACTIVE,
            is_active=True,
        ),
    ]

    for item in items:
        db_session.add(item)
    db_session.commit()

    return items


@pytest.fixture
def sample_recipes(db_session: Session, sample_menu_items, sample_inventory_items):
    """Create sample recipes with ingredients."""
    # Pizza sauce recipe (will be a sub-recipe)
    sauce_recipe = Recipe(
        id=1,
        menu_item_id=3,
        name="Pizza Sauce",
        status=RecipeStatus.ACTIVE,
        yield_quantity=1.0,
        yield_unit="portion",
        total_cost=0.0,
        created_by=1,
    )
    db_session.add(sauce_recipe)
    db_session.flush()

    # Sauce ingredients
    sauce_ingredients = [
        RecipeIngredient(
            recipe_id=1,
            inventory_id=1,  # Tomatoes
            quantity=0.2,
            unit="kg",
            created_by=1,
        ),
        RecipeIngredient(
            recipe_id=1, inventory_id=4, quantity=0.01, unit="kg", created_by=1  # Basil
        ),
    ]

    for ing in sauce_ingredients:
        db_session.add(ing)

    # Margherita pizza recipe
    margherita_recipe = Recipe(
        id=2,
        menu_item_id=1,
        name="Margherita Pizza",
        status=RecipeStatus.ACTIVE,
        yield_quantity=1.0,
        yield_unit="pizza",
        total_cost=0.0,
        created_by=1,
    )
    db_session.add(margherita_recipe)
    db_session.flush()

    # Margherita ingredients
    margherita_ingredients = [
        RecipeIngredient(
            recipe_id=2,
            inventory_id=3,  # Pizza Dough
            quantity=1.0,
            unit="piece",
            created_by=1,
        ),
        RecipeIngredient(
            recipe_id=2,
            inventory_id=2,  # Cheese
            quantity=0.15,
            unit="kg",
            created_by=1,
        ),
    ]

    for ing in margherita_ingredients:
        db_session.add(ing)

    # Add sauce as sub-recipe
    sub_recipe = RecipeSubRecipe(
        parent_recipe_id=2, sub_recipe_id=1, quantity=1.0, created_by=1
    )
    db_session.add(sub_recipe)

    db_session.commit()

    return [sauce_recipe, margherita_recipe]


@pytest.fixture
def sample_order(db_session: Session, sample_menu_items):
    """Create a sample order with items."""
    order = Order(
        id=1,
        order_number="ORD-001",
        status=OrderStatus.PENDING,
        total_amount=27.98,
        created_by=1,
    )
    db_session.add(order)
    db_session.flush()

    # Order items
    items = [
        OrderItem(
            order_id=1,
            menu_item_id=1,  # Margherita Pizza
            quantity=2,
            price=12.99,
            menu_item=sample_menu_items[0],
        )
    ]

    for item in items:
        db_session.add(item)

    order.order_items = items
    db_session.commit()

    return order


class TestRecipeInventoryService:
    """Test cases for recipe-based inventory deduction."""

    async def test_calculate_required_ingredients(
        self, db_session, sample_order, sample_recipes
    ):
        """Test calculation of required ingredients including sub-recipes."""
        service = RecipeInventoryService(db_session)

        # Calculate required ingredients
        required = await service._calculate_required_ingredients(
            sample_order.order_items
        )

        # Should include:
        # - 2 pizza dough (2 pizzas)
        # - 0.3 kg cheese (0.15 kg per pizza * 2)
        # - 0.4 kg tomatoes (0.2 kg per sauce * 2)
        # - 0.02 kg basil (0.01 kg per sauce * 2)

        assert len(required) == 4
        assert required[3]["quantity"] == 2.0  # Pizza dough
        assert required[2]["quantity"] == 0.3  # Cheese
        assert required[1]["quantity"] == 0.4  # Tomatoes
        assert required[4]["quantity"] == 0.02  # Basil

    async def test_successful_inventory_deduction(
        self, db_session, sample_order, sample_recipes, sample_inventory_items
    ):
        """Test successful inventory deduction for an order."""
        service = RecipeInventoryService(db_session)

        # Get initial quantities
        initial_dough = sample_inventory_items[2].quantity  # 30
        initial_cheese = sample_inventory_items[1].quantity  # 20
        initial_tomatoes = sample_inventory_items[0].quantity  # 50
        initial_basil = sample_inventory_items[3].quantity  # 5

        # Deduct inventory
        result = await service.deduct_inventory_for_order(
            order_items=sample_order.order_items,
            order_id=sample_order.id,
            user_id=1,
            deduction_type="order_completion",
        )

        # Verify result
        assert result["success"] is True
        assert len(result["deducted_items"]) == 4

        # Verify inventory quantities updated
        db_session.refresh(sample_inventory_items[2])  # Pizza dough
        assert sample_inventory_items[2].quantity == initial_dough - 2

        db_session.refresh(sample_inventory_items[1])  # Cheese
        assert sample_inventory_items[1].quantity == initial_cheese - 0.3

        db_session.refresh(sample_inventory_items[0])  # Tomatoes
        assert sample_inventory_items[0].quantity == initial_tomatoes - 0.4

        db_session.refresh(sample_inventory_items[3])  # Basil
        assert sample_inventory_items[3].quantity == initial_basil - 0.02

        # Verify adjustments created
        adjustments = (
            db_session.query(InventoryAdjustment)
            .filter(InventoryAdjustment.reference_id == str(sample_order.id))
            .all()
        )

        assert len(adjustments) == 4
        for adj in adjustments:
            assert adj.adjustment_type == AdjustmentType.CONSUMPTION
            assert adj.reference_type == "order"
            assert adj.quantity_change < 0  # Negative for consumption

    async def test_insufficient_inventory(
        self, db_session, sample_order, sample_recipes, sample_inventory_items
    ):
        """Test handling of insufficient inventory."""
        service = RecipeInventoryService(db_session)

        # Set cheese quantity too low
        sample_inventory_items[1].quantity = 0.1  # Need 0.3 kg
        db_session.commit()

        # Try to deduct inventory
        with pytest.raises(HTTPException) as exc_info:
            await service.deduct_inventory_for_order(
                order_items=sample_order.order_items,
                order_id=sample_order.id,
                user_id=1,
            )

        # Verify error details
        assert exc_info.value.status_code == 400
        assert "Insufficient inventory" in exc_info.value.detail["message"]
        assert len(exc_info.value.detail["items"]) > 0

        # Verify no changes were made
        db_session.refresh(sample_inventory_items[0])
        assert sample_inventory_items[0].quantity == 50.0  # Unchanged

    async def test_low_stock_alerts(
        self, db_session, sample_order, sample_recipes, sample_inventory_items
    ):
        """Test low stock alert generation."""
        service = RecipeInventoryService(db_session)

        # Set basil quantity close to threshold
        sample_inventory_items[3].quantity = 1.02  # Will be 1.0 after deduction
        sample_inventory_items[3].threshold = 1.0
        db_session.commit()

        # Deduct inventory
        result = await service.deduct_inventory_for_order(
            order_items=sample_order.order_items, order_id=sample_order.id, user_id=1
        )

        # Verify low stock alert
        assert len(result["low_stock_alerts"]) == 1
        alert = result["low_stock_alerts"][0]
        assert alert["item_name"] == "Basil"
        assert alert["current_quantity"] == 1.0
        assert alert["threshold"] == 1.0

    async def test_inventory_reversal(
        self, db_session, sample_order, sample_recipes, sample_inventory_items
    ):
        """Test reversing inventory deductions."""
        service = RecipeInventoryService(db_session)

        # First, deduct inventory
        await service.deduct_inventory_for_order(
            order_items=sample_order.order_items, order_id=sample_order.id, user_id=1
        )

        # Get quantities after deduction
        db_session.refresh(sample_inventory_items[2])
        quantity_after_deduction = sample_inventory_items[2].quantity

        # Reverse the deduction
        result = await service.reverse_inventory_deduction(
            order_id=sample_order.id, user_id=1, reason="Order cancelled"
        )

        # Verify reversal
        assert result["success"] is True
        assert len(result["reversed_items"]) == 4

        # Verify quantities restored
        db_session.refresh(sample_inventory_items[2])
        assert sample_inventory_items[2].quantity == 30.0  # Original quantity

        # Verify reversal adjustments created
        reversals = (
            db_session.query(InventoryAdjustment)
            .filter(
                InventoryAdjustment.reference_type == "order_reversal",
                InventoryAdjustment.reference_id == str(sample_order.id),
            )
            .all()
        )

        assert len(reversals) == 4
        for rev in reversals:
            assert rev.adjustment_type == AdjustmentType.RETURN
            assert rev.quantity_change > 0  # Positive for returns

    async def test_partial_fulfillment(
        self, db_session, sample_recipes, sample_inventory_items
    ):
        """Test handling partial order fulfillment."""
        service = RecipeInventoryService(db_session)

        # Partial fulfillment data (1 pizza instead of 2)
        partial_items = [{"menu_item_id": 1, "fulfilled_quantity": 1}]

        # Process partial fulfillment
        result = await service.handle_partial_fulfillment(
            order_items=partial_items, order_id=1, user_id=1
        )

        # Verify only half the ingredients were deducted
        assert result["success"] is True
        db_session.refresh(sample_inventory_items[2])  # Pizza dough
        assert sample_inventory_items[2].quantity == 29.0  # 30 - 1

    async def test_items_without_recipes(self, db_session, sample_menu_items):
        """Test handling of menu items without recipes."""
        service = RecipeInventoryService(db_session)

        # Create order with item that has no recipe
        order = Order(id=2, order_number="ORD-002", status=OrderStatus.PENDING)
        db_session.add(order)

        order_item = OrderItem(
            order_id=2,
            menu_item_id=2,  # Pepperoni Pizza (no recipe)
            quantity=1,
            price=14.99,
            menu_item=sample_menu_items[1],
        )
        db_session.add(order_item)
        db_session.commit()

        order.order_items = [order_item]

        # Try to deduct inventory
        result = await service.deduct_inventory_for_order(
            order_items=order.order_items, order_id=order.id, user_id=1
        )

        # Should succeed but note items without recipes
        assert result["success"] is True
        assert len(result["items_without_recipes"]) == 1
        assert result["items_without_recipes"][0]["menu_item_id"] == 2

    async def test_inventory_impact_preview(
        self, db_session, sample_order, sample_recipes, sample_inventory_items
    ):
        """Test previewing inventory impact without making changes."""
        service = RecipeInventoryService(db_session)

        # Get preview
        preview = await service.get_inventory_impact_preview(
            order_items=sample_order.order_items
        )

        # Verify preview data
        assert preview["can_fulfill"] is True
        assert len(preview["impact_preview"]) == 4

        # Check one item in detail
        dough_preview = next(
            item
            for item in preview["impact_preview"]
            if item["item_name"] == "Pizza Dough"
        )
        assert dough_preview["current_quantity"] == 30.0
        assert dough_preview["required_quantity"] == 2.0
        assert dough_preview["new_quantity"] == 28.0
        assert dough_preview["sufficient_stock"] is True

        # Verify no actual changes were made
        db_session.refresh(sample_inventory_items[2])
        assert sample_inventory_items[2].quantity == 30.0  # Unchanged

    async def test_circular_recipe_prevention(self, db_session, sample_recipes):
        """Test that circular recipe references are handled."""
        service = RecipeInventoryService(db_session)

        # This should be prevented at recipe creation, but test the service handles it
        visited_recipes = set()

        # Simulate processing a recipe
        await service._add_recipe_ingredients(
            recipe_id=2,
            quantity_multiplier=1.0,
            required_ingredients={},
            visited_recipes=visited_recipes,
        )

        # Verify the recipe was marked as visited
        assert 2 in visited_recipes

        # Try to process it again (simulating circular reference)
        await service._add_recipe_ingredients(
            recipe_id=2,
            quantity_multiplier=1.0,
            required_ingredients={},
            visited_recipes=visited_recipes,
        )

        # Should return early without processing
        assert len(visited_recipes) == 2  # Only recipes 2 and 1 (sub-recipe)
