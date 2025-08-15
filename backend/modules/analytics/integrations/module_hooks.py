# backend/modules/analytics/integrations/module_hooks.py

"""
Integration hooks for other modules to trigger real-time analytics updates.

This module provides simple functions that other modules can call to notify
the analytics system of events that should trigger real-time metrics updates.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from decimal import Decimal

from ..services.event_processor import event_processor
from ..services.realtime_metrics_service import realtime_metrics_service
from ..services.websocket_manager import websocket_manager
from ..schemas.realtime_schemas import (
    OrderCompletedEvent,
    StaffActionEvent,
    SystemEvent,
    AlertSeverity,
)

logger = logging.getLogger(__name__)


# Order-related hooks


async def order_completed_hook(
    order_id: int,
    staff_id: int,
    customer_id: Optional[int],
    total_amount: Decimal,
    items_count: int,
    table_no: Optional[int] = None,
    completed_at: Optional[datetime] = None,
):
    """
    Hook to be called when an order is completed.

    This should be called from the orders module when an order status
    changes to 'completed' to trigger real-time metrics updates.

    Args:
        order_id: ID of the completed order
        staff_id: ID of the staff member who processed the order
        customer_id: ID of the customer (if available)
        total_amount: Total amount of the order
        items_count: Number of items in the order
        table_no: Table number (if applicable)
        completed_at: Completion timestamp (defaults to now)
    """
    try:
        event = OrderCompletedEvent(
            order_id=order_id,
            staff_id=staff_id,
            customer_id=customer_id,
            total_amount=total_amount,
            items_count=items_count,
            completed_at=completed_at or datetime.now(),
            table_no=table_no,
        )

        await event_processor.process_order_completed(event)
        logger.info(
            f"Order completed event processed: order_id={order_id}, amount=${total_amount}"
        )

    except Exception as e:
        logger.error(f"Error processing order completed hook: {e}")


def order_completed_sync(
    order_id: int,
    staff_id: int,
    customer_id: Optional[int],
    total_amount: Decimal,
    items_count: int,
    table_no: Optional[int] = None,
    completed_at: Optional[datetime] = None,
):
    """
    Synchronous version of order_completed_hook for non-async contexts.

    This creates an async task to handle the event processing.
    """
    try:
        asyncio.create_task(
            order_completed_hook(
                order_id=order_id,
                staff_id=staff_id,
                customer_id=customer_id,
                total_amount=total_amount,
                items_count=items_count,
                table_no=table_no,
                completed_at=completed_at,
            )
        )
    except Exception as e:
        logger.error(f"Error creating order completed task: {e}")


async def order_cancelled_hook(
    order_id: int, staff_id: int, reason: str, cancelled_at: Optional[datetime] = None
):
    """
    Hook to be called when an order is cancelled.

    Args:
        order_id: ID of the cancelled order
        staff_id: ID of the staff member who cancelled the order
        reason: Reason for cancellation
        cancelled_at: Cancellation timestamp (defaults to now)
    """
    try:
        await event_processor.process_event(
            event_processor.EventType.ORDER_CANCELLED,
            {
                "order_id": order_id,
                "staff_id": staff_id,
                "reason": reason,
                "cancelled_at": cancelled_at or datetime.now(),
            },
            priority=True,
        )

        logger.info(f"Order cancelled event processed: order_id={order_id}")

    except Exception as e:
        logger.error(f"Error processing order cancelled hook: {e}")


# Staff-related hooks


async def staff_action_hook(
    staff_id: int,
    action_type: str,
    action_data: Optional[Dict[str, Any]] = None,
    shift_id: Optional[int] = None,
    timestamp: Optional[datetime] = None,
):
    """
    Hook to be called when staff members perform significant actions.

    Args:
        staff_id: ID of the staff member
        action_type: Type of action (e.g., "order_processed", "shift_started")
        action_data: Additional data about the action
        shift_id: Current shift ID (if applicable)
        timestamp: Action timestamp (defaults to now)
    """
    try:
        event = StaffActionEvent(
            staff_id=staff_id,
            action_type=action_type,
            action_data=action_data or {},
            shift_id=shift_id,
            timestamp=timestamp or datetime.now(),
        )

        await event_processor.process_staff_action(event)
        logger.debug(
            f"Staff action event processed: staff_id={staff_id}, action={action_type}"
        )

    except Exception as e:
        logger.error(f"Error processing staff action hook: {e}")


def staff_action_sync(
    staff_id: int,
    action_type: str,
    action_data: Optional[Dict[str, Any]] = None,
    shift_id: Optional[int] = None,
    timestamp: Optional[datetime] = None,
):
    """
    Synchronous version of staff_action_hook.
    """
    try:
        asyncio.create_task(
            staff_action_hook(
                staff_id=staff_id,
                action_type=action_type,
                action_data=action_data,
                shift_id=shift_id,
                timestamp=timestamp,
            )
        )
    except Exception as e:
        logger.error(f"Error creating staff action task: {e}")


# Customer-related hooks


async def customer_action_hook(
    customer_id: int,
    action_type: str,
    action_data: Optional[Dict[str, Any]] = None,
    timestamp: Optional[datetime] = None,
):
    """
    Hook to be called for customer actions (new customer, loyalty points, etc.).

    Args:
        customer_id: ID of the customer
        action_type: Type of action (e.g., "new_customer", "loyalty_earned")
        action_data: Additional data about the action
        timestamp: Action timestamp (defaults to now)
    """
    try:
        await event_processor.process_event(
            event_processor.EventType.CUSTOMER_ACTION,
            {
                "customer_id": customer_id,
                "action_type": action_type,
                "action_data": action_data or {},
                "timestamp": timestamp or datetime.now(),
            },
        )

        logger.debug(
            f"Customer action event processed: customer_id={customer_id}, action={action_type}"
        )

    except Exception as e:
        logger.error(f"Error processing customer action hook: {e}")


# Payment-related hooks


async def payment_processed_hook(
    order_id: int,
    payment_method: str,
    amount: Decimal,
    status: str,
    transaction_id: Optional[str] = None,
    processed_at: Optional[datetime] = None,
):
    """
    Hook to be called when a payment is processed.

    Args:
        order_id: ID of the order being paid
        payment_method: Payment method used
        amount: Payment amount
        status: Payment status (e.g., "success", "failed")
        transaction_id: External transaction ID
        processed_at: Processing timestamp (defaults to now)
    """
    try:
        await event_processor.process_event(
            event_processor.EventType.PAYMENT_PROCESSED,
            {
                "order_id": order_id,
                "payment_method": payment_method,
                "amount": float(amount),
                "status": status,
                "transaction_id": transaction_id,
                "processed_at": processed_at or datetime.now(),
            },
            priority=True if status == "success" else False,
        )

        logger.info(
            f"Payment processed event: order_id={order_id}, amount=${amount}, status={status}"
        )

    except Exception as e:
        logger.error(f"Error processing payment hook: {e}")


# System-related hooks


async def system_event_hook(
    event_type: str,
    message: str,
    severity: str = "low",
    source_service: str = "unknown",
    event_data: Optional[Dict[str, Any]] = None,
    timestamp: Optional[datetime] = None,
):
    """
    Hook for system-wide events that should be tracked in analytics.

    Args:
        event_type: Type of system event
        message: Human-readable message about the event
        severity: Event severity ("low", "medium", "high", "critical")
        source_service: Service that generated the event
        event_data: Additional event data
        timestamp: Event timestamp (defaults to now)
    """
    try:
        event = SystemEvent(
            event_type=event_type,
            event_data={"message": message, **(event_data or {})},
            timestamp=timestamp or datetime.now(),
            source_service=source_service,
            severity=AlertSeverity(severity),
        )

        await event_processor.process_system_event(event)
        logger.info(
            f"System event processed: {event_type} ({severity}) from {source_service}"
        )

    except Exception as e:
        logger.error(f"Error processing system event hook: {e}")


# Cache invalidation hooks


async def invalidate_analytics_cache_hook(cache_pattern: Optional[str] = None):
    """
    Hook to invalidate analytics caches when data changes.

    Args:
        cache_pattern: Specific cache pattern to invalidate (None for all)
    """
    try:
        await realtime_metrics_service.invalidate_cache(cache_pattern)
        logger.info(f"Analytics cache invalidated: {cache_pattern or 'all'}")

    except Exception as e:
        logger.error(f"Error invalidating analytics cache: {e}")


def invalidate_analytics_cache_sync(cache_pattern: Optional[str] = None):
    """
    Synchronous version of cache invalidation hook.
    """
    try:
        asyncio.create_task(invalidate_analytics_cache_hook(cache_pattern))
    except Exception as e:
        logger.error(f"Error creating cache invalidation task: {e}")


# Alert hooks


async def trigger_custom_alert_hook(
    alert_name: str,
    message: str,
    metric_name: str,
    current_value: float,
    threshold_value: float,
    severity: str = "medium",
):
    """
    Hook to trigger custom alerts from other modules.

    Args:
        alert_name: Name of the alert
        message: Alert message
        metric_name: Name of the metric that triggered the alert
        current_value: Current value of the metric
        threshold_value: Threshold that was exceeded
        severity: Alert severity
    """
    try:
        await websocket_manager.broadcast_alert_notification(
            {
                "type": "custom_alert",
                "alert_name": alert_name,
                "message": message,
                "metric_name": metric_name,
                "current_value": current_value,
                "threshold_value": threshold_value,
                "severity": severity,
                "triggered_at": datetime.now().isoformat(),
                "source": "external_module",
            }
        )

        logger.info(f"Custom alert triggered: {alert_name} (severity: {severity})")

    except Exception as e:
        logger.error(f"Error triggering custom alert: {e}")


# Utility functions for module integration


def get_analytics_status() -> Dict[str, Any]:
    """
    Get current analytics system status for health checks.

    Returns:
        Dictionary with system status information
    """
    try:
        from ..services.websocket_manager import websocket_manager

        ws_stats = websocket_manager.get_connection_stats()
        event_metrics = event_processor.get_event_metrics()

        return {
            "status": "healthy",
            "websocket_connections": ws_stats["total_connections"],
            "dashboard_subscribers": ws_stats["dashboard_subscribers"],
            "events_processed": event_metrics["total_events_processed"],
            "events_per_minute": event_metrics["events_per_minute"],
            "failed_events": event_metrics["failed_events"],
            "last_check": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting analytics status: {e}")
        return {
            "status": "error",
            "error": str(e),
            "last_check": datetime.now().isoformat(),
        }


async def force_dashboard_refresh():
    """
    Force a refresh of all dashboard data and broadcast to clients.

    This can be called by other modules when they know significant
    changes have occurred that should be immediately reflected.
    """
    try:
        # Invalidate all caches
        await realtime_metrics_service.invalidate_cache()

        # Get fresh dashboard snapshot
        snapshot = await realtime_metrics_service.get_current_dashboard_snapshot()

        # Broadcast to all connected clients
        await websocket_manager.broadcast_dashboard_update(snapshot)

        logger.info("Dashboard refresh forced and broadcast to clients")

    except Exception as e:
        logger.error(f"Error forcing dashboard refresh: {e}")


def force_dashboard_refresh_sync():
    """
    Synchronous version of force_dashboard_refresh.
    """
    try:
        asyncio.create_task(force_dashboard_refresh())
    except Exception as e:
        logger.error(f"Error creating dashboard refresh task: {e}")


# Example usage documentation
"""
Example usage from other modules:

# In orders module, when an order is completed:
from modules.analytics.integrations.module_hooks import order_completed_sync

def complete_order(order):
    # ... order completion logic ...
    
    # Notify analytics system
    order_completed_sync(
        order_id=order.id,
        staff_id=order.staff_id,
        customer_id=order.customer_id,
        total_amount=order.total_amount,
        items_count=len(order.items)
    )

# In staff module, when staff performs an action:
from modules.analytics.integrations.module_hooks import staff_action_sync

def process_order(staff_id, order_id):
    # ... processing logic ...
    
    # Notify analytics
    staff_action_sync(
        staff_id=staff_id,
        action_type="order_processed",
        action_data={"order_id": order_id}
    )

# In any module, to trigger a system event:
from modules.analytics.integrations.module_hooks import system_event_hook

async def handle_critical_error():
    await system_event_hook(
        event_type="critical_error",
        message="Database connection lost",
        severity="critical",
        source_service="orders_service"
    )

# To check analytics system health:
from modules.analytics.integrations.module_hooks import get_analytics_status

def health_check():
    analytics_status = get_analytics_status()
    return analytics_status["status"] == "healthy"
"""
