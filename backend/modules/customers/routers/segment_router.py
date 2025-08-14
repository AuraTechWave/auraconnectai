# backend/modules/customers/routers/segment_router.py
"""API endpoints for managing customer segments.

The router is mounted under the ``/customers/segments`` prefix to keep all
customer-related endpoints grouped together.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import get_current_user, User
from ..schemas.customer_schemas import (
    CustomerSegmentCreate,
    CustomerSegment as CustomerSegmentSchema,
    Customer as CustomerSchema,
)
from ..services.segment_service import CustomerSegmentService

router = APIRouter(prefix="/api/v1/customers/segments", tags=["Customer Segments"])


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=List[CustomerSegmentSchema])
def list_segments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Return all customer segments."""
    service = CustomerSegmentService(db)
    return service.list_segments()


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=CustomerSegmentSchema,
)
def create_segment(
    segment: CustomerSegmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new customer segment and evaluate its membership."""
    service = CustomerSegmentService(db)
    try:
        return service.create_segment(segment)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{segment_id}", response_model=CustomerSegmentSchema)
def get_segment(
    segment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = CustomerSegmentService(db)
    seg = service.get_segment(segment_id)
    if not seg:
        raise HTTPException(status_code=404, detail="Segment not found")
    return seg


@router.put("/{segment_id}", response_model=CustomerSegmentSchema)
def update_segment(
    segment_id: int,
    segment_update: CustomerSegmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an existing segment.

    The same schema is reused for create and update – only provided fields are
    applied.
    """
    service = CustomerSegmentService(db)
    try:
        return service.update_segment(segment_id, segment_update.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_segment(
    segment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = CustomerSegmentService(db)
    try:
        service.delete_segment(segment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Membership helpers
# ---------------------------------------------------------------------------


@router.post("/{segment_id}/evaluate", response_model=CustomerSegmentSchema)
def evaluate_segment(
    segment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger re-evaluation of a *dynamic* segment."""
    service = CustomerSegmentService(db)
    try:
        return service.evaluate_segment(segment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{segment_id}/customers", response_model=List[CustomerSchema])
def list_segment_customers(
    segment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = CustomerSegmentService(db)
    try:
        return service.get_segment_customers(segment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc