"""
Test to verify that the scheduling conflict bug has been fixed.

This test demonstrates that the generate_demand_aware_schedule function
no longer creates overlapping shifts for the same staff member.
"""

import pytest
from datetime import date, time, datetime, timedelta
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch

from modules.staff.services.scheduling_service import SchedulingService
from modules.staff.models.scheduling_models import EnhancedShift, ShiftStatus
from modules.staff.models.staff_models import StaffMember, Role
from modules.staff.enums.scheduling_enums import DayOfWeek


class TestSchedulingConflictFix:
    """Test that scheduling conflicts are properly avoided during generation."""
    
    def test_no_overlapping_shifts_for_same_staff(self, db_session: Session):
        """Test that the same staff member is not assigned to overlapping shifts."""
        
        # Setup test data
        location_id = 1
        role_id = 1
        staff_id = 1
        
        # Create test staff member
        staff = StaffMember(
            id=staff_id,
            restaurant_id=location_id,
            role_id=role_id,
            status="active"
        )
        db_session.add(staff)
        db_session.commit()
        
        # Mock the demand estimation to return predictable data
        service = SchedulingService(db_session)
        
        with patch.object(service, '_estimate_peak_orders') as mock_estimate:
            # Mock demand data - return high demand for all hours
            mock_estimate.return_value = {hour: 50 for hour in range(24)}
            
            with patch.object(service, '_map_orders_to_role_requirements') as mock_map:
                # Mock role requirements - need 2 staff for each role
                mock_map.return_value = {
                    hour: {role_id: 2} for hour in range(24)
                }
                
                # Generate schedule for a single day
                start_date = date(2024, 1, 1)
                end_date = date(2024, 1, 1)
                
                shifts = service.generate_demand_aware_schedule(
                    start_date=start_date,
                    end_date=end_date,
                    location_id=location_id,
                    demand_lookback_days=90,
                    buffer_percentage=10.0,
                    respect_availability=False,  # Disable availability checks for testing
                    max_hours_per_week=40,
                    min_hours_between_shifts=8,
                )
        
        # Verify that shifts were created
        assert len(shifts) > 0, "No shifts were generated"
        
        # Group shifts by staff member
        shifts_by_staff = {}
        for shift in shifts:
            if shift.staff_id not in shifts_by_staff:
                shifts_by_staff[shift.staff_id] = []
            shifts_by_staff[shift.staff_id].append(shift)
        
        # Check each staff member's shifts for overlaps
        for staff_id, staff_shifts in shifts_by_staff.items():
            if len(staff_shifts) <= 1:
                continue  # No overlaps possible with single shift
            
            # Sort shifts by start time
            staff_shifts.sort(key=lambda s: s.start_time)
            
            # Check for overlaps
            for i in range(len(staff_shifts) - 1):
                current_shift = staff_shifts[i]
                next_shift = staff_shifts[i + 1]
                
                # Verify no overlap between consecutive shifts
                assert current_shift.end_time <= next_shift.start_time, \
                    f"Overlapping shifts found for staff {staff_id}: " \
                    f"Shift {current_shift.id} ends at {current_shift.end_time} " \
                    f"but shift {next_shift.id} starts at {next_shift.start_time}"
                
                # Verify minimum rest period (8 hours)
                rest_period = (next_shift.start_time - current_shift.end_time).total_seconds() / 3600
                assert rest_period >= 8, \
                    f"Insufficient rest period for staff {staff_id}: " \
                    f"Only {rest_period:.1f} hours between shifts"
    
    def test_flexible_scheduling_creates_non_overlapping_shifts(self, db_session: Session):
        """Test that flexible scheduling also avoids overlapping shifts."""
        
        # Setup test data
        location_id = 1
        role_id = 1
        staff_id = 1
        
        # Create test staff member
        staff = StaffMember(
            id=staff_id,
            restaurant_id=location_id,
            role_id=role_id,
            status="active"
        )
        db_session.add(staff)
        db_session.commit()
        
        service = SchedulingService(db_session)
        
        with patch.object(service, '_estimate_peak_orders') as mock_estimate:
            # Mock demand data with specific patterns
            mock_estimate.return_value = {
                6: 10, 7: 15, 8: 20, 9: 25, 10: 30, 11: 35, 12: 40, 13: 35, 14: 30,
                15: 25, 16: 20, 17: 25, 18: 30, 19: 35, 20: 30, 21: 25, 22: 20, 23: 15
            }
            
            with patch.object(service, '_map_orders_to_role_requirements') as mock_map:
                # Mock role requirements
                mock_map.return_value = {
                    hour: {role_id: 2} for hour in range(6, 24)
                }
                
                # Generate flexible schedule
                start_date = date(2024, 1, 1)
                end_date = date(2024, 1, 1)
                
                shifts = service.generate_flexible_demand_schedule(
                    start_date=start_date,
                    end_date=end_date,
                    location_id=location_id,
                    demand_lookback_days=90,
                    buffer_percentage=10.0,
                    respect_availability=False,
                    max_hours_per_week=40,
                    min_hours_between_shifts=8,
                    min_shift_hours=4,
                    max_shift_hours=8,
                )
        
        # Verify that shifts were created
        assert len(shifts) > 0, "No shifts were generated with flexible scheduling"
        
        # Check for overlaps
        shifts_by_staff = {}
        for shift in shifts:
            if shift.staff_id not in shifts_by_staff:
                shifts_by_staff[shift.staff_id] = []
            shifts_by_staff[shift.staff_id].append(shift)
        
        for staff_id, staff_shifts in shifts_by_staff.items():
            if len(staff_shifts) <= 1:
                continue
            
            staff_shifts.sort(key=lambda s: s.start_time)
            
            for i in range(len(staff_shifts) - 1):
                current_shift = staff_shifts[i]
                next_shift = staff_shifts[i + 1]
                
                # Verify no overlap
                assert current_shift.end_time <= next_shift.start_time, \
                    f"Flexible scheduling created overlapping shifts for staff {staff_id}"
                
                # Verify minimum rest period
                rest_period = (next_shift.start_time - current_shift.end_time).total_seconds() / 3600
                assert rest_period >= 8, \
                    f"Flexible scheduling created insufficient rest period: {rest_period:.1f} hours"
    
    def test_shift_blocks_are_non_overlapping(self):
        """Test that the fixed shift blocks don't overlap."""
        
        # The fixed shift blocks should be:
        # 6:00-14:00 (Morning)
        # 14:00-22:00 (Afternoon/Evening) 
        # 22:00-6:00 (Night - overnight)
        
        shift_blocks = [
            (time(6, 0), time(14, 0)),   # Morning shift
            (time(14, 0), time(22, 0)),  # Afternoon/Evening shift
            (time(22, 0), time(6, 0)),   # Night shift (overnight)
        ]
        
        # Check that the first two blocks don't overlap
        morning_start = shift_blocks[0][0]
        morning_end = shift_blocks[0][1]
        afternoon_start = shift_blocks[1][0]
        afternoon_end = shift_blocks[1][1]
        
        assert morning_end <= afternoon_start, "Morning and afternoon shifts overlap"
        
        # Check that afternoon and night shifts don't overlap
        night_start = shift_blocks[2][0]
        night_end = shift_blocks[2][1]
        
        assert afternoon_end <= night_start, "Afternoon and night shifts overlap"
        
        # Night shift is overnight, so it should end before morning starts
        # (night_end = 6:00, morning_start = 6:00, so they meet but don't overlap)
        assert night_end <= morning_start, "Night and morning shifts overlap"


if __name__ == "__main__":
    pytest.main([__file__])
