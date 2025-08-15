# backend/modules/reservations/tests/test_reservation_service.py

"""
Tests for reservation service.
"""

import pytest
from datetime import datetime, date, time, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException

from ..services import ReservationService, AvailabilityService
from ..models.reservation_models import (
    Reservation,
    ReservationStatus,
    ReservationSettings,
    TableConfiguration,
    SpecialDate,
)
from ..schemas.reservation_schemas import (
    ReservationCreate,
    ReservationUpdate,
    ReservationCancellation,
    ReservationConfirmation,
)
from modules.customers.models.customer_models import Customer


class TestReservationService:
    """Test reservation service functionality"""

    @pytest.fixture
    def service(self, db_session: Session):
        """Create service instance"""
        return ReservationService(db_session)

    @pytest.fixture
    def availability_service(self, db_session: Session):
        """Create availability service instance"""
        return AvailabilityService(db_session)

    @pytest.fixture
    def test_customer(self, db_session: Session):
        """Create test customer"""
        customer = Customer(
            first_name="Test",
            last_name="Customer",
            email="test@example.com",
            phone="+1234567890",
        )
        db_session.add(customer)
        db_session.commit()
        return customer

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
            ),
            TableConfiguration(
                table_number="2",
                section="main",
                min_capacity=4,
                max_capacity=6,
                preferred_capacity=4,
            ),
            TableConfiguration(
                table_number="3",
                section="patio",
                min_capacity=2,
                max_capacity=4,
                preferred_capacity=2,
                features=["outdoor"],
            ),
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
            advance_booking_days=90,
            min_advance_hours=2,
            max_party_size=20,
            min_party_size=1,
            total_capacity=50,
            buffer_percentage=0.1,
            operating_hours={
                "monday": {"open": "11:00", "close": "22:00"},
                "tuesday": {"open": "11:00", "close": "22:00"},
                "wednesday": {"open": "11:00", "close": "22:00"},
                "thursday": {"open": "11:00", "close": "22:00"},
                "friday": {"open": "11:00", "close": "23:00"},
                "saturday": {"open": "10:00", "close": "23:00"},
                "sunday": {"open": "10:00", "close": "21:00"},
            },
        )
        db_session.add(settings)
        db_session.commit()
        return settings

    @pytest.mark.asyncio
    async def test_create_reservation_success(
        self, service, test_customer, test_tables, reservation_settings
    ):
        """Test successful reservation creation"""
        tomorrow = date.today() + timedelta(days=1)
        reservation_data = ReservationCreate(
            reservation_date=tomorrow,
            reservation_time=time(19, 0),
            party_size=2,
            special_requests="Window seat please",
        )

        reservation = await service.create_reservation(
            test_customer.id, reservation_data
        )

        assert reservation.id is not None
        assert reservation.customer_id == test_customer.id
        assert reservation.reservation_date == tomorrow
        assert reservation.reservation_time == time(19, 0)
        assert reservation.party_size == 2
        assert reservation.status == ReservationStatus.PENDING
        assert reservation.confirmation_code is not None
        assert reservation.table_numbers is not None

    @pytest.mark.asyncio
    async def test_create_reservation_no_availability(
        self, service, test_customer, test_tables, reservation_settings, db_session
    ):
        """Test reservation creation when no tables available"""
        tomorrow = date.today() + timedelta(days=1)

        # Create existing reservations to fill capacity
        for i in range(10):
            existing = Reservation(
                customer_id=test_customer.id,
                reservation_date=tomorrow,
                reservation_time=time(19, 0),
                party_size=5,
                status=ReservationStatus.CONFIRMED,
                confirmation_code=f"TEST-{i:04d}",
                table_ids=[1],
            )
            db_session.add(existing)
        db_session.commit()

        # Try to create another reservation
        reservation_data = ReservationCreate(
            reservation_date=tomorrow, reservation_time=time(19, 0), party_size=10
        )

        with pytest.raises(ValueError, match="not available"):
            await service.create_reservation(test_customer.id, reservation_data)

    @pytest.mark.asyncio
    async def test_create_reservation_past_date(
        self, service, test_customer, test_tables
    ):
        """Test reservation creation with past date"""
        yesterday = date.today() - timedelta(days=1)
        reservation_data = ReservationCreate(
            reservation_date=yesterday, reservation_time=time(19, 0), party_size=2
        )

        with pytest.raises(ValueError, match="cannot be in the past"):
            await service.create_reservation(test_customer.id, reservation_data)

    @pytest.mark.asyncio
    async def test_create_reservation_too_far_advance(
        self, service, test_customer, test_tables, reservation_settings
    ):
        """Test reservation creation too far in advance"""
        far_future = date.today() + timedelta(days=100)
        reservation_data = ReservationCreate(
            reservation_date=far_future, reservation_time=time(19, 0), party_size=2
        )

        with pytest.raises(ValueError, match="90 days in advance"):
            await service.create_reservation(test_customer.id, reservation_data)

    @pytest.mark.asyncio
    async def test_create_reservation_outside_hours(
        self, service, test_customer, test_tables, reservation_settings
    ):
        """Test reservation creation outside operating hours"""
        tomorrow = date.today() + timedelta(days=1)
        reservation_data = ReservationCreate(
            reservation_date=tomorrow,
            reservation_time=time(23, 0),  # After closing
            party_size=2,
        )

        with pytest.raises(ValueError, match="Restaurant hours"):
            await service.create_reservation(test_customer.id, reservation_data)

    @pytest.mark.asyncio
    async def test_create_reservation_special_date(
        self, service, test_customer, test_tables, db_session
    ):
        """Test reservation creation on special date"""
        tomorrow = date.today() + timedelta(days=1)

        # Create special date
        special_date = SpecialDate(
            date=tomorrow,
            name="Valentine's Day",
            min_party_size=2,
            max_party_size=6,
            special_hours={"open": "17:00", "close": "23:00"},
        )
        db_session.add(special_date)
        db_session.commit()

        # Try to create reservation during regular hours (should fail)
        reservation_data = ReservationCreate(
            reservation_date=tomorrow,
            reservation_time=time(12, 0),  # Regular hours but not special hours
            party_size=2,
        )

        with pytest.raises(ValueError, match="Special hours"):
            await service.create_reservation(test_customer.id, reservation_data)

        # Create during special hours (should succeed)
        reservation_data.reservation_time = time(18, 0)
        reservation = await service.create_reservation(
            test_customer.id, reservation_data
        )
        assert reservation.id is not None

    @pytest.mark.asyncio
    async def test_update_reservation_success(
        self, service, test_customer, test_tables, reservation_settings
    ):
        """Test successful reservation update"""
        # Create reservation
        tomorrow = date.today() + timedelta(days=1)
        reservation_data = ReservationCreate(
            reservation_date=tomorrow, reservation_time=time(19, 0), party_size=2
        )

        reservation = await service.create_reservation(
            test_customer.id, reservation_data
        )

        # Update reservation
        update_data = ReservationUpdate(
            party_size=4, special_requests="Need high chair"
        )

        updated = await service.update_reservation(
            reservation.id, test_customer.id, update_data
        )

        assert updated.party_size == 4
        assert updated.special_requests == "Need high chair"

    @pytest.mark.asyncio
    async def test_update_reservation_time_change(
        self, service, test_customer, test_tables, reservation_settings
    ):
        """Test reservation update with time change"""
        tomorrow = date.today() + timedelta(days=1)

        # Create reservation
        reservation_data = ReservationCreate(
            reservation_date=tomorrow, reservation_time=time(19, 0), party_size=2
        )

        reservation = await service.create_reservation(
            test_customer.id, reservation_data
        )

        # Update time
        update_data = ReservationUpdate(reservation_time=time(20, 0))

        updated = await service.update_reservation(
            reservation.id, test_customer.id, update_data
        )

        assert updated.reservation_time == time(20, 0)
        # Should have new table assignment
        assert updated.table_numbers is not None

    @pytest.mark.asyncio
    async def test_cancel_reservation_success(
        self, service, test_customer, test_tables, reservation_settings
    ):
        """Test successful reservation cancellation"""
        # Create reservation
        tomorrow = date.today() + timedelta(days=1)
        reservation_data = ReservationCreate(
            reservation_date=tomorrow, reservation_time=time(19, 0), party_size=2
        )

        reservation = await service.create_reservation(
            test_customer.id, reservation_data
        )

        # Cancel reservation
        cancellation_data = ReservationCancellation(
            reason="Changed plans", cancelled_by="customer"
        )

        cancelled = await service.cancel_reservation(
            reservation.id, test_customer.id, cancellation_data
        )

        assert cancelled.status == ReservationStatus.CANCELLED
        assert cancelled.cancellation_reason == "Changed plans"
        assert cancelled.cancelled_by == "customer"
        assert cancelled.cancelled_at is not None

    @pytest.mark.asyncio
    async def test_cancel_already_cancelled(
        self, service, test_customer, test_tables, reservation_settings
    ):
        """Test cancelling already cancelled reservation"""
        # Create and cancel reservation
        tomorrow = date.today() + timedelta(days=1)
        reservation_data = ReservationCreate(
            reservation_date=tomorrow, reservation_time=time(19, 0), party_size=2
        )

        reservation = await service.create_reservation(
            test_customer.id, reservation_data
        )

        cancellation_data = ReservationCancellation(
            reason="Changed plans", cancelled_by="customer"
        )

        await service.cancel_reservation(
            reservation.id, test_customer.id, cancellation_data
        )

        # Try to cancel again
        with pytest.raises(ValueError, match="already completed or cancelled"):
            await service.cancel_reservation(
                reservation.id, test_customer.id, cancellation_data
            )

    @pytest.mark.asyncio
    async def test_confirm_reservation_success(
        self, service, test_customer, test_tables, reservation_settings
    ):
        """Test reservation confirmation"""
        # Create reservation
        tomorrow = date.today() + timedelta(days=1)
        reservation_data = ReservationCreate(
            reservation_date=tomorrow, reservation_time=time(19, 0), party_size=2
        )

        reservation = await service.create_reservation(
            test_customer.id, reservation_data
        )

        # Confirm reservation
        confirmation_data = ReservationConfirmation(
            confirmed=True, special_requests_update="Allergic to nuts"
        )

        confirmed = await service.confirm_reservation(
            reservation.id, test_customer.id, confirmation_data
        )

        assert confirmed.status == ReservationStatus.CONFIRMED
        assert confirmed.confirmed_at is not None
        assert confirmed.special_requests == "Allergic to nuts"

    def test_get_reservation_by_code(self, service, test_customer, db_session):
        """Test getting reservation by confirmation code"""
        # Create reservation
        reservation = Reservation(
            customer_id=test_customer.id,
            reservation_date=date.today() + timedelta(days=1),
            reservation_time=time(19, 0),
            party_size=2,
            confirmation_code="RES-TEST-1234",
            status=ReservationStatus.PENDING,
        )
        db_session.add(reservation)
        db_session.commit()

        # Get by code
        found = service.get_reservation_by_confirmation_code("RES-TEST-1234")
        assert found is not None
        assert found.id == reservation.id

        # Non-existent code
        not_found = service.get_reservation_by_confirmation_code("INVALID")
        assert not_found is None

    def test_get_customer_reservations(self, service, test_customer, db_session):
        """Test getting customer reservations"""
        # Create multiple reservations
        for i in range(5):
            reservation = Reservation(
                customer_id=test_customer.id,
                reservation_date=date.today() + timedelta(days=i + 1),
                reservation_time=time(19, 0),
                party_size=2,
                confirmation_code=f"RES-TEST-{i:04d}",
                status=ReservationStatus.CONFIRMED,
            )
            db_session.add(reservation)
        db_session.commit()

        # Get all reservations
        reservations, total = service.get_customer_reservations(test_customer.id)
        assert total == 5
        assert len(reservations) == 5

        # Get upcoming only
        upcoming, total = service.get_customer_reservations(
            test_customer.id, upcoming_only=True
        )
        assert total == 5  # All are upcoming

        # Get with pagination
        page1, _ = service.get_customer_reservations(test_customer.id, skip=0, limit=2)
        assert len(page1) == 2

        page2, _ = service.get_customer_reservations(test_customer.id, skip=2, limit=2)
        assert len(page2) == 2

    @pytest.mark.asyncio
    async def test_staff_update_reservation(
        self, service, test_customer, test_tables, reservation_settings
    ):
        """Test staff updating reservation"""
        # Create reservation
        tomorrow = date.today() + timedelta(days=1)
        reservation_data = ReservationCreate(
            reservation_date=tomorrow, reservation_time=time(19, 0), party_size=2
        )

        reservation = await service.create_reservation(
            test_customer.id, reservation_data
        )

        # Confirm it first
        confirmation = ReservationConfirmation(confirmed=True)
        await service.confirm_reservation(
            reservation.id, test_customer.id, confirmation
        )

        # Staff marks as seated
        from ..schemas import StaffReservationUpdate

        staff_update = StaffReservationUpdate(
            status=ReservationStatus.SEATED, table_numbers="5", notes="VIP customer"
        )

        updated = await service.staff_update_reservation(reservation.id, staff_update)

        assert updated.status == ReservationStatus.SEATED
        assert updated.table_numbers == "5"
        assert "VIP customer" in updated.special_requests
        assert updated.seated_at is not None

    def test_get_daily_reservations(self, service, test_customer, db_session):
        """Test getting daily reservations for staff view"""
        target_date = date.today() + timedelta(days=1)

        # Create reservations for different times
        times = [time(12, 0), time(18, 0), time(19, 0), time(20, 0)]
        for t in times:
            reservation = Reservation(
                customer_id=test_customer.id,
                reservation_date=target_date,
                reservation_time=t,
                party_size=2,
                confirmation_code=f"RES-{t.hour:02d}00",
                status=ReservationStatus.CONFIRMED,
            )
            db_session.add(reservation)

        # Add one for different date
        other = Reservation(
            customer_id=test_customer.id,
            reservation_date=target_date + timedelta(days=1),
            reservation_time=time(19, 0),
            party_size=2,
            confirmation_code="RES-OTHER",
            status=ReservationStatus.CONFIRMED,
        )
        db_session.add(other)
        db_session.commit()

        # Get daily reservations
        daily = service.get_daily_reservations(target_date)
        assert len(daily) == 4

        # Should be ordered by time
        assert daily[0].reservation_time == time(12, 0)
        assert daily[-1].reservation_time == time(20, 0)

    def test_generate_confirmation_code(self, service):
        """Test confirmation code generation"""
        codes = set()

        # Generate multiple codes
        for _ in range(100):
            code = service.generate_confirmation_code()
            assert code.startswith("RES-")
            assert len(code) == 13  # RES-XXXX-XXXX
            codes.add(code)

        # All should be unique
        assert len(codes) == 100
