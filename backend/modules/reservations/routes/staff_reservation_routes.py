# backend/modules/reservations/routes/staff_reservation_routes.py

"""
Staff-facing reservation management routes.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from core.database import get_db
from core.auth import get_current_user
from modules.auth.models import User
from modules.auth.permissions import Permission, check_permission
from ..services import ReservationService, WaitlistService
from ..schemas import (
    ReservationResponse,
    ReservationListResponse,
    StaffReservationUpdate,
    ReservationStatus,
    WaitlistResponse,
    WaitlistListResponse,
    WaitlistStatus,
    ReservationSettingsResponse
)
from ..models.reservation_models import ReservationSettings

router = APIRouter()


@router.get("/daily", response_model=ReservationListResponse)
async def get_daily_reservations(
    reservation_date: date = Query(..., description="Date to get reservations for"),
    status: Optional[ReservationStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all reservations for a specific date.
    
    Requires RESERVATION_VIEW permission.
    """
    check_permission(current_user, Permission.RESERVATION_VIEW)
    
    service = ReservationService(db)
    
    # Get all reservations for the date
    all_reservations = service.get_daily_reservations(reservation_date, status)
    
    # Paginate
    total = len(all_reservations)
    skip = (page - 1) * page_size
    reservations = all_reservations[skip:skip + page_size]
    
    # Convert to response models
    reservation_responses = []
    for reservation in reservations:
        customer = reservation.customer
        reservation_responses.append(ReservationResponse(
            id=reservation.id,
            customer_id=reservation.customer_id,
            reservation_date=reservation.reservation_date,
            reservation_time=reservation.reservation_time,
            party_size=reservation.party_size,
            duration_minutes=reservation.duration_minutes,
            status=reservation.status,
            confirmation_code=reservation.confirmation_code,
            source=reservation.source,
            table_numbers=reservation.table_numbers,
            customer_name=f"{customer.first_name} {customer.last_name}",
            customer_email=customer.email,
            customer_phone=customer.phone,
            special_requests=reservation.special_requests,
            dietary_restrictions=reservation.dietary_restrictions,
            occasion=reservation.occasion,
            notification_method=reservation.notification_method,
            reminder_sent=reservation.reminder_sent,
            converted_from_waitlist=reservation.converted_from_waitlist,
            created_at=reservation.created_at,
            updated_at=reservation.updated_at,
            confirmed_at=reservation.confirmed_at,
            seated_at=reservation.seated_at,
            completed_at=reservation.completed_at,
            cancelled_at=reservation.cancelled_at,
            cancellation_reason=reservation.cancellation_reason,
            cancelled_by=reservation.cancelled_by
        ))
    
    total_pages = (total + page_size - 1) // page_size
    
    return ReservationListResponse(
        reservations=reservation_responses,
        total=total,
        page=page,
        page_size=page_size,
        has_next=page < total_pages,
        has_previous=page > 1
    )


