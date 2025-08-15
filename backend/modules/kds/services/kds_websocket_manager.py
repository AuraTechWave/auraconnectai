# backend/modules/kds/services/kds_websocket_manager.py

"""
WebSocket manager for real-time KDS updates.
"""

from fastapi import WebSocket
from typing import Dict, List, Set
import json
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class KDSWebSocketManager:
    """Manages WebSocket connections for KDS real-time updates"""

    def __init__(self):
        # Dictionary mapping station_id to list of WebSocket connections
        self.active_connections: Dict[int, List[WebSocket]] = {}
        # Lock for thread-safe operations
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, station_id: int):
        """Connect a WebSocket to a station"""
        await websocket.accept()

        async with self.lock:
            if station_id not in self.active_connections:
                self.active_connections[station_id] = []
            self.active_connections[station_id].append(websocket)

        logger.info(
            f"WebSocket connected for station {station_id}. "
            f"Total connections: {len(self.active_connections.get(station_id, []))}"
        )

    def disconnect(self, websocket: WebSocket, station_id: int):
        """Disconnect a WebSocket from a station"""
        try:
            if station_id in self.active_connections:
                self.active_connections[station_id].remove(websocket)
                if not self.active_connections[station_id]:
                    del self.active_connections[station_id]

            logger.info(f"WebSocket disconnected for station {station_id}")
        except ValueError:
            logger.warning(
                f"WebSocket not found in active connections for station {station_id}"
            )

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a message to a specific WebSocket"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {str(e)}")

    async def broadcast_to_station(self, station_id: int, message: dict):
        """Broadcast a message to all connections for a station"""
        if station_id not in self.active_connections:
            return

        dead_connections = []
        message_text = json.dumps(message, default=str)

        # Send to all connections for this station
        for websocket in self.active_connections[station_id]:
            try:
                await websocket.send_text(message_text)
            except Exception as e:
                logger.error(f"Error broadcasting to station {station_id}: {str(e)}")
                dead_connections.append(websocket)

        # Clean up dead connections
        for websocket in dead_connections:
            self.disconnect(websocket, station_id)

    async def broadcast_to_all_stations(self, message: dict):
        """Broadcast a message to all connected stations"""
        tasks = []
        for station_id in self.active_connections:
            tasks.append(self.broadcast_to_station(station_id, message))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_new_item(self, station_id: int, data: dict):
        """Broadcast a new item to a station"""
        message = {
            "type": "new_item",
            "station_id": station_id,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self.broadcast_to_station(station_id, message)

    async def broadcast_item_update(self, station_id: int, item_id: int, data: dict):
        """Broadcast an item update to a station"""
        message = {
            "type": "update_item",
            "station_id": station_id,
            "item_id": item_id,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self.broadcast_to_station(station_id, message)

    async def broadcast_item_removal(self, station_id: int, item_id: int):
        """Broadcast item removal to a station"""
        message = {
            "type": "remove_item",
            "station_id": station_id,
            "item_id": item_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self.broadcast_to_station(station_id, message)

    async def broadcast_station_update(self, station_id: int, data: dict):
        """Broadcast station update"""
        message = {
            "type": "station_update",
            "station_id": station_id,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self.broadcast_to_station(station_id, message)

    async def send_heartbeat(self, station_id: int):
        """Send heartbeat to all connections for a station"""
        message = {"type": "heartbeat", "timestamp": datetime.utcnow().isoformat()}
        await self.broadcast_to_station(station_id, message)

    def get_connection_count(self, station_id: int) -> int:
        """Get number of active connections for a station"""
        return len(self.active_connections.get(station_id, []))

    def get_all_connection_counts(self) -> Dict[int, int]:
        """Get connection counts for all stations"""
        return {
            station_id: len(connections)
            for station_id, connections in self.active_connections.items()
        }

    async def close_all_connections(self):
        """Close all WebSocket connections"""
        tasks = []
        for station_id, connections in self.active_connections.items():
            for websocket in connections:
                try:
                    tasks.append(websocket.close())
                except Exception as e:
                    logger.error(f"Error closing WebSocket: {str(e)}")

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self.active_connections.clear()
        logger.info("All WebSocket connections closed")


# Global instance
kds_websocket_manager = KDSWebSocketManager()
