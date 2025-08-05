# backend/modules/orders/tests/test_order_tracking.py

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.orm import Session
from fastapi import WebSocket

from ..services.order_tracking_service import OrderTrackingService
from ..models.order_tracking_models import (
    OrderTrackingEvent, CustomerOrderTracking, OrderNotification,
    TrackingEventType, NotificationChannel
)
from ..models.order_models import Order
from ..enums.order_enums import OrderStatus
from ...customers.models.customer_models import Customer
from tests.factories import OrderFactory, CustomerFactory


@pytest.mark.unit
class TestOrderTrackingService:
    """Unit tests for order tracking service"""
    
    @pytest.fixture
    def tracking_service(self, db: Session):
        """Create tracking service instance"""
        return OrderTrackingService(db)
    
    @pytest.fixture
    def test_order(self, db: Session):
        """Create test order"""
        customer = CustomerFactory()
        order = OrderFactory(customer_id=customer.id, status=OrderStatus.PENDING)
        db.commit()
        return order
    
    @pytest.mark.asyncio
    async def test_create_tracking_event(self, tracking_service, test_order, db):
        """Test creating a tracking event"""
        event = await tracking_service.create_tracking_event(
            order_id=test_order.id,
            event_type=TrackingEventType.ORDER_CONFIRMED,
            old_status=OrderStatus.PENDING,
            new_status=OrderStatus.IN_PROGRESS,
            description="Order confirmed by restaurant",
            triggered_by_type="staff",
            triggered_by_id=1,
            triggered_by_name="Staff Member"
        )
        
        assert event.id is not None
        assert event.order_id == test_order.id
        assert event.event_type == TrackingEventType.ORDER_CONFIRMED
        assert event.old_status == OrderStatus.PENDING
        assert event.new_status == OrderStatus.IN_PROGRESS
        assert event.triggered_by_type == "staff"
        
        # Verify event is saved
        saved_event = db.query(OrderTrackingEvent).filter(
            OrderTrackingEvent.id == event.id
        ).first()
        assert saved_event is not None
    
    @pytest.mark.asyncio
    async def test_create_tracking_event_with_location(self, tracking_service, test_order):
        """Test creating a tracking event with location data"""
        location_data = {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "accuracy": 10.5
        }
        
        event = await tracking_service.create_tracking_event(
            order_id=test_order.id,
            event_type=TrackingEventType.ORDER_OUT_FOR_DELIVERY,
            description="Driver en route",
            location_data=location_data
        )
        
        assert event.latitude == 40.7128
        assert event.longitude == -74.0060
        assert event.location_accuracy == 10.5
    
    def test_create_customer_tracking(self, tracking_service, test_order, db):
        """Test creating customer tracking entry"""
        tracking = tracking_service.create_customer_tracking(
            order_id=test_order.id,
            customer_id=test_order.customer_id,
            notification_email="customer@example.com",
            notification_phone="+1234567890",
            enable_notifications=True
        )
        
        assert tracking.id is not None
        assert tracking.order_id == test_order.id
        assert tracking.customer_id == test_order.customer_id
        assert len(tracking.tracking_code) == 8
        assert tracking.access_token is not None
        assert tracking.enable_email is True
        assert tracking.enable_sms is True
        
        # Verify tracking code is unique
        another_order = OrderFactory()
        db.commit()
        
        tracking2 = tracking_service.create_customer_tracking(
            order_id=another_order.id,
            customer_id=another_order.customer_id
        )
        assert tracking2.tracking_code != tracking.tracking_code
    
    def test_get_order_tracking_by_code(self, tracking_service, test_order, db):
        """Test retrieving order tracking by code"""
        # Create tracking
        tracking = tracking_service.create_customer_tracking(
            order_id=test_order.id,
            customer_id=test_order.customer_id
        )
        
        # Create some events
        asyncio.run(tracking_service.create_tracking_event(
            order_id=test_order.id,
            event_type=TrackingEventType.ORDER_PLACED,
            new_status=OrderStatus.PENDING
        ))
        
        asyncio.run(tracking_service.create_tracking_event(
            order_id=test_order.id,
            event_type=TrackingEventType.ORDER_CONFIRMED,
            old_status=OrderStatus.PENDING,
            new_status=OrderStatus.IN_PROGRESS
        ))
        
        # Get tracking info
        tracking_info = tracking_service.get_order_tracking_by_code(tracking.tracking_code)
        
        assert tracking_info is not None
        assert tracking_info["order_id"] == test_order.id
        assert tracking_info["tracking_code"] == tracking.tracking_code
        assert tracking_info["current_status"] == test_order.status
        assert len(tracking_info["events"]) == 2
        
        # Verify access count incremented
        db.refresh(tracking)
        assert tracking.access_count == 1
        assert tracking.last_accessed_at is not None
    
    def test_get_order_tracking_invalid_code(self, tracking_service):
        """Test retrieving order tracking with invalid code"""
        tracking_info = tracking_service.get_order_tracking_by_code("INVALID")
        assert tracking_info is None
    
    @pytest.mark.asyncio
    async def test_track_order_status_change(self, tracking_service, test_order, db):
        """Test tracking order status changes"""
        # Track status change
        event = await tracking_service.track_order_status_change(
            order=test_order,
            new_status=OrderStatus.IN_KITCHEN,
            user_id=1,
            user_name="Chef",
            user_type="staff",
            reason="Started preparation"
        )
        
        assert event.event_type == TrackingEventType.ORDER_IN_KITCHEN
        assert event.old_status == test_order.status
        assert event.new_status == OrderStatus.IN_KITCHEN
        assert event.description == "Started preparation"
        assert event.estimated_completion_time is not None
        
        # Verify estimated time is reasonable (around 20 minutes)
        time_diff = event.estimated_completion_time - datetime.utcnow()
        assert timedelta(minutes=15) < time_diff < timedelta(minutes=25)
    
    @pytest.mark.asyncio
    async def test_send_event_notifications(self, tracking_service, test_order, db):
        """Test sending notifications for events"""
        # Create tracking with notifications enabled
        tracking = tracking_service.create_customer_tracking(
            order_id=test_order.id,
            customer_id=test_order.customer_id,
            notification_email="test@example.com",
            enable_notifications=True
        )
        
        # Mock notification adapter
        with patch.object(tracking_service.notification_adapter, 'send_to_user') as mock_send:
            mock_send.return_value = True
            
            # Create event
            event = await tracking_service.create_tracking_event(
                order_id=test_order.id,
                event_type=TrackingEventType.ORDER_READY,
                description="Your order is ready for pickup!"
            )
            
            # Verify notification was sent
            mock_send.assert_called()
            call_args = mock_send.call_args
            assert call_args[1]['user_id'] == test_order.customer_id
            assert "ready" in call_args[1]['message'].message.lower()
        
        # Verify notification record created
        notification = db.query(OrderNotification).filter(
            OrderNotification.order_id == test_order.id
        ).first()
        assert notification is not None
        assert notification.channel == NotificationChannel.EMAIL
        assert notification.recipient == "test@example.com"
    
    def test_get_active_orders_for_customer(self, tracking_service, db):
        """Test getting active orders for a customer"""
        customer = CustomerFactory()
        db.commit()
        
        # Create multiple orders with different statuses
        active_order1 = OrderFactory(
            customer_id=customer.id,
            status=OrderStatus.IN_PROGRESS
        )
        active_order2 = OrderFactory(
            customer_id=customer.id,
            status=OrderStatus.IN_KITCHEN
        )
        completed_order = OrderFactory(
            customer_id=customer.id,
            status=OrderStatus.COMPLETED
        )
        cancelled_order = OrderFactory(
            customer_id=customer.id,
            status=OrderStatus.CANCELLED
        )
        db.commit()
        
        # Create tracking for active orders
        tracking_service.create_customer_tracking(order_id=active_order1.id)
        tracking_service.create_customer_tracking(order_id=active_order2.id)
        tracking_service.create_customer_tracking(order_id=completed_order.id)
        
        # Get active orders
        active_orders = tracking_service.get_active_orders_for_customer(
            customer_id=customer.id,
            include_completed=False
        )
        
        assert len(active_orders) == 2
        order_ids = [o["order_id"] for o in active_orders]
        assert active_order1.id in order_ids
        assert active_order2.id in order_ids
        assert completed_order.id not in order_ids
        
        # Get all orders including completed
        all_orders = tracking_service.get_active_orders_for_customer(
            customer_id=customer.id,
            include_completed=True
        )
        
        assert len(all_orders) == 3
        order_ids = [o["order_id"] for o in all_orders]
        assert completed_order.id in order_ids
    
    @pytest.mark.asyncio
    async def test_websocket_integration(self, tracking_service, test_order, db):
        """Test WebSocket integration"""
        # Create mock websocket
        mock_ws = Mock(spec=WebSocket)
        mock_ws.send_json = AsyncMock()
        
        # Create tracking
        tracking = tracking_service.create_customer_tracking(
            order_id=test_order.id
        )
        
        # Register websocket
        session_id = "test-session-123"
        tracking_service.register_websocket(mock_ws, session_id, test_order.id)
        
        # Verify registration
        db.refresh(tracking)
        assert tracking.websocket_connected is True
        assert tracking.websocket_session_id == session_id
        
        # Create event and verify broadcast
        event = await tracking_service.create_tracking_event(
            order_id=test_order.id,
            event_type=TrackingEventType.ORDER_READY,
            description="Ready for pickup!"
        )
        
        # Verify websocket received update
        mock_ws.send_json.assert_called()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "order_update"
        assert call_args["order_id"] == test_order.id
        assert call_args["event"]["event_type"] == TrackingEventType.ORDER_READY.value
        
        # Unregister websocket
        tracking_service.unregister_websocket(mock_ws, session_id)
        
        # Verify unregistration
        db.refresh(tracking)
        assert tracking.websocket_connected is False
        assert tracking.websocket_session_id is None


