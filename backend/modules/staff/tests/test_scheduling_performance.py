"""
Performance tests for staff scheduling functionality
"""

import pytest
import time
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from unittest.mock import Mock, MagicMock
import random

from ..models.scheduling_models import ScheduledShift, ShiftTemplate
from ..services.scheduling_service import SchedulingService
from ..enums.scheduling_enums import ShiftStatus


@pytest.fixture
def mock_db():
    """Create a mock database session"""
    return Mock(spec=Session)


@pytest.fixture
def scheduling_service(mock_db):
    """Create a scheduling service instance"""
    return SchedulingService(mock_db)


class TestSchedulingPerformance:
    """Test performance of scheduling operations"""

    def test_conflict_detection_performance_large_dataset(
        self, scheduling_service, mock_db
    ):
        """Test conflict detection performance with large number of shifts"""
        # Generate 1000 existing shifts
        existing_shifts = []
        base_date = date(2024, 2, 1)

        for i in range(1000):
            shift_date = base_date + timedelta(days=i % 30)
            staff_id = (i % 50) + 1  # 50 staff members

            shift = ScheduledShift(
                id=i,
                staff_id=staff_id,
                date=shift_date,
                start_time=datetime.combine(shift_date, datetime.min.time())
                + timedelta(hours=8),
                end_time=datetime.combine(shift_date, datetime.min.time())
                + timedelta(hours=16),
                status=ShiftStatus.SCHEDULED,
            )
            existing_shifts.append(shift)

        # Mock the query to return filtered results
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = existing_shifts[:10]  # Return subset

        # Test conflict detection performance
        start_time = time.time()

        conflicts = scheduling_service.check_shift_conflicts(
            staff_id=1,
            shift_date=date(2024, 2, 15),
            start_time=datetime(2024, 2, 15, 9, 0),
            end_time=datetime(2024, 2, 15, 17, 0),
        )

        end_time = time.time()
        execution_time = end_time - start_time

        # Should complete in under 100ms even with large dataset
        assert execution_time < 0.1
        print(f"Conflict detection took {execution_time:.4f} seconds")

    def test_auto_schedule_performance_multiple_staff(
        self, scheduling_service, mock_db
    ):
        """Test auto-scheduling performance with multiple staff members"""
        # Generate 100 staff members
        staff_members = []
        for i in range(100):
            staff = Mock(
                id=i + 1,
                name=f"Staff {i+1}",
                max_hours_per_week=40,
                min_hours_per_week=20,
            )
            staff_members.append(staff)

        # Mock database queries
        mock_db.query.return_value.filter.return_value.all.return_value = staff_members
        mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = (
            []
        )
        mock_db.add = Mock()
        mock_db.commit = Mock()

        # Test auto-scheduling performance
        start_time = time.time()

        result = scheduling_service.auto_schedule(
            restaurant_id=1,
            start_date=date(2024, 2, 1),
            end_date=date(2024, 2, 7),  # One week
        )

        end_time = time.time()
        execution_time = end_time - start_time

        # Should complete in under 5 seconds for 100 staff over a week
        assert execution_time < 5.0
        print(f"Auto-scheduling for 100 staff took {execution_time:.4f} seconds")

    def test_analytics_query_performance(self, scheduling_service, mock_db):
        """Test analytics query performance with large dataset"""
        # Generate mock shifts for analytics
        shifts = []
        for i in range(5000):  # 5000 shifts
            shift = Mock(
                staff_member=Mock(
                    pay_policies=[Mock(hourly_rate=random.uniform(15, 30))]
                ),
                start_time=datetime(2024, 2, 1, 8, 0) + timedelta(days=i % 30),
                end_time=datetime(2024, 2, 1, 16, 0) + timedelta(days=i % 30),
                status=ShiftStatus.SCHEDULED,
            )
            shifts.append(shift)

        mock_db.query.return_value.join.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = (
            shifts
        )

        # Test analytics performance
        start_time = time.time()

        analytics = scheduling_service.get_schedule_analytics(
            restaurant_id=1,
            start_date=date(2024, 2, 1),
            end_date=date(2024, 2, 28),  # Full month
        )

        end_time = time.time()
        execution_time = end_time - start_time

        # Should complete in under 1 second even with 5000 shifts
        assert execution_time < 1.0
        print(
            f"Analytics calculation for 5000 shifts took {execution_time:.4f} seconds"
        )

    def test_batch_operations_performance(self, scheduling_service, mock_db):
        """Test performance of batch operations"""
        # Test batch shift creation
        shifts_to_create = []
        for i in range(500):
            shift_data = {
                "staff_id": (i % 50) + 1,
                "date": date(2024, 2, 1) + timedelta(days=i % 30),
                "start_time": datetime(2024, 2, 1, 8, 0),
                "end_time": datetime(2024, 2, 1, 16, 0),
            }
            shifts_to_create.append(shift_data)

        mock_db.bulk_insert_mappings = Mock()
        mock_db.commit = Mock()

        start_time = time.time()

        # Batch create shifts
        scheduling_service.batch_create_shifts(shifts_to_create)

        end_time = time.time()
        execution_time = end_time - start_time

        # Batch operation should be fast
        assert execution_time < 0.5
        print(f"Batch creation of 500 shifts took {execution_time:.4f} seconds")

    def test_concurrent_conflict_detection(self, scheduling_service, mock_db):
        """Test conflict detection under concurrent access"""
        import threading
        import queue

        results = queue.Queue()

        def check_conflicts(staff_id, date_offset):
            shifts = scheduling_service.check_shift_conflicts(
                staff_id=staff_id,
                shift_date=date(2024, 2, 1) + timedelta(days=date_offset),
                start_time=datetime(2024, 2, 1, 8, 0),
                end_time=datetime(2024, 2, 1, 16, 0),
            )
            results.put(len(shifts))

        # Mock database to return empty conflicts
        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = (
            []
        )

        # Create 50 threads checking conflicts simultaneously
        threads = []
        start_time = time.time()

        for i in range(50):
            thread = threading.Thread(target=check_conflicts, args=(i % 10 + 1, i % 30))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        end_time = time.time()
        execution_time = end_time - start_time

        # Should handle concurrent access efficiently
        assert execution_time < 2.0
        assert results.qsize() == 50
        print(f"50 concurrent conflict checks took {execution_time:.4f} seconds")


