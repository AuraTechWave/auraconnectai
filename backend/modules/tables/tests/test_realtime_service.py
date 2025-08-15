# backend/modules/tables/tests/test_realtime_service.py

"""
Tests for real-time table service functionality
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from ..services.realtime_table_service import (
    RealtimeTableService,
    TurnTimeAlert,
    TableTurnTime,
    TableHeatMapData,
)
from ..models.table_models import (
    Table,
    TableSession,
    TableStatus,
    TableShape,
)


class TestRealtimeTableService:
    """Test real-time table service"""

    @pytest.fixture
    def service(self):
        return RealtimeTableService()

    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def sample_table(self):
        return Table(
            id=1,
            restaurant_id=1,
            table_number="T1",
            max_capacity=4,
            min_capacity=2,
            status=TableStatus.OCCUPIED,
            shape=TableShape.RECTANGLE,
            position_x=100,
            position_y=200,
            is_active=True,
        )

    @pytest.fixture
    def sample_session(self):
        return TableSession(
            id=1,
            restaurant_id=1,
            table_id=1,
            guest_count=2,
            guest_name="John Doe",
            start_time=datetime.utcnow() - timedelta(minutes=90),
            end_time=None,
        )

    async def test_get_expected_turn_time_breakfast(self, service):
        """Test expected turn time calculation for breakfast"""
        morning_time = datetime.now().replace(hour=8, minute=0)
        expected = service._get_expected_turn_time(morning_time)
        assert expected == 45  # Breakfast threshold

    async def test_get_expected_turn_time_lunch(self, service):
        """Test expected turn time calculation for lunch"""
        lunch_time = datetime.now().replace(hour=12, minute=30)
        expected = service._get_expected_turn_time(lunch_time)
        assert expected == 60  # Lunch threshold

    async def test_get_expected_turn_time_dinner(self, service):
        """Test expected turn time calculation for dinner"""
        dinner_time = datetime.now().replace(hour=19, minute=0)
        expected = service._get_expected_turn_time(dinner_time)
        assert expected == 90  # Dinner threshold

    async def test_calculate_alert_level_normal(self, service):
        """Test alert level calculation for normal turn time"""
        alert = service._calculate_alert_level(current_minutes=45, expected_minutes=60)
        assert alert == TurnTimeAlert.NORMAL

    async def test_calculate_alert_level_warning(self, service):
        """Test alert level calculation for warning turn time"""
        alert = service._calculate_alert_level(current_minutes=55, expected_minutes=60)
        assert alert == TurnTimeAlert.WARNING

    async def test_calculate_alert_level_critical(self, service):
        """Test alert level calculation for critical turn time"""
        alert = service._calculate_alert_level(current_minutes=70, expected_minutes=60)
        assert alert == TurnTimeAlert.CRITICAL

    async def test_calculate_alert_level_excessive(self, service):
        """Test alert level calculation for excessive turn time"""
        alert = service._calculate_alert_level(current_minutes=100, expected_minutes=60)
        assert alert == TurnTimeAlert.EXCESSIVE

    async def test_calculate_heat_score(self, service):
        """Test heat score calculation"""
        heat_score = service._calculate_heat_score(
            occupancy_rate=80.0,
            session_count=6,
            revenue_per_hour=300.0,
            avg_turn_time=65.0
        )
        
        assert 0 <= heat_score <= 100
        assert isinstance(heat_score, float)

    async def test_calculate_heat_score_high_performance(self, service):
        """Test heat score for high-performing table"""
        heat_score = service._calculate_heat_score(
            occupancy_rate=90.0,
            session_count=8,
            revenue_per_hour=400.0,
            avg_turn_time=55.0  # Faster than optimal
        )
        
        assert heat_score > 80  # Should be high score

    async def test_calculate_heat_score_low_performance(self, service):
        """Test heat score for low-performing table"""
        heat_score = service._calculate_heat_score(
            occupancy_rate=20.0,
            session_count=1,
            revenue_per_hour=50.0,
            avg_turn_time=120.0  # Much slower than optimal
        )
        
        assert heat_score < 50  # Should be low score

    @patch('modules.tables.services.realtime_table_service.get_db_context')
    async def test_start_monitoring(self, mock_db_context, service):
        """Test starting monitoring task"""
        mock_db_context.return_value.__aenter__ = AsyncMock()
        mock_db_context.return_value.__aexit__ = AsyncMock()
        
        # Mock the monitoring methods
        service.get_turn_time_alerts = AsyncMock(return_value=[])
        service.get_occupancy_summary = AsyncMock(return_value={})
        service.get_heat_map_data = AsyncMock(return_value=[])
        
        with patch('modules.tables.services.realtime_table_service.websocket_manager') as mock_ws:
            mock_ws.active_connections = {}
            mock_ws.broadcast_to_restaurant = AsyncMock()
            
            await service.start_monitoring()
            assert service.monitoring_task is not None
            assert not service.monitoring_task.done()
            
            # Clean up
            await service.stop_monitoring()

    async def test_stop_monitoring(self, service):
        """Test stopping monitoring task"""
        # Start monitoring first
        service.monitoring_task = AsyncMock()
        service.monitoring_task.done.return_value = False
        service.monitoring_task.cancel = MagicMock()
        
        await service.stop_monitoring()
        service.monitoring_task.cancel.assert_called_once()

    @patch('modules.tables.services.realtime_table_service.websocket_manager')
    async def test_broadcast_realtime_updates(self, mock_ws_manager, service):
        """Test broadcasting real-time updates"""
        mock_ws_manager.active_connections = {1: set()}
        mock_ws_manager.broadcast_to_restaurant = AsyncMock()
        
        # Mock service methods
        service.get_turn_time_alerts = AsyncMock(return_value=[])
        service.get_occupancy_summary = AsyncMock(return_value={})
        service.get_heat_map_data = AsyncMock(return_value=[])
        
        with patch('modules.tables.services.realtime_table_service.get_db_context') as mock_db:
            mock_db.return_value.__aenter__ = AsyncMock()
            mock_db.return_value.__aexit__ = AsyncMock()
            
            await service._broadcast_realtime_updates()
            
            mock_ws_manager.broadcast_to_restaurant.assert_called_once()

    def test_table_turn_time_properties(self):
        """Test TableTurnTime dataclass properties"""
        turn_time = TableTurnTime(
            table_id=1,
            table_number="T1",
            current_duration_minutes=90,
            expected_duration_minutes=75,
            alert_level=TurnTimeAlert.CRITICAL,
            guest_count=2,
            server_name="Alice",
            order_value=125.50,
            session_start=datetime.utcnow(),
        )
        
        assert turn_time.overrun_minutes == 15
        assert turn_time.progress_percentage == 120.0

    def test_table_heat_map_data_properties(self):
        """Test TableHeatMapData dataclass properties"""
        heat_data = TableHeatMapData(
            table_id=1,
            table_number="T1",
            heat_score=85.5,
            occupancy_rate=75.0,
            revenue_per_hour=300.0,
            turn_count_today=6,
            avg_turn_time_minutes=65.0,
            status=TableStatus.OCCUPIED,
            position_x=100,
            position_y=200,
        )
        
        assert heat_data.heat_color == "#FF4444"  # Hot red
        assert heat_data.table_number == "T1"

    def test_heat_map_color_calculation(self):
        """Test heat map color calculation for different scores"""
        # Test hot (red)
        hot_data = TableHeatMapData(
            table_id=1, table_number="T1", heat_score=90,
            occupancy_rate=0, revenue_per_hour=0, turn_count_today=0,
            avg_turn_time_minutes=0, status=TableStatus.AVAILABLE,
            position_x=0, position_y=0
        )
        assert hot_data.heat_color == "#FF4444"
        
        # Test medium (orange)
        medium_data = TableHeatMapData(
            table_id=1, table_number="T1", heat_score=70,
            occupancy_rate=0, revenue_per_hour=0, turn_count_today=0,
            avg_turn_time_minutes=0, status=TableStatus.AVAILABLE,
            position_x=0, position_y=0
        )
        assert medium_data.heat_color == "#FF8800"
        
        # Test cool (gray)
        cool_data = TableHeatMapData(
            table_id=1, table_number="T1", heat_score=10,
            occupancy_rate=0, revenue_per_hour=0, turn_count_today=0,
            avg_turn_time_minutes=0, status=TableStatus.AVAILABLE,
            position_x=0, position_y=0
        )
        assert cool_data.heat_color == "#CCCCCC"

    def test_identify_service_periods(self, service):
        """Test service period identification"""
        hourly_data = [
            {"hour": 8, "sessions_started": 5, "avg_duration_minutes": 45},
            {"hour": 12, "sessions_started": 8, "avg_duration_minutes": 60},
            {"hour": 18, "sessions_started": 12, "avg_duration_minutes": 90},
        ]
        
        periods = service._identify_service_periods(hourly_data)
        
        assert len(periods) == 3
        breakfast = next(p for p in periods if p["name"] == "Breakfast")
        assert breakfast["peak_sessions"] == 5
        
        lunch = next(p for p in periods if p["name"] == "Lunch")
        assert lunch["peak_sessions"] == 8
        
        dinner = next(p for p in periods if p["name"] == "Dinner")
        assert dinner["peak_sessions"] == 12

    def test_generate_peak_hour_recommendations(self, service):
        """Test peak hour recommendations generation"""
        # High utilization scenario
        high_util_data = [
            {"hour": h, "sessions_started": 10, "avg_duration_minutes": 60}
            for h in range(18, 22)
        ]
        
        recommendations = service._generate_peak_hour_recommendations(high_util_data)
        assert any("staggered reservation" in rec for rec in recommendations)
        
        # Long duration scenario
        long_duration_data = [
            {"hour": 19, "sessions_started": 5, "avg_duration_minutes": 120}
        ]
        
        recommendations = service._generate_peak_hour_recommendations(long_duration_data)
        assert any("turn times" in rec for rec in recommendations)

    @pytest.mark.asyncio
    async def test_monitoring_loop_error_handling(self, service):
        """Test monitoring loop handles errors gracefully"""
        service._broadcast_realtime_updates = AsyncMock(side_effect=Exception("Test error"))
        
        # Start and quickly stop to test error handling
        await service.start_monitoring()
        await asyncio.sleep(0.1)  # Let it run briefly
        await service.stop_monitoring()
        
        # Should not raise exception


class TestTurnTimeAlerts:
    """Test turn time alert functionality"""

    def test_turn_time_alert_enum_values(self):
        """Test turn time alert enum values"""
        assert TurnTimeAlert.NORMAL == "normal"
        assert TurnTimeAlert.WARNING == "warning"
        assert TurnTimeAlert.CRITICAL == "critical"
        assert TurnTimeAlert.EXCESSIVE == "excessive"

    def test_turn_time_dataclass_creation(self):
        """Test TableTurnTime dataclass creation"""
        session_start = datetime.utcnow() - timedelta(hours=1)
        
        turn_time = TableTurnTime(
            table_id=5,
            table_number="T5",
            current_duration_minutes=95,
            expected_duration_minutes=75,
            alert_level=TurnTimeAlert.CRITICAL,
            guest_count=4,
            server_name="Bob Smith",
            order_value=180.75,
            session_start=session_start,
        )
        
        assert turn_time.table_id == 5
        assert turn_time.table_number == "T5"
        assert turn_time.overrun_minutes == 20
        assert turn_time.progress_percentage == pytest.approx(126.67, rel=1e-2)
        assert turn_time.alert_level == TurnTimeAlert.CRITICAL


class TestHeatMapVisualization:
    """Test heat map visualization functionality"""

    def test_heat_map_data_creation(self):
        """Test TableHeatMapData creation"""
        heat_data = TableHeatMapData(
            table_id=3,
            table_number="T3",
            heat_score=65.5,
            occupancy_rate=82.3,
            revenue_per_hour=245.80,
            turn_count_today=7,
            avg_turn_time_minutes=58.5,
            status=TableStatus.OCCUPIED,
            position_x=150,
            position_y=250,
        )
        
        assert heat_data.table_id == 3
        assert heat_data.heat_score == 65.5
        assert heat_data.heat_color == "#FF8800"  # Orange for 65.5 score
        assert heat_data.position_x == 150

    def test_heat_score_boundaries(self):
        """Test heat score color boundaries"""
        test_cases = [
            (95, "#FF4444"),  # >= 80: Hot red
            (80, "#FF4444"),  # >= 80: Hot red
            (79, "#FF8800"),  # >= 60: Orange
            (60, "#FF8800"),  # >= 60: Orange
            (59, "#FFAA00"),  # >= 40: Yellow
            (40, "#FFAA00"),  # >= 40: Yellow
            (39, "#88DD88"),  # >= 20: Light green
            (20, "#88DD88"),  # >= 20: Light green
            (19, "#CCCCCC"),  # < 20: Cool gray
            (0, "#CCCCCC"),   # < 20: Cool gray
        ]
        
        for score, expected_color in test_cases:
            heat_data = TableHeatMapData(
                table_id=1, table_number="T1", heat_score=score,
                occupancy_rate=0, revenue_per_hour=0, turn_count_today=0,
                avg_turn_time_minutes=0, status=TableStatus.AVAILABLE,
                position_x=0, position_y=0
            )
            assert heat_data.heat_color == expected_color, f"Score {score} should map to {expected_color}"


class TestServiceIntegration:
    """Test integration between services"""

    @pytest.mark.asyncio
    async def test_monitoring_service_lifecycle(self):
        """Test complete monitoring service lifecycle"""
        service = RealtimeTableService()
        
        # Test starting monitoring
        assert service.monitoring_task is None
        
        with patch.object(service, '_monitoring_loop') as mock_loop:
            mock_loop.return_value = asyncio.create_task(asyncio.sleep(0.1))
            
            await service.start_monitoring()
            assert service.monitoring_task is not None
            
            # Test stopping monitoring
            await service.stop_monitoring()
            assert service.monitoring_task.cancelled()

    @pytest.mark.asyncio 
    async def test_error_resilience(self):
        """Test service handles errors without crashing"""
        service = RealtimeTableService()
        
        # Test heat score calculation with invalid data
        score = service._calculate_heat_score(
            occupancy_rate=-10,  # Invalid negative
            session_count=0,
            revenue_per_hour=0,
            avg_turn_time=0
        )
        
        assert 0 <= score <= 100  # Should still return valid range
        
        # Test alert level calculation with edge cases
        alert = service._calculate_alert_level(0, 0)
        assert alert in [TurnTimeAlert.NORMAL, TurnTimeAlert.WARNING, TurnTimeAlert.CRITICAL, TurnTimeAlert.EXCESSIVE]