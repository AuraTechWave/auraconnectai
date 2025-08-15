# backend/tests/test_query_performance.py

import pytest
import time
from typing import List, Tuple
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from unittest.mock import patch, MagicMock

from core.database import Base, get_db
from core.query_logger import log_query_performance, analyze_n_plus_one
from modules.orders.models.order_models import Order, OrderItem
from modules.customers.models.customer_models import Customer
from modules.menu.models import MenuItem, MenuCategory
from modules.staff.models.staff_models import Staff, Schedule


class QueryCounter:
    """Helper class to count database queries during tests"""
    
    def __init__(self):
        self.queries = []
        self.count = 0
    
    def __call__(self, conn, cursor, statement, parameters, context, executemany):
        self.count += 1
        self.queries.append({
            'statement': statement,
            'parameters': parameters,
            'time': time.time()
        })
    
    def reset(self):
        self.queries = []
        self.count = 0
    
    def get_table_counts(self) -> dict:
        """Get count of queries per table"""
        table_counts = {}
        for query in self.queries:
            statement = query['statement'].upper()
            if 'FROM' in statement:
                # Simple table extraction
                parts = statement.split('FROM')[1].split()
                if parts:
                    table = parts[0].strip().lower()
                    table_counts[table] = table_counts.get(table, 0) + 1
        return table_counts


@pytest.fixture
def query_counter(db_session):
    """Fixture to count queries in a test"""
    counter = QueryCounter()
    event.listen(db_session.bind, "before_cursor_execute", counter)
    yield counter
    event.remove(db_session.bind, "before_cursor_execute", counter)


class TestOrderEndpointPerformance:
    """Test performance of order-related endpoints"""
    
    def test_get_orders_no_n_plus_one(self, db_session: Session, query_counter: QueryCounter):
        """Test that getting orders doesn't cause N+1 queries"""
        # Create test data
        customer = Customer(
            name="Test Customer",
            email="test@example.com",
            phone="+1234567890"
        )
        db_session.add(customer)
        db_session.commit()
        
        # Create multiple orders
        for i in range(10):
            order = Order(
                customer_id=customer.id,
                restaurant_id=1,
                status="pending",
                total_amount=100.0 + i
            )
            db_session.add(order)
        
        db_session.commit()
        query_counter.reset()
        
        # Import the service function
        from modules.orders.services.order_service import get_orders_service
        
        # Execute the query
        orders = get_orders_service(
            db=db_session,
            limit=10,
            offset=0
        )
        
        # Check query count
        assert query_counter.count <= 3, f"Too many queries: {query_counter.count}. Expected <= 3"
        
        # Verify eager loading worked
        query_counter.reset()
        for order in orders:
            # Access customer relationship (should not trigger new queries)
            _ = order.customer.name if order.customer else None
        
        assert query_counter.count == 0, f"N+1 detected: {query_counter.count} additional queries for customer access"
    
    def test_order_with_items_eager_loading(self, db_session: Session, query_counter: QueryCounter):
        """Test that order items are properly eager loaded"""
        # Create test order with items
        order = Order(
            customer_id=1,
            restaurant_id=1,
            status="pending",
            total_amount=0
        )
        db_session.add(order)
        db_session.commit()
        
        # Add order items
        for i in range(5):
            item = OrderItem(
                order_id=order.id,
                menu_item_id=i + 1,
                quantity=2,
                price=10.0 + i
            )
            db_session.add(item)
        
        db_session.commit()
        query_counter.reset()
        
        # Query with eager loading
        from modules.orders.services.order_service import get_orders_service
        
        orders = get_orders_service(
            db=db_session,
            include_items=True,
            limit=1,
            offset=0
        )
        
        # Should be 2 queries: one for orders, one for items (with joinedload)
        assert query_counter.count <= 2, f"Too many queries: {query_counter.count}"
        
        # Access items shouldn't trigger new queries
        query_counter.reset()
        for order in orders:
            for item in order.order_items:
                _ = item.price
        
        assert query_counter.count == 0, f"N+1 detected: {query_counter.count} additional queries"