@pytest.mark.integration
@pytest.mark.api
class TestOrderTrackingAPI:
    """Integration tests for order tracking API endpoints"""
    
    @pytest.fixture
    def test_customer_order(self, db: Session):
        """Create test customer and order"""
        customer = CustomerFactory()
        order = OrderFactory(
            customer_id=customer.id,
            status=OrderStatus.PENDING
        )
        db.commit()
        return {"customer": customer, "order": order}
    
    def test_enable_order_tracking(self, client, test_customer_order):
        """Test enabling tracking for an order"""
        order = test_customer_order["order"]
        
        response = client.post(
            f"/api/customer/tracking/orders/{order.id}/enable-tracking",
            json={
                "notification_email": "customer@example.com",
                "notification_phone": "+1234567890",
                "enable_notifications": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "tracking_code" in data
        assert "access_token" in data
        assert "tracking_url" in data
        assert "websocket_url" in data
        assert len(data["tracking_code"]) == 8
    
    def test_get_order_by_tracking_code(self, client, test_customer_order, db):
        """Test retrieving order by tracking code"""
        order = test_customer_order["order"]
        
        # Enable tracking
        tracking_service = OrderTrackingService(db)
        tracking = tracking_service.create_customer_tracking(
            order_id=order.id,
            customer_id=order.customer_id
        )
        
        # Create some events
        asyncio.run(tracking_service.create_tracking_event(
            order_id=order.id,
            event_type=TrackingEventType.ORDER_PLACED,
            new_status=OrderStatus.PENDING
        ))
        
        # Get tracking info
        response = client.get(
            f"/api/customer/tracking/track/{tracking.tracking_code}"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["order_id"] == order.id
        assert data["tracking_code"] == tracking.tracking_code
        assert data["current_status"] == order.status
        assert len(data["events"]) >= 1
    
    def test_update_notification_preferences(self, client, test_customer_order, db):
        """Test updating notification preferences"""
        order = test_customer_order["order"]
        
        # Enable tracking
        tracking_service = OrderTrackingService(db)
        tracking = tracking_service.create_customer_tracking(
            order_id=order.id
        )
        
        # Update preferences
        response = client.put(
            f"/api/customer/tracking/orders/{order.id}/notifications",
            json={
                "access_token": tracking.access_token,
                "enable_push": True,
                "enable_email": False,
                "push_token": "test-push-token-123"
            }
        )
        
        assert response.status_code == 200
        
        # Verify preferences updated
        db.refresh(tracking)
        assert tracking.enable_push is True
        assert tracking.enable_email is False
        assert tracking.push_token == "test-push-token-123"
    
    @pytest.mark.asyncio
    async def test_websocket_connection(self, client, test_customer_order, db):
        """Test WebSocket connection for order tracking"""
        order = test_customer_order["order"]
        
        # Enable tracking
        tracking_service = OrderTrackingService(db)
        tracking = tracking_service.create_customer_tracking(
            order_id=order.id
        )
        
        # Connect to websocket
        with client.websocket_connect(
            f"/ws/order-tracking?access_token={tracking.access_token}"
        ) as websocket:
            # Receive connection confirmation
            data = websocket.receive_json()
            assert data["type"] == "connection_established"
            assert data["order_id"] == order.id
            
            # Receive current status
            data = websocket.receive_json()
            assert data["type"] == "current_status"
            assert data["data"]["order_id"] == order.id
            
            # Send ping
            websocket.send_json({"type": "ping"})
            
            # Receive pong
            data = websocket.receive_json()
            assert data["type"] == "pong"


@pytest.mark.unit
class TestPushNotificationService:
    """Unit tests for push notification service"""
    
    @pytest.mark.asyncio
    async def test_send_order_push_notification(self):
        """Test sending order push notification"""
        from ..services.push_notification_service import send_order_push_notification
        
        # Mock configuration
        config = {
            "fcm_server_key": "test-key",
            "environment": "development"
        }
        
        # Test sending notification
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": 1}
            mock_post.return_value = mock_response
            
            result = await send_order_push_notification(
                customer_id=1,
                order_id=123,
                event_type="order_ready",
                title="Order Ready!",
                message="Your order #123 is ready for pickup",
                push_tokens=["test-token-123"],
                config=config
            )
            
            assert result is True
            mock_post.assert_called_once()