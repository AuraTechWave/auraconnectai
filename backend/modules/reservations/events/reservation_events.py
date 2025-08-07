# backend/modules/reservations/events/reservation_events.py

"""
Event system for reservation lifecycle hooks.
"""

from typing import Dict, Any, List, Callable, Optional
from datetime import datetime
from dataclasses import dataclass, field
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass
class ReservationEvent:
    """Base reservation event"""
    event_type: str
    reservation_id: int
    customer_id: int
    timestamp: datetime
    user_id: Optional[int] = None  # Who triggered the event
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        return {
            "event_type": self.event_type,
            "reservation_id": self.reservation_id,
            "customer_id": self.customer_id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "metadata": self.metadata or {}
        }


@dataclass
class ReservationCreatedEvent(ReservationEvent):
    """Emitted when reservation is created"""
    party_size: Optional[int] = None
    reservation_date: Optional[str] = None
    reservation_time: Optional[str] = None
    source: Optional[str] = None
    
    def __post_init__(self):
        if not hasattr(self, 'event_type') or self.event_type is None:
            self.event_type = "reservation.created"


@dataclass
class ReservationUpdatedEvent(ReservationEvent):
    """Emitted when reservation is updated"""
    changes: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if not hasattr(self, 'event_type') or self.event_type is None:
            self.event_type = "reservation.updated"


@dataclass
class ReservationCancelledEvent(ReservationEvent):
    """Emitted when reservation is cancelled"""
    reason: Optional[str] = None
    cancelled_by: Optional[str] = None
    
    def __post_init__(self):
        if not hasattr(self, 'event_type') or self.event_type is None:
            self.event_type = "reservation.cancelled"


@dataclass
class ReservationPromotedEvent(ReservationEvent):
    """Emitted when reservation is promoted from waitlist"""
    waitlist_id: Optional[int] = None
    original_position: Optional[int] = None
    
    def __post_init__(self):
        if not hasattr(self, 'event_type') or self.event_type is None:
            self.event_type = "reservation.promoted"


@dataclass
class ReservationSeatedEvent(ReservationEvent):
    """Emitted when guests are seated"""
    table_numbers: Optional[str] = None
    seated_by: Optional[int] = None
    
    def __post_init__(self):
        if not hasattr(self, 'event_type') or self.event_type is None:
            self.event_type = "reservation.seated"


@dataclass
class ReservationCompletedEvent(ReservationEvent):
    """Emitted when reservation is completed"""
    duration_minutes: Optional[int] = None
    
    def __post_init__(self):
        if not hasattr(self, 'event_type') or self.event_type is None:
            self.event_type = "reservation.completed"


@dataclass
class ReservationNoShowEvent(ReservationEvent):
    """Emitted when reservation is marked as no-show"""
    marked_by: Optional[int] = None
    
    def __post_init__(self):
        if not hasattr(self, 'event_type') or self.event_type is None:
            self.event_type = "reservation.no_show"


@dataclass
class WaitlistCreatedEvent(ReservationEvent):
    """Emitted when added to waitlist"""
    position: Optional[int] = None
    requested_date: Optional[str] = None
    party_size: Optional[int] = None
    
    def __post_init__(self):
        if not hasattr(self, 'event_type') or self.event_type is None:
            self.event_type = "waitlist.created"


@dataclass
class WaitlistNotifiedEvent(ReservationEvent):
    """Emitted when waitlist customer is notified"""
    waitlist_id: Optional[int] = None
    available_time: Optional[str] = None
    expires_at: Optional[str] = None
    
    def __post_init__(self):
        if not hasattr(self, 'event_type') or self.event_type is None:
            self.event_type = "waitlist.notified"


@dataclass
class WaitlistConvertedEvent(ReservationEvent):
    """Emitted when waitlist converts to reservation"""
    waitlist_id: Optional[int] = None
    new_reservation_id: Optional[int] = None
    
    def __post_init__(self):
        if not hasattr(self, 'event_type') or self.event_type is None:
            self.event_type = "waitlist.converted"


# Event handlers registry
reservation_event_handlers: Dict[str, List[Callable]] = {
    "reservation.created": [],
    "reservation.updated": [],
    "reservation.cancelled": [],
    "reservation.promoted": [],
    "reservation.seated": [],
    "reservation.completed": [],
    "reservation.no_show": [],
    "waitlist.created": [],
    "waitlist.notified": [],
    "waitlist.converted": [],
}


def register_event_handler(event_type: str, handler: Callable):
    """Register an event handler for a specific event type"""
    if event_type not in reservation_event_handlers:
        reservation_event_handlers[event_type] = []
    reservation_event_handlers[event_type].append(handler)


async def emit_reservation_event(event: ReservationEvent):
    """Emit a reservation event to all registered handlers"""
    handlers = reservation_event_handlers.get(event.event_type, [])
    
    if not handlers:
        logger.debug(f"No handlers registered for event type: {event.event_type}")
        return
    
    logger.info(f"Emitting event: {event.event_type} for reservation {event.reservation_id}")
    
    for handler in handlers:
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
        except Exception as e:
            logger.error(f"Error in event handler for {event.event_type}: {str(e)}")


def get_event_handlers(event_type: str) -> List[Callable]:
    """Get all handlers for a specific event type"""
    return reservation_event_handlers.get(event_type, [])


def clear_event_handlers(event_type: str):
    """Clear all handlers for a specific event type"""
    if event_type in reservation_event_handlers:
        reservation_event_handlers[event_type] = []


def clear_all_event_handlers():
    """Clear all event handlers"""
    for event_type in reservation_event_handlers:
        reservation_event_handlers[event_type] = []