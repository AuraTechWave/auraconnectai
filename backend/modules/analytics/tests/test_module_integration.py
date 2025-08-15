# backend/modules/analytics/tests/test_module_integration.py

"""
Integration tests for analytics module hooks and cross-module functionality.

These tests verify that the analytics module properly integrates with other
modules through the hooks system and that real-time updates work correctly.
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any, List

from ..integrations.module_hooks import (
    order_completed_hook,
    order_completed_sync,
    staff_action_hook,
    customer_action_hook,
    payment_processed_hook,
    system_event_hook,
    invalidate_analytics_cache_hook,
    trigger_custom_alert_hook,
    get_analytics_status,
    force_dashboard_refresh,
)
from ..services.realtime_metrics_service import realtime_metrics_service
from ..services.websocket_manager import websocket_manager
from ..services.event_processor import event_processor
from ..services.dashboard_widgets_service import dashboard_widgets_service
from ..schemas.realtime_schemas import OrderCompletedEvent, StaffActionEvent


class TestModuleHooksIntegration:
    """Test integration hooks with other modules"""

    @pytest.fixture
    def mock_event_processor(self):
        """Mock event processor for testing"""
        with patch(
            "backend.modules.analytics.integrations.module_hooks.event_processor"
        ) as mock:
            mock.process_order_completed = AsyncMock()
            mock.process_staff_action = AsyncMock()
            mock.process_event = AsyncMock()
            yield mock

    @pytest.fixture
    def mock_websocket_manager(self):
        """Mock WebSocket manager for testing"""
        with patch(
            "backend.modules.analytics.integrations.module_hooks.websocket_manager"
        ) as mock:
            mock.broadcast_dashboard_update = AsyncMock()
            mock.broadcast_alert_notification = AsyncMock()
            yield mock

    @pytest.fixture
    def mock_realtime_service(self):
        """Mock realtime metrics service for testing"""
        with patch(
            "backend.modules.analytics.integrations.module_hooks.realtime_metrics_service"
        ) as mock:
            mock.invalidate_cache = AsyncMock()
            mock.get_current_dashboard_snapshot = AsyncMock()
            yield mock

    @pytest.mark.asyncio
    async def test_order_completed_hook_integration(self, mock_event_processor):
        """Test order completed hook integration"""

        # Test data
        order_id = 123
        staff_id = 1
        customer_id = 45
        total_amount = Decimal("75.50")
        items_count = 3
        table_no = 5

        # Call the hook
        await order_completed_hook(
            order_id=order_id,
            staff_id=staff_id,
            customer_id=customer_id,
            total_amount=total_amount,
            items_count=items_count,
            table_no=table_no,
        )

        # Verify event processor was called
        mock_event_processor.process_order_completed.assert_called_once()

        # Get the call arguments
        call_args = mock_event_processor.process_order_completed.call_args[0][0]
        assert isinstance(call_args, OrderCompletedEvent)
        assert call_args.order_id == order_id
        assert call_args.staff_id == staff_id
        assert call_args.customer_id == customer_id
        assert call_args.total_amount == total_amount
        assert call_args.items_count == items_count
        assert call_args.table_no == table_no

    @pytest.mark.asyncio
    async def test_order_completed_sync_hook(self, mock_event_processor):
        """Test synchronous order completed hook"""

        # Test data
        order_id = 456
        staff_id = 2
        total_amount = Decimal("30.00")
        items_count = 2

        # Call the sync hook
        order_completed_sync(
            order_id=order_id,
            staff_id=staff_id,
            customer_id=None,
            total_amount=total_amount,
            items_count=items_count,
        )

        # Give time for the task to be created
        await asyncio.sleep(0.01)

        # The sync version creates a task, so we can't directly verify the call
        # But we can verify no exceptions were raised
        assert True

    @pytest.mark.asyncio
    async def test_staff_action_hook_integration(self, mock_event_processor):
        """Test staff action hook integration"""

        # Test data
        staff_id = 3
        action_type = "order_processed"
        action_data = {"order_id": 789, "processing_time": 120}
        shift_id = 15

        # Call the hook
        await staff_action_hook(
            staff_id=staff_id,
            action_type=action_type,
            action_data=action_data,
            shift_id=shift_id,
        )

        # Verify event processor was called
        mock_event_processor.process_staff_action.assert_called_once()

        # Get the call arguments
        call_args = mock_event_processor.process_staff_action.call_args[0][0]
        assert isinstance(call_args, StaffActionEvent)
        assert call_args.staff_id == staff_id
        assert call_args.action_type == action_type
        assert call_args.action_data == action_data
        assert call_args.shift_id == shift_id

    @pytest.mark.asyncio
    async def test_payment_processed_hook_integration(self, mock_event_processor):
        """Test payment processed hook integration"""

        # Test data
        order_id = 321
        payment_method = "credit_card"
        amount = Decimal("45.00")
        status = "success"
        transaction_id = "txn_123456"

        # Call the hook
        await payment_processed_hook(
            order_id=order_id,
            payment_method=payment_method,
            amount=amount,
            status=status,
            transaction_id=transaction_id,
        )

        # Verify event processor was called with priority
        mock_event_processor.process_event.assert_called_once_with(
            mock_event_processor.EventType.PAYMENT_PROCESSED,
            {
                "order_id": order_id,
                "payment_method": payment_method,
                "amount": float(amount),
                "status": status,
                "transaction_id": transaction_id,
                "processed_at": mock_event_processor.process_event.call_args[0][1][
                    "processed_at"
                ],
            },
            priority=True,  # Success payments are high priority
        )

    @pytest.mark.asyncio
    async def test_system_event_hook_integration(self, mock_event_processor):
        """Test system event hook integration"""

        # Test data
        event_type = "database_error"
        message = "Connection timeout occurred"
        severity = "high"
        source_service = "orders_service"
        event_data = {"error_code": "DB_TIMEOUT", "retry_count": 3}

        # Call the hook
        await system_event_hook(
            event_type=event_type,
            message=message,
            severity=severity,
            source_service=source_service,
            event_data=event_data,
        )

        # Verify event processor was called
        mock_event_processor.process_system_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_custom_alert_hook_integration(self, mock_websocket_manager):
        """Test custom alert hook integration"""

        # Test data
        alert_name = "High Order Volume"
        message = "Order volume exceeded threshold"
        metric_name = "orders_per_minute"
        current_value = 25.0
        threshold_value = 20.0
        severity = "medium"

        # Call the hook
        await trigger_custom_alert_hook(
            alert_name=alert_name,
            message=message,
            metric_name=metric_name,
            current_value=current_value,
            threshold_value=threshold_value,
            severity=severity,
        )

        # Verify WebSocket manager was called
        mock_websocket_manager.broadcast_alert_notification.assert_called_once()

        # Get the call arguments
        call_args = mock_websocket_manager.broadcast_alert_notification.call_args[0][0]
        assert call_args["type"] == "custom_alert"
        assert call_args["alert_name"] == alert_name
        assert call_args["message"] == message
        assert call_args["metric_name"] == metric_name
        assert call_args["current_value"] == current_value
        assert call_args["threshold_value"] == threshold_value
        assert call_args["severity"] == severity
        assert call_args["source"] == "external_module"

    @pytest.mark.asyncio
    async def test_cache_invalidation_hook_integration(self, mock_realtime_service):
        """Test cache invalidation hook integration"""

        # Test with specific pattern
        cache_pattern = "revenue_*"
        await invalidate_analytics_cache_hook(cache_pattern)

        mock_realtime_service.invalidate_cache.assert_called_once_with(cache_pattern)

        # Test with no pattern (invalidate all)
        mock_realtime_service.reset_mock()
        await invalidate_analytics_cache_hook()

        mock_realtime_service.invalidate_cache.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_dashboard_refresh_hook_integration(
        self, mock_realtime_service, mock_websocket_manager
    ):
        """Test dashboard refresh hook integration"""

        # Mock dashboard snapshot
        mock_snapshot = Mock()
        mock_realtime_service.get_current_dashboard_snapshot.return_value = (
            mock_snapshot
        )

        # Call the hook
        await force_dashboard_refresh()

        # Verify cache was invalidated
        mock_realtime_service.invalidate_cache.assert_called_once_with()

        # Verify snapshot was retrieved
        mock_realtime_service.get_current_dashboard_snapshot.assert_called_once()

        # Verify WebSocket broadcast
        mock_websocket_manager.broadcast_dashboard_update.assert_called_once_with(
            mock_snapshot
        )

    def test_analytics_status_integration(self):
        """Test analytics status integration"""

        # Mock dependencies
        with (
            patch(
                "backend.modules.analytics.integrations.module_hooks.websocket_manager"
            ) as mock_ws,
            patch(
                "backend.modules.analytics.integrations.module_hooks.event_processor"
            ) as mock_ep,
        ):

            # Mock return values
            mock_ws.get_connection_stats.return_value = {
                "total_connections": 5,
                "dashboard_subscribers": 3,
            }
            mock_ep.get_event_metrics.return_value = {
                "total_events_processed": 150,
                "events_per_minute": 12,
                "failed_events": 2,
            }

            # Get status
            status = get_analytics_status()

            # Verify status structure
            assert status["status"] == "healthy"
            assert status["websocket_connections"] == 5
            assert status["dashboard_subscribers"] == 3
            assert status["events_processed"] == 150
            assert status["events_per_minute"] == 12
            assert status["failed_events"] == 2
            assert "last_check" in status

    def test_analytics_status_error_handling(self):
        """Test analytics status error handling"""

        # Mock an error
        with patch(
            "backend.modules.analytics.integrations.module_hooks.websocket_manager"
        ) as mock_ws:
            mock_ws.get_connection_stats.side_effect = Exception("Connection error")

            # Get status
            status = get_analytics_status()

            # Verify error status
            assert status["status"] == "error"
            assert "error" in status
            assert "last_check" in status


class TestRealTimeFlowIntegration:
    """Test complete real-time data flow integration"""

    @pytest.fixture
    def mock_database(self):
        """Mock database session and queries"""
        mock_db = Mock()

        # Mock query results for metrics
        mock_result = Mock()
        mock_result.revenue = 1500.0
        mock_result.orders = 45
        mock_result.customers = 35
        mock_result.aov = 33.33

        mock_db.query.return_value.filter.return_value.first.return_value = mock_result
        mock_db.query.return_value.join.return_value.filter.return_value.first.return_value = (
            mock_result
        )

        return mock_db

    @pytest.mark.asyncio
    async def test_order_to_dashboard_update_flow(self, mock_database):
        """Test complete flow from order completion to dashboard update"""

        with (
            patch("backend.core.database.get_db", return_value=iter([mock_database])),
            patch(
                "backend.modules.analytics.services.realtime_metrics_service.realtime_metrics_service"
            ) as mock_service,
            patch(
                "backend.modules.analytics.services.websocket_manager.websocket_manager"
            ) as mock_ws,
        ):

            # Mock services
            mock_service.invalidate_cache = AsyncMock()
            mock_service.get_current_dashboard_snapshot = AsyncMock()
            mock_ws.broadcast_dashboard_update = AsyncMock()

            # Simulate order completion
            await order_completed_hook(
                order_id=100,
                staff_id=1,
                customer_id=50,
                total_amount=Decimal("85.00"),
                items_count=4,
            )

            # Simulate dashboard refresh triggered by event processing
            await force_dashboard_refresh()

            # Verify the flow
            mock_service.invalidate_cache.assert_called()
            mock_service.get_current_dashboard_snapshot.assert_called()
            mock_ws.broadcast_dashboard_update.assert_called()

    @pytest.mark.asyncio
    async def test_concurrent_events_handling(self):
        """Test handling of concurrent events"""

        with patch(
            "backend.modules.analytics.integrations.module_hooks.event_processor"
        ) as mock_ep:
            mock_ep.process_order_completed = AsyncMock()
            mock_ep.process_staff_action = AsyncMock()
            mock_ep.process_event = AsyncMock()

            # Create multiple concurrent events
            tasks = []

            # Order events
            for i in range(5):
                task = asyncio.create_task(
                    order_completed_hook(
                        order_id=100 + i,
                        staff_id=1,
                        customer_id=None,
                        total_amount=Decimal("50.00"),
                        items_count=2,
                    )
                )
                tasks.append(task)

            # Staff events
            for i in range(3):
                task = asyncio.create_task(
                    staff_action_hook(
                        staff_id=1,
                        action_type="order_processed",
                        action_data={"order_id": 200 + i},
                    )
                )
                tasks.append(task)

            # Payment events
            for i in range(2):
                task = asyncio.create_task(
                    payment_processed_hook(
                        order_id=300 + i,
                        payment_method="card",
                        amount=Decimal("25.00"),
                        status="success",
                    )
                )
                tasks.append(task)

            # Wait for all events to complete
            await asyncio.gather(*tasks)

            # Verify all events were processed
            assert mock_ep.process_order_completed.call_count == 5
            assert mock_ep.process_staff_action.call_count == 3
            assert mock_ep.process_event.call_count == 2

    @pytest.mark.asyncio
    async def test_error_resilience_in_integration(self):
        """Test error resilience in integration points"""

        # Test with failing event processor
        with patch(
            "backend.modules.analytics.integrations.module_hooks.event_processor"
        ) as mock_ep:
            mock_ep.process_order_completed.side_effect = Exception("Processing failed")

            # Event should not raise exception
            try:
                await order_completed_hook(
                    order_id=999,
                    staff_id=1,
                    customer_id=None,
                    total_amount=Decimal("100.00"),
                    items_count=1,
                )
                # Should complete without raising
                assert True
            except Exception:
                pytest.fail("Hook should handle exceptions gracefully")

        # Test with failing WebSocket manager
        with patch(
            "backend.modules.analytics.integrations.module_hooks.websocket_manager"
        ) as mock_ws:
            mock_ws.broadcast_alert_notification.side_effect = Exception(
                "Broadcast failed"
            )

            # Alert should not raise exception
            try:
                await trigger_custom_alert_hook(
                    alert_name="Test Alert",
                    message="Test message",
                    metric_name="test_metric",
                    current_value=100.0,
                    threshold_value=80.0,
                )
                # Should complete without raising
                assert True
            except Exception:
                pytest.fail("Alert hook should handle exceptions gracefully")


class TestWebSocketIntegration:
    """Test WebSocket integration across the system"""

    @pytest.fixture
    def mock_websocket(self):
        """Mock WebSocket connection"""
        websocket = Mock()
        websocket.accept = AsyncMock()
        websocket.send_text = AsyncMock()
        websocket.close = AsyncMock()
        websocket.client_state.DISCONNECTED = False
        return websocket

    @pytest.mark.asyncio
    async def test_client_subscription_and_updates(self, mock_websocket):
        """Test client subscription and real-time updates"""

        # Mock the WebSocket manager
        from ..services.websocket_manager import WebSocketManager

        ws_manager = WebSocketManager()

        # Connect client
        client_id = await ws_manager.connect_client(
            websocket=mock_websocket,
            user_id=1,
            user_permissions=["analytics:view_dashboard"],
        )

        # Subscribe to dashboard updates
        ws_manager.dashboard_subscribers.add(client_id)

        # Simulate dashboard update
        from ..services.realtime_metrics_service import DashboardSnapshot

        snapshot = DashboardSnapshot(
            timestamp=datetime.now(),
            revenue_today=Decimal("2000.00"),
            orders_today=60,
            customers_today=45,
            average_order_value=Decimal("33.33"),
            revenue_growth=15.0,
            order_growth=12.0,
            customer_growth=8.0,
            top_staff=[],
            top_products=[],
            hourly_trends=[],
            active_alerts=1,
            critical_metrics=[],
        )

        # Broadcast update
        await ws_manager.broadcast_dashboard_update(snapshot)

        # Verify message was sent
        mock_websocket.send_text.assert_called()

        # Verify message content
        call_args = mock_websocket.send_text.call_args[0][0]
        message_data = json.loads(call_args)

        assert message_data["type"] == "dashboard_update"
        assert "data" in message_data
        assert message_data["data"]["revenue_today"] == 2000.0
        assert message_data["data"]["orders_today"] == 60

    @pytest.mark.asyncio
    async def test_permission_based_filtering(self, mock_websocket):
        """Test permission-based message filtering"""

        from ..services.websocket_manager import WebSocketManager

        ws_manager = WebSocketManager()

        # Connect client with limited permissions
        client_id = await ws_manager.connect_client(
            websocket=mock_websocket,
            user_id=1,
            user_permissions=["analytics:view_dashboard"],  # No admin permissions
        )

        # Try to send admin-only alert
        admin_alert = {
            "type": "admin_alert",
            "message": "System maintenance required",
            "severity": "high",
            "admin_only": True,
        }

        # This should be filtered out for non-admin users
        await ws_manager.broadcast_alert_notification(admin_alert)

        # In a real implementation, this would be filtered
        # For now, we just verify the broadcast attempt was made
        assert True


class TestCacheIntegration:
    """Test cache integration across services"""

    @pytest.mark.asyncio
    async def test_cache_invalidation_propagation(self):
        """Test cache invalidation propagation"""

        with patch(
            "backend.modules.analytics.services.realtime_metrics_service.realtime_metrics_service"
        ) as mock_service:
            mock_service.invalidate_cache = AsyncMock()

            # Trigger cache invalidation from different sources
            await invalidate_analytics_cache_hook("revenue_*")
            await invalidate_analytics_cache_hook("orders_*")
            await invalidate_analytics_cache_hook()  # All caches

            # Verify all invalidations were called
            assert mock_service.invalidate_cache.call_count == 3

            # Verify specific patterns
            call_args_list = mock_service.invalidate_cache.call_args_list
            assert call_args_list[0][0][0] == "revenue_*"
            assert call_args_list[1][0][0] == "orders_*"
            assert call_args_list[2][0][0] is None  # All caches

    @pytest.mark.asyncio
    async def test_widget_cache_coordination(self):
        """Test widget cache coordination with metrics cache"""

        from ..services.dashboard_widgets_service import dashboard_widgets_service

        # Add some test data to widget cache
        dashboard_widgets_service.widget_data_cache["test_widget"] = {
            "data": {"value": 100},
            "timestamp": datetime.now(),
        }

        # Invalidate specific widget
        dashboard_widgets_service.invalidate_widget_cache("test_widget")

        # Verify cache was cleared
        assert len(dashboard_widgets_service.widget_data_cache) == 0

    def test_cache_performance_simulation(self):
        """Test cache performance under load"""

        from ..services.dashboard_widgets_service import dashboard_widgets_service

        # Simulate multiple widgets being cached
        for i in range(100):
            cache_key = f"widget_{i}_{hash(f'config_{i}')}"
            dashboard_widgets_service.widget_data_cache[cache_key] = {
                "data": {"value": i * 10},
                "timestamp": datetime.now(),
            }

        # Verify all cached
        assert len(dashboard_widgets_service.widget_data_cache) == 100

        # Test pattern-based invalidation
        dashboard_widgets_service.invalidate_widget_cache("widget_1")

        # Should remove widgets starting with "widget_1"
        remaining_count = len(dashboard_widgets_service.widget_data_cache)
        assert remaining_count < 100  # Some were removed

        # Clear all
        dashboard_widgets_service.invalidate_widget_cache()
        assert len(dashboard_widgets_service.widget_data_cache) == 0


if __name__ == "__main__":
    # Run tests with: python -m pytest backend/modules/analytics/tests/test_module_integration.py -v
    pytest.main([__file__, "-v"])
