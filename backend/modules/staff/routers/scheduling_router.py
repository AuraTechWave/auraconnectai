from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload, joinedload
from typing import List, Optional
from datetime import datetime, date, timedelta

from core.database import get_db
from core.auth import get_current_user
from ..models.scheduling_models import (
    EnhancedShift, ShiftTemplate, StaffAvailability,
    ShiftSwap, ShiftBreak, SchedulePublication
)
from ..utils.permissions import SchedulingPermissions
from ..models.staff_models import StaffMember
from ..schemas.scheduling_schemas import (
    ShiftTemplateCreate, ShiftTemplateUpdate, ShiftTemplateResponse,
    ShiftCreate, ShiftUpdate, ShiftResponse,
    ShiftBreakCreate, ShiftBreakResponse,
    AvailabilityCreate, AvailabilityUpdate, AvailabilityResponse,
    ShiftSwapRequest, ShiftSwapApproval, ShiftSwapResponse,
    ScheduleGenerationRequest, SchedulePublishRequest, SchedulePublishResponse,
    StaffingAnalytics, StaffScheduleSummary, ScheduleConflict
)
from ..services.scheduling_service import SchedulingService
from ..enums.scheduling_enums import ShiftStatus, SwapStatus

router = APIRouter()


# Shift Template Endpoints
@router.post("/templates", response_model=ShiftTemplateResponse)
async def create_shift_template(
    template: ShiftTemplateCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new shift template (Manager/Admin only)"""
    # Check permission
    SchedulingPermissions.require_permission(
        current_user["sub"],
        "create_template",
        db,
        location_id=template.location_id
    )
    
    db_template = ShiftTemplate(**template.dict())
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template


@router.get("/templates", response_model=List[ShiftTemplateResponse])
async def get_shift_templates(
    location_id: Optional[int] = None,
    role_id: Optional[int] = None,
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all shift templates"""
    query = db.query(ShiftTemplate)
    
    if location_id:
        query = query.filter(ShiftTemplate.location_id == location_id)
    if role_id:
        query = query.filter(ShiftTemplate.role_id == role_id)
    if is_active is not None:
        query = query.filter(ShiftTemplate.is_active == is_active)
    
    return query.all()


@router.put("/templates/{template_id}", response_model=ShiftTemplateResponse)
async def update_shift_template(
    template_id: int,
    template: ShiftTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update a shift template"""
    db_template = db.query(ShiftTemplate).filter(ShiftTemplate.id == template_id).first()
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    for key, value in template.dict(exclude_unset=True).items():
        setattr(db_template, key, value)
    
    db.commit()
    db.refresh(db_template)
    return db_template


# Shift Management Endpoints
@router.post("/shifts", response_model=ShiftResponse)
async def create_shift(
    shift: ShiftCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new shift"""
    # Check for conflicts
    service = SchedulingService(db)
    conflicts = service.detect_conflicts(
        shift.staff_id,
        shift.start_time,
        shift.end_time
    )
    
    error_conflicts = [c for c in conflicts if c.severity == "error"]
    if error_conflicts:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Scheduling conflicts detected",
                "conflicts": [c.dict() for c in error_conflicts]
            }
        )
    
    # Calculate estimated cost
    estimated_cost = service.calculate_labor_cost(
        shift.staff_id,
        shift.start_time,
        shift.end_time,
        shift.hourly_rate
    )
    
    db_shift = EnhancedShift(
        **shift.dict(),
        estimated_cost=estimated_cost,
        created_by_id=current_user["user_id"]
    )
    db.add(db_shift)
    db.commit()
    db.refresh(db_shift)
    
    # Add staff name and role name for response
    staff = db.query(StaffMember).filter(StaffMember.id == db_shift.staff_id).first()
    response_dict = db_shift.__dict__.copy()
    response_dict["staff_name"] = staff.name if staff else None
    response_dict["role_name"] = staff.role.name if staff and staff.role else None
    
    return ShiftResponse(**response_dict)


