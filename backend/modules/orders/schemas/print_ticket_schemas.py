from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from ..enums.order_enums import PrintStatus, TicketType


class PrintTicketRequest(BaseModel):
    order_id: int
    ticket_type: TicketType
    station_id: Optional[int] = None
    priority: int = Field(default=1, ge=1, le=10)


class PrintTicketResponse(BaseModel):
    id: int
    order_id: int
    ticket_type: TicketType
    status: PrintStatus
    station_id: Optional[int] = None
    priority: int
    ticket_content: str
    created_at: datetime
    printed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class PrintQueueItem(BaseModel):
    id: int
    order_id: int
    ticket_type: TicketType
    status: PrintStatus
    station_id: Optional[int] = None
    priority: int
    created_at: datetime
    retry_count: int = 0

    class Config:
        from_attributes = True


class PrintQueueStatus(BaseModel):
    total_items: int
    pending_items: int
    printing_items: int
    failed_items: int
    queue_items: List[PrintQueueItem]


class PrintTicketStatusUpdate(BaseModel):
    status: PrintStatus
    error_message: Optional[str] = None
