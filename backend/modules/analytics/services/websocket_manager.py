# backend/modules/analytics/services/websocket_manager.py

import asyncio
import json
import logging
from typing import Dict, Set, List, Any, Optional
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from dataclasses import dataclass
import uuid
from enum import Enum

from .realtime_metrics_service import (
    DashboardSnapshot,
    RealtimeMetric,
    realtime_metrics_service,
)
from ..models.analytics_models import AlertRule
from ..services.permissions_service import PermissionsService, AnalyticsPermission

logger = logging.getLogger(__name__)


class WebSocketMessageType(str, Enum):
    """Types of WebSocket messages"""

    DASHBOARD_UPDATE = "dashboard_update"
    METRIC_UPDATE = "metric_update"
    ALERT_NOTIFICATION = "alert_notification"
    SYSTEM_STATUS = "system_status"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    SUBSCRIPTION_CONFIRM = "subscription_confirm"


@dataclass
class WebSocketMessage:
    """Structure for WebSocket messages"""

    type: WebSocketMessageType
    data: Dict[str, Any]
    timestamp: datetime
    message_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "message_id": self.message_id,
        }


@dataclass
class WebSocketClient:
    """Represents a connected WebSocket client"""

    websocket: WebSocket
    client_id: str
    user_id: Optional[int]
    user_permissions: List[str]
    subscriptions: Set[str]
    connected_at: datetime
    last_heartbeat: datetime

    def has_permission(self, permission: str) -> bool:
        """Check if client has specific permission"""
        return permission in self.user_permissions


