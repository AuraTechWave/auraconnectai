# backend/modules/kds/tests/test_kds_stress.py

"""
Stress tests for KDS to identify race conditions and performance issues.
"""

import pytest
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine
import time
import random

from modules.kds.services.kds_service import KDSService
from modules.kds.services.kds_order_routing_service import KDSOrderRoutingService
from modules.kds.models.kds_models import (
    KitchenStation,
    KDSOrderItem,
    StationType,
    StationStatus,
    DisplayStatus,
)
from modules.kds.schemas.kds_schemas import StationCreate
from modules.orders.models.order_models import Order, OrderItem
from modules.staff.models import StaffMember
from core.database import Base


class TestKDSStress:
    """Stress tests for KDS concurrent operations"""

    @pytest.fixture
    def db_engine(self):
        """Create a test database engine for concurrent connections"""
        # Use in-memory SQLite for tests (replace with test DB URL in production)
        engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=engine)
        return engine

    @pytest.fixture
    def session_factory(self, db_engine):
        """Create a session factory for concurrent tests"""
        return sessionmaker(bind=db_engine)

    def test_concurrent_station_updates(self, session_factory):
        """Test concurrent updates to the same station"""
        # Setup
        with session_factory() as session:
            station = KitchenStation(
                name="Test Station",
                station_type=StationType.GRILL,
                status=StationStatus.ACTIVE,
            )
            session.add(station)
            session.commit()
            station_id = station.id

        def update_station_status(status: StationStatus, iteration: int):
            """Update station status in a separate session"""
            with session_factory() as session:
                service = KDSService(session)
                try:
                    from ..schemas.kds_schemas import StationUpdate

                    service.update_station(station_id, StationUpdate(status=status))
                    return f"Success: {status.value} - {iteration}"
                except Exception as e:
                    return f"Error: {str(e)} - {iteration}"

        # Run concurrent updates
        statuses = [StationStatus.BUSY, StationStatus.ACTIVE, StationStatus.OFFLINE]
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(30):
                status = statuses[i % len(statuses)]
                future = executor.submit(update_station_status, status, i)
                futures.append(future)

            results = [future.result() for future in as_completed(futures)]

        # Verify no errors occurred
        errors = [r for r in results if r.startswith("Error")]
        assert len(errors) == 0, f"Concurrent update errors: {errors}"

    def test_concurrent_item_status_updates(self, session_factory):
        """Test concurrent status updates to the same KDS item"""
        # Setup
        with session_factory() as session:
            # Create station
            station = KitchenStation(
                name="Test Station",
                station_type=StationType.GRILL,
                status=StationStatus.ACTIVE,
            )
            session.add(station)

            # Create staff members
            staff_members = []
            for i in range(5):
                staff = StaffMember(
                    name=f"Chef {i}",
                    email=f"chef{i}@test.com",
                    phone=f"123456789{i}",
                    role="chef",
                    is_active=True,
                )
                session.add(staff)
                staff_members.append(staff)

            session.commit()

            # Create order and KDS item
            order = Order(staff_id=staff_members[0].id, table_no=1, status="pending")
            session.add(order)
            session.commit()

            order_item = OrderItem(
                order_id=order.id, menu_item_id=1, quantity=1, price=10.00
            )
            session.add(order_item)
            session.commit()

            kds_item = KDSOrderItem(
                order_item_id=order_item.id,
                station_id=station.id,
                display_name="Test Item",
                quantity=1,
                status=DisplayStatus.PENDING,
            )
            session.add(kds_item)
            session.commit()

            kds_item_id = kds_item.id
            staff_ids = [s.id for s in staff_members]

        def update_item_status(staff_id: int, action: str):
            """Update item status in a separate session"""
            with session_factory() as session:
                service = KDSService(session)
                try:
                    if action == "acknowledge":
                        service.acknowledge_item(kds_item_id, staff_id)
                    elif action == "start":
                        service.start_item(kds_item_id, staff_id)
                    elif action == "complete":
                        service.complete_item(kds_item_id, staff_id)
                    return f"Success: {action} by staff {staff_id}"
                except Exception as e:
                    return f"Error: {action} - {str(e)}"

        # Simulate concurrent kitchen operations
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []

            # Multiple chefs trying to acknowledge
            for staff_id in staff_ids[:3]:
                future = executor.submit(update_item_status, staff_id, "acknowledge")
                futures.append(future)

            # Wait a bit then try to start
            time.sleep(0.1)
            for staff_id in staff_ids[:2]:
                future = executor.submit(update_item_status, staff_id, "start")
                futures.append(future)

            results = [future.result() for future in as_completed(futures)]

        # Verify final state
        with session_factory() as session:
            final_item = session.query(KDSOrderItem).filter_by(id=kds_item_id).first()
            assert final_item.status == DisplayStatus.IN_PROGRESS
            assert final_item.started_by_id is not None

    def test_high_volume_order_routing(self, session_factory):
        """Test routing many orders simultaneously"""
        # Setup stations and menu items
        with session_factory() as session:
            # Create multiple stations
            stations = []
            for i, station_type in enumerate(
                [
                    StationType.GRILL,
                    StationType.FRY,
                    StationType.SALAD,
                    StationType.DESSERT,
                ]
            ):
                station = KitchenStation(
                    name=f"{station_type.value} Station",
                    station_type=station_type,
                    status=StationStatus.ACTIVE,
                    priority=10 - i,
                )
                session.add(station)
                stations.append(station)

            # Create staff
            staff = StaffMember(
                name="Server",
                email="server@test.com",
                phone="1234567890",
                role="server",
                is_active=True,
            )
            session.add(staff)
            session.commit()

            staff_id = staff.id
            station_ids = [s.id for s in stations]

        def create_and_route_order(order_num: int):
            """Create an order and route it"""
            with session_factory() as session:
                try:
                    # Create order
                    order = Order(
                        staff_id=staff_id, table_no=order_num % 20 + 1, status="pending"
                    )
                    session.add(order)
                    session.commit()

                    # Add random items
                    num_items = random.randint(1, 5)
                    for i in range(num_items):
                        item = OrderItem(
                            order_id=order.id,
                            menu_item_id=random.randint(1, 20),
                            quantity=random.randint(1, 3),
                            price=random.uniform(5.99, 25.99),
                        )
                        session.add(item)
                    session.commit()

                    # Route the order
                    routing_service = KDSOrderRoutingService(session)
                    routed_items = routing_service.route_order_to_stations(order.id)

                    return f"Order {order_num}: {len(routed_items)} items routed"
                except Exception as e:
                    return f"Order {order_num} Error: {str(e)}"

        # Create many orders concurrently
        num_orders = 50
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(create_and_route_order, i) for i in range(num_orders)
            ]

            results = [future.result() for future in as_completed(futures)]

        # Check results
        errors = [r for r in results if "Error" in r]
        assert len(errors) == 0, f"Routing errors: {errors}"

        # Verify all items were routed
        with session_factory() as session:
            total_orders = session.query(Order).count()
            total_kds_items = session.query(KDSOrderItem).count()
            assert total_orders == num_orders
            assert total_kds_items > 0

    def test_station_summary_under_load(self, session_factory):
        """Test station summary calculations with many concurrent operations"""
        # Setup
        with session_factory() as session:
            station = KitchenStation(
                name="Busy Station",
                station_type=StationType.GRILL,
                status=StationStatus.ACTIVE,
            )
            session.add(station)

            staff = StaffMember(
                name="Chef",
                email="chef@test.com",
                phone="1234567890",
                role="chef",
                is_active=True,
            )
            session.add(staff)
            session.commit()

            station_id = station.id
            staff_id = staff.id

            # Create many KDS items
            for i in range(100):
                order = Order(staff_id=staff_id, table_no=1, status="pending")
                session.add(order)
                session.commit()

                order_item = OrderItem(
                    order_id=order.id, menu_item_id=1, quantity=1, price=10.00
                )
                session.add(order_item)
                session.commit()

                status = random.choice(
                    [
                        DisplayStatus.PENDING,
                        DisplayStatus.IN_PROGRESS,
                        DisplayStatus.COMPLETED,
                    ]
                )

                kds_item = KDSOrderItem(
                    order_item_id=order_item.id,
                    station_id=station_id,
                    display_name=f"Item {i}",
                    quantity=1,
                    status=status,
                    received_at=datetime.utcnow()
                    - timedelta(minutes=random.randint(1, 60)),
                )

                if status == DisplayStatus.COMPLETED:
                    kds_item.completed_at = datetime.utcnow()

                session.add(kds_item)

            session.commit()

        def get_station_summary():
            """Get station summary in a separate session"""
            with session_factory() as session:
                service = KDSService(session)
                try:
                    summary = service.get_station_summary(station_id)
                    return {
                        "success": True,
                        "active": summary.active_items,
                        "pending": summary.pending_items,
                        "completed": summary.completed_today,
                    }
                except Exception as e:
                    return {"success": False, "error": str(e)}

        # Get summary multiple times concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(get_station_summary) for _ in range(20)]

            results = [future.result() for future in as_completed(futures)]

        # Verify all summaries succeeded and are consistent
        assert all(r["success"] for r in results)

        # Check that all summaries return the same values
        first_result = results[0]
        for result in results[1:]:
            assert result["active"] == first_result["active"]
            assert result["pending"] == first_result["pending"]
            assert result["completed"] == first_result["completed"]

    @pytest.mark.asyncio
    async def test_websocket_broadcast_performance(self, session_factory):
        """Test WebSocket broadcasting under load"""
        from ..services.kds_websocket_manager import KDSWebSocketManager

        manager = KDSWebSocketManager()

        # Simulate multiple WebSocket connections
        class MockWebSocket:
            def __init__(self, station_id):
                self.station_id = station_id
                self.messages = []
                self.closed = False

            async def send_text(self, message):
                if not self.closed:
                    self.messages.append(message)

            async def close(self):
                self.closed = True

        # Create many mock connections
        station_ids = list(range(1, 11))  # 10 stations
        connections_per_station = 10

        for station_id in station_ids:
            for _ in range(connections_per_station):
                ws = MockWebSocket(station_id)
                await manager.connect(ws, station_id)

        # Broadcast many messages
        start_time = time.time()

        tasks = []
        for _ in range(100):
            station_id = random.choice(station_ids)
            task = manager.broadcast_new_item(
                station_id,
                {
                    "item": {
                        "id": random.randint(1, 1000),
                        "display_name": "Test Item",
                        "status": "pending",
                    }
                },
            )
            tasks.append(task)

        # Wait for all broadcasts
        await asyncio.gather(*tasks)

        end_time = time.time()
        duration = end_time - start_time

        # Performance check
        assert duration < 5.0, f"Broadcasting took too long: {duration}s"

        # Verify message delivery
        total_connections = len(station_ids) * connections_per_station
        assert manager.get_all_connection_counts()

    def test_race_condition_prevention(self, session_factory):
        """Test that race conditions are properly handled"""
        # This test specifically checks for race conditions in critical operations

        with session_factory() as session:
            # Setup
            station = KitchenStation(
                name="Race Test Station",
                station_type=StationType.GRILL,
                status=StationStatus.ACTIVE,
            )
            session.add(station)

            staff1 = StaffMember(
                name="Chef 1",
                email="chef1@test.com",
                phone="1111111111",
                role="chef",
                is_active=True,
            )
            staff2 = StaffMember(
                name="Chef 2",
                email="chef2@test.com",
                phone="2222222222",
                role="chef",
                is_active=True,
            )
            session.add_all([staff1, staff2])
            session.commit()

            # Create order item
            order = Order(staff_id=staff1.id, table_no=1, status="pending")
            session.add(order)
            session.commit()

            order_item = OrderItem(
                order_id=order.id, menu_item_id=1, quantity=1, price=10.00
            )
            session.add(order_item)
            session.commit()

            kds_item = KDSOrderItem(
                order_item_id=order_item.id,
                station_id=station.id,
                display_name="Race Test Item",
                quantity=1,
                status=DisplayStatus.PENDING,
            )
            session.add(kds_item)
            session.commit()

            kds_item_id = kds_item.id
            staff1_id = staff1.id
            staff2_id = staff2.id

        # Both chefs try to start the same item simultaneously
        def try_start_item(staff_id: int, delay: float = 0):
            if delay:
                time.sleep(delay)

            with session_factory() as session:
                service = KDSService(session)
                try:
                    item = service.start_item(kds_item_id, staff_id)
                    return {"success": True, "started_by": item.started_by_id}
                except Exception as e:
                    return {"success": False, "error": str(e)}

        # Run concurrent starts with minimal delay
        with ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(try_start_item, staff1_id, 0)
            future2 = executor.submit(try_start_item, staff2_id, 0.001)  # 1ms delay

            result1 = future1.result()
            result2 = future2.result()

        # Only one should succeed
        success_count = sum(1 for r in [result1, result2] if r["success"])
        assert (
            success_count == 1
        ), "Race condition: multiple chefs started the same item"

        # Verify final state
        with session_factory() as session:
            final_item = session.query(KDSOrderItem).filter_by(id=kds_item_id).first()
            assert final_item.status == DisplayStatus.IN_PROGRESS
            assert final_item.started_by_id in [staff1_id, staff2_id]
