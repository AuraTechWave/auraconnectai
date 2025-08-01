from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, Date, cast
from datetime import datetime, date, time, timedelta
from typing import List, Optional
import random
import string

from app.models.reservation import Reservation, ReservationStatus
from app.schemas.reservation import (
    ReservationCreate, ReservationUpdate, ReservationResponse,
    ReservationAvailability, ReservationCancellation
)
from backend.modules.customers.models.customer_models import Customer
from backend.modules.notifications.services.notification_service import NotificationService


class ReservationService:
    def __init__(self, db: Session):
        self.db = db
        self.notification_service = NotificationService(db)
    
    def generate_confirmation_code(self) -> str:
        """Generate a unique confirmation code"""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            # Check if code already exists
            if not self.db.query(Reservation).filter_by(confirmation_code=code).first():
                return code
    
    def create_reservation(self, customer_id: int, reservation_data: ReservationCreate) -> Reservation:
        """Create a new reservation"""
        # Check availability
        if not self.check_availability(
            reservation_data.reservation_date,
            reservation_data.reservation_time,
            reservation_data.party_size
        ):
            raise ValueError("No tables available for the requested time and party size")
        
        # Create reservation
        reservation = Reservation(
            customer_id=customer_id,
            reservation_date=reservation_data.reservation_date,
            reservation_time=reservation_data.reservation_time,
            party_size=reservation_data.party_size,
            special_requests=reservation_data.special_requests,
            status=ReservationStatus.PENDING,
            confirmation_code=self.generate_confirmation_code()
        )
        
        self.db.add(reservation)
        self.db.commit()
        self.db.refresh(reservation)
        
        # Send confirmation notification
        self._send_confirmation_notification(reservation)
        
        return reservation
    
    def get_reservation(self, reservation_id: int, customer_id: Optional[int] = None) -> Optional[Reservation]:
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
    ) -> List[Reservation]:
        """Get all reservations for a customer"""
        query = self.db.query(Reservation).filter_by(customer_id=customer_id)
        
        if status:
            query = query.filter_by(status=status)
        
        if upcoming_only:
            query = query.filter(
                or_(
                    Reservation.reservation_date > date.today(),
                    and_(
                        Reservation.reservation_date == date.today(),
                        Reservation.reservation_time > datetime.now().time()
                    )
                )
            )
        
        return query.order_by(
            Reservation.reservation_date.desc(),
            Reservation.reservation_time.desc()
        ).offset(skip).limit(limit).all()
    
    def update_reservation(
        self, 
        reservation_id: int, 
        customer_id: int,
        update_data: ReservationUpdate
    ) -> Optional[Reservation]:
        """Update a reservation"""
        reservation = self.get_reservation(reservation_id, customer_id)
        if not reservation:
            return None
        
        # Check if reservation can be modified
        if reservation.status in [ReservationStatus.COMPLETED, ReservationStatus.CANCELLED]:
            raise ValueError("Cannot modify completed or cancelled reservations")
        
        # If changing date/time/size, check availability
        if any([update_data.reservation_date, update_data.reservation_time, update_data.party_size]):
            new_date = update_data.reservation_date or reservation.reservation_date
            new_time = update_data.reservation_time or reservation.reservation_time
            new_size = update_data.party_size or reservation.party_size
            
            if not self.check_availability(new_date, new_time, new_size, exclude_id=reservation_id):
                raise ValueError("No tables available for the requested changes")
        
        # Update fields
        for field, value in update_data.dict(exclude_unset=True).items():
            setattr(reservation, field, value)
        
        reservation.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(reservation)
        
        # Send update notification
        self._send_update_notification(reservation)
        
        return reservation
    
    def cancel_reservation(
        self, 
        reservation_id: int, 
        customer_id: int,
        cancellation_data: ReservationCancellation
    ) -> Optional[Reservation]:
        """Cancel a reservation"""
        reservation = self.get_reservation(reservation_id, customer_id)
        if not reservation:
            return None
        
        if reservation.status in [ReservationStatus.COMPLETED, ReservationStatus.CANCELLED]:
            raise ValueError("Reservation is already completed or cancelled")
        
        reservation.status = ReservationStatus.CANCELLED
        reservation.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(reservation)
        
        # Send cancellation notification
        self._send_cancellation_notification(reservation, cancellation_data.reason)
        
        return reservation
    
    def check_availability(
        self,
        date: date,
        time: time,
        party_size: int,
        exclude_id: Optional[int] = None
    ) -> bool:
        """Check if a table is available for the given date, time, and party size"""
        # Simple availability check - in a real system, this would check against
        # actual table inventory and capacity
        
        # Get reservations for the same date within 2 hours
        start_time = (datetime.combine(date, time) - timedelta(hours=1)).time()
        end_time = (datetime.combine(date, time) + timedelta(hours=1)).time()
        
        query = self.db.query(Reservation).filter(
            Reservation.reservation_date == date,
            Reservation.reservation_time.between(start_time, end_time),
            Reservation.status.in_([ReservationStatus.PENDING, ReservationStatus.CONFIRMED])
        )
        
        if exclude_id:
            query = query.filter(Reservation.id != exclude_id)
        
        existing_reservations = query.all()
        
        # Simple capacity check - assume restaurant can handle 100 people at once
        total_party_size = sum(r.party_size for r in existing_reservations) + party_size
        
        return total_party_size <= 100
    
    def get_available_times(self, date: date, party_size: int) -> List[time]:
        """Get available reservation times for a given date and party size"""
        available_times = []
        
        # Restaurant hours: 11 AM to 9:30 PM, slots every 30 minutes
        current_time = time(11, 0)
        end_time = time(21, 30)
        
        while current_time <= end_time:
            if self.check_availability(date, current_time, party_size):
                available_times.append(current_time)
            
            # Add 30 minutes
            current_datetime = datetime.combine(date, current_time) + timedelta(minutes=30)
            current_time = current_datetime.time()
        
        return available_times
    
    def confirm_reservation(self, reservation_id: int) -> Optional[Reservation]:
        """Confirm a pending reservation (staff action)"""
        reservation = self.db.query(Reservation).filter_by(id=reservation_id).first()
        if not reservation:
            return None
        
        if reservation.status != ReservationStatus.PENDING:
            raise ValueError("Only pending reservations can be confirmed")
        
        reservation.status = ReservationStatus.CONFIRMED
        reservation.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(reservation)
        
        # Send confirmation notification
        self._send_confirmation_status_notification(reservation)
        
        return reservation
    
    def mark_as_seated(self, reservation_id: int, table_number: Optional[str] = None) -> Optional[Reservation]:
        """Mark a reservation as seated (staff action)"""
        reservation = self.db.query(Reservation).filter_by(id=reservation_id).first()
        if not reservation:
            return None
        
        if reservation.status != ReservationStatus.CONFIRMED:
            raise ValueError("Only confirmed reservations can be marked as seated")
        
        reservation.status = ReservationStatus.SEATED
        if table_number:
            reservation.table_number = table_number
        reservation.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(reservation)
        
        return reservation
    
    def mark_as_completed(self, reservation_id: int) -> Optional[Reservation]:
        """Mark a reservation as completed (staff action)"""
        reservation = self.db.query(Reservation).filter_by(id=reservation_id).first()
        if not reservation:
            return None
        
        if reservation.status != ReservationStatus.SEATED:
            raise ValueError("Only seated reservations can be marked as completed")
        
        reservation.status = ReservationStatus.COMPLETED
        reservation.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(reservation)
        
        return reservation
    
    def mark_as_no_show(self, reservation_id: int) -> Optional[Reservation]:
        """Mark a reservation as no-show (staff action)"""
        reservation = self.db.query(Reservation).filter_by(id=reservation_id).first()
        if not reservation:
            return None
        
        if reservation.status not in [ReservationStatus.PENDING, ReservationStatus.CONFIRMED]:
            raise ValueError("Only pending or confirmed reservations can be marked as no-show")
        
        reservation.status = ReservationStatus.NO_SHOW
        reservation.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(reservation)
        
        return reservation
    
    def get_daily_reservations(self, date: date) -> List[Reservation]:
        """Get all reservations for a specific date (staff view)"""
        return self.db.query(Reservation).filter(
            Reservation.reservation_date == date
        ).order_by(Reservation.reservation_time).all()
    
    def _send_confirmation_notification(self, reservation: Reservation):
        """Send reservation confirmation notification"""
        # This would integrate with the notification service
        # For now, it's a placeholder
        pass
    
    def _send_update_notification(self, reservation: Reservation):
        """Send reservation update notification"""
        # This would integrate with the notification service
        # For now, it's a placeholder
        pass
    
    def _send_cancellation_notification(self, reservation: Reservation, reason: Optional[str]):
        """Send reservation cancellation notification"""
        # This would integrate with the notification service
        # For now, it's a placeholder
        pass
    
    def _send_confirmation_status_notification(self, reservation: Reservation):
        """Send notification when reservation is confirmed by staff"""
        # This would integrate with the notification service
        # For now, it's a placeholder
        pass