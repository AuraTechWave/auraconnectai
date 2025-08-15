# backend/modules/kds/tests/test_kds_bug_fixes.py

"""
Tests for KDS bug fixes
"""

import pytest
import json
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from sqlalchemy.orm import Session
from fastapi import WebSocket

from ..services.kds_performance_service import KDSPerformanceService, TimeRange
from ..services.kds_realtime_service import KDSRealtimeService
from ..models.kds_models import (
    KDSOrderItem,
    KitchenStation,
    DisplayStatus,
    StationType,
)
from modules.orders.models.order_models import Order, OrderItem


class TestWebSocketStatusValidation:
    """Test WebSocket status message validation fixes"""
    
    @pytest.mark.asyncio
    async def test_websocket_missing_status_key(self):
        """Test handling of missing status key in WebSocket message"""
        from ..routes.kds_realtime_routes import websocket_station_endpoint
        
        # Mock WebSocket
        websocket = AsyncMock(spec=WebSocket)
        websocket.accept = AsyncMock()
        websocket.send_json = AsyncMock()
        websocket.receive_text = AsyncMock()
        
        # Mock database session
        db_session = Mock(spec=Session)
        service = Mock(spec=KDSRealtimeService)
        service.get_station_summary.return_value = {"station_id": 1}
        service.get_station_display_items.return_value = []
        
        # Create message without status key
        message = json.dumps({
            "type": "update_status",
            "item_id": 1,
            # "status" key is missing
        })
        
        # Set up WebSocket to return the message then disconnect
        websocket.receive_text.side_effect = [
            message,
            asyncio.TimeoutError()  # To exit the loop
        ]
        
        with patch('backend.modules.kds.routes.kds_realtime_routes.KDSRealtimeService', return_value=service):
            with patch('backend.modules.kds.routes.kds_realtime_routes.kds_websocket_manager') as mock_manager:
                mock_manager.connect = AsyncMock()
                mock_manager.disconnect = Mock()
                
                try:
                    await websocket_station_endpoint(websocket, 1, db_session)
                except asyncio.TimeoutError:
                    pass
        
        # Verify error message was sent
        error_calls = [
            call for call in websocket.send_json.call_args_list
            if call[0][0].get("type") == "error"
        ]
        assert len(error_calls) > 0
        assert "Status is required" in error_calls[0][0][0]["message"]
    
    @pytest.mark.asyncio
    async def test_websocket_invalid_status_value(self):
        """Test handling of invalid status value in WebSocket message"""
        from ..routes.kds_realtime_routes import websocket_station_endpoint
        
        # Mock WebSocket
        websocket = AsyncMock(spec=WebSocket)
        websocket.accept = AsyncMock()
        websocket.send_json = AsyncMock()
        websocket.receive_text = AsyncMock()
        
        # Mock database session
        db_session = Mock(spec=Session)
        service = Mock(spec=KDSRealtimeService)
        service.get_station_summary.return_value = {"station_id": 1}
        service.get_station_display_items.return_value = []
        
        # Create message with invalid status
        message = json.dumps({
            "type": "update_status",
            "item_id": 1,
            "status": "INVALID_STATUS"
        })
        
        # Set up WebSocket to return the message then disconnect
        websocket.receive_text.side_effect = [
            message,
            asyncio.TimeoutError()  # To exit the loop
        ]
        
        with patch('backend.modules.kds.routes.kds_realtime_routes.KDSRealtimeService', return_value=service):
            with patch('backend.modules.kds.routes.kds_realtime_routes.kds_websocket_manager') as mock_manager:
                mock_manager.connect = AsyncMock()
                mock_manager.disconnect = Mock()
                
                try:
                    await websocket_station_endpoint(websocket, 1, db_session)
                except asyncio.TimeoutError:
                    pass
        
        # Verify error message was sent with valid statuses
        error_calls = [
            call for call in websocket.send_json.call_args_list
            if call[0][0].get("type") == "error"
        ]
        assert len(error_calls) > 0
        assert "Invalid status" in error_calls[0][0][0]["message"]
        assert "valid_statuses" in error_calls[0][0][0]
    
    @pytest.mark.asyncio
    async def test_websocket_valid_status_processing(self):
        """Test successful processing of valid status"""
        from ..routes.kds_realtime_routes import websocket_station_endpoint
        
        # Mock WebSocket
        websocket = AsyncMock(spec=WebSocket)
        websocket.accept = AsyncMock()
        websocket.send_json = AsyncMock()
        websocket.receive_text = AsyncMock()
        
        # Mock database session and service
        db_session = Mock(spec=Session)
        service = Mock(spec=KDSRealtimeService)
        service.get_station_summary.return_value = {"station_id": 1}
        service.get_station_display_items.return_value = []
        service.update_item_status = AsyncMock()
        
        # Create valid message
        message = json.dumps({
            "type": "update_status",
            "item_id": 1,
            "status": "in_progress",
            "staff_id": 10
        })
        
        # Set up WebSocket to return the message then disconnect
        websocket.receive_text.side_effect = [
            message,
            asyncio.TimeoutError()  # To exit the loop
        ]
        
        with patch('backend.modules.kds.routes.kds_realtime_routes.KDSRealtimeService', return_value=service):
            with patch('backend.modules.kds.routes.kds_realtime_routes.kds_websocket_manager') as mock_manager:
                mock_manager.connect = AsyncMock()
                mock_manager.disconnect = Mock()
                
                try:
                    await websocket_station_endpoint(websocket, 1, db_session)
                except asyncio.TimeoutError:
                    pass
        
        # Verify update_item_status was called
        service.update_item_status.assert_called_once_with(
            item_id=1,
            new_status=DisplayStatus.IN_PROGRESS,
            staff_id=10
        )


