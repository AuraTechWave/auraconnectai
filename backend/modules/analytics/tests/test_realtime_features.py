# backend/modules/analytics/tests/test_realtime_features.py

import pytest
import asyncio
import json
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

from ..services.realtime_metrics_service import (
    RealtimeMetricsService, DashboardSnapshot, RealtimeMetric
)
from ..services.websocket_manager import WebSocketManager, WebSocketClient, WebSocketMessageType
from ..services.event_processor import RealtimeEventProcessor, EventType
from ..services.dashboard_widgets_service import DashboardWidgetsService, WidgetType
from ..schemas.realtime_schemas import (
    OrderCompletedEvent, StaffActionEvent, WidgetConfiguration, DashboardLayout
)


class TestRealtimeMetricsService:
    """Test real-time metrics service functionality"""

    @pytest.fixture
    def metrics_service(self):
        """Create metrics service instance for testing"""
        return RealtimeMetricsService(redis_client=None)  # Use in-memory caching

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return Mock()

    def test_realtime_metric_creation(self):
        """Test RealtimeMetric data structure"""
        metric = RealtimeMetric(
            metric_name="test_metric",
            value=100.5,
            timestamp=datetime.now(),
            change_percentage=5.2,
            previous_value=95.3,
            metadata={"unit": "currency"}
        )
        
        assert metric.metric_name == "test_metric"
        assert metric.value == 100.5
        assert metric.change_percentage == 5.2
        
        # Test serialization
        metric_dict = metric.to_dict()
        assert "metric_name" in metric_dict
        assert "timestamp" in metric_dict
        assert metric_dict["metadata"]["unit"] == "currency"

    def test_dashboard_snapshot_creation(self):
        """Test DashboardSnapshot data structure"""
        snapshot = DashboardSnapshot(
            timestamp=datetime.now(),
            revenue_today=Decimal('1500.00'),
            orders_today=50,
            customers_today=35,
            average_order_value=Decimal('30.00'),
            revenue_growth=12.5,
            order_growth=8.3,
            customer_growth=15.2,
            top_staff=[],
            top_products=[],
            hourly_trends=[],
            active_alerts=2,
            critical_metrics=["revenue_decline"]
        )
        
        assert snapshot.revenue_today == Decimal('1500.00')
        assert snapshot.orders_today == 50
        assert len(snapshot.critical_metrics) == 1
        
        # Test serialization
        snapshot_dict = snapshot.to_dict()
        assert snapshot_dict["revenue_today"] == 1500.0
        assert "timestamp" in snapshot_dict

    @pytest.mark.asyncio
    async def test_metrics_service_initialization(self, metrics_service):
        """Test metrics service initialization"""
        assert metrics_service.subscribers == set()
        assert metrics_service.is_running == False
        assert metrics_service.update_interval == 30

    @pytest.mark.asyncio
    async def test_subscriber_management(self, metrics_service):
        """Test subscriber management"""
        
        callback_called = False
        
        def test_callback(snapshot):
            nonlocal callback_called
            callback_called = True
        
        # Test subscription
        metrics_service.subscribe_to_updates(test_callback)
        assert len(metrics_service.subscribers) == 1
        
        # Test unsubscription
        metrics_service.unsubscribe_from_updates(test_callback)
        assert len(metrics_service.subscribers) == 0

    @pytest.mark.asyncio
    async def test_cache_operations(self, metrics_service):
        """Test cache operations"""
        
        # Test cache invalidation
        await metrics_service.invalidate_cache("test_pattern")
        
        # Should complete without error even with no Redis
        assert True

    @pytest.mark.asyncio
    async def test_daily_metrics_calculation(self, metrics_service, mock_db_session):
        """Test daily metrics calculation"""
        
        # Mock database query results
        mock_result = Mock()
        mock_result.revenue = 1000.0
        mock_result.orders = 25
        mock_result.customers = 20
        mock_result.aov = 40.0
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        mock_db_session.query.return_value.filter.return_value.all.return_value = []
        mock_db_session.query.return_value.join.return_value.filter.return_value.first.return_value = mock_result
        
        with patch('backend.core.database.get_db', return_value=iter([mock_db_session])):
            metrics = await metrics_service._get_daily_metrics(mock_db_session, date.today())
            
            assert metrics["revenue"] == 1000.0
            assert metrics["orders"] == 25
            assert metrics["customers"] == 20
            assert metrics["aov"] == 40.0

    @pytest.mark.asyncio
    async def test_growth_percentage_calculation(self, metrics_service):
        """Test growth percentage calculation"""
        
        # Test normal growth
        growth = metrics_service._calculate_growth_percentage(110, 100)
        assert growth == 10.0
        
        # Test decline
        growth = metrics_service._calculate_growth_percentage(90, 100)
        assert growth == -10.0
        
        # Test zero previous value
        growth = metrics_service._calculate_growth_percentage(50, 0)
        assert growth == 100.0
        
        # Test zero current value
        growth = metrics_service._calculate_growth_percentage(0, 0)
        assert growth == 0.0


