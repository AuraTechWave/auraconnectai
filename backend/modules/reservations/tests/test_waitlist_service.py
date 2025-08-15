# backend/modules/reservations/tests/test_waitlist_service.py

"""
Tests for waitlist service.
"""

import pytest
from datetime import datetime, date, time, timedelta
from sqlalchemy.orm import Session

from ..services import WaitlistService, ReservationService
from ..models.reservation_models import (
    Waitlist,
    WaitlistStatus,
    Reservation,
    ReservationStatus,
    ReservationSettings,
    NotificationMethod,
)
from ..schemas.reservation_schemas import WaitlistCreate, ReservationCreate
from modules.customers.models.customer_models import Customer


class TestWaitlistService:
    """Test waitlist service functionality"""

    @pytest.fixture
    def service(self, db_session: Session):
        """Create service instance"""
        return WaitlistService(db_session)

    @pytest.fixture
    def reservation_service(self, db_session: Session):
        """Create reservation service instance"""
        return ReservationService(db_session)

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
    def test_customer2(self, db_session: Session):
        """Create second test customer"""
        customer = Customer(
            first_name="Another",
            last_name="Customer",
            email="another@example.com",
            phone="+0987654321",
        )
        db_session.add(customer)
        db_session.commit()
        return customer

    @pytest.fixture
    def reservation_settings(self, db_session: Session):
        """Create test reservation settings"""
        settings = ReservationSettings(
            restaurant_id=1,
            waitlist_enabled=True,
            waitlist_notification_window=30,
            waitlist_auto_expire_hours=24,
        )
        db_session.add(settings)
        db_session.commit()
        return settings

    @pytest.mark.asyncio
    async def test_add_to_waitlist_success(
        self, service, test_customer, reservation_settings
    ):
        """Test successful waitlist addition"""
        tomorrow = date.today() + timedelta(days=1)
        waitlist_data = WaitlistCreate(
            requested_date=tomorrow,
            requested_time_start=time(19, 0),
            requested_time_end=time(21, 0),
            party_size=4,
            special_requests="Prefer booth seating",
        )

        entry = await service.add_to_waitlist(test_customer.id, waitlist_data)

        assert entry.id is not None
        assert entry.customer_id == test_customer.id
        assert entry.requested_date == tomorrow
        assert entry.status == WaitlistStatus.WAITING
        assert entry.position == 1
        assert entry.expires_at is not None

    @pytest.mark.asyncio
    async def test_add_to_waitlist_duplicate(
        self, service, test_customer, reservation_settings
    ):
        """Test adding duplicate waitlist entry"""
        tomorrow = date.today() + timedelta(days=1)
        waitlist_data = WaitlistCreate(
            requested_date=tomorrow,
            requested_time_start=time(19, 0),
            requested_time_end=time(21, 0),
            party_size=4,
        )

        # Add first entry
        await service.add_to_waitlist(test_customer.id, waitlist_data)

        # Try to add duplicate
        with pytest.raises(ValueError, match="already have an active waitlist"):
            await service.add_to_waitlist(test_customer.id, waitlist_data)

    @pytest.mark.asyncio
    async def test_waitlist_position_calculation(
        self, service, test_customer, test_customer2, reservation_settings
    ):
        """Test waitlist position calculation"""
        tomorrow = date.today() + timedelta(days=1)

        # Add first customer
        waitlist_data1 = WaitlistCreate(
            requested_date=tomorrow,
            requested_time_start=time(19, 0),
            requested_time_end=time(21, 0),
            party_size=2,
        )
        entry1 = await service.add_to_waitlist(test_customer.id, waitlist_data1)
        assert entry1.position == 1

        # Add second customer
        waitlist_data2 = WaitlistCreate(
            requested_date=tomorrow,
            requested_time_start=time(19, 30),
            requested_time_end=time(21, 30),
            party_size=4,
        )
        entry2 = await service.add_to_waitlist(test_customer2.id, waitlist_data2)
        assert entry2.position == 2

    @pytest.mark.asyncio
    async def test_check_waitlist_for_availability(
        self, service, test_customer, test_customer2, reservation_settings, db_session
    ):
        """Test checking waitlist when table becomes available"""
        tomorrow = date.today() + timedelta(days=1)

        # Add multiple waitlist entries
        entries = []
        for i, customer in enumerate([test_customer, test_customer2]):
            waitlist_data = WaitlistCreate(
                requested_date=tomorrow,
                requested_time_start=time(19, 0),
                requested_time_end=time(21, 0),
                party_size=2,
                priority=1 if i == 1 else 0,  # Second customer has higher priority
            )
            entry = await service.add_to_waitlist(customer.id, waitlist_data)
            entries.append(entry)

        # Check waitlist for availability
        await service.check_waitlist_for_availability(
            tomorrow, time(19, 30), available_capacity=4
        )

        # Refresh entries
        db_session.refresh(entries[0])
        db_session.refresh(entries[1])

        # Higher priority customer should be notified first
        assert entries[1].status == WaitlistStatus.NOTIFIED
        assert entries[1].notified_at is not None
        assert entries[1].notification_expires_at is not None

    @pytest.mark.asyncio
    async def test_confirm_waitlist_availability(
        self,
        service,
        reservation_service,
        test_customer,
        reservation_settings,
        db_session,
    ):
        """Test converting waitlist to reservation"""
        tomorrow = date.today() + timedelta(days=1)

        # Add to waitlist
        waitlist_data = WaitlistCreate(
            requested_date=tomorrow,
            requested_time_start=time(19, 0),
            requested_time_end=time(21, 0),
            party_size=2,
        )
        entry = await service.add_to_waitlist(test_customer.id, waitlist_data)

        # Manually set as notified
        entry.status = WaitlistStatus.NOTIFIED
        entry.notified_at = datetime.utcnow()
        entry.notification_expires_at = datetime.utcnow() + timedelta(minutes=30)
        db_session.commit()

        # Create table configuration for the test
        from ..models.reservation_models import TableConfiguration

        table = TableConfiguration(
            table_number="1", section="main", min_capacity=2, max_capacity=4
        )
        db_session.add(table)
        db_session.commit()

        # Confirm availability
        reservation = await service.confirm_waitlist_availability(
            entry.id, test_customer.id
        )

        assert reservation is not None
        assert reservation.customer_id == test_customer.id
        assert reservation.converted_from_waitlist is True
        assert reservation.waitlist_id == entry.id

        # Check waitlist entry status
        db_session.refresh(entry)
        assert entry.status == WaitlistStatus.CONVERTED
        assert entry.confirmed_at is not None

    @pytest.mark.asyncio
    async def test_confirm_expired_notification(
        self, service, test_customer, reservation_settings, db_session
    ):
        """Test confirming expired waitlist notification"""
        tomorrow = date.today() + timedelta(days=1)

        # Add to waitlist
        waitlist_data = WaitlistCreate(
            requested_date=tomorrow,
            requested_time_start=time(19, 0),
            requested_time_end=time(21, 0),
            party_size=2,
        )
        entry = await service.add_to_waitlist(test_customer.id, waitlist_data)

        # Set as notified but expired
        entry.status = WaitlistStatus.NOTIFIED
        entry.notified_at = datetime.utcnow() - timedelta(hours=1)
        entry.notification_expires_at = datetime.utcnow() - timedelta(minutes=30)
        db_session.commit()

        # Try to confirm
        with pytest.raises(ValueError, match="notification has expired"):
            await service.confirm_waitlist_availability(entry.id, test_customer.id)

        # Check status was updated
        db_session.refresh(entry)
        assert entry.status == WaitlistStatus.EXPIRED

    def test_cancel_waitlist_entry(
        self, service, test_customer, reservation_settings, db_session
    ):
        """Test cancelling waitlist entry"""
        tomorrow = date.today() + timedelta(days=1)

        # Create entry manually for testing
        entry = Waitlist(
            customer_id=test_customer.id,
            requested_date=tomorrow,
            requested_time_start=time(19, 0),
            requested_time_end=time(21, 0),
            party_size=2,
            status=WaitlistStatus.WAITING,
            position=1,
        )
        db_session.add(entry)
        db_session.commit()

        # Cancel entry
        cancelled = service.cancel_waitlist_entry(entry.id, test_customer.id)

        assert cancelled.status == WaitlistStatus.CANCELLED
        assert cancelled.updated_at is not None

    def test_cancel_converted_entry(self, service, test_customer, db_session):
        """Test cancelling already converted waitlist entry"""
        tomorrow = date.today() + timedelta(days=1)

        # Create converted entry
        entry = Waitlist(
            customer_id=test_customer.id,
            requested_date=tomorrow,
            requested_time_start=time(19, 0),
            requested_time_end=time(21, 0),
            party_size=2,
            status=WaitlistStatus.CONVERTED,
        )
        db_session.add(entry)
        db_session.commit()

        # Try to cancel
        with pytest.raises(ValueError, match="already converted or cancelled"):
            service.cancel_waitlist_entry(entry.id, test_customer.id)

    def test_get_customer_waitlist_entries(self, service, test_customer, db_session):
        """Test getting customer waitlist entries"""
        # Create multiple entries
        for i in range(3):
            entry = Waitlist(
                customer_id=test_customer.id,
                requested_date=date.today() + timedelta(days=i + 1),
                requested_time_start=time(19, 0),
                requested_time_end=time(21, 0),
                party_size=2,
                status=WaitlistStatus.WAITING,
            )
            db_session.add(entry)

        # Add cancelled entry
        cancelled = Waitlist(
            customer_id=test_customer.id,
            requested_date=date.today() + timedelta(days=4),
            requested_time_start=time(19, 0),
            requested_time_end=time(21, 0),
            party_size=2,
            status=WaitlistStatus.CANCELLED,
        )
        db_session.add(cancelled)
        db_session.commit()

        # Get active only
        active, total = service.get_customer_waitlist_entries(
            test_customer.id, active_only=True
        )
        assert total == 3

        # Get all
        all_entries, total = service.get_customer_waitlist_entries(
            test_customer.id, active_only=False
        )
        assert total == 4

    def test_get_waitlist_by_date(
        self, service, test_customer, test_customer2, db_session
    ):
        """Test getting waitlist entries by date"""
        target_date = date.today() + timedelta(days=1)

        # Create entries for target date
        for customer in [test_customer, test_customer2]:
            entry = Waitlist(
                customer_id=customer.id,
                requested_date=target_date,
                requested_time_start=time(19, 0),
                requested_time_end=time(21, 0),
                party_size=2,
                status=WaitlistStatus.WAITING,
                priority=1 if customer == test_customer2 else 0,
            )
            db_session.add(entry)

        # Create entry for different date
        other = Waitlist(
            customer_id=test_customer.id,
            requested_date=target_date + timedelta(days=1),
            requested_time_start=time(19, 0),
            requested_time_end=time(21, 0),
            party_size=2,
            status=WaitlistStatus.WAITING,
        )
        db_session.add(other)
        db_session.commit()

        # Get by date
        entries = service.get_waitlist_by_date(target_date)
        assert len(entries) == 2

        # Should be ordered by priority
        assert entries[0].priority == 1

    @pytest.mark.asyncio
    async def test_process_expired_notifications(
        self, service, test_customer, db_session
    ):
        """Test processing expired waitlist notifications"""
        # Create expired notification
        entry = Waitlist(
            customer_id=test_customer.id,
            requested_date=date.today() + timedelta(days=1),
            requested_time_start=time(19, 0),
            requested_time_end=time(21, 0),
            party_size=2,
            status=WaitlistStatus.NOTIFIED,
            notified_at=datetime.utcnow() - timedelta(hours=1),
            notification_expires_at=datetime.utcnow() - timedelta(minutes=30),
        )
        db_session.add(entry)
        db_session.commit()

        # Process expired
        await service.process_expired_notifications()

        # Check status
        db_session.refresh(entry)
        assert entry.status == WaitlistStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_process_expired_waitlist_entries(
        self, service, test_customer, db_session
    ):
        """Test processing expired waitlist entries"""
        # Create expired entry
        entry = Waitlist(
            customer_id=test_customer.id,
            requested_date=date.today() + timedelta(days=1),
            requested_time_start=time(19, 0),
            requested_time_end=time(21, 0),
            party_size=2,
            status=WaitlistStatus.WAITING,
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        db_session.add(entry)
        db_session.commit()

        # Process expired
        await service.process_expired_waitlist_entries()

        # Check status
        db_session.refresh(entry)
        assert entry.status == WaitlistStatus.EXPIRED

    def test_estimate_wait_time(self, service, test_customer, db_session):
        """Test wait time estimation"""
        tomorrow = date.today() + timedelta(days=1)
        target_time = time(19, 0)

        # No entries - no wait
        wait_time = service.estimate_wait_time(tomorrow, target_time, 2)
        assert wait_time is None

        # Add entries
        for i in range(3):
            entry = Waitlist(
                customer_id=test_customer.id,
                requested_date=tomorrow,
                requested_time_start=target_time,
                requested_time_end=time(21, 0),
                party_size=2,
                status=WaitlistStatus.WAITING,
                created_at=datetime.utcnow() - timedelta(hours=i + 1),
            )
            db_session.add(entry)
        db_session.commit()

        # Should estimate based on position
        wait_time = service.estimate_wait_time(tomorrow, target_time, 2)
        assert wait_time == 90  # 3 ahead * 30 minutes

    def test_recalculate_positions(
        self, service, test_customer, test_customer2, db_session
    ):
        """Test position recalculation after cancellation"""
        tomorrow = date.today() + timedelta(days=1)

        # Create multiple entries
        entries = []
        for i, customer in enumerate([test_customer, test_customer2, test_customer]):
            entry = Waitlist(
                customer_id=customer.id if i < 2 else test_customer.id,
                requested_date=tomorrow,
                requested_time_start=time(19, 0),
                requested_time_end=time(21, 0),
                party_size=2,
                status=WaitlistStatus.WAITING,
                position=i + 1,
                created_at=datetime.utcnow() + timedelta(seconds=i),
            )
            db_session.add(entry)
            entries.append(entry)
        db_session.commit()

        # Cancel middle entry
        service.cancel_waitlist_entry(entries[1].id, test_customer2.id)

        # Check positions were recalculated
        db_session.refresh(entries[0])
        db_session.refresh(entries[2])

        assert entries[0].position == 1
        assert entries[2].position == 2
