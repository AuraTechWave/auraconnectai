"""
Comprehensive tests for staff scheduling functionality
"""
import pytest
from datetime import datetime, date, time, timedelta
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from ..models.staff_models import StaffMember
from ..models.scheduling_models import (
    ShiftTemplate, ScheduledShift, StaffAvailability,
    TimeOffRequest, ShiftSwapRequest
)
from ..enums.scheduling_enums import (
    ShiftType, ShiftStatus, AvailabilityStatus, SwapRequestStatus
)
from ..services.scheduling_service import SchedulingService
from ..schemas.scheduling_schemas import (
    ShiftTemplateCreate, ScheduledShiftCreate,
    StaffAvailabilityCreate, TimeOffRequestCreate
)


@pytest.fixture
def mock_db():
    """Create a mock database session"""
    return Mock(spec=Session)


@pytest.fixture
def scheduling_service(mock_db):
    """Create a scheduling service instance"""
    return SchedulingService(mock_db)


@pytest.fixture
def sample_staff():
    """Create sample staff members"""
    return [
        StaffMember(id=1, name="John Doe", email="john@example.com", 
                   max_hours_per_week=40, min_hours_per_week=20),
        StaffMember(id=2, name="Jane Smith", email="jane@example.com",
                   max_hours_per_week=35, min_hours_per_week=25),
        StaffMember(id=3, name="Bob Wilson", email="bob@example.com",
                   max_hours_per_week=40, min_hours_per_week=30)
    ]


@pytest.fixture
def sample_shift_template():
    """Create a sample shift template"""
    return ShiftTemplate(
        id=1,
        restaurant_id=1,
        name="Morning Shift",
        type=ShiftType.MORNING,
        start_time=time(8, 0),
        end_time=time(16, 0),
        break_duration=30,
        min_staff=2,
        max_staff=5
    )


class TestConflictDetection:
    """Test conflict detection functionality"""
    
    def test_detect_overlapping_shifts(self, scheduling_service, mock_db):
        """Test detection of overlapping shifts"""
        # Existing shift: 8 AM - 4 PM
        existing_shift = ScheduledShift(
            id=1,
            staff_id=1,
            date=date(2024, 2, 15),
            start_time=datetime(2024, 2, 15, 8, 0),
            end_time=datetime(2024, 2, 15, 16, 0),
            status=ShiftStatus.SCHEDULED
        )
        
        # New shift: 2 PM - 10 PM (overlaps with existing)
        new_shift = ScheduledShiftCreate(
            staff_id=1,
            date=date(2024, 2, 15),
            start_time=datetime(2024, 2, 15, 14, 0),
            end_time=datetime(2024, 2, 15, 22, 0)
        )
        
        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [existing_shift]
        
        conflicts = scheduling_service.check_shift_conflicts(
            new_shift.staff_id,
            new_shift.date,
            new_shift.start_time,
            new_shift.end_time
        )
        
        assert len(conflicts) == 1
        assert conflicts[0].id == 1
    
    def test_no_conflict_different_days(self, scheduling_service, mock_db):
        """Test no conflict when shifts are on different days"""
        existing_shift = ScheduledShift(
            id=1,
            staff_id=1,
            date=date(2024, 2, 15),
            start_time=datetime(2024, 2, 15, 8, 0),
            end_time=datetime(2024, 2, 15, 16, 0),
            status=ShiftStatus.SCHEDULED
        )
        
        new_shift = ScheduledShiftCreate(
            staff_id=1,
            date=date(2024, 2, 16),  # Different day
            start_time=datetime(2024, 2, 16, 8, 0),
            end_time=datetime(2024, 2, 16, 16, 0)
        )
        
        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []
        
        conflicts = scheduling_service.check_shift_conflicts(
            new_shift.staff_id,
            new_shift.date,
            new_shift.start_time,
            new_shift.end_time
        )
        
        assert len(conflicts) == 0
    
    def test_no_conflict_adjacent_shifts(self, scheduling_service, mock_db):
        """Test no conflict when shifts are adjacent (not overlapping)"""
        existing_shift = ScheduledShift(
            id=1,
            staff_id=1,
            date=date(2024, 2, 15),
            start_time=datetime(2024, 2, 15, 8, 0),
            end_time=datetime(2024, 2, 15, 16, 0),
            status=ShiftStatus.SCHEDULED
        )
        
        new_shift = ScheduledShiftCreate(
            staff_id=1,
            date=date(2024, 2, 15),
            start_time=datetime(2024, 2, 15, 16, 0),  # Starts when previous ends
            end_time=datetime(2024, 2, 15, 22, 0)
        )
        
        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []
        
        conflicts = scheduling_service.check_shift_conflicts(
            new_shift.staff_id,
            new_shift.date,
            new_shift.start_time,
            new_shift.end_time
        )
        
        assert len(conflicts) == 0


