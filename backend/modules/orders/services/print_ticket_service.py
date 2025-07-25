from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional
from datetime import datetime
import json
from ..schemas.print_ticket_schemas import (
    PrintTicketRequest, PrintTicketResponse, PrintQueueStatus,
    PrintTicketStatusUpdate, PrintQueueItem
)
from ..enums.order_enums import PrintStatus, TicketType
from ..models.order_models import PrintTicket, PrintStation
from ..services.order_service import get_order_by_id


async def generate_print_ticket(
    request: PrintTicketRequest, db: Session
) -> PrintTicketResponse:
    order = await get_order_by_id(db, request.order_id)

    ticket_content = await _format_ticket_content(order, request.ticket_type)

    station_id = request.station_id or await _route_to_station(
        order, request.ticket_type, db
    )

    ticket_data = {
        "order_id": request.order_id,
        "ticket_type": request.ticket_type.value,
        "status": PrintStatus.PENDING.value,
        "station_id": station_id,
        "priority": request.priority,
        "ticket_content": ticket_content,
        "retry_count": 0
    }

    ticket = await _add_to_print_queue(ticket_data, db)

    return PrintTicketResponse(
        id=ticket.id,
        order_id=ticket.order_id,
        ticket_type=TicketType(ticket.ticket_type),
        status=PrintStatus(ticket.status),
        station_id=ticket.station_id,
        priority=ticket.priority,
        ticket_content=ticket.ticket_content,
        created_at=ticket.created_at,
        printed_at=ticket.printed_at,
        failed_at=ticket.failed_at,
        error_message=ticket.error_message
    )


async def get_print_queue(db: Session) -> PrintQueueStatus:
    queue_items = await _get_queue_items(db)

    total_items = len(queue_items)
    pending_items = len([item for item in queue_items
                        if item.status == PrintStatus.PENDING])
    printing_items = len([item for item in queue_items
                         if item.status == PrintStatus.PRINTING])
    failed_items = len([item for item in queue_items
                       if item.status == PrintStatus.FAILED])

    return PrintQueueStatus(
        total_items=total_items,
        pending_items=pending_items,
        printing_items=printing_items,
        failed_items=failed_items,
        queue_items=queue_items
    )


async def update_print_ticket_status(
    ticket_id: int, status_update: PrintTicketStatusUpdate, db: Session
) -> PrintTicketResponse:
    ticket = await _get_ticket_by_id(ticket_id, db)

    if not ticket:
        raise HTTPException(
            status_code=404,
            detail=f"Print ticket with id {ticket_id} not found"
        )

    ticket.status = status_update.status.value
    if status_update.status == PrintStatus.PRINTED:
        ticket.printed_at = datetime.utcnow()
    elif status_update.status == PrintStatus.FAILED:
        ticket.failed_at = datetime.utcnow()
        ticket.error_message = status_update.error_message
        ticket.retry_count = ticket.retry_count + 1

    await _update_ticket_in_db(ticket, db)

    return PrintTicketResponse(
        id=ticket.id,
        order_id=ticket.order_id,
        ticket_type=TicketType(ticket.ticket_type),
        status=PrintStatus(ticket.status),
        station_id=ticket.station_id,
        priority=ticket.priority,
        ticket_content=ticket.ticket_content,
        created_at=ticket.created_at,
        printed_at=ticket.printed_at,
        failed_at=ticket.failed_at,
        error_message=ticket.error_message
    )


async def retry_failed_tickets(
    db: Session, max_retries: int = 3
) -> List[PrintTicketResponse]:
    failed_tickets = await _get_failed_tickets(db, max_retries)
    retried_tickets = []

    for ticket in failed_tickets:
        ticket.status = PrintStatus.PENDING.value
        ticket.error_message = None
        await _update_ticket_in_db(ticket, db)
        
        retried_tickets.append(PrintTicketResponse(
            id=ticket.id,
            order_id=ticket.order_id,
            ticket_type=TicketType(ticket.ticket_type),
            status=PrintStatus(ticket.status),
            station_id=ticket.station_id,
            priority=ticket.priority,
            ticket_content=ticket.ticket_content,
            created_at=ticket.created_at,
            printed_at=ticket.printed_at,
            failed_at=ticket.failed_at,
            error_message=ticket.error_message
        ))

    return retried_tickets


async def _format_ticket_content(order, ticket_type: TicketType) -> str:
    content = f"ORDER #{order.id}\n"
    content += f"Table: {order.table_no or 'N/A'}\n"
    content += f"Type: {ticket_type.value.upper()}\n"
    content += "=" * 30 + "\n"

    for item in order.order_items:
        content += f"{item.quantity}x Item #{item.menu_item_id}\n"
        if item.notes:
            content += f"  Notes: {item.notes}\n"

    content += "=" * 30 + "\n"
    content += f"Time: {datetime.utcnow().strftime('%H:%M:%S')}\n"

    return content


async def _route_to_station(
    order, ticket_type: TicketType, db: Session
) -> Optional[int]:
    stations = db.query(PrintStation).filter(
        PrintStation.is_active == True
    ).all()
    
    for station in stations:
        try:
            supported_types = json.loads(station.ticket_types)
            if ticket_type.value in supported_types:
                return station.id
        except (json.JSONDecodeError, TypeError):
            continue
    
    station_mapping = {
        TicketType.KITCHEN: 1,
        TicketType.BAR: 2,
        TicketType.GRILL: 3,
        TicketType.COLD_PREP: 4,
        TicketType.HOT_PREP: 5
    }
    return station_mapping.get(ticket_type)


async def _add_to_print_queue(ticket_data: dict, db: Session) -> PrintTicket:
    ticket = PrintTicket(**ticket_data)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


async def _get_queue_items(db: Session) -> List[PrintQueueItem]:
    tickets = db.query(PrintTicket).filter(
        PrintTicket.status.in_([
            PrintStatus.PENDING.value,
            PrintStatus.PRINTING.value,
            PrintStatus.FAILED.value
        ])
    ).order_by(PrintTicket.priority.desc(), PrintTicket.created_at.asc()).all()
    
    return [PrintQueueItem(
        id=ticket.id,
        order_id=ticket.order_id,
        ticket_type=TicketType(ticket.ticket_type),
        status=PrintStatus(ticket.status),
        station_id=ticket.station_id,
        priority=ticket.priority,
        created_at=ticket.created_at,
        retry_count=ticket.retry_count
    ) for ticket in tickets]


async def _get_ticket_by_id(ticket_id: int, db: Session) -> Optional[PrintTicket]:
    return db.query(PrintTicket).filter(PrintTicket.id == ticket_id).first()


async def _update_ticket_in_db(ticket: PrintTicket, db: Session):
    db.commit()
    db.refresh(ticket)


async def _get_failed_tickets(db: Session, max_retries: int) -> List[PrintTicket]:
    return db.query(PrintTicket).filter(
        PrintTicket.status == PrintStatus.FAILED.value,
        PrintTicket.retry_count < max_retries
    ).all()
