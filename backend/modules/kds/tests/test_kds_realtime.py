# backend/modules/kds/tests/test_kds_realtime.py

"""
Tests for KDS Real-time Service
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from sqlalchemy.orm import Session

from ..services.kds_realtime_service import KDSRealtimeService, CourseType
from ..models.kds_models import (
    KDSOrderItem,
    KitchenStation,
    DisplayStatus,
    StationType,
    StationAssignment,
    MenuItemStation,
)
from modules.orders.models.order_models import Order, OrderItem
from modules.menu.models import MenuItem


@pytest.fixture
def db_session():
    """Mock database session"""
    session = Mock(spec=Session)
    session.commit = Mock()
    session.add = Mock()
    return session


@pytest.fixture
def realtime_service(db_session):
    """Create realtime service instance"""
    service = KDSRealtimeService(db_session)
    # Mock WebSocket manager
    service.ws_manager = AsyncMock()
    return service


@pytest.fixture
def sample_order():
    """Create sample order"""
    order = Mock(spec=Order)
    order.id = 1
    order.order_number = "ORD-001"
    order.table_number = 5
    order.created_at = datetime.utcnow() - timedelta(minutes=5)
    order.priority = 1
    order.is_rush = False
    return order


@pytest.fixture
def sample_order_items():
    """Create sample order items"""
    items = []
    
    # Appetizer
    item1 = Mock(spec=OrderItem)
    item1.id = 1
    item1.order_id = 1
    item1.menu_item_id = 101
    item1.quantity = 2
    item1.modifiers = ["No onions", "Extra cheese"]
    item1.special_instructions = "Make it spicy"
    items.append(item1)
    
    # Entree
    item2 = Mock(spec=OrderItem)
    item2.id = 2
    item2.order_id = 1
    item2.menu_item_id = 201
    item2.quantity = 1
    item2.modifiers = []
    item2.special_instructions = None
    items.append(item2)
    
    return items


@pytest.fixture
def sample_stations():
    """Create sample stations"""
    stations = []
    
    # Grill station
    grill = Mock(spec=KitchenStation)
    grill.id = 1
    grill.name = "Grill"
    grill.station_type = StationType.GRILL
    grill.prep_time_multiplier = 1.0
    grill.warning_time_minutes = 5
    grill.critical_time_minutes = 10
    stations.append(grill)
    
    # Salad station
    salad = Mock(spec=KitchenStation)
    salad.id = 2
    salad.name = "Salad"
    salad.station_type = StationType.SALAD
    salad.prep_time_multiplier = 0.8
    salad.warning_time_minutes = 3
    salad.critical_time_minutes = 6
    stations.append(salad)
    
    # Expo station
    expo = Mock(spec=KitchenStation)
    expo.id = 3
    expo.name = "Expo"
    expo.station_type = StationType.EXPO
    expo.prep_time_multiplier = 1.0
    expo.warning_time_minutes = 2
    expo.critical_time_minutes = 5
    stations.append(expo)
    
    return stations


class TestOrderProcessing:
    """Test order processing and routing"""
    
    @pytest.mark.asyncio
    async def test_process_new_order_basic(
        self, realtime_service, db_session, sample_order, sample_order_items
    ):
        """Test basic order processing"""
        # Setup mocks
        db_session.query(Order).filter_by().first.return_value = sample_order
        db_session.query(OrderItem).filter_by().all.return_value = sample_order_items
        
        # Mock routing
        with patch.object(realtime_service, "_route_item_to_stations") as mock_route:
            mock_route.return_value = [(1, True, 0)]  # Station 1, primary, sequence 0
            
            with patch.object(realtime_service, "_create_kds_item") as mock_create:
                mock_kds_item = Mock(spec=KDSOrderItem)
                mock_kds_item.id = 1
                mock_kds_item.station_id = 1
                mock_create.return_value = mock_kds_item
                
                with patch.object(realtime_service, "_notify_new_item") as mock_notify:
                    # Process order
                    result = await realtime_service.process_new_order(1)
        
        # Verify processing
        assert len(result) == 2  # Two order items
        assert db_session.add.call_count == 2
        assert db_session.commit.called
        assert mock_notify.call_count == 2
    
    @pytest.mark.asyncio
    async def test_process_new_order_invalid(self, realtime_service, db_session):
        """Test processing invalid order"""
        # Setup mock for non-existent order
        db_session.query(Order).filter_by().first.return_value = None
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Order 999 not found"):
            await realtime_service.process_new_order(999)
    
    def test_route_item_to_stations_direct_mapping(
        self, realtime_service, db_session
    ):
        """Test routing with direct menu item to station mapping"""
        # Create menu item station mapping
        mapping = Mock(spec=MenuItemStation)
        mapping.station_id = 1
        mapping.is_primary = True
        mapping.sequence = 0
        
        # Setup mocks
        db_session.query(MenuItemStation).filter_by().order_by().all.return_value = [mapping]
        
        # Create order item
        order_item = Mock(spec=OrderItem)
        order_item.menu_item_id = 101
        
        # Route item
        stations = realtime_service._route_item_to_stations(order_item)
        
        # Verify routing
        assert len(stations) == 1
        assert stations[0] == (1, True, 0)
    
    def test_route_item_to_stations_category_based(
        self, realtime_service, db_session, sample_stations
    ):
        """Test category-based routing"""
        # No direct mapping
        db_session.query(MenuItemStation).filter_by().order_by().all.return_value = []
        
        # Create menu item with category
        menu_item = Mock(spec=MenuItem)
        menu_item.category = "Salads"
        db_session.query(MenuItem).filter_by().first.return_value = menu_item
        
        # Create category assignment
        assignment = Mock(spec=StationAssignment)
        assignment.station_id = 2
        assignment.is_primary = True
        assignment.priority = 10
        assignment.conditions = {}
        db_session.query(StationAssignment).filter().order_by().all.return_value = [assignment]
        
        # Mock condition check
        with patch.object(realtime_service, "_check_assignment_conditions", return_value=True):
            # Create order item
            order_item = Mock(spec=OrderItem)
            order_item.menu_item_id = 101
            
            # Route item
            stations = realtime_service._route_item_to_stations(order_item)
        
        # Verify routing
        assert len(stations) == 1
        assert stations[0][0] == 2  # Salad station
    
    def test_route_item_to_stations_default_expo(
        self, realtime_service, db_session, sample_stations
    ):
        """Test default routing to expo station"""
        # No mappings found
        db_session.query(MenuItemStation).filter_by().order_by().all.return_value = []
        db_session.query(MenuItem).filter_by().first.return_value = None
        
        # Default to expo station
        db_session.query(KitchenStation).filter_by().first.return_value = sample_stations[2]  # Expo
        
        # Create order item
        order_item = Mock(spec=OrderItem)
        order_item.menu_item_id = 999
        
        # Route item
        stations = realtime_service._route_item_to_stations(order_item)
        
        # Verify default routing
        assert len(stations) == 1
        assert stations[0][0] == 3  # Expo station


class TestItemCreation:
    """Test KDS item creation"""
    
    def test_create_kds_item_basic(
        self, realtime_service, db_session, sample_order, sample_stations
    ):
        """Test basic KDS item creation"""
        # Setup mocks
        db_session.query(KitchenStation).filter_by().first.return_value = sample_stations[0]
        db_session.query(MenuItemStation).filter_by().first.return_value = None
        
        # Create menu item
        menu_item = Mock(spec=MenuItem)
        menu_item.name = "Burger"
        menu_item.category = "Entrees"
        db_session.query(MenuItem).filter_by().first.return_value = menu_item
        
        # Mock helper methods
        with patch.object(realtime_service, "_determine_course", return_value=4):
            with patch.object(realtime_service, "_calculate_priority", return_value=10):
                with patch.object(realtime_service, "_build_display_name", return_value="Burger"):
                    # Create order item
                    order_item = Mock(spec=OrderItem)
                    order_item.id = 1
                    order_item.menu_item_id = 101
                    order_item.quantity = 2
                    order_item.modifiers = ["No pickles"]
                    order_item.special_instructions = "Well done"
                    
                    # Create KDS item
                    kds_item = realtime_service._create_kds_item(
                        order_item, 1, 0, True, sample_order
                    )
        
        # Verify creation
        assert kds_item.order_item_id == 1
        assert kds_item.station_id == 1
        assert kds_item.display_name == "Burger"
        assert kds_item.quantity == 2
        assert kds_item.priority == 10
        assert kds_item.course_number == 4
    
    def test_determine_course(self, realtime_service, db_session):
        """Test course determination"""
        # Test appetizer
        menu_item = Mock(spec=MenuItem)
        menu_item.category = "Appetizers"
        db_session.query(MenuItem).filter_by().first.return_value = menu_item
        
        order_item = Mock(spec=OrderItem)
        order_item.menu_item_id = 101
        
        course = realtime_service._determine_course(order_item)
        assert course == 1
        
        # Test entree
        menu_item.category = "Main Courses"
        course = realtime_service._determine_course(order_item)
        assert course == 4
        
        # Test dessert
        menu_item.category = "Desserts"
        course = realtime_service._determine_course(order_item)
        assert course == 5
        
        # Test beverage
        menu_item.category = "Beverages"
        course = realtime_service._determine_course(order_item)
        assert course == 0
    
    def test_calculate_priority(self, realtime_service, sample_order):
        """Test priority calculation"""
        order_item = Mock(spec=OrderItem)
        
        # Normal priority
        priority = realtime_service._calculate_priority(sample_order, order_item, True)
        assert priority == 15  # Base + primary station
        
        # Rush order
        sample_order.is_rush = True
        priority = realtime_service._calculate_priority(sample_order, order_item, True)
        assert priority == 35  # Base + primary + rush
        
        # Old order
        sample_order.is_rush = False
        sample_order.created_at = datetime.utcnow() - timedelta(minutes=35)
        priority = realtime_service._calculate_priority(sample_order, order_item, False)
        assert priority == 25  # Base + long wait


class TestStatusUpdates:
    """Test item status updates"""
    
    @pytest.mark.asyncio
    async def test_update_item_status_to_in_progress(
        self, realtime_service, db_session
    ):
        """Test updating item to in progress"""
        # Create KDS item
        item = Mock(spec=KDSOrderItem)
        item.id = 1
        item.status = DisplayStatus.PENDING
        item.station_id = 1
        item.order_item_id = 101
        
        # Setup mocks
        db_session.query(KDSOrderItem).filter_by().first.return_value = item
        
        with patch.object(realtime_service, "_notify_item_update") as mock_notify:
            with patch.object(realtime_service, "_check_order_completion") as mock_check:
                # Update status
                result = await realtime_service.update_item_status(
                    1, DisplayStatus.IN_PROGRESS, staff_id=10
                )
        
        # Verify update
        assert item.status == DisplayStatus.IN_PROGRESS
        assert item.started_at is not None
        assert item.started_by_id == 10
        assert db_session.commit.called
        assert mock_notify.called
    
    @pytest.mark.asyncio
    async def test_update_item_status_to_completed(
        self, realtime_service, db_session
    ):
        """Test completing an item"""
        # Create KDS item
        item = Mock(spec=KDSOrderItem)
        item.id = 1
        item.status = DisplayStatus.IN_PROGRESS
        item.station_id = 1
        item.order_item_id = 101
        
        # Setup mocks
        db_session.query(KDSOrderItem).filter_by().first.return_value = item
        
        with patch.object(realtime_service, "_notify_item_update") as mock_notify:
            with patch.object(realtime_service, "_check_order_completion") as mock_check:
                # Complete item
                result = await realtime_service.update_item_status(
                    1, DisplayStatus.COMPLETED, staff_id=10
                )
        
        # Verify completion
        assert item.status == DisplayStatus.COMPLETED
        assert item.completed_at is not None
        assert item.completed_by_id == 10
        assert mock_check.called
    
    @pytest.mark.asyncio
    async def test_update_item_status_recall(
        self, realtime_service, db_session
    ):
        """Test recalling an item"""
        # Create KDS item
        item = Mock(spec=KDSOrderItem)
        item.id = 1
        item.status = DisplayStatus.COMPLETED
        item.station_id = 1
        item.recall_count = 0
        item.order_item_id = 101
        
        # Setup mocks
        db_session.query(KDSOrderItem).filter_by().first.return_value = item
        
        with patch.object(realtime_service, "_notify_item_update") as mock_notify:
            # Recall item
            result = await realtime_service.update_item_status(
                1, DisplayStatus.RECALLED, reason="Quality issue"
            )
        
        # Verify recall
        assert item.status == DisplayStatus.PENDING  # Reset to pending
        assert item.recall_count == 1
        assert item.recall_reason == "Quality issue"
        assert item.last_recalled_at is not None


class TestStationDisplay:
    """Test station display functionality"""
    
    def test_get_station_display_items(
        self, realtime_service, db_session, sample_stations
    ):
        """Test getting display items for a station"""
        # Create KDS items
        items = []
        base_time = datetime.utcnow()
        
        for i in range(3):
            item = Mock(spec=KDSOrderItem)
            item.id = i + 1
            item.order_item_id = 100 + i
            item.station_id = 1
            item.display_name = f"Item {i+1}"
            item.quantity = 1
            item.modifiers = []
            item.special_instructions = None
            item.status = DisplayStatus.PENDING
            item.priority = 10 - i
            item.course_number = 1
            item.received_at = base_time - timedelta(minutes=i*2)
            item.target_time = base_time + timedelta(minutes=10)
            item.is_late = False
            item.recall_count = 0
            item.fire_time = None
            items.append(item)
        
        # Setup mocks
        db_session.query(KDSOrderItem).filter().order_by().limit().all.return_value = items
        db_session.query(OrderItem).filter_by().first.return_value = None
        db_session.query(KitchenStation).filter_by().first.return_value = sample_stations[0]
        
        # Get display items
        display_items = realtime_service.get_station_display_items(1)
        
        # Verify display
        assert len(display_items) == 3
        assert display_items[0]["display_name"] == "Item 1"
        assert display_items[0]["status"] == "pending"
        assert "elapsed_time" in display_items[0]
    
    def test_get_station_summary(
        self, realtime_service, db_session, sample_stations
    ):
        """Test getting station summary"""
        # Setup mocks
        db_session.query(KitchenStation).filter_by().first.return_value = sample_stations[0]
        
        # Mock status counts
        db_session.query(KDSOrderItem).filter().count.side_effect = [
            5,  # Pending
            3,  # In progress
            10, # Ready
            0,  # Recalled
            15, # Completed
            0,  # Cancelled
        ]
        
        # Mock active items
        db_session.query(KDSOrderItem).filter().all.return_value = []
        
        # Get summary
        summary = realtime_service.get_station_summary(1)
        
        # Verify summary
        assert summary["station_id"] == 1
        assert summary["station_name"] == "Grill"
        assert summary["status_counts"]["pending"] == 5
        assert summary["status_counts"]["in_progress"] == 3
        assert summary["active_items"] == 8  # Pending + In progress


class TestCourseFiring:
    """Test course firing functionality"""
    
    def test_fire_course(self, realtime_service, db_session):
        """Test firing a course"""
        # Create KDS items for course
        items = []
        for i in range(3):
            item = Mock(spec=KDSOrderItem)
            item.id = i + 1
            item.station_id = i + 1
            item.course_number = 2
            item.status = DisplayStatus.PENDING
            item.fire_time = None
            items.append(item)
        
        # Setup mocks
        db_session.query(KDSOrderItem).join().filter().all.return_value = items
        
        # Fire course
        result = realtime_service.fire_course(1, 2)
        
        # Verify firing
        assert len(result) == 3
        for item in items:
            assert item.fire_time is not None
        assert db_session.commit.called


class TestWebSocketNotifications:
    """Test WebSocket notifications"""
    
    @pytest.mark.asyncio
    async def test_notify_new_item(self, realtime_service):
        """Test new item notification"""
        # Create KDS item
        item = Mock(spec=KDSOrderItem)
        item.id = 1
        item.station_id = 1
        item.order_item_id = 101
        item.display_name = "Test Item"
        item.quantity = 2
        item.modifiers = []
        item.special_instructions = None
        item.status = DisplayStatus.PENDING
        item.priority = 10
        item.course_number = 1
        item.received_at = datetime.utcnow()
        item.target_time = datetime.utcnow() + timedelta(minutes=15)
        
        # Notify
        await realtime_service._notify_new_item(item)
        
        # Verify notification
        realtime_service.ws_manager.broadcast_new_item.assert_called_once()
        call_args = realtime_service.ws_manager.broadcast_new_item.call_args
        assert call_args[0][0] == 1  # Station ID
        assert call_args[0][1]["display_name"] == "Test Item"
    
    @pytest.mark.asyncio
    async def test_bump_item(self, realtime_service, db_session):
        """Test bumping an item"""
        # Create KDS item
        item = Mock(spec=KDSOrderItem)
        item.id = 1
        item.station_id = 1
        item.status = DisplayStatus.IN_PROGRESS
        
        # Setup mocks
        db_session.query(KDSOrderItem).filter_by().first.return_value = item
        
        with patch("asyncio.create_task") as mock_task:
            # Bump item
            await realtime_service.bump_item(1, staff_id=10)
        
        # Verify bump
        assert item.status == DisplayStatus.READY
        assert item.completed_at is not None
        assert item.completed_by_id == 10
        assert mock_task.called  # Auto-complete task created