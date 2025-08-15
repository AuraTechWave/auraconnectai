# backend/modules/reservations/events/reservation_events.py

"""
Event system for reservation lifecycle hooks.
"""

from typing import Dict, Any, List, Callable, Optional
from datetime import datetime
from dataclasses import dataclass
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
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        return {
            "event_type": self.event_type,
            "reservation_id": self.reservation_id,
            "customer_id": self.customer_id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "metadata": self.metadata or {},
        }


@dataclass
class ReservationCreatedEvent(ReservationEvent):
    """Emitted when reservation is created"""

    event_type: str = "reservation.created"
    party_size: int = None
    reservation_date: str = None
    reservation_time: str = None
    source: str = None


@dataclass
class ReservationUpdatedEvent(ReservationEvent):
    """Emitted when reservation is updated"""

    event_type: str = "reservation.updated"
    changes: Dict[str, Any] = None


@dataclass
class ReservationCancelledEvent(ReservationEvent):
    """Emitted when reservation is cancelled"""

    event_type: str = "reservation.cancelled"
    reason: str = None
    cancelled_by: str = None


@dataclass
class ReservationPromotedEvent(ReservationEvent):
    """Emitted when reservation is promoted from waitlist"""

    event_type: str = "reservation.promoted"
    waitlist_id: int = None
    original_position: int = None


@dataclass
class ReservationSeatedEvent(ReservationEvent):
    """Emitted when guests are seated"""

    event_type: str = "reservation.seated"
    table_numbers: str = None
    seated_by: int = None


@dataclass
class ReservationCompletedEvent(ReservationEvent):
    """Emitted when reservation is completed"""

    event_type: str = "reservation.completed"
    duration_minutes: int = None


@dataclass
class ReservationNoShowEvent(ReservationEvent):
    """Emitted when reservation is marked as no-show"""

    event_type: str = "reservation.no_show"
    marked_by: int = None


@dataclass
class WaitlistCreatedEvent(ReservationEvent):
    """Emitted when added to waitlist"""

    event_type: str = "waitlist.created"
    position: int = None
    requested_date: str = None
    party_size: int = None


@dataclass
class WaitlistNotifiedEvent(ReservationEvent):
    """Emitted when waitlist customer is notified"""

    event_type: str = "waitlist.notified"
    waitlist_id: int = None
    available_time: str = None
    expires_at: str = None


@dataclass
class WaitlistConvertedEvent(ReservationEvent):
    """Emitted when waitlist converts to reservation"""

    event_type: str = "waitlist.converted"
    waitlist_id: int = None
    new_reservation_id: int = None


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
    """Register an event handler"""
    if event_type not in reservation_event_handlers:
        raise ValueError(f"Unknown event type: {event_type}")

    reservation_event_handlers[event_type].append(handler)
    logger.info(f"Registered handler {handler.__name__} for {event_type}")


def unregister_event_handler(event_type: str, handler: Callable):
    """Unregister an event handler"""
    if event_type in reservation_event_handlers:
        reservation_event_handlers[event_type].remove(handler)


async def emit_reservation_event(event: ReservationEvent):
    """Emit a reservation event to all registered handlers"""
    event_type = event.event_type
    handlers = reservation_event_handlers.get(event_type, [])

    if not handlers:
        logger.debug(f"No handlers registered for {event_type}")
        return

    logger.info(f"Emitting {event_type} for reservation {event.reservation_id}")

    # Run handlers concurrently
    tasks = []
    for handler in handlers:
        if asyncio.iscoroutinefunction(handler):
            tasks.append(handler(event))
        else:
            # Wrap sync handlers
            tasks.append(asyncio.create_task(asyncio.to_thread(handler, event)))

    # Wait for all handlers to complete
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    f"Handler {handlers[i].__name__} failed for {event_type}: {result}"
                )


# Example handlers that could be registered


async def log_reservation_event(event: ReservationEvent):
    """Log reservation events for analytics"""
    logger.info(f"Event logged: {event.to_dict()}")


async def send_confirmation_on_creation(event: ReservationCreatedEvent):
    """Send confirmation when reservation is created"""
    if event.event_type == "reservation.created":
        logger.info(f"Would send confirmation for reservation {event.reservation_id}")
        # In production, would call notification service


async def notify_kitchen_on_seating(event: ReservationSeatedEvent):
    """Notify kitchen when guests are seated"""
    if event.event_type == "reservation.seated":
        logger.info(f"Would notify kitchen about table {event.table_numbers}")
        # In production, would send to kitchen display system


async def update_analytics_on_completion(event: ReservationCompletedEvent):
    """Update analytics when reservation completes"""
    if event.event_type == "reservation.completed":
        logger.info(f"Would update analytics for {event.duration_minutes} min dining")
        # In production, would update analytics database


async def check_waitlist_on_cancellation(event: ReservationCancelledEvent):
    """Check waitlist when reservation is cancelled"""
    if event.event_type == "reservation.cancelled":
        logger.info(
            f"Would check waitlist after cancellation of {event.reservation_id}"
        )
        # In production, would trigger waitlist service