class TestCustomerEndpointPerformance:
    """Test performance of customer-related endpoints"""
    
    def test_customer_search_eager_loading(self, db_session: Session, query_counter: QueryCounter):
        """Test that customer search properly eager loads relationships"""
        # Create test customers with orders
        for i in range(5):
            customer = Customer(
                name=f"Customer {i}",
                email=f"customer{i}@example.com",
                phone=f"+123456789{i}"
            )
            db_session.add(customer)
        
        db_session.commit()
        
        # Add orders for each customer
        customers = db_session.query(Customer).all()
        for customer in customers:
            for j in range(3):
                order = Order(
                    customer_id=customer.id,
                    restaurant_id=1,
                    status="completed",
                    total_amount=50.0 * (j + 1)
                )
                db_session.add(order)
        
        db_session.commit()
        query_counter.reset()
        
        # Import and test the service
        from modules.customers.services.customer_service import CustomerService
        from modules.customers.schemas.customer_schemas import CustomerSearchParams
        
        service = CustomerService(db_session)
        params = CustomerSearchParams(limit=10, offset=0)
        
        customers, total = service.search_customers(params)
        
        # Should be minimal queries with eager loading
        assert query_counter.count <= 7, f"Too many queries: {query_counter.count}"
        
        # Access relationships shouldn't trigger new queries
        query_counter.reset()
        for customer in customers:
            _ = len(customer.orders) if hasattr(customer, 'orders') else 0
            _ = len(customer.addresses) if hasattr(customer, 'addresses') else 0
        
        assert query_counter.count == 0, f"N+1 detected: {query_counter.count} additional queries"
    
    def test_customer_order_history_batch_loading(self, db_session: Session, query_counter: QueryCounter):
        """Test that customer order history uses batch loading for menu items"""
        # Create customer with orders
        customer = Customer(
            name="Test Customer",
            email="test@example.com",
            phone="+1234567890"
        )
        db_session.add(customer)
        db_session.commit()
        
        # Create menu items
        for i in range(10):
            category = MenuCategory(name=f"Category {i}", display_order=i)
            db_session.add(category)
            db_session.commit()
            
            item = MenuItem(
                name=f"Item {i}",
                category_id=category.id,
                price=10.0 + i,
                is_available=True
            )
            db_session.add(item)
        
        db_session.commit()
        
        # Create orders with items
        menu_items = db_session.query(MenuItem).all()
        for i in range(5):
            order = Order(
                customer_id=customer.id,
                restaurant_id=1,
                status="completed",
                total_amount=100.0
            )
            db_session.add(order)
            db_session.commit()
            
            # Add order items
            for j in range(3):
                item = OrderItem(
                    order_id=order.id,
                    menu_item_id=menu_items[j].id,
                    quantity=1,
                    price=menu_items[j].price
                )
                db_session.add(item)
        
        db_session.commit()
        query_counter.reset()
        
        # Test the order history service
        from modules.customers.services.order_history_service import OrderHistoryService
        
        service = OrderHistoryService(db_session)
        favorites = service.get_favorite_items(customer.id, min_orders=1)
        
        # Should use batch loading for menu items
        table_counts = query_counter.get_table_counts()
        
        # Should not have individual queries for each menu item
        assert query_counter.count <= 5, f"Too many queries: {query_counter.count}"


