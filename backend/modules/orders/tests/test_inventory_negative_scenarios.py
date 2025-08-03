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
from core.inventory_models import Inventory, InventoryAdjustment
from ..models.order_models import Order, OrderItem
from ...menu.models.recipe_models import Recipe, RecipeIngredient
from ...menu.models.menu_models import MenuItem
from ..services.recipe_inventory_service import RecipeInventoryService


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
            
            # Create inventory items
            items = []
            for i in range(1, 5):
                item = Inventory(
                    id=i,
                    item_name=f"Item {i}",
                    quantity=100.0,
                    unit="unit",
                    is_active=True
                )
                items.append(item)
            session.add_all(items)
            
            # Create menu items
            menu_items = []
            for i in range(1, 4):
                menu_item = MenuItem(
                    id=i,
                    name=f"Product {i}",
                    price=10.0,
                    is_active=True
                )
                menu_items.append(menu_item)
            session.add_all(menu_items)
            
            # Create recipes with potential circular access patterns
            recipes = []
            for i in range(1, 4):
                recipe = Recipe(
                    id=i,
                    menu_item_id=i,
                    name=f"Recipe {i}",
                    status="active",
                    created_by=1
                )
                recipes.append(recipe)
            session.add_all(recipes)
            session.flush()
            
            # Create circular ingredient dependencies
            # Recipe 1: Items 1->2->3->4
            # Recipe 2: Items 4->3->2->1
            # Recipe 3: Items 2->4->1->3
            dependencies = [
                (1, [1, 2, 3, 4]),
                (2, [4, 3, 2, 1]),
                (3, [2, 4, 1, 3])
            ]
            
            for recipe_id, item_order in dependencies:
                for idx, item_id in enumerate(item_order):
                    ingredient = RecipeIngredient(
                        recipe_id=recipe_id,
                        inventory_id=item_id,
                        quantity=1.0,
                        unit="unit",
                        display_order=idx,
                        created_by=1
                    )
                    session.add(ingredient)
            
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
                    
                    order = Order(
                        id=order_data["id"],
                        order_number=f"DL-{order_data['id']:03d}",
                        status="PENDING"
                    )
                    session.add(order)
                    
                    order_item = OrderItem(
                        order_id=order_data["id"],
                        menu_item_id=order_data["menu_item_id"],
                        quantity=1,
                        price=10.0
                    )
                    session.add(order_item)
                    session.commit()
                    
                    # Add random delay to increase chance of deadlock
                    await asyncio.sleep(0.001 * order_data["id"])
                    
                    result = await service.deduct_inventory_for_order(
                        order_items=[order_item],
                        order_id=order_data["id"],
                        user_id=1
                    )
                    
                    completed_orders.append(order_data["id"])
                    session.close()
                    
            except (OperationalError, DBAPIError) as e:
                if "deadlock" in str(e).lower() or "database is locked" in str(e).lower():
                    nonlocal deadlock_detected
                    deadlock_detected = True
                failed_orders.append(order_data["id"])
            except Exception as e:
                failed_orders.append(order_data["id"])
        
        # Create tasks that access items in different orders
        tasks = []
        for i in range(10):
            order_data = {
                "id": i + 1,
                "menu_item_id": (i % 3) + 1  # Rotate through recipes
            }
            tasks.append(process_order(order_data))
        
        # Run with timeout to prevent infinite deadlock
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=5.0
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
            
            # Create limited inventory
            inventory = Inventory(
                id=1,
                item_name="Limited Item",
                quantity=10.0,
                unit="unit",
                is_active=True
            )
            session.add(inventory)
            
            # Create menu item and recipe
            menu_item = MenuItem(id=1, name="Product", price=10.0, is_active=True)
            session.add(menu_item)
            
            recipe = Recipe(
                id=1,
                menu_item_id=1,
                name="Recipe",
                status="active",
                created_by=1
            )
            session.add(recipe)
            session.flush()
            
            ingredient = RecipeIngredient(
                recipe_id=1,
                inventory_id=1,
                quantity=5.0,
                unit="unit",
                created_by=1
            )
            session.add(ingredient)
            
            session.commit()
            session.close()
        
        # Create order that will be processed twice
        order_id = 1
        double_deduction_occurred = False
        
        async def attempt_deduction(attempt_num):
            nonlocal double_deduction_occurred
            
            with db_engine.connect() as conn:
                session = Session(bind=conn)
                service = RecipeInventoryService(session)
                
                try:
                    # Both attempts use the same order
                    if attempt_num == 1:
                        order = Order(id=order_id, order_number="DBL-001", status="PENDING")
                        session.add(order)
                        
                        order_item = OrderItem(
                            order_id=order_id,
                            menu_item_id=1,
                            quantity=1,
                            price=10.0
                        )
                        session.add(order_item)
                        session.commit()
                    else:
                        # Second attempt reuses existing order
                        order_item = session.query(OrderItem).filter(
                            OrderItem.order_id == order_id
                        ).first()
                    
                    result = await service.deduct_inventory_for_order(
                        order_items=[order_item],
                        order_id=order_id,
                        user_id=1
                    )
                    
                    # Check if we deducted twice
                    adjustments = session.query(InventoryAdjustment).filter(
                        InventoryAdjustment.reference_id == str(order_id)
                    ).all()
                    
                    if len(adjustments) > 1:
                        double_deduction_occurred = True
                    
                    session.close()
                    return True
                    
                except Exception:
                    session.close()
                    return False
        
        # Run two deduction attempts concurrently
        results = await asyncio.gather(
            attempt_deduction(1),
            attempt_deduction(2),
            return_exceptions=True
        )
        
        # Verify protection against double deduction
        assert not double_deduction_occurred, "Double deduction occurred"
        
        # Check final inventory state
        with db_engine.connect() as conn:
            session = Session(bind=conn)
            final_inventory = session.query(Inventory).filter(Inventory.id == 1).first()
            
            # Should only be deducted once
            assert final_inventory.quantity == 5.0  # 10 - 5
            
            # Should only have one adjustment
            adjustments = session.query(InventoryAdjustment).all()
            assert len(adjustments) == 1
            
            session.close()
    
    async def test_transaction_rollback_on_partial_failure(self, db_engine):
        """Test that partial failures roll back entire transaction."""
        with db_engine.connect() as conn:
            session = Session(bind=conn)
            
            # Create inventory items - one with sufficient stock, one without
            items = [
                Inventory(id=1, item_name="Sufficient", quantity=100.0, unit="unit", is_active=True),
                Inventory(id=2, item_name="Insufficient", quantity=0.5, unit="unit", is_active=True),
            ]
            session.add_all(items)
            
            # Create menu item with recipe requiring both
            menu_item = MenuItem(id=1, name="Combo", price=20.0, is_active=True)
            session.add(menu_item)
            
            recipe = Recipe(
                id=1,
                menu_item_id=1,
                name="Combo Recipe",
                status="active",
                created_by=1
            )
            session.add(recipe)
            session.flush()
            
            # Add ingredients
            ingredients = [
                RecipeIngredient(recipe_id=1, inventory_id=1, quantity=10.0, unit="unit", created_by=1),
                RecipeIngredient(recipe_id=1, inventory_id=2, quantity=5.0, unit="unit", created_by=1),
            ]
            session.add_all(ingredients)
            session.commit()
            
            # Try to process order
            service = RecipeInventoryService(session)
            
            order = Order(id=1, order_number="FAIL-001", status="PENDING")
            session.add(order)
            
            order_item = OrderItem(order_id=1, menu_item_id=1, quantity=1, price=20.0)
            session.add(order_item)
            session.commit()
            
            # Should fail due to insufficient stock of item 2
            with pytest.raises(Exception):
                await service.deduct_inventory_for_order(
                    order_items=[order_item],
                    order_id=1,
                    user_id=1
                )
            
            # Verify NO inventory was deducted (transaction rolled back)
            session.rollback()
            sufficient_item = session.query(Inventory).filter(Inventory.id == 1).first()
            assert sufficient_item.quantity == 100.0  # Unchanged
            
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
            
            inventory = Inventory(
                id=1,
                item_name="Stress Test Item",
                quantity=1000.0,
                unit="unit",
                is_active=True
            )
            session.add(inventory)
            
            menu_item = MenuItem(id=1, name="Stress Product", price=5.0, is_active=True)
            session.add(menu_item)
            
            recipe = Recipe(id=1, menu_item_id=1, name="Stress Recipe", status="active", created_by=1)
            session.add(recipe)
            session.flush()
            
            ingredient = RecipeIngredient(
                recipe_id=1,
                inventory_id=1,
                quantity=1.0,
                unit="unit",
                created_by=1
            )
            session.add(ingredient)
            
            session.commit()
            session.close()
        
        # Run many concurrent orders
        num_orders = 50
        successful_orders = []
        failed_orders = []
        
        async def stress_order(order_id):
            try:
                with db_engine.connect() as conn:
                    session = Session(bind=conn)
                    service = RecipeInventoryService(session)
                    
                    order = Order(
                        id=order_id,
                        order_number=f"STRESS-{order_id:04d}",
                        status="PENDING"
                    )
                    session.add(order)
                    
                    order_item = OrderItem(
                        order_id=order_id,
                        menu_item_id=1,
                        quantity=1,
                        price=5.0
                    )
                    session.add(order_item)
                    session.commit()
                    
                    await service.deduct_inventory_for_order(
                        order_items=[order_item],
                        order_id=order_id,
                        user_id=1
                    )
                    
                    successful_orders.append(order_id)
                    session.close()
                    
            except Exception:
                failed_orders.append(order_id)
        
        # Create all tasks
        tasks = [stress_order(i + 1) for i in range(num_orders)]
        
        # Run concurrently
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify results
        with db_engine.connect() as conn:
            session = Session(bind=conn)
            
            # Check final inventory
            final_inventory = session.query(Inventory).filter(Inventory.id == 1).first()
            
            # Total deducted should match successful orders
            total_deducted = 1000.0 - final_inventory.quantity
            assert total_deducted == len(successful_orders)
            
            # Verify all adjustments
            adjustments = session.query(InventoryAdjustment).all()
            assert len(adjustments) == len(successful_orders)
            
            # Verify no negative inventory
            assert final_inventory.quantity >= 0
            
            session.close()
        
        print(f"Stress test completed: {len(successful_orders)} successful, {len(failed_orders)} failed")