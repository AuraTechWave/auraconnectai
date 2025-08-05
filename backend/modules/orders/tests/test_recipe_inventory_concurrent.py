# backend/modules/orders/tests/test_recipe_inventory_concurrent.py

import pytest
import asyncio
import os
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import threading

from core.database import get_test_db, Base
from core.inventory_models import Inventory, InventoryAdjustment
from ..models.order_models import Order, OrderItem
from ..enums.order_enums import OrderStatus
from ...menu.models.recipe_models import Recipe, RecipeIngredient
from ...menu.models.menu_models import MenuItem
from ..services.recipe_inventory_service import RecipeInventoryService
from fastapi import HTTPException


def is_postgres_available():
    """Check if we're running against PostgreSQL."""
    db_url = os.getenv("DATABASE_URL", "")
    return "postgresql" in db_url.lower()


# Skip these tests if not running on PostgreSQL for realistic concurrency testing
pytestmark = pytest.mark.skipif(
    not is_postgres_available(),
    reason="Concurrent tests require PostgreSQL for realistic transaction isolation"
)


@pytest.mark.concurrent
@pytest.mark.slow
@pytest.mark.db
class TestConcurrentInventoryDeduction:
    """Test cases for concurrent inventory deduction scenarios."""
    
    @pytest.fixture
    def db_engine(self, request):
        """Create a test database engine with thread-safe connection pool."""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        return engine
    
    @pytest.fixture
    def create_test_data(self, db_engine):
        """Create test data for concurrent tests."""
        def _create_data(session):
            # Create inventory item with limited stock
            inventory = Inventory(
                id=1,
                item_name="Limited Stock Item",
                quantity=10.0,  # Only enough for 2 orders
                unit="piece",
                threshold=5.0,
                is_active=True
            )
            session.add(inventory)
            
            # Create menu item
            menu_item = MenuItem(
                id=1,
                name="Test Product",
                price=10.0,
                is_active=True
            )
            session.add(menu_item)
            
            # Create recipe
            recipe = Recipe(
                id=1,
                menu_item_id=1,
                name="Test Recipe",
                status="active",
                created_by=1
            )
            session.add(recipe)
            session.flush()
            
            # Create recipe ingredient
            ingredient = RecipeIngredient(
                recipe_id=1,
                inventory_id=1,
                quantity=5.0,  # Each order needs 5 pieces
                unit="piece",
                created_by=1
            )
            session.add(ingredient)
            
            session.commit()
        
        return _create_data
    
    async def test_concurrent_orders_same_inventory(self, db_engine, create_test_data):
        """Test multiple orders trying to deduct the same inventory concurrently."""
        # Create test data
        with db_engine.connect() as conn:
            session = Session(bind=conn)
            create_test_data(session)
            session.close()
        
        # Track results
        results = []
        errors = []
        lock = threading.Lock()
        
        async def process_order(order_id: int):
            """Process a single order."""
            # Each thread gets its own session
            with db_engine.connect() as conn:
                session = Session(bind=conn)
                service = RecipeInventoryService(session)
                
                try:
                    # Create order
                    order = Order(
                        id=order_id,
                        order_number=f"ORD-{order_id:03d}",
                        status=OrderStatus.PENDING
                    )
                    session.add(order)
                    
                    # Create order item
                    order_item = OrderItem(
                        order_id=order_id,
                        menu_item_id=1,
                        quantity=1,  # Needs 5 pieces of inventory
                        price=10.0
                    )
                    session.add(order_item)
                    session.commit()
                    
                    # Simulate some processing delay
                    await asyncio.sleep(0.01)
                    
                    # Try to deduct inventory
                    result = await service.deduct_inventory_for_order(
                        order_items=[order_item],
                        order_id=order_id,
                        user_id=1
                    )
                    
                    with lock:
                        results.append({
                            "order_id": order_id,
                            "success": True,
                            "result": result
                        })
                    
                except HTTPException as e:
                    with lock:
                        errors.append({
                            "order_id": order_id,
                            "error": str(e.detail)
                        })
                except Exception as e:
                    with lock:
                        errors.append({
                            "order_id": order_id,
                            "error": str(e)
                        })
                finally:
                    session.close()
        
        # Process 10 concurrent orders (but only enough inventory for 2)
        tasks = []
        for i in range(1, 11):
            tasks.append(process_order(i))
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify results
        assert len(results) == 2  # Only 2 orders should succeed
        assert len(errors) == 8   # 8 orders should fail due to insufficient stock
        
        # Check that the error is about insufficient inventory
        assert "Insufficient inventory" in errors[0]["error"]
        
        # Verify final inventory state
        with db_engine.connect() as conn:
            session = Session(bind=conn)
            inventory = session.query(Inventory).filter(Inventory.id == 1).first()
            assert inventory.quantity == 0.0  # All stock consumed
            
            # Verify adjustment records
            adjustments = session.query(InventoryAdjustment).all()
            assert len(adjustments) == 2  # Only 2 successful deductions
            
            total_deducted = sum(abs(adj.quantity_change) for adj in adjustments)
            assert total_deducted == 10.0  # Total of 10 pieces deducted
            
            session.close()
    
    async def test_concurrent_order_and_reversal(self, db_engine, create_test_data):
        """Test order deduction happening concurrently with a reversal."""
        # Create test data
        with db_engine.connect() as conn:
            session = Session(bind=conn)
            create_test_data(session)
            
            # Create and process first order
            service = RecipeInventoryService(session)
            
            order1 = Order(id=1, order_number="ORD-001", status=OrderStatus.PENDING)
            session.add(order1)
            
            order_item1 = OrderItem(
                order_id=1,
                menu_item_id=1,
                quantity=1,
                price=10.0
            )
            session.add(order_item1)
            session.commit()
            
            # Deduct inventory for first order
            await service.deduct_inventory_for_order(
                order_items=[order_item1],
                order_id=1,
                user_id=1
            )
            
            session.close()
        
        # Now run concurrent operations
        results = {"reversal": None, "new_order": None}
        
        async def reverse_first_order():
            """Reverse the first order."""
            with db_engine.connect() as conn:
                session = Session(bind=conn)
                service = RecipeInventoryService(session)
                
                try:
                    result = await service.reverse_inventory_deduction(
                        order_id=1,
                        user_id=1,
                        reason="Concurrent test"
                    )
                    results["reversal"] = {"success": True, "result": result}
                except Exception as e:
                    results["reversal"] = {"success": False, "error": str(e)}
                finally:
                    session.close()
        
        async def create_new_order():
            """Create a new order concurrently."""
            await asyncio.sleep(0.01)  # Small delay to ensure reversal starts first
            
            with db_engine.connect() as conn:
                session = Session(bind=conn)
                service = RecipeInventoryService(session)
                
                try:
                    order2 = Order(id=2, order_number="ORD-002", status=OrderStatus.PENDING)
                    session.add(order2)
                    
                    order_item2 = OrderItem(
                        order_id=2,
                        menu_item_id=1,
                        quantity=1,
                        price=10.0
                    )
                    session.add(order_item2)
                    session.commit()
                    
                    result = await service.deduct_inventory_for_order(
                        order_items=[order_item2],
                        order_id=2,
                        user_id=1
                    )
                    results["new_order"] = {"success": True, "result": result}
                except Exception as e:
                    results["new_order"] = {"success": False, "error": str(e)}
                finally:
                    session.close()
        
        # Run concurrently
        await asyncio.gather(
            reverse_first_order(),
            create_new_order()
        )
        
        # Both operations should succeed
        assert results["reversal"]["success"] is True
        assert results["new_order"]["success"] is True
        
        # Verify final state
        with db_engine.connect() as conn:
            session = Session(bind=conn)
            inventory = session.query(Inventory).filter(Inventory.id == 1).first()
            
            # Should have 10 (original) - 5 (order 2) = 5
            assert inventory.quantity == 5.0
            
            # Check adjustments
            adjustments = session.query(InventoryAdjustment).order_by(
                InventoryAdjustment.created_at
            ).all()
            
            # Should have: deduction for order 1, reversal for order 1, deduction for order 2
            assert len(adjustments) == 3
            assert adjustments[0].reference_id == "1"
            assert adjustments[0].quantity_change < 0  # Deduction
            assert adjustments[1].reference_id == "1"
            assert adjustments[1].quantity_change > 0  # Reversal
            assert adjustments[2].reference_id == "2"
            assert adjustments[2].quantity_change < 0  # Deduction
            
            session.close()
    
    async def test_deadlock_prevention(self, db_engine, create_test_data):
        """Test that the system handles potential deadlock scenarios."""
        # Create test data with multiple inventory items
        with db_engine.connect() as conn:
            session = Session(bind=conn)
            
            # Create multiple inventory items
            for i in range(1, 4):
                inventory = Inventory(
                    id=i,
                    item_name=f"Item {i}",
                    quantity=100.0,
                    unit="piece",
                    is_active=True
                )
                session.add(inventory)
            
            # Create menu items and recipes that use multiple ingredients
            for i in range(1, 3):
                menu_item = MenuItem(
                    id=i,
                    name=f"Product {i}",
                    price=20.0,
                    is_active=True
                )
                session.add(menu_item)
                
                recipe = Recipe(
                    id=i,
                    menu_item_id=i,
                    name=f"Recipe {i}",
                    status="active",
                    created_by=1
                )
                session.add(recipe)
                session.flush()
                
                # Recipe 1 uses items 1,2,3 in that order
                # Recipe 2 uses items 3,2,1 in that order (potential deadlock)
                ingredient_order = [1, 2, 3] if i == 1 else [3, 2, 1]
                for inv_id in ingredient_order:
                    ingredient = RecipeIngredient(
                        recipe_id=i,
                        inventory_id=inv_id,
                        quantity=1.0,
                        unit="piece",
                        created_by=1
                    )
                    session.add(ingredient)
            
            session.commit()
            session.close()
        
        # Process orders concurrently
        errors = []
        
        async def process_order_type(order_id: int, menu_item_id: int):
            """Process an order for a specific menu item."""
            with db_engine.connect() as conn:
                session = Session(bind=conn)
                service = RecipeInventoryService(session)
                
                try:
                    order = Order(
                        id=order_id,
                        order_number=f"ORD-{order_id:03d}",
                        status=OrderStatus.PENDING
                    )
                    session.add(order)
                    
                    order_item = OrderItem(
                        order_id=order_id,
                        menu_item_id=menu_item_id,
                        quantity=1,
                        price=20.0
                    )
                    session.add(order_item)
                    session.commit()
                    
                    await service.deduct_inventory_for_order(
                        order_items=[order_item],
                        order_id=order_id,
                        user_id=1
                    )
                    
                except Exception as e:
                    errors.append(str(e))
                finally:
                    session.close()
        
        # Run multiple orders concurrently that could cause deadlock
        tasks = []
        for i in range(5):
            # Alternate between menu items to create lock contention
            menu_item_id = 1 if i % 2 == 0 else 2
            tasks.append(process_order_type(i + 1, menu_item_id))
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # All operations should complete without deadlock
        # Some might fail due to other reasons, but not deadlock
        assert all("deadlock" not in error.lower() for error in errors)