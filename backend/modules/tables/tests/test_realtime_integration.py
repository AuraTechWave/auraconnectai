# backend/modules/tables/tests/test_realtime_integration.py

"""
Integration tests for table real-time features
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect
from unittest.mock import AsyncMock, patch
import json

from app.main import app
from ..services.realtime_table_service import realtime_table_service, TurnTimeAlert
from ..models.table_models import TableStatus


class TestRealtimeAPIEndpoints:
    """Test real-time API endpoints"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        # Mock authentication for testing
        return {"Authorization": "Bearer test-token"}

    def test_get_turn_time_alerts_endpoint(self, client, auth_headers):
        """Test turn time alerts API endpoint"""
        with patch('modules.tables.routers.realtime_table_router.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "role": "manager"}
            
            with patch('modules.tables.routers.realtime_table_router.realtime_table_service.get_turn_time_alerts') as mock_alerts:
                mock_alerts.return_value = []
                
                response = client.get(
                    "/api/v1/tables/realtime/turn-alerts/1",
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "alerts" in data["data"]
                assert "summary" in data["data"]

    def test_get_occupancy_summary_endpoint(self, client, auth_headers):
        """Test occupancy summary API endpoint"""
        with patch('modules.tables.routers.realtime_table_router.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "role": "manager"}
            
            with patch('modules.tables.routers.realtime_table_router.realtime_table_service.get_occupancy_summary') as mock_occupancy:
                mock_occupancy.return_value = {
                    "total_tables": 20,
                    "occupied_tables": 12,
                    "available_tables": 8,
                    "occupancy_rate": 60.0,
                }
                
                response = client.get(
                    "/api/v1/tables/realtime/occupancy/1",
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["data"]["total_tables"] == 20

    def test_get_heat_map_data_endpoint(self, client, auth_headers):
        """Test heat map data API endpoint"""
        with patch('modules.tables.routers.realtime_table_router.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "role": "manager"}
            
            with patch('modules.tables.routers.realtime_table_router.realtime_table_service.get_heat_map_data') as mock_heat_map:
                mock_heat_map.return_value = []
                
                response = client.get(
                    "/api/v1/tables/realtime/heat-map/1?period=today",
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "heat_map" in data["data"]
                assert "summary" in data["data"]

    def test_start_monitoring_endpoint(self, client, auth_headers):
        """Test start monitoring API endpoint"""
        with patch('modules.tables.routers.realtime_table_router.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "role": "admin"}
            
            with patch('modules.tables.routers.realtime_table_router.realtime_table_service.start_monitoring') as mock_start:
                mock_start.return_value = None
                
                response = client.post(
                    "/api/v1/tables/realtime/monitoring/start/1",
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "monitoring started" in data["message"]

    def test_get_live_status_endpoint(self, client, auth_headers):
        """Test live status API endpoint"""
        with patch('modules.tables.routers.realtime_table_router.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "role": "manager"}
            
            with patch('modules.tables.routers.realtime_table_router.table_state_service.get_floor_status') as mock_floor:
                mock_floor.return_value = []
                
                with patch('modules.tables.routers.realtime_table_router.realtime_table_service.get_occupancy_summary') as mock_occupancy:
                    mock_occupancy.return_value = {}
                    
                    with patch('modules.tables.routers.realtime_table_router.realtime_table_service.get_turn_time_alerts') as mock_alerts:
                        mock_alerts.return_value = []
                        
                        response = client.get(
                            "/api/v1/tables/realtime/status/live/1",
                            headers=auth_headers
                        )
                        
                        assert response.status_code == 200
                        data = response.json()
                        assert data["success"] is True
                        assert "floors" in data["data"]

    def test_error_handling(self, client, auth_headers):
        """Test API error handling"""
        with patch('modules.tables.routers.realtime_table_router.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "role": "manager"}
            
            with patch('modules.tables.routers.realtime_table_router.realtime_table_service.get_turn_time_alerts') as mock_alerts:
                mock_alerts.side_effect = Exception("Database error")
                
                response = client.get(
                    "/api/v1/tables/realtime/turn-alerts/1",
                    headers=auth_headers
                )
                
                assert response.status_code == 500
                data = response.json()
                assert "Error retrieving turn time alerts" in data["detail"]


class TestWebSocketIntegration:
    """Test WebSocket integration"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_websocket_connection(self, client):
        """Test WebSocket connection establishment"""
        with patch('modules.tables.routers.realtime_table_router.websocket_endpoint') as mock_endpoint:
            mock_endpoint.return_value = None
            
            with client.websocket_connect("/api/v1/tables/realtime/ws/1") as websocket:
                # Connection should be established
                assert websocket is not None

    @patch('modules.tables.websocket.table_websocket.table_state_service.get_floor_status')
    def test_websocket_initial_state(self, mock_floor_status, client):
        """Test WebSocket sends initial state"""
        mock_floor_status.return_value = [{"floor_id": 1, "tables": []}]
        
        with patch('modules.tables.websocket.table_websocket.get_db_context'):
            with client.websocket_connect("/api/v1/tables/realtime/ws/1?user_id=1") as websocket:
                # Should receive initial state message
                data = websocket.receive_json()
                assert data["type"] == "initial_state"
                assert "data" in data

    def test_websocket_ping_pong(self, client):
        """Test WebSocket ping/pong mechanism"""
        with patch('modules.tables.websocket.table_websocket.get_db_context'):
            with client.websocket_connect("/api/v1/tables/realtime/ws/1") as websocket:
                # Send ping
                websocket.send_json({"type": "ping"})
                
                # Should receive pong
                data = websocket.receive_json()
                assert data["type"] == "pong"

    def test_websocket_subscription(self, client):
        """Test WebSocket subscription mechanism"""
        with patch('modules.tables.websocket.table_websocket.get_db_context'):
            with client.websocket_connect("/api/v1/tables/realtime/ws/1") as websocket:
                # Send subscription
                websocket.send_json({
                    "type": "subscribe",
                    "subscriptions": ["turn_alerts", "occupancy"]
                })
                
                # Should receive confirmation
                data = websocket.receive_json()
                assert data["type"] == "subscription_confirmed"
                assert data["subscriptions"] == ["turn_alerts", "occupancy"]


class TestServiceIntegration:
    """Test integration between services"""

    @pytest.mark.asyncio
    async def test_table_status_change_notification(self):
        """Test that table status changes trigger WebSocket notifications"""
        from modules.tables.websocket.table_websocket import notify_table_status_change
        
        with patch('modules.tables.websocket.table_websocket.manager.send_table_update') as mock_send:
            await notify_table_status_change(
                restaurant_id=1,
                table_id=5,
                old_status=TableStatus.AVAILABLE,
                new_status=TableStatus.OCCUPIED,
                reason="Session started"
            )
            
            mock_send.assert_called_once()
            args = mock_send.call_args
            assert args[0][0] == 1  # restaurant_id
            assert args[0][1] == 5  # table_id
            assert args[0][2] == "status_changed"

    @pytest.mark.asyncio
    async def test_session_notification_integration(self):
        """Test session start/end notifications"""
        from modules.tables.websocket.table_websocket import notify_session_started, notify_session_ended
        
        with patch('modules.tables.websocket.table_websocket.manager.send_session_update') as mock_send:
            # Test session started
            await notify_session_started(
                restaurant_id=1,
                session_id=10,
                table_id=3,
                guest_count=2,
                server_name="Alice"
            )
            
            mock_send.assert_called()
            args = mock_send.call_args
            assert args[0][0] == 1  # restaurant_id
            assert args[0][1] == 10  # session_id
            assert args[0][2] == "started"

            # Test session ended
            await notify_session_ended(
                restaurant_id=1,
                session_id=10,
                table_id=3,
                duration_minutes=75
            )
            
            assert mock_send.call_count == 2

    @pytest.mark.asyncio
    async def test_real_time_monitoring_lifecycle(self):
        """Test complete real-time monitoring lifecycle"""
        # Start monitoring
        await realtime_table_service.start_monitoring()
        assert realtime_table_service.monitoring_task is not None
        
        # Let it run briefly
        await asyncio.sleep(0.1)
        
        # Stop monitoring
        await realtime_table_service.stop_monitoring()
        assert realtime_table_service.monitoring_task.cancelled()

    @pytest.mark.asyncio
    async def test_turn_time_alert_generation(self):
        """Test turn time alert generation with mocked data"""
        mock_db = AsyncMock()
        
        # Mock query results for occupied tables
        mock_result = AsyncMock()
        mock_result.all.return_value = []  # No occupied tables
        mock_db.execute.return_value = mock_result
        
        alerts = await realtime_table_service.get_turn_time_alerts(mock_db, 1)
        assert isinstance(alerts, list)
        assert len(alerts) == 0  # No alerts for no tables

    @pytest.mark.asyncio
    async def test_heat_map_data_generation(self):
        """Test heat map data generation"""
        mock_db = AsyncMock()
        
        # Mock query results
        mock_result = AsyncMock()
        mock_result.all.return_value = []  # No table data
        mock_db.execute.return_value = mock_result
        
        heat_map = await realtime_table_service.get_heat_map_data(mock_db, 1)
        assert isinstance(heat_map, list)
        assert len(heat_map) == 0  # No heat map data

    @pytest.mark.asyncio
    async def test_occupancy_summary_generation(self):
        """Test occupancy summary generation"""
        mock_db = AsyncMock()
        
        # Mock status counts query
        status_result = AsyncMock()
        status_result.all.return_value = [
            type('Row', (), {'status': TableStatus.OCCUPIED, 'count': 5}),
            type('Row', (), {'status': TableStatus.AVAILABLE, 'count': 10}),
        ]
        
        # Mock guest count query  
        guest_result = AsyncMock()
        guest_result.scalar.return_value = 15
        
        # Mock average turn time query
        turn_result = AsyncMock()
        turn_result.scalar.return_value = 65.5
        
        mock_db.execute.side_effect = [status_result, guest_result, turn_result]
        
        occupancy = await realtime_table_service.get_occupancy_summary(mock_db, 1)
        
        assert occupancy["total_tables"] == 15
        assert occupancy["occupied_tables"] == 5
        assert occupancy["available_tables"] == 10
        assert occupancy["current_guests"] == 15
        assert occupancy["occupancy_rate"] == 33.3  # 5/15 * 100


class TestErrorScenarios:
    """Test error handling scenarios"""

    @pytest.mark.asyncio
    async def test_database_connection_error(self):
        """Test handling of database connection errors"""
        mock_db = AsyncMock()
        mock_db.execute.side_effect = Exception("Connection lost")
        
        with pytest.raises(Exception):
            await realtime_table_service.get_turn_time_alerts(mock_db, 1)

    @pytest.mark.asyncio
    async def test_websocket_broadcast_error(self):
        """Test WebSocket broadcast error handling"""
        from modules.tables.websocket.table_websocket import manager
        
        # Mock a websocket that raises an error
        mock_ws = AsyncMock()
        mock_ws.send_json.side_effect = Exception("Connection closed")
        
        manager.active_connections[1] = {mock_ws}
        
        # Should not raise exception
        await manager.broadcast_to_restaurant(1, {"type": "test"})
        
        # Clean up
        manager.active_connections.clear()

    def test_invalid_heat_score_calculation(self):
        """Test heat score calculation with invalid inputs"""
        service = realtime_table_service
        
        # Test with invalid values
        score = service._calculate_heat_score(
            occupancy_rate=150.0,  # > 100
            session_count=-1,      # Negative
            revenue_per_hour=-50.0,  # Negative
            avg_turn_time=-10.0    # Negative
        )
        
        # Should still return a valid score
        assert 0 <= score <= 100

    @pytest.mark.asyncio
    async def test_monitoring_service_restart(self):
        """Test restarting monitoring service"""
        service = realtime_table_service
        
        # Start monitoring
        await service.start_monitoring()
        first_task = service.monitoring_task
        
        # Start again (should not create duplicate)
        await service.start_monitoring()
        assert service.monitoring_task == first_task
        
        # Stop and restart
        await service.stop_monitoring()
        await service.start_monitoring()
        assert service.monitoring_task != first_task
        
        # Clean up
        await service.stop_monitoring()