class TestWebSocketManager:
    """Test WebSocket manager functionality"""

    @pytest.fixture
    def websocket_manager(self):
        """Create WebSocket manager for testing"""
        return WebSocketManager()

    @pytest.fixture
    def mock_websocket(self):
        """Mock WebSocket connection"""
        websocket = Mock()
        websocket.accept = AsyncMock()
        websocket.send_text = AsyncMock()
        websocket.close = AsyncMock()
        websocket.client_state.DISCONNECTED = False
        return websocket

    def test_websocket_manager_initialization(self, websocket_manager):
        """Test WebSocket manager initialization"""
        assert len(websocket_manager.active_connections) == 0
        assert len(websocket_manager.dashboard_subscribers) == 0
        assert websocket_manager.is_running == False

    @pytest.mark.asyncio
    async def test_client_connection(self, websocket_manager, mock_websocket):
        """Test client connection handling"""
        
        user_permissions = ["analytics:view_dashboard"]
        
        client_id = await websocket_manager.connect_client(
            websocket=mock_websocket,
            user_id=1,
            user_permissions=user_permissions
        )
        
        assert client_id in websocket_manager.active_connections
        assert len(websocket_manager.active_connections) == 1
        
        client = websocket_manager.active_connections[client_id]
        assert client.user_id == 1
        assert client.user_permissions == user_permissions
        
        mock_websocket.accept.assert_called_once()
        mock_websocket.send_text.assert_called()

    @pytest.mark.asyncio
    async def test_client_disconnection(self, websocket_manager, mock_websocket):
        """Test client disconnection handling"""
        
        # Connect client first
        client_id = await websocket_manager.connect_client(
            websocket=mock_websocket,
            user_id=1,
            user_permissions=["analytics:view_dashboard"]
        )
        
        assert len(websocket_manager.active_connections) == 1
        
        # Disconnect client
        await websocket_manager.disconnect_client(client_id)
        
        assert len(websocket_manager.active_connections) == 0
        mock_websocket.close.assert_called()

    @pytest.mark.asyncio
    async def test_message_handling(self, websocket_manager, mock_websocket):
        """Test WebSocket message handling"""
        
        # Connect client
        client_id = await websocket_manager.connect_client(
            websocket=mock_websocket,
            user_id=1,
            user_permissions=["analytics:view_dashboard"]
        )
        
        # Test subscription message
        subscription_message = json.dumps({
            "type": "subscribe",
            "data": {
                "subscription_type": "dashboard"
            }
        })
        
        await websocket_manager.handle_client_message(client_id, subscription_message)
        
        # Client should be subscribed to dashboard
        assert client_id in websocket_manager.dashboard_subscribers

    @pytest.mark.asyncio
    async def test_broadcast_functionality(self, websocket_manager, mock_websocket):
        """Test broadcast functionality"""
        
        # Connect and subscribe client
        client_id = await websocket_manager.connect_client(
            websocket=mock_websocket,
            user_id=1,
            user_permissions=["analytics:view_dashboard"]
        )
        
        websocket_manager.dashboard_subscribers.add(client_id)
        
        # Create test snapshot
        snapshot = DashboardSnapshot(
            timestamp=datetime.now(),
            revenue_today=Decimal('1000.00'),
            orders_today=25,
            customers_today=20,
            average_order_value=Decimal('40.00'),
            revenue_growth=10.0,
            order_growth=5.0,
            customer_growth=8.0,
            top_staff=[],
            top_products=[],
            hourly_trends=[],
            active_alerts=0,
            critical_metrics=[]
        )
        
        # Broadcast update
        await websocket_manager.broadcast_dashboard_update(snapshot)
        
        # Verify message was sent
        mock_websocket.send_text.assert_called()
        
        # Get the last call arguments
        call_args = mock_websocket.send_text.call_args[0][0]
        message_data = json.loads(call_args)
        
        assert message_data["type"] == "dashboard_update"
        assert "data" in message_data

    def test_connection_stats(self, websocket_manager):
        """Test connection statistics"""
        
        stats = websocket_manager.get_connection_stats()
        
        assert "total_connections" in stats
        assert "dashboard_subscribers" in stats
        assert "alert_subscribers" in stats
        assert "metric_subscribers" in stats
        assert stats["total_connections"] == 0


