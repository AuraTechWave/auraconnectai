"""
WebSocket routes for real-time table status updates.

This module provides WebSocket endpoints for:
- Real-time table status updates
- Turn time tracking
- Heat map visualization
- Live occupancy monitoring
"""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from fastapi.exceptions import WebSocketException
import logging
import json

from core.websocket_auth import (
    get_websocket_user,
    AuthenticatedWebSocket,
    WebSocketAuthError,
    validate_tenant_access,
    IS_PRODUCTION,
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
        # Authenticate WebSocket connection (query params disabled in production)
        user = await get_websocket_user(websocket, token, use_query_param=not IS_PRODUCTION)
        
        # Check restaurant access using secure validation
        if not validate_tenant_access(user, restaurant_id):
            logger.warning(f"Tenant access denied for user {user.id} to restaurant {restaurant_id}")
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Policy violation"
            )
            return
        
        # Check table management permissions
        allowed_roles = ["admin", "manager", "host", "server", "staff"]
        if not any(role in allowed_roles for role in user.roles):
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Policy violation"
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
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Policy violation"
        )
    except WebSocketDisconnect:
        logger.info(f"Table WebSocket disconnected for restaurant {restaurant_id}")
    except Exception as e:
        logger.error(f"Table WebSocket error: {e}")
        await websocket.close(
            code=status.WS_1011_INTERNAL_ERROR,
            reason="Internal server error"
        )
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
    
    try:
        # Authenticate WebSocket connection (query params disabled in production)
        user = await get_websocket_user(websocket, token, use_query_param=not IS_PRODUCTION)
        
        # Check restaurant access using secure validation
        if not validate_tenant_access(user, restaurant_id):
            logger.warning(f"Tenant access denied for user {user.id} to restaurant {restaurant_id}")
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Policy violation"
            )
            return
        
        # Check analytics permissions
        allowed_roles = ["admin", "manager", "analytics_viewer", "analytics_admin"]
        if not any(role in allowed_roles for role in user.roles):
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Policy violation"
            )
            return
        
        # Create authenticated WebSocket wrapper with analytics permissions
        analytics_permissions = []
        for role in user.roles:
            if role == "admin":
                analytics_permissions.extend([
                    "analytics.view_dashboard",
                    "analytics.view_sales_reports",
                    "analytics.view_table_metrics",
                    "analytics.admin_analytics"
                ])
            elif role in ["manager", "analytics_admin"]:
                analytics_permissions.extend([
                    "analytics.view_dashboard",
                    "analytics.view_sales_reports",
                    "analytics.view_table_metrics"
                ])
            elif role == "analytics_viewer":
                analytics_permissions.extend([
                    "analytics.view_dashboard",
                    "analytics.view_table_metrics"
                ])
        
        auth_ws = AuthenticatedWebSocket(websocket, user, analytics_permissions)
        await auth_ws.accept()
        
        # Connect to manager with authenticated user context
        await realtime_table_manager.connect(
            websocket=websocket,
            restaurant_id=restaurant_id,
            floor_id=None,  # Analytics cover all floors
            user_id=user.id,
            role="analytics"
        )
        
        logger.info(
            f"Table analytics WebSocket connected for restaurant {restaurant_id} by user {user.username}"
        )
        
        # Send welcome message
        await auth_ws.send_json({
            "type": "connection_established",
            "restaurant_id": restaurant_id,
            "user": {
                "id": user.id,
                "username": user.username,
                "permissions": analytics_permissions
            },
            "timestamp": datetime.utcnow().isoformat()
        })
        
        while True:
            # Receive and handle messages
            data = await auth_ws.receive_text()
            
            try:
                message = json.loads(data)
                # Add user context to message
                message["user_id"] = user.id
                message["username"] = user.username
                
                # Handle analytics-specific messages
                if message.get("type") == "request_analytics":
                    # Send comprehensive analytics update
                    await realtime_table_manager.handle_message(websocket, {
                        "type": "request_update",
                        "include_analytics": True,
                        "user_id": user.id
                    })
                else:
                    await realtime_table_manager.handle_message(websocket, message)
                    
            except json.JSONDecodeError:
                await auth_ws.send_json({
                    "type": "error",
                    "message": "Invalid JSON format"
                })
            except Exception as e:
                logger.error(f"Error handling analytics message: {e}")
                await auth_ws.send_json({
                    "type": "error",
                    "message": "Error processing message"
                })
                
    except WebSocketAuthError as e:
        logger.warning(f"Table analytics WebSocket authentication failed: {e}")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Policy violation"
        )
    except WebSocketDisconnect:
        logger.info(f"Table analytics WebSocket disconnected for restaurant {restaurant_id}")
    except Exception as e:
        logger.error(f"Table analytics WebSocket error: {e}")
        await websocket.close(
            code=status.WS_1011_INTERNAL_ERROR,
            reason="Internal server error"
        )
    finally:
        realtime_table_manager.disconnect(websocket)