class TestKitchenAnalyticsOrderCounting:
    """Test kitchen analytics order counting fix"""
    
    def test_correct_order_counting(self):
        """Test that orders are counted correctly, not order items"""
        # Mock database session
        db_session = Mock(spec=Session)
        service = KDSPerformanceService(db_session)
        
        # Mock stations
        stations = [Mock(spec=KitchenStation)]
        db_session.query(KitchenStation).all.return_value = stations
        
        # Mock total items count
        items_query = Mock()
        items_query.count.return_value = 10  # 10 items total
        db_session.query(KDSOrderItem).filter().return_value = items_query
        
        # Mock unique orders query
        # Simulate 3 orders with multiple items each
        unique_orders_query = Mock()
        unique_orders_query.distinct().all.return_value = [
            (1,),  # Order 1
            (2,),  # Order 2
            (3,),  # Order 3
        ]
        
        # Setup the join query for unique orders
        order_item_query = Mock()
        order_item_query.join().filter().return_value = unique_orders_query
        db_session.query(OrderItem.order_id).return_value = order_item_query
        
        # Mock completed items
        items_query.filter().all.return_value = []
        
        # Mock helper methods
        with patch.object(service, "_get_peak_hours", return_value=[]):
            with patch.object(service, "_identify_bottlenecks", return_value=[]):
                with patch.object(service, "_get_staff_rankings", return_value=[]):
                    with patch.object(service, "_get_hourly_throughput", return_value={}):
                        with patch.object(service, "_get_daily_trends", return_value={}):
                            with patch.object(service, "_calculate_efficiency_score", return_value=75.0):
                                # Get analytics
                                analytics = service.get_kitchen_analytics(1, TimeRange.TODAY)
        
        # Verify correct order count
        assert analytics.total_orders == 3  # 3 unique orders, not 10 items
        assert analytics.total_items == 10  # 10 items total
    
    def test_order_counting_with_multiple_items_per_order(self):
        """Test order counting when orders have multiple items"""
        db_session = Mock(spec=Session)
        service = KDSPerformanceService(db_session)
        
        # Mock stations
        db_session.query(KitchenStation).all.return_value = []
        
        # Mock total items
        items_query = Mock()
        items_query.count.return_value = 15  # 15 items total
        db_session.query(KDSOrderItem).filter().return_value = items_query
        
        # Mock unique orders - only 5 orders despite 15 items
        unique_orders_query = Mock()
        unique_orders_query.distinct().all.return_value = [
            (1,), (2,), (3,), (4,), (5,)
        ]
        
        order_item_query = Mock()
        order_item_query.join().filter().return_value = unique_orders_query
        db_session.query(OrderItem.order_id).return_value = order_item_query
        
        # Mock completed items
        items_query.filter().all.return_value = []
        
        # Mock helper methods
        with patch.object(service, "_get_peak_hours", return_value=[]):
            with patch.object(service, "_identify_bottlenecks", return_value=[]):
                with patch.object(service, "_get_staff_rankings", return_value=[]):
                    with patch.object(service, "_get_hourly_throughput", return_value={}):
                        with patch.object(service, "_get_daily_trends", return_value={}):
                            with patch.object(service, "_calculate_efficiency_score", return_value=0):
                                analytics = service.get_kitchen_analytics(1, TimeRange.TODAY)
        
        # Verify
        assert analytics.total_orders == 5
        assert analytics.total_items == 15


