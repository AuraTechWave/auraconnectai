# backend/modules/orders/services/order_service_tracking_integration.py

from sqlalchemy.orm import Session
from typing import Optional
import logging

from ..models.order_models import Order
from ..enums.order_enums import OrderStatus
from ..services.order_tracking_service import OrderTrackingService
from ..models.order_tracking_models import TrackingEventType


logger = logging.getLogger(__name__)


def integrate_tracking_with_order_service(order_service_class):
    """
    Decorator to add automatic tracking to order service methods

    This decorator can be applied to the OrderService class to automatically
    track status changes and create tracking events
    """

    # Store original methods
    original_create_order = order_service_class.create_order
    original_update_order_status = order_service_class.update_order_status
    original_cancel_order = order_service_class.cancel_order

    async def create_order_with_tracking(self, *args, **kwargs):
        """Create order with automatic tracking setup"""
        # Call original method
        order = await original_create_order(self, *args, **kwargs)

        try:
            # Create tracking service
            tracking_service = OrderTrackingService(self.db)

            # Enable tracking for the order
            customer_id = kwargs.get("customer_id") or order.customer_id
            customer_email = kwargs.get("customer_email")
            customer_phone = kwargs.get("customer_phone")

            tracking = tracking_service.create_customer_tracking(
                order_id=order.id,
                customer_id=customer_id,
                notification_email=customer_email,
                notification_phone=customer_phone,
                enable_notifications=True,
            )

            # Create initial tracking event
            await tracking_service.create_tracking_event(
                order_id=order.id,
                event_type=TrackingEventType.ORDER_PLACED,
                new_status=order.status,
                description="Order placed successfully",
                triggered_by_type="customer" if customer_id else "system",
                triggered_by_id=customer_id,
            )

            # Add tracking info to order response
            if hasattr(order, "__dict__"):
                order.tracking_code = tracking.tracking_code
                order.tracking_url = f"/track/{tracking.tracking_code}"

            logger.info(f"Order tracking enabled for order {order.id}")

        except Exception as e:
            logger.error(f"Failed to enable tracking for order {order.id}: {e}")
            # Don't fail the order creation if tracking fails

        return order

    async def update_order_status_with_tracking(
        self,
        order_id: int,
        new_status: str,
        user_id: Optional[int] = None,
        reason: Optional[str] = None,
        *args,
        **kwargs,
    ):
        """Update order status with automatic tracking"""
        # Get order before update
        order = self.db.query(Order).filter(Order.id == order_id).first()
        old_status = order.status if order else None

        # Call original method
        result = await original_update_order_status(
            self,
            order_id=order_id,
            new_status=new_status,
            user_id=user_id,
            reason=reason,
            *args,
            **kwargs,
        )

        try:
            if order and old_status != new_status:
                # Create tracking service
                tracking_service = OrderTrackingService(self.db)

                # Track the status change
                await tracking_service.track_order_status_change(
                    order=order,
                    new_status=new_status,
                    user_id=user_id,
                    user_type="staff" if user_id else "system",
                    reason=reason,
                )

                logger.info(
                    f"Tracked status change for order {order_id}: {old_status} -> {new_status}"
                )

        except Exception as e:
            logger.error(f"Failed to track status change for order {order_id}: {e}")

        return result

    async def cancel_order_with_tracking(
        self,
        order_id: int,
        reason: str,
        cancelled_by: Optional[int] = None,
        *args,
        **kwargs,
    ):
        """Cancel order with automatic tracking"""
        # Call original method
        result = await original_cancel_order(
            self,
            order_id=order_id,
            reason=reason,
            cancelled_by=cancelled_by,
            *args,
            **kwargs,
        )

        try:
            # Create tracking service
            tracking_service = OrderTrackingService(self.db)

            # Get order
            order = self.db.query(Order).filter(Order.id == order_id).first()

            if order:
                # Track cancellation
                await tracking_service.create_tracking_event(
                    order_id=order_id,
                    event_type=TrackingEventType.ORDER_CANCELLED,
                    old_status=order.status,
                    new_status=OrderStatus.CANCELLED,
                    description=f"Order cancelled: {reason}",
                    triggered_by_type="staff" if cancelled_by else "system",
                    triggered_by_id=cancelled_by,
                )

                logger.info(f"Tracked cancellation for order {order_id}")

        except Exception as e:
            logger.error(f"Failed to track cancellation for order {order_id}: {e}")

        return result

    # Replace methods
    order_service_class.create_order = create_order_with_tracking
    order_service_class.update_order_status = update_order_status_with_tracking
    order_service_class.cancel_order = cancel_order_with_tracking

    return order_service_class


