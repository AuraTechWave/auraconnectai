from sqlalchemy.orm import Session
from ..services.print_ticket_service import (
    generate_print_ticket,
    get_print_queue,
    update_print_ticket_status,
    retry_failed_tickets,
)
from ..schemas.print_ticket_schemas import (
    PrintTicketRequest,
    PrintTicketResponse,
    PrintQueueStatus,
    PrintTicketStatusUpdate,
)
from ..enums.order_enums import PrintStatus
from typing import List


async def create_print_ticket(
    request: PrintTicketRequest, db: Session
) -> PrintTicketResponse:
    return await generate_print_ticket(request, db)


async def get_current_print_queue(db: Session) -> PrintQueueStatus:
    return await get_print_queue(db)


async def update_ticket_status(
    ticket_id: int, status_update: PrintTicketStatusUpdate, db: Session
) -> PrintTicketResponse:
    return await update_print_ticket_status(ticket_id, status_update, db)


async def retry_failed_print_jobs(
    db: Session, max_retries: int = 3
) -> List[PrintTicketResponse]:
    return await retry_failed_tickets(db, max_retries)


async def handle_print_job_error(
    ticket_id: int, error_message: str, db: Session
) -> PrintTicketResponse:
    status_update = PrintTicketStatusUpdate(
        status=PrintStatus.FAILED, error_message=error_message
    )
    return await update_ticket_status(ticket_id, status_update, db)
