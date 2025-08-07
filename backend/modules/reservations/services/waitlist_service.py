# backend/modules/reservations/services/waitlist_service.py

"""
Waitlist management service for handling reservation overflow.
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime, date, time, timedelta
from typing import List, Optional, Tuple
import logging

from ..models.reservation_models import (
    Waitlist, WaitlistStatus, Reservation, ReservationSettings,
    ReservationStatus
)
from ..schemas.reservation_schemas import WaitlistCreate
from .notification_service import ReservationNotificationService
from .reservation_service import ReservationService

logger = logging.getLogger(__name__)


class WaitlistService:
    """Service for managing waitlist entries"""
    
    def __init__(self, db: Session):
        self.db = db
        self.notification_service = ReservationNotificationService(db)
    
    async def add_to_waitlist(
        self,
        customer_id: int,
        waitlist_data: WaitlistCreate
    ) -> Waitlist:
        """Add a customer to the waitlist"""
        # Check if customer already has an active waitlist entry for this date
        existing = self.db.query(Waitlist).filter(
            Waitlist.customer_id == customer_id,
            Waitlist.requested_date == waitlist_data.requested_date,
            Waitlist.status.in_([WaitlistStatus.WAITING, WaitlistStatus.NOTIFIED])
        ).first()
        
        if existing:
            raise ValueError("You already have an active waitlist entry for this date")
        
        # Calculate position in waitlist
        position = self._calculate_waitlist_position(
            waitlist_data.requested_date,
            waitlist_data.requested_time_start,
            waitlist_data.party_size
        )
        
        # Get settings for expiration
        settings = self.db.query(ReservationSettings).filter_by(restaurant_id=1).first()
        expires_at = datetime.utcnow() + timedelta(hours=settings.waitlist_auto_expire_hours)
        
        # Create waitlist entry
        waitlist_entry = Waitlist(
            customer_id=customer_id,
            requested_date=waitlist_data.requested_date,
            requested_time_start=waitlist_data.requested_time_start,
            requested_time_end=waitlist_data.requested_time_end,
            party_size=waitlist_data.party_size,
            flexible_date=waitlist_data.flexible_date,
            flexible_time=waitlist_data.flexible_time,
            alternative_dates=waitlist_data.alternative_dates or [],
            special_requests=waitlist_data.special_requests,
            notification_method=waitlist_data.notification_method,
            status=WaitlistStatus.WAITING,
            position=position,
            expires_at=expires_at
        )
        
        self.db.add(waitlist_entry)
        self.db.commit()
        self.db.refresh(waitlist_entry)
        
        # Send confirmation notification
        await self.notification_service.send_waitlist_confirmation(waitlist_entry)
        
        logger.info(f"Added customer {customer_id} to waitlist with position {position}")
        
        return waitlist_entry
    
    def _calculate_waitlist_position(
        self,
        requested_date: date,
        requested_time: time,
        party_size: int
    ) -> int:
        """Calculate position in waitlist based on various factors"""
        # Get active waitlist entries for the same date
        active_entries = self.db.query(Waitlist).filter(
            Waitlist.requested_date == requested_date,
            Waitlist.status.in_([WaitlistStatus.WAITING, WaitlistStatus.NOTIFIED])
        ).count()
        
        return active_entries + 1
    
    async def check_waitlist_for_availability(
        self,
        target_date: date,
        target_time: time,
        available_capacity: int
    ):
        """Check waitlist when a table becomes available"""
        settings = self.db.query(ReservationSettings).filter_by(restaurant_id=1).first()
        
        # Find matching waitlist entries
        time_window_start = (datetime.combine(target_date, target_time) - timedelta(hours=1)).time()
        time_window_end = (datetime.combine(target_date, target_time) + timedelta(hours=1)).time()
        
        matching_entries = self.db.query(Waitlist).filter(
            Waitlist.status == WaitlistStatus.WAITING,
            Waitlist.party_size <= available_capacity,
            or_(
                # Exact date match
                and_(
                    Waitlist.requested_date == target_date,
                    Waitlist.requested_time_start <= time_window_end,
                    Waitlist.requested_time_end >= time_window_start
                ),
                # Flexible date
                and_(
                    Waitlist.flexible_date == True,
                    Waitlist.requested_date >= target_date
                ),
                # Alternative dates
                Waitlist.alternative_dates.contains([target_date])
            )
        ).order_by(
            Waitlist.priority.desc(),  # VIP customers first
            Waitlist.position  # Then by position
        ).all()
        
        for entry in matching_entries:
            # Notify customer about availability
            await self.notify_waitlist_availability(
                entry,
                target_date,
                target_time,
                settings.waitlist_notification_window
            )
            
            # Only notify a limited number to avoid overbooking
            if len(matching_entries) >= 3:  # Notify top 3
                break
    
    async def notify_waitlist_availability(
        self,
        waitlist_entry: Waitlist,
        available_date: date,
        available_time: time,
        response_window_minutes: int
    ):
        """Notify a waitlist customer about availability"""
        waitlist_entry.status = WaitlistStatus.NOTIFIED
        waitlist_entry.notified_at = datetime.utcnow()
        waitlist_entry.notification_expires_at = datetime.utcnow() + timedelta(
            minutes=response_window_minutes
        )
        
        self.db.commit()
        
        # Send notification
        await self.notification_service.send_waitlist_availability_notification(
            waitlist_entry,
            available_date,
            available_time,
            response_window_minutes
        )
        
        logger.info(f"Notified waitlist entry {waitlist_entry.id} about availability")
    
    async def confirm_waitlist_availability(
        self,
        waitlist_id: int,
        customer_id: int
    ) -> Reservation:
        """Convert waitlist entry to reservation when customer confirms"""
        waitlist_entry = self.db.query(Waitlist).filter(
            Waitlist.id == waitlist_id,
            Waitlist.customer_id == customer_id
        ).first()
        
        if not waitlist_entry:
            raise ValueError("Waitlist entry not found")
        
        if waitlist_entry.status != WaitlistStatus.NOTIFIED:
            raise ValueError("This waitlist entry has not been notified of availability")
        
        if datetime.utcnow() > waitlist_entry.notification_expires_at:
            waitlist_entry.status = WaitlistStatus.EXPIRED
            self.db.commit()
            raise ValueError("The notification has expired")
        
        # Create reservation from waitlist
        from ..schemas.reservation_schemas import ReservationCreate
        
        reservation_service = ReservationService(self.db)
        
        reservation_data = ReservationCreate(
            reservation_date=waitlist_entry.requested_date,
            reservation_time=waitlist_entry.requested_time_start,
            party_size=waitlist_entry.party_size,
            special_requests=waitlist_entry.special_requests,
            notification_method=waitlist_entry.notification_method,
            source="waitlist"
        )
        
        try:
            # Create reservation (skip availability check as we've already verified)
            reservation = await reservation_service.create_reservation(
                customer_id,
                reservation_data,
                skip_availability_check=True
            )
            
            # Update waitlist entry
            waitlist_entry.status = WaitlistStatus.CONVERTED
            waitlist_entry.confirmed_at = datetime.utcnow()
            
            # Link reservation to waitlist
            reservation.waitlist_id = waitlist_entry.id
            reservation.converted_from_waitlist = True
            
            self.db.commit()
            self.db.refresh(reservation)
            
            logger.info(f"Converted waitlist entry {waitlist_id} to reservation {reservation.id}")
            
            return reservation
            
        except Exception as e:
            logger.error(f"Failed to convert waitlist to reservation: {str(e)}")
            raise
    
    def cancel_waitlist_entry(
        self,
        waitlist_id: int,
        customer_id: int
    ) -> Waitlist:
        """Cancel a waitlist entry"""
        waitlist_entry = self.db.query(Waitlist).filter(
            Waitlist.id == waitlist_id,
            Waitlist.customer_id == customer_id
        ).first()
        
        if not waitlist_entry:
            raise ValueError("Waitlist entry not found")
        
        if waitlist_entry.status in [WaitlistStatus.CONVERTED, WaitlistStatus.CANCELLED]:
            raise ValueError("Waitlist entry is already converted or cancelled")
        
        waitlist_entry.status = WaitlistStatus.CANCELLED
        waitlist_entry.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(waitlist_entry)
        
        # Recalculate positions for remaining entries
        self._recalculate_positions(
            waitlist_entry.requested_date,
            waitlist_entry.requested_time_start
        )
        
        logger.info(f"Cancelled waitlist entry {waitlist_id}")
        
        return waitlist_entry
    
    def _recalculate_positions(self, date: date, time: time):
        """Recalculate waitlist positions after a cancellation"""
        active_entries = self.db.query(Waitlist).filter(
            Waitlist.requested_date == date,
            Waitlist.status.in_([WaitlistStatus.WAITING, WaitlistStatus.NOTIFIED])
        ).order_by(
            Waitlist.priority.desc(),
            Waitlist.created_at
        ).all()
        
        for idx, entry in enumerate(active_entries, 1):
            entry.position = idx
        
        self.db.commit()
    
    def get_customer_waitlist_entries(
        self,
        customer_id: int,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 20
    ) -> Tuple[List[Waitlist], int]:
        """Get waitlist entries for a customer"""
        query = self.db.query(Waitlist).filter_by(customer_id=customer_id)
        
        if active_only:
            query = query.filter(
                Waitlist.status.in_([WaitlistStatus.WAITING, WaitlistStatus.NOTIFIED])
            )
        
        total = query.count()
        
        entries = query.order_by(
            Waitlist.requested_date.desc(),
            Waitlist.created_at.desc()
        ).offset(skip).limit(limit).all()
        
        return entries, total
    
    def get_waitlist_by_date(
        self,
        date: date,
        status: Optional[WaitlistStatus] = None
    ) -> List[Waitlist]:
        """Get all waitlist entries for a date (staff view)"""
        query = self.db.query(Waitlist).filter(
            Waitlist.requested_date == date
        )
        
        if status:
            query = query.filter_by(status=status)
        
        return query.order_by(
            Waitlist.priority.desc(),
            Waitlist.position
        ).all()
    
    async def process_expired_notifications(self):
        """Process waitlist notifications that have expired"""
        expired = self.db.query(Waitlist).filter(
            Waitlist.status == WaitlistStatus.NOTIFIED,
            Waitlist.notification_expires_at < datetime.utcnow()
        ).all()
        
        for entry in expired:
            entry.status = WaitlistStatus.EXPIRED
            logger.info(f"Waitlist entry {entry.id} notification expired")
        
        self.db.commit()
        
        # Check if there are more people to notify
        for entry in expired:
            await self.check_waitlist_for_availability(
                entry.requested_date,
                entry.requested_time_start,
                entry.party_size
            )
    
    async def process_expired_waitlist_entries(self):
        """Process waitlist entries that have expired"""
        expired = self.db.query(Waitlist).filter(
            Waitlist.status == WaitlistStatus.WAITING,
            Waitlist.expires_at < datetime.utcnow()
        ).all()
        
        for entry in expired:
            entry.status = WaitlistStatus.EXPIRED
            logger.info(f"Waitlist entry {entry.id} expired")
        
        self.db.commit()
    
    def estimate_wait_time(
        self,
        date: date,
        time: time,
        party_size: int
    ) -> Optional[int]:
        """Estimate wait time in minutes for a waitlist position"""
        # This is a simplified estimation
        # In reality, would use historical data and ML models
        
        active_ahead = self.db.query(Waitlist).filter(
            Waitlist.requested_date == date,
            Waitlist.status.in_([WaitlistStatus.WAITING, WaitlistStatus.NOTIFIED]),
            Waitlist.created_at < datetime.utcnow()
        ).count()
        
        # Assume 30 minutes per position as a rough estimate
        return active_ahead * 30 if active_ahead > 0 else None