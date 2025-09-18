# backend/modules/reservations/routes/waitlist_routes.py

"""
Waitlist management API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date

from core.database import get_db
from modules.customers.auth.customer_auth import get_current_customer
from modules.customers.models.customer_models import Customer
from ..services import WaitlistService
from ..schemas import (
    WaitlistCreate,
    WaitlistResponse,
    WaitlistListResponse,
    WaitlistStatus,
    ReservationResponse,
)

router = APIRouter()


@router.post("/", response_model=WaitlistResponse, status_code=status.HTTP_201_CREATED)
async def join_waitlist(
    waitlist_data: WaitlistCreate,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """
    Add customer to waitlist for a specific date/time range.

    - Automatically assigns position in queue
    - Sends confirmation notification
    - Monitors for availability
    """
    service = WaitlistService(db)

    try:
        waitlist_entry = await service.add_to_waitlist(
            current_customer.id, waitlist_data
        )

        # Estimate wait time
        estimated_wait = service.estimate_wait_time(
            waitlist_entry.requested_date,
            waitlist_entry.requested_time_start,
            waitlist_entry.party_size,
        )

        return WaitlistResponse(
            id=waitlist_entry.id,
            customer_id=waitlist_entry.customer_id,
            requested_date=waitlist_entry.requested_date,
            requested_time_start=waitlist_entry.requested_time_start,
            requested_time_end=waitlist_entry.requested_time_end,
            party_size=waitlist_entry.party_size,
            flexible_date=waitlist_entry.flexible_date,
            flexible_time=waitlist_entry.flexible_time,
            alternative_dates=waitlist_entry.alternative_dates,
            status=waitlist_entry.status,
            position=waitlist_entry.position,
            estimated_wait_time=estimated_wait,
            customer_name=f"{current_customer.first_name} {current_customer.last_name}",
            customer_email=current_customer.email,
            customer_phone=current_customer.phone,
            notification_method=waitlist_entry.notification_method,
            notified_at=waitlist_entry.notified_at,
            notification_expires_at=waitlist_entry.notification_expires_at,
            special_requests=waitlist_entry.special_requests,
            priority=waitlist_entry.priority,
            created_at=waitlist_entry.created_at,
            updated_at=waitlist_entry.updated_at,
            expires_at=waitlist_entry.expires_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/my-waitlist", response_model=WaitlistListResponse)
async def get_my_waitlist_entries(
    active_only: bool = Query(True, description="Show only active waitlist entries"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """Get all waitlist entries for the current customer."""
    service = WaitlistService(db)

    skip = (page - 1) * page_size
    entries, total = service.get_customer_waitlist_entries(
        current_customer.id, active_only=active_only, skip=skip, limit=page_size
    )

    # Convert to response models
    waitlist_responses = []
    for entry in entries:
        estimated_wait = service.estimate_wait_time(
            entry.requested_date, entry.requested_time_start, entry.party_size
        )

        waitlist_responses.append(
            WaitlistResponse(
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
                customer_name=f"{current_customer.first_name} {current_customer.last_name}",
                customer_email=current_customer.email,
                customer_phone=current_customer.phone,
                notification_method=entry.notification_method,
                notified_at=entry.notified_at,
                notification_expires_at=entry.notification_expires_at,
                special_requests=entry.special_requests,
                priority=entry.priority,
                created_at=entry.created_at,
                updated_at=entry.updated_at,
                expires_at=entry.expires_at,
            )
        )

    total_pages = (total + page_size - 1) // page_size

    return WaitlistListResponse(
        waitlist_entries=waitlist_responses,
        total=total,
        page=page,
        page_size=page_size,
        has_next=page < total_pages,
        has_previous=page > 1,
    )


@router.get("/{waitlist_id}", response_model=WaitlistResponse)
async def get_waitlist_entry(
    waitlist_id: int,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """Get a specific waitlist entry."""
    service = WaitlistService(db)

    # Get the entry
    from ..models.reservation_models import Waitlist

    entry = (
        db.query(Waitlist)
        .filter(Waitlist.id == waitlist_id, Waitlist.customer_id == current_customer.id)
        .first()
    )

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waitlist entry not found"
        )

    estimated_wait = service.estimate_wait_time(
        entry.requested_date, entry.requested_time_start, entry.party_size
    )

    return WaitlistResponse(
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
        customer_name=f"{current_customer.first_name} {current_customer.last_name}",
        customer_email=current_customer.email,
        customer_phone=current_customer.phone,
        notification_method=entry.notification_method,
        notified_at=entry.notified_at,
        notification_expires_at=entry.notification_expires_at,
        special_requests=entry.special_requests,
        priority=entry.priority,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        expires_at=entry.expires_at,
    )


@router.post("/{waitlist_id}/confirm", response_model=ReservationResponse)
async def confirm_waitlist_availability(
    waitlist_id: int,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """
    Confirm availability notification and convert waitlist to reservation.

    Must be called within the notification window after being notified.
    """
    service = WaitlistService(db)

    try:
        reservation = await service.confirm_waitlist_availability(
            waitlist_id, current_customer.id
        )

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
            customer_name=f"{current_customer.first_name} {current_customer.last_name}",
            customer_email=current_customer.email,
            customer_phone=current_customer.phone,
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
            cancelled_by=reservation.cancelled_by,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{waitlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_waitlist_entry(
    waitlist_id: int,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """
    Cancel a waitlist entry.

    - Updates positions for remaining entries
    - Cannot cancel if already converted or cancelled
    """
    service = WaitlistService(db)

    try:
        service.cancel_waitlist_entry(waitlist_id, current_customer.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/estimate/{date}", response_model=dict)
async def estimate_wait_time(
    date: date,
    time_start: str = Query(..., pattern="^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"),
    party_size: int = Query(..., ge=1, le=20),
    db: Session = Depends(get_db),
):
    """
    Estimate wait time for a potential waitlist entry.

    Helps customers decide if they want to join the waitlist.
    """
    service = WaitlistService(db)

    # Parse time
    from datetime import datetime

    time_obj = datetime.strptime(time_start, "%H:%M").time()

    estimated_minutes = service.estimate_wait_time(date, time_obj, party_size)

    return {
        "date": date,
        "time": time_start,
        "party_size": party_size,
        "estimated_wait_minutes": estimated_minutes,
        "estimated_wait_text": (
            f"{estimated_minutes} minutes" if estimated_minutes else "No wait"
        ),
    }