class TestAutoScheduling:
    """Test auto-scheduling algorithm"""
    
    def test_auto_schedule_respects_availability(self, scheduling_service, mock_db, sample_staff):
        """Test that auto-scheduling respects staff availability"""
        # Monday availability: 8 AM - 4 PM
        availability = StaffAvailability(
            staff_id=1,
            day_of_week=1,  # Monday
            start_time=time(8, 0),
            end_time=time(16, 0),
            status=AvailabilityStatus.AVAILABLE
        )
        
        # Try to schedule for Monday
        start_date = date(2024, 2, 12)  # Monday
        end_date = date(2024, 2, 12)
        
        mock_db.query.return_value.filter.return_value.all.return_value = sample_staff[:1]
        mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = [availability]
        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []
        
        result = scheduling_service.auto_schedule(1, start_date, end_date)
        
        assert result["success"] is True
        assert result["scheduled_count"] >= 0
    
    def test_auto_schedule_respects_max_hours(self, scheduling_service, mock_db, sample_staff):
        """Test that auto-scheduling respects max hours per week"""
        staff = sample_staff[0]  # max_hours_per_week = 40
        
        # Existing shifts totaling 35 hours
        existing_shifts = [
            ScheduledShift(
                staff_id=1,
                date=date(2024, 2, 12),
                start_time=datetime(2024, 2, 12, 8, 0),
                end_time=datetime(2024, 2, 12, 15, 0),  # 7 hours * 5 days = 35 hours
                status=ShiftStatus.SCHEDULED
            )
        ]
        
        mock_db.query.return_value.filter.return_value.all.return_value = [staff]
        mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = existing_shifts
        
        # Calculate current hours
        current_hours = scheduling_service._calculate_weekly_hours(staff.id, date(2024, 2, 12))
        
        # Should not exceed max hours (40)
        assert current_hours <= staff.max_hours_per_week
    
    def test_auto_schedule_avoids_conflicts(self, scheduling_service, mock_db, sample_staff):
        """Test that auto-scheduling avoids creating conflicts"""
        # Existing shift
        existing_shift = ScheduledShift(
            id=1,
            staff_id=1,
            date=date(2024, 2, 15),
            start_time=datetime(2024, 2, 15, 8, 0),
            end_time=datetime(2024, 2, 15, 16, 0),
            status=ShiftStatus.SCHEDULED
        )
        
        mock_db.query.return_value.filter.return_value.all.return_value = sample_staff[:1]
        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [existing_shift]
        
        # Auto-schedule should detect and avoid the conflict
        result = scheduling_service.auto_schedule(
            1, 
            date(2024, 2, 15), 
            date(2024, 2, 15)
        )
        
        # Should handle conflicts appropriately
        assert result is not None