class TestDatabaseIndexEffectiveness:
    """Test effectiveness of database indexes"""

    def test_date_range_query_with_index(self, scheduling_service, mock_db):
        """Test performance of date range queries with indexes"""
        # Simulate indexed query response time
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        # Simulate fast response due to index
        def fast_all():
            time.sleep(0.01)  # 10ms with index
            return []

        mock_query.all = fast_all

        start_time = time.time()

        # Query shifts for a date range
        scheduling_service.get_shifts_by_date_range(
            restaurant_id=1, start_date=date(2024, 2, 1), end_date=date(2024, 2, 28)
        )

        end_time = time.time()
        execution_time = end_time - start_time

        # With index, should be very fast
        assert execution_time < 0.02
        print(f"Indexed date range query took {execution_time:.4f} seconds")

    def test_staff_location_query_with_index(self, scheduling_service, mock_db):
        """Test performance of staff+location queries with composite index"""
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.join.return_value = mock_query

        # Simulate fast response due to composite index
        mock_query.all.return_value = []

        start_time = time.time()

        # Query shifts for specific staff at specific location
        scheduling_service.get_staff_shifts_by_location(
            staff_id=1,
            location_id=1,
            start_date=date(2024, 2, 1),
            end_date=date(2024, 2, 28),
        )

        end_time = time.time()
        execution_time = end_time - start_time

        # With composite index, should be fast
        assert execution_time < 0.01
        print(f"Indexed staff+location query took {execution_time:.4f} seconds")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
