from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.core.database import get_db
from ..controllers.print_ticket_controller import (
    create_print_ticket, get_current_print_queue, update_ticket_status,
    retry_failed_print_jobs
)
from ..schemas.print_ticket_schemas import (
    PrintTicketRequest, PrintTicketResponse, PrintQueueStatus,
    PrintTicketStatusUpdate
)
from typing import List

router = APIRouter(prefix="/kitchen", tags=["Kitchen Print Tickets"])


@router.post("/orders/{order_id}/print-ticket",
             response_model=PrintTicketResponse)
async def generate_print_ticket(
    order_id: int,
    request: PrintTicketRequest,
    db: Session = Depends(get_db)
):
    if request.order_id != order_id:
        raise HTTPException(
            status_code=400,
            detail="Order ID in URL must match order ID in request body"
        )

    return await create_print_ticket(request, db)


@router.get("/print-queue", response_model=PrintQueueStatus)
async def view_print_queue(db: Session = Depends(get_db)):
    return await get_current_print_queue(db)


@router.put("/print-tickets/{ticket_id}/status",
            response_model=PrintTicketResponse)
async def update_print_ticket_status(
    ticket_id: int,
    status_update: PrintTicketStatusUpdate,
    db: Session = Depends(get_db)
):
    return await update_ticket_status(ticket_id, status_update, db)


@router.post("/print-tickets/retry-failed",
             response_model=List[PrintTicketResponse])
async def retry_failed_tickets(
    max_retries: int = 3,
    db: Session = Depends(get_db)
):
    return await retry_failed_print_jobs(db, max_retries)