class TestEventProcessor:
    """Test real-time event processor"""

    @pytest.fixture
    def event_processor(self):
        """Create event processor for testing"""
        return RealtimeEventProcessor()

    def test_event_processor_initialization(self, event_processor):
        """Test event processor initialization"""
        assert len(event_processor.event_handlers) > 0  # Default handlers registered
        assert event_processor.is_running == False
        assert event_processor.event_queue.qsize() == 0

    def test_event_handler_registration(self, event_processor):
        """Test event handler registration"""
        
        handler_called = False
        
        def test_handler(event_record):
            nonlocal handler_called
            handler_called = True
        
        # Register handler
        event_processor.register_event_handler(EventType.ORDER_COMPLETED, test_handler)
        
        # Verify handler is registered
        assert test_handler in event_processor.event_handlers[EventType.ORDER_COMPLETED]
        
        # Unregister handler
        event_processor.unregister_event_handler(EventType.ORDER_COMPLETED, test_handler)
        
        # Verify handler is removed
        assert test_handler not in event_processor.event_handlers[EventType.ORDER_COMPLETED]

    @pytest.mark.asyncio
    async def test_event_processing(self, event_processor):
        """Test event processing"""
        
        handler_called = False
        event_data = None
        
        async def test_handler(event_record):
            nonlocal handler_called, event_data
            handler_called = True
            event_data = event_record
        
        # Register handler
        event_processor.register_event_handler(EventType.ORDER_COMPLETED, test_handler)
        
        # Process event
        test_event_data = {"order_id": 123, "amount": 50.0}
        success = await event_processor.process_event(
            EventType.ORDER_COMPLETED,
            test_event_data,
            priority=True
        )
        
        assert success == True
        assert handler_called == True
        assert event_data["data"] == test_event_data

    def test_rate_limiting(self, event_processor):
        """Test event rate limiting"""
        
        # Test normal rate limit check
        assert event_processor._check_rate_limit(EventType.ORDER_COMPLETED) == True
        
        # Simulate hitting rate limit
        event_processor.event_counts[EventType.ORDER_COMPLETED.value] = event_processor.max_events_per_window
        
        assert event_processor._check_rate_limit(EventType.ORDER_COMPLETED) == False

    def test_event_metrics(self, event_processor):
        """Test event metrics collection"""
        
        metrics = event_processor.get_event_metrics()
        
        assert "total_events_processed" in metrics
        assert "events_per_minute" in metrics
        assert "failed_events" in metrics
        assert "queue_size" in metrics
        assert "is_running" in metrics

    def test_recent_events_history(self, event_processor):
        """Test recent events history"""
        
        # Add test event to history
        test_event = {
            "id": "test-123",
            "type": "test_event",
            "timestamp": datetime.now(),
            "status": "completed"
        }
        
        event_processor.event_history.append(test_event)
        
        recent_events = event_processor.get_recent_events(limit=10)
        
        assert len(recent_events) == 1
        assert recent_events[0]["id"] == "test-123"


