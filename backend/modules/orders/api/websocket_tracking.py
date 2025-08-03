# backend/modules/orders/api/websocket_tracking.py

from fastapi import WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict
import json
import asyncio
import logging
from datetime import datetime

from core.database import get_db
from core.auth import get_current_user_optional
from ..services.order_tracking_service import OrderTrackingService
from ..models.order_tracking_models import CustomerOrderTracking


logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage WebSocket connections for order tracking"""
    
    def __init__(self):
        # Map of order_id to list of active connections
        self.active_connections: Dict[int, list[WebSocket]] = {}
        # Map of connection to order_id for cleanup
        self.connection_orders: Dict[WebSocket, int] = {}
        # Map of connection to session_id
        self.connection_sessions: Dict[WebSocket, str] = {}
    
    async def connect(self, websocket: WebSocket, order_id: int, session_id: str):
        """Accept and register a new connection"""
        await websocket.accept()
        
        # Add to connections
        if order_id not in self.active_connections:
            self.active_connections[order_id] = []
        self.active_connections[order_id].append(websocket)
        
        # Track connection metadata
        self.connection_orders[websocket] = order_id
        self.connection_sessions[websocket] = session_id
        
        logger.info(f"WebSocket connected for order {order_id}, session {session_id}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a connection"""
        # Get order_id for this connection
        order_id = self.connection_orders.get(websocket)
        session_id = self.connection_sessions.get(websocket)
        
        if order_id and order_id in self.active_connections:
            self.active_connections[order_id].remove(websocket)
            if not self.active_connections[order_id]:
                del self.active_connections[order_id]
        
        # Clean up metadata
        if websocket in self.connection_orders:
            del self.connection_orders[websocket]
        if websocket in self.connection_sessions:
            del self.connection_sessions[websocket]
        
        logger.info(f"WebSocket disconnected for order {order_id}, session {session_id}")
    
    async def send_to_order(self, order_id: int, message: dict):
        """Send a message to all connections for an order"""
        if order_id in self.active_connections:
            # Send to all connections for this order
            disconnected = []
            for connection in self.active_connections[order_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending to connection: {e}")
                    disconnected.append(connection)
            
            # Clean up disconnected connections
            for conn in disconnected:
                self.disconnect(conn)
    
    async def broadcast_order_update(self, order_id: int, event: dict):
        """Broadcast an order update to all connections"""
        message = {
            "type": "order_update",
            "timestamp": datetime.utcnow().isoformat(),
            "order_id": order_id,
            "event": event
        }
        await self.send_to_order(order_id, message)


# Global connection manager instance
manager = ConnectionManager()


async def get_order_tracking_auth(
    tracking_code: Optional[str] = Query(None),
    access_token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[dict] = Depends(get_current_user_optional)
) -> Optional[CustomerOrderTracking]:
    """
    Authenticate WebSocket connection for order tracking
    
    Can authenticate via:
    1. Tracking code (for anonymous tracking)
    2. Access token (for anonymous tracking)
    3. Current user session (for logged-in customers)
    """
    tracking = None
    
    # Try tracking code first
    if tracking_code:
        tracking = db.query(CustomerOrderTracking).filter(
            CustomerOrderTracking.tracking_code == tracking_code
        ).first()
    
    # Try access token
    elif access_token:
        tracking = db.query(CustomerOrderTracking).filter(
            CustomerOrderTracking.access_token == access_token
        ).first()
    
    # Try current user
    elif current_user and current_user.get("customer_id"):
        # This would need to be implemented based on your auth system
        # For now, we'll skip this option
        pass
    
    return tracking


@websocket("/ws/order-tracking")
async def websocket_order_tracking(
    websocket: WebSocket,
    tracking_code: Optional[str] = Query(None),
    access_token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time order tracking
    
    Client connects with either tracking_code or access_token
    """
    # Authenticate the connection
    tracking = await get_order_tracking_auth(
        tracking_code=tracking_code,
        access_token=access_token,
        db=db
    )
    
    if not tracking:
        await websocket.close(code=4001, reason="Invalid tracking credentials")
        return
    
    # Generate session ID
    import uuid
    session_id = str(uuid.uuid4())
    
    # Connect
    await manager.connect(websocket, tracking.order_id, session_id)
    
    # Register with tracking service
    tracking_service = OrderTrackingService(db)
    tracking_service.register_websocket(websocket, session_id, tracking.order_id)
    
    try:
        # Send initial connection success message
        await websocket.send_json({
            "type": "connection_established",
            "order_id": tracking.order_id,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Get current order status and send it
        order_info = tracking_service.get_order_tracking_by_code(tracking.tracking_code)
        if order_info:
            await websocket.send_json({
                "type": "current_status",
                "data": order_info,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for any message from client (can be ping/pong)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                # Parse message
                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid JSON"
                    })
                    continue
                
                # Handle different message types
                if message.get("type") == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                
                elif message.get("type") == "get_status":
                    # Send current status
                    order_info = tracking_service.get_order_tracking_by_code(tracking.tracking_code)
                    if order_info:
                        await websocket.send_json({
                            "type": "current_status",
                            "data": order_info,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                
            except asyncio.TimeoutError:
                # Send ping to check if client is still connected
                try:
                    await websocket.send_json({
                        "type": "ping",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except Exception:
                    # Connection is dead
                    break
                    
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from order {tracking.order_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Clean up
        manager.disconnect(websocket)
        tracking_service.unregister_websocket(websocket, session_id)


@websocket("/ws/delivery-tracking/{order_id}")
async def websocket_delivery_tracking(
    websocket: WebSocket,
    order_id: int,
    driver_token: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for delivery drivers to send location updates
    
    Requires driver authentication token
    """
    # TODO: Implement driver authentication
    # For now, we'll accept any token for development
    
    await websocket.accept()
    
    tracking_service = OrderTrackingService(db)
    
    try:
        await websocket.send_json({
            "type": "connection_established",
            "order_id": order_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        while True:
            # Receive location updates from driver
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON"
                })
                continue
            
            if message.get("type") == "location_update":
                # Create tracking event with location
                latitude = message.get("latitude")
                longitude = message.get("longitude")
                accuracy = message.get("accuracy", 0)
                
                if latitude and longitude:
                    # Create location update event
                    await tracking_service.send_delivery_location_update(
                        order_id=order_id,
                        latitude=latitude,
                        longitude=longitude,
                        accuracy=accuracy,
                        driver_id=1,  # TODO: Get from auth
                        driver_name="Driver"  # TODO: Get from auth
                    )
                    
                    # Send confirmation
                    await websocket.send_json({
                        "type": "location_update_received",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                    # Broadcast to customers tracking this order
                    await manager.broadcast_order_update(order_id, {
                        "type": "delivery_location",
                        "location": {
                            "latitude": latitude,
                            "longitude": longitude,
                            "accuracy": accuracy
                        }
                    })
            
            elif message.get("type") == "status_update":
                # Handle driver status updates (picked up, delivered, etc.)
                status = message.get("status")
                if status == "picked_up":
                    event_type = "ORDER_PICKED_UP"
                elif status == "delivered":
                    event_type = "ORDER_DELIVERED"
                else:
                    continue
                
                # Create status update event
                event = await tracking_service.create_tracking_event(
                    order_id=order_id,
                    event_type=event_type,
                    description=message.get("notes"),
                    triggered_by_type="staff",
                    triggered_by_id=1,  # TODO: Get from auth
                    triggered_by_name="Driver"  # TODO: Get from auth
                )
                
                # Send confirmation
                await websocket.send_json({
                    "type": "status_update_received",
                    "timestamp": datetime.utcnow().isoformat()
                })
                
    except WebSocketDisconnect:
        logger.info(f"Driver disconnected from order {order_id}")
    except Exception as e:
        logger.error(f"WebSocket error in delivery tracking: {e}")
        

# Helper function to broadcast updates from other parts of the system
async def broadcast_order_update(order_id: int, event_data: dict):
    """
    Broadcast an order update to all WebSocket connections
    
    This can be called from other parts of the system when order status changes
    """
    await manager.broadcast_order_update(order_id, event_data)