# Hook functions that can be called from existing order processing
async def on_order_created(db: Session, order: Order, **kwargs):
    """Hook to be called when an order is created"""
    try:
        tracking_service = OrderTrackingService(db)

        # Enable tracking
        tracking = tracking_service.create_customer_tracking(
            order_id=order.id,
            customer_id=order.customer_id,
            notification_email=kwargs.get("customer_email"),
            notification_phone=kwargs.get("customer_phone"),
            enable_notifications=kwargs.get("enable_notifications", True),
        )

        # Create initial event
        await tracking_service.create_tracking_event(
            order_id=order.id,
            event_type=TrackingEventType.ORDER_PLACED,
            new_status=order.status,
            description="Order placed successfully",
        )

        return tracking

    except Exception as e:
        logger.error(f"Failed to setup tracking for order {order.id}: {e}")
        return None


async def on_order_status_changed(
    db: Session,
    order: Order,
    old_status: str,
    new_status: str,
    changed_by: Optional[int] = None,
    reason: Optional[str] = None,
):
    """Hook to be called when order status changes"""
    try:
        tracking_service = OrderTrackingService(db)

        # Track the change
        await tracking_service.track_order_status_change(
            order=order,
            new_status=new_status,
            user_id=changed_by,
            user_type="staff" if changed_by else "system",
            reason=reason,
        )

    except Exception as e:
        logger.error(f"Failed to track status change for order {order.id}: {e}")


async def on_kitchen_update(
    db: Session,
    order_id: int,
    update_type: str,
    message: str,
    updated_by: Optional[int] = None,
):
    """Hook for kitchen display system updates"""
    try:
        tracking_service = OrderTrackingService(db)

        # Map kitchen updates to tracking events
        event_type_map = {
            "started": TrackingEventType.ORDER_BEING_PREPARED,
            "ready": TrackingEventType.ORDER_READY,
            "delayed": TrackingEventType.ORDER_DELAYED,
        }

        event_type = event_type_map.get(update_type, TrackingEventType.CUSTOM_EVENT)

        await tracking_service.create_tracking_event(
            order_id=order_id,
            event_type=event_type,
            description=message,
            triggered_by_type="staff",
            triggered_by_id=updated_by,
            triggered_by_name="Kitchen Staff",
        )

    except Exception as e:
        logger.error(f"Failed to track kitchen update for order {order_id}: {e}")


async def on_delivery_update(
    db: Session,
    order_id: int,
    driver_id: int,
    driver_name: str,
    update_type: str,
    location: Optional[dict] = None,
    message: Optional[str] = None,
):
    """Hook for delivery driver updates"""
    try:
        tracking_service = OrderTrackingService(db)

        # Map delivery updates to tracking events
        event_type_map = {
            "assigned": TrackingEventType.CUSTOM_EVENT,
            "picked_up": TrackingEventType.ORDER_PICKED_UP,
            "en_route": TrackingEventType.ORDER_OUT_FOR_DELIVERY,
            "delivered": TrackingEventType.ORDER_DELIVERED,
        }

        event_type = event_type_map.get(update_type, TrackingEventType.CUSTOM_EVENT)

        await tracking_service.create_tracking_event(
            order_id=order_id,
            event_type=event_type,
            description=message or f"Delivery {update_type}",
            triggered_by_type="staff",
            triggered_by_id=driver_id,
            triggered_by_name=driver_name,
            location_data=location,
        )

    except Exception as e:
        logger.error(f"Failed to track delivery update for order {order_id}: {e}")


# Example usage in order service:
"""
from .order_service_tracking_integration import on_order_created, on_order_status_changed

class OrderService:
    async def create_order(self, ...):
        # Create order logic
        order = Order(...)
        self.db.add(order)
        self.db.commit()
        
        # Enable tracking
        await on_order_created(self.db, order, customer_email=email)
        
        return order
    
    async def update_status(self, order_id: int, new_status: str):
        order = self.db.query(Order).filter(Order.id == order_id).first()
        old_status = order.status
        
        # Update status
        order.status = new_status
        self.db.commit()
        
        # Track change
        await on_order_status_changed(
            self.db, order, old_status, new_status
        )
"""
