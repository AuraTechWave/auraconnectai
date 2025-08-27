"""
WebSocket routes for real-time table status updates.

This module provides WebSocket endpoints for:
- Real-time table status updates
- Turn time tracking
- Heat map visualization
- Live occupancy monitoring
"""

from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.exceptions import WebSocketException
import logging
import json

from core.websocket_auth import (
    get_websocket_user,
    AuthenticatedWebSocket,
    WebSocketAuthError,
)
from ..websocket.realtime_table_manager import realtime_table_manager
from ..schemas.table_schemas import WebSocketMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["tables-websocket"])


@router.websocket("/tables/{restaurant_id}")
async def table_status_websocket(
    websocket: WebSocket,
    restaurant_id: int,
    floor_id: Optional[int] = Query(None),
    token: Optional[str] = Query(None)
):
    """
    WebSocket endpoint for real-time table status updates.
    
    Query parameters:
    - floor_id: Optional floor ID to filter updates
    - token: JWT token for authentication
    
    Message types:
    - initial_state: Sent on connection with current state
    - table_status: Table status changes
    - occupancy_update: Occupancy metrics
    - turn_time_update: Turn time metrics
    - heat_map_update: Heat map visualization data
    - alert: System alerts (long turn times, etc.)
    """
    
    try:
        # Authenticate WebSocket connection
        user = await get_websocket_user(websocket, token)
        
        # Check restaurant access
        if restaurant_id not in user.tenant_ids and "admin" not in user.roles:
            await websocket.close(
                code=4003,
                reason="Unauthorized: No access to this restaurant"
            )
            return
        
        # Check table management permissions
        allowed_roles = ["admin", "manager", "host", "server", "staff"]
        if not any(role in allowed_roles for role in user.roles):
            await websocket.close(
                code=4003,
                reason="Insufficient permissions for table management"
            )
            return
        
        # Create authenticated WebSocket wrapper
        auth_ws = AuthenticatedWebSocket(websocket, user, user.roles)
        await auth_ws.accept()
        
        # Connect to manager with authenticated user context
        await realtime_table_manager.connect(
            websocket=websocket,
            restaurant_id=restaurant_id,
            floor_id=floor_id,
            user_id=user.id,
            role=user.roles[0] if user.roles else "staff"
        )
        
        logger.info(
            f"Table WebSocket connected for restaurant {restaurant_id} by user {user.username}"
        )
        
        # Send welcome message
        await auth_ws.send_json({
            "type": "connection_established",
            "restaurant_id": restaurant_id,
            "floor_id": floor_id,
            "user": {
                "id": user.id,
                "username": user.username,
            },
        })
        
        while True:
            # Receive and handle messages
            data = await auth_ws.receive_text()
            
            try:
                message = json.loads(data)
                # Add user context to message
                message["user_id"] = user.id
                message["username"] = user.username
                
                await realtime_table_manager.handle_message(websocket, message)
            except json.JSONDecodeError:
                await auth_ws.send_json({
                    "type": "error",
                    "message": "Invalid JSON format"
                })
            except Exception as e:
                logger.error(f"Error handling message: {e}")
                await auth_ws.send_json({
                    "type": "error",
                    "message": "Error processing message"
                })
    
    except WebSocketAuthError as e:
        logger.warning(f"Table WebSocket authentication failed: {e}")
        await websocket.close(code=4001, reason=str(e))
    except WebSocketDisconnect:
        logger.info(f"Table WebSocket disconnected for restaurant {restaurant_id}")
    except Exception as e:
        logger.error(f"Table WebSocket error: {e}")
        await websocket.close(code=4011, reason="Internal server error")
    finally:
        realtime_table_manager.disconnect(websocket)


@router.websocket("/analytics/{restaurant_id}")
async def table_analytics_websocket(
    websocket: WebSocket,
    restaurant_id: int,
    token: Optional[str] = Query(None)
):
    """
    WebSocket endpoint for real-time table analytics.
    
    Provides higher-frequency updates for analytics dashboards:
    - Turn time trends
    - Occupancy patterns
    - Revenue metrics
    - Performance indicators
    """
    
    # Authenticate user
    user = None
    if token:
        try:
            user = await get_current_user_ws(token)
            if user.restaurant_id != restaurant_id and not user.is_superadmin:
                await websocket.close(code=4003, reason="Unauthorized")
                return
        except Exception as e:
            logger.error(f"WebSocket auth error: {e}")
            await websocket.close(code=4001, reason="Invalid token")
            return
    
    # Connect to manager with analytics focus
    await realtime_table_manager.connect(
        websocket=websocket,
        restaurant_id=restaurant_id,
        floor_id=None,  # Analytics cover all floors
        user_id=user.id if user else None,
        role="analytics"
    )
    
    try:
        while True:
            # Receive and handle messages
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                # Handle analytics-specific messages
                if message.get("type") == "request_analytics":
                    # Send comprehensive analytics update
                    await realtime_table_manager.handle_message(websocket, {
                        "type": "request_update",
                        "include_analytics": True
                    })
                else:
                    await realtime_table_manager.handle_message(websocket, message)
                    
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format"
                })
            except Exception as e:
                logger.error(f"Error handling analytics message: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": "Error processing message"
                })
                
    except WebSocketDisconnect:
        logger.info(f"Analytics WebSocket disconnected for restaurant {restaurant_id}")
    except Exception as e:
        logger.error(f"Analytics WebSocket error: {e}")
    finally:
        realtime_table_manager.disconnect(websocket)