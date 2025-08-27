# backend/modules/pos_migration/services/websocket_manager.py

"""
WebSocket manager for real-time migration updates.
Handles broadcasting progress events to connected clients.
"""

import logging
from typing import Dict, List, Set
from fastapi import WebSocket
import asyncio

from ..schemas.migration_schemas import MigrationProgressEvent

logger = logging.getLogger(__name__)


class MigrationWebSocketManager:
    """Manages WebSocket connections for migration updates"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.active_connections: Dict[str, Set[WebSocket]] = {}
            cls._instance.connection_tasks: Dict[WebSocket, asyncio.Task] = {}
        return cls._instance
    
    async def connect(self, websocket: WebSocket, migration_id: str):
        """Add a new WebSocket connection for a migration"""
        
        await websocket.accept()
        
        if migration_id not in self.active_connections:
            self.active_connections[migration_id] = set()
        
        self.active_connections[migration_id].add(websocket)
        
        # Send initial connection message
        await websocket.send_json({
            "type": "connected",
            "migration_id": migration_id,
            "message": "Connected to migration updates"
        })
        
        logger.info(f"WebSocket connected for migration {migration_id}")
    
    def disconnect(self, websocket: WebSocket, migration_id: str):
        """Remove a WebSocket connection"""
        
        if migration_id in self.active_connections:
            self.active_connections[migration_id].discard(websocket)
            
            # Clean up empty sets
            if not self.active_connections[migration_id]:
                del self.active_connections[migration_id]
        
        # Cancel any associated tasks
        if websocket in self.connection_tasks:
            self.connection_tasks[websocket].cancel()
            del self.connection_tasks[websocket]
        
        logger.info(f"WebSocket disconnected for migration {migration_id}")
    
    async def broadcast_event(self, event: MigrationProgressEvent):
        """Broadcast an event to all connected clients for a migration"""
        
        migration_id = event.migration_id
        
        if migration_id not in self.active_connections:
            return
        
        # Convert event to dict for JSON serialization
        message = event.dict()
        
        # Send to all connected clients
        disconnected = []
        for websocket in self.active_connections[migration_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to websocket: {e}")
                disconnected.append(websocket)
        
        # Remove disconnected clients
        for websocket in disconnected:
            self.disconnect(websocket, migration_id)
    
    async def send_progress_update(
        self,
        migration_id: str,
        phase: str,
        progress: float,
        details: Dict = None
    ):
        """Send a progress update event"""
        
        event = MigrationProgressEvent(
            type="progress",
            migration_id=migration_id,
            data={
                "phase": phase,
                "progress": progress,
                "details": details or {}
            }
        )
        
        await self.broadcast_event(event)
    
    async def send_phase_change(
        self,
        migration_id: str,
        old_phase: str,
        new_phase: str,
        progress: float
    ):
        """Send a phase change event"""
        
        event = MigrationProgressEvent(
            type="phase_change",
            migration_id=migration_id,
            data={
                "old_phase": old_phase,
                "new_phase": new_phase,
                "progress": progress
            }
        )
        
        await self.broadcast_event(event)
    
    async def send_error(
        self,
        migration_id: str,
        error_code: str,
        error_message: str,
        recoverable: bool = False
    ):
        """Send an error event"""
        
        event = MigrationProgressEvent(
            type="error",
            migration_id=migration_id,
            data={
                "error_code": error_code,
                "error_message": error_message,
                "recoverable": recoverable
            }
        )
        
        await self.broadcast_event(event)
    
    async def send_warning(
        self,
        migration_id: str,
        warning_message: str,
        details: Dict = None
    ):
        """Send a warning event"""
        
        event = MigrationProgressEvent(
            type="warning",
            migration_id=migration_id,
            data={
                "message": warning_message,
                "details": details or {}
            }
        )
        
        await self.broadcast_event(event)
    
    async def send_completion(
        self,
        migration_id: str,
        summary: Dict
    ):
        """Send a completion event"""
        
        event = MigrationProgressEvent(
            type="completion",
            migration_id=migration_id,
            data={
                "status": "completed",
                "summary": summary
            }
        )
        
        await self.broadcast_event(event)
    
    def get_connection_count(self, migration_id: str) -> int:
        """Get number of active connections for a migration"""
        
        if migration_id in self.active_connections:
            return len(self.active_connections[migration_id])
        return 0
    
    def get_all_migrations(self) -> List[str]:
        """Get list of migrations with active connections"""
        
        return list(self.active_connections.keys())
    
    async def keep_alive(self, websocket: WebSocket):
        """Send periodic ping messages to keep connection alive"""
        
        try:
            while True:
                await asyncio.sleep(30)  # Ping every 30 seconds
                await websocket.send_json({"type": "ping"})
        except Exception:
            pass  # Connection closed
    
    def start_keep_alive(self, websocket: WebSocket):
        """Start keep-alive task for a connection"""
        
        task = asyncio.create_task(self.keep_alive(websocket))
        self.connection_tasks[websocket] = task


# Global instance
websocket_manager = MigrationWebSocketManager()