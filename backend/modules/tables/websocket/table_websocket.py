# backend/modules/tables/websocket/table_websocket.py

from typing import Dict, Set, Optional
from fastapi import WebSocket
from datetime import datetime
import asyncio
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from ..services.table_state_service import table_state_service
from ..models.table_models import TableStatus
from core.database_utils import get_db_context

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""

    def __init__(self):
        # Store active connections by restaurant
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        self.connection_metadata: Dict[WebSocket, Dict] = {}

    async def connect(
        self,
        websocket: WebSocket,
        restaurant_id: int,
        user_id: Optional[int] = None,
        role: Optional[str] = None,
    ):
        """Accept new connection"""
        await websocket.accept()

        if restaurant_id not in self.active_connections:
            self.active_connections[restaurant_id] = set()

        self.active_connections[restaurant_id].add(websocket)
        self.connection_metadata[websocket] = {
            "restaurant_id": restaurant_id,
            "user_id": user_id,
            "role": role,
            "connected_at": datetime.utcnow(),
        }

        logger.info(f"WebSocket connected for restaurant {restaurant_id}")

        # Send initial state
        await self.send_initial_state(websocket, restaurant_id)

    def disconnect(self, websocket: WebSocket):
        """Remove connection"""
        metadata = self.connection_metadata.get(websocket)
        if metadata:
            restaurant_id = metadata["restaurant_id"]
            if restaurant_id in self.active_connections:
                self.active_connections[restaurant_id].discard(websocket)
                if not self.active_connections[restaurant_id]:
                    del self.active_connections[restaurant_id]

            del self.connection_metadata[websocket]
            logger.info(f"WebSocket disconnected for restaurant {restaurant_id}")

    async def send_initial_state(self, websocket: WebSocket, restaurant_id: int):
        """Send initial floor state to new connection"""
        try:
            async with get_db_context() as db:
                floor_status = await table_state_service.get_floor_status(
                    db, restaurant_id
                )

                await websocket.send_json(
                    {
                        "type": "initial_state",
                        "data": floor_status,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
        except Exception as e:
            logger.error(f"Error sending initial state: {e}")

    async def broadcast_to_restaurant(
        self,
        restaurant_id: int,
        message: Dict,
        exclude_websocket: Optional[WebSocket] = None,
    ):
        """Broadcast message to all connections for a restaurant"""
        if restaurant_id not in self.active_connections:
            return

        disconnected = set()

        for websocket in self.active_connections[restaurant_id]:
            if websocket == exclude_websocket:
                continue

            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to websocket: {e}")
                disconnected.add(websocket)

        # Clean up disconnected websockets
        for websocket in disconnected:
            self.disconnect(websocket)

    async def send_table_update(
        self,
        restaurant_id: int,
        table_id: int,
        update_type: str,
        data: Dict,
        triggered_by: Optional[WebSocket] = None,
    ):
        """Send table update to all relevant connections"""
        message = {
            "type": "table_update",
            "update_type": update_type,
            "table_id": table_id,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await self.broadcast_to_restaurant(
            restaurant_id, message, exclude_websocket=triggered_by
        )

    async def send_session_update(
        self,
        restaurant_id: int,
        session_id: int,
        action: str,  # started, updated, ended
        session_data: Dict,
        triggered_by: Optional[WebSocket] = None,
    ):
        """Send session update to all relevant connections"""
        message = {
            "type": "session_update",
            "action": action,
            "session_id": session_id,
            "data": session_data,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await self.broadcast_to_restaurant(
            restaurant_id, message, exclude_websocket=triggered_by
        )

    async def send_reservation_update(
        self,
        restaurant_id: int,
        reservation_id: int,
        action: str,  # created, updated, cancelled, seated
        reservation_data: Dict,
        triggered_by: Optional[WebSocket] = None,
    ):
        """Send reservation update to all relevant connections"""
        message = {
            "type": "reservation_update",
            "action": action,
            "reservation_id": reservation_id,
            "data": reservation_data,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await self.broadcast_to_restaurant(
            restaurant_id, message, exclude_websocket=triggered_by
        )

    async def handle_client_message(self, websocket: WebSocket, message: Dict):
        """Handle incoming message from client"""
        metadata = self.connection_metadata.get(websocket)
        if not metadata:
            return

        message_type = message.get("type")

        if message_type == "ping":
            # Respond to ping
            await websocket.send_json(
                {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
            )

        elif message_type == "subscribe":
            # Handle subscription to specific updates
            subscriptions = message.get("subscriptions", [])
            metadata["subscriptions"] = subscriptions

            await websocket.send_json(
                {
                    "type": "subscription_confirmed",
                    "subscriptions": subscriptions,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

        elif message_type == "get_floor_status":
            # Send current floor status
            floor_id = message.get("floor_id")
            restaurant_id = metadata["restaurant_id"]

            async with get_db_context() as db:
                floor_status = await table_state_service.get_floor_status(
                    db, restaurant_id, floor_id
                )

                await websocket.send_json(
                    {
                        "type": "floor_status",
                        "data": floor_status,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )


# Global connection manager
manager = ConnectionManager()


async def websocket_endpoint(
    websocket: WebSocket,
    restaurant_id: int,
    user_id: Optional[int] = None,
    role: Optional[str] = None,
):
    """Main WebSocket endpoint handler"""
    await manager.connect(websocket, restaurant_id, user_id, role)

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            await manager.handle_client_message(websocket, data)

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)


# Event handlers to be called from services
async def notify_table_status_change(
    restaurant_id: int,
    table_id: int,
    old_status: TableStatus,
    new_status: TableStatus,
    reason: Optional[str] = None,
):
    """Notify clients of table status change"""
    await manager.send_table_update(
        restaurant_id,
        table_id,
        "status_changed",
        {"old_status": old_status, "new_status": new_status, "reason": reason},
    )


async def notify_session_started(
    restaurant_id: int,
    session_id: int,
    table_id: int,
    guest_count: int,
    server_name: Optional[str] = None,
):
    """Notify clients of new session"""
    await manager.send_session_update(
        restaurant_id,
        session_id,
        "started",
        {
            "table_id": table_id,
            "guest_count": guest_count,
            "server_name": server_name,
            "start_time": datetime.utcnow().isoformat(),
        },
    )


async def notify_session_ended(
    restaurant_id: int, session_id: int, table_id: int, duration_minutes: int
):
    """Notify clients of ended session"""
    await manager.send_session_update(
        restaurant_id,
        session_id,
        "ended",
        {
            "table_id": table_id,
            "duration_minutes": duration_minutes,
            "end_time": datetime.utcnow().isoformat(),
        },
    )


async def notify_reservation_created(
    restaurant_id: int,
    reservation_id: int,
    table_id: Optional[int],
    reservation_date: datetime,
    guest_count: int,
):
    """Notify clients of new reservation"""
    await manager.send_reservation_update(
        restaurant_id,
        reservation_id,
        "created",
        {
            "table_id": table_id,
            "reservation_date": reservation_date.isoformat(),
            "guest_count": guest_count,
        },
    )


async def notify_reservation_cancelled(
    restaurant_id: int,
    reservation_id: int,
    table_id: Optional[int],
    reason: Optional[str] = None,
):
    """Notify clients of cancelled reservation"""
    await manager.send_reservation_update(
        restaurant_id,
        reservation_id,
        "cancelled",
        {
            "table_id": table_id,
            "reason": reason,
            "cancelled_at": datetime.utcnow().isoformat(),
        },
    )


# Background task for periodic updates
async def periodic_status_broadcast():
    """Periodically broadcast floor status to all connected clients"""
    while True:
        try:
            # Get all restaurants with active connections
            restaurant_ids = list(manager.active_connections.keys())

            for restaurant_id in restaurant_ids:
                try:
                    # Get current floor status
                    async with get_db_context() as db:
                        floor_status = await table_state_service.get_floor_status(
                            db, restaurant_id
                        )

                    # Broadcast to all connections
                    await manager.broadcast_to_restaurant(
                        restaurant_id,
                        {
                            "type": "periodic_update",
                            "data": floor_status,
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    )
                except Exception as e:
                    logger.error(
                        f"Error in periodic broadcast for restaurant {restaurant_id}: {e}"
                    )

            # Wait before next broadcast
            await asyncio.sleep(30)  # Every 30 seconds

        except Exception as e:
            logger.error(f"Error in periodic broadcast task: {e}")
            await asyncio.sleep(5)  # Wait before retrying
