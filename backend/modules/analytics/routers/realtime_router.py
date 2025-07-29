# backend/modules/analytics/routers/realtime_router.py

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.auth import get_current_staff_user
from ..services.websocket_manager import websocket_manager, WebSocketManager
from ..services.realtime_metrics_service import realtime_metrics_service, DashboardSnapshot
from ..services.permissions_service import (
    PermissionsService, AnalyticsPermission, require_analytics_permission
)
from ..schemas.analytics_schemas import SalesFilterRequest

router = APIRouter(prefix="/analytics/realtime", tags=["Real-time Analytics"])
logger = logging.getLogger(__name__)


@router.websocket("/dashboard")
async def dashboard_websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="Authentication token")
):
    """
    WebSocket endpoint for real-time dashboard updates
    
    Supports the following message types:
    - subscribe: Subscribe to dashboard updates
    - unsubscribe: Unsubscribe from updates
    - heartbeat: Keep connection alive
    - get_current_data: Request current dashboard data
    """
    
    client_id = None
    
    try:
        # TODO: Implement proper WebSocket authentication using token
        # For now, using basic authentication
        user_permissions = [
            AnalyticsPermission.VIEW_DASHBOARD.value,
            AnalyticsPermission.VIEW_SALES_REPORTS.value
        ]
        
        # Connect client
        client_id = await websocket_manager.connect_client(
            websocket=websocket,
            user_id=1,  # TODO: Extract from token
            user_permissions=user_permissions
        )
        
        logger.info(f"Dashboard WebSocket client connected: {client_id}")
        
        # Handle incoming messages
        while True:
            try:
                message = await websocket.receive_text()
                await websocket_manager.handle_client_message(client_id, message)
            except WebSocketDisconnect:
                logger.info(f"Dashboard WebSocket client disconnected: {client_id}")
                break
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")
                break
    
    except Exception as e:
        logger.error(f"Error in dashboard WebSocket endpoint: {e}")
    
    finally:
        if client_id:
            await websocket_manager.disconnect_client(client_id)


@router.websocket("/metrics/{metric_name}")
async def metric_websocket_endpoint(
    websocket: WebSocket,
    metric_name: str,
    token: Optional[str] = Query(None, description="Authentication token")
):
    """
    WebSocket endpoint for specific metric real-time updates
    
    Provides real-time updates for individual metrics like:
    - revenue_current
    - orders_current  
    - customers_current
    - average_order_value
    """
    
    client_id = None
    
    try:
        # TODO: Implement proper WebSocket authentication
        user_permissions = [
            AnalyticsPermission.VIEW_SALES_REPORTS.value,
            AnalyticsPermission.ACCESS_REALTIME.value
        ]
        
        # Connect client
        client_id = await websocket_manager.connect_client(
            websocket=websocket,
            user_id=1,  # TODO: Extract from token
            user_permissions=user_permissions
        )
        
        # Auto-subscribe to the specific metric
        await websocket_manager.handle_client_message(client_id, f'''{{
            "type": "subscribe",
            "data": {{
                "subscription_type": "metrics",
                "metrics": ["{metric_name}"]
            }}
        }}''')
        
        logger.info(f"Metric WebSocket client connected for '{metric_name}': {client_id}")
        
        # Handle incoming messages
        while True:
            try:
                message = await websocket.receive_text()
                await websocket_manager.handle_client_message(client_id, message)
            except WebSocketDisconnect:
                logger.info(f"Metric WebSocket client disconnected: {client_id}")
                break
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")
                break
    
    except Exception as e:
        logger.error(f"Error in metric WebSocket endpoint: {e}")
    
    finally:
        if client_id:
            await websocket_manager.disconnect_client(client_id)


@router.get("/dashboard/current")
async def get_current_dashboard_data(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_analytics_permission(AnalyticsPermission.VIEW_DASHBOARD))
):
    """
    Get current dashboard data via REST API
    
    Returns the same data as WebSocket but via HTTP request
    """
    try:
        snapshot = await realtime_metrics_service.get_current_dashboard_snapshot()
        return {
            "success": True,
            "data": snapshot.to_dict(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting current dashboard data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dashboard data"
        )


@router.get("/metrics/{metric_name}/current")
async def get_current_metric_data(
    metric_name: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_analytics_permission(AnalyticsPermission.VIEW_SALES_REPORTS))
):
    """
    Get current value for a specific metric via REST API
    """
    try:
        metric = await realtime_metrics_service.get_realtime_metric(metric_name)
        
        if not metric:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Metric '{metric_name}' not found"
            )
        
        return {
            "success": True,
            "data": metric.to_dict(),
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current metric data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve metric data"
        )


