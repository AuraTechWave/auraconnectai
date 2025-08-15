# backend/modules/orders/tests/test_inventory_negative_scenarios.py

import pytest
import asyncio
import threading
import time
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import OperationalError, DBAPIError
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from core.database import Base
from core.models import User
from core.inventory_models import Inventory, InventoryAdjustment
from ..models.order_models import Order, OrderItem
from ...menu.models.recipe_models import Recipe, RecipeIngredient
from ...menu.models.menu_models import MenuItem
from ..services.recipe_inventory_service import RecipeInventoryService
from tests.factories import (
    UserFactory,
    InventoryFactory,
    MenuItemFactory,
    RecipeFactory,
    RecipeIngredientFactory,
    OrderFactory,
    OrderItemFactory,
)


@pytest.mark.concurrent
@pytest.mark.db
class TestNegativeScenarios:
    """Test negative scenarios and edge cases for inventory deduction."""

    @pytest.fixture
    def db_engine(self):
        """Create a test database engine."""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        return engine

    @pytest.mark.slow
    async def test_circular_dependency_deadlock(self, db_engine):
        """Test potential deadlock with circular recipe dependencies."""
        # Create circular dependency scenario
        with db_engine.connect() as conn:
            session = Session(bind=conn)

            # Create test user
            user = UserFactory(_session=session)

            # Create inventory items
            items = []
            for i in range(4):
                item = InventoryFactory(
                    _session=session,
                    item_name=f"Item {i+1}",
                    quantity=100.0,
                    unit="unit",
                    created_by=user.id,
                )
                items.append(item)

            # Create menu items
            menu_items = []
            for i in range(3):
                menu_item = MenuItemFactory(
                    _session=session,
                    name=f"Product {i+1}",
                    price=10.0,
                    created_by=user.id,
                )
                menu_items.append(menu_item)

            # Create recipes with potential circular access patterns
            recipes = []
            for i, menu_item in enumerate(menu_items):
                recipe = RecipeFactory(
                    _session=session,
                    menu_item=menu_item,
                    name=f"Recipe {i+1}",
                    status="active",
                    created_by=user.id,
                )
                recipes.append(recipe)

            # Create circular ingredient dependencies
            # Recipe 1: Items 1->2->3->4
            # Recipe 2: Items 4->3->2->1
            # Recipe 3: Items 2->4->1->3
            dependencies = [
                (recipes[0], [items[0], items[1], items[2], items[3]]),
                (recipes[1], [items[3], items[2], items[1], items[0]]),
                (recipes[2], [items[1], items[3], items[0], items[2]]),
            ]

            for recipe, item_order in dependencies:
                for idx, item in enumerate(item_order):
                    RecipeIngredientFactory(
                        _session=session,
                        recipe=recipe,
                        inventory_item=item,
                        quantity=1.0,
                        unit="unit",
                        display_order=idx,
                        created_by=user.id,
                    )

            session.commit()
            session.close()

        # Simulate concurrent orders that could deadlock
        deadlock_detected = False
        completed_orders = []
        failed_orders = []

        async def process_order(order_data):
            try:
                with db_engine.connect() as conn:
                    session = Session(bind=conn)
                    service = RecipeInventoryService(session)

                    order = OrderFactory(
                        _session=session,
                        order_number=f"DL-{order_data['order_num']:03d}",
                        status="PENDING",
                        created_by=order_data["user"],
                    )

                    order_item = OrderItemFactory(
                        _session=session,
                        order=order,
                        menu_item_id=order_data["menu_item_id"],
                        quantity=1,
                        price=10.0,
                    )
                    session.commit()

                    # Add variable random delay to increase chance of deadlock
                    import random

                    delay = random.uniform(0.001, 0.01) * (order_data["order_num"] % 3)
                    await asyncio.sleep(delay)

                    result = await service.deduct_inventory_for_order(
                        order_items=[order_item],
                        order_id=order.id,
                        user_id=order_data["user"].id,
                    )

                    completed_orders.append(order.id)
                    session.close()

            except (OperationalError, DBAPIError) as e:
                if (
                    "deadlock" in str(e).lower()
                    or "database is locked" in str(e).lower()
                ):
                    nonlocal deadlock_detected
                    deadlock_detected = True
                failed_orders.append(order_data["order_num"])
            except Exception as e:
                failed_orders.append(order_data["order_num"])

        # Get menu item IDs from the database
        with db_engine.connect() as conn:
            session = Session(bind=conn)
            menu_item_ids = [item.id for item in session.query(MenuItem).limit(3).all()]
            test_user = session.query(User).first()
            session.close()

        # Create tasks that access items in different orders
        tasks = []
        for i in range(10):
            order_data = {
                "order_num": i + 1,
                "menu_item_id": menu_item_ids[
                    i % len(menu_item_ids)
                ],  # Rotate through recipes
                "user": test_user,
            }
            tasks.append(process_order(order_data))

        # Run with timeout to prevent infinite deadlock
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), timeout=5.0
            )
        except asyncio.TimeoutError:
            deadlock_detected = True

        # Verify no actual deadlock occurred (SQLite handles this well)
        assert not deadlock_detected, "Deadlock detected in inventory operations"
        assert len(completed_orders) > 0, "No orders completed successfully"

    @pytest.mark.slow
    async def test_race_condition_double_deduction(self, db_engine):
        """Test protection against double deduction in race conditions."""
        # Setup test data
        with db_engine.connect() as conn:
            session = Session(bind=conn)

            # Create test user
            user = UserFactory(_session=session)

            # Create limited inventory
            inventory = InventoryFactory(
                _session=session,
                item_name="Limited Item",
                quantity=10.0,
                unit="unit",
                created_by=user.id,
            )

            # Create menu item and recipe
            menu_item = MenuItemFactory(
                _session=session, name="Product", price=10.0, created_by=user.id
            )

            recipe = RecipeFactory(
                _session=session,
                menu_item=menu_item,
                name="Recipe",
                status="active",
                created_by=user.id,
            )

            ingredient = RecipeIngredientFactory(
                _session=session,
                recipe=recipe,
                inventory_item=inventory,
                quantity=5.0,
                unit="unit",
                created_by=user.id,
            )

            session.commit()
            # Store IDs for later use
            order_id = None
            menu_item_id = menu_item.id
            inventory_id = inventory.id
            user_id = user.id
            session.close()

        # Create order that will be processed twice
        double_deduction_occurred = False

        async def attempt_deduction(attempt_num):
            nonlocal double_deduction_occurred
            nonlocal order_id

            with db_engine.connect() as conn:
                session = Session(bind=conn)
                service = RecipeInventoryService(session)

                try:
                    # Both attempts use the same order
                    if attempt_num == 1:
                        order = OrderFactory(
                            _session=session,
                            order_number="DBL-001",
                            status="PENDING",
                            created_by_id=user_id,
                        )
                        order_id = order.id

                        order_item = OrderItemFactory(
                            _session=session,
                            order=order,
                            menu_item_id=menu_item_id,
                            quantity=1,
                            price=10.0,
                        )
                        session.commit()
                    else:
                        # Second attempt reuses existing order
                        order_item = (
                            session.query(OrderItem)
                            .filter(OrderItem.order_id == order_id)
                            .first()
                        )

                    result = await service.deduct_inventory_for_order(
                        order_items=[order_item], order_id=order_id, user_id=user_id
                    )

                    # Check if we deducted twice
                    adjustments = (
                        session.query(InventoryAdjustment)
                        .filter(InventoryAdjustment.reference_id == str(order_id))
                        .all()
                    )

                    if len(adjustments) > 1:
                        double_deduction_occurred = True

                    session.close()
                    return True

                except Exception:
                    session.close()
                    return False

        # Run two deduction attempts concurrently
        results = await asyncio.gather(
            attempt_deduction(1), attempt_deduction(2), return_exceptions=True
        )

        # Verify protection against double deduction
        assert not double_deduction_occurred, "Double deduction occurred"

        # Check final inventory state
        with db_engine.connect() as conn:
            session = Session(bind=conn)
            final_inventory = (
                session.query(Inventory).filter(Inventory.id == inventory_id).first()
            )

            # Should only be deducted once
            assert final_inventory.quantity == 5.0  # 10 - 5

            # Should only have one adjustment
            adjustments = session.query(InventoryAdjustment).all()
            assert len(adjustments) == 1

            session.close()

    async def test_transaction_rollback_on_partial_failure(self, db_engine):
        """Test that partial failures roll back entire transaction using nested transactions."""
        with db_engine.connect() as conn:
            session = Session(bind=conn)

            # Create test user
            user = UserFactory(_session=session)

            # Create inventory items - one with sufficient stock, one without
            sufficient_item = InventoryFactory(
                _session=session,
                item_name="Sufficient",
                quantity=100.0,
                unit="unit",
                created_by=user.id,
            )
            insufficient_item = InventoryFactory(
                _session=session,
                item_name="Insufficient",
                quantity=0.5,
                unit="unit",
                created_by=user.id,
            )

            # Create menu item with recipe requiring both
            menu_item = MenuItemFactory(
                _session=session, name="Combo", price=20.0, created_by=user.id
            )

            recipe = RecipeFactory(
                _session=session,
                menu_item=menu_item,
                name="Combo Recipe",
                status="active",
                created_by=user.id,
            )

            # Add ingredients
            RecipeIngredientFactory(
                _session=session,
                recipe=recipe,
                inventory_item=sufficient_item,
                quantity=10.0,
                unit="unit",
                created_by=user.id,
            )
            RecipeIngredientFactory(
                _session=session,
                recipe=recipe,
                inventory_item=insufficient_item,
                quantity=5.0,
                unit="unit",
                created_by=user.id,
            )

            session.commit()

            # Try to process order with nested transaction
            service = RecipeInventoryService(session)

            order = OrderFactory(
                _session=session,
                order_number="FAIL-001",
                status="PENDING",
                created_by=user,
            )

            order_item = OrderItemFactory(
                _session=session,
                order=order,
                menu_item=menu_item,
                quantity=1,
                price=20.0,
            )
            session.commit()

            # Store IDs for verification
            sufficient_item_id = sufficient_item.id

            # Use nested transaction to ensure proper rollback
            with session.begin_nested() as savepoint:
                try:
                    # Should fail due to insufficient stock of item 2
                    await service.deduct_inventory_for_order(
                        order_items=[order_item], order_id=order.id, user_id=user.id
                    )
                    # If we get here, test should fail
                    pytest.fail("Expected exception due to insufficient stock")
                except Exception as e:
                    # Expected failure - rollback to savepoint
                    savepoint.rollback()
                    # Verify the exception was about insufficient inventory
                    assert "insufficient" in str(e).lower()

            # Verify NO inventory was deducted (transaction rolled back)
            sufficient_check = (
                session.query(Inventory)
                .filter(Inventory.id == sufficient_item_id)
                .first()
            )
            assert sufficient_check.quantity == 100.0  # Unchanged

            # Verify NO adjustments were created
            adjustments = session.query(InventoryAdjustment).all()
            assert len(adjustments) == 0

            session.close()

    @pytest.mark.stress
    @pytest.mark.slow
    async def test_high_concurrency_stress(self, db_engine):
        """Stress test with high concurrency to find edge cases."""
        # Setup inventory with moderate stock
        with db_engine.connect() as conn:
            session = Session(bind=conn)

            # Create test user
            user = UserFactory(_session=session)

            inventory = InventoryFactory(
                _session=session,
                item_name="Stress Test Item",
                quantity=1000.0,
                unit="unit",
                created_by=user.id,
            )

            menu_item = MenuItemFactory(
                _session=session, name="Stress Product", price=5.0, created_by=user.id
            )

            recipe = RecipeFactory(
                _session=session,
                menu_item=menu_item,
                name="Stress Recipe",
                status="active",
                created_by=user.id,
            )

            ingredient = RecipeIngredientFactory(
                _session=session,
                recipe=recipe,
                inventory_item=inventory,
                quantity=1.0,
                unit="unit",
                created_by=user.id,
            )

            session.commit()
            # Store IDs for later use
            inventory_id = inventory.id
            menu_item_id = menu_item.id
            user_id = user.id
            session.close()

        # Run many concurrent orders
        num_orders = 50
        successful_orders = []
        failed_orders = []

        async def stress_order(order_num):
            try:
                with db_engine.connect() as conn:
                    session = Session(bind=conn)
                    service = RecipeInventoryService(session)

                    order = OrderFactory(
                        _session=session,
                        order_number=f"STRESS-{order_num:04d}",
                        status="PENDING",
                        created_by_id=user_id,
                    )

                    order_item = OrderItemFactory(
                        _session=session,
                        order=order,
                        menu_item_id=menu_item_id,
                        quantity=1,
                        price=5.0,
                    )
                    session.commit()

                    await service.deduct_inventory_for_order(
                        order_items=[order_item], order_id=order.id, user_id=user_id
                    )

                    successful_orders.append(order.id)
                    session.close()

            except Exception:
                failed_orders.append(order_num)

        # Create all tasks
        tasks = [stress_order(i + 1) for i in range(num_orders)]

        # Run concurrently
        await asyncio.gather(*tasks, return_exceptions=True)

        # Verify results
        with db_engine.connect() as conn:
            session = Session(bind=conn)

            # Check final inventory
            final_inventory = (
                session.query(Inventory).filter(Inventory.id == inventory_id).first()
            )

            # Total deducted should match successful orders
            total_deducted = 1000.0 - final_inventory.quantity
            assert total_deducted == len(successful_orders)

            # Verify all adjustments
            adjustments = session.query(InventoryAdjustment).all()
            assert len(adjustments) == len(successful_orders)

            # Verify no negative inventory
            assert final_inventory.quantity >= 0

            session.close()

        print(
            f"Stress test completed: {len(successful_orders)} successful, {len(failed_orders)} failed"
        )
