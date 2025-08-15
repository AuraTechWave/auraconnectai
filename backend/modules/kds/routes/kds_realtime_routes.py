# backend/modules/kds/routes/kds_realtime_routes.py

"""
Real-time KDS routes with WebSocket support
"""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    Query,
    Body,
)
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import asyncio
import logging

from core.database import get_db
from core.auth import get_current_user
from ..services.kds_realtime_service import KDSRealtimeService
from ..services.kds_websocket_manager import kds_websocket_manager
from ..models.kds_models import DisplayStatus
from ..schemas.kds_schemas import (
    KDSOrderItemResponse,
    ItemStatusUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/kds/realtime", tags=["KDS Real-time"])


# ========== WebSocket Endpoints ==========

@router.websocket("/ws/station/{station_id}")
async def websocket_station_endpoint(
    websocket: WebSocket,
    station_id: int,
    db: Session = Depends(get_db),
):
    """WebSocket endpoint for real-time station updates"""
    
    await kds_websocket_manager.connect(websocket, station_id)
    service = KDSRealtimeService(db)
    
    try:
        # Send initial station data
        station_data = service.get_station_summary(station_id)
        await websocket.send_json({
            "type": "station_init",
            "data": station_data,
        })
        
        # Send current items
        items = service.get_station_display_items(station_id)
        await websocket.send_json({
            "type": "items_init",
            "data": items,
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages with timeout for heartbeat
                message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                
                data = json.loads(message)
                
                # Handle different message types
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                
                elif data.get("type") == "update_status":
                    item_id = data.get("item_id")
                    new_status = DisplayStatus[data.get("status").upper()]
                    staff_id = data.get("staff_id")
                    
                    await service.update_item_status(
                        item_id=item_id,
                        new_status=new_status,
                        staff_id=staff_id,
                    )
                
                elif data.get("type") == "bump_item":
                    item_id = data.get("item_id")
                    staff_id = data.get("staff_id")
                    
                    await service.bump_item(item_id, staff_id)
                
                elif data.get("type") == "recall_item":
                    item_id = data.get("item_id")
                    reason = data.get("reason", "Quality issue")
                    staff_id = data.get("staff_id")
                    
                    await service.recall_item(item_id, reason, staff_id)
                
                elif data.get("type") == "refresh":
                    # Resend current items
                    items = service.get_station_display_items(station_id)
                    await websocket.send_json({
                        "type": "items_refresh",
                        "data": items,
                    })
                
            except asyncio.TimeoutError:
                # Send heartbeat
                await kds_websocket_manager.send_heartbeat(station_id)
                
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format",
                })
                
    except WebSocketDisconnect:
        kds_websocket_manager.disconnect(websocket, station_id)
        logger.info(f"WebSocket disconnected for station {station_id}")
    except Exception as e:
        logger.error(f"WebSocket error for station {station_id}: {str(e)}")
        kds_websocket_manager.disconnect(websocket, station_id)


@router.websocket("/ws/kitchen")
async def websocket_kitchen_endpoint(
    websocket: WebSocket,
    db: Session = Depends(get_db),
):
    """WebSocket endpoint for kitchen-wide updates"""
    
    await websocket.accept()
    
    try:
        # This endpoint can be used for kitchen managers to monitor all stations
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            
            if data.get("type") == "subscribe_all":
                # Subscribe to all station updates
                # Implementation would depend on requirements
                pass
                
    except WebSocketDisconnect:
        logger.info("Kitchen WebSocket disconnected")
    except Exception as e:
        logger.error(f"Kitchen WebSocket error: {str(e)}")


# ========== REST Endpoints ==========

@router.post("/orders/{order_id}/process")
async def process_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Process a new order and route items to stations"""
    
    service = KDSRealtimeService(db)
    
    try:
        kds_items = await service.process_new_order(order_id)
        
        return {
            "success": True,
            "message": f"Order {order_id} processed successfully",
            "data": {
                "order_id": order_id,
                "items_created": len(kds_items),
                "stations_notified": list(set(item.station_id for item in kds_items)),
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing order: {str(e)}")


@router.get("/station/{station_id}/display")
async def get_station_display(
    station_id: int,
    include_completed: bool = Query(False),
    limit: int = Query(50, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get current display items for a station"""
    
    service = KDSRealtimeService(db)
    
    try:
        items = service.get_station_display_items(
            station_id=station_id,
            include_completed=include_completed,
            limit=limit,
        )
        
        summary = service.get_station_summary(station_id)
        
        return {
            "success": True,
            "data": {
                "station": summary,
                "items": items,
                "timestamp": datetime.utcnow().isoformat(),
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving display: {str(e)}")


@router.put("/items/{item_id}/status")
async def update_item_status(
    item_id: int,
    status_update: ItemStatusUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Update the status of a KDS item"""
    
    service = KDSRealtimeService(db)
    
    try:
        item = await service.update_item_status(
            item_id=item_id,
            new_status=status_update.status,
            staff_id=status_update.staff_id,
            reason=status_update.reason,
        )
        
        return {
            "success": True,
            "message": f"Item {item_id} status updated to {status_update.status.value}",
            "data": {
                "item_id": item.id,
                "new_status": item.status.value,
                "updated_at": datetime.utcnow().isoformat(),
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating status: {str(e)}")


@router.post("/items/{item_id}/bump")
async def bump_item(
    item_id: int,
    staff_id: Optional[int] = Body(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Bump an item (mark as ready)"""
    
    service = KDSRealtimeService(db)
    
    try:
        await service.bump_item(item_id, staff_id)
        
        return {
            "success": True,
            "message": f"Item {item_id} bumped successfully",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error bumping item: {str(e)}")


@router.post("/items/{item_id}/recall")
async def recall_item(
    item_id: int,
    reason: str = Body(..., min_length=1),
    staff_id: Optional[int] = Body(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Recall a completed item"""
    
    service = KDSRealtimeService(db)
    
    try:
        await service.recall_item(item_id, reason, staff_id)
        
        return {
            "success": True,
            "message": f"Item {item_id} recalled",
            "data": {
                "item_id": item_id,
                "reason": reason,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error recalling item: {str(e)}")


@router.post("/orders/{order_id}/fire-course")
async def fire_course(
    order_id: int,
    course_number: int = Body(..., ge=0, le=5),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Fire all items for a specific course"""
    
    service = KDSRealtimeService(db)
    
    try:
        items = service.fire_course(order_id, course_number)
        
        # Notify stations
        for item in items:
            await kds_websocket_manager.broadcast_item_update(
                item.station_id,
                item.id,
                {"fire_time": datetime.utcnow().isoformat(), "status": "fired"},
            )
        
        return {
            "success": True,
            "message": f"Course {course_number} fired for order {order_id}",
            "data": {
                "order_id": order_id,
                "course_number": course_number,
                "items_fired": len(items),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error firing course: {str(e)}")


@router.get("/items/late")
async def get_late_items(
    station_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get all late items"""
    
    from ..models.kds_models import KDSOrderItem
    
    query = db.query(KDSOrderItem).filter(
        KDSOrderItem.status.notin_([DisplayStatus.COMPLETED, DisplayStatus.CANCELLED])
    )
    
    if station_id:
        query = query.filter(KDSOrderItem.station_id == station_id)
    
    # Get items past target time
    late_items = []
    for item in query.all():
        if item.is_late:
            wait_time = (datetime.utcnow() - item.received_at).total_seconds() / 60
            late_items.append({
                "id": item.id,
                "station_id": item.station_id,
                "display_name": item.display_name,
                "status": item.status.value,
                "wait_time_minutes": round(wait_time, 2),
                "target_time": item.target_time.isoformat() if item.target_time else None,
                "minutes_late": round(
                    (datetime.utcnow() - item.target_time).total_seconds() / 60
                    if item.target_time
                    else 0,
                    2,
                ),
            })
    
    # Sort by how late they are
    late_items.sort(key=lambda x: x["minutes_late"], reverse=True)
    
    return {
        "success": True,
        "data": {
            "total_late_items": len(late_items),
            "items": late_items,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }


@router.get("/coordination/status")
async def get_coordination_status(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get coordination status for all items in an order"""
    
    from ..models.kds_models import KDSOrderItem
    from modules.orders.models.order_models import OrderItem
    
    # Get all KDS items for this order
    kds_items = (
        db.query(KDSOrderItem)
        .join(OrderItem)
        .filter(OrderItem.order_id == order_id)
        .all()
    )
    
    # Group by course
    courses = {}
    for item in kds_items:
        course = item.course_number
        if course not in courses:
            courses[course] = []
        
        courses[course].append({
            "id": item.id,
            "display_name": item.display_name,
            "station_id": item.station_id,
            "status": item.status.value,
            "can_fire": not item.fire_time or datetime.utcnow() >= item.fire_time,
            "is_ready": item.status == DisplayStatus.READY,
            "is_complete": item.status == DisplayStatus.COMPLETED,
        })
    
    # Determine overall readiness
    course_status = {}
    for course_num, items in courses.items():
        all_ready = all(item["is_ready"] or item["is_complete"] for item in items)
        any_in_progress = any(
            item["status"] == "in_progress" for item in items
        )
        
        course_status[f"course_{course_num}"] = {
            "items": items,
            "ready_to_serve": all_ready,
            "in_progress": any_in_progress,
            "total_items": len(items),
            "completed_items": sum(1 for item in items if item["is_complete"]),
        }
    
    return {
        "success": True,
        "data": {
            "order_id": order_id,
            "courses": course_status,
            "all_courses_ready": all(
                status["ready_to_serve"] for status in course_status.values()
            ),
            "timestamp": datetime.utcnow().isoformat(),
        },
    }