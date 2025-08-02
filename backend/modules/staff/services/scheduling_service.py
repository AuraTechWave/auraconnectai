from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime, date, timedelta, time
from typing import List, Dict, Optional, Tuple
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

logger = logging.getLogger(__name__)


class SchedulingService:
    def __init__(self, db: Session):
        self.db = db
    
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
        """Get staffing analytics for a date range"""
        
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
        
        return analytics