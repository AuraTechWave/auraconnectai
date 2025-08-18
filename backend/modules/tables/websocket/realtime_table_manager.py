"""
Enhanced WebSocket manager for real-time table status updates.

This module provides comprehensive real-time table management with
live occupancy status, turn time tracking, and heat map visualization.
"""

from typing import Dict, Set, Optional, List, Any
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime, timedelta
import asyncio
import json
import logging
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from ..models.table_models import Table, TableSession, TableStatus, TableReservation
from ..services.table_analytics_service import TableAnalyticsService
from core.database_utils import get_db_context

logger = logging.getLogger(__name__)


class UpdateType(str, Enum):
    """Types of real-time updates"""
    TABLE_STATUS = "table_status"
    OCCUPANCY_UPDATE = "occupancy_update"
    RESERVATION_UPDATE = "reservation_update"
    TURN_TIME_UPDATE = "turn_time_update"
    HEAT_MAP_UPDATE = "heat_map_update"
    ANALYTICS_UPDATE = "analytics_update"
    ALERT = "alert"


class RealtimeTableManager:
    """Enhanced manager for real-time table status updates"""
    
    def __init__(self):
        # WebSocket connections by restaurant and floor
        self.connections: Dict[int, Dict[int, Set[WebSocket]]] = {}
        self.connection_metadata: Dict[WebSocket, Dict] = {}
        
        # Cache for frequently accessed data
        self.table_status_cache: Dict[int, Dict[int, Dict]] = {}
        self.turn_time_cache: Dict[int, Dict] = {}
        
        # Background tasks
        self.update_tasks: Dict[int, asyncio.Task] = {}
        self.analytics_service = TableAnalyticsService()
        
    async def connect(
        self,
        websocket: WebSocket,
        restaurant_id: int,
        floor_id: Optional[int] = None,
        user_id: Optional[int] = None,
        role: Optional[str] = None
    ):
        """Accept and register new WebSocket connection"""
        await websocket.accept()
        
        # Initialize restaurant connection dict if needed
        if restaurant_id not in self.connections:
            self.connections[restaurant_id] = {}
            self.table_status_cache[restaurant_id] = {}
            
        # Store connection by floor (0 for all floors)
        floor_key = floor_id or 0
        if floor_key not in self.connections[restaurant_id]:
            self.connections[restaurant_id][floor_key] = set()
            
        self.connections[restaurant_id][floor_key].add(websocket)
        
        # Store metadata
        self.connection_metadata[websocket] = {
            "restaurant_id": restaurant_id,
            "floor_id": floor_id,
            "user_id": user_id,
            "role": role,
            "connected_at": datetime.utcnow(),
            "last_heartbeat": datetime.utcnow()
        }
        
        logger.info(
            f"WebSocket connected: restaurant={restaurant_id}, "
            f"floor={floor_id}, user={user_id}"
        )
        
        # Send initial state
        await self._send_initial_state(websocket, restaurant_id, floor_id)
        
        # Start background update task if not running
        if restaurant_id not in self.update_tasks:
            task = asyncio.create_task(self._background_updates(restaurant_id))
            self.update_tasks[restaurant_id] = task
            
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        metadata = self.connection_metadata.get(websocket)
        if not metadata:
            return
            
        restaurant_id = metadata["restaurant_id"]
        floor_id = metadata["floor_id"] or 0
        
        # Remove from connections
        if (restaurant_id in self.connections and 
            floor_id in self.connections[restaurant_id]):
            self.connections[restaurant_id][floor_id].discard(websocket)
            
            # Clean up empty structures
            if not self.connections[restaurant_id][floor_id]:
                del self.connections[restaurant_id][floor_id]
            if not self.connections[restaurant_id]:
                del self.connections[restaurant_id]
                # Cancel background task
                if restaurant_id in self.update_tasks:
                    self.update_tasks[restaurant_id].cancel()
                    del self.update_tasks[restaurant_id]
                    
        del self.connection_metadata[websocket]
        logger.info(f"WebSocket disconnected: restaurant={restaurant_id}")
        
    async def _send_initial_state(
        self, 
        websocket: WebSocket, 
        restaurant_id: int,
        floor_id: Optional[int]
    ):
        """Send initial table state to new connection"""
        try:
            async with get_db_context() as db:
                # Get table statuses
                table_status = await self._get_table_status(
                    db, restaurant_id, floor_id
                )
                
                # Get current analytics
                analytics = await self.analytics_service.get_current_analytics(
                    db, restaurant_id, floor_id
                )
                
                # Get heat map data
                heat_map = await self._get_heat_map_data(
                    db, restaurant_id, floor_id
                )
                
                await websocket.send_json({
                    "type": "initial_state",
                    "data": {
                        "tables": table_status,
                        "analytics": analytics,
                        "heat_map": heat_map,
                        "server_time": datetime.utcnow().isoformat()
                    }
                })
                
        except Exception as e:
            logger.error(f"Error sending initial state: {e}")
            await websocket.send_json({
                "type": "error",
                "message": "Failed to load initial state"
            })
            
    async def broadcast_table_update(
        self,
        restaurant_id: int,
        table_id: int,
        update_type: UpdateType,
        data: Dict[str, Any],
        floor_id: Optional[int] = None
    ):
        """Broadcast table update to relevant connections"""
        if restaurant_id not in self.connections:
            return
            
        message = {
            "type": update_type.value,
            "table_id": table_id,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Send to connections watching specific floor
        if floor_id and floor_id in self.connections[restaurant_id]:
            await self._send_to_connections(
                self.connections[restaurant_id][floor_id], 
                message
            )
            
        # Also send to connections watching all floors
        if 0 in self.connections[restaurant_id]:
            await self._send_to_connections(
                self.connections[restaurant_id][0], 
                message
            )
            
    async def _send_to_connections(
        self, 
        connections: Set[WebSocket], 
        message: Dict
    ):
        """Send message to multiple connections"""
        disconnected = set()
        
        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to websocket: {e}")
                disconnected.add(websocket)
                
        # Clean up disconnected sockets
        for websocket in disconnected:
            self.disconnect(websocket)
            
    async def _background_updates(self, restaurant_id: int):
        """Background task to send periodic updates"""
        logger.info(f"Starting background updates for restaurant {restaurant_id}")
        
        try:
            while restaurant_id in self.connections:
                async with get_db_context() as db:
                    # Update turn times
                    await self._update_turn_times(db, restaurant_id)
                    
                    # Update heat map
                    await self._update_heat_map(db, restaurant_id)
                    
                    # Check for alerts
                    await self._check_alerts(db, restaurant_id)
                    
                # Wait before next update
                await asyncio.sleep(30)  # Update every 30 seconds
                
        except asyncio.CancelledError:
            logger.info(f"Background updates cancelled for restaurant {restaurant_id}")
        except Exception as e:
            logger.error(f"Error in background updates: {e}")
            
    async def _get_table_status(
        self,
        db: AsyncSession,
        restaurant_id: int,
        floor_id: Optional[int]
    ) -> List[Dict]:
        """Get current status of all tables"""
        query = (
            select(Table)
            .options(selectinload(Table.current_session))
            .where(Table.restaurant_id == restaurant_id)
        )
        
        if floor_id:
            query = query.where(Table.floor_id == floor_id)
            
        result = await db.execute(query)
        tables = result.scalars().all()
        
        table_data = []
        for table in tables:
            session = table.current_session
            
            # Calculate turn time if occupied
            turn_time = None
            if session:
                turn_time = (datetime.utcnow() - session.start_time).total_seconds() / 60
                
            table_data.append({
                "id": table.id,
                "table_number": table.table_number,
                "floor_id": table.floor_id,
                "status": table.status.value,
                "capacity": {
                    "min": table.min_capacity,
                    "max": table.max_capacity,
                    "preferred": table.preferred_capacity
                },
                "position": {
                    "x": table.position_x,
                    "y": table.position_y,
                    "width": table.width,
                    "height": table.height,
                    "rotation": table.rotation
                },
                "current_session": {
                    "session_id": session.id,
                    "guest_count": session.guest_count,
                    "start_time": session.start_time.isoformat(),
                    "turn_time_minutes": round(turn_time, 1) if turn_time else None,
                    "server_id": session.server_id,
                    "order_id": session.order_id
                } if session else None,
                "features": {
                    "has_power": table.has_power_outlet,
                    "wheelchair_accessible": table.is_wheelchair_accessible,
                    "by_window": table.is_by_window,
                    "is_private": table.is_private
                }
            })
            
        return table_data
        
    async def _update_turn_times(
        self,
        db: AsyncSession,
        restaurant_id: int
    ):
        """Update and broadcast turn time analytics"""
        # Get active sessions with turn times
        query = (
            select(
                TableSession.table_id,
                func.extract('epoch', func.current_timestamp() - TableSession.start_time) / 60
            )
            .join(Table)
            .where(
                and_(
                    Table.restaurant_id == restaurant_id,
                    TableSession.end_time.is_(None)
                )
            )
        )
        
        result = await db.execute(query)
        turn_times = {
            table_id: round(minutes, 1) 
            for table_id, minutes in result.all()
        }
        
        # Calculate average turn time
        avg_turn_time = (
            sum(turn_times.values()) / len(turn_times) 
            if turn_times else 0
        )
        
        # Broadcast update
        for floor_connections in self.connections.get(restaurant_id, {}).values():
            await self._send_to_connections(
                floor_connections,
                {
                    "type": UpdateType.TURN_TIME_UPDATE.value,
                    "data": {
                        "turn_times": turn_times,
                        "average_turn_time": round(avg_turn_time, 1),
                        "active_tables": len(turn_times)
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
    async def _get_heat_map_data(
        self,
        db: AsyncSession,
        restaurant_id: int,
        floor_id: Optional[int]
    ) -> Dict:
        """Generate heat map data for table occupancy"""
        # Get historical occupancy data for the past 7 days
        since = datetime.utcnow() - timedelta(days=7)
        
        query = (
            select(
                Table.id,
                Table.table_number,
                Table.position_x,
                Table.position_y,
                func.count(TableSession.id).label('session_count'),
                func.avg(
                    func.extract(
                        'epoch', 
                        func.coalesce(
                            TableSession.end_time, 
                            func.current_timestamp()
                        ) - TableSession.start_time
                    ) / 60
                ).label('avg_duration')
            )
            .outerjoin(
                TableSession,
                and_(
                    Table.id == TableSession.table_id,
                    TableSession.start_time >= since
                )
            )
            .where(Table.restaurant_id == restaurant_id)
            .group_by(Table.id, Table.table_number, Table.position_x, Table.position_y)
        )
        
        if floor_id:
            query = query.where(Table.floor_id == floor_id)
            
        result = await db.execute(query)
        
        heat_map_data = []
        max_occupancy = 0
        
        for row in result.all():
            occupancy_score = row.session_count * (row.avg_duration or 0)
            max_occupancy = max(max_occupancy, occupancy_score)
            
            heat_map_data.append({
                "table_id": row.id,
                "table_number": row.table_number,
                "x": row.position_x,
                "y": row.position_y,
                "occupancy_score": occupancy_score,
                "session_count": row.session_count,
                "avg_duration_minutes": round(row.avg_duration or 0, 1)
            })
            
        # Normalize scores
        if max_occupancy > 0:
            for item in heat_map_data:
                item["heat_intensity"] = item["occupancy_score"] / max_occupancy
                
        return {
            "data": heat_map_data,
            "period_days": 7,
            "max_occupancy_score": max_occupancy
        }
        
    async def _update_heat_map(
        self,
        db: AsyncSession,
        restaurant_id: int
    ):
        """Update and broadcast heat map data"""
        heat_map = await self._get_heat_map_data(db, restaurant_id, None)
        
        # Broadcast to all connections
        for floor_connections in self.connections.get(restaurant_id, {}).values():
            await self._send_to_connections(
                floor_connections,
                {
                    "type": UpdateType.HEAT_MAP_UPDATE.value,
                    "data": heat_map,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
    async def _check_alerts(
        self,
        db: AsyncSession,
        restaurant_id: int
    ):
        """Check for and broadcast alerts"""
        alerts = []
        
        # Check for tables exceeding average turn time
        avg_turn_time = await self.analytics_service.get_average_turn_time(
            db, restaurant_id
        )
        
        if avg_turn_time:
            query = (
                select(Table, TableSession)
                .join(TableSession)
                .where(
                    and_(
                        Table.restaurant_id == restaurant_id,
                        TableSession.end_time.is_(None),
                        func.extract(
                            'epoch', 
                            func.current_timestamp() - TableSession.start_time
                        ) / 60 > avg_turn_time * 1.5  # 50% over average
                    )
                )
            )
            
            result = await db.execute(query)
            
            for table, session in result.all():
                turn_time = (
                    datetime.utcnow() - session.start_time
                ).total_seconds() / 60
                
                alerts.append({
                    "type": "long_turn_time",
                    "severity": "warning",
                    "table_id": table.id,
                    "table_number": table.table_number,
                    "message": f"Table {table.table_number} has been occupied "
                              f"for {round(turn_time)} minutes "
                              f"(avg: {round(avg_turn_time)} min)",
                    "data": {
                        "turn_time_minutes": round(turn_time, 1),
                        "average_turn_time": round(avg_turn_time, 1),
                        "guest_count": session.guest_count
                    }
                })
                
        # Broadcast alerts if any
        if alerts:
            for floor_connections in self.connections.get(restaurant_id, {}).values():
                await self._send_to_connections(
                    floor_connections,
                    {
                        "type": UpdateType.ALERT.value,
                        "alerts": alerts,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
                
    async def handle_message(
        self,
        websocket: WebSocket,
        message: Dict[str, Any]
    ):
        """Handle incoming WebSocket messages"""
        metadata = self.connection_metadata.get(websocket)
        if not metadata:
            return
            
        message_type = message.get("type")
        
        if message_type == "heartbeat":
            # Update last heartbeat
            metadata["last_heartbeat"] = datetime.utcnow()
            await websocket.send_json({
                "type": "heartbeat_ack",
                "timestamp": datetime.utcnow().isoformat()
            })
            
        elif message_type == "request_update":
            # Send current state
            await self._send_initial_state(
                websocket,
                metadata["restaurant_id"],
                metadata["floor_id"]
            )
            
        elif message_type == "subscribe_table":
            # Subscribe to specific table updates
            table_id = message.get("table_id")
            if table_id:
                metadata.setdefault("subscribed_tables", set()).add(table_id)
                
        elif message_type == "unsubscribe_table":
            # Unsubscribe from table updates
            table_id = message.get("table_id")
            if table_id and "subscribed_tables" in metadata:
                metadata["subscribed_tables"].discard(table_id)


# Global instance
realtime_table_manager = RealtimeTableManager()