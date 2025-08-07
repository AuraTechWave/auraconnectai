# backend/modules/reservations/tests/test_availability_service.py

"""
Tests for availability service.
"""

import pytest
from datetime import date, time, datetime, timedelta
from sqlalchemy.orm import Session

from ..services import AvailabilityService
from ..models.reservation_models import (
    Reservation, ReservationStatus, TableConfiguration,
    ReservationSettings, SpecialDate
)


class TestAvailabilityService:
    """Test availability service functionality"""
    
    @pytest.fixture
    def service(self, db_session: Session):
        """Create service instance"""
        return AvailabilityService(db_session)
    
    @pytest.fixture
    def test_tables(self, db_session: Session):
        """Create test table configurations"""
        tables = [
            TableConfiguration(
                table_number="1",
                section="main",
                min_capacity=2,
                max_capacity=4,
                preferred_capacity=2,
                priority=1
            ),
            TableConfiguration(
                table_number="2",
                section="main",
                min_capacity=2,
                max_capacity=4,
                preferred_capacity=4,
                priority=1
            ),
            TableConfiguration(
                table_number="3",
                section="main",
                min_capacity=4,
                max_capacity=6,
                preferred_capacity=4,
                priority=2
            ),
            TableConfiguration(
                table_number="4",
                section="patio",
                min_capacity=2,
                max_capacity=4,
                features=["outdoor", "umbrella"],
                priority=0
            ),
            TableConfiguration(
                table_number="5",
                section="main",
                min_capacity=6,
                max_capacity=8,
                is_combinable=True,
                combine_with=["6"],
                priority=1
            ),
            TableConfiguration(
                table_number="6",
                section="main",
                min_capacity=6,
                max_capacity=8,
                is_combinable=True,
                combine_with=["5"],
                priority=1
            )
        ]
        for table in tables:
            db_session.add(table)
        db_session.commit()
        return tables
    
    @pytest.fixture
    def reservation_settings(self, db_session: Session):
        """Create test reservation settings"""
        settings = ReservationSettings(
            restaurant_id=1,
            total_capacity=50,
            buffer_percentage=0.1,
            slot_duration_minutes=30,
            operating_hours={
                "monday": {"open": "11:00", "close": "22:00"},
                "tuesday": {"open": "11:00", "close": "22:00"},
                "wednesday": {"open": "11:00", "close": "22:00"},
                "thursday": {"open": "11:00", "close": "22:00"},
                "friday": {"open": "11:00", "close": "23:00"},
                "saturday": {"open": "10:00", "close": "23:00"},
                "sunday": {"open": "10:00", "close": "21:00"}
            }
        )
        db_session.add(settings)
        db_session.commit()
        return settings
    
    @pytest.mark.asyncio
    async def test_check_availability_success(
        self, service, test_tables, reservation_settings
    ):
        """Test successful availability check"""
        tomorrow = date.today() + timedelta(days=1)
        
        available, reason = await service.check_availability(
            tomorrow,
            time(19, 0),
            party_size=4,
            duration_minutes=90
        )
        
        assert available is True
        assert reason is None
    
    @pytest.mark.asyncio
    async def test_check_availability_special_date_closed(
        self, service, test_tables, reservation_settings, db_session
    ):
        """Test availability check on closed special date"""
        tomorrow = date.today() + timedelta(days=1)
        
        # Create special date - closed
        special_date = SpecialDate(
            date=tomorrow,
            name="Christmas",
            is_closed=True
        )
        db_session.add(special_date)
        db_session.commit()
        
        available, reason = await service.check_availability(
            tomorrow,
            time(19, 0),
            party_size=4,
            duration_minutes=90
        )
        
        assert available is False
        assert "closed" in reason
    
    @pytest.mark.asyncio
    async def test_check_availability_special_date_restrictions(
        self, service, test_tables, reservation_settings, db_session
    ):
        """Test availability check with special date party size restrictions"""
        tomorrow = date.today() + timedelta(days=1)
        
        # Create special date with restrictions
        special_date = SpecialDate(
            date=tomorrow,
            name="Valentine's Day",
            min_party_size=2,
            max_party_size=4
        )
        db_session.add(special_date)
        db_session.commit()
        
        # Party too large
        available, reason = await service.check_availability(
            tomorrow,
            time(19, 0),
            party_size=6,
            duration_minutes=90
        )
        
        assert available is False
        assert "Maximum party size" in reason
        
        # Valid party size
        available, reason = await service.check_availability(
            tomorrow,
            time(19, 0),
            party_size=2,
            duration_minutes=90
        )
        
        assert available is True
    
    @pytest.mark.asyncio
    async def test_check_availability_capacity_limit(
        self, service, test_tables, reservation_settings, db_session
    ):
        """Test availability check against capacity limits"""
        tomorrow = date.today() + timedelta(days=1)
        
        # Fill up capacity
        for i in range(10):
            reservation = Reservation(
                customer_id=i+1,
                reservation_date=tomorrow,
                reservation_time=time(19, 0),
                party_size=5,
                duration_minutes=90,
                status=ReservationStatus.CONFIRMED,
                confirmation_code=f"TEST-{i:04d}",
                table_ids=[i % 3 + 1]
            )
            db_session.add(reservation)
        db_session.commit()
        
        # Check availability (should fail due to capacity)
        available, reason = await service.check_availability(
            tomorrow,
            time(19, 0),
            party_size=4,
            duration_minutes=90
        )
        
        assert available is False
        assert "No tables available" in reason
    
    @pytest.mark.asyncio
    async def test_get_available_tables(
        self, service, test_tables, db_session
    ):
        """Test getting available tables for a time slot"""
        tomorrow = date.today() + timedelta(days=1)
        
        # Reserve one table
        reservation = Reservation(
            customer_id=1,
            reservation_date=tomorrow,
            reservation_time=time(19, 0),
            party_size=2,
            duration_minutes=90,
            status=ReservationStatus.CONFIRMED,
            confirmation_code="TEST-0001",
            table_ids=[1]  # Reserve table 1
        )
        db_session.add(reservation)
        db_session.commit()
        
        # Get available tables for party of 2
        available = await service.get_available_tables(
            tomorrow,
            time(19, 0),
            duration_minutes=90,
            party_size=2
        )
        
        # Table 1 should not be available
        table_numbers = [t.table_number for t in available]
        assert "1" not in table_numbers
        assert "2" in table_numbers  # Can accommodate 2
        assert "4" in table_numbers  # Patio table can accommodate 2
        
        # Tables 3, 5, 6 are too large for party of 2
        assert "3" not in table_numbers
        assert "5" not in table_numbers
        assert "6" not in table_numbers
    
    @pytest.mark.asyncio
    async def test_get_available_tables_combinable(
        self, service, test_tables
    ):
        """Test getting combinable tables for larger parties"""
        tomorrow = date.today() + timedelta(days=1)
        
        # Get available tables for large party
        available = await service.get_available_tables(
            tomorrow,
            time(19, 0),
            duration_minutes=90,
            party_size=12  # Needs combination
        )
        
        # Should include combinable tables
        table_numbers = [t.table_number for t in available]
        assert "5" in table_numbers or "6" in table_numbers
    
    @pytest.mark.asyncio
    async def test_assign_tables_single(
        self, service, test_tables
    ):
        """Test table assignment for single table"""
        tomorrow = date.today() + timedelta(days=1)
        
        # Assign for party of 2
        assigned = await service.assign_tables(
            tomorrow,
            time(19, 0),
            party_size=2,
            duration_minutes=90
        )
        
        assert len(assigned) == 1
        assert assigned[0].min_capacity <= 2 <= assigned[0].max_capacity
        
        # Should prefer table with matching preferred capacity
        if assigned[0].preferred_capacity:
            assert assigned[0].preferred_capacity == 2
    
    @pytest.mark.asyncio
    async def test_assign_tables_combination(
        self, service, test_tables
    ):
        """Test table assignment requiring combination"""
        tomorrow = date.today() + timedelta(days=1)
        
        # Assign for large party
        assigned = await service.assign_tables(
            tomorrow,
            time(19, 0),
            party_size=14,  # Needs tables 5 + 6
            duration_minutes=90
        )
        
        assert len(assigned) == 2
        table_numbers = [t.table_number for t in assigned]
        assert "5" in table_numbers
        assert "6" in table_numbers
    
    def test_get_time_slots(
        self, service, reservation_settings
    ):
        """Test getting time slots for a date"""
        # Use next Monday for consistent testing
        days_until_monday = (7 - date.today().weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        next_monday = date.today() + timedelta(days=days_until_monday)
        
        slots = service.get_time_slots(
            next_monday,
            party_size=2,
            duration_minutes=90
        )
        
        assert len(slots) > 0
        
        # First slot should be at opening time
        assert slots[0]["time"] == time(11, 0)
        
        # Slots should be 30 minutes apart (based on settings)
        if len(slots) > 1:
            slot1_minutes = slots[0]["time"].hour * 60 + slots[0]["time"].minute
            slot2_minutes = slots[1]["time"].hour * 60 + slots[1]["time"].minute
            assert slot2_minutes - slot1_minutes == 30
        
        # All slots should have availability info
        for slot in slots:
            assert "available" in slot
            assert "capacity_remaining" in slot
            assert "waitlist_count" in slot
    
    def test_get_time_slots_special_date(
        self, service, reservation_settings, db_session
    ):
        """Test getting time slots for special date"""
        tomorrow = date.today() + timedelta(days=1)
        
        # Create special date with different hours
        special_date = SpecialDate(
            date=tomorrow,
            name="New Year's Eve",
            special_hours={"open": "17:00", "close": "02:00"}
        )
        db_session.add(special_date)
        db_session.commit()
        
        slots = service.get_time_slots(
            tomorrow,
            party_size=2,
            duration_minutes=90
        )
        
        # Should use special hours
        assert slots[0]["time"] == time(17, 0)
    
    def test_get_effective_capacity(
        self, service, reservation_settings, db_session
    ):
        """Test calculating effective capacity"""
        tomorrow = date.today() + timedelta(days=1)
        
        # Normal day
        capacity = service._get_effective_capacity(tomorrow, reservation_settings)
        assert capacity == 50  # Base capacity
        
        # Special date with reduced capacity
        special_date = SpecialDate(
            date=tomorrow,
            name="Private Event",
            capacity_modifier=0.5  # 50% capacity
        )
        db_session.add(special_date)
        db_session.commit()
        
        capacity = service._get_effective_capacity(tomorrow, reservation_settings)
        assert capacity == 25  # 50% of 50
    
    def test_get_overlapping_capacity(
        self, service, db_session
    ):
        """Test calculating overlapping reservation capacity"""
        tomorrow = date.today() + timedelta(days=1)
        
        # Create reservations with different times
        # 18:00-19:30 (party of 4)
        res1 = Reservation(
            customer_id=1,
            reservation_date=tomorrow,
            reservation_time=time(18, 0),
            duration_minutes=90,
            party_size=4,
            status=ReservationStatus.CONFIRMED,
            confirmation_code="TEST-0001"
        )
        
        # 19:00-20:30 (party of 6)
        res2 = Reservation(
            customer_id=2,
            reservation_date=tomorrow,
            reservation_time=time(19, 0),
            duration_minutes=90,
            party_size=6,
            status=ReservationStatus.CONFIRMED,
            confirmation_code="TEST-0002"
        )
        
        # 20:00-21:30 (party of 2)
        res3 = Reservation(
            customer_id=3,
            reservation_date=tomorrow,
            reservation_time=time(20, 0),
            duration_minutes=90,
            party_size=2,
            status=ReservationStatus.CONFIRMED,
            confirmation_code="TEST-0003"
        )
        
        # Cancelled (should not count)
        res4 = Reservation(
            customer_id=4,
            reservation_date=tomorrow,
            reservation_time=time(19, 0),
            duration_minutes=90,
            party_size=10,
            status=ReservationStatus.CANCELLED,
            confirmation_code="TEST-0004"
        )
        
        for res in [res1, res2, res3, res4]:
            db_session.add(res)
        db_session.commit()
        
        # Check capacity at 19:00 (overlaps with res1 and res2)
        capacity = service._get_overlapping_capacity(
            tomorrow,
            time(19, 0),
            duration_minutes=90
        )
        assert capacity == 10  # 4 + 6
        
        # Check capacity at 20:00 (overlaps with res2 and res3)
        capacity = service._get_overlapping_capacity(
            tomorrow,
            time(20, 0),
            duration_minutes=90
        )
        assert capacity == 8  # 6 + 2
        
        # Check with exclusion
        capacity = service._get_overlapping_capacity(
            tomorrow,
            time(19, 0),
            duration_minutes=90,
            exclude_reservation_id=res2.id
        )
        assert capacity == 4  # Only res1
    
    def test_get_peak_times(
        self, service, db_session
    ):
        """Test getting peak reservation times"""
        tomorrow = date.today() + timedelta(days=1)
        
        # Create reservations at different times
        times_and_sizes = [
            (time(12, 0), 10),
            (time(12, 0), 15),
            (time(19, 0), 20),
            (time(19, 0), 25),
            (time(20, 0), 15)
        ]
        
        for i, (t, size) in enumerate(times_and_sizes):
            reservation = Reservation(
                customer_id=i+1,
                reservation_date=tomorrow,
                reservation_time=t,
                party_size=size,
                status=ReservationStatus.CONFIRMED,
                confirmation_code=f"TEST-{i:04d}"
            )
            db_session.add(reservation)
        db_session.commit()
        
        peak_times = service.get_peak_times(tomorrow)
        
        assert len(peak_times) == 3
        
        # Should be grouped by time
        peak_dict = {pt["time"]: pt["total_guests"] for pt in peak_times}
        assert peak_dict[time(12, 0)] == 25  # 10 + 15
        assert peak_dict[time(19, 0)] == 45  # 20 + 25
        assert peak_dict[time(20, 0)] == 15