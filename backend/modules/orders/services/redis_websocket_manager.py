# backend/modules/orders/services/redis_websocket_manager.py

import redis.asyncio as redis
import json
import logging
import asyncio
from typing import Dict, List, Set, Optional, Any
from datetime import datetime, timedelta
from fastapi import WebSocket
import uuid

from core.config import settings
from core.redis_config import get_redis_client, get_redis_pubsub
from .notification_metrics import NotificationMetrics


logger = logging.getLogger(__name__)


class RedisWebSocketManager:
    """
    WebSocket connection manager with Redis pub/sub for horizontal scaling

    This allows multiple backend instances to share WebSocket state
    and broadcast messages across all connected clients
    """

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self.server_id = str(uuid.uuid4())

        # Local connection tracking
        self.local_connections: Dict[str, Dict[int, List[WebSocket]]] = {
            "order": {},  # order_id -> [websockets]
            "session": {},  # session_id -> [websockets]
        }

        # Connection metadata
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}

        # Rate limiting
        self.connection_rate_limits: Dict[str, datetime] = {}
        self.message_rate_limits: Dict[str, List[datetime]] = {}

        # Heartbeat tracking
        self.last_heartbeat: Dict[WebSocket, datetime] = {}
        self.heartbeat_interval = 30  # seconds
        self.heartbeat_timeout = 90  # seconds

        self._subscription_task = None

    async def initialize(self):
        """Initialize Redis connection and pub/sub"""
        try:
            # Use centralized Redis client that supports cluster/sentinel
            self.redis_client = await get_redis_client()

            # Test connection
            await self.redis_client.ping()

            # Create pub/sub instance
            self.pubsub = await get_redis_pubsub()

            # Subscribe to broadcast channel
            await self.pubsub.subscribe("order_tracking:broadcast")

            # Start subscription handler
            self._subscription_task = asyncio.create_task(self._handle_subscriptions())

            # Initialize metrics
            self.metrics = NotificationMetrics()

            logger.info(
                f"Redis WebSocket manager initialized with server ID: {self.server_id}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            raise

    async def close(self):
        """Close Redis connections"""
        if self._subscription_task:
            self._subscription_task.cancel()

        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()

        if self.redis_client:
            await self.redis_client.close()

    async def connect(
        self,
        websocket: WebSocket,
        order_id: int,
        session_id: str,
        user_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Accept and register a WebSocket connection

        Returns:
            True if connection accepted, False if rate limited
        """
        # Check connection rate limit
        client_ip = websocket.client.host if websocket.client else "unknown"
        if not await self._check_connection_rate_limit(client_ip):
            logger.warning(f"Connection rate limit exceeded for {client_ip}")
            return False

        # Accept connection
        await websocket.accept()

        # Store locally
        if order_id not in self.local_connections["order"]:
            self.local_connections["order"][order_id] = []
        self.local_connections["order"][order_id].append(websocket)

        if session_id not in self.local_connections["session"]:
            self.local_connections["session"][session_id] = []
        self.local_connections["session"][session_id].append(websocket)

        # Store metadata
        self.connection_metadata[websocket] = {
            "order_id": order_id,
            "session_id": session_id,
            "user_id": user_id,
            "connected_at": datetime.utcnow(),
            "server_id": self.server_id,
            "client_ip": client_ip,
            **(metadata or {}),
        }

        # Initialize heartbeat
        self.last_heartbeat[websocket] = datetime.utcnow()

        # Publish connection event to Redis
        await self._publish_connection_event("connect", order_id, session_id, user_id)

        # Store connection info in Redis
        await self._store_connection_info(order_id, session_id, user_id)

        # Update metrics
        self.metrics.record_websocket_connection(self.server_id, "connect")
        self.metrics.set_active_websocket_connections(
            self.server_id,
            sum(len(conns) for conns in self.local_connections["order"].values()),
        )

        logger.info(
            f"WebSocket connected: order={order_id}, session={session_id}, user={user_id}"
        )
        return True

    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        metadata = self.connection_metadata.get(websocket)
        if not metadata:
            return

        order_id = metadata["order_id"]
        session_id = metadata["session_id"]
        user_id = metadata.get("user_id")

        # Remove from local tracking
        if order_id in self.local_connections["order"]:
            self.local_connections["order"][order_id].remove(websocket)
            if not self.local_connections["order"][order_id]:
                del self.local_connections["order"][order_id]

        if session_id in self.local_connections["session"]:
            self.local_connections["session"][session_id].remove(websocket)
            if not self.local_connections["session"][session_id]:
                del self.local_connections["session"][session_id]

        # Clean up metadata
        del self.connection_metadata[websocket]
        if websocket in self.last_heartbeat:
            del self.last_heartbeat[websocket]

        # Publish disconnection event
        await self._publish_connection_event(
            "disconnect", order_id, session_id, user_id
        )

        # Remove connection info from Redis
        await self._remove_connection_info(order_id, session_id)

        # Update metrics
        self.metrics.record_websocket_connection(self.server_id, "disconnect")
        self.metrics.set_active_websocket_connections(
            self.server_id,
            sum(len(conns) for conns in self.local_connections["order"].values()),
        )

        logger.info(f"WebSocket disconnected: order={order_id}, session={session_id}")

    async def send_to_order(self, order_id: int, message: Dict[str, Any]):
        """Send message to all connections for an order (local and remote)"""
        # Send to local connections
        await self._send_to_local_order(order_id, message)

        # Broadcast to other servers via Redis
        await self._broadcast_message(
            {
                "type": "order_message",
                "order_id": order_id,
                "message": message,
                "server_id": self.server_id,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    async def _send_to_local_order(self, order_id: int, message: Dict[str, Any]):
        """Send message to local connections for an order"""
        if order_id not in self.local_connections["order"]:
            return

        disconnected = []
        for websocket in self.local_connections["order"][order_id]:
            try:
                # Check message rate limit for this connection
                if await self._check_message_rate_limit(websocket):
                    await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to websocket: {e}")
                disconnected.append(websocket)

        # Clean up disconnected
        for ws in disconnected:
            await self.disconnect(ws)

    async def broadcast_order_update(self, order_id: int, event: Dict[str, Any]):
        """Broadcast order update to all servers"""
        message = {
            "type": "order_update",
            "timestamp": datetime.utcnow().isoformat(),
            "order_id": order_id,
            "event": event,
        }

        await self.send_to_order(order_id, message)

    async def handle_heartbeat(self, websocket: WebSocket):
        """Handle heartbeat from client"""
        self.last_heartbeat[websocket] = datetime.utcnow()

        # Send heartbeat response
        await websocket.send_json(
            {
                "type": "heartbeat",
                "timestamp": datetime.utcnow().isoformat(),
                "server_id": self.server_id,
            }
        )

    async def check_heartbeats(self):
        """Check for stale connections and disconnect them"""
        now = datetime.utcnow()
        timeout_threshold = now - timedelta(seconds=self.heartbeat_timeout)

        stale_connections = []
        for websocket, last_beat in self.last_heartbeat.items():
            if last_beat < timeout_threshold:
                stale_connections.append(websocket)

        for ws in stale_connections:
            logger.warning(
                f"Disconnecting stale connection: {self.connection_metadata.get(ws)}"
            )
            await self.disconnect(ws)
            try:
                await ws.close(code=1001, reason="Heartbeat timeout")
            except:
                pass

    async def _broadcast_message(self, message: Dict[str, Any]):
        """Broadcast message via Redis pub/sub"""
        if self.redis_client:
            await self.redis_client.publish(
                "order_tracking:broadcast", json.dumps(message)
            )

    async def _handle_subscriptions(self):
        """Handle incoming Redis pub/sub messages"""
        try:
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    await self._process_broadcast_message(message["data"])
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error in subscription handler: {e}")

    async def _process_broadcast_message(self, data: str):
        """Process incoming broadcast message"""
        try:
            message = json.loads(data)

            # Skip messages from this server
            if message.get("server_id") == self.server_id:
                return

            # Handle different message types
            if message["type"] == "order_message":
                # Send to local connections for this order
                await self._send_to_local_order(message["order_id"], message["message"])

        except Exception as e:
            logger.error(f"Error processing broadcast message: {e}")

    async def _publish_connection_event(
        self, event_type: str, order_id: int, session_id: str, user_id: Optional[int]
    ):
        """Publish connection event to Redis"""
        if self.redis_client:
            event = {
                "type": "connection_event",
                "event": event_type,
                "order_id": order_id,
                "session_id": session_id,
                "user_id": user_id,
                "server_id": self.server_id,
                "timestamp": datetime.utcnow().isoformat(),
            }

            await self.redis_client.publish(
                "order_tracking:connections", json.dumps(event)
            )

    async def _store_connection_info(
        self, order_id: int, session_id: str, user_id: Optional[int]
    ):
        """Store connection info in Redis for cross-server visibility"""
        if self.redis_client:
            key = f"order_tracking:connections:{order_id}"
            connection_info = {
                "session_id": session_id,
                "user_id": user_id,
                "server_id": self.server_id,
                "connected_at": datetime.utcnow().isoformat(),
            }

            # Store with expiry
            await self.redis_client.hset(key, session_id, json.dumps(connection_info))
            await self.redis_client.expire(key, 3600)  # 1 hour TTL

    async def _remove_connection_info(self, order_id: int, session_id: str):
        """Remove connection info from Redis"""
        if self.redis_client:
            key = f"order_tracking:connections:{order_id}"
            await self.redis_client.hdel(key, session_id)

    async def get_connection_count(self, order_id: int) -> int:
        """Get total connection count for an order across all servers"""
        if not self.redis_client:
            # Fallback to local count
            return len(self.local_connections["order"].get(order_id, []))

        key = f"order_tracking:connections:{order_id}"
        return await self.redis_client.hlen(key)

    async def _check_connection_rate_limit(self, client_ip: str) -> bool:
        """Check if client IP is within connection rate limit"""
        # Simple rate limit: 5 connections per minute per IP
        now = datetime.utcnow()

        if client_ip in self.connection_rate_limits:
            last_connection = self.connection_rate_limits[client_ip]
            if (
                now - last_connection
            ).total_seconds() < 12:  # 5 per minute = 1 per 12 seconds
                return False

        self.connection_rate_limits[client_ip] = now

        # Clean up old entries
        cutoff = now - timedelta(minutes=5)
        self.connection_rate_limits = {
            ip: time
            for ip, time in self.connection_rate_limits.items()
            if time > cutoff
        }

        return True

    async def _check_message_rate_limit(self, websocket: WebSocket) -> bool:
        """Check if connection is within message rate limit"""
        # Rate limit: 60 messages per minute per connection
        metadata = self.connection_metadata.get(websocket)
        if not metadata:
            return True

        session_id = metadata["session_id"]
        now = datetime.utcnow()

        if session_id not in self.message_rate_limits:
            self.message_rate_limits[session_id] = []

        # Remove old timestamps
        cutoff = now - timedelta(minutes=1)
        self.message_rate_limits[session_id] = [
            ts for ts in self.message_rate_limits[session_id] if ts > cutoff
        ]

        # Check limit
        if len(self.message_rate_limits[session_id]) >= 60:
            return False

        self.message_rate_limits[session_id].append(now)
        return True


# Background task to check heartbeats
async def monitor_websocket_health(manager: RedisWebSocketManager):
    """Background task to monitor WebSocket connection health"""
    while True:
        try:
            await manager.check_heartbeats()
            await asyncio.sleep(30)  # Check every 30 seconds
        except Exception as e:
            logger.error(f"Error monitoring WebSocket health: {e}")
            await asyncio.sleep(60)


# Global manager instance
redis_ws_manager = RedisWebSocketManager()


# Initialize on startup
async def startup_redis_websocket():
    """Initialize Redis WebSocket manager on startup"""
    await redis_ws_manager.initialize()

    # Start health monitor
    asyncio.create_task(monitor_websocket_health(redis_ws_manager))


# Cleanup on shutdown
async def shutdown_redis_websocket():
    """Cleanup Redis WebSocket manager on shutdown"""
    await redis_ws_manager.close()
