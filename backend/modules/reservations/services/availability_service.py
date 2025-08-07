# backend/modules/reservations/services/availability_service.py

"""
Service for checking table availability and managing capacity.
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime, date, time, timedelta
from typing import List, Optional, Tuple, Dict
import logging

from ..models.reservation_models import (
    Reservation, ReservationStatus, TableConfiguration,
    ReservationSettings, SpecialDate
)

logger = logging.getLogger(__name__)


class AvailabilityService:
    """Service for managing table availability"""
    
    def __init__(self, db: Session):
        self.db = db
        self._table_cache = None
        self._table_cache_time = None
    
    def get_tables(self, force_refresh: bool = False) -> List[TableConfiguration]:
        """Get all active tables with caching"""
        # Cache for 10 minutes
        if (not force_refresh and self._table_cache and self._table_cache_time and
            datetime.utcnow() - self._table_cache_time < timedelta(minutes=10)):
            return self._table_cache
        
        tables = self.db.query(TableConfiguration).filter(
            TableConfiguration.is_active == True,
            TableConfiguration.available_for_reservation == True
        ).order_by(TableConfiguration.priority.desc()).all()
        
        self._table_cache = tables
        self._table_cache_time = datetime.utcnow()
        return tables
    
    async def check_availability(
        self,
        target_date: date,
        target_time: time,
        party_size: int,
        duration_minutes: int,
        exclude_reservation_id: Optional[int] = None
    ) -> Tuple[bool, Optional[str]]:
        """Check if a reservation can be accommodated"""
        settings = self.db.query(ReservationSettings).filter_by(restaurant_id=1).first()
        
        # Check special dates
        special_date = self.db.query(SpecialDate).filter_by(date=target_date).first()
        if special_date:
            if special_date.is_closed:
                return False, f"Restaurant is closed on {special_date.name or 'this date'}"
            
            if special_date.min_party_size and party_size < special_date.min_party_size:
                return False, f"Minimum party size on {special_date.name} is {special_date.min_party_size}"
            
            if special_date.max_party_size and party_size > special_date.max_party_size:
                return False, f"Maximum party size on {special_date.name} is {special_date.max_party_size}"
        
        # Get total capacity
        total_capacity = self._get_effective_capacity(target_date, settings)
        
        # Calculate time window for overlapping reservations
        start_datetime = datetime.combine(target_date, target_time)
        end_datetime = start_datetime + timedelta(minutes=duration_minutes)
        
        # Get overlapping reservations
        overlapping_capacity = self._get_overlapping_capacity(
            target_date,
            target_time,
            duration_minutes,
            exclude_reservation_id
        )
        
        # Apply buffer
        available_capacity = total_capacity * (1 - settings.buffer_percentage)
        
        if overlapping_capacity + party_size > available_capacity:
            return False, "No tables available for this time slot"
        
        # Check if specific tables are available
        available_tables = await self.get_available_tables(
            target_date,
            target_time,
            duration_minutes,
            party_size,
            exclude_reservation_id
        )
        
        if not available_tables:
            return False, "No suitable tables for your party size"
        
        return True, None
    
    def _get_effective_capacity(self, target_date: date, settings: ReservationSettings) -> int:
        """Get effective capacity considering special dates"""
        base_capacity = settings.total_capacity
        
        # Check for special date capacity modifiers
        special_date = self.db.query(SpecialDate).filter_by(date=target_date).first()
        if special_date and special_date.capacity_modifier:
            base_capacity = int(base_capacity * special_date.capacity_modifier)
        
        return base_capacity
    
    def _get_overlapping_capacity(
        self,
        target_date: date,
        target_time: time,
        duration_minutes: int,
        exclude_reservation_id: Optional[int] = None
    ) -> int:
        """Calculate total capacity used by overlapping reservations"""
        start_datetime = datetime.combine(target_date, target_time)
        end_datetime = start_datetime + timedelta(minutes=duration_minutes)
        
        query = self.db.query(
            func.sum(Reservation.party_size).label('total_capacity')
        ).filter(
            Reservation.reservation_date == target_date,
            Reservation.status.in_([
                ReservationStatus.PENDING,
                ReservationStatus.CONFIRMED,
                ReservationStatus.SEATED
            ])
        )
        
        if exclude_reservation_id:
            query = query.filter(Reservation.id != exclude_reservation_id)
        
        # Get reservations that overlap with the requested time
        overlapping = query.filter(
            or_(
                # Reservation starts during our window
                and_(
                    Reservation.reservation_time >= target_time,
                    Reservation.reservation_time < end_datetime.time()
                ),
                # Reservation ends during our window
                and_(
                    func.time(
                        func.datetime(
                            func.date(Reservation.reservation_date),
                            func.time(Reservation.reservation_time)
                        ) + func.cast(
                            func.concat(Reservation.duration_minutes, ' minutes'),
                            func.interval()
                        )
                    ) > target_time,
                    Reservation.reservation_time <= target_time
                )
            )
        ).scalar()
        
        return overlapping or 0
    
    async def get_available_tables(
        self,
        target_date: date,
        target_time: time,
        duration_minutes: int,
        party_size: int,
        exclude_reservation_id: Optional[int] = None
    ) -> List[TableConfiguration]:
        """Get available tables for a given time slot"""
        all_tables = self.get_tables()
        
        # Get reserved tables for the time slot
        reserved_table_ids = self._get_reserved_table_ids(
            target_date,
            target_time,
            duration_minutes,
            exclude_reservation_id
        )
        
        available_tables = []
        
        for table in all_tables:
            # Skip if table is reserved
            if table.id in reserved_table_ids:
                continue
            
            # Check if table can accommodate party size
            if table.min_capacity <= party_size <= table.max_capacity:
                available_tables.append(table)
            
            # Check combinable tables
            elif table.is_combinable and table.combine_with:
                # Check if combination can accommodate party
                combined_capacity = table.max_capacity
                combinable_available = True
                
                for other_table_num in table.combine_with:
                    other_table = next(
                        (t for t in all_tables if t.table_number == other_table_num),
                        None
                    )
                    if other_table:
                        if other_table.id in reserved_table_ids:
                            combinable_available = False
                            break
                        combined_capacity += other_table.max_capacity
                
                if combinable_available and combined_capacity >= party_size:
                    available_tables.append(table)
        
        return available_tables
    
    def _get_reserved_table_ids(
        self,
        target_date: date,
        target_time: time,
        duration_minutes: int,
        exclude_reservation_id: Optional[int] = None
    ) -> set:
        """Get IDs of tables that are reserved during the time slot"""
        start_datetime = datetime.combine(target_date, target_time)
        end_datetime = start_datetime + timedelta(minutes=duration_minutes)
        
        query = self.db.query(Reservation).filter(
            Reservation.reservation_date == target_date,
            Reservation.status.in_([
                ReservationStatus.PENDING,
                ReservationStatus.CONFIRMED,
                ReservationStatus.SEATED
            ])
        )
        
        if exclude_reservation_id:
            query = query.filter(Reservation.id != exclude_reservation_id)
        
        # Get overlapping reservations
        overlapping_reservations = query.all()
        
        reserved_table_ids = set()
        for reservation in overlapping_reservations:
            res_start = datetime.combine(reservation.reservation_date, reservation.reservation_time)
            res_end = res_start + timedelta(minutes=reservation.duration_minutes)
            
            # Check if times overlap
            if res_start < end_datetime and res_end > start_datetime:
                reserved_table_ids.update(reservation.table_ids or [])
        
        return reserved_table_ids
    
    async def assign_tables(
        self,
        target_date: date,
        target_time: time,
        party_size: int,
        duration_minutes: int,
        exclude_reservation_id: Optional[int] = None
    ) -> List[TableConfiguration]:
        """Assign optimal tables for a reservation"""
        available_tables = await self.get_available_tables(
            target_date,
            target_time,
            duration_minutes,
            party_size,
            exclude_reservation_id
        )
        
        if not available_tables:
            return []
        
        # Try to find single table that fits perfectly
        for table in available_tables:
            if (table.preferred_capacity and 
                table.preferred_capacity == party_size):
                return [table]
            elif (table.min_capacity <= party_size <= table.max_capacity):
                return [table]
        
        # If no single table, try combinations
        assigned_tables = self._find_table_combination(available_tables, party_size)
        
        return assigned_tables
    
    def _find_table_combination(
        self,
        available_tables: List[TableConfiguration],
        party_size: int
    ) -> List[TableConfiguration]:
        """Find optimal combination of tables for larger parties"""
        # Sort by priority and capacity
        sorted_tables = sorted(
            available_tables,
            key=lambda t: (t.priority, t.max_capacity),
            reverse=True
        )
        
        # Try to find minimal combination
        for i, table1 in enumerate(sorted_tables):
            if not table1.is_combinable:
                continue
            
            for j, table2 in enumerate(sorted_tables[i+1:], i+1):
                if (table2.table_number in table1.combine_with and
                    table1.max_capacity + table2.max_capacity >= party_size):
                    return [table1, table2]
        
        # If no good combination found, just return the largest available
        return [sorted_tables[0]] if sorted_tables else []
    
    def get_time_slots(
        self,
        target_date: date,
        party_size: int,
        duration_minutes: int = 90
    ) -> List[Dict]:
        """Get all available time slots for a date"""
        settings = self.db.query(ReservationSettings).filter_by(restaurant_id=1).first()
        
        # Get operating hours for the day
        day_name = target_date.strftime("%A").lower()
        day_hours = settings.operating_hours.get(day_name)
        
        if not day_hours:
            return []
        
        # Check for special date hours
        special_date = self.db.query(SpecialDate).filter_by(date=target_date).first()
        if special_date:
            if special_date.is_closed:
                return []
            if special_date.special_hours:
                day_hours = special_date.special_hours
        
        # Generate time slots
        slots = []
        current_time = datetime.strptime(day_hours["open"], "%H:%M").time()
        close_time = datetime.strptime(day_hours["close"], "%H:%M").time()
        
        # Subtract duration to ensure reservation fits before closing
        last_slot_time = (
            datetime.combine(target_date, close_time) - timedelta(minutes=duration_minutes)
        ).time()
        
        while current_time <= last_slot_time:
            # Check availability for this slot
            available, _ = asyncio.run(self.check_availability(
                target_date,
                current_time,
                party_size,
                duration_minutes
            ))
            
            # Get waitlist count
            waitlist_count = self._get_waitlist_count(target_date, current_time, party_size)
            
            # Get remaining capacity
            total_capacity = self._get_effective_capacity(target_date, settings)
            used_capacity = self._get_overlapping_capacity(
                target_date,
                current_time,
                duration_minutes
            )
            remaining_capacity = max(0, total_capacity - used_capacity)
            
            slots.append({
                "time": current_time,
                "available": available,
                "capacity_remaining": remaining_capacity,
                "waitlist_count": waitlist_count
            })
            
            # Move to next slot
            current_datetime = datetime.combine(target_date, current_time)
            current_datetime += timedelta(minutes=settings.slot_duration_minutes)
            current_time = current_datetime.time()
        
        return slots
    
    def _get_waitlist_count(self, date: date, time: time, party_size: int) -> int:
        """Get number of waitlist entries for a time slot"""
        from ..models.reservation_models import Waitlist, WaitlistStatus
        
        return self.db.query(Waitlist).filter(
            Waitlist.requested_date == date,
            Waitlist.requested_time_start <= time,
            Waitlist.requested_time_end >= time,
            Waitlist.party_size <= party_size,
            Waitlist.status == WaitlistStatus.WAITING
        ).count()
    
    def get_peak_times(self, date: date) -> List[Dict]:
        """Get peak reservation times for capacity planning"""
        reservations = self.db.query(
            Reservation.reservation_time,
            func.sum(Reservation.party_size).label('total_guests')
        ).filter(
            Reservation.reservation_date == date,
            Reservation.status.in_([
                ReservationStatus.PENDING,
                ReservationStatus.CONFIRMED,
                ReservationStatus.SEATED
            ])
        ).group_by(Reservation.reservation_time).all()
        
        return [
            {
                "time": r.reservation_time,
                "total_guests": r.total_guests
            }
            for r in reservations
        ]


# Import asyncio for async operations
import asyncio