# backend/modules/analytics/services/event_processor.py

import asyncio
import logging
import json
from typing import Dict, Any, List, Optional, Callable, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict, deque
import uuid

from ..schemas.realtime_schemas import (
    OrderCompletedEvent,
    StaffActionEvent,
    SystemEvent,
    AlertSeverity,
)
from .realtime_metrics_service import realtime_metrics_service
from .websocket_manager import websocket_manager
from .alerting_service import AlertingService

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of real-time events"""

    ORDER_COMPLETED = "order_completed"
    ORDER_CANCELLED = "order_cancelled"
    STAFF_ACTION = "staff_action"
    CUSTOMER_ACTION = "customer_action"
    SYSTEM_EVENT = "system_event"
    ALERT_TRIGGERED = "alert_triggered"
    PAYMENT_PROCESSED = "payment_processed"
    INVENTORY_UPDATED = "inventory_updated"


@dataclass
class EventMetrics:
    """Metrics for event processing"""

    total_events_processed: int = 0
    events_per_minute: float = 0.0
    average_processing_time_ms: float = 0.0
    failed_events: int = 0
    active_handlers: int = 0
    last_reset: datetime = None


class RealtimeEventProcessor:
    """Service for processing real-time events and triggering metrics updates"""

    def __init__(self):
        self.event_handlers: Dict[EventType, List[Callable]] = defaultdict(list)
        self.event_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self.event_history: deque = deque(maxlen=1000)  # Keep last 1000 events
        self.is_running = False
        self.worker_tasks: List[asyncio.Task] = []
        self.metrics = EventMetrics(last_reset=datetime.now())

        # Rate limiting
        self.rate_limit_window = 60  # seconds
        self.max_events_per_window = 1000
        self.event_counts = defaultdict(int)
        self.rate_limit_reset_time = datetime.now()

        # Event aggregation for batch processing
        self.aggregation_buffer: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.aggregation_interval = 5  # seconds

        # Register default event handlers
        self._register_default_handlers()

    async def start_processor(self, num_workers: int = 3):
        """Start the event processor with worker tasks"""
        if self.is_running:
            return

        self.is_running = True
        logger.info(f"Starting real-time event processor with {num_workers} workers")

        # Start worker tasks
        for i in range(num_workers):
            task = asyncio.create_task(self._event_worker(f"worker-{i}"))
            self.worker_tasks.append(task)

        # Start aggregation task
        aggregation_task = asyncio.create_task(self._aggregation_worker())
        self.worker_tasks.append(aggregation_task)

        # Start metrics collection task
        metrics_task = asyncio.create_task(self._metrics_worker())
        self.worker_tasks.append(metrics_task)

        # Wait for all tasks
        await asyncio.gather(*self.worker_tasks, return_exceptions=True)

    async def stop_processor(self):
        """Stop the event processor"""
        self.is_running = False
        logger.info("Stopping real-time event processor")

        # Cancel all worker tasks
        for task in self.worker_tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        self.worker_tasks.clear()

    def register_event_handler(self, event_type: EventType, handler: Callable):
        """Register an event handler for a specific event type"""
        self.event_handlers[event_type].append(handler)
        self.metrics.active_handlers += 1
        logger.info(f"Registered handler for event type: {event_type.value}")

    def unregister_event_handler(self, event_type: EventType, handler: Callable):
        """Unregister an event handler"""
        if handler in self.event_handlers[event_type]:
            self.event_handlers[event_type].remove(handler)
            self.metrics.active_handlers -= 1
            logger.info(f"Unregistered handler for event type: {event_type.value}")

    async def process_event(
        self, event_type: EventType, event_data: Dict[str, Any], priority: bool = False
    ):
        """Process a real-time event"""

        # Check rate limiting
        if not self._check_rate_limit(event_type):
            logger.warning(f"Rate limit exceeded for event type: {event_type.value}")
            return False

        # Create event record
        event_record = {
            "id": str(uuid.uuid4()),
            "type": event_type.value,
            "data": event_data,
            "timestamp": datetime.now(),
            "priority": priority,
            "processing_time": None,
            "status": "pending",
        }

        try:
            if priority:
                # Process high-priority events immediately
                await self._process_single_event(event_record)
            else:
                # Queue normal events
                await self.event_queue.put(event_record)

            return True

        except asyncio.QueueFull:
            logger.error(f"Event queue full, dropping event: {event_type.value}")
            self.metrics.failed_events += 1
            return False
        except Exception as e:
            logger.error(f"Error processing event {event_type.value}: {e}")
            self.metrics.failed_events += 1
            return False

    async def process_order_completed(self, order_data: OrderCompletedEvent):
        """Process order completed event"""
        await self.process_event(
            EventType.ORDER_COMPLETED,
            order_data.dict(),
            priority=True,  # High priority for revenue-impacting events
        )

    async def process_staff_action(self, action_data: StaffActionEvent):
        """Process staff action event"""
        await self.process_event(
            EventType.STAFF_ACTION, action_data.dict(), priority=False
        )

    async def process_system_event(self, system_data: SystemEvent):
        """Process system event"""
        priority = system_data.severity in [AlertSeverity.HIGH, AlertSeverity.CRITICAL]
        await self.process_event(
            EventType.SYSTEM_EVENT, system_data.dict(), priority=priority
        )

    def get_event_metrics(self) -> Dict[str, Any]:
        """Get event processing metrics"""
        return {
            "total_events_processed": self.metrics.total_events_processed,
            "events_per_minute": self.metrics.events_per_minute,
            "average_processing_time_ms": self.metrics.average_processing_time_ms,
            "failed_events": self.metrics.failed_events,
            "active_handlers": self.metrics.active_handlers,
            "queue_size": self.event_queue.qsize(),
            "queue_max_size": self.event_queue.maxsize,
            "last_reset": (
                self.metrics.last_reset.isoformat() if self.metrics.last_reset else None
            ),
            "is_running": self.is_running,
        }

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent event history"""
        recent_events = list(self.event_history)[-limit:]
        return [
            {
                **event,
                "timestamp": (
                    event["timestamp"].isoformat()
                    if isinstance(event["timestamp"], datetime)
                    else event["timestamp"]
                ),
            }
            for event in recent_events
        ]

    # Private methods

    def _register_default_handlers(self):
        """Register default event handlers"""

        # Order completion handlers
        self.register_event_handler(
            EventType.ORDER_COMPLETED, self._handle_order_completed
        )

        # Staff action handlers
        self.register_event_handler(EventType.STAFF_ACTION, self._handle_staff_action)

        # System event handlers
        self.register_event_handler(EventType.SYSTEM_EVENT, self._handle_system_event)

        # Alert handlers
        self.register_event_handler(
            EventType.ALERT_TRIGGERED, self._handle_alert_triggered
        )

    async def _event_worker(self, worker_name: str):
        """Background worker for processing events"""
        logger.info(f"Event worker {worker_name} started")

        while self.is_running:
            try:
                # Get event from queue with timeout
                event_record = await asyncio.wait_for(
                    self.event_queue.get(), timeout=1.0
                )

                # Process the event
                await self._process_single_event(event_record)

                # Mark task as done
                self.event_queue.task_done()

            except asyncio.TimeoutError:
                # No events to process, continue
                continue
            except Exception as e:
                logger.error(f"Error in event worker {worker_name}: {e}")
                await asyncio.sleep(1)

        logger.info(f"Event worker {worker_name} stopped")

    async def _process_single_event(self, event_record: Dict[str, Any]):
        """Process a single event record"""
        start_time = datetime.now()
        event_type = EventType(event_record["type"])

        try:
            event_record["status"] = "processing"

            # Get handlers for this event type
            handlers = self.event_handlers.get(event_type, [])

            if not handlers:
                logger.warning(
                    f"No handlers registered for event type: {event_type.value}"
                )
                event_record["status"] = "no_handlers"
                return

            # Execute all handlers concurrently
            handler_tasks = []
            for handler in handlers:
                task = asyncio.create_task(
                    self._safe_handler_execution(handler, event_record)
                )
                handler_tasks.append(task)

            # Wait for all handlers to complete
            results = await asyncio.gather(*handler_tasks, return_exceptions=True)

            # Check for handler failures
            failed_handlers = sum(
                1 for result in results if isinstance(result, Exception)
            )
            if failed_handlers > 0:
                logger.warning(
                    f"Event {event_record['id']}: {failed_handlers}/{len(handlers)} handlers failed"
                )

            event_record["status"] = "completed"
            self.metrics.total_events_processed += 1

        except Exception as e:
            logger.error(f"Error processing event {event_record['id']}: {e}")
            event_record["status"] = "failed"
            self.metrics.failed_events += 1

        finally:
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            event_record["processing_time"] = processing_time

            # Update metrics
            self._update_processing_time_metric(processing_time)

            # Add to history
            self.event_history.append(event_record.copy())

    async def _safe_handler_execution(
        self, handler: Callable, event_record: Dict[str, Any]
    ):
        """Safely execute an event handler with error handling"""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event_record)
            else:
                handler(event_record)
        except Exception as e:
            logger.error(f"Handler execution failed: {e}")
            raise

    async def _aggregation_worker(self):
        """Worker for aggregating events for batch processing"""
        logger.info("Event aggregation worker started")

        while self.is_running:
            try:
                # Wait for aggregation interval
                await asyncio.sleep(self.aggregation_interval)

                # Process aggregated events
                if self.aggregation_buffer:
                    await self._process_aggregated_events()

            except Exception as e:
                logger.error(f"Error in aggregation worker: {e}")

        logger.info("Event aggregation worker stopped")

    async def _process_aggregated_events(self):
        """Process aggregated events for batch operations"""

        for event_type, events in self.aggregation_buffer.items():
            if not events:
                continue

            try:
                if event_type == "order_metrics_update":
                    # Batch update order metrics
                    await self._batch_update_order_metrics(events)
                elif event_type == "staff_performance_update":
                    # Batch update staff performance
                    await self._batch_update_staff_performance(events)

                logger.debug(
                    f"Processed {len(events)} aggregated events of type: {event_type}"
                )

            except Exception as e:
                logger.error(f"Error processing aggregated events {event_type}: {e}")

        # Clear aggregation buffer
        self.aggregation_buffer.clear()

    async def _metrics_worker(self):
        """Worker for updating event processing metrics"""
        logger.info("Event metrics worker started")

        last_count = 0
        last_time = datetime.now()

        while self.is_running:
            try:
                await asyncio.sleep(60)  # Update every minute

                current_time = datetime.now()
                current_count = self.metrics.total_events_processed

                # Calculate events per minute
                time_diff = (current_time - last_time).total_seconds() / 60.0
                event_diff = current_count - last_count

                if time_diff > 0:
                    self.metrics.events_per_minute = event_diff / time_diff

                last_count = current_count
                last_time = current_time

                # Reset rate limiting counters if needed
                if (
                    current_time - self.rate_limit_reset_time
                ).total_seconds() >= self.rate_limit_window:
                    self.event_counts.clear()
                    self.rate_limit_reset_time = current_time

            except Exception as e:
                logger.error(f"Error in metrics worker: {e}")

        logger.info("Event metrics worker stopped")

    def _check_rate_limit(self, event_type: EventType) -> bool:
        """Check if event type is within rate limit"""
        current_time = datetime.now()

        # Reset counters if window expired
        if (
            current_time - self.rate_limit_reset_time
        ).total_seconds() >= self.rate_limit_window:
            self.event_counts.clear()
            self.rate_limit_reset_time = current_time

        # Check current count
        current_count = self.event_counts[event_type.value]
        if current_count >= self.max_events_per_window:
            return False

        # Increment counter
        self.event_counts[event_type.value] += 1
        return True

    def _update_processing_time_metric(self, processing_time: float):
        """Update average processing time metric"""
        if self.metrics.average_processing_time_ms == 0:
            self.metrics.average_processing_time_ms = processing_time
        else:
            # Exponential moving average
            alpha = 0.1
            self.metrics.average_processing_time_ms = (
                alpha * processing_time
                + (1 - alpha) * self.metrics.average_processing_time_ms
            )

    # Default event handlers

    async def _handle_order_completed(self, event_record: Dict[str, Any]):
        """Handle order completed event"""
        try:
            order_data = event_record["data"]

            # Invalidate relevant caches
            await realtime_metrics_service.invalidate_cache("dashboard")
            await realtime_metrics_service.invalidate_cache("hourly")

            # Update dashboard metrics
            snapshot = await realtime_metrics_service.get_current_dashboard_snapshot()
            await websocket_manager.broadcast_dashboard_update(snapshot)

            # Add to aggregation buffer for batch processing
            self.aggregation_buffer["order_metrics_update"].append(
                {
                    "order_id": order_data.get("order_id"),
                    "staff_id": order_data.get("staff_id"),
                    "amount": order_data.get("total_amount"),
                    "timestamp": event_record["timestamp"],
                }
            )

            logger.debug(
                f"Processed order completed event: {order_data.get('order_id')}"
            )

        except Exception as e:
            logger.error(f"Error handling order completed event: {e}")
            raise

    async def _handle_staff_action(self, event_record: Dict[str, Any]):
        """Handle staff action event"""
        try:
            action_data = event_record["data"]
            action_type = action_data.get("action_type")

            # Handle specific staff actions
            if action_type in ["order_processed", "customer_served"]:
                # Invalidate performance cache
                await realtime_metrics_service.invalidate_cache("performers")

                # Add to aggregation buffer
                self.aggregation_buffer["staff_performance_update"].append(
                    {
                        "staff_id": action_data.get("staff_id"),
                        "action_type": action_type,
                        "timestamp": event_record["timestamp"],
                    }
                )

            elif action_type in ["shift_started", "shift_ended"]:
                # Update dashboard for staff availability changes
                snapshot = (
                    await realtime_metrics_service.get_current_dashboard_snapshot()
                )
                await websocket_manager.broadcast_dashboard_update(snapshot)

            logger.debug(f"Processed staff action event: {action_type}")

        except Exception as e:
            logger.error(f"Error handling staff action event: {e}")
            raise

    async def _handle_system_event(self, event_record: Dict[str, Any]):
        """Handle system event"""
        try:
            system_data = event_record["data"]
            event_type = system_data.get("event_type")
            severity = system_data.get("severity", "low")

            # Broadcast high-severity system events
            if severity in ["high", "critical"]:
                await websocket_manager.broadcast_alert_notification(
                    {
                        "type": "system_event",
                        "event_type": event_type,
                        "severity": severity,
                        "message": system_data.get("message", "System event occurred"),
                        "timestamp": event_record["timestamp"].isoformat(),
                    }
                )

            logger.debug(f"Processed system event: {event_type} (severity: {severity})")

        except Exception as e:
            logger.error(f"Error handling system event: {e}")
            raise

    async def _handle_alert_triggered(self, event_record: Dict[str, Any]):
        """Handle alert triggered event"""
        try:
            alert_data = event_record["data"]

            # Broadcast alert notification
            await websocket_manager.broadcast_alert_notification(
                {
                    "type": "alert_triggered",
                    "alert_id": alert_data.get("alert_id"),
                    "alert_name": alert_data.get("alert_name"),
                    "severity": alert_data.get("severity", "medium"),
                    "message": alert_data.get("message"),
                    "metric_name": alert_data.get("metric_name"),
                    "current_value": alert_data.get("current_value"),
                    "threshold_value": alert_data.get("threshold_value"),
                    "timestamp": event_record["timestamp"].isoformat(),
                }
            )

            logger.info(f"Processed alert triggered: {alert_data.get('alert_name')}")

        except Exception as e:
            logger.error(f"Error handling alert triggered event: {e}")
            raise

    async def _batch_update_order_metrics(self, events: List[Dict[str, Any]]):
        """Batch update order-related metrics"""
        try:
            # Group events by staff member
            staff_metrics = defaultdict(lambda: {"orders": 0, "revenue": 0})

            for event in events:
                staff_id = event.get("staff_id")
                amount = float(event.get("amount", 0))

                staff_metrics[staff_id]["orders"] += 1
                staff_metrics[staff_id]["revenue"] += amount

            # Update metrics (this would typically involve database updates)
            logger.debug(
                f"Batch updated order metrics for {len(staff_metrics)} staff members"
            )

        except Exception as e:
            logger.error(f"Error in batch order metrics update: {e}")
            raise

    async def _batch_update_staff_performance(self, events: List[Dict[str, Any]]):
        """Batch update staff performance metrics"""
        try:
            # Group events by staff member and action type
            staff_actions = defaultdict(lambda: defaultdict(int))

            for event in events:
                staff_id = event.get("staff_id")
                action_type = event.get("action_type")

                staff_actions[staff_id][action_type] += 1

            # Update performance metrics
            logger.debug(
                f"Batch updated staff performance for {len(staff_actions)} staff members"
            )

        except Exception as e:
            logger.error(f"Error in batch staff performance update: {e}")
            raise


# Global event processor instance
event_processor = RealtimeEventProcessor()


# Utility functions for external use
async def trigger_order_completed(order_data: OrderCompletedEvent):
    """Trigger order completed event"""
    await event_processor.process_order_completed(order_data)


async def trigger_staff_action(action_data: StaffActionEvent):
    """Trigger staff action event"""
    await event_processor.process_staff_action(action_data)


async def trigger_system_event(system_data: SystemEvent):
    """Trigger system event"""
    await event_processor.process_system_event(system_data)


def get_event_metrics() -> Dict[str, Any]:
    """Get current event processing metrics"""
    return event_processor.get_event_metrics()


def get_recent_events(limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent event history"""
    return event_processor.get_recent_events(limit)