class TestStationDataLoading:
    """Test station data loading in real-time metrics"""
    
    def test_real_time_metrics_loads_station_data(self):
        """Test that station data is properly loaded for real-time metrics"""
        db_session = Mock(spec=Session)
        service = KDSPerformanceService(db_session)
        
        # Create mock items with station data
        items = []
        for i in range(3):
            item = Mock(spec=KDSOrderItem)
            item.id = i + 1
            item.received_at = datetime.utcnow() - timedelta(minutes=i*5)
            item.status = DisplayStatus.PENDING
            
            # Mock station with thresholds
            station = Mock(spec=KitchenStation)
            station.warning_time_minutes = 5
            station.critical_time_minutes = 10
            item.station = station
            
            items.append(item)
        
        # Make the oldest item critical (15 minutes old)
        items[2].received_at = datetime.utcnow() - timedelta(minutes=15)
        
        # Mock query with joinedload
        query_mock = Mock()
        query_mock.options().filter().all.return_value = items
        query_mock.filter().count.return_value = 0  # For status counts
        db_session.query().options.return_value = query_mock
        db_session.query().filter.return_value = query_mock
        
        # Get metrics
        metrics = service.get_real_time_metrics()
        
        # Verify critical items were identified
        assert len(metrics["critical_items"]) > 0
        assert metrics["critical_items"][0]["id"] == 3  # The oldest item
    
    def test_display_items_loads_station_data(self):
        """Test that station data is loaded for display items"""
        db_session = Mock(spec=Session)
        service = KDSRealtimeService(db_session)
        
        # Create mock item with station
        item = Mock(spec=KDSOrderItem)
        item.id = 1
        item.order_item_id = 101
        item.display_name = "Test Item"
        item.quantity = 1
        item.modifiers = []
        item.special_instructions = None
        item.status = DisplayStatus.PENDING
        item.priority = 10
        item.course_number = 1
        item.received_at = datetime.utcnow() - timedelta(minutes=12)
        item.target_time = datetime.utcnow() + timedelta(minutes=3)
        item.is_late = False
        item.recall_count = 0
        item.fire_time = None
        
        # Mock station attached to item
        station = Mock(spec=KitchenStation)
        station.warning_time_minutes = 5
        station.critical_time_minutes = 10
        item.station = station
        
        # Mock query with options
        query_mock = Mock()
        query_mock.options().filter().order_by().limit().all.return_value = [item]
        db_session.query().options.return_value = query_mock
        
        # Mock order item and order lookups
        db_session.query(OrderItem).filter_by().first.return_value = None
        
        # Get display items
        display_items = service.get_station_display_items(1)
        
        # Verify display status was determined correctly
        assert len(display_items) == 1
        assert display_items[0]["display_status"] == "critical"  # 12 minutes > 10 minute threshold
    
    def test_display_items_fallback_when_no_station_loaded(self):
        """Test fallback to fetching station when not preloaded"""
        db_session = Mock(spec=Session)
        service = KDSRealtimeService(db_session)
        
        # Create mock item WITHOUT station preloaded
        item = Mock(spec=KDSOrderItem)
        item.id = 1
        item.order_item_id = 101
        item.display_name = "Test Item"
        item.quantity = 1
        item.modifiers = []
        item.special_instructions = None
        item.status = DisplayStatus.PENDING
        item.priority = 10
        item.course_number = 1
        item.received_at = datetime.utcnow() - timedelta(minutes=7)
        item.target_time = datetime.utcnow() + timedelta(minutes=8)
        item.is_late = False
        item.recall_count = 0
        item.fire_time = None
        item.station = None  # No station preloaded
        
        # Mock query
        query_mock = Mock()
        query_mock.options().filter().order_by().limit().all.return_value = [item]
        db_session.query().options.return_value = query_mock
        
        # Mock fallback station fetch
        fallback_station = Mock(spec=KitchenStation)
        fallback_station.warning_time_minutes = 5
        fallback_station.critical_time_minutes = 10
        db_session.query(KitchenStation).filter_by().first.return_value = fallback_station
        
        # Mock order item
        db_session.query(OrderItem).filter_by().first.return_value = None
        
        # Get display items
        display_items = service.get_station_display_items(1)
        
        # Verify display status was determined using fallback
        assert len(display_items) == 1
        assert display_items[0]["display_status"] == "warning"  # 7 minutes > 5 minute warning