# backend/modules/kds/tests/test_kds_performance.py

"""
Tests for KDS Performance Service
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from ..services.kds_performance_service import (
    KDSPerformanceService,
    TimeRange,
    StationMetrics,
    KitchenAnalytics,
)
from ..models.kds_models import (
    KDSOrderItem,
    KitchenStation,
    DisplayStatus,
    StationType,
    StationStatus,
)


@pytest.fixture
def db_session():
    """Mock database session"""
    return Mock(spec=Session)


@pytest.fixture
def performance_service(db_session):
    """Create performance service instance"""
    return KDSPerformanceService(db_session)


@pytest.fixture
def sample_station():
    """Create sample station"""
    station = Mock(spec=KitchenStation)
    station.id = 1
    station.name = "Grill Station"
    station.station_type = StationType.GRILL
    station.status = StationStatus.ACTIVE
    station.warning_time_minutes = 5
    station.critical_time_minutes = 10
    station.prep_time_multiplier = 1.0
    return station


@pytest.fixture
def sample_kds_items():
    """Create sample KDS items"""
    items = []
    base_time = datetime.utcnow()
    
    # Completed item
    item1 = Mock(spec=KDSOrderItem)
    item1.id = 1
    item1.station_id = 1
    item1.status = DisplayStatus.COMPLETED
    item1.received_at = base_time - timedelta(minutes=15)
    item1.started_at = base_time - timedelta(minutes=14)
    item1.completed_at = base_time - timedelta(minutes=5)
    item1.recall_count = 0
    item1.is_late = False
    item1.target_time = base_time - timedelta(minutes=10)
    items.append(item1)
    
    # Pending item
    item2 = Mock(spec=KDSOrderItem)
    item2.id = 2
    item2.station_id = 1
    item2.status = DisplayStatus.PENDING
    item2.received_at = base_time - timedelta(minutes=8)
    item2.started_at = None
    item2.completed_at = None
    item2.recall_count = 0
    item2.is_late = True
    item2.target_time = base_time - timedelta(minutes=3)
    items.append(item2)
    
    # In progress item
    item3 = Mock(spec=KDSOrderItem)
    item3.id = 3
    item3.station_id = 1
    item3.status = DisplayStatus.IN_PROGRESS
    item3.received_at = base_time - timedelta(minutes=6)
    item3.started_at = base_time - timedelta(minutes=5)
    item3.completed_at = None
    item3.recall_count = 0
    item3.is_late = False
    item3.target_time = base_time + timedelta(minutes=4)
    items.append(item3)
    
    # Recalled item
    item4 = Mock(spec=KDSOrderItem)
    item4.id = 4
    item4.station_id = 1
    item4.status = DisplayStatus.PENDING
    item4.received_at = base_time - timedelta(minutes=20)
    item4.started_at = None
    item4.completed_at = None
    item4.recall_count = 2
    item4.is_late = True
    item4.target_time = base_time - timedelta(minutes=10)
    items.append(item4)
    
    return items


class TestStationMetrics:
    """Test station metrics calculation"""
    
    def test_get_station_metrics_basic(
        self, performance_service, db_session, sample_station, sample_kds_items
    ):
        """Test basic station metrics calculation"""
        # Setup mocks
        db_session.query().filter_by().first.return_value = sample_station
        db_session.query().filter().all.return_value = sample_kds_items
        db_session.query().filter().count.return_value = 2  # Current load
        
        # Get metrics
        metrics = performance_service.get_station_metrics(1, TimeRange.TODAY)
        
        # Verify metrics
        assert metrics.station_id == 1
        assert metrics.station_name == "Grill Station"
        assert metrics.total_items == 4
        assert metrics.completed_items == 1
        assert metrics.current_load == 2
        
    def test_get_station_metrics_performance(
        self, performance_service, db_session, sample_station, sample_kds_items
    ):
        """Test performance metrics calculation"""
        # Setup mocks
        db_session.query().filter_by().first.return_value = sample_station
        db_session.query().filter().all.return_value = sample_kds_items
        
        # Get metrics
        metrics = performance_service.get_station_metrics(1, TimeRange.TODAY)
        
        # Verify performance metrics
        assert metrics.completion_rate == 25.0  # 1 of 4 completed
        assert metrics.recall_rate == 25.0  # 1 of 4 recalled
        assert metrics.late_order_percentage == 50.0  # 2 of 4 late
        
    def test_get_station_metrics_empty(
        self, performance_service, db_session, sample_station
    ):
        """Test metrics with no items"""
        # Setup mocks
        db_session.query().filter_by().first.return_value = sample_station
        db_session.query().filter().all.return_value = []
        db_session.query().filter().count.return_value = 0
        
        # Get metrics
        metrics = performance_service.get_station_metrics(1, TimeRange.TODAY)
        
        # Verify empty metrics
        assert metrics.total_items == 0
        assert metrics.completed_items == 0
        assert metrics.completion_rate == 0
        assert metrics.average_prep_time == 0
        
    def test_get_station_metrics_invalid_station(
        self, performance_service, db_session
    ):
        """Test metrics for invalid station"""
        # Setup mocks
        db_session.query().filter_by().first.return_value = None
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Station 999 not found"):
            performance_service.get_station_metrics(999, TimeRange.TODAY)


class TestKitchenAnalytics:
    """Test kitchen-wide analytics"""
    
    def test_get_kitchen_analytics_basic(
        self, performance_service, db_session, sample_station
    ):
        """Test basic kitchen analytics"""
        # Setup mocks
        db_session.query(KitchenStation).all.return_value = [sample_station]
        db_session.query().filter().count.return_value = 10  # Total items
        db_session.query().filter().distinct().all.return_value = [(1,), (2,)]  # Orders
        db_session.query().filter().all.return_value = []  # Completed items
        
        # Mock helper methods
        with patch.object(performance_service, "_get_peak_hours", return_value=[12, 13, 18]):
            with patch.object(performance_service, "_identify_bottlenecks", return_value=[]):
                with patch.object(performance_service, "_get_staff_rankings", return_value=[]):
                    with patch.object(performance_service, "_get_hourly_throughput", return_value={}):
                        with patch.object(performance_service, "_get_daily_trends", return_value={}):
                            with patch.object(performance_service, "_calculate_efficiency_score", return_value=75.0):
                                
                                # Get analytics
                                analytics = performance_service.get_kitchen_analytics(1, TimeRange.TODAY)
        
        # Verify analytics
        assert analytics.total_orders == 2
        assert analytics.total_items == 10
        assert analytics.efficiency_score == 75.0
        assert analytics.peak_hours == [12, 13, 18]
    
    def test_calculate_efficiency_score(self, performance_service):
        """Test efficiency score calculation"""
        # Perfect score
        score = performance_service._calculate_efficiency_score(
            completion_rate=100,
            avg_order_time=10,
            recall_rate=0
        )
        assert score == 100.0
        
        # Poor score
        score = performance_service._calculate_efficiency_score(
            completion_rate=50,
            avg_order_time=35,
            recall_rate=20
        )
        assert score < 50
        
        # Average score
        score = performance_service._calculate_efficiency_score(
            completion_rate=80,
            avg_order_time=20,
            recall_rate=5
        )
        assert 60 < score < 80


class TestRealTimeMetrics:
    """Test real-time metrics"""
    
    def test_get_real_time_metrics(
        self, performance_service, db_session, sample_kds_items
    ):
        """Test real-time metrics retrieval"""
        # Setup mocks
        active_items = [item for item in sample_kds_items if item.status in [DisplayStatus.PENDING, DisplayStatus.IN_PROGRESS]]
        db_session.query().filter().all.return_value = active_items
        
        # Mock status counts
        db_session.query().filter().count.side_effect = [2, 1, 1, 0, 0, 0]  # Status counts
        
        # Get metrics
        metrics = performance_service.get_real_time_metrics()
        
        # Verify metrics
        assert metrics["active_items_count"] == len(active_items)
        assert "status_breakdown" in metrics
        assert "critical_items" in metrics
        assert "warning_items" in metrics
    
    def test_get_real_time_metrics_station_filter(
        self, performance_service, db_session
    ):
        """Test real-time metrics with station filter"""
        # Setup mocks
        db_session.query().filter().all.return_value = []
        db_session.query().filter().count.return_value = 0
        
        # Get metrics for specific station
        metrics = performance_service.get_real_time_metrics(station_id=1)
        
        # Verify empty metrics
        assert metrics["active_items_count"] == 0
        assert metrics["average_current_wait_time"] == 0


class TestStaffPerformance:
    """Test staff performance metrics"""
    
    def test_get_staff_performance(self, performance_service, db_session):
        """Test staff performance calculation"""
        # Create mock staff member
        staff = Mock()
        staff.id = 1
        staff.first_name = "John"
        staff.last_name = "Doe"
        
        # Create mock completed items
        completed_items = []
        base_time = datetime.utcnow()
        
        for i in range(5):
            item = Mock()
            item.completed_at = base_time - timedelta(minutes=i*10)
            item.started_at = base_time - timedelta(minutes=i*10 + 5)
            item.recall_count = 1 if i == 2 else 0  # One recalled item
            completed_items.append(item)
        
        # Setup mocks
        db_session.query().filter().all.side_effect = [completed_items, []]  # Completed, then started
        db_session.query().filter_by().first.return_value = staff
        
        # Get performance
        performance = performance_service.get_staff_performance(1, TimeRange.TODAY)
        
        # Verify performance
        assert performance["staff_id"] == 1
        assert performance["staff_name"] == "John Doe"
        assert performance["items_completed"] == 5
        assert performance["recall_rate"] == 20.0  # 1 of 5 recalled
        assert performance["accuracy_rate"] == 80.0  # 100 - recall_rate


class TestPerformanceReport:
    """Test performance report generation"""
    
    def test_generate_performance_report(
        self, performance_service, db_session, sample_station
    ):
        """Test comprehensive report generation"""
        # Setup mocks
        db_session.query(KitchenStation).all.return_value = [sample_station]
        
        # Mock analytics and metrics
        with patch.object(performance_service, "get_kitchen_analytics") as mock_analytics:
            mock_analytics.return_value = Mock(
                total_orders=10,
                total_items=50,
                average_order_time=15.5,
                efficiency_score=82.0,
                bottleneck_stations=[],
                peak_hours=[12, 18],
                __dict__={"total_orders": 10, "efficiency_score": 82.0}
            )
            
            with patch.object(performance_service, "get_station_metrics") as mock_metrics:
                mock_metrics.return_value = Mock(
                    station_name="Grill",
                    recall_rate=5.0,
                    __dict__={"station_name": "Grill", "recall_rate": 5.0}
                )
                
                with patch.object(performance_service, "get_real_time_metrics") as mock_realtime:
                    mock_realtime.return_value = {"active_items": 10}
                    
                    # Generate report
                    report = performance_service.generate_performance_report(1, TimeRange.TODAY)
        
        # Verify report structure
        assert "generated_at" in report
        assert "summary" in report
        assert "analytics" in report
        assert "station_metrics" in report
        assert "real_time_status" in report
        assert "recommendations" in report
        
        # Verify summary
        assert report["summary"]["efficiency_score"] == 82.0
    
    def test_generate_recommendations(self, performance_service):
        """Test recommendation generation"""
        # Create mock analytics
        analytics = Mock()
        analytics.bottleneck_stations = ["Grill", "Fryer"]
        analytics.efficiency_score = 65.0
        analytics.peak_hours = [12, 18, 19]
        
        # Create mock station metrics
        station_metrics = [
            {"station_name": "Grill", "recall_rate": 15.0},
            {"station_name": "Salad", "recall_rate": 3.0},
        ]
        
        # Generate recommendations
        recommendations = performance_service._generate_recommendations(
            analytics, station_metrics
        )
        
        # Verify recommendations
        assert len(recommendations) > 0
        assert any("bottleneck" in r for r in recommendations)
        assert any("efficiency" in r for r in recommendations)
        assert any("recall rate" in r for r in recommendations)


class TestTimeRanges:
    """Test time range filtering"""
    
    def test_get_date_filter_last_hour(self, performance_service):
        """Test last hour filter"""
        date_filter = performance_service._get_date_filter(TimeRange.LAST_HOUR)
        
        # Verify time range
        duration = date_filter["end"] - date_filter["start"]
        assert duration.total_seconds() == 3600  # 1 hour
    
    def test_get_date_filter_today(self, performance_service):
        """Test today filter"""
        date_filter = performance_service._get_date_filter(TimeRange.TODAY)
        
        # Verify start is beginning of day
        assert date_filter["start"].hour == 0
        assert date_filter["start"].minute == 0
    
    def test_get_date_filter_custom(self, performance_service):
        """Test custom date range"""
        start = datetime(2024, 1, 1, 8, 0)
        end = datetime(2024, 1, 1, 20, 0)
        
        date_filter = performance_service._get_date_filter(
            TimeRange.CUSTOM, start, end
        )
        
        # Verify custom range
        assert date_filter["start"] == start
        assert date_filter["end"] == end
    
    def test_get_date_filter_custom_missing_dates(self, performance_service):
        """Test custom range without dates raises error"""
        with pytest.raises(ValueError, match="Custom range requires"):
            performance_service._get_date_filter(TimeRange.CUSTOM)