@router.get("/trends/hourly")
async def get_hourly_trends(
    hours_back: int = Query(24, ge=1, le=168, description="Hours to look back (max 1 week)"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_analytics_permission(AnalyticsPermission.VIEW_SALES_REPORTS))
):
    """
    Get hourly trends for dashboard charts
    """
    try:
        trends = await realtime_metrics_service.get_hourly_trends(hours_back)
        
        return {
            "success": True,
            "data": trends,
            "period": {
                "hours_back": hours_back,
                "start_time": (datetime.now() - timedelta(hours=hours_back)).isoformat(),
                "end_time": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error getting hourly trends: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve hourly trends"
        )


@router.get("/performers/top")
async def get_top_performers(
    limit: int = Query(5, ge=1, le=20, description="Number of top performers to return"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_analytics_permission(AnalyticsPermission.VIEW_STAFF_REPORTS))
):
    """
    Get top performing staff and products
    """
    try:
        performers = await realtime_metrics_service.get_top_performers(limit)
        
        return {
            "success": True,
            "data": performers,
            "limit": limit,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting top performers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve top performers"
        )


@router.post("/cache/invalidate")
async def invalidate_cache(
    cache_pattern: Optional[str] = Query(None, description="Cache pattern to invalidate"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_analytics_permission(AnalyticsPermission.ADMIN_ANALYTICS))
):
    """
    Invalidate real-time metrics cache (admin only)
    """
    try:
        await realtime_metrics_service.invalidate_cache(cache_pattern)
        
        return {
            "success": True,
            "message": f"Cache invalidated for pattern: {cache_pattern or 'all'}",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invalidate cache"
        )


@router.get("/websocket/stats")
async def get_websocket_stats(
    current_user: dict = Depends(require_analytics_permission(AnalyticsPermission.ADMIN_ANALYTICS))
):
    """
    Get WebSocket connection statistics (admin only)
    """
    try:
        stats = websocket_manager.get_connection_stats()
        
        return {
            "success": True,
            "data": stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting WebSocket stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve WebSocket statistics"
        )


@router.post("/websocket/broadcast")
async def broadcast_message(
    message_type: str = Query(..., description="Type of message to broadcast"),
    message_data: Dict[str, Any] = None,
    current_user: dict = Depends(require_analytics_permission(AnalyticsPermission.ADMIN_ANALYTICS))
):
    """
    Broadcast a message to all connected WebSocket clients (admin only)
    """
    try:
        if message_type == "dashboard_refresh":
            # Force refresh of dashboard data
            snapshot = await realtime_metrics_service.get_current_dashboard_snapshot()
            await websocket_manager.broadcast_dashboard_update(snapshot)
            
        elif message_type == "system_notification":
            # Broadcast system notification
            await websocket_manager.broadcast_alert_notification({
                "type": "system_notification",
                "message": message_data.get("message", "System notification"),
                "severity": message_data.get("severity", "info"),
                "timestamp": datetime.now().isoformat()
            })
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown message type: {message_type}"
            )
        
        return {
            "success": True,
            "message": f"Broadcast sent: {message_type}",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error broadcasting message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to broadcast message"
        )


@router.get("/health")
async def health_check():
    """
    Health check endpoint for real-time analytics services
    """
    try:
        # Check if real-time metrics service is running
        current_snapshot = await realtime_metrics_service.get_current_dashboard_snapshot()
        
        # Check WebSocket manager stats
        ws_stats = websocket_manager.get_connection_stats()
        
        return {
            "status": "healthy",
            "services": {
                "realtime_metrics": "running",
                "websocket_manager": "running"
            },
            "metrics": {
                "last_update": current_snapshot.timestamp.isoformat(),
                "websocket_connections": ws_stats["total_connections"]
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# Event handling endpoints

@router.post("/events/order-completed")
async def handle_order_completed_event(
    order_data: Dict[str, Any],
    current_user: dict = Depends(get_current_staff_user)
):
    """
    Handle order completed event for real-time metrics update
    
    This endpoint can be called by the orders module when an order is completed
    to trigger immediate metrics updates
    """
    try:
        # Invalidate relevant cache entries
        await realtime_metrics_service.invalidate_cache("dashboard")
        await realtime_metrics_service.invalidate_cache("hourly")
        
        # Force metrics update
        snapshot = await realtime_metrics_service.get_current_dashboard_snapshot()
        await websocket_manager.broadcast_dashboard_update(snapshot)
        
        logger.info(f"Order completed event processed: {order_data.get('order_id')}")
        
        return {
            "success": True,
            "message": "Order completion event processed",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error handling order completed event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process order completion event"
        )


@router.post("/events/staff-action")
async def handle_staff_action_event(
    action_data: Dict[str, Any],
    current_user: dict = Depends(get_current_staff_user)
):
    """
    Handle staff action event for real-time metrics update
    
    This endpoint can be called when staff members perform significant actions
    that should trigger metrics updates
    """
    try:
        action_type = action_data.get("action_type")
        
        if action_type in ["order_processed", "customer_served", "shift_started", "shift_ended"]:
            # Invalidate performance-related cache
            await realtime_metrics_service.invalidate_cache("performers")
            
            # Update top performers if needed
            performers = await realtime_metrics_service.get_top_performers(5)
            
            # Broadcast update if there are subscribers
            ws_stats = websocket_manager.get_connection_stats()
            if ws_stats["total_connections"] > 0:
                snapshot = await realtime_metrics_service.get_current_dashboard_snapshot()
                await websocket_manager.broadcast_dashboard_update(snapshot)
        
        return {
            "success": True,
            "message": "Staff action event processed",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error handling staff action event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process staff action event"
        )


# WebSocket message examples for documentation
"""
Example WebSocket messages:

1. Subscribe to dashboard updates:
{
    "type": "subscribe",
    "data": {
        "subscription_type": "dashboard"
    }
}

2. Subscribe to specific metrics:
{
    "type": "subscribe", 
    "data": {
        "subscription_type": "metrics",
        "metrics": ["revenue_current", "orders_current"]
    }
}

3. Subscribe to alerts:
{
    "type": "subscribe",
    "data": {
        "subscription_type": "alerts"
    }
}

4. Request current data:
{
    "type": "get_current_data",
    "data": {
        "data_type": "dashboard"
    }
}

5. Heartbeat:
{
    "type": "heartbeat",
    "data": {}
}

6. Unsubscribe:
{
    "type": "unsubscribe",
    "data": {
        "subscription_type": "dashboard"
    }
}

Server responses include:
- dashboard_update: Complete dashboard metrics
- metric_update: Individual metric updates  
- alert_notification: Alert notifications
- system_status: Connection status
- error: Error messages
- heartbeat: Heartbeat responses
- subscription_confirm: Subscription confirmations
"""