# backend/modules/tables/routers/realtime_table_router.py

"""
Real-time table status and analytics API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import logging

from core.database import get_async_db
from core.auth import get_current_user
from ..services.realtime_table_service import realtime_table_service, TurnTimeAlert
from ..services.table_state_service import table_state_service
from ..websocket.table_websocket import websocket_endpoint, manager as websocket_manager
from ..schemas.table_schemas import TableHeatMapResponse, TurnTimeAlertResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tables/realtime", tags=["Table Real-time"])


@router.websocket("/ws/{restaurant_id}")
async def websocket_realtime_updates(
    websocket: WebSocket,
    restaurant_id: int,
    user_id: Optional[int] = Query(None),
    role: Optional[str] = Query(None),
):
    """WebSocket endpoint for real-time table updates"""
    await websocket_endpoint(websocket, restaurant_id, user_id, role)


@router.get("/turn-alerts/{restaurant_id}")
async def get_turn_time_alerts(
    restaurant_id: int,
    alert_level: Optional[TurnTimeAlert] = Query(None, description="Filter by alert level"),
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get current turn time alerts for tables"""
    
    try:
        alerts = await realtime_table_service.get_turn_time_alerts(db, restaurant_id)
        
        # Filter by alert level if specified
        if alert_level:
            alerts = [alert for alert in alerts if alert.alert_level == alert_level]
        
        return {
            "success": True,
            "data": {
                "alerts": [
                    {
                        "table_id": alert.table_id,
                        "table_number": alert.table_number,
                        "current_duration_minutes": alert.current_duration_minutes,
                        "expected_duration_minutes": alert.expected_duration_minutes,
                        "overrun_minutes": alert.overrun_minutes,
                        "progress_percentage": alert.progress_percentage,
                        "alert_level": alert.alert_level.value,
                        "guest_count": alert.guest_count,
                        "server_name": alert.server_name,
                        "order_value": alert.order_value,
                        "session_start": alert.session_start.isoformat(),
                    }
                    for alert in alerts
                ],
                "summary": {
                    "total_alerts": len(alerts),
                    "critical_count": len([a for a in alerts if a.alert_level == TurnTimeAlert.CRITICAL]),
                    "warning_count": len([a for a in alerts if a.alert_level == TurnTimeAlert.WARNING]),
                    "excessive_count": len([a for a in alerts if a.alert_level == TurnTimeAlert.EXCESSIVE]),
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        }
    
    except Exception as e:
        logger.error(f"Error getting turn time alerts: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving turn time alerts: {str(e)}")


@router.get("/occupancy/{restaurant_id}")
async def get_occupancy_summary(
    restaurant_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get current occupancy summary"""
    
    try:
        occupancy = await realtime_table_service.get_occupancy_summary(db, restaurant_id)
        
        return {
            "success": True,
            "data": occupancy,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    except Exception as e:
        logger.error(f"Error getting occupancy summary: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving occupancy data: {str(e)}")


@router.get("/heat-map/{restaurant_id}")
async def get_heat_map_data(
    restaurant_id: int,
    period: str = Query("today", regex="^(today|week|month)$"),
    floor_id: Optional[int] = Query(None, description="Filter by floor"),
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get heat map visualization data"""
    
    try:
        heat_map = await realtime_table_service.get_heat_map_data(db, restaurant_id, period)
        
        # Filter by floor if specified
        if floor_id:
            # Would need to add floor_id to heat map data or join with table data
            pass
        
        return {
            "success": True,
            "data": {
                "heat_map": [
                    {
                        "table_id": hm.table_id,
                        "table_number": hm.table_number,
                        "heat_score": hm.heat_score,
                        "heat_color": hm.heat_color,
                        "occupancy_rate": hm.occupancy_rate,
                        "revenue_per_hour": hm.revenue_per_hour,
                        "turn_count_today": hm.turn_count_today,
                        "avg_turn_time_minutes": hm.avg_turn_time_minutes,
                        "status": hm.status.value,
                        "position": {
                            "x": hm.position_x,
                            "y": hm.position_y,
                        },
                    }
                    for hm in heat_map
                ],
                "period": period,
                "summary": {
                    "total_tables": len(heat_map),
                    "avg_heat_score": round(sum(hm.heat_score for hm in heat_map) / len(heat_map), 1) if heat_map else 0,
                    "avg_occupancy": round(sum(hm.occupancy_rate for hm in heat_map) / len(heat_map), 1) if heat_map else 0,
                    "total_revenue": sum(hm.revenue_per_hour for hm in heat_map),
                    "hottest_table": max(heat_map, key=lambda x: x.heat_score).table_number if heat_map else None,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        }
    
    except Exception as e:
        logger.error(f"Error getting heat map data: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving heat map data: {str(e)}")


@router.get("/analytics/turn-times/{restaurant_id}")
async def get_turn_time_analytics(
    restaurant_id: int,
    start_date: datetime = Query(..., description="Start date for analytics"),
    end_date: datetime = Query(..., description="End date for analytics"),
    table_id: Optional[int] = Query(None, description="Specific table ID"),
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get detailed turn time analytics"""
    
    try:
        analytics = await realtime_table_service.get_table_turn_analytics(
            db, restaurant_id, start_date, end_date, table_id
        )
        
        return {
            "success": True,
            "data": analytics,
        }
    
    except Exception as e:
        logger.error(f"Error getting turn time analytics: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving analytics: {str(e)}")


@router.get("/analytics/peak-hours/{restaurant_id}")
async def get_peak_hours_analysis(
    restaurant_id: int,
    date: datetime = Query(..., description="Date to analyze"),
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get peak hours analysis for a specific date"""
    
    try:
        analysis = await realtime_table_service.get_peak_hours_analysis(
            db, restaurant_id, date
        )
        
        return {
            "success": True,
            "data": analysis,
        }
    
    except Exception as e:
        logger.error(f"Error getting peak hours analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving peak hours data: {str(e)}")


@router.get("/status/live/{restaurant_id}")
async def get_live_status(
    restaurant_id: int,
    floor_id: Optional[int] = Query(None, description="Filter by floor"),
    include_analytics: bool = Query(True, description="Include real-time analytics"),
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get comprehensive live status including tables, occupancy, and alerts"""
    
    try:
        # Get basic floor status
        floor_status = await table_state_service.get_floor_status(db, restaurant_id, floor_id)
        
        data = {
            "floors": floor_status,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        if include_analytics:
            # Add real-time analytics
            occupancy = await realtime_table_service.get_occupancy_summary(db, restaurant_id)
            alerts = await realtime_table_service.get_turn_time_alerts(db, restaurant_id)
            
            data["analytics"] = {
                "occupancy": occupancy,
                "turn_alerts": [
                    {
                        "table_id": alert.table_id,
                        "table_number": alert.table_number,
                        "alert_level": alert.alert_level.value,
                        "overrun_minutes": alert.overrun_minutes,
                    }
                    for alert in alerts[:5]  # Top 5 alerts
                ],
                "alert_summary": {
                    "total_alerts": len(alerts),
                    "critical_count": len([a for a in alerts if a.alert_level == TurnTimeAlert.CRITICAL]),
                    "warning_count": len([a for a in alerts if a.alert_level == TurnTimeAlert.WARNING]),
                }
            }
        
        return {
            "success": True,
            "data": data,
        }
    
    except Exception as e:
        logger.error(f"Error getting live status: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving live status: {str(e)}")


@router.post("/monitoring/start/{restaurant_id}")
async def start_realtime_monitoring(
    restaurant_id: int,
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Start real-time monitoring for a restaurant"""
    
    try:
        await realtime_table_service.start_monitoring()
        
        return {
            "success": True,
            "message": "Real-time monitoring started",
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    except Exception as e:
        logger.error(f"Error starting monitoring: {e}")
        raise HTTPException(status_code=500, detail=f"Error starting monitoring: {str(e)}")


@router.post("/monitoring/stop/{restaurant_id}")
async def stop_realtime_monitoring(
    restaurant_id: int,
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Stop real-time monitoring for a restaurant"""
    
    try:
        await realtime_table_service.stop_monitoring()
        
        return {
            "success": True,
            "message": "Real-time monitoring stopped",
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    except Exception as e:
        logger.error(f"Error stopping monitoring: {e}")
        raise HTTPException(status_code=500, detail=f"Error stopping monitoring: {str(e)}")


@router.get("/connections/{restaurant_id}")
async def get_websocket_connections(
    restaurant_id: int,
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get information about active WebSocket connections"""
    
    try:
        connections = websocket_manager.active_connections.get(restaurant_id, set())
        
        connection_info = []
        for ws in connections:
            metadata = websocket_manager.connection_metadata.get(ws, {})
            connection_info.append({
                "user_id": metadata.get("user_id"),
                "role": metadata.get("role"),
                "connected_at": metadata.get("connected_at", datetime.utcnow()).isoformat(),
            })
        
        return {
            "success": True,
            "data": {
                "restaurant_id": restaurant_id,
                "active_connections": len(connections),
                "connections": connection_info,
                "timestamp": datetime.utcnow().isoformat(),
            }
        }
    
    except Exception as e:
        logger.error(f"Error getting connection info: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving connection info: {str(e)}")


@router.post("/broadcast/{restaurant_id}")
async def broadcast_message(
    restaurant_id: int,
    message: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Broadcast a custom message to all connected clients"""
    
    try:
        # Add timestamp to message
        message["timestamp"] = datetime.utcnow().isoformat()
        message["sent_by"] = current_user.get("id")
        
        await websocket_manager.broadcast_to_restaurant(restaurant_id, message)
        
        return {
            "success": True,
            "message": "Message broadcasted successfully",
            "recipients": len(websocket_manager.active_connections.get(restaurant_id, set())),
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    except Exception as e:
        logger.error(f"Error broadcasting message: {e}")
        raise HTTPException(status_code=500, detail=f"Error broadcasting message: {str(e)}")


# Utility endpoints for development/debugging
@router.get("/test/generate-alerts/{restaurant_id}")
async def generate_test_alerts(
    restaurant_id: int,
    count: int = Query(3, ge=1, le=10),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Generate test turn time alerts for development/testing"""
    
    # This would be development only - create fake alerts for UI testing
    test_alerts = []
    
    for i in range(count):
        test_alerts.append({
            "table_id": i + 1,
            "table_number": f"T{i + 1}",
            "current_duration_minutes": 90 + (i * 15),
            "expected_duration_minutes": 75,
            "alert_level": ["warning", "critical", "excessive"][i % 3],
            "guest_count": 2 + i,
            "server_name": f"Server {i + 1}",
            "overrun_minutes": 15 + (i * 15),
        })
    
    return {
        "success": True,
        "data": {
            "test_alerts": test_alerts,
            "note": "These are test alerts for development purposes",
        }
    }