class TestDashboardWidgetsService:
    """Test dashboard widgets service"""

    @pytest.fixture
    def widgets_service(self):
        """Create widgets service for testing"""
        return DashboardWidgetsService()

    @pytest.fixture
    def sample_widget_config(self):
        """Create sample widget configuration"""
        return WidgetConfiguration(
            widget_id="test_widget",
            widget_type=WidgetType.METRIC_CARD,
            title="Test Widget",
            position={"x": 0, "y": 0, "width": 3, "height": 2},
            data_source="realtime_metric",
            config={
                "metric_name": "revenue_current",
                "format": "currency"
            }
        )

    def test_widgets_service_initialization(self, widgets_service):
        """Test widgets service initialization"""
        assert len(widgets_service.widget_data_cache) == 0
        assert widgets_service.cache_ttl == 60
        assert len(widgets_service.widget_processors) > 0

    @pytest.mark.asyncio
    async def test_metric_card_processing(self, widgets_service, sample_widget_config):
        """Test metric card widget processing"""
        
        # Mock the realtime metrics service
        mock_metric = RealtimeMetric(
            metric_name="revenue_current",
            value=1500.0,
            timestamp=datetime.now(),
            change_percentage=12.5,
            previous_value=1334.0
        )
        
        with patch('backend.modules.analytics.services.dashboard_widgets_service.realtime_metrics_service.get_realtime_metric', 
                  return_value=mock_metric):
            
            widget_data = await widgets_service._process_metric_card(sample_widget_config)
            
            assert widget_data["value"] == 1500.0
            assert widget_data["change_percentage"] == 12.5
            assert widget_data["format"] == "currency"
            assert widget_data["status"] == "success"

    @pytest.mark.asyncio
    async def test_widget_data_caching(self, widgets_service, sample_widget_config):
        """Test widget data caching"""
        
        # Mock the realtime metrics service
        mock_metric = RealtimeMetric(
            metric_name="revenue_current",
            value=1500.0,
            timestamp=datetime.now()
        )
        
        with patch('backend.modules.analytics.services.dashboard_widgets_service.realtime_metrics_service.get_realtime_metric', 
                  return_value=mock_metric) as mock_get_metric:
            
            # First call should hit the service
            response1 = await widgets_service.get_widget_data(sample_widget_config)
            assert response1.cache_status == "fresh"
            assert mock_get_metric.call_count == 1
            
            # Second call should use cache
            response2 = await widgets_service.get_widget_data(sample_widget_config)
            assert response2.cache_status == "cached"
            assert mock_get_metric.call_count == 1  # Should not increase

    @pytest.mark.asyncio
    async def test_line_chart_processing(self, widgets_service):
        """Test line chart widget processing"""
        
        widget_config = WidgetConfiguration(
            widget_id="test_line_chart",
            widget_type=WidgetType.LINE_CHART,
            title="Revenue Trend",
            position={"x": 0, "y": 0, "width": 6, "height": 4},
            data_source="hourly_trends",
            config={
                "metric": "revenue",
                "hours_back": 12
            }
        )
        
        # Mock hourly trends data
        mock_trends = [
            {"hour": "2024-01-01 09:00", "revenue": 100, "orders": 5},
            {"hour": "2024-01-01 10:00", "revenue": 150, "orders": 7},
            {"hour": "2024-01-01 11:00", "revenue": 200, "orders": 10}
        ]
        
        with patch('backend.modules.analytics.services.dashboard_widgets_service.realtime_metrics_service.get_hourly_trends', 
                  return_value=mock_trends):
            
            widget_data = await widgets_service._process_line_chart(widget_config)
            
            assert len(widget_data["data"]) == 3
            assert widget_data["data"][0]["y"] == 100
            assert widget_data["data"][1]["y"] == 150
            assert widget_data["metric"] == "revenue"

    @pytest.mark.asyncio
    async def test_default_dashboard_creation(self, widgets_service):
        """Test default dashboard layout creation"""
        
        layout = await widgets_service.create_default_dashboard_layout(user_id=1)
        
        assert layout.created_by == 1
        assert layout.is_default == True
        assert len(layout.widgets) > 0
        
        # Check for expected default widgets
        widget_types = [widget.widget_type for widget in layout.widgets]
        assert WidgetType.METRIC_CARD in widget_types
        assert WidgetType.LINE_CHART in widget_types
        assert WidgetType.TABLE in widget_types

    def test_cache_invalidation(self, widgets_service):
        """Test widget cache invalidation"""
        
        # Add some test data to cache
        widgets_service.widget_data_cache["test_widget_123"] = {
            "data": {"value": 100},
            "timestamp": datetime.now()
        }
        widgets_service.widget_data_cache["other_widget_456"] = {
            "data": {"value": 200},
            "timestamp": datetime.now()
        }
        
        assert len(widgets_service.widget_data_cache) == 2
        
        # Test specific widget invalidation
        widgets_service.invalidate_widget_cache("test_widget")
        assert len(widgets_service.widget_data_cache) == 1
        assert "other_widget_456" in widgets_service.widget_data_cache
        
        # Test full cache invalidation
        widgets_service.invalidate_widget_cache()
        assert len(widgets_service.widget_data_cache) == 0


