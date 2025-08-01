from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from backend.core.database import get_db
from backend.modules.customers.auth.customer_auth import get_current_customer
from backend.modules.customers.models.customer_models import Customer
from app.models.reservation import Reservation
from app.services.reservation_service import ReservationService
from app.schemas.reservation import (
    ReservationCreate,
    ReservationUpdate,
    ReservationResponse,
    ReservationListResponse,
    ReservationAvailability,
    ReservationCancellation,
    ReservationStatus
)

router = APIRouter()


@router.post("/", response_model=ReservationResponse)
def create_reservation(
    reservation_data: ReservationCreate,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """Create a new reservation for the current customer"""
    service = ReservationService(db)
    
    try:
        reservation = service.create_reservation(current_customer.id, reservation_data)
        
        # Convert to response model
        return ReservationResponse(
            id=reservation.id,
            customer_id=reservation.customer_id,
            reservation_date=reservation.reservation_date,
            reservation_time=reservation.reservation_time,
            party_size=reservation.party_size,
            special_requests=reservation.special_requests,
            status=reservation.status.value,
            table_number=reservation.table_number,
            confirmation_code=reservation.confirmation_code,
            created_at=reservation.created_at,
            updated_at=reservation.updated_at,
            customer_name=f"{current_customer.first_name} {current_customer.last_name}",
            customer_email=current_customer.email,
            customer_phone=current_customer.phone
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/my-reservations", response_model=ReservationListResponse)
def get_my_reservations(
    status: Optional[ReservationStatus] = None,
    upcoming_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """Get all reservations for the current customer"""
    service = ReservationService(db)
    
    skip = (page - 1) * page_size
    reservations = service.get_customer_reservations(
        current_customer.id,
        status=status,
        upcoming_only=upcoming_only,
        skip=skip,
        limit=page_size
    )
    
    # Get total count
    total_query = db.query(Reservation).filter_by(customer_id=current_customer.id)
    if status:
        total_query = total_query.filter_by(status=status)
    total = total_query.count()
    
    # Convert to response models
    reservation_responses = []
    for reservation in reservations:
        reservation_responses.append(ReservationResponse(
            id=reservation.id,
            customer_id=reservation.customer_id,
            reservation_date=reservation.reservation_date,
            reservation_time=reservation.reservation_time,
            party_size=reservation.party_size,
            special_requests=reservation.special_requests,
            status=reservation.status.value,
            table_number=reservation.table_number,
            confirmation_code=reservation.confirmation_code,
            created_at=reservation.created_at,
            updated_at=reservation.updated_at,
            customer_name=f"{current_customer.first_name} {current_customer.last_name}",
            customer_email=current_customer.email,
            customer_phone=current_customer.phone
        ))
    
    return ReservationListResponse(
        reservations=reservation_responses,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/availability", response_model=ReservationAvailability)
def check_availability(
    date: date,
    party_size: int = Query(..., ge=1, le=20),
    db: Session = Depends(get_db)
):
    """Check available reservation times for a given date and party size"""
    service = ReservationService(db)
    
    available_times = service.get_available_times(date, party_size)
    
    return ReservationAvailability(
        date=date,
        available_times=available_times,
        is_fully_booked=len(available_times) == 0
    )


@router.get("/{reservation_id}", response_model=ReservationResponse)
def get_reservation(
    reservation_id: int,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """Get a specific reservation"""
    service = ReservationService(db)
    
    reservation = service.get_reservation(reservation_id, current_customer.id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    
    return ReservationResponse(
        id=reservation.id,
        customer_id=reservation.customer_id,
        reservation_date=reservation.reservation_date,
        reservation_time=reservation.reservation_time,
        party_size=reservation.party_size,
        special_requests=reservation.special_requests,
        status=reservation.status.value,
        table_number=reservation.table_number,
        confirmation_code=reservation.confirmation_code,
        created_at=reservation.created_at,
        updated_at=reservation.updated_at,
        customer_name=f"{current_customer.first_name} {current_customer.last_name}",
        customer_email=current_customer.email,
        customer_phone=current_customer.phone
    )


@router.get("/confirm/{confirmation_code}", response_model=ReservationResponse)
def get_reservation_by_code(
    confirmation_code: str,
    db: Session = Depends(get_db)
):
    """Get a reservation by confirmation code (no auth required)"""
    service = ReservationService(db)
    
    reservation = service.get_reservation_by_confirmation_code(confirmation_code)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    
    # Get customer info
    customer = reservation.customer
    
    return ReservationResponse(
        id=reservation.id,
        customer_id=reservation.customer_id,
        reservation_date=reservation.reservation_date,
        reservation_time=reservation.reservation_time,
        party_size=reservation.party_size,
        special_requests=reservation.special_requests,
        status=reservation.status.value,
        table_number=reservation.table_number,
        confirmation_code=reservation.confirmation_code,
        created_at=reservation.created_at,
        updated_at=reservation.updated_at,
        customer_name=f"{customer.first_name} {customer.last_name}",
        customer_email=customer.email,
        customer_phone=customer.phone
    )


@router.put("/{reservation_id}", response_model=ReservationResponse)
def update_reservation(
    reservation_id: int,
    update_data: ReservationUpdate,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """Update a reservation"""
    service = ReservationService(db)
    
    try:
        reservation = service.update_reservation(reservation_id, current_customer.id, update_data)
        if not reservation:
            raise HTTPException(status_code=404, detail="Reservation not found")
        
        return ReservationResponse(
            id=reservation.id,
            customer_id=reservation.customer_id,
            reservation_date=reservation.reservation_date,
            reservation_time=reservation.reservation_time,
            party_size=reservation.party_size,
            special_requests=reservation.special_requests,
            status=reservation.status.value,
            table_number=reservation.table_number,
            confirmation_code=reservation.confirmation_code,
            created_at=reservation.created_at,
            updated_at=reservation.updated_at,
            customer_name=f"{current_customer.first_name} {current_customer.last_name}",
            customer_email=current_customer.email,
            customer_phone=current_customer.phone
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{reservation_id}/cancel", response_model=ReservationResponse)
def cancel_reservation(
    reservation_id: int,
    cancellation_data: ReservationCancellation,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """Cancel a reservation"""
    service = ReservationService(db)
    
    try:
        reservation = service.cancel_reservation(reservation_id, current_customer.id, cancellation_data)
        if not reservation:
            raise HTTPException(status_code=404, detail="Reservation not found")
        
        return ReservationResponse(
            id=reservation.id,
            customer_id=reservation.customer_id,
            reservation_date=reservation.reservation_date,
            reservation_time=reservation.reservation_time,
            party_size=reservation.party_size,
            special_requests=reservation.special_requests,
            status=reservation.status.value,
            table_number=reservation.table_number,
            confirmation_code=reservation.confirmation_code,
            created_at=reservation.created_at,
            updated_at=reservation.updated_at,
            customer_name=f"{current_customer.first_name} {current_customer.last_name}",
            customer_email=current_customer.email,
            customer_phone=current_customer.phone
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Staff endpoints (would typically be in a separate staff API)
@router.post("/{reservation_id}/confirm", response_model=ReservationResponse, tags=["staff"])
def confirm_reservation_staff(
    reservation_id: int,
    db: Session = Depends(get_db)
    # Add staff authentication dependency here
):
    """Confirm a pending reservation (staff only)"""
    service = ReservationService(db)
    
    try:
        reservation = service.confirm_reservation(reservation_id)
        if not reservation:
            raise HTTPException(status_code=404, detail="Reservation not found")
        
        customer = reservation.customer
        
        return ReservationResponse(
            id=reservation.id,
            customer_id=reservation.customer_id,
            reservation_date=reservation.reservation_date,
            reservation_time=reservation.reservation_time,
            party_size=reservation.party_size,
            special_requests=reservation.special_requests,
            status=reservation.status.value,
            table_number=reservation.table_number,
            confirmation_code=reservation.confirmation_code,
            created_at=reservation.created_at,
            updated_at=reservation.updated_at,
            customer_name=f"{customer.first_name} {customer.last_name}",
            customer_email=customer.email,
            customer_phone=customer.phone
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))