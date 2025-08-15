# backend/modules/tables/services/reservation_service.py

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload
import logging
import string
import random
from decimal import Decimal

from ..models.table_models import (
    Table,
    TableReservation,
    TableSession,
    TableStatus,
    ReservationStatus,
)
from ..schemas.table_schemas import TableReservationCreate, TableReservationUpdate
from core.exceptions import (
    ConflictError as BusinessLogicError,
    NotFoundError as ResourceNotFoundError,
)
from core.notification_service import NotificationService

# TODO: Create proper instance when service is initialized
# notification_service = NotificationService()

logger = logging.getLogger(__name__)


class ReservationService:
    """Service for managing table reservations"""

    def __init__(self):
        self.default_duration_minutes = 120
        self.min_advance_minutes = 30
        self.max_advance_days = 90
        self.reminder_advance_hours = 2

    async def create_reservation(
        self,
        db: AsyncSession,
        restaurant_id: int,
        reservation_data: TableReservationCreate,
    ) -> TableReservation:
        """Create a new reservation"""

        # Validate reservation time
        self._validate_reservation_time(reservation_data.reservation_date)

        # Generate reservation code
        reservation_code = await self._generate_reservation_code(db)

        # Auto-assign table if not specified
        table_id = reservation_data.table_id
        if not table_id:
            table_id = await self._auto_assign_table(
                db,
                restaurant_id,
                reservation_data.reservation_date,
                reservation_data.duration_minutes,
                reservation_data.guest_count,
                reservation_data.table_preferences,
            )

            if not table_id:
                raise BusinessLogicError(
                    "No suitable tables available for the requested time and party size"
                )
        else:
            # Validate specified table
            await self._validate_table_for_reservation(
                db,
                restaurant_id,
                table_id,
                reservation_data.reservation_date,
                reservation_data.duration_minutes,
                reservation_data.guest_count,
            )

        # Create reservation
        reservation = TableReservation(
            restaurant_id=restaurant_id,
            table_id=table_id,
            customer_id=reservation_data.customer_id,
            reservation_code=reservation_code,
            reservation_date=reservation_data.reservation_date,
            duration_minutes=reservation_data.duration_minutes,
            guest_count=reservation_data.guest_count,
            guest_name=reservation_data.guest_name,
            guest_phone=reservation_data.guest_phone,
            guest_email=reservation_data.guest_email,
            special_requests=reservation_data.special_requests,
            occasion=reservation_data.occasion,
            table_preferences=reservation_data.table_preferences,
            deposit_amount=reservation_data.deposit_amount,
            source=reservation_data.source,
        )

        db.add(reservation)
        await db.commit()
        await db.refresh(reservation)

        # Send confirmation notification
        await self._send_reservation_confirmation(reservation)

        return reservation

    async def update_reservation(
        self,
        db: AsyncSession,
        restaurant_id: int,
        reservation_id: int,
        update_data: TableReservationUpdate,
    ) -> TableReservation:
        """Update an existing reservation"""

        reservation = await self._get_reservation(db, reservation_id, restaurant_id)

        # Check if reservation can be modified
        if reservation.status in [
            ReservationStatus.COMPLETED,
            ReservationStatus.CANCELLED,
        ]:
            raise BusinessLogicError(f"Cannot modify {reservation.status} reservation")

        # Validate new time if changed
        if (
            update_data.reservation_date
            and update_data.reservation_date != reservation.reservation_date
        ):
            self._validate_reservation_time(update_data.reservation_date)

        # Handle table change
        if (
            update_data.table_id is not None
            and update_data.table_id != reservation.table_id
        ):
            new_date = update_data.reservation_date or reservation.reservation_date
            new_duration = update_data.duration_minutes or reservation.duration_minutes
            new_guest_count = update_data.guest_count or reservation.guest_count

            if update_data.table_id:
                # Validate new table
                await self._validate_table_for_reservation(
                    db,
                    restaurant_id,
                    update_data.table_id,
                    new_date,
                    new_duration,
                    new_guest_count,
                )
            else:
                # Auto-assign new table
                update_data.table_id = await self._auto_assign_table(
                    db,
                    restaurant_id,
                    new_date,
                    new_duration,
                    new_guest_count,
                    update_data.table_preferences or reservation.table_preferences,
                )

                if not update_data.table_id:
                    raise BusinessLogicError(
                        "No suitable tables available for the updated requirements"
                    )

        # Update fields
        for field, value in update_data.dict(exclude_unset=True).items():
            setattr(reservation, field, value)

        await db.commit()
        await db.refresh(reservation)

        # Send update notification
        await self._send_reservation_update(reservation)

        return reservation

    async def confirm_reservation(
        self, db: AsyncSession, restaurant_id: int, reservation_id: int
    ) -> TableReservation:
        """Confirm a pending reservation"""

        reservation = await self._get_reservation(db, reservation_id, restaurant_id)

        if reservation.status != ReservationStatus.PENDING:
            raise BusinessLogicError(
                f"Cannot confirm reservation with status {reservation.status}"
            )

        reservation.status = ReservationStatus.CONFIRMED
        reservation.confirmed_at = datetime.utcnow()

        await db.commit()
        await db.refresh(reservation)

        # Send confirmation
        await self._send_reservation_confirmation(reservation)

        return reservation

    async def cancel_reservation(
        self,
        db: AsyncSession,
        restaurant_id: int,
        reservation_id: int,
        reason: Optional[str] = None,
    ) -> TableReservation:
        """Cancel a reservation"""

        reservation = await self._get_reservation(db, reservation_id, restaurant_id)

        if reservation.status in [
            ReservationStatus.COMPLETED,
            ReservationStatus.CANCELLED,
        ]:
            raise BusinessLogicError(f"Cannot cancel {reservation.status} reservation")

        reservation.status = ReservationStatus.CANCELLED
        reservation.cancelled_at = datetime.utcnow()
        reservation.cancellation_reason = reason

        # TODO: Process refund if deposit was paid
        if reservation.deposit_paid:
            logger.info(f"Refund needed for reservation {reservation.reservation_code}")

        await db.commit()
        await db.refresh(reservation)

        # Send cancellation notification
        await self._send_reservation_cancellation(reservation)

        return reservation

    async def seat_reservation(
        self,
        db: AsyncSession,
        restaurant_id: int,
        reservation_id: int,
        server_id: Optional[int] = None,
    ) -> Tuple[TableReservation, TableSession]:
        """Convert reservation to active session"""

        reservation = await self._get_reservation(db, reservation_id, restaurant_id)

        if reservation.status not in [
            ReservationStatus.PENDING,
            ReservationStatus.CONFIRMED,
        ]:
            raise BusinessLogicError(f"Cannot seat {reservation.status} reservation")

        # Check if it's close to reservation time (allow 30 min early)
        time_until = (
            reservation.reservation_date - datetime.utcnow()
        ).total_seconds() / 60
        if time_until > 30:
            raise BusinessLogicError(
                f"Reservation is not due for {int(time_until)} minutes"
            )

        # Get table
        table = await self._get_table(db, reservation.table_id, restaurant_id)

        if table.status != TableStatus.AVAILABLE:
            raise BusinessLogicError(
                f"Reserved table {table.table_number} is not available"
            )

        # Create session
        from .table_state_service import table_state_service
        from ..schemas.table_schemas import TableSessionCreate

        session_data = TableSessionCreate(
            table_id=reservation.table_id,
            guest_count=reservation.guest_count,
            guest_name=reservation.guest_name,
            guest_phone=reservation.guest_phone,
            server_id=server_id,
        )

        session = await table_state_service.start_table_session(
            db, restaurant_id, session_data, server_id or 1  # TODO: Get actual user
        )

        # Update reservation
        reservation.status = ReservationStatus.SEATED
        reservation.seated_at = datetime.utcnow()

        await db.commit()

        return reservation, session

    async def mark_no_show(
        self, db: AsyncSession, restaurant_id: int, reservation_id: int
    ) -> TableReservation:
        """Mark reservation as no-show"""

        reservation = await self._get_reservation(db, reservation_id, restaurant_id)

        if reservation.status != ReservationStatus.CONFIRMED:
            raise BusinessLogicError(
                f"Cannot mark {reservation.status} reservation as no-show"
            )

        # Check if past reservation time
        if datetime.utcnow() < reservation.reservation_date:
            raise BusinessLogicError("Cannot mark future reservation as no-show")

        reservation.status = ReservationStatus.NO_SHOW

        # TODO: Track no-show history for customer

        await db.commit()
        await db.refresh(reservation)

        return reservation

    async def get_reservations(
        self,
        db: AsyncSession,
        restaurant_id: int,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        status: Optional[ReservationStatus] = None,
        customer_id: Optional[int] = None,
        table_id: Optional[int] = None,
    ) -> List[TableReservation]:
        """Get reservations with filters"""

        query = (
            select(TableReservation)
            .where(TableReservation.restaurant_id == restaurant_id)
            .options(
                selectinload(TableReservation.table),
                selectinload(TableReservation.customer),
            )
        )

        if date_from:
            query = query.where(TableReservation.reservation_date >= date_from)
        if date_to:
            query = query.where(TableReservation.reservation_date <= date_to)
        if status:
            query = query.where(TableReservation.status == status)
        if customer_id:
            query = query.where(TableReservation.customer_id == customer_id)
        if table_id:
            query = query.where(TableReservation.table_id == table_id)

        query = query.order_by(TableReservation.reservation_date)

        result = await db.execute(query)
        return result.scalars().all()

    async def send_reminders(
        self, db: AsyncSession, restaurant_id: int
    ) -> List[TableReservation]:
        """Send reminders for upcoming reservations"""

        reminder_time = datetime.utcnow() + timedelta(hours=self.reminder_advance_hours)

        query = select(TableReservation).where(
            and_(
                TableReservation.restaurant_id == restaurant_id,
                TableReservation.status == ReservationStatus.CONFIRMED,
                TableReservation.reservation_date <= reminder_time,
                TableReservation.reservation_date > datetime.utcnow(),
                TableReservation.reminder_sent == False,
            )
        )

        result = await db.execute(query)
        reservations = result.scalars().all()

        reminded = []
        for reservation in reservations:
            try:
                await self._send_reservation_reminder(reservation)
                reservation.reminder_sent = True
                reservation.reminder_sent_at = datetime.utcnow()
                reminded.append(reservation)
            except Exception as e:
                logger.error(
                    f"Failed to send reminder for {reservation.reservation_code}: {e}"
                )

        await db.commit()

        return reminded

    async def _validate_reservation_time(self, reservation_date: datetime):
        """Validate reservation time constraints"""

        now = datetime.utcnow()

        # Check minimum advance time
        min_time = now + timedelta(minutes=self.min_advance_minutes)
        if reservation_date < min_time:
            raise BusinessLogicError(
                f"Reservations must be made at least {self.min_advance_minutes} minutes in advance"
            )

        # Check maximum advance time
        max_time = now + timedelta(days=self.max_advance_days)
        if reservation_date > max_time:
            raise BusinessLogicError(
                f"Reservations cannot be made more than {self.max_advance_days} days in advance"
            )

    async def _auto_assign_table(
        self,
        db: AsyncSession,
        restaurant_id: int,
        reservation_date: datetime,
        duration_minutes: int,
        guest_count: int,
        preferences: Dict[str, Any],
    ) -> Optional[int]:
        """Auto-assign best available table"""

        from .table_state_service import table_state_service

        # Get available tables
        end_time = reservation_date + timedelta(minutes=duration_minutes)
        available_tables = await table_state_service.get_table_availability(
            db, restaurant_id, reservation_date, end_time, guest_count
        )

        if not available_tables:
            return None

        # Score tables based on preferences
        scored_tables = []
        for table_info in available_tables:
            score = 0

            # Prefer tables with capacity close to party size
            capacity_diff = table_info["max_capacity"] - guest_count
            if capacity_diff == 0:
                score += 10
            elif capacity_diff <= 2:
                score += 5

            # Apply preferences
            features = table_info["features"]
            if preferences.get("by_window") and features["is_by_window"]:
                score += 8
            if (
                preferences.get("wheelchair_accessible")
                and features["is_wheelchair_accessible"]
            ):
                score += 10
            if preferences.get("private") and features["is_private"]:
                score += 7
            if preferences.get("quiet") and table_info.get("section") != "Bar":
                score += 5

            scored_tables.append((score, table_info["table_id"]))

        # Sort by score (highest first) and return best match
        scored_tables.sort(key=lambda x: x[0], reverse=True)

        return scored_tables[0][1] if scored_tables else None

    async def _validate_table_for_reservation(
        self,
        db: AsyncSession,
        restaurant_id: int,
        table_id: int,
        reservation_date: datetime,
        duration_minutes: int,
        guest_count: int,
    ):
        """Validate if table can be reserved"""

        # Get table
        table = await self._get_table(db, table_id, restaurant_id)

        # Check capacity
        if guest_count > table.max_capacity:
            raise BusinessLogicError(
                f"Table {table.table_number} has maximum capacity of {table.max_capacity}"
            )

        # Check availability
        from .table_state_service import table_state_service

        end_time = reservation_date + timedelta(minutes=duration_minutes)
        is_available = await table_state_service._is_table_available(
            db, table_id, reservation_date, end_time
        )

        if not is_available:
            raise BusinessLogicError(
                f"Table {table.table_number} is not available at the requested time"
            )

    async def _generate_reservation_code(self, db: AsyncSession) -> str:
        """Generate unique reservation code"""

        while True:
            # Generate 8-character code
            code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

            # Check uniqueness
            query = select(TableReservation).where(
                TableReservation.reservation_code == code
            )
            result = await db.execute(query)

            if not result.scalar():
                return code

    async def _get_reservation(
        self, db: AsyncSession, reservation_id: int, restaurant_id: int
    ) -> TableReservation:
        """Get reservation by ID with validation"""

        query = select(TableReservation).where(
            and_(
                TableReservation.id == reservation_id,
                TableReservation.restaurant_id == restaurant_id,
            )
        )

        result = await db.execute(query)
        reservation = result.scalar_one_or_none()

        if not reservation:
            raise ResourceNotFoundError(f"Reservation {reservation_id} not found")

        return reservation

    async def _get_table(
        self, db: AsyncSession, table_id: int, restaurant_id: int
    ) -> Table:
        """Get table by ID with validation"""

        query = select(Table).where(
            and_(Table.id == table_id, Table.restaurant_id == restaurant_id)
        )

        result = await db.execute(query)
        table = result.scalar_one_or_none()

        if not table:
            raise ResourceNotFoundError(f"Table {table_id} not found")

        return table

    async def _send_reservation_confirmation(self, reservation: TableReservation):
        """Send reservation confirmation notification"""

        # TODO: Implement actual notification
        logger.info(
            f"Sending confirmation for reservation {reservation.reservation_code}"
        )

    async def _send_reservation_update(self, reservation: TableReservation):
        """Send reservation update notification"""

        # TODO: Implement actual notification
        logger.info(f"Sending update for reservation {reservation.reservation_code}")

    async def _send_reservation_cancellation(self, reservation: TableReservation):
        """Send cancellation notification"""

        # TODO: Implement actual notification
        logger.info(
            f"Sending cancellation for reservation {reservation.reservation_code}"
        )

    async def _send_reservation_reminder(self, reservation: TableReservation):
        """Send reservation reminder"""

        # TODO: Implement actual notification
        logger.info(f"Sending reminder for reservation {reservation.reservation_code}")


# Create singleton service
reservation_service = ReservationService()