@router.get("/shifts", response_model=List[ShiftResponse])
async def get_shifts(
    start_date: date = Query(...),
    end_date: date = Query(...),
    staff_id: Optional[int] = None,
    location_id: Optional[int] = None,
    status: Optional[ShiftStatus] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get shifts for a date range with eager loading to prevent N+1 queries"""
    query = db.query(EnhancedShift).options(
        joinedload(EnhancedShift.staff_member).joinedload(StaffMember.role),
        selectinload(EnhancedShift.breaks),
        joinedload(EnhancedShift.template)
    ).filter(
        EnhancedShift.date >= start_date,
        EnhancedShift.date <= end_date
    )
    
    if staff_id:
        query = query.filter(EnhancedShift.staff_id == staff_id)
    if location_id:
        query = query.filter(EnhancedShift.location_id == location_id)
    if status:
        query = query.filter(EnhancedShift.status == status)
    
    shifts = query.all()
    
    # Transform to response format (no additional queries needed)
    result = []
    for shift in shifts:
        shift_dict = {
            "id": shift.id,
            "staff_id": shift.staff_id,
            "staff_name": shift.staff_member.name if shift.staff_member else None,
            "role_id": shift.role_id,
            "role_name": shift.role.name if shift.role else None,
            "location_id": shift.location_id,
            "date": shift.date,
            "start_time": shift.start_time,
            "end_time": shift.end_time,
            "shift_type": shift.shift_type,
            "status": shift.status,
            "template_id": shift.template_id,
            "hourly_rate": shift.hourly_rate,
            "estimated_cost": shift.estimated_cost,
            "actual_cost": shift.actual_cost,
            "notes": shift.notes,
            "color": shift.color,
            "breaks": shift.breaks,
            "created_at": shift.created_at,
            "updated_at": shift.updated_at,
            "published_at": shift.published_at
        }
        result.append(ShiftResponse(**shift_dict))
    
    return result


@router.put("/shifts/{shift_id}", response_model=ShiftResponse)
async def update_shift(
    shift_id: int,
    shift: ShiftUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update a shift"""
    db_shift = db.query(EnhancedShift).filter(EnhancedShift.id == shift_id).first()
    if not db_shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    
    # Check conflicts if times or staff changed
    if shift.start_time or shift.end_time or shift.staff_id:
        service = SchedulingService(db)
        conflicts = service.detect_conflicts(
            shift.staff_id or db_shift.staff_id,
            shift.start_time or db_shift.start_time,
            shift.end_time or db_shift.end_time,
            exclude_shift_id=shift_id
        )
        
        error_conflicts = [c for c in conflicts if c.severity == "error"]
        if error_conflicts:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Scheduling conflicts detected",
                    "conflicts": [c.dict() for c in error_conflicts]
                }
            )
    
    for key, value in shift.dict(exclude_unset=True).items():
        setattr(db_shift, key, value)
    
    db.commit()
    db.refresh(db_shift)
    
    # Add staff name and role name for response
    staff = db.query(StaffMember).filter(StaffMember.id == db_shift.staff_id).first()
    response_dict = db_shift.__dict__.copy()
    response_dict["staff_name"] = staff.name if staff else None
    response_dict["role_name"] = staff.role.name if staff and staff.role else None
    response_dict["breaks"] = db_shift.breaks
    
    return ShiftResponse(**response_dict)