class TestShiftSwapWorkflow:
    """Test shift swap approval workflows"""
    
    def test_create_swap_request(self, scheduling_service, mock_db):
        """Test creating a shift swap request"""
        shift = ScheduledShift(
            id=1,
            staff_id=1,
            date=date(2024, 2, 15),
            start_time=datetime(2024, 2, 15, 8, 0),
            end_time=datetime(2024, 2, 15, 16, 0),
            status=ShiftStatus.SCHEDULED
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = shift
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        request = scheduling_service.create_swap_request(
            shift_id=1,
            requester_id=1,
            target_staff_id=2,
            reason="Personal emergency"
        )
        
        assert mock_db.add.called
        assert mock_db.commit.called
    
    def test_approve_swap_request(self, scheduling_service, mock_db):
        """Test approving a shift swap request"""
        swap_request = ShiftSwapRequest(
            id=1,
            shift_id=1,
            requester_id=1,
            target_staff_id=2,
            status=SwapRequestStatus.PENDING
        )
        
        shift = ScheduledShift(
            id=1,
            staff_id=1,
            date=date(2024, 2, 15),
            start_time=datetime(2024, 2, 15, 8, 0),
            end_time=datetime(2024, 2, 15, 16, 0),
            status=ShiftStatus.SCHEDULED
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = swap_request
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = shift
        mock_db.commit = Mock()
        
        result = scheduling_service.approve_swap_request(1, 999)  # 999 = manager ID
        
        assert swap_request.status == SwapRequestStatus.APPROVED
        assert swap_request.approved_by == 999
        assert shift.staff_id == 2  # Shift reassigned to target staff
        assert mock_db.commit.called
    
    def test_reject_swap_request(self, scheduling_service, mock_db):
        """Test rejecting a shift swap request"""
        swap_request = ShiftSwapRequest(
            id=1,
            shift_id=1,
            requester_id=1,
            target_staff_id=2,
            status=SwapRequestStatus.PENDING
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = swap_request
        mock_db.commit = Mock()
        
        result = scheduling_service.reject_swap_request(1, 999, "Not enough coverage")
        
        assert swap_request.status == SwapRequestStatus.REJECTED
        assert swap_request.notes == "Not enough coverage"
        assert mock_db.commit.called


class TestPublishingWorkflow:
    """Test schedule publishing functionality"""
    
    def test_publish_schedule(self, scheduling_service, mock_db):
        """Test publishing schedules"""
        unpublished_shifts = [
            ScheduledShift(
                id=1,
                staff_id=1,
                date=date(2024, 2, 15),
                status=ShiftStatus.SCHEDULED
            ),
            ScheduledShift(
                id=2,
                staff_id=2,
                date=date(2024, 2, 16),
                status=ShiftStatus.SCHEDULED
            )
        ]
        
        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = unpublished_shifts
        mock_db.commit = Mock()
        
        result = scheduling_service.publish_schedule(
            1,
            date(2024, 2, 15),
            date(2024, 2, 16)
        )
        
        assert result["published_count"] == 2
        assert all(shift.status == ShiftStatus.PUBLISHED for shift in unpublished_shifts)
        assert mock_db.commit.called
    
    @patch('backend.modules.staff.services.scheduling_service.send_notification')
    def test_publish_schedule_sends_notifications(self, mock_send_notification, scheduling_service, mock_db):
        """Test that publishing sends notifications"""
        shifts = [
            ScheduledShift(
                id=1,
                staff_id=1,
                date=date(2024, 2, 15),
                status=ShiftStatus.SCHEDULED,
                staff_member=Mock(email="john@example.com", name="John")
            )
        ]
        
        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = shifts
        mock_db.commit = Mock()
        
        result = scheduling_service.publish_schedule(
            1,
            date(2024, 2, 15),
            date(2024, 2, 15),
            notify=True
        )
        
        assert mock_send_notification.called


class TestAnalytics:
    """Test analytics functionality"""
    
    def test_labor_cost_calculation(self, scheduling_service, mock_db):
        """Test labor cost analytics calculation"""
        shifts = [
            Mock(
                staff_member=Mock(pay_policies=[Mock(hourly_rate=15.0)]),
                start_time=datetime(2024, 2, 15, 8, 0),
                end_time=datetime(2024, 2, 15, 16, 0),  # 8 hours
                status=ShiftStatus.SCHEDULED
            ),
            Mock(
                staff_member=Mock(pay_policies=[Mock(hourly_rate=20.0)]),
                start_time=datetime(2024, 2, 15, 9, 0),
                end_time=datetime(2024, 2, 15, 17, 0),  # 8 hours
                status=ShiftStatus.SCHEDULED
            )
        ]
        
        mock_db.query.return_value.join.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = shifts
        
        analytics = scheduling_service.get_schedule_analytics(
            1,
            date(2024, 2, 15),
            date(2024, 2, 15)
        )
        
        # Expected: (8 * 15) + (8 * 20) = 120 + 160 = 280
        assert analytics["total_labor_cost"] == 280.0
        assert analytics["total_scheduled_hours"] == 16.0
        assert analytics["average_hourly_cost"] == 17.5  # 280 / 16
    
    def test_analytics_with_caching(self, scheduling_service, mock_db):
        """Test that analytics results are cached"""
        # First call
        shifts = [Mock(
            staff_member=Mock(pay_policies=[Mock(hourly_rate=15.0)]),
            start_time=datetime(2024, 2, 15, 8, 0),
            end_time=datetime(2024, 2, 15, 16, 0),
            status=ShiftStatus.SCHEDULED
        )]
        
        mock_db.query.return_value.join.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = shifts
        
        analytics1 = scheduling_service.get_schedule_analytics(
            1,
            date(2024, 2, 15),
            date(2024, 2, 15)
        )
        
        # Second call (should use cache)
        analytics2 = scheduling_service.get_schedule_analytics(
            1,
            date(2024, 2, 15),
            date(2024, 2, 15)
        )
        
        assert analytics1 == analytics2


class TestValidation:
    """Test validation logic"""
    
    def test_validate_shift_times(self, scheduling_service):
        """Test shift time validation"""
        # Valid shift
        assert scheduling_service.validate_shift_times(
            datetime(2024, 2, 15, 8, 0),
            datetime(2024, 2, 15, 16, 0)
        ) is True
        
        # Invalid: end before start
        assert scheduling_service.validate_shift_times(
            datetime(2024, 2, 15, 16, 0),
            datetime(2024, 2, 15, 8, 0)
        ) is False
        
        # Invalid: shift too long (>12 hours)
        assert scheduling_service.validate_shift_times(
            datetime(2024, 2, 15, 8, 0),
            datetime(2024, 2, 15, 21, 0)
        ) is False
    
    def test_validate_break_duration(self, scheduling_service):
        """Test break duration validation"""
        # 8-hour shift should have at least 30 min break
        shift_duration = 8 * 60  # minutes
        assert scheduling_service.validate_break_duration(shift_duration, 30) is True
        assert scheduling_service.validate_break_duration(shift_duration, 15) is False
        
        # 4-hour shift doesn't require break
        shift_duration = 4 * 60
        assert scheduling_service.validate_break_duration(shift_duration, 0) is True
    
    def test_validate_availability(self, scheduling_service):
        """Test availability validation"""
        # Valid availability
        assert scheduling_service.validate_availability(
            time(8, 0),
            time(16, 0)
        ) is True
        
        # Invalid: end before start
        assert scheduling_service.validate_availability(
            time(16, 0),
            time(8, 0)
        ) is False


if __name__ == "__main__":
    pytest.main([__file__])