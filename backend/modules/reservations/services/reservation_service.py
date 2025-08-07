# backend/modules/reservations/services/reservation_service.py

"""
Enhanced reservation service with full booking management.
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime, date, time, timedelta
from typing import List, Optional, Dict, Tuple
import random
import string
import logging

from ..models.reservation_models import (
    Reservation, ReservationStatus, ReservationSettings,
    TableConfiguration, SpecialDate
)
from ..schemas.reservation_schemas import (
    ReservationCreate, ReservationUpdate, ReservationCancellation,
    ReservationConfirmation, StaffReservationUpdate
)
from .availability_service import AvailabilityService
from .notification_service import ReservationNotificationService

logger = logging.getLogger(__name__)


class ReservationService:
    """Service for managing reservations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.availability_service = AvailabilityService(db)
        self.notification_service = ReservationNotificationService(db)
        self._settings_cache = None
        self._settings_cache_time = None
    
    def get_settings(self, force_refresh: bool = False) -> ReservationSettings:
        """Get reservation settings with caching"""
        # Cache for 5 minutes
        if (not force_refresh and self._settings_cache and self._settings_cache_time and 
            datetime.utcnow() - self._settings_cache_time < timedelta(minutes=5)):
            return self._settings_cache
        
        settings = self.db.query(ReservationSettings).filter_by(restaurant_id=1).first()
        if not settings:
            # Create default settings
            settings = ReservationSettings(restaurant_id=1)
            self.db.add(settings)
            self.db.commit()
            self.db.refresh(settings)
        
        self._settings_cache = settings
        self._settings_cache_time = datetime.utcnow()
        return settings
    
    def generate_confirmation_code(self) -> str:
        """Generate a unique confirmation code"""
        while True:
            # Format: RES-XXXX-XXXX
            code = f"RES-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
            if not self.db.query(Reservation).filter_by(confirmation_code=code).first():
                return code
    
    async def create_reservation(
        self, 
        customer_id: int, 
        reservation_data: ReservationCreate,
        skip_availability_check: bool = False
    ) -> Reservation:
        """Create a new reservation"""
        settings = self.get_settings()
        
        # Validate booking rules
        self._validate_booking_rules(reservation_data, settings)
        
        # Check availability unless skipped (e.g., converting from waitlist)
        if not skip_availability_check:
            available, reason = await self.availability_service.check_availability(
                reservation_data.reservation_date,
                reservation_data.reservation_time,
                reservation_data.party_size,
                reservation_data.duration_minutes or settings.default_reservation_duration
            )
            
            if not available:
                raise ValueError(f"Reservation not available: {reason}")
        
        # Assign tables
        assigned_tables = await self.availability_service.assign_tables(
            reservation_data.reservation_date,
            reservation_data.reservation_time,
            reservation_data.party_size,
            reservation_data.duration_minutes or settings.default_reservation_duration
        )
        
        if not assigned_tables:
            raise ValueError("No suitable tables available")
        
        # Create reservation
        reservation = Reservation(
            customer_id=customer_id,
            reservation_date=reservation_data.reservation_date,
            reservation_time=reservation_data.reservation_time,
            party_size=reservation_data.party_size,
            duration_minutes=reservation_data.duration_minutes or settings.default_reservation_duration,
            special_requests=reservation_data.special_requests,
            dietary_restrictions=reservation_data.dietary_restrictions or [],
            occasion=reservation_data.occasion,
            notification_method=reservation_data.notification_method,
            source=reservation_data.source,
            status=ReservationStatus.PENDING,
            confirmation_code=self.generate_confirmation_code(),
            table_ids=[t.id for t in assigned_tables],
            table_numbers=", ".join([t.table_number for t in assigned_tables])
        )
        
        self.db.add(reservation)
        self.db.commit()
        self.db.refresh(reservation)
        
        # Send confirmation notification
        await self.notification_service.send_booking_confirmation(reservation)
        
        # Schedule reminder if enabled
        if settings.send_reminders:
            await self.notification_service.schedule_reminder(
                reservation,
                settings.reminder_hours_before
            )
        
        logger.info(f"Created reservation {reservation.id} for customer {customer_id}")
        
        return reservation
    
    def _validate_booking_rules(self, reservation_data: ReservationCreate, settings: ReservationSettings):
        """Validate reservation against booking rules"""
        now = datetime.utcnow()
        reservation_datetime = datetime.combine(
            reservation_data.reservation_date,
            reservation_data.reservation_time
        )
        
        # Check advance booking
        days_in_advance = (reservation_datetime.date() - now.date()).days
        if days_in_advance > settings.advance_booking_days:
            raise ValueError(f"Reservations can only be made up to {settings.advance_booking_days} days in advance")
        
        # Check minimum advance time
        hours_in_advance = (reservation_datetime - now).total_seconds() / 3600
        if hours_in_advance < settings.min_advance_hours:
            raise ValueError(f"Reservations must be made at least {settings.min_advance_hours} hours in advance")
        
        # Check party size
        if reservation_data.party_size < settings.min_party_size:
            raise ValueError(f"Minimum party size is {settings.min_party_size}")
        if reservation_data.party_size > settings.max_party_size:
            raise ValueError(f"Maximum party size is {settings.max_party_size}")
        
        # Check operating hours
        day_name = reservation_data.reservation_date.strftime("%A").lower()
        day_hours = settings.operating_hours.get(day_name)
        
        if not day_hours:
            raise ValueError(f"Restaurant is closed on {day_name}")
        
        open_time = datetime.strptime(day_hours["open"], "%H:%M").time()
        close_time = datetime.strptime(day_hours["close"], "%H:%M").time()
        
        if reservation_data.reservation_time < open_time or reservation_data.reservation_time >= close_time:
            raise ValueError(f"Restaurant hours on {day_name} are {open_time} to {close_time}")
        
        # Check special dates
        special_date = self.db.query(SpecialDate).filter_by(
            date=reservation_data.reservation_date
        ).first()
        
        if special_date:
            if special_date.is_closed:
                raise ValueError(f"Restaurant is closed on {special_date.name or 'this date'}")
            
            if special_date.special_hours:
                open_time = datetime.strptime(special_date.special_hours["open"], "%H:%M").time()
                close_time = datetime.strptime(special_date.special_hours["close"], "%H:%M").time()
                
                if reservation_data.reservation_time < open_time or reservation_data.reservation_time >= close_time:
                    raise ValueError(f"Special hours on {special_date.name}: {open_time} to {close_time}")
    
    async def update_reservation(
        self,
        reservation_id: int,
        customer_id: int,
        update_data: ReservationUpdate
    ) -> Reservation:
        """Update a reservation"""
        reservation = self.get_reservation(reservation_id, customer_id)
        if not reservation:
            raise ValueError("Reservation not found")
        
        # Check if reservation can be modified
        if reservation.status in [ReservationStatus.COMPLETED, ReservationStatus.CANCELLED]:
            raise ValueError("Cannot modify completed or cancelled reservations")
        
        # If changing date/time/size, need to check availability
        needs_availability_check = any([
            update_data.reservation_date and update_data.reservation_date != reservation.reservation_date,
            update_data.reservation_time and update_data.reservation_time != reservation.reservation_time,
            update_data.party_size and update_data.party_size != reservation.party_size
        ])
        
        if needs_availability_check:
            new_date = update_data.reservation_date or reservation.reservation_date
            new_time = update_data.reservation_time or reservation.reservation_time
            new_size = update_data.party_size or reservation.party_size
            
            # Check availability
            available, reason = await self.availability_service.check_availability(
                new_date,
                new_time,
                new_size,
                reservation.duration_minutes,
                exclude_reservation_id=reservation_id
            )
            
            if not available:
                raise ValueError(f"Updated time not available: {reason}")
            
            # Reassign tables
            assigned_tables = await self.availability_service.assign_tables(
                new_date,
                new_time,
                new_size,
                reservation.duration_minutes,
                exclude_reservation_id=reservation_id
            )
            
            if not assigned_tables:
                raise ValueError("No suitable tables available for the update")
            
            reservation.table_ids = [t.id for t in assigned_tables]
            reservation.table_numbers = ", ".join([t.table_number for t in assigned_tables])
        
        # Update fields
        for field, value in update_data.dict(exclude_unset=True).items():
            setattr(reservation, field, value)
        
        reservation.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(reservation)
        
        # Send update notification
        await self.notification_service.send_update_notification(reservation)
        
        logger.info(f"Updated reservation {reservation_id}")
        
        return reservation
    
    async def cancel_reservation(
        self,
        reservation_id: int,
        customer_id: int,
        cancellation_data: ReservationCancellation
    ) -> Reservation:
        """Cancel a reservation"""
        reservation = self.get_reservation(reservation_id, customer_id)
        if not reservation:
            raise ValueError("Reservation not found")
        
        if reservation.status in [ReservationStatus.COMPLETED, ReservationStatus.CANCELLED]:
            raise ValueError("Reservation is already completed or cancelled")
        
        reservation.status = ReservationStatus.CANCELLED
        reservation.cancelled_at = datetime.utcnow()
        reservation.cancellation_reason = cancellation_data.reason
        reservation.cancelled_by = cancellation_data.cancelled_by
        
        self.db.commit()
        self.db.refresh(reservation)
        
        # Send cancellation notification
        await self.notification_service.send_cancellation_notification(
            reservation,
            cancellation_data.reason
        )
        
        # Check waitlist for this time slot
        await self._check_waitlist_for_opening(
            reservation.reservation_date,
            reservation.reservation_time,
            reservation.party_size
        )
        
        logger.info(f"Cancelled reservation {reservation_id}")
        
        return reservation
    
    async def confirm_reservation(
        self,
        reservation_id: int,
        customer_id: int,
        confirmation_data: ReservationConfirmation
    ) -> Reservation:
        """Confirm a pending reservation"""
        reservation = self.get_reservation(reservation_id, customer_id)
        if not reservation:
            raise ValueError("Reservation not found")
        
        if reservation.status != ReservationStatus.PENDING:
            raise ValueError("Only pending reservations can be confirmed")
        
        reservation.status = ReservationStatus.CONFIRMED
        reservation.confirmed_at = datetime.utcnow()
        
        if confirmation_data.special_requests_update:
            reservation.special_requests = confirmation_data.special_requests_update
        
        self.db.commit()
        self.db.refresh(reservation)
        
        # Send confirmation notification
        await self.notification_service.send_confirmation_status_notification(reservation)
        
        logger.info(f"Confirmed reservation {reservation_id}")
        
        return reservation
    
    def get_reservation(
        self, 
        reservation_id: int, 
        customer_id: Optional[int] = None
    ) -> Optional[Reservation]:
        """Get a reservation by ID"""
        query = self.db.query(Reservation).filter_by(id=reservation_id)
        if customer_id:
            query = query.filter_by(customer_id=customer_id)
        return query.first()
    
    def get_reservation_by_confirmation_code(self, code: str) -> Optional[Reservation]:
        """Get a reservation by confirmation code"""
        return self.db.query(Reservation).filter_by(confirmation_code=code).first()
    
    def get_customer_reservations(
        self,
        customer_id: int,
        status: Optional[ReservationStatus] = None,
        upcoming_only: bool = False,
        skip: int = 0,
        limit: int = 20
    ) -> Tuple[List[Reservation], int]:
        """Get all reservations for a customer"""
        query = self.db.query(Reservation).filter_by(customer_id=customer_id)
        
        if status:
            query = query.filter_by(status=status)
        
        if upcoming_only:
            now = datetime.utcnow()
            query = query.filter(
                or_(
                    Reservation.reservation_date > now.date(),
                    and_(
                        Reservation.reservation_date == now.date(),
                        Reservation.reservation_time > now.time()
                    )
                )
            )
        
        # Get total count
        total = query.count()
        
        # Get paginated results
        reservations = query.order_by(
            Reservation.reservation_date.desc(),
            Reservation.reservation_time.desc()
        ).offset(skip).limit(limit).all()
        
        return reservations, total
    
    async def _check_waitlist_for_opening(
        self,
        date: date,
        time: time,
        party_size: int
    ):
        """Check if any waitlist entries can be converted to reservations"""
        # This will be implemented in the waitlist service
        pass
    
    # Staff methods
    async def staff_update_reservation(
        self,
        reservation_id: int,
        update_data: StaffReservationUpdate
    ) -> Reservation:
        """Staff update reservation status or details"""
        reservation = self.db.query(Reservation).filter_by(id=reservation_id).first()
        if not reservation:
            raise ValueError("Reservation not found")
        
        # Update status
        if update_data.status:
            old_status = reservation.status
            reservation.status = update_data.status
            
            # Set appropriate timestamps
            if update_data.status == ReservationStatus.SEATED:
                reservation.seated_at = datetime.utcnow()
            elif update_data.status == ReservationStatus.COMPLETED:
                reservation.completed_at = datetime.utcnow()
            elif update_data.status == ReservationStatus.NO_SHOW:
                # Track no-shows for customer
                await self._track_no_show(reservation.customer_id)
        
        # Update table assignment
        if update_data.table_numbers:
            reservation.table_numbers = update_data.table_numbers
        
        # Add staff notes
        if update_data.notes:
            if reservation.special_requests:
                reservation.special_requests += f"\n[Staff note]: {update_data.notes}"
            else:
                reservation.special_requests = f"[Staff note]: {update_data.notes}"
        
        self.db.commit()
        self.db.refresh(reservation)
        
        logger.info(f"Staff updated reservation {reservation_id}")
        
        return reservation
    
    async def _track_no_show(self, customer_id: int):
        """Track customer no-shows"""
        settings = self.get_settings()
        if not settings.track_no_shows:
            return
        
        # Count recent no-shows (last 6 months)
        six_months_ago = datetime.utcnow() - timedelta(days=180)
        no_show_count = self.db.query(Reservation).filter(
            Reservation.customer_id == customer_id,
            Reservation.status == ReservationStatus.NO_SHOW,
            Reservation.created_at >= six_months_ago
        ).count()
        
        if no_show_count >= settings.no_show_threshold:
            # Mark customer for review or block future reservations
            logger.warning(f"Customer {customer_id} has {no_show_count} no-shows")
            # Implementation would depend on customer model structure
    
    def get_daily_reservations(
        self,
        date: date,
        status: Optional[ReservationStatus] = None
    ) -> List[Reservation]:
        """Get all reservations for a specific date (staff view)"""
        query = self.db.query(Reservation).filter(
            Reservation.reservation_date == date
        )
        
        if status:
            query = query.filter_by(status=status)
        
        return query.order_by(Reservation.reservation_time).all()
    
    async def process_unconfirmed_reservations(self):
        """Process unconfirmed reservations that need confirmation"""
        settings = self.get_settings()
        if not settings.require_confirmation:
            return
        
        # Find reservations that need confirmation
        confirmation_deadline = datetime.utcnow() + timedelta(hours=settings.confirmation_required_hours)
        
        unconfirmed = self.db.query(Reservation).filter(
            Reservation.status == ReservationStatus.PENDING,
            Reservation.reservation_date == confirmation_deadline.date(),
            Reservation.reservation_time <= confirmation_deadline.time()
        ).all()
        
        for reservation in unconfirmed:
            # Send reminder to confirm
            await self.notification_service.send_confirmation_reminder(reservation)
            
            if settings.auto_cancel_unconfirmed:
                # Schedule auto-cancellation
                # This would be handled by a background task
                pass