@router.patch("/{reservation_id}", response_model=ReservationResponse)
async def update_reservation_status(
    reservation_id: int,
    update_data: StaffReservationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update reservation status or details.
    
    Requires RESERVATION_UPDATE permission.
    Can update status (seated, completed, no-show) and table assignment.
    """
    check_permission(current_user, Permission.RESERVATION_UPDATE)
    
    service = ReservationService(db)
    
    try:
        reservation = await service.staff_update_reservation(
            reservation_id,
            update_data,
            current_user.id
        )
        
        customer = reservation.customer
        return ReservationResponse(
            id=reservation.id,
            customer_id=reservation.customer_id,
            reservation_date=reservation.reservation_date,
            reservation_time=reservation.reservation_time,
            party_size=reservation.party_size,
            duration_minutes=reservation.duration_minutes,
            status=reservation.status,
            confirmation_code=reservation.confirmation_code,
            source=reservation.source,
            table_numbers=reservation.table_numbers,
            customer_name=f"{customer.first_name} {customer.last_name}",
            customer_email=customer.email,
            customer_phone=customer.phone,
            special_requests=reservation.special_requests,
            dietary_restrictions=reservation.dietary_restrictions,
            occasion=reservation.occasion,
            notification_method=reservation.notification_method,
            reminder_sent=reservation.reminder_sent,
            converted_from_waitlist=reservation.converted_from_waitlist,
            created_at=reservation.created_at,
            updated_at=reservation.updated_at,
            confirmed_at=reservation.confirmed_at,
            seated_at=reservation.seated_at,
            completed_at=reservation.completed_at,
            cancelled_at=reservation.cancelled_at,
            cancellation_reason=reservation.cancellation_reason,
            cancelled_by=reservation.cancelled_by
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{reservation_id}/seat", response_model=ReservationResponse)
async def mark_as_seated(
    reservation_id: int,
    table_number: Optional[str] = Query(None, description="Assigned table number"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark a reservation as seated.
    
    Requires RESERVATION_UPDATE permission.
    """
    check_permission(current_user, Permission.RESERVATION_UPDATE)
    
    update_data = StaffReservationUpdate(
        status=ReservationStatus.SEATED,
        table_numbers=table_number
    )
    
    return await update_reservation_status(
        reservation_id,
        update_data,
        current_user,
        db
    )


@router.post("/{reservation_id}/complete", response_model=ReservationResponse)
async def mark_as_completed(
    reservation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark a reservation as completed.
    
    Requires RESERVATION_UPDATE permission.
    """
    check_permission(current_user, Permission.RESERVATION_UPDATE)
    
    update_data = StaffReservationUpdate(status=ReservationStatus.COMPLETED)
    
    return await update_reservation_status(
        reservation_id,
        update_data,
        current_user,
        db
    )


@router.post("/{reservation_id}/no-show", response_model=ReservationResponse)
async def mark_as_no_show(
    reservation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark a reservation as no-show.
    
    Requires RESERVATION_UPDATE permission.
    Tracks no-show history for customers.
    """
    check_permission(current_user, Permission.RESERVATION_UPDATE)
    
    update_data = StaffReservationUpdate(status=ReservationStatus.NO_SHOW)
    
    return await update_reservation_status(
        reservation_id,
        update_data,
        current_user,
        db
    )


# Waitlist management for staff
@router.get("/waitlist/daily", response_model=WaitlistListResponse)
async def get_daily_waitlist(
    waitlist_date: date = Query(..., description="Date to get waitlist for"),
    status: Optional[WaitlistStatus] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all waitlist entries for a specific date.
    
    Requires RESERVATION_VIEW permission.
    """
    check_permission(current_user, Permission.RESERVATION_VIEW)
    
    service = WaitlistService(db)
    
    entries = service.get_waitlist_by_date(waitlist_date, status)
    
    # Convert to response models
    waitlist_responses = []
    for entry in entries:
        customer = entry.customer
        estimated_wait = service.estimate_wait_time(
            entry.requested_date,
            entry.requested_time_start,
            entry.party_size
        )
        
        waitlist_responses.append(WaitlistResponse(
            id=entry.id,
            customer_id=entry.customer_id,
            requested_date=entry.requested_date,
            requested_time_start=entry.requested_time_start,
            requested_time_end=entry.requested_time_end,
            party_size=entry.party_size,
            flexible_date=entry.flexible_date,
            flexible_time=entry.flexible_time,
            alternative_dates=entry.alternative_dates,
            status=entry.status,
            position=entry.position,
            estimated_wait_time=estimated_wait,
            customer_name=f"{customer.first_name} {customer.last_name}",
            customer_email=customer.email,
            customer_phone=customer.phone,
            notification_method=entry.notification_method,
            notified_at=entry.notified_at,
            notification_expires_at=entry.notification_expires_at,
            special_requests=entry.special_requests,
            priority=entry.priority,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            expires_at=entry.expires_at
        ))
    
    return WaitlistListResponse(
        waitlist_entries=waitlist_responses,
        total=len(entries),
        page=1,
        page_size=len(entries),
        has_next=False,
        has_previous=False
    )


@router.post("/waitlist/{waitlist_id}/notify")
async def notify_waitlist_customer(
    waitlist_id: int,
    available_time: str = Query(..., pattern="^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually notify a waitlist customer about availability.
    
    Requires RESERVATION_UPDATE permission.
    """
    check_permission(current_user, Permission.RESERVATION_UPDATE)
    
    service = WaitlistService(db)
    
    # Get the waitlist entry
    from ..models.reservation_models import Waitlist
    entry = db.query(Waitlist).filter_by(id=waitlist_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Waitlist entry not found"
        )
    
    # Parse time
    from datetime import datetime
    time_obj = datetime.strptime(available_time, "%H:%M").time()
    
    # Get settings for notification window
    settings = db.query(ReservationSettings).filter_by(restaurant_id=1).first()
    
    try:
        await service.notify_waitlist_availability(
            entry,
            entry.requested_date,
            time_obj,
            settings.waitlist_notification_window
        )
        
        return {"message": "Customer notified successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to notify customer: {str(e)}"
        )


# Settings management
@router.get("/settings", response_model=ReservationSettingsResponse)
async def get_reservation_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current reservation settings.
    
    Requires ADMIN_ACCESS permission.
    """
    check_permission(current_user, Permission.ADMIN_ACCESS)
    
    settings = db.query(ReservationSettings).filter_by(restaurant_id=1).first()
    if not settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation settings not found"
        )
    
    return ReservationSettingsResponse.from_orm(settings)


@router.put("/settings", response_model=ReservationSettingsResponse)
async def update_reservation_settings(
    settings_update: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update reservation settings.
    
    Requires ADMIN_ACCESS permission.
    """
    check_permission(current_user, Permission.ADMIN_ACCESS)
    
    settings = db.query(ReservationSettings).filter_by(restaurant_id=1).first()
    if not settings:
        settings = ReservationSettings(restaurant_id=1)
        db.add(settings)
    
    # Update fields
    for field, value in settings_update.items():
        if hasattr(settings, field):
            setattr(settings, field, value)
    
    db.commit()
    db.refresh(settings)
    
    return ReservationSettingsResponse.from_orm(settings)