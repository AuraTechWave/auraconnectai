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
    # Check permission
    SchedulingPermissions.require_permission(
        current_user["sub"],
        "create_shift",
        db,
        location_id=shift.location_id
    )
    
    db_shift = EnhancedShift(**shift.dict())
    db.add(db_shift)
    db.commit()
    db.refresh(db_shift)
    return db_shift


@router.get("/shifts", response_model=List[ShiftResponse])
async def get_shifts(
    location_id: Optional[int] = None,
    staff_id: Optional[int] = None,
    role_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    status: Optional[ShiftStatus] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get shifts with optional filters"""
    query = db.query(EnhancedShift)
    
    if location_id:
        query = query.filter(EnhancedShift.location_id == location_id)
    if staff_id:
        query = query.filter(EnhancedShift.staff_id == staff_id)
    if role_id:
        query = query.filter(EnhancedShift.role_id == role_id)
    if start_date:
        query = query.filter(EnhancedShift.date >= start_date)
    if end_date:
        query = query.filter(EnhancedShift.date <= end_date)
    if status:
        query = query.filter(EnhancedShift.status == status)
    
    return query.all()


@router.get("/shifts/{shift_id}", response_model=ShiftResponse)
async def get_shift(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get a specific shift"""
    shift = db.query(EnhancedShift).filter(EnhancedShift.id == shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    return shift


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
    
    for key, value in shift.dict(exclude_unset=True).items():
        setattr(db_shift, key, value)
    
    db.commit()
    db.refresh(db_shift)
    return db_shift


@router.delete("/shifts/{shift_id}")
async def delete_shift(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete a shift"""
    shift = db.query(EnhancedShift).filter(EnhancedShift.id == shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    
    db.delete(shift)
    db.commit()
    return {"message": "Shift deleted successfully"}


# Break Management Endpoints
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
    
    db_break = ShiftBreak(**break_data.dict())
    db.add(db_break)
    db.commit()
    db.refresh(db_break)
    return db_break


@router.get("/shifts/{shift_id}/breaks", response_model=List[ShiftBreakResponse])
async def get_shift_breaks(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all breaks for a shift"""
    breaks = db.query(ShiftBreak).filter(ShiftBreak.shift_id == shift_id).all()
    return breaks


# Availability Management Endpoints
@router.post("/availability", response_model=AvailabilityResponse)
async def create_availability(
    availability: AvailabilityCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create availability for a staff member"""
    # Check if staff member exists
    staff = db.query(StaffMember).filter(StaffMember.id == availability.staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    db_availability = StaffAvailability(**availability.dict())
    db.add(db_availability)
    db.commit()
    db.refresh(db_availability)
    return db_availability


@router.get("/availability", response_model=List[AvailabilityResponse])
async def get_availability(
    staff_id: Optional[int] = None,
    day_of_week: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get availability records"""
    query = db.query(StaffAvailability)
    
    if staff_id:
        query = query.filter(StaffAvailability.staff_id == staff_id)
    if day_of_week is not None:
        query = query.filter(StaffAvailability.day_of_week == day_of_week)
    
    return query.all()


@router.put("/availability/{availability_id}", response_model=AvailabilityResponse)
async def update_availability(
    availability_id: int,
    availability: AvailabilityUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update availability"""
    db_availability = db.query(StaffAvailability).filter(
        StaffAvailability.id == availability_id
    ).first()
    if not db_availability:
        raise HTTPException(status_code=404, detail="Availability not found")
    
    for key, value in availability.dict(exclude_unset=True).items():
        setattr(db_availability, key, value)
    
    db.commit()
    db.refresh(db_availability)
    return db_availability


# Shift Swap Endpoints
@router.post("/swaps", response_model=ShiftSwapResponse)
async def request_shift_swap(
    swap_request: ShiftSwapRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Request a shift swap"""
    # Verify the from_shift exists and belongs to the requester
    from_shift = db.query(EnhancedShift).filter(
        EnhancedShift.id == swap_request.from_shift_id
    ).first()
    if not from_shift:
        raise HTTPException(status_code=404, detail="From shift not found")
    
    if from_shift.staff_id != swap_request.requester_id:
        raise HTTPException(status_code=403, detail="Cannot swap shifts you don't own")
    
    # If to_shift_id is provided, verify it exists
    if swap_request.to_shift_id:
        to_shift = db.query(EnhancedShift).filter(
            EnhancedShift.id == swap_request.to_shift_id
        ).first()
        if not to_shift:
            raise HTTPException(status_code=404, detail="To shift not found")
    
    db_swap = ShiftSwap(**swap_request.dict())
    db.add(db_swap)
    db.commit()
    db.refresh(db_swap)
    return db_swap


@router.get("/swaps", response_model=List[ShiftSwapResponse])
async def get_shift_swaps(
    requester_id: Optional[int] = None,
    status: Optional[SwapStatus] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get shift swap requests"""
    query = db.query(ShiftSwap)
    
    if requester_id:
        query = query.filter(ShiftSwap.requester_id == requester_id)
    if status:
        query = query.filter(ShiftSwap.status == status)
    
    return query.all()


@router.put("/swaps/{swap_id}/approve", response_model=ShiftSwapResponse)
async def approve_shift_swap(
    swap_id: int,
    approval: ShiftSwapApproval,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Approve or reject a shift swap request"""
    # Check permission
    SchedulingPermissions.require_permission(
        current_user["sub"],
        "approve_swaps",
        db
    )
    
    db_swap = db.query(ShiftSwap).filter(ShiftSwap.id == swap_id).first()
    if not db_swap:
        raise HTTPException(status_code=404, detail="Swap request not found")
    
    if approval.approved:
        db_swap.status = SwapStatus.APPROVED
        db_swap.approved_by_id = current_user["user_id"]
        db_swap.approved_at = datetime.utcnow()
        db_swap.manager_notes = approval.manager_notes
        
        # Perform the actual swap
        from_shift = db.query(EnhancedShift).filter(
            EnhancedShift.id == db_swap.from_shift_id
        ).first()
        
        if db_swap.to_shift_id:
            to_shift = db.query(EnhancedShift).filter(
                EnhancedShift.id == db_swap.to_shift_id
            ).first()
            
            # Swap staff assignments
            from_staff_id = from_shift.staff_id
            from_shift.staff_id = to_shift.staff_id
            to_shift.staff_id = from_staff_id
        elif db_swap.to_staff_id:
            from_shift.staff_id = db_swap.to_staff_id
    else:
        db_swap.status = SwapStatus.REJECTED
        db_swap.manager_notes = approval.manager_notes
    
    db.commit()
    db.refresh(db_swap)
    return db_swap


# Schedule Generation Endpoints
@router.post("/generate", response_model=dict)
async def generate_schedule(
    request: ScheduleGenerationRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Generate a schedule for a date range"""
    # Check permission
    SchedulingPermissions.require_permission(
        current_user["sub"],
        "generate_schedule",
        db,
        location_id=request.location_id
    )
    
    service = SchedulingService(db)
    
    if getattr(request, "use_historical_demand", False):
        # Use flexible demand-based scheduling for better shift optimization
        if getattr(request, "use_flexible_shifts", False):
            shifts = service.generate_flexible_demand_schedule(
                request.start_date,
                request.end_date,
                request.location_id,
                demand_lookback_days=getattr(request, "demand_lookback_days", 90),
                buffer_percentage=getattr(request, "buffer_percentage", 10.0),
                respect_availability=getattr(request, "respect_availability", True),
                max_hours_per_week=getattr(request, "max_hours_per_week", 40),
                min_hours_between_shifts=getattr(request, "min_hours_between_shifts", 8),
                min_shift_hours=getattr(request, "min_shift_hours", 4),
                max_shift_hours=getattr(request, "max_shift_hours", 8),
            )
        else:
            # Use fixed block scheduling
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
    
    # Determine strategy name
    if getattr(request, "use_historical_demand", False):
        if getattr(request, "use_flexible_shifts", False):
            strategy = "flexible_demand"
        else:
            strategy = "demand_aware"
    else:
        strategy = "templates"
    
    return {
        "message": "Schedule generated",
        "strategy": strategy,
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
    """Check for schedule conflicts"""
    service = SchedulingService(db)
    return service.check_schedule_conflicts(
        staff_id, start_time, end_time, exclude_shift_id
    )


@router.get("/analytics/summary", response_model=List[StaffScheduleSummary])
async def get_staff_schedule_summary(
    week_start: date = Query(...),
    location_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get weekly schedule summary for staff"""
    service = SchedulingService(db)
    return service.get_staff_schedule_summary(week_start, location_id)