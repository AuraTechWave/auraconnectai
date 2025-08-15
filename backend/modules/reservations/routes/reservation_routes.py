# backend/modules/reservations/routes/reservation_routes.py

"""
Customer-facing reservation API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from core.database import get_db
from modules.customers.auth.customer_auth import get_current_customer
from modules.customers.models.customer_models import Customer
from ..services import ReservationService, AvailabilityService
from ..schemas import (
    ReservationCreate,
    ReservationUpdate,
    ReservationResponse,
    ReservationListResponse,
    ReservationAvailability,
    ReservationCancellation,
    ReservationConfirmation,
    TimeSlot,
    ReservationStatus,
)

router = APIRouter()


@router.post(
    "/", response_model=ReservationResponse, status_code=status.HTTP_201_CREATED
)
async def create_reservation(
    reservation_data: ReservationCreate,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """
    Create a new reservation for the current customer.

    - Validates availability
    - Assigns tables automatically
    - Sends confirmation notification
    """
    service = ReservationService(db)

    try:
        reservation = await service.create_reservation(
            current_customer.id, reservation_data
        )

        # Get customer info for response
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create reservation",
        )


@router.get("/my-reservations", response_model=ReservationListResponse)
async def get_my_reservations(
    status: Optional[ReservationStatus] = None,
    upcoming_only: bool = Query(False, description="Show only upcoming reservations"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """Get all reservations for the current customer with pagination."""
    service = ReservationService(db)

    skip = (page - 1) * page_size
    reservations, total = service.get_customer_reservations(
        current_customer.id,
        status=status,
        upcoming_only=upcoming_only,
        skip=skip,
        limit=page_size,
    )

    # Convert to response models
    reservation_responses = []
    for reservation in reservations:
        reservation_responses.append(
            ReservationResponse(
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
        )

    total_pages = (total + page_size - 1) // page_size

    return ReservationListResponse(
        reservations=reservation_responses,
        total=total,
        page=page,
        page_size=page_size,
        has_next=page < total_pages,
        has_previous=page > 1,
    )


@router.get("/availability", response_model=ReservationAvailability)
async def check_availability(
    check_date: date = Query(..., description="Date to check availability"),
    party_size: int = Query(..., ge=1, le=20, description="Number of guests"),
    db: Session = Depends(get_db),
):
    """
    Check available reservation times for a given date and party size.

    Returns time slots with availability status and waitlist information.
    """
    availability_service = AvailabilityService(db)

    # Get time slots
    time_slots_data = availability_service.get_time_slots(check_date, party_size)

    # Convert to TimeSlot objects
    time_slots = [
        TimeSlot(
            time=slot["time"],
            available=slot["available"],
            capacity_remaining=slot["capacity_remaining"],
            waitlist_count=slot["waitlist_count"],
        )
        for slot in time_slots_data
    ]

    # Check if fully booked
    is_fully_booked = all(not slot.available for slot in time_slots)

    # Get special date info if any
    special_date_info = None
    from ..models.reservation_models import SpecialDate

    special_date = db.query(SpecialDate).filter_by(date=check_date).first()
    if special_date:
        special_date_info = {
            "name": special_date.name,
            "special_menu": special_date.special_menu,
            "require_deposit": special_date.require_deposit,
            "deposit_amount": special_date.deposit_amount,
        }

    # Get available tables for first available slot (for display)
    available_tables = []
    if time_slots and any(slot.available for slot in time_slots):
        first_available = next(slot for slot in time_slots if slot.available)
        tables = await availability_service.get_available_tables(
            check_date, first_available.time, 90, party_size  # Default duration
        )

        from ..schemas import TableAvailability

        available_tables = [
            TableAvailability(
                table_number=table.table_number,
                section=table.section,
                capacity=table.max_capacity,
                features=table.features or [],
                is_available=True,
            )
            for table in tables
        ]

    return ReservationAvailability(
        date=check_date,
        party_size=party_size,
        time_slots=time_slots,
        available_tables=available_tables,
        is_fully_booked=is_fully_booked,
        waitlist_available=True,  # Always allow waitlist
        special_date_info=special_date_info,
    )


@router.get("/{reservation_id}", response_model=ReservationResponse)
async def get_reservation(
    reservation_id: int,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """Get a specific reservation by ID."""
    service = ReservationService(db)

    reservation = service.get_reservation(reservation_id, current_customer.id)
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found"
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


@router.get("/confirm/{confirmation_code}", response_model=ReservationResponse)
async def get_reservation_by_code(
    confirmation_code: str, db: Session = Depends(get_db)
):
    """
    Get a reservation by confirmation code (no authentication required).

    Useful for sharing reservation details or quick lookups.
    """
    service = ReservationService(db)

    reservation = service.get_reservation_by_confirmation_code(confirmation_code)
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found"
        )

    # Get customer info
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
        cancelled_by=reservation.cancelled_by,
    )


@router.put("/{reservation_id}", response_model=ReservationResponse)
async def update_reservation(
    reservation_id: int,
    update_data: ReservationUpdate,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """
    Update a reservation.

    - Can modify date, time, party size, or preferences
    - Automatically re-checks availability and reassigns tables if needed
    """
    service = ReservationService(db)

    try:
        reservation = await service.update_reservation(
            reservation_id, current_customer.id, update_data
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


@router.post("/{reservation_id}/cancel", response_model=ReservationResponse)
async def cancel_reservation(
    reservation_id: int,
    cancellation_data: ReservationCancellation,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """
    Cancel a reservation.

    - Updates status to cancelled
    - Sends cancellation notification
    - Checks waitlist for available slots
    """
    service = ReservationService(db)

    try:
        reservation = await service.cancel_reservation(
            reservation_id, current_customer.id, cancellation_data
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


@router.post("/{reservation_id}/confirm", response_model=ReservationResponse)
async def confirm_reservation(
    reservation_id: int,
    confirmation_data: ReservationConfirmation,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """
    Confirm a pending reservation.

    Some restaurants require confirmation 24-48 hours before the reservation.
    """
    service = ReservationService(db)

    try:
        reservation = await service.confirm_reservation(
            reservation_id, current_customer.id, confirmation_data
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
