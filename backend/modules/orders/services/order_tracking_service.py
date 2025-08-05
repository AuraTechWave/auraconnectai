# backend/modules/orders/services/order_tracking_service.py

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import secrets
import string
from fastapi import HTTPException, WebSocket

from core.database import get_db
from core.notification_adapter import (
    NotificationAdapter, NotificationMessage, NotificationPriority,
    LoggingAdapter, CompositeAdapter
)
from ..models.order_models import Order
from ..enums.order_enums import OrderStatus
from ..models.order_tracking_models import (
    OrderTrackingEvent, CustomerOrderTracking, OrderNotification,
    OrderTrackingTemplate, TrackingEventType, NotificationChannel
)
from ..utils.audit_logger import AuditLogger, audit_action
from ...customers.models.customer_models import Customer


class OrderTrackingService:
    """Service for managing order tracking and real-time notifications"""
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = AuditLogger("order_tracking")
        self.notification_adapter = self._get_notification_adapter()
        self._websocket_connections: Dict[str, List[WebSocket]] = {}
    
    def _get_notification_adapter(self) -> NotificationAdapter:
        """Get the configured notification adapter"""
        # For now, use logging adapter. In production, this would be configured
        # to use real adapters (email, SMS, push, etc.)
        return LoggingAdapter()
    
    @audit_action("create_tracking_event", "order")
    async def create_tracking_event(
        self,
        order_id: int,
        event_type: TrackingEventType,
        old_status: Optional[str] = None,
        new_status: Optional[str] = None,
        description: Optional[str] = None,
        triggered_by_type: str = "system",
        triggered_by_id: Optional[int] = None,
        triggered_by_name: Optional[str] = None,
        metadata: Optional[Dict] = None,
        location_data: Optional[Dict] = None,
        estimated_completion_time: Optional[datetime] = None
    ) -> OrderTrackingEvent:
        """
        Create a new tracking event for an order
        
        Args:
            order_id: ID of the order
            event_type: Type of tracking event
            old_status: Previous order status
            new_status: New order status
            description: Human-readable description
            triggered_by_type: Who triggered the event (system, staff, customer, api)
            triggered_by_id: ID of the user who triggered the event
            triggered_by_name: Name of the user who triggered the event
            metadata: Additional event data
            location_data: Dict with latitude, longitude, accuracy for delivery tracking
            estimated_completion_time: Estimated time for order completion
        
        Returns:
            Created OrderTrackingEvent
        """
        # Verify order exists
        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Create tracking event
        tracking_event = OrderTrackingEvent(
            order_id=order_id,
            event_type=event_type,
            old_status=old_status,
            new_status=new_status,
            description=description,
            triggered_by_type=triggered_by_type,
            triggered_by_id=triggered_by_id,
            triggered_by_name=triggered_by_name,
            metadata=metadata or {},
            estimated_completion_time=estimated_completion_time
        )
        
        # Add location data if provided
        if location_data:
            tracking_event.latitude = location_data.get("latitude")
            tracking_event.longitude = location_data.get("longitude")
            tracking_event.location_accuracy = location_data.get("accuracy")
        
        self.db.add(tracking_event)
        self.db.commit()
        self.db.refresh(tracking_event)
        
        # Send notifications asynchronously
        await self._send_event_notifications(tracking_event, order)
        
        # Send WebSocket updates
        await self._broadcast_websocket_update(order_id, tracking_event)
        
        return tracking_event
    
    async def track_order_status_change(
        self,
        order: Order,
        new_status: str,
        user_id: Optional[int] = None,
        user_name: Optional[str] = None,
        user_type: str = "system",
        reason: Optional[str] = None
    ) -> OrderTrackingEvent:
        """
        Track an order status change
        
        Args:
            order: Order object
            new_status: New order status
            user_id: ID of user making the change
            user_name: Name of user making the change
            user_type: Type of user (system, staff, customer, api)
            reason: Reason for status change
        
        Returns:
            Created tracking event
        """
        # Map status to event type
        event_type_map = {
            OrderStatus.PENDING: TrackingEventType.ORDER_PLACED,
            OrderStatus.IN_PROGRESS: TrackingEventType.ORDER_CONFIRMED,
            OrderStatus.IN_KITCHEN: TrackingEventType.ORDER_IN_KITCHEN,
            OrderStatus.READY: TrackingEventType.ORDER_READY,
            OrderStatus.SERVED: TrackingEventType.ORDER_SERVED,
            OrderStatus.COMPLETED: TrackingEventType.ORDER_COMPLETED,
            OrderStatus.CANCELLED: TrackingEventType.ORDER_CANCELLED,
            OrderStatus.DELAYED: TrackingEventType.ORDER_DELAYED,
            OrderStatus.PAID: TrackingEventType.PAYMENT_RECEIVED
        }
        
        event_type = event_type_map.get(new_status, TrackingEventType.CUSTOM_EVENT)
        
        # Calculate estimated completion time based on status
        estimated_time = None
        if new_status == OrderStatus.IN_KITCHEN:
            # Estimate 20 minutes for kitchen preparation
            estimated_time = datetime.utcnow() + timedelta(minutes=20)
        elif new_status == OrderStatus.IN_PROGRESS:
            # Estimate 30 minutes total from confirmation
            estimated_time = datetime.utcnow() + timedelta(minutes=30)
        
        return await self.create_tracking_event(
            order_id=order.id,
            event_type=event_type,
            old_status=order.status,
            new_status=new_status,
            description=reason,
            triggered_by_type=user_type,
            triggered_by_id=user_id,
            triggered_by_name=user_name,
            estimated_completion_time=estimated_time
        )
    
    def create_customer_tracking(
        self,
        order_id: int,
        customer_id: Optional[int] = None,
        notification_email: Optional[str] = None,
        notification_phone: Optional[str] = None,
        enable_notifications: bool = True
    ) -> CustomerOrderTracking:
        """
        Create customer tracking entry for an order
        
        Args:
            order_id: ID of the order
            customer_id: ID of the customer (optional for guest orders)
            notification_email: Email for notifications
            notification_phone: Phone for SMS notifications
            enable_notifications: Whether to enable notifications
        
        Returns:
            Created CustomerOrderTracking
        """
        # Generate unique tracking code
        tracking_code = self._generate_tracking_code()
        
        # Generate access token for anonymous tracking
        access_token = secrets.token_urlsafe(32)
        
        # Create tracking entry
        tracking = CustomerOrderTracking(
            order_id=order_id,
            customer_id=customer_id,
            tracking_code=tracking_code,
            access_token=access_token,
            notification_email=notification_email,
            notification_phone=notification_phone,
            enable_push=enable_notifications,
            enable_email=enable_notifications and bool(notification_email),
            enable_sms=enable_notifications and bool(notification_phone)
        )
        
        self.db.add(tracking)
        self.db.commit()
        self.db.refresh(tracking)
        
        return tracking
    
    def _generate_tracking_code(self) -> str:
        """Generate a unique tracking code"""
        # Generate 8-character alphanumeric code
        while True:
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            # Check if code already exists
            existing = self.db.query(CustomerOrderTracking).filter(
                CustomerOrderTracking.tracking_code == code
            ).first()
            if not existing:
                return code
    
    def get_order_tracking_by_code(self, tracking_code: str) -> Optional[Dict]:
        """
        Get order tracking information by tracking code
        
        Args:
            tracking_code: The tracking code
        
        Returns:
            Order tracking information or None
        """
        tracking = self.db.query(CustomerOrderTracking).filter(
            CustomerOrderTracking.tracking_code == tracking_code
        ).first()
        
        if not tracking:
            return None
        
        # Update access count and timestamp
        tracking.access_count += 1
        tracking.last_accessed_at = datetime.utcnow()
        self.db.commit()
        
        # Get order and tracking events
        order = tracking.order
        events = self.db.query(OrderTrackingEvent).filter(
            OrderTrackingEvent.order_id == order.id
        ).order_by(OrderTrackingEvent.created_at.desc()).all()
        
        return {
            "order_id": order.id,
            "tracking_code": tracking_code,
            "current_status": order.status,
            "created_at": order.created_at,
            "estimated_completion_time": events[0].estimated_completion_time if events else None,
            "events": [
                {
                    "id": event.id,
                    "event_type": event.event_type.value,
                    "description": event.description,
                    "created_at": event.created_at,
                    "location": {
                        "latitude": event.latitude,
                        "longitude": event.longitude,
                        "accuracy": event.location_accuracy
                    } if event.latitude else None
                }
                for event in events
            ]
        }
    
    def get_order_tracking_by_token(self, access_token: str) -> Optional[Dict]:
        """
        Get order tracking information by access token
        
        Args:
            access_token: The access token
        
        Returns:
            Order tracking information or None
        """
        tracking = self.db.query(CustomerOrderTracking).filter(
            CustomerOrderTracking.access_token == access_token
        ).first()
        
        if not tracking:
            return None
        
        return self.get_order_tracking_by_code(tracking.tracking_code)
    
    async def _send_event_notifications(
        self,
        event: OrderTrackingEvent,
        order: Order
    ):
        """Send notifications for a tracking event"""
        # Get customer tracking preferences
        tracking = self.db.query(CustomerOrderTracking).filter(
            CustomerOrderTracking.order_id == order.id
        ).first()
        
        if not tracking:
            return
        
        # Import notification services
        from .push_notification_service import PushNotificationService
        from .notification_retry_service import NotificationRetryService
        from ..models.notification_config_models import NotificationChannelConfig
        
        # Get notification templates
        templates = self.db.query(OrderTrackingTemplate).filter(
            and_(
                OrderTrackingTemplate.event_type == event.event_type,
                OrderTrackingTemplate.is_active == True
            )
        ).order_by(OrderTrackingTemplate.priority.desc()).all()
        
        if not templates:
            # Use default message
            message = f"Order #{order.id}: {event.description or event.event_type.value}"
        else:
            # Use template (simplified for now)
            template = templates[0]
            message = template.message_template.format(
                order_id=order.id,
                status=event.new_status or order.status,
                estimated_time=event.estimated_completion_time.strftime("%I:%M %p") if event.estimated_completion_time else "N/A"
            )
        
        # Determine notification priority based on event type
        priority_map = {
            TrackingEventType.ORDER_READY: NotificationPriority.HIGH,
            TrackingEventType.ORDER_DELIVERED: NotificationPriority.HIGH,
            TrackingEventType.ORDER_CANCELLED: NotificationPriority.URGENT,
            TrackingEventType.ORDER_DELAYED: NotificationPriority.HIGH
        }
        priority = priority_map.get(event.event_type, NotificationPriority.NORMAL)
        
        # Send notifications based on preferences
        notification_msg = NotificationMessage(
            subject=f"Order #{order.id} Update",
            message=message,
            priority=priority,
            metadata={
                "order_id": order.id,
                "event_id": event.id,
                "event_type": event.event_type.value
            }
        )
        
        notifications_sent = []
        retry_service = NotificationRetryService(self.db)
        
        # Send email notification
        if tracking.enable_email and tracking.notification_email:
            # Get email channel config
            email_config = self.db.query(NotificationChannelConfig).filter(
                and_(
                    NotificationChannelConfig.channel_type == "email",
                    NotificationChannelConfig.is_enabled == True
                )
            ).first()
            
            if email_config:
                try:
                    sent = await self.notification_adapter.send_to_user(
                        user_id=tracking.customer_id or 0,
                        message=notification_msg
                    )
                    notification = self._create_notification_record(
                        order.id, event.id, tracking.customer_id,
                        NotificationChannel.EMAIL, tracking.notification_email,
                        notification_msg, sent
                    )
                    notifications_sent.append(notification)
                    
                    if not sent:
                        # Queue for retry
                        await retry_service.queue_for_retry(
                            notification, "Failed to send email", email_config
                        )
                except Exception as e:
                    logger.error(f"Email notification failed: {e}")
        
        # Send push notification
        if tracking.enable_push and tracking.push_token:
            # Get push channel config
            push_config = self.db.query(NotificationChannelConfig).filter(
                and_(
                    NotificationChannelConfig.channel_type == "push",
                    NotificationChannelConfig.is_enabled == True
                )
            ).first()
            
            if push_config:
                try:
                    # Use actual push notification service
                    push_service = PushNotificationService(push_config.config)
                    sent = await push_service._send_fcm(
                        token=tracking.push_token,
                        title=notification_msg.subject,
                        body=notification_msg.message,
                        data=notification_msg.metadata
                    )
                    
                    notification = self._create_notification_record(
                        order.id, event.id, tracking.customer_id,
                        NotificationChannel.PUSH, tracking.push_token,
                        notification_msg, sent
                    )
                    notifications_sent.append(notification)
                    
                    if not sent:
                        # Queue for retry
                        await retry_service.queue_for_retry(
                            notification, "Failed to send push notification", push_config
                        )
                except Exception as e:
                    logger.error(f"Push notification failed: {e}")
        
        # Send SMS for high-priority events
        if (tracking.enable_sms and tracking.notification_phone and 
            event.event_type in [TrackingEventType.ORDER_READY, TrackingEventType.ORDER_DELIVERED]):
            
            # Get SMS channel config
            sms_config = self.db.query(NotificationChannelConfig).filter(
                and_(
                    NotificationChannelConfig.channel_type == "sms",
                    NotificationChannelConfig.is_enabled == True
                )
            ).first()
            
            if sms_config:
                try:
                    sent = await self.notification_adapter.send_to_user(
                        user_id=tracking.customer_id or 0,
                        message=notification_msg
                    )
                    notification = self._create_notification_record(
                        order.id, event.id, tracking.customer_id,
                        NotificationChannel.SMS, tracking.notification_phone,
                        notification_msg, sent
                    )
                    notifications_sent.append(notification)
                    
                    if not sent:
                        # Queue for retry
                        await retry_service.queue_for_retry(
                            notification, "Failed to send SMS", sms_config
                        )
                except Exception as e:
                    logger.error(f"SMS notification failed: {e}")
        
        # Save all notification records
        for notification in notifications_sent:
            self.db.add(notification)
        self.db.commit()
    
    def _create_notification_record(
        self,
        order_id: int,
        event_id: int,
        customer_id: Optional[int],
        channel: NotificationChannel,
        recipient: str,
        message: NotificationMessage,
        sent: bool
    ) -> OrderNotification:
        """Create a notification record"""
        notification = OrderNotification(
            order_id=order_id,
            tracking_event_id=event_id,
            customer_id=customer_id,
            channel=channel,
            recipient=recipient,
            subject=message.subject,
            message=message.message,
            sent_at=datetime.utcnow() if sent else None,
            metadata=message.metadata
        )
        return notification
    
    async def _broadcast_websocket_update(
        self,
        order_id: int,
        event: OrderTrackingEvent
    ):
        """Broadcast update to WebSocket connections"""
        # Get tracking info
        tracking = self.db.query(CustomerOrderTracking).filter(
            CustomerOrderTracking.order_id == order_id
        ).first()
        
        if not tracking or not tracking.websocket_session_id:
            return
        
        # Get connections for this order
        connections = self._websocket_connections.get(tracking.websocket_session_id, [])
        
        # Prepare update message
        update = {
            "type": "order_update",
            "order_id": order_id,
            "event": {
                "id": event.id,
                "event_type": event.event_type.value,
                "description": event.description,
                "created_at": event.created_at.isoformat(),
                "new_status": event.new_status,
                "estimated_completion_time": event.estimated_completion_time.isoformat() if event.estimated_completion_time else None,
                "location": {
                    "latitude": event.latitude,
                    "longitude": event.longitude,
                    "accuracy": event.location_accuracy
                } if event.latitude else None
            }
        }
        
        # Send to all connections
        disconnected = []
        for websocket in connections:
            try:
                await websocket.send_json(update)
            except Exception:
                disconnected.append(websocket)
        
        # Remove disconnected websockets
        for ws in disconnected:
            connections.remove(ws)
        
        if not connections:
            del self._websocket_connections[tracking.websocket_session_id]
            tracking.websocket_connected = False
            tracking.websocket_session_id = None
            self.db.commit()
    
    def register_websocket(
        self,
        websocket: WebSocket,
        session_id: str,
        order_id: int
    ):
        """Register a WebSocket connection for an order"""
        # Update tracking record
        tracking = self.db.query(CustomerOrderTracking).filter(
            CustomerOrderTracking.order_id == order_id
        ).first()
        
        if tracking:
            tracking.websocket_connected = True
            tracking.websocket_session_id = session_id
            self.db.commit()
        
        # Add to connections
        if session_id not in self._websocket_connections:
            self._websocket_connections[session_id] = []
        self._websocket_connections[session_id].append(websocket)
    
    def unregister_websocket(
        self,
        websocket: WebSocket,
        session_id: str
    ):
        """Unregister a WebSocket connection"""
        if session_id in self._websocket_connections:
            connections = self._websocket_connections[session_id]
            if websocket in connections:
                connections.remove(websocket)
            
            if not connections:
                del self._websocket_connections[session_id]
                
                # Update tracking records
                tracking = self.db.query(CustomerOrderTracking).filter(
                    CustomerOrderTracking.websocket_session_id == session_id
                ).first()
                if tracking:
                    tracking.websocket_connected = False
                    tracking.websocket_session_id = None
                    self.db.commit()
    
    def get_active_orders_for_customer(
        self,
        customer_id: int,
        include_completed: bool = False
    ) -> List[Dict]:
        """
        Get active orders with tracking for a customer
        
        Args:
            customer_id: Customer ID
            include_completed: Whether to include completed orders
        
        Returns:
            List of orders with tracking information
        """
        # Define active statuses
        active_statuses = [
            OrderStatus.PENDING,
            OrderStatus.IN_PROGRESS,
            OrderStatus.IN_KITCHEN,
            OrderStatus.READY,
            OrderStatus.DELAYED,
            OrderStatus.SCHEDULED,
            OrderStatus.AWAITING_FULFILLMENT
        ]
        
        if include_completed:
            active_statuses.extend([
                OrderStatus.COMPLETED,
                OrderStatus.SERVED,
                OrderStatus.PAID
            ])
        
        # Query orders with tracking
        orders = self.db.query(Order).join(
            CustomerOrderTracking,
            Order.id == CustomerOrderTracking.order_id
        ).filter(
            and_(
                Order.customer_id == customer_id,
                Order.status.in_(active_statuses),
                Order.deleted_at.is_(None)
            )
        ).order_by(Order.created_at.desc()).all()
        
        result = []
        for order in orders:
            # Get latest tracking event
            latest_event = self.db.query(OrderTrackingEvent).filter(
                OrderTrackingEvent.order_id == order.id
            ).order_by(OrderTrackingEvent.created_at.desc()).first()
            
            # Get tracking info
            tracking = order.customer_tracking
            
            result.append({
                "order_id": order.id,
                "status": order.status,
                "created_at": order.created_at,
                "tracking_code": tracking.tracking_code if tracking else None,
                "estimated_completion_time": latest_event.estimated_completion_time if latest_event else None,
                "latest_event": {
                    "event_type": latest_event.event_type.value,
                    "description": latest_event.description,
                    "created_at": latest_event.created_at
                } if latest_event else None
            })
        
        return result
    
    async def send_delivery_location_update(
        self,
        order_id: int,
        latitude: float,
        longitude: float,
        accuracy: float,
        driver_id: int,
        driver_name: str
    ) -> OrderTrackingEvent:
        """
        Send delivery driver location update
        
        Args:
            order_id: Order ID
            latitude: Current latitude
            longitude: Current longitude
            accuracy: Location accuracy in meters
            driver_id: Driver ID
            driver_name: Driver name
        
        Returns:
            Created tracking event
        """
        return await self.create_tracking_event(
            order_id=order_id,
            event_type=TrackingEventType.CUSTOM_EVENT,
            description=f"Driver {driver_name} location updated",
            triggered_by_type="staff",
            triggered_by_id=driver_id,
            triggered_by_name=driver_name,
            location_data={
                "latitude": latitude,
                "longitude": longitude,
                "accuracy": accuracy
            },
            metadata={
                "update_type": "driver_location",
                "driver_id": driver_id
            }
        )