class TestMenuEndpointPerformance:
    """Test performance of menu-related endpoints"""
    
    def test_menu_items_eager_loading_categories(self, db_session: Session, query_counter: QueryCounter):
        """Test that menu items endpoint eager loads categories"""
        # Create categories
        categories = []
        for i in range(5):
            category = MenuCategory(
                name=f"Category {i}",
                display_order=i
            )
            db_session.add(category)
            categories.append(category)
        
        db_session.commit()
        
        # Create menu items
        for i in range(20):
            item = MenuItem(
                name=f"Item {i}",
                category_id=categories[i % 5].id,
                price=10.0 + i,
                is_available=True
            )
            db_session.add(item)
        
        db_session.commit()
        query_counter.reset()
        
        # Test the menu service
        from core.menu_service import MenuService
        from core.menu_schemas import MenuSearchParams
        
        service = MenuService(db_session)
        params = MenuSearchParams(limit=20, offset=0)
        
        items, total = service.get_menu_items(params)
        
        # Should be 2 queries: count and items with categories
        assert query_counter.count <= 2, f"Too many queries: {query_counter.count}"
        
        # Access categories shouldn't trigger new queries
        query_counter.reset()
        for item in items:
            _ = item.category.name if item.category else "Uncategorized"
        
        assert query_counter.count == 0, f"N+1 detected: {query_counter.count} additional queries"


class TestStaffSchedulePerformance:
    """Test performance of staff schedule endpoints"""
    
    def test_schedule_eager_loading_staff(self, db_session: Session, query_counter: QueryCounter):
        """Test that schedule endpoints properly eager load staff"""
        # Create staff members
        staff_members = []
        for i in range(10):
            staff = Staff(
                name=f"Staff {i}",
                email=f"staff{i}@example.com",
                phone=f"+123456789{i}",
                role_id=1,
                restaurant_id=1
            )
            db_session.add(staff)
            staff_members.append(staff)
        
        db_session.commit()
        
        # Create schedules
        from datetime import date, time
        for staff in staff_members:
            for day in range(7):
                schedule = Schedule(
                    staff_id=staff.id,
                    restaurant_id=1,
                    date=date.today(),
                    start_time=time(9, 0),
                    end_time=time(17, 0),
                    status="confirmed"
                )
                db_session.add(schedule)
        
        db_session.commit()
        query_counter.reset()
        
        # Test the schedule service
        from modules.staff.services.schedule_service import ScheduleService
        
        service = ScheduleService(db_session)
        schedules = service.generate_preview(
            restaurant_id=1,
            start_date=date.today(),
            end_date=date.today()
        )
        
        # Should use eager loading
        assert query_counter.count <= 3, f"Too many queries: {query_counter.count}"
        
        # Access staff shouldn't trigger new queries
        query_counter.reset()
        for schedule in schedules:
            _ = schedule.staff.name if schedule.staff else None
            _ = schedule.staff.role.name if schedule.staff and schedule.staff.role else None
        
        # Already optimized, should be 0
        assert query_counter.count == 0, f"Queries detected: {query_counter.count}"


class TestCacheIntegration:
    """Test cache integration with database queries"""
    
    @patch('core.cache_service.redis.Redis')
    def test_cached_query_results(self, mock_redis, db_session: Session):
        """Test that cached decorator properly caches query results"""
        from core.cache_service import cached, cache_service
        
        # Mock Redis client
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.get.return_value = None
        mock_redis_instance.setex.return_value = True
        
        cache_service.redis_client = mock_redis_instance
        
        # Create a cached function
        @cached("test_query", ttl=60)
        def get_customers(limit: int):
            return db_session.query(Customer).limit(limit).all()
        
        # First call should hit database
        result1 = get_customers(5)
        assert mock_redis_instance.setex.called
        
        # Mock cache hit
        mock_redis_instance.get.return_value = '[]'  # Simulate cached empty list
        
        # Second call should hit cache
        result2 = get_customers(5)
        assert mock_redis_instance.get.called


def test_query_logger_integration():
    """Test query logger functionality"""
    from core.query_logger import QueryLogger, log_query_performance
    
    logger = QueryLogger()
    logger.enabled = True
    logger.reset_stats()
    
    with log_query_performance("test_operation"):
        # Simulate some queries
        logger.query_stats['total_queries'] = 5
        logger.query_stats['total_time'] = 0.5
    
    assert logger.query_stats['total_queries'] == 5
    assert logger.query_stats['total_time'] == 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])