# backend/modules/orders/api/customer_tracking_endpoints.py

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime

from core.database import get_db
from core.auth import get_current_user_optional
from modules.customers.auth.customer_auth import get_current_customer
from ..services.order_tracking_service import OrderTrackingService
from ..models.order_tracking_models import TrackingEventType, NotificationChannel
from ..schemas.tracking_schemas import (
    OrderTrackingResponse,
    CustomerTrackingCreate,
    NotificationPreferencesUpdate,
    ActiveOrdersResponse,
    TrackingEventResponse,
)


router = APIRouter(prefix="/customer/tracking", tags=["customer-tracking"])


@router.post("/orders/{order_id}/enable-tracking", response_model=Dict[str, Any])
async def enable_order_tracking(
    order_id: int,
    tracking_data: CustomerTrackingCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_customer: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Enable tracking for an order

    Creates tracking entry with notification preferences
    Returns tracking code and access token
    """
    tracking_service = OrderTrackingService(db)

    # Verify order exists and belongs to customer (if authenticated)
    from ..models.order_models import Order

    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # If authenticated, verify ownership
    if current_customer and order.customer_id != current_customer.get("customer_id"):
        raise HTTPException(
            status_code=403, detail="Not authorized to track this order"
        )

    # Check if tracking already exists
    from ..models.order_tracking_models import CustomerOrderTracking

    existing = (
        db.query(CustomerOrderTracking)
        .filter(CustomerOrderTracking.order_id == order_id)
        .first()
    )

    if existing:
        return {
            "tracking_code": existing.tracking_code,
            "access_token": existing.access_token,
            "tracking_url": f"/track/{existing.tracking_code}",
        }

    # Create tracking
    tracking = tracking_service.create_customer_tracking(
        order_id=order_id,
        customer_id=current_customer.get("customer_id") if current_customer else None,
        notification_email=tracking_data.notification_email,
        notification_phone=tracking_data.notification_phone,
        enable_notifications=tracking_data.enable_notifications,
    )

    # Create initial tracking event
    background_tasks.add_task(
        tracking_service.create_tracking_event,
        order_id=order_id,
        event_type=TrackingEventType.ORDER_PLACED,
        new_status=order.status,
        description="Order tracking enabled",
        triggered_by_type="customer",
        triggered_by_id=(
            current_customer.get("customer_id") if current_customer else None
        ),
    )

    return {
        "tracking_code": tracking.tracking_code,
        "access_token": tracking.access_token,
        "tracking_url": f"/track/{tracking.tracking_code}",
        "websocket_url": f"/ws/order-tracking?access_token={tracking.access_token}",
    }


@router.get("/track/{tracking_code}", response_model=OrderTrackingResponse)
async def get_order_by_tracking_code(tracking_code: str, db: Session = Depends(get_db)):
    """
    Get order tracking information by tracking code

    Public endpoint - no authentication required
    """
    tracking_service = OrderTrackingService(db)

    tracking_info = tracking_service.get_order_tracking_by_code(tracking_code)

    if not tracking_info:
        raise HTTPException(status_code=404, detail="Invalid tracking code")

    return tracking_info


@router.get("/track", response_model=OrderTrackingResponse)
async def get_order_by_token(
    access_token: str = Query(..., description="Access token for order tracking"),
    db: Session = Depends(get_db),
):
    """
    Get order tracking information by access token

    Alternative to tracking code for programmatic access
    """
    tracking_service = OrderTrackingService(db)

    tracking_info = tracking_service.get_order_tracking_by_token(access_token)

    if not tracking_info:
        raise HTTPException(status_code=404, detail="Invalid access token")

    return tracking_info


@router.get("/my-orders/active", response_model=List[ActiveOrdersResponse])
async def get_my_active_orders(
    include_completed: bool = Query(
        False, description="Include recently completed orders"
    ),
    db: Session = Depends(get_db),
    current_customer: dict = Depends(get_current_customer),
):
    """
    Get all active orders for the authenticated customer

    Requires customer authentication
    """
    tracking_service = OrderTrackingService(db)

    orders = tracking_service.get_active_orders_for_customer(
        customer_id=current_customer["customer_id"], include_completed=include_completed
    )

    return orders


@router.put("/orders/{order_id}/notifications", response_model=Dict[str, str])
async def update_notification_preferences(
    order_id: int,
    preferences: NotificationPreferencesUpdate,
    db: Session = Depends(get_db),
    current_customer: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Update notification preferences for an order

    Can be accessed with tracking token or customer auth
    """
    from ..models.order_tracking_models import CustomerOrderTracking

    # Get tracking record
    tracking = (
        db.query(CustomerOrderTracking)
        .filter(CustomerOrderTracking.order_id == order_id)
        .first()
    )

    if not tracking:
        raise HTTPException(status_code=404, detail="Order tracking not found")

    # Verify access
    if current_customer:
        # Authenticated customer must own the order
        if tracking.customer_id != current_customer.get("customer_id"):
            raise HTTPException(status_code=403, detail="Not authorized")
    else:
        # Must provide valid access token
        if preferences.access_token != tracking.access_token:
            raise HTTPException(status_code=403, detail="Invalid access token")

    # Update preferences
    if preferences.enable_push is not None:
        tracking.enable_push = preferences.enable_push
    if preferences.enable_email is not None:
        tracking.enable_email = preferences.enable_email
    if preferences.enable_sms is not None:
        tracking.enable_sms = preferences.enable_sms
    if preferences.notification_email:
        tracking.notification_email = preferences.notification_email
    if preferences.notification_phone:
        tracking.notification_phone = preferences.notification_phone
    if preferences.push_token:
        tracking.push_token = preferences.push_token

    db.commit()

    return {"message": "Notification preferences updated"}


@router.post("/orders/{order_id}/events", response_model=TrackingEventResponse)
async def create_customer_event(
    order_id: int,
    event_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_customer: dict = Depends(get_current_customer),
):
    """
    Allow customers to create certain tracking events

    For example: marking order as picked up, rating delivery, etc.
    """
    tracking_service = OrderTrackingService(db)

    # Verify order belongs to customer
    from ..models.order_models import Order

    order = (
        db.query(Order)
        .filter(
            Order.id == order_id, Order.customer_id == current_customer["customer_id"]
        )
        .first()
    )

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Map customer actions to event types
    action = event_data.get("action")
    allowed_actions = {
        "picked_up": TrackingEventType.ORDER_PICKED_UP,
        "feedback": TrackingEventType.CUSTOM_EVENT,
        "eta_inquiry": TrackingEventType.CUSTOM_EVENT,
    }

    if action not in allowed_actions:
        raise HTTPException(status_code=400, detail="Invalid action")

    event_type = allowed_actions[action]

    # Create event
    event = await tracking_service.create_tracking_event(
        order_id=order_id,
        event_type=event_type,
        description=event_data.get("description", f"Customer action: {action}"),
        triggered_by_type="customer",
        triggered_by_id=current_customer["customer_id"],
        triggered_by_name=current_customer.get("name", "Customer"),
        metadata=event_data.get("metadata", {}),
    )

    return {
        "event_id": event.id,
        "event_type": event.event_type.value,
        "created_at": event.created_at,
    }


@router.get("/orders/{order_id}/events", response_model=List[TrackingEventResponse])
async def get_order_events(
    order_id: int,
    tracking_code: Optional[str] = Query(None),
    access_token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_customer: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Get all tracking events for an order

    Requires either:
    - Valid tracking code
    - Valid access token
    - Customer authentication (for own orders)
    """
    from ..models.order_tracking_models import CustomerOrderTracking, OrderTrackingEvent

    # Verify access
    authorized = False

    if tracking_code:
        tracking = (
            db.query(CustomerOrderTracking)
            .filter(
                CustomerOrderTracking.order_id == order_id,
                CustomerOrderTracking.tracking_code == tracking_code,
            )
            .first()
        )
        authorized = tracking is not None

    elif access_token:
        tracking = (
            db.query(CustomerOrderTracking)
            .filter(
                CustomerOrderTracking.order_id == order_id,
                CustomerOrderTracking.access_token == access_token,
            )
            .first()
        )
        authorized = tracking is not None

    elif current_customer:
        from ..models.order_models import Order

        order = (
            db.query(Order)
            .filter(
                Order.id == order_id,
                Order.customer_id == current_customer["customer_id"],
            )
            .first()
        )
        authorized = order is not None

    if not authorized:
        raise HTTPException(status_code=403, detail="Not authorized to view this order")

    # Get events
    events = (
        db.query(OrderTrackingEvent)
        .filter(OrderTrackingEvent.order_id == order_id)
        .order_by(OrderTrackingEvent.created_at.desc())
        .all()
    )

    return [
        {
            "event_id": event.id,
            "event_type": event.event_type.value,
            "description": event.description,
            "created_at": event.created_at,
            "old_status": event.old_status,
            "new_status": event.new_status,
            "estimated_completion_time": event.estimated_completion_time,
            "location": (
                {
                    "latitude": event.latitude,
                    "longitude": event.longitude,
                    "accuracy": event.location_accuracy,
                }
                if event.latitude
                else None
            ),
            "triggered_by": {
                "type": event.triggered_by_type,
                "name": event.triggered_by_name,
            },
        }
        for event in events
    ]


@router.post("/register-push-token", response_model=Dict[str, str])
async def register_push_token(
    token_data: Dict[str, str],
    db: Session = Depends(get_db),
    current_customer: dict = Depends(get_current_customer),
):
    """
    Register a push notification token for the customer

    Updates all active order trackings with the new token
    """
    push_token = token_data.get("push_token")
    platform = token_data.get("platform", "unknown")  # ios, android, web

    if not push_token:
        raise HTTPException(status_code=400, detail="Push token required")

    # Update all active order trackings for this customer
    from ..models.order_tracking_models import CustomerOrderTracking
    from ..models.order_models import Order
    from ..enums.order_enums import OrderStatus

    active_statuses = [
        OrderStatus.PENDING,
        OrderStatus.IN_PROGRESS,
        OrderStatus.IN_KITCHEN,
        OrderStatus.READY,
        OrderStatus.DELAYED,
        OrderStatus.SCHEDULED,
        OrderStatus.AWAITING_FULFILLMENT,
    ]

    # Get active order trackings
    trackings = (
        db.query(CustomerOrderTracking)
        .join(Order, CustomerOrderTracking.order_id == Order.id)
        .filter(
            CustomerOrderTracking.customer_id == current_customer["customer_id"],
            Order.status.in_(active_statuses),
        )
        .all()
    )

    # Update push tokens
    for tracking in trackings:
        tracking.push_token = push_token
        tracking.enable_push = True

    db.commit()

    return {
        "message": f"Push token registered for {len(trackings)} active orders",
        "platform": platform,
    }


# Helper endpoint for testing notifications
@router.post("/test-notification/{order_id}")
async def test_notification(
    order_id: int,
    channel: NotificationChannel,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_customer: dict = Depends(get_current_customer),
):
    """
    Test endpoint to trigger a notification for an order

    For development/testing purposes
    """
    tracking_service = OrderTrackingService(db)

    # Verify order belongs to customer
    from ..models.order_models import Order

    order = (
        db.query(Order)
        .filter(
            Order.id == order_id, Order.customer_id == current_customer["customer_id"]
        )
        .first()
    )

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Create test event
    event = await tracking_service.create_tracking_event(
        order_id=order_id,
        event_type=TrackingEventType.CUSTOM_EVENT,
        description=f"Test {channel.value} notification",
        triggered_by_type="customer",
        triggered_by_id=current_customer["customer_id"],
        metadata={"test": True, "channel": channel.value},
    )

    return {"message": f"Test {channel.value} notification sent", "event_id": event.id}
