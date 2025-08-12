from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime, date, timedelta, time
from typing import List, Dict, Optional, Tuple, Any
import logging

from ..models.scheduling_models import (
    EnhancedShift, ShiftTemplate, StaffAvailability, 
    ShiftSwap, ShiftBreak, SchedulePublication
)
from ..models.staff_models import StaffMember
from ..enums.scheduling_enums import (
    ShiftStatus, AvailabilityStatus, SwapStatus, 
    RecurrenceType, DayOfWeek
)
from ..schemas.scheduling_schemas import (
    ScheduleConflict, StaffingAnalytics
)
from modules.orders.models.order_models import Order


logger = logging.getLogger(__name__)


class SchedulingService:
    def __init__(self, db: Session):
        self.db = db
        self._cache = {}  # Simple in-memory cache for analytics
    
    def check_availability(
        self, 
        staff_id: int, 
        start_time: datetime, 
        end_time: datetime
    ) -> Tuple[bool, Optional[str]]:
        """Check if staff member is available for a given time slot"""
        
        # Get the day of week
        day_of_week = DayOfWeek(start_time.weekday())
        
        # Check recurring availability
        recurring_availability = self.db.query(StaffAvailability).filter(
            and_(
                StaffAvailability.staff_id == staff_id,
                StaffAvailability.day_of_week == day_of_week,
                StaffAvailability.status.in_([
                    AvailabilityStatus.AVAILABLE, 
                    AvailabilityStatus.PREFERRED
                ]),
                or_(
                    StaffAvailability.effective_until.is_(None),
                    StaffAvailability.effective_until >= start_time
                ),
                StaffAvailability.effective_from <= start_time
            )
        ).first()
        
        if recurring_availability:
            # Check if the shift time fits within available hours
            shift_start_time = start_time.time()
            shift_end_time = end_time.time()
            
            if (shift_start_time < recurring_availability.start_time or 
                shift_end_time > recurring_availability.end_time):
                return False, "Shift times outside of available hours"
        
        # Check specific date availability
        specific_availability = self.db.query(StaffAvailability).filter(
            and_(
                StaffAvailability.staff_id == staff_id,
                StaffAvailability.specific_date == start_time.date(),
                StaffAvailability.status == AvailabilityStatus.UNAVAILABLE
            )
        ).first()
        
        if specific_availability:
            return False, "Staff marked as unavailable on this date"
        
        return True, None
    
    def detect_conflicts(
        self, 
        staff_id: int, 
        start_time: datetime, 
        end_time: datetime,
        exclude_shift_id: Optional[int] = None
    ) -> List[ScheduleConflict]:
        """Detect scheduling conflicts for a staff member"""
        conflicts = []
        
        # Check for overlapping shifts
        overlap_query = self.db.query(EnhancedShift).filter(
            and_(
                EnhancedShift.staff_id == staff_id,
                EnhancedShift.status != ShiftStatus.CANCELLED,
                or_(
                    and_(
                        EnhancedShift.start_time <= start_time,
                        EnhancedShift.end_time > start_time
                    ),
                    and_(
                        EnhancedShift.start_time < end_time,
                        EnhancedShift.end_time >= end_time
                    ),
                    and_(
                        EnhancedShift.start_time >= start_time,
                        EnhancedShift.end_time <= end_time
                    )
                )
            )
        )
        
        if exclude_shift_id:
            overlap_query = overlap_query.filter(EnhancedShift.id != exclude_shift_id)
        
        overlapping_shifts = overlap_query.all()
        
        if overlapping_shifts:
            conflicts.append(ScheduleConflict(
                conflict_type="overlap",
                severity="error",
                shift_ids=[shift.id for shift in overlapping_shifts],
                description="Shift overlaps with existing shifts",
                resolution_suggestions=[
                    "Adjust shift times to avoid overlap",
                    "Cancel or reschedule one of the conflicting shifts"
                ]
            ))
        
        # Check minimum rest period between shifts
        min_rest_hours = 8  # Configurable
        rest_check_start = start_time - timedelta(hours=min_rest_hours)
        rest_check_end = end_time + timedelta(hours=min_rest_hours)
        
        nearby_shifts = self.db.query(EnhancedShift).filter(
            and_(
                EnhancedShift.staff_id == staff_id,
                EnhancedShift.status != ShiftStatus.CANCELLED,
                or_(
                    and_(
                        EnhancedShift.end_time > rest_check_start,
                        EnhancedShift.end_time <= start_time
                    ),
                    and_(
                        EnhancedShift.start_time >= end_time,
                        EnhancedShift.start_time < rest_check_end
                    )
                )
            )
        ).all()
        
        for shift in nearby_shifts:
            if shift.end_time <= start_time:
                rest_period = (start_time - shift.end_time).total_seconds() / 3600
            else:
                rest_period = (shift.start_time - end_time).total_seconds() / 3600
            
            if rest_period < min_rest_hours:
                conflicts.append(ScheduleConflict(
                    conflict_type="insufficient_rest",
                    severity="warning",
                    shift_ids=[shift.id],
                    description=f"Less than {min_rest_hours} hours rest between shifts",
                    resolution_suggestions=[
                        f"Ensure at least {min_rest_hours} hours between shifts",
                        "Consider assigning shift to another staff member"
                    ]
                ))
        
        # Check weekly hour limits
        week_start = start_time.date() - timedelta(days=start_time.weekday())
        week_end = week_start + timedelta(days=6)
        
        weekly_hours = self.db.query(
            func.sum(
                func.extract('epoch', EnhancedShift.end_time - EnhancedShift.start_time) / 3600
            )
        ).filter(
            and_(
                EnhancedShift.staff_id == staff_id,
                EnhancedShift.status != ShiftStatus.CANCELLED,
                EnhancedShift.date >= week_start,
                EnhancedShift.date <= week_end
            )
        ).scalar() or 0
        
        shift_hours = (end_time - start_time).total_seconds() / 3600
        total_hours = weekly_hours + shift_hours
        
        if total_hours > 40:  # Configurable max hours
            conflicts.append(ScheduleConflict(
                conflict_type="max_hours",
                severity="warning" if total_hours <= 60 else "error",
                shift_ids=[],
                description=f"Weekly hours would exceed limit ({total_hours:.1f} hours)",
                resolution_suggestions=[
                    "Reduce shift hours",
                    "Assign overtime shifts to other staff",
                    "Review weekly schedule distribution"
                ]
            ))
        
        # Check availability
        available, reason = self.check_availability(staff_id, start_time, end_time)
        if not available:
            conflicts.append(ScheduleConflict(
                conflict_type="availability",
                severity="error",
                shift_ids=[],
                description=reason or "Staff not available during this time",
                resolution_suggestions=[
                    "Check staff availability calendar",
                    "Request availability change from staff member",
                    "Assign shift to available staff"
                ]
            ))
        
        return conflicts
    
    def calculate_labor_cost(
        self, 
        staff_id: int, 
        start_time: datetime, 
        end_time: datetime,
        hourly_rate: Optional[float] = None
    ) -> float:
        """Calculate estimated labor cost for a shift"""
        
        if not hourly_rate:
            # Get staff's default hourly rate from pay policies
            # This would need to be implemented based on your pay policy structure
            hourly_rate = 15.0  # Default fallback
        
        # Calculate base hours
        hours = (end_time - start_time).total_seconds() / 3600
        
        # Check for overtime (over 8 hours in a day or over 40 in a week)
        overtime_multiplier = 1.5
        regular_hours = min(hours, 8)
        overtime_hours = max(0, hours - 8)
        
        # Calculate cost
        cost = (regular_hours * hourly_rate) + (overtime_hours * hourly_rate * overtime_multiplier)
        
        return round(cost, 2)
    
    def generate_schedule_from_templates(
        self,
        start_date: date,
        end_date: date,
        location_id: int,
        auto_assign: bool = False
    ) -> List[EnhancedShift]:
        """Generate schedule based on shift templates"""
        
        generated_shifts = []
        current_date = start_date
        
        while current_date <= end_date:
            day_of_week = DayOfWeek(current_date.weekday())
            
            # Get active templates for this day
            templates = self.db.query(ShiftTemplate).filter(
                and_(
                    ShiftTemplate.location_id == location_id,
                    ShiftTemplate.is_active == True,
                    or_(
                        ShiftTemplate.recurrence_type == RecurrenceType.DAILY,
                        and_(
                            ShiftTemplate.recurrence_type == RecurrenceType.WEEKLY,
                            ShiftTemplate.recurrence_days.contains([day_of_week.value])
                        )
                    )
                )
            ).all()
            
            for template in templates:
                # Create shifts based on template requirements
                shifts_to_create = template.preferred_staff or template.min_staff
                
                for i in range(shifts_to_create):
                    shift_start = datetime.combine(current_date, template.start_time)
                    shift_end = datetime.combine(
                        current_date if template.end_time > template.start_time else current_date + timedelta(days=1),
                        template.end_time
                    )
                    
                    shift = EnhancedShift(
                        location_id=location_id,
                        role_id=template.role_id,
                        template_id=template.id,
                        date=current_date,
                        start_time=shift_start,
                        end_time=shift_end,
                        status=ShiftStatus.DRAFT,
                        hourly_rate=template.estimated_hourly_rate
                    )
                    
                    if auto_assign:
                        # Find available staff for this shift
                        available_staff = self._find_available_staff(
                            shift_start, 
                            shift_end, 
                            template.role_id,
                            location_id
                        )
                        if available_staff:
                            shift.staff_id = available_staff[0].id
                            shift.estimated_cost = self.calculate_labor_cost(
                                available_staff[0].id,
                                shift_start,
                                shift_end,
                                template.estimated_hourly_rate
                            )
                    
                    generated_shifts.append(shift)
            
            current_date += timedelta(days=1)
        
        return generated_shifts
    
    def _find_available_staff(
        self,
        start_time: datetime,
        end_time: datetime,
        role_id: Optional[int],
        location_id: int
    ) -> List[StaffMember]:
        """Find staff members available for a shift"""
        
        # Base query for active staff
        query = self.db.query(StaffMember).filter(
            StaffMember.status == "active"
        )
        
        if role_id:
            query = query.filter(StaffMember.role_id == role_id)
        
        potential_staff = query.all()
        available_staff = []
        
        for staff in potential_staff:
            # Check availability and conflicts
            available, _ = self.check_availability(staff.id, start_time, end_time)
            conflicts = self.detect_conflicts(staff.id, start_time, end_time)
            
            if available and not any(c.severity == "error" for c in conflicts):
                available_staff.append(staff)
        
        # Sort by preference (could be based on various factors)
        # For now, random order
        return available_staff
    
    def validate_swap_request(
        self,
        from_shift_id: int,
        to_shift_id: Optional[int] = None,
        to_staff_id: Optional[int] = None
    ) -> Tuple[bool, Optional[str]]:
        """Validate a shift swap request"""
        # Get from shift
        from_shift = self.db.query(EnhancedShift).filter(
            EnhancedShift.id == from_shift_id
        ).first()
        
        if not from_shift:
            return False, "Source shift not found"
        
        if from_shift.status == ShiftStatus.COMPLETED:
            return False, "Cannot swap completed shifts"
        
        if from_shift.status == ShiftStatus.CANCELLED:
            return False, "Cannot swap cancelled shifts"
        
        # If swapping with another shift
        if to_shift_id:
            to_shift = self.db.query(EnhancedShift).filter(
                EnhancedShift.id == to_shift_id
            ).first()
            
            if not to_shift:
                return False, "Target shift not found"
            
            # Verify shifts are from same location and role
            if from_shift.location_id != to_shift.location_id:
                return False, "Shifts must be at the same location"
            
            if from_shift.role_id != to_shift.role_id:
                return False, "Shifts must be for the same role"
            
            if to_shift.status == ShiftStatus.COMPLETED:
                return False, "Cannot swap with completed shifts"
        
        # If assigning to specific staff
        if to_staff_id:
            to_staff = self.db.query(StaffMember).filter(
                StaffMember.id == to_staff_id
            ).first()
            
            if not to_staff:
                return False, "Target staff member not found"
            
            # Check if target staff has required role
            if from_shift.role_id and to_staff.role_id != from_shift.role_id:
                return False, "Target staff member doesn't have required role"
            
            # Check availability
            available, reason = self.check_availability(
                to_staff_id,
                from_shift.start_time,
                from_shift.end_time
            )
            
            if not available:
                return False, f"Target staff not available: {reason}"
            
            # Check for conflicts
            conflicts = self.detect_conflicts(
                to_staff_id,
                from_shift.start_time,
                from_shift.end_time
            )
            
            if conflicts:
                return False, "Target staff has scheduling conflicts"
        
        return True, None
    
    def approve_shift_swap(
        self,
        swap_id: int,
        approved_by_id: int,
        notes: Optional[str] = None
    ) -> ShiftSwap:
        """Approve a shift swap request"""
        
        swap = self.db.query(ShiftSwap).filter(ShiftSwap.id == swap_id).first()
        if not swap:
            raise ValueError("Shift swap not found")
        
        if swap.status != SwapStatus.PENDING:
            raise ValueError("Can only approve pending swap requests")
        
        # Validate the swap
        valid, reason = self.validate_swap_request(
            swap.from_shift_id,
            swap.to_shift_id,
            swap.to_staff_id
        )
        
        if not valid:
            raise ValueError(f"Invalid swap request: {reason}")
        
        # Update the shifts
        from_shift = swap.from_shift
        
        if swap.to_shift_id:
            # Swapping with another shift
            to_shift = swap.to_shift
            
            # Swap staff IDs
            from_shift.staff_id, to_shift.staff_id = to_shift.staff_id, from_shift.staff_id
        else:
            # Assigning to a specific staff member
            from_shift.staff_id = swap.to_staff_id
        
        # Update swap status
        swap.status = SwapStatus.APPROVED
        swap.approved_by_id = approved_by_id
        swap.approved_at = datetime.utcnow()
        
        if notes:
            swap.manager_notes = notes
        
        self.db.commit()
        return swap
    
    def get_staffing_analytics(
        self,
        start_date: date,
        end_date: date,
        location_id: int
    ) -> List[StaffingAnalytics]:
        """Get staffing analytics for a date range with caching"""
        
        # Check cache first
        cached = self.get_cached_analytics(location_id, start_date, end_date)
        if cached:
            return cached
        
        analytics = []
        current_date = start_date
        
        while current_date <= end_date:
            # Get all shifts for this date
            shifts = self.db.query(EnhancedShift).filter(
                and_(
                    EnhancedShift.location_id == location_id,
                    EnhancedShift.date == current_date,
                    EnhancedShift.status != ShiftStatus.CANCELLED
                )
            ).all()
            
            # Calculate metrics
            scheduled_staff = len(set(shift.staff_id for shift in shifts if shift.staff_id))
            total_cost = sum(shift.estimated_cost or 0 for shift in shifts)
            
            # Group by role
            shifts_by_role = {}
            for shift in shifts:
                if shift.role and shift.role.name:
                    role_name = shift.role.name
                    shifts_by_role[role_name] = shifts_by_role.get(role_name, 0) + 1
            
            # Get required staff from templates
            templates = self.db.query(ShiftTemplate).filter(
                and_(
                    ShiftTemplate.location_id == location_id,
                    ShiftTemplate.is_active == True
                )
            ).all()
            
            required_staff = sum(t.min_staff for t in templates)
            
            analytics.append(StaffingAnalytics(
                date=current_date,
                location_id=location_id,
                scheduled_staff=scheduled_staff,
                required_staff=required_staff,
                coverage_percentage=(scheduled_staff / required_staff * 100) if required_staff > 0 else 100,
                estimated_labor_cost=total_cost,
                shifts_by_role=shifts_by_role
            ))
            
            current_date += timedelta(days=1)
        
        # Cache the results
        self.cache_analytics(location_id, start_date, end_date, analytics)
        
        return analytics
    
    def generate_demand_aware_schedule(
        self,
        start_date: date,
        end_date: date,
        location_id: int,
        demand_lookback_days: int = 90,
        buffer_percentage: float = 10.0,
        respect_availability: bool = True,
        max_hours_per_week: float = 40,
        min_hours_between_shifts: int = 8,
    ) -> List[EnhancedShift]:
        """Generate schedule using historical demand to determine staffing levels per role.

        Simple heuristic:
        - Use historical orders per hour for the same DOW over a lookback window to estimate peak load
        - Map predicted peak orders to minimum staff per role via productivity ratios
        - Create non-overlapping shifts per day and assign available qualified staff
        """
        generated: List[EnhancedShift] = []
        # Track assigned shifts during generation to properly calculate weekly hours
        assigned_shifts_by_staff: Dict[int, List[Tuple[datetime, datetime]]] = {}
        
        current_date = start_date
        while current_date <= end_date:
            # Estimate hourly demand using recent history
            hourly_demand = self._estimate_peak_orders(current_date, location_id, demand_lookback_days)
            hourly_role_requirements = self._map_orders_to_role_requirements(hourly_demand, location_id)
            
            # Create non-overlapping shift blocks to avoid conflicts
            shift_blocks = [
                (time(6, 0), time(14, 0)),   # Morning shift
                (time(14, 0), time(22, 0)),  # Afternoon/Evening shift
                (time(22, 0), time(6, 0)),   # Night shift (overnight)
            ]
            
            for start_t, end_t in shift_blocks:
                # Calculate the peak requirement for this shift block
                shift_start_hour = start_t.hour
                shift_end_hour = end_t.hour
                
                # Handle overnight shift
                if shift_end_hour <= shift_start_hour:
                    shift_end_hour += 24
                
                # Find peak demand within this shift block
                peak_requirements = {}
                for hour in range(shift_start_hour, shift_end_hour):
                    actual_hour = hour % 24
                    if actual_hour in hourly_role_requirements:
                        for role_id, required in hourly_role_requirements[actual_hour].items():
                            if role_id not in peak_requirements:
                                peak_requirements[role_id] = 0
                            peak_requirements[role_id] = max(peak_requirements[role_id], required)
                
                # Create shifts based on peak requirements
                for role_id, required in peak_requirements.items():
                    required_with_buffer = max(0, int(round(required * (1 + buffer_percentage / 100.0))))
                    for _ in range(required_with_buffer):
                        shift_start = datetime.combine(current_date, start_t)
                        shift_end = datetime.combine(current_date, end_t)
                        
                        # Handle overnight shift
                        if end_t <= start_t:
                            shift_end = shift_end + timedelta(days=1)
                        
                        staff_member = self._pick_best_staff_for_shift_with_tracking(
                            shift_start, shift_end, role_id, location_id,
                            respect_availability, max_hours_per_week, min_hours_between_shifts,
                            assigned_shifts_by_staff
                        )
                        if not staff_member:
                            continue
                        
                        shift = EnhancedShift(
                            location_id=location_id,
                            role_id=role_id,
                            date=current_date,
                            start_time=shift_start,
                            end_time=shift_end,
                            status=ShiftStatus.DRAFT,
                        )
                        shift.staff_id = staff_member.id
                        shift.estimated_cost = self.calculate_labor_cost(
                            staff_member.id, shift_start, shift_end
                        )
                        generated.append(shift)
                        
                        # Track this assignment for future calculations
                        if staff_member.id not in assigned_shifts_by_staff:
                            assigned_shifts_by_staff[staff_member.id] = []
                        assigned_shifts_by_staff[staff_member.id].append((shift_start, shift_end))
            
            current_date += timedelta(days=1)
        return generated
    
    def generate_flexible_demand_schedule(
        self,
        start_date: date,
        end_date: date,
        location_id: int,
        demand_lookback_days: int = 90,
        buffer_percentage: float = 10.0,
        respect_availability: bool = True,
        max_hours_per_week: float = 40,
        min_hours_between_shifts: int = 8,
        min_shift_hours: int = 4,
        max_shift_hours: int = 8,
    ) -> List[EnhancedShift]:
        """Generate schedule with flexible shifts that better match actual demand patterns.
        
        This method creates shifts that start and end based on actual demand peaks,
        rather than using fixed shift blocks.
        """
        generated: List[EnhancedShift] = []
        assigned_shifts_by_staff: Dict[int, List[Tuple[datetime, datetime]]] = {}
        
        current_date = start_date
        while current_date <= end_date:
            # Get hourly demand for this day
            hourly_demand = self._estimate_peak_orders(current_date, location_id, demand_lookback_days)
            hourly_role_requirements = self._map_orders_to_role_requirements(hourly_demand, location_id)
            
            # Find demand peaks and create shifts around them
            for role_id in self._get_all_role_ids(location_id):
                shifts_created = self._create_shifts_for_role_on_date(
                    current_date, role_id, location_id, hourly_role_requirements,
                    assigned_shifts_by_staff, respect_availability, max_hours_per_week,
                    min_hours_between_shifts, buffer_percentage, min_shift_hours, max_shift_hours
                )
                generated.extend(shifts_created)
            
            current_date += timedelta(days=1)
        
        return generated
    
    def _get_all_role_ids(self, location_id: int) -> List[int]:
        """Get all role IDs for a location"""
        from ..models.staff_models import Role
        roles = self.db.query(Role).filter(Role.restaurant_id == location_id).all()
        return [role.id for role in roles]
    
    def _create_shifts_for_role_on_date(
        self,
        target_date: date,
        role_id: int,
        location_id: int,
        hourly_role_requirements: Dict[int, Dict[int, int]],
        assigned_shifts_by_staff: Dict[int, List[Tuple[datetime, datetime]]],
        respect_availability: bool,
        max_hours_per_week: float,
        min_hours_between_shifts: int,
        buffer_percentage: float,
        min_shift_hours: int,
        max_shift_hours: int,
    ) -> List[EnhancedShift]:
        """Create shifts for a specific role on a specific date based on demand patterns"""
        shifts = []
        
        # Get requirements for this role across all hours
        role_requirements = {}
        for hour, requirements in hourly_role_requirements.items():
            if role_id in requirements:
                role_requirements[hour] = requirements[role_id]
        
        if not role_requirements:
            return shifts
        
        # Find continuous periods where staff is needed
        active_hours = []
        for hour in range(24):
            required = role_requirements.get(hour, 0)
            if required > 0:
                active_hours.append(hour)
        
        if not active_hours:
            return shifts
        
        # Group consecutive hours into shift periods
        shift_periods = self._group_hours_into_shifts(active_hours, min_shift_hours, max_shift_hours)
        
        # Create shifts for each period
        for start_hour, end_hour in shift_periods:
            # Find peak requirement in this period
            peak_required = 0
            for hour in range(start_hour, end_hour + 1):
                required = role_requirements.get(hour, 0)
                peak_required = max(peak_required, required)
            
            if peak_required <= 0:
                continue
            
            # Apply buffer
            required_with_buffer = max(0, int(round(peak_required * (1 + buffer_percentage / 100.0))))
            
            # Create shifts
            for _ in range(required_with_buffer):
                shift_start = datetime.combine(target_date, time(start_hour, 0))
                shift_end = datetime.combine(target_date, time(end_hour, 0))
                
                # Handle overnight shift
                if end_hour <= start_hour:
                    shift_end = shift_end + timedelta(days=1)
                
                staff_member = self._pick_best_staff_for_shift_with_tracking(
                    shift_start, shift_end, role_id, location_id,
                    respect_availability, max_hours_per_week, min_hours_between_shifts,
                    assigned_shifts_by_staff
                )
                if not staff_member:
                    continue
                
                shift = EnhancedShift(
                    location_id=location_id,
                    role_id=role_id,
                    date=target_date,
                    start_time=shift_start,
                    end_time=shift_end,
                    status=ShiftStatus.DRAFT,
                )
                shift.staff_id = staff_member.id
                shift.estimated_cost = self.calculate_labor_cost(
                    staff_member.id, shift_start, shift_end
                )
                shifts.append(shift)
                
                # Track this assignment
                if staff_member.id not in assigned_shifts_by_staff:
                    assigned_shifts_by_staff[staff_member.id] = []
                assigned_shifts_by_staff[staff_member.id].append((shift_start, shift_end))
        
        return shifts
    
    def _group_hours_into_shifts(
        self,
        active_hours: List[int],
        min_shift_hours: int,
        max_shift_hours: int
    ) -> List[Tuple[int, int]]:
        """Group consecutive active hours into shift periods"""
        if not active_hours:
            return []
        
        shifts = []
        current_start = active_hours[0]
        current_end = active_hours[0]
        
        for i in range(1, len(active_hours)):
            hour = active_hours[i]
            
            # Check if this hour is consecutive
            if hour == current_end + 1:
                current_end = hour
            else:
                # End current shift if it meets minimum requirements
                if current_end - current_start + 1 >= min_shift_hours:
                    shifts.append((current_start, current_end))
                
                # Start new shift
                current_start = hour
                current_end = hour
        
        # Add final shift
        if current_end - current_start + 1 >= min_shift_hours:
            shifts.append((current_start, current_end))
        
        # Split long shifts if they exceed max_shift_hours
        final_shifts = []
        for start, end in shifts:
            duration = end - start + 1
            if duration <= max_shift_hours:
                final_shifts.append((start, end))
            else:
                # Split into multiple shifts
                num_shifts = (duration + max_shift_hours - 1) // max_shift_hours
                shift_duration = duration // num_shifts
                
                for i in range(num_shifts):
                    shift_start = start + (i * shift_duration)
                    shift_end = min(end, shift_start + shift_duration - 1)
                    final_shifts.append((shift_start, shift_end))
        
        return final_shifts

    def _estimate_peak_orders(self, target_date: date, location_id: int, demand_lookback_days: int) -> Dict[int, int]:
        """Estimate orders per hour using historical data for the same day-of-week over a configurable lookback window, filtered by location.
        
        Returns a dict mapping hour -> order_count for the entire day.
        """
        lookback_start = target_date - timedelta(days=demand_lookback_days)
        dow_iso = target_date.isoweekday()  # 1=Mon .. 7=Sun
        
        # Count orders per hour for matching DOW and location
        rows = self.db.query(
            func.extract('hour', Order.created_at).label('hour'),
            func.count(Order.id).label('cnt')
        ).filter(
            func.date(Order.created_at) >= lookback_start,
            func.date(Order.created_at) < target_date,
            func.extract('isodow', Order.created_at) == dow_iso,
            Order.staff_id == StaffMember.id,
            StaffMember.restaurant_id == location_id,
            Order.status.in_(['completed', 'paid'])
        ).group_by(func.extract('hour', Order.created_at)).all()
        
        # Initialize hourly demand dict
        hourly_demand = {hour: 0 for hour in range(24)}
        
        # Populate with actual data
        for row in rows:
            hourly_demand[int(row.hour)] = int(row.cnt)
        
        return hourly_demand

    def _map_orders_to_role_requirements(self, hourly_demand: Dict[int, int], location_id: int) -> Dict[int, Dict[int, int]]:
        """Translate hourly orders to per-role required counts using simple productivity ratios.
        Returns a dict of role_id -> {hour -> required_count}.
        """
        if not hourly_demand or max(hourly_demand.values()) <= 0:
            return {}
        
        # Load configurable productivity and minimums
        from .scheduling_config import load_scheduling_config
        cfg = load_scheduling_config()
        productivity = cfg.productivity
        minimums = cfg.minimums
        
        # Map role names to ids for the location
        role_name_to_id = {}
        from ..models.staff_models import Role
        # Get all roles for the restaurant (not filtered by location_id since roles are restaurant-scoped)
        roles = self.db.query(Role).filter(Role.restaurant_id == location_id).all()
        for r in roles:
            role_name_to_id[r.name] = r.id
        
        # Calculate requirements for each hour
        hourly_requirements: Dict[int, Dict[int, int]] = {}
        
        for hour, orders in hourly_demand.items():
            if orders <= 0:
                continue
                
            hour_requirements: Dict[int, int] = {}
            for role_name, prod in productivity.items():
                # Fix: Handle zero productivity to prevent ZeroDivisionError
                if prod <= 0:
                    logger.warning(f"Invalid productivity value {prod} for role {role_name}, skipping")
                    continue
                
                base = int((orders + prod - 1) // prod)  # ceiling division
                base = max(base, minimums.get(role_name, 0))
                role_id = role_name_to_id.get(role_name)
                if role_id:
                    hour_requirements[role_id] = base
            
            if hour_requirements:
                hourly_requirements[hour] = hour_requirements
        
        return hourly_requirements

    def _pick_best_staff_for_shift(
        self,
        start_time: datetime,
        end_time: datetime,
        role_id: Optional[int],
        location_id: int,
        respect_availability: bool,
        max_hours_per_week: float,
        min_hours_between_shifts: int,
    ) -> Optional[StaffMember]:
        """Choose staff who matches role, passes availability/conflicts, and has lowest weekly hours so far."""
        query = self.db.query(StaffMember).filter(
            StaffMember.status == "active",
            StaffMember.role_id == role_id,
            StaffMember.restaurant_id == location_id,
        )
        candidates = query.all()
        viable: List[Tuple[StaffMember, float]] = []
        for staff in candidates:
            if respect_availability:
                ok, _ = self.check_availability(staff.id, start_time, end_time)
                if not ok:
                    continue
            conflicts = self.detect_conflicts(staff.id, start_time, end_time)
            if any(c.severity == "error" for c in conflicts):
                continue
            # weekly hours so far
            week_hours = self._calculate_weekly_hours(staff.id, start_time.date())
            if week_hours >= max_hours_per_week:
                continue
            viable.append((staff, week_hours))
        if not viable:
            return None
        viable.sort(key=lambda x: x[1])
        return viable[0][0]
    
    def _pick_best_staff_for_shift_with_tracking(
        self,
        start_time: datetime,
        end_time: datetime,
        role_id: Optional[int],
        location_id: int,
        respect_availability: bool,
        max_hours_per_week: float,
        min_hours_between_shifts: int,
        assigned_shifts_by_staff: Dict[int, List[Tuple[datetime, datetime]]]
    ) -> Optional[StaffMember]:
        """Choose staff who matches role, passes availability/conflicts, and has lowest weekly hours so far.
        
        This version properly handles min_hours_between_shifts and tracks assigned shifts during generation.
        """
        query = self.db.query(StaffMember).filter(
            StaffMember.status == "active",
            StaffMember.role_id == role_id,
            StaffMember.restaurant_id == location_id,
        )
        candidates = query.all()
        viable: List[Tuple[StaffMember, float]] = []
        
        for staff in candidates:
            if respect_availability:
                ok, _ = self.check_availability(staff.id, start_time, end_time)
                if not ok:
                    continue
            
            # Check conflicts with existing shifts using custom rest period
            conflicts = self._detect_conflicts_with_custom_rest(
                staff.id, start_time, end_time, min_hours_between_shifts
            )
            if any(c.severity == "error" for c in conflicts):
                continue
            
            # Check conflicts with shifts assigned during this generation
            if staff.id in assigned_shifts_by_staff:
                generation_conflicts = self._check_generation_conflicts(
                    start_time, end_time, assigned_shifts_by_staff[staff.id], min_hours_between_shifts
                )
                if generation_conflicts:
                    continue
            
            # Calculate total weekly hours including existing shifts and newly assigned shifts
            existing_hours = self._calculate_weekly_hours(staff.id, start_time.date())
            generation_hours = self._calculate_generation_hours(
                staff.id, start_time.date(), assigned_shifts_by_staff.get(staff.id, [])
            )
            shift_hours = (end_time - start_time).total_seconds() / 3600
            total_weekly_hours = existing_hours + generation_hours + shift_hours
            
            if total_weekly_hours > max_hours_per_week:
                continue
                
            viable.append((staff, total_weekly_hours))
        
        if not viable:
            return None
        viable.sort(key=lambda x: x[1])
        return viable[0][0]
    
    def _detect_conflicts_with_custom_rest(
        self, 
        staff_id: int, 
        start_time: datetime, 
        end_time: datetime,
        min_rest_hours: int,
        exclude_shift_id: Optional[int] = None
    ) -> List[ScheduleConflict]:
        """Detect scheduling conflicts for a staff member with custom rest period"""
        conflicts = []
        
        # Check for overlapping shifts
        overlap_query = self.db.query(EnhancedShift).filter(
            and_(
                EnhancedShift.staff_id == staff_id,
                EnhancedShift.status != ShiftStatus.CANCELLED,
                or_(
                    and_(
                        EnhancedShift.start_time <= start_time,
                        EnhancedShift.end_time > start_time
                    ),
                    and_(
                        EnhancedShift.start_time < end_time,
                        EnhancedShift.end_time >= end_time
                    ),
                    and_(
                        EnhancedShift.start_time >= start_time,
                        EnhancedShift.end_time <= end_time
                    )
                )
            )
        )
        
        if exclude_shift_id:
            overlap_query = overlap_query.filter(EnhancedShift.id != exclude_shift_id)
        
        overlapping_shifts = overlap_query.all()
        
        if overlapping_shifts:
            conflicts.append(ScheduleConflict(
                conflict_type="overlap",
                severity="error",
                shift_ids=[shift.id for shift in overlapping_shifts],
                description="Shift overlaps with existing shifts",
                resolution_suggestions=[
                    "Adjust shift times to avoid overlap",
                    "Cancel or reschedule one of the conflicting shifts"
                ]
            ))
        
        # Check minimum rest period between shifts using custom parameter
        rest_check_start = start_time - timedelta(hours=min_rest_hours)
        rest_check_end = end_time + timedelta(hours=min_rest_hours)
        
        nearby_shifts = self.db.query(EnhancedShift).filter(
            and_(
                EnhancedShift.staff_id == staff_id,
                EnhancedShift.status != ShiftStatus.CANCELLED,
                or_(
                    and_(
                        EnhancedShift.end_time > rest_check_start,
                        EnhancedShift.end_time <= start_time
                    ),
                    and_(
                        EnhancedShift.start_time >= end_time,
                        EnhancedShift.start_time < rest_check_end
                    )
                )
            )
        ).all()
        
        for shift in nearby_shifts:
            if shift.end_time <= start_time:
                rest_period = (start_time - shift.end_time).total_seconds() / 3600
            else:
                rest_period = (shift.start_time - end_time).total_seconds() / 3600
            
            if rest_period < min_rest_hours:
                conflicts.append(ScheduleConflict(
                    conflict_type="insufficient_rest",
                    severity="warning",
                    shift_ids=[shift.id],
                    description=f"Less than {min_rest_hours} hours rest between shifts",
                    resolution_suggestions=[
                        f"Ensure at least {min_rest_hours} hours between shifts",
                        "Consider assigning shift to another staff member"
                    ]
                ))
        
        return conflicts
    
    def _check_generation_conflicts(
        self,
        start_time: datetime,
        end_time: datetime,
        assigned_shifts: List[Tuple[datetime, datetime]],
        min_rest_hours: int
    ) -> bool:
        """Check for conflicts with shifts assigned during the current generation run"""
        for shift_start, shift_end in assigned_shifts:
            # Check for overlap
            if (shift_start <= start_time < shift_end or
                shift_start < end_time <= shift_end or
                (start_time <= shift_start and end_time >= shift_end)):
                return True
            
            # Check for insufficient rest period
            if shift_end <= start_time:
                rest_period = (start_time - shift_end).total_seconds() / 3600
            else:
                rest_period = (shift_start - end_time).total_seconds() / 3600
            
            if rest_period < min_rest_hours:
                return True
        
        return False
    
    def _calculate_generation_hours(
        self,
        staff_id: int,
        reference_date: date,
        assigned_shifts: List[Tuple[datetime, datetime]]
    ) -> float:
        """Calculate hours from shifts assigned during the current generation run"""
        # Find start of week (Monday)
        start_of_week = reference_date - timedelta(days=reference_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        total_hours = 0
        for shift_start, shift_end in assigned_shifts:
            # Only count shifts in the same week as reference_date
            if start_of_week <= shift_start.date() <= end_of_week:
                duration = (shift_end - shift_start).total_seconds() / 3600
                total_hours += duration
        
        return total_hours
    
    # Validation methods
    def validate_shift_times(self, start_time: datetime, end_time: datetime) -> bool:
        """Validate shift start and end times"""
        if end_time <= start_time:
            return False
        
        # Check if shift duration is reasonable (not more than 12 hours)
        duration = (end_time - start_time).total_seconds() / 3600
        if duration > 12:
            return False
        
        return True
    
    def validate_break_duration(self, shift_duration_minutes: int, break_duration: int) -> bool:
        """Validate break duration based on shift length"""
        # Basic labor law compliance - adjust based on local regulations
        if shift_duration_minutes >= 480:  # 8 hours or more
            return break_duration >= 30  # At least 30 min break
        elif shift_duration_minutes >= 360:  # 6 hours or more
            return break_duration >= 15  # At least 15 min break
        else:
            return True  # No break required for short shifts
    
    def validate_availability(self, start_time: time, end_time: time) -> bool:
        """Validate availability time range"""
        # Convert to comparable format if needed
        if isinstance(start_time, str):
            start_time = datetime.strptime(start_time, "%H:%M").time()
        if isinstance(end_time, str):
            end_time = datetime.strptime(end_time, "%H:%M").time()
        
        # End time must be after start time
        # Note: This doesn't handle overnight shifts properly
        return end_time > start_time
    
    def validate_shift_assignment(
        self, 
        staff_id: int, 
        start_time: datetime, 
        end_time: datetime,
        template_id: Optional[int] = None
    ) -> Tuple[bool, Optional[str]]:
        """Comprehensive shift assignment validation"""
        # Validate times
        if not self.validate_shift_times(start_time, end_time):
            return False, "Invalid shift times"
        
        # Check availability
        available, reason = self.check_availability(staff_id, start_time, end_time)
        if not available:
            return False, reason
        
        # Check conflicts
        conflicts = self.detect_conflicts(staff_id, start_time, end_time)
        if conflicts:
            return False, f"Conflicts with {len(conflicts)} other shifts"
        
        # Check weekly hours limit
        staff = self.db.query(StaffMember).filter(StaffMember.id == staff_id).first()
        if staff and staff.max_hours_per_week:
            current_hours = self._calculate_weekly_hours(staff_id, start_time.date())
            shift_hours = (end_time - start_time).total_seconds() / 3600
            
            if current_hours + shift_hours > staff.max_hours_per_week:
                return False, f"Would exceed maximum weekly hours ({staff.max_hours_per_week})"
        
        # Validate against template requirements if provided
        if template_id:
            template = self.db.query(ShiftTemplate).filter(
                ShiftTemplate.id == template_id
            ).first()
            
            if template:
                # Check if shift times match template
                shift_start_time = start_time.time()
                shift_end_time = end_time.time()
                
                if (shift_start_time != template.start_time or 
                    shift_end_time != template.end_time):
                    return False, "Shift times don't match template"
        
        return True, None
    
    def _calculate_weekly_hours(self, staff_id: int, reference_date: date) -> float:
        """Calculate total scheduled hours for a staff member in the week"""
        # Find start of week (Monday)
        start_of_week = reference_date - timedelta(days=reference_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        shifts = self.db.query(EnhancedShift).filter(
            and_(
                EnhancedShift.staff_id == staff_id,
                EnhancedShift.date >= start_of_week,
                EnhancedShift.date <= end_of_week,
                EnhancedShift.status.in_([ShiftStatus.SCHEDULED, ShiftStatus.PUBLISHED])
            )
        ).all()
        
        total_hours = 0
        for shift in shifts:
            duration = (shift.end_time - shift.start_time).total_seconds() / 3600
            total_hours += duration
        
        return total_hours
    
    def batch_create_shifts(self, shifts_data: List[dict]) -> List[EnhancedShift]:
        """Batch create multiple shifts efficiently"""
        shifts = []
        
        for shift_data in shifts_data:
            # Validate each shift
            valid, reason = self.validate_shift_assignment(
                shift_data['staff_id'],
                shift_data['start_time'],
                shift_data['end_time'],
                shift_data.get('template_id')
            )
            
            if valid:
                shift = EnhancedShift(**shift_data)
                shifts.append(shift)
            else:
                logger.warning(f"Skipping invalid shift: {reason}")
        
        # Bulk insert
        if shifts:
            self.db.bulk_save_objects(shifts)
            self.db.commit()
        
        return shifts
    
    def get_shifts_by_date_range(
        self, 
        restaurant_id: int, 
        start_date: date, 
        end_date: date
    ) -> List[EnhancedShift]:
        """Get shifts within a date range - optimized with indexes"""
        return self.db.query(EnhancedShift).filter(
            and_(
                EnhancedShift.date >= start_date,
                EnhancedShift.date <= end_date,
                EnhancedShift.location_id == restaurant_id
            )
        ).order_by(EnhancedShift.date, EnhancedShift.start_time).all()
    
    def get_staff_shifts_by_location(
        self, 
        staff_id: int, 
        location_id: int,
        start_date: date,
        end_date: date
    ) -> List[EnhancedShift]:
        """Get shifts for specific staff at specific location - uses composite index"""
        return self.db.query(EnhancedShift).filter(
            and_(
                EnhancedShift.staff_id == staff_id,
                EnhancedShift.location_id == location_id,
                EnhancedShift.date >= start_date,
                EnhancedShift.date <= end_date
            )
        ).order_by(EnhancedShift.date).all()
    
    def get_cached_analytics(
        self, 
        location_id: int, 
        start_date: date, 
        end_date: date
    ) -> Optional[Dict]:
        """Get cached analytics if available"""
        cache_key = f"analytics_{location_id}_{start_date}_{end_date}"
        
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            # Cache expires after 5 minutes
            if (datetime.utcnow() - timestamp).seconds < 300:
                return cached_data
        
        return None
    
    def cache_analytics(
        self, 
        location_id: int, 
        start_date: date, 
        end_date: date,
        data: Dict
    ):
        """Cache analytics data"""
        cache_key = f"analytics_{location_id}_{start_date}_{end_date}"
        self._cache[cache_key] = (data, datetime.utcnow())
        
        # Clean old cache entries
        if len(self._cache) > 100:
            # Remove oldest entries
            sorted_keys = sorted(
                self._cache.keys(), 
                key=lambda k: self._cache[k][1]
            )
            for key in sorted_keys[:20]:
                del self._cache[key]
    
    def publish_schedule(
        self,
        location_id: int,
        start_date: date,
        end_date: date,
        notify: bool = True
    ) -> Dict[str, Any]:
        """Publish draft schedules and optionally notify staff"""
        # Get all draft shifts in the date range
        shifts = self.db.query(EnhancedShift).filter(
            and_(
                EnhancedShift.location_id == location_id,
                EnhancedShift.date >= start_date,
                EnhancedShift.date <= end_date,
                EnhancedShift.status == ShiftStatus.DRAFT
            )
        ).all()
        
        published_count = 0
        for shift in shifts:
            shift.status = ShiftStatus.PUBLISHED
            shift.published_at = datetime.utcnow()
            published_count += 1
        
        # Create publication record
        publication = SchedulePublication(
            location_id=location_id,
            start_date=start_date,
            end_date=end_date,
            published_shift_count=published_count,
            published_at=datetime.utcnow()
        )
        self.db.add(publication)
        self.db.commit()
        
        # TODO: Send notifications to affected staff
        # This will be implemented in a follow-up PR
        # Example implementation:
        # if notify:
        #     notified_staff = set()
        #     for shift in shifts:
        #         if shift.staff_id not in notified_staff:
        #             send_notification(
        #                 staff_id=shift.staff_id,
        #                 type="schedule_published",
        #                 data={
        #                     "week_start": start_date,
        #                     "week_end": end_date,
        #                     "shift_count": len([s for s in shifts if s.staff_id == shift.staff_id])
        #                 }
        #             )
        #             notified_staff.add(shift.staff_id)
        
        return {
            "published_count": published_count,
            "publication_id": publication.id
        }