class WebSocketManager:
    """Manages WebSocket connections for real-time analytics updates"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocketClient] = {}
        self.dashboard_subscribers: Set[str] = set()
        self.metric_subscribers: Dict[str, Set[str]] = {}  # metric_name -> client_ids
        self.alert_subscribers: Set[str] = set()
        self.heartbeat_interval = 30  # seconds
        self.cleanup_interval = 60  # seconds
        self.is_running = False

    async def start_manager(self):
        """Start the WebSocket manager with background tasks"""
        if self.is_running:
            return

        self.is_running = True
        logger.info("Starting WebSocket manager")

        # Subscribe to real-time metrics service
        realtime_metrics_service.subscribe_to_updates(self._handle_dashboard_update)

        # Start background tasks
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        cleanup_task = asyncio.create_task(self._cleanup_loop())

        await asyncio.gather(heartbeat_task, cleanup_task, return_exceptions=True)

    async def stop_manager(self):
        """Stop the WebSocket manager"""
        self.is_running = False
        logger.info("Stopping WebSocket manager")

        # Disconnect all clients
        for client_id in list(self.active_connections.keys()):
            await self.disconnect_client(client_id)

        # Unsubscribe from metrics service
        realtime_metrics_service.unsubscribe_from_updates(self._handle_dashboard_update)

    async def connect_client(
        self,
        websocket: WebSocket,
        user_id: Optional[int] = None,
        user_permissions: Optional[List[str]] = None,
    ) -> str:
        """Connect a new WebSocket client"""

        client_id = str(uuid.uuid4())

        try:
            await websocket.accept()

            client = WebSocketClient(
                websocket=websocket,
                client_id=client_id,
                user_id=user_id,
                user_permissions=user_permissions or [],
                subscriptions=set(),
                connected_at=datetime.now(),
                last_heartbeat=datetime.now(),
            )

            self.active_connections[client_id] = client

            # Send connection confirmation
            await self._send_message(
                client_id,
                WebSocketMessage(
                    type=WebSocketMessageType.SYSTEM_STATUS,
                    data={
                        "status": "connected",
                        "client_id": client_id,
                        "server_time": datetime.now().isoformat(),
                        "permissions": user_permissions or [],
                    },
                    timestamp=datetime.now(),
                    message_id=str(uuid.uuid4()),
                ),
            )

            logger.info(f"WebSocket client connected: {client_id} (user: {user_id})")
            return client_id

        except Exception as e:
            logger.error(f"Error connecting WebSocket client: {e}")
            if client_id in self.active_connections:
                del self.active_connections[client_id]
            raise

    async def disconnect_client(self, client_id: str):
        """Disconnect a WebSocket client"""

        if client_id not in self.active_connections:
            return

        client = self.active_connections[client_id]

        try:
            # Remove from all subscriptions
            self.dashboard_subscribers.discard(client_id)
            self.alert_subscribers.discard(client_id)

            for metric_clients in self.metric_subscribers.values():
                metric_clients.discard(client_id)

            # Close WebSocket connection
            if not client.websocket.client_state.DISCONNECTED:
                await client.websocket.close()

        except Exception as e:
            logger.error(f"Error disconnecting client {client_id}: {e}")
        finally:
            # Remove from active connections
            del self.active_connections[client_id]
            logger.info(f"WebSocket client disconnected: {client_id}")

    async def handle_client_message(self, client_id: str, message: str):
        """Handle incoming message from client"""

        if client_id not in self.active_connections:
            return

        client = self.active_connections[client_id]

        try:
            data = json.loads(message)
            message_type = data.get("type")
            payload = data.get("data", {})

            if message_type == "subscribe":
                await self._handle_subscription(client_id, payload)
            elif message_type == "unsubscribe":
                await self._handle_unsubscription(client_id, payload)
            elif message_type == "heartbeat":
                await self._handle_heartbeat(client_id)
            elif message_type == "get_current_data":
                await self._handle_current_data_request(client_id, payload)
            else:
                await self._send_error(
                    client_id, f"Unknown message type: {message_type}"
                )

        except json.JSONDecodeError:
            await self._send_error(client_id, "Invalid JSON message")
        except Exception as e:
            logger.error(f"Error handling client message: {e}")
            await self._send_error(client_id, "Internal server error")

    async def broadcast_dashboard_update(self, snapshot: DashboardSnapshot):
        """Broadcast dashboard update to all subscribed clients"""

        if not self.dashboard_subscribers:
            return

        message = WebSocketMessage(
            type=WebSocketMessageType.DASHBOARD_UPDATE,
            data=snapshot.to_dict(),
            timestamp=datetime.now(),
            message_id=str(uuid.uuid4()),
        )

        # Send to all dashboard subscribers
        tasks = []
        for client_id in self.dashboard_subscribers.copy():
            if self._client_has_permission(
                client_id, AnalyticsPermission.VIEW_DASHBOARD
            ):
                tasks.append(self._send_message(client_id, message))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.debug(f"Dashboard update sent to {len(tasks)} clients")

    async def broadcast_metric_update(self, metric: RealtimeMetric):
        """Broadcast specific metric update to subscribed clients"""

        metric_subscribers = self.metric_subscribers.get(metric.metric_name, set())
        if not metric_subscribers:
            return

        message = WebSocketMessage(
            type=WebSocketMessageType.METRIC_UPDATE,
            data=metric.to_dict(),
            timestamp=datetime.now(),
            message_id=str(uuid.uuid4()),
        )

        # Send to metric subscribers
        tasks = []
        for client_id in metric_subscribers.copy():
            if self._client_has_permission(
                client_id, AnalyticsPermission.VIEW_SALES_REPORTS
            ):
                tasks.append(self._send_message(client_id, message))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.debug(
                f"Metric update '{metric.metric_name}' sent to {len(tasks)} clients"
            )

    async def broadcast_alert_notification(self, alert_data: Dict[str, Any]):
        """Broadcast alert notification to subscribed clients"""

        if not self.alert_subscribers:
            return

        message = WebSocketMessage(
            type=WebSocketMessageType.ALERT_NOTIFICATION,
            data=alert_data,
            timestamp=datetime.now(),
            message_id=str(uuid.uuid4()),
        )

        # Send to alert subscribers
        tasks = []
        for client_id in self.alert_subscribers.copy():
            if self._client_has_permission(
                client_id, AnalyticsPermission.CREATE_ALERTS
            ):
                tasks.append(self._send_message(client_id, message))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.debug(f"Alert notification sent to {len(tasks)} clients")

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get WebSocket connection statistics"""

        stats = {
            "total_connections": len(self.active_connections),
            "dashboard_subscribers": len(self.dashboard_subscribers),
            "alert_subscribers": len(self.alert_subscribers),
            "metric_subscribers": {
                metric: len(subscribers)
                for metric, subscribers in self.metric_subscribers.items()
            },
            "connections_by_user": {},
            "uptime_seconds": 0,
        }

        # Group connections by user
        for client in self.active_connections.values():
            user_id = client.user_id or "anonymous"
            if user_id not in stats["connections_by_user"]:
                stats["connections_by_user"][user_id] = 0
            stats["connections_by_user"][user_id] += 1

        return stats

    # Private methods

    async def _handle_subscription(self, client_id: str, payload: Dict[str, Any]):
        """Handle subscription request from client"""

        client = self.active_connections.get(client_id)
        if not client:
            return

        subscription_type = payload.get("subscription_type")

        try:
            if subscription_type == "dashboard":
                if self._client_has_permission(
                    client_id, AnalyticsPermission.VIEW_DASHBOARD
                ):
                    self.dashboard_subscribers.add(client_id)
                    client.subscriptions.add("dashboard")

                    # Send current dashboard data
                    current_snapshot = (
                        await realtime_metrics_service.get_current_dashboard_snapshot()
                    )
                    await self._send_message(
                        client_id,
                        WebSocketMessage(
                            type=WebSocketMessageType.DASHBOARD_UPDATE,
                            data=current_snapshot.to_dict(),
                            timestamp=datetime.now(),
                            message_id=str(uuid.uuid4()),
                        ),
                    )
                else:
                    await self._send_error(
                        client_id, "Insufficient permissions for dashboard subscription"
                    )
                    return

            elif subscription_type == "metrics":
                if self._client_has_permission(
                    client_id, AnalyticsPermission.VIEW_SALES_REPORTS
                ):
                    metrics = payload.get("metrics", [])
                    for metric_name in metrics:
                        if metric_name not in self.metric_subscribers:
                            self.metric_subscribers[metric_name] = set()
                        self.metric_subscribers[metric_name].add(client_id)
                        client.subscriptions.add(f"metric:{metric_name}")
                else:
                    await self._send_error(
                        client_id, "Insufficient permissions for metrics subscription"
                    )
                    return

            elif subscription_type == "alerts":
                if self._client_has_permission(
                    client_id, AnalyticsPermission.CREATE_ALERTS
                ):
                    self.alert_subscribers.add(client_id)
                    client.subscriptions.add("alerts")
                else:
                    await self._send_error(
                        client_id, "Insufficient permissions for alerts subscription"
                    )
                    return

            else:
                await self._send_error(
                    client_id, f"Unknown subscription type: {subscription_type}"
                )
                return

            # Send subscription confirmation
            await self._send_message(
                client_id,
                WebSocketMessage(
                    type=WebSocketMessageType.SUBSCRIPTION_CONFIRM,
                    data={
                        "subscription_type": subscription_type,
                        "status": "subscribed",
                        "details": payload,
                    },
                    timestamp=datetime.now(),
                    message_id=str(uuid.uuid4()),
                ),
            )

            logger.info(f"Client {client_id} subscribed to {subscription_type}")

        except Exception as e:
            logger.error(f"Error handling subscription: {e}")
            await self._send_error(client_id, "Subscription failed")

    async def _handle_unsubscription(self, client_id: str, payload: Dict[str, Any]):
        """Handle unsubscription request from client"""

        client = self.active_connections.get(client_id)
        if not client:
            return

        subscription_type = payload.get("subscription_type")

        if subscription_type == "dashboard":
            self.dashboard_subscribers.discard(client_id)
            client.subscriptions.discard("dashboard")

        elif subscription_type == "metrics":
            metrics = payload.get("metrics", [])
            for metric_name in metrics:
                if metric_name in self.metric_subscribers:
                    self.metric_subscribers[metric_name].discard(client_id)
                client.subscriptions.discard(f"metric:{metric_name}")

        elif subscription_type == "alerts":
            self.alert_subscribers.discard(client_id)
            client.subscriptions.discard("alerts")

        logger.info(f"Client {client_id} unsubscribed from {subscription_type}")

    async def _handle_heartbeat(self, client_id: str):
        """Handle heartbeat from client"""

        client = self.active_connections.get(client_id)
        if client:
            client.last_heartbeat = datetime.now()

            # Send heartbeat response
            await self._send_message(
                client_id,
                WebSocketMessage(
                    type=WebSocketMessageType.HEARTBEAT,
                    data={"status": "pong", "server_time": datetime.now().isoformat()},
                    timestamp=datetime.now(),
                    message_id=str(uuid.uuid4()),
                ),
            )

    async def _handle_current_data_request(
        self, client_id: str, payload: Dict[str, Any]
    ):
        """Handle request for current data"""

        data_type = payload.get("data_type")

        try:
            if data_type == "dashboard":
                if self._client_has_permission(
                    client_id, AnalyticsPermission.VIEW_DASHBOARD
                ):
                    snapshot = (
                        await realtime_metrics_service.get_current_dashboard_snapshot()
                    )
                    await self._send_message(
                        client_id,
                        WebSocketMessage(
                            type=WebSocketMessageType.DASHBOARD_UPDATE,
                            data=snapshot.to_dict(),
                            timestamp=datetime.now(),
                            message_id=str(uuid.uuid4()),
                        ),
                    )
                else:
                    await self._send_error(client_id, "Insufficient permissions")

            elif data_type == "metric":
                metric_name = payload.get("metric_name")
                if metric_name and self._client_has_permission(
                    client_id, AnalyticsPermission.VIEW_SALES_REPORTS
                ):
                    metric = await realtime_metrics_service.get_realtime_metric(
                        metric_name
                    )
                    if metric:
                        await self._send_message(
                            client_id,
                            WebSocketMessage(
                                type=WebSocketMessageType.METRIC_UPDATE,
                                data=metric.to_dict(),
                                timestamp=datetime.now(),
                                message_id=str(uuid.uuid4()),
                            ),
                        )
                    else:
                        await self._send_error(
                            client_id, f"Metric '{metric_name}' not found"
                        )
                else:
                    await self._send_error(
                        client_id, "Invalid metric request or insufficient permissions"
                    )

        except Exception as e:
            logger.error(f"Error handling current data request: {e}")
            await self._send_error(client_id, "Failed to retrieve current data")

    async def _send_message(self, client_id: str, message: WebSocketMessage):
        """Send message to specific client"""

        client = self.active_connections.get(client_id)
        if not client:
            return

        try:
            await client.websocket.send_text(json.dumps(message.to_dict(), default=str))
        except Exception as e:
            logger.error(f"Error sending message to client {client_id}: {e}")
            # Remove client if connection is broken
            await self.disconnect_client(client_id)

    async def _send_error(self, client_id: str, error_message: str):
        """Send error message to client"""

        error_msg = WebSocketMessage(
            type=WebSocketMessageType.ERROR,
            data={"error": error_message},
            timestamp=datetime.now(),
            message_id=str(uuid.uuid4()),
        )

        await self._send_message(client_id, error_msg)

    def _client_has_permission(
        self, client_id: str, permission: AnalyticsPermission
    ) -> bool:
        """Check if client has required permission"""

        client = self.active_connections.get(client_id)
        if not client:
            return False

        return permission.value in client.user_permissions

    async def _handle_dashboard_update(self, snapshot: DashboardSnapshot):
        """Handle dashboard update from metrics service"""
        await self.broadcast_dashboard_update(snapshot)

    async def _heartbeat_loop(self):
        """Background loop for sending heartbeats and checking client health"""

        while self.is_running:
            try:
                current_time = datetime.now()
                stale_clients = []

                # Check for stale clients
                for client_id, client in self.active_connections.items():
                    time_since_heartbeat = (
                        current_time - client.last_heartbeat
                    ).total_seconds()

                    if time_since_heartbeat > (
                        self.heartbeat_interval * 3
                    ):  # 3x heartbeat interval
                        stale_clients.append(client_id)

                # Remove stale clients
                for client_id in stale_clients:
                    logger.warning(f"Removing stale client: {client_id}")
                    await self.disconnect_client(client_id)

                # Send heartbeat to remaining clients
                heartbeat_tasks = []
                for client_id in list(self.active_connections.keys()):
                    task = self._send_message(
                        client_id,
                        WebSocketMessage(
                            type=WebSocketMessageType.HEARTBEAT,
                            data={
                                "status": "ping",
                                "server_time": current_time.isoformat(),
                            },
                            timestamp=current_time,
                            message_id=str(uuid.uuid4()),
                        ),
                    )
                    heartbeat_tasks.append(task)

                if heartbeat_tasks:
                    await asyncio.gather(*heartbeat_tasks, return_exceptions=True)

            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")

            await asyncio.sleep(self.heartbeat_interval)

    async def _cleanup_loop(self):
        """Background loop for cleanup tasks"""

        while self.is_running:
            try:
                # Clean up empty metric subscriptions
                empty_metrics = []
                for metric_name, subscribers in self.metric_subscribers.items():
                    if not subscribers:
                        empty_metrics.append(metric_name)

                for metric_name in empty_metrics:
                    del self.metric_subscribers[metric_name]

                if empty_metrics:
                    logger.debug(
                        f"Cleaned up {len(empty_metrics)} empty metric subscriptions"
                    )

            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

            await asyncio.sleep(self.cleanup_interval)


# Global WebSocket manager instance
websocket_manager = WebSocketManager()


# Utility functions
async def get_websocket_stats() -> Dict[str, Any]:
    """Get WebSocket connection statistics"""
    return websocket_manager.get_connection_stats()


async def broadcast_alert(alert_data: Dict[str, Any]):
    """Broadcast alert to all subscribed clients"""
    await websocket_manager.broadcast_alert_notification(alert_data)


async def broadcast_metric(metric: RealtimeMetric):
    """Broadcast metric update to subscribed clients"""
    await websocket_manager.broadcast_metric_update(metric)