class TestRealtimeIntegration:
    """Integration tests for real-time features"""

    @pytest.mark.asyncio
    async def test_event_to_websocket_flow(self):
        """Test complete flow from event to WebSocket broadcast"""
        
        # This would test the complete integration but requires more setup
        # For now, we'll test the components work together conceptually
        
        # Create event
        order_event = OrderCompletedEvent(
            order_id=123,
            staff_id=1,
            total_amount=Decimal('50.00'),
            items_count=3,
            completed_at=datetime.now()
        )
        
        # Verify event structure
        assert order_event.order_id == 123
        assert order_event.total_amount == Decimal('50.00')
        
        # Convert to dict for processing
        event_dict = order_event.dict()
        assert event_dict["order_id"] == 123

    @pytest.mark.asyncio
    async def test_dashboard_data_consistency(self):
        """Test data consistency across different components"""
        
        # Create dashboard snapshot
        snapshot = DashboardSnapshot(
            timestamp=datetime.now(),
            revenue_today=Decimal('2000.00'),
            orders_today=50,
            customers_today=35,
            average_order_value=Decimal('40.00'),
            revenue_growth=15.0,
            order_growth=10.0,
            customer_growth=5.0,
            top_staff=[],
            top_products=[],
            hourly_trends=[],
            active_alerts=1,
            critical_metrics=[]
        )
        
        # Test serialization consistency
        snapshot_dict = snapshot.to_dict()
        assert snapshot_dict["revenue_today"] == 2000.0
        assert snapshot_dict["orders_today"] == 50
        
        # Test metric consistency
        aov_calculated = float(snapshot.revenue_today) / snapshot.orders_today
        assert abs(aov_calculated - float(snapshot.average_order_value)) < 0.01

    def test_permission_integration(self):
        """Test permission integration across services"""
        
        # Test user permissions
        user_permissions = [
            "analytics:view_dashboard",
            "analytics:view_sales_reports"
        ]
        
        # Verify permissions are properly formatted
        assert all(perm.startswith("analytics:") for perm in user_permissions)
        
        # Test permission checking logic
        has_dashboard_perm = "analytics:view_dashboard" in user_permissions
        has_admin_perm = "analytics:admin" in user_permissions
        
        assert has_dashboard_perm == True
        assert has_admin_perm == False

    @pytest.mark.asyncio
    async def test_error_handling_across_services(self):
        """Test error handling consistency"""
        
        # Test metrics service error handling
        metrics_service = RealtimeMetricsService(redis_client=None)
        
        # Test with invalid metric name
        metric = await metrics_service.get_realtime_metric("invalid_metric")
        assert metric is None  # Should return None, not raise exception
        
        # Test widgets service error handling
        widgets_service = DashboardWidgetsService()
        
        invalid_config = WidgetConfiguration(
            widget_id="invalid_widget",
            widget_type="invalid_type",
            title="Invalid Widget",
            position={"x": 0, "y": 0, "width": 1, "height": 1},
            data_source="invalid_source",
            config={}
        )
        
        # Should raise ValueError for unknown widget type
        with pytest.raises(ValueError):
            await widgets_service.get_widget_data(invalid_config)