@router.delete("/shifts/{shift_id}")
async def delete_shift(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete or cancel a shift"""
    db_shift = db.query(EnhancedShift).filter(EnhancedShift.id == shift_id).first()
    if not db_shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    
    # Cancel instead of delete if published
    if db_shift.status == ShiftStatus.PUBLISHED:
        db_shift.status = ShiftStatus.CANCELLED
        db.commit()
        return {"message": "Shift cancelled"}
    else:
        db.delete(db_shift)
        db.commit()
        return {"message": "Shift deleted"}


# Break Management
@router.post("/shifts/{shift_id}/breaks", response_model=ShiftBreakResponse)
async def add_shift_break(
    shift_id: int,
    break_data: ShiftBreakCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Add a break to a shift"""
    shift = db.query(EnhancedShift).filter(EnhancedShift.id == shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    
    # Validate break times are within shift
    if break_data.start_time < shift.start_time or break_data.end_time > shift.end_time:
        raise HTTPException(status_code=400, detail="Break times must be within shift times")
    
    duration_minutes = int((break_data.end_time - break_data.start_time).total_seconds() / 60)
    
    db_break = ShiftBreak(
        shift_id=shift_id,
        break_type=break_data.break_type,
        start_time=break_data.start_time,
        end_time=break_data.end_time,
        duration_minutes=duration_minutes,
        is_paid=break_data.is_paid
    )
    
    db.add(db_break)
    db.commit()
    db.refresh(db_break)
    return db_break


# Availability Management
@router.post("/availability", response_model=AvailabilityResponse)
async def set_availability(
    availability: AvailabilityCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Set staff availability"""
    db_availability = StaffAvailability(**availability.dict())
    db.add(db_availability)
    db.commit()
    db.refresh(db_availability)
    
    # Add staff name
    staff = db.query(StaffMember).filter(StaffMember.id == db_availability.staff_id).first()
    response_dict = db_availability.__dict__.copy()
    response_dict["staff_name"] = staff.name if staff else None
    
    return AvailabilityResponse(**response_dict)


@router.get("/availability", response_model=List[AvailabilityResponse])
async def get_availability(
    staff_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get staff availability"""
    query = db.query(StaffAvailability)
    
    if staff_id:
        query = query.filter(StaffAvailability.staff_id == staff_id)
    
    if start_date and end_date:
        query = query.filter(
            or_(
                StaffAvailability.specific_date.between(start_date, end_date),
                StaffAvailability.day_of_week.isnot(None)
            )
        )
    
    availability = query.all()
    
    # Add staff names
    result = []
    for avail in availability:
        staff = db.query(StaffMember).filter(StaffMember.id == avail.staff_id).first()
        avail_dict = avail.__dict__.copy()
        avail_dict["staff_name"] = staff.name if staff else None
        result.append(AvailabilityResponse(**avail_dict))
    
    return result


# Shift Swap Management
@router.post("/swaps", response_model=ShiftSwapResponse)
async def request_shift_swap(
    swap_request: ShiftSwapRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Request a shift swap"""
    # Verify requester owns the from_shift (with eager loading)
    from_shift = db.query(EnhancedShift).options(
        joinedload(EnhancedShift.staff_member)
    ).filter(
        EnhancedShift.id == swap_request.from_shift_id
    ).first()
    
    if not from_shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    
    if from_shift.staff_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Can only swap your own shifts")
    
    # Validate the swap request
    service = SchedulingService(db)
    valid, reason = service.validate_swap_request(
        swap_request.from_shift_id,
        swap_request.to_shift_id,
        swap_request.to_staff_id
    )
    
    if not valid:
        raise HTTPException(status_code=400, detail=reason)
    
    db_swap = ShiftSwap(
        requester_id=current_user["user_id"],
        **swap_request.dict()
    )
    
    db.add(db_swap)
    db.commit()
    db.refresh(db_swap)
    
    # Build response
    response_dict = {
        "id": db_swap.id,
        "requester_id": db_swap.requester_id,
        "requester_name": from_shift.staff_member.name,
        "from_shift_id": db_swap.from_shift_id,
        "from_shift_details": {
            "date": from_shift.date,
            "start_time": from_shift.start_time,
            "end_time": from_shift.end_time
        },
        "to_shift_id": db_swap.to_shift_id,
        "to_staff_id": db_swap.to_staff_id,
        "status": db_swap.status,
        "reason": db_swap.reason,
        "created_at": db_swap.created_at
    }
    
    if db_swap.to_shift_id:
        to_shift = db_swap.to_shift
        response_dict["to_shift_details"] = {
            "date": to_shift.date,
            "start_time": to_shift.start_time,
            "end_time": to_shift.end_time
        }
    
    if db_swap.to_staff_id:
        to_staff = db_swap.to_staff
        response_dict["to_staff_name"] = to_staff.name
    
    return ShiftSwapResponse(**response_dict)


@router.put("/swaps/{swap_id}/approve")
async def approve_shift_swap(
    swap_id: int,
    approval: ShiftSwapApproval,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Approve or reject a shift swap (Manager/Supervisor only)"""
    # Check permission
    SchedulingPermissions.require_permission(
        current_user["sub"],
        "approve_swap",
        db
    )
    
    service = SchedulingService(db)
    
    if approval.status == SwapStatus.APPROVED:
        swap = service.approve_shift_swap(
            swap_id,
            current_user["user_id"],
            approval.manager_notes
        )
        return {"message": "Shift swap approved", "swap_id": swap.id}
    else:
        swap = db.query(ShiftSwap).filter(ShiftSwap.id == swap_id).first()
        if not swap:
            raise HTTPException(status_code=404, detail="Swap request not found")
        
        swap.status = approval.status
        swap.manager_notes = approval.manager_notes
        swap.approved_by_id = current_user["user_id"]
        swap.approved_at = datetime.utcnow()
        
        db.commit()
        return {"message": f"Shift swap {approval.status.value}", "swap_id": swap.id}


# Schedule Generation
@router.post("/schedule/generate")
async def generate_schedule(
    request: ScheduleGenerationRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Generate schedule from templates or historical demand (Manager/Admin only)"""
    # Check permission
    SchedulingPermissions.require_permission(
        current_user["sub"],
        "generate_schedule",
        db,
        location_id=request.location_id
    )
    
    service = SchedulingService(db)
    
    if getattr(request, "use_historical_demand", False):
        shifts = service.generate_demand_aware_schedule(
            request.start_date,
            request.end_date,
            request.location_id,
            demand_lookback_days=getattr(request, "demand_lookback_days", 90),
            buffer_percentage=getattr(request, "buffer_percentage", 10.0),
            respect_availability=getattr(request, "respect_availability", True),
            max_hours_per_week=getattr(request, "max_hours_per_week", 40),
            min_hours_between_shifts=getattr(request, "min_hours_between_shifts", 8),
        )
    else:
        shifts = service.generate_schedule_from_templates(
            request.start_date,
            request.end_date,
            request.location_id,
            request.auto_assign
        )
    
    # Save generated shifts
    for shift in shifts:
        db.add(shift)
    
    db.commit()
    
    return {
        "message": "Schedule generated",
        "strategy": "demand_aware" if getattr(request, "use_historical_demand", False) else "templates",
        "shifts_created": len(shifts),
        "start_date": request.start_date,
        "end_date": request.end_date
    }


# Schedule Publishing
@router.post("/schedule/publish", response_model=SchedulePublishResponse)
async def publish_schedule(
    request: SchedulePublishRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Publish schedule and notify staff (Manager/Admin only)"""
    # Check permission
    SchedulingPermissions.require_permission(
        current_user["sub"],
        "publish_schedule",
        db,
        location_id=request.location_id if hasattr(request, 'location_id') else None
    )
    # Get all draft shifts in date range
    shifts = db.query(EnhancedShift).filter(
        EnhancedShift.date >= request.start_date,
        EnhancedShift.date <= request.end_date,
        EnhancedShift.status == ShiftStatus.DRAFT
    ).all()
    
    if not shifts:
        raise HTTPException(status_code=400, detail="No draft shifts to publish")
    
    # Calculate statistics
    total_hours = sum(
        (shift.end_time - shift.start_time).total_seconds() / 3600
        for shift in shifts
    )
    estimated_cost = sum(shift.estimated_cost or 0 for shift in shifts)
    
    # Update shift status
    for shift in shifts:
        shift.status = ShiftStatus.PUBLISHED
        shift.published_at = datetime.utcnow()
    
    # Create publication record
    publication = SchedulePublication(
        start_date=request.start_date,
        end_date=request.end_date,
        published_by_id=current_user["user_id"],
        total_shifts=len(shifts),
        total_hours=total_hours,
        estimated_labor_cost=estimated_cost,
        notes=request.notes
    )
    
    db.add(publication)
    
    # TODO: Send notifications if requested
    if request.send_notifications:
        # Implement notification logic
        publication.notifications_sent = True
        publication.notification_count = len(set(s.staff_id for s in shifts if s.staff_id))
    
    db.commit()
    db.refresh(publication)
    
    return publication


# Analytics
@router.get("/analytics/staffing", response_model=List[StaffingAnalytics])
async def get_staffing_analytics(
    start_date: date = Query(...),
    end_date: date = Query(...),
    location_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get staffing analytics for a date range"""
    service = SchedulingService(db)
    return service.get_staffing_analytics(start_date, end_date, location_id)


@router.get("/analytics/conflicts", response_model=List[ScheduleConflict])
async def check_schedule_conflicts(
    staff_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_shift_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Check for scheduling conflicts"""
    service = SchedulingService(db)
    return service.detect_conflicts(staff_id, start_time, end_time, exclude_shift_id)


@router.get("/staff/{staff_id}/schedule-summary", response_model=StaffScheduleSummary)
async def get_staff_schedule_summary(
    staff_id: int,
    week_start: date = Query(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get weekly schedule summary for a staff member"""
    week_end = week_start + timedelta(days=6)
    
    shifts = db.query(EnhancedShift).filter(
        EnhancedShift.staff_id == staff_id,
        EnhancedShift.date >= week_start,
        EnhancedShift.date <= week_end,
        EnhancedShift.status != ShiftStatus.CANCELLED
    ).all()
    
    staff = db.query(StaffMember).filter(StaffMember.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    total_hours = sum(
        (shift.end_time - shift.start_time).total_seconds() / 3600
        for shift in shifts
    )
    
    overtime_hours = max(0, total_hours - 40)
    estimated_earnings = sum(shift.estimated_cost or 0 for shift in shifts)
    
    # Check availability compliance
    service = SchedulingService(db)
    compliant_shifts = 0
    for shift in shifts:
        available, _ = service.check_availability(staff_id, shift.start_time, shift.end_time)
        if available:
            compliant_shifts += 1
    
    availability_compliance = (compliant_shifts / len(shifts) * 100) if shifts else 100
    
    return StaffScheduleSummary(
        staff_id=staff_id,
        staff_name=staff.name,
        week_start=week_start,
        total_shifts=len(shifts),
        total_hours=total_hours,
        overtime_hours=overtime_hours,
        availability_compliance=availability_compliance,
        estimated_earnings=estimated_earnings
    )