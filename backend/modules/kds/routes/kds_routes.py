# backend/modules/kds/routes/kds_routes.py

"""
API routes for Kitchen Display System.
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json
import asyncio
import logging

from core.database import get_db
from core.auth import get_current_user
from ..services.kds_service import KDSService
from ..services.kds_order_routing_service import KDSOrderRoutingService
from ..services.kds_websocket_manager import KDSWebSocketManager
from ..schemas.kds_schemas import (
    StationCreate, StationUpdate, StationResponse,
    KitchenDisplayCreate, KitchenDisplayUpdate, KitchenDisplayResponse,
    StationAssignmentCreate, StationAssignmentResponse,
    MenuItemStationCreate, MenuItemStationResponse,
    KDSOrderItemResponse, StationSummary,
    KDSWebSocketMessage
)
from ..models.kds_models import DisplayStatus, StationType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/kds", tags=["Kitchen Display System"])

# WebSocket manager instance
ws_manager = KDSWebSocketManager()

# ========== Station Management ==========

@router.post("/stations", response_model=StationResponse)
async def create_station(
    station_data: StationCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new kitchen station"""
    service = KDSService(db)
    station = service.create_station(station_data)
    
    # Broadcast station update
    await ws_manager.broadcast_station_update(station.id, {
        "action": "created",
        "station": StationResponse.from_orm(station).dict()
    })
    
    return station

@router.get("/stations", response_model=List[StationResponse])
async def list_stations(
    include_inactive: bool = Query(False),
    station_type: Optional[StationType] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """List all kitchen stations"""
    service = KDSService(db)
    
    if station_type:
        stations = service.get_stations_by_type(station_type)
    else:
        stations = service.get_all_stations(include_inactive)
    
    # Add computed fields
    responses = []
    for station in stations:
        response = StationResponse.from_orm(station)
        
        # Get active and pending counts
        items = service.get_station_items(station.id)
        response.active_items_count = sum(1 for item in items if item.status == DisplayStatus.IN_PROGRESS)
        response.pending_items_count = sum(1 for item in items if item.status == DisplayStatus.PENDING)
        
        responses.append(response)
    
    return responses

@router.get("/stations/{station_id}", response_model=StationResponse)
async def get_station(
    station_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get a specific kitchen station"""
    service = KDSService(db)
    station = service.get_station(station_id)
    
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    
    response = StationResponse.from_orm(station)
    
    # Add computed fields
    items = service.get_station_items(station.id)
    response.active_items_count = sum(1 for item in items if item.status == DisplayStatus.IN_PROGRESS)
    response.pending_items_count = sum(1 for item in items if item.status == DisplayStatus.PENDING)
    
    return response

@router.put("/stations/{station_id}", response_model=StationResponse)
async def update_station(
    station_id: int,
    update_data: StationUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update a kitchen station"""
    service = KDSService(db)
    
    try:
        station = service.update_station(station_id, update_data)
        
        # Broadcast station update
        await ws_manager.broadcast_station_update(station_id, {
            "action": "updated",
            "station": StationResponse.from_orm(station).dict()
        })
        
        return station
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/stations/{station_id}")
async def delete_station(
    station_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete a kitchen station (soft delete by marking as inactive)"""
    service = KDSService(db)
    
    try:
        from ..models.kds_models import StationStatus
        update_data = StationUpdate(status=StationStatus.INACTIVE)
        service.update_station(station_id, update_data)
        
        # Broadcast station update
        await ws_manager.broadcast_station_update(station_id, {
            "action": "deleted",
            "station_id": station_id
        })
        
        return {"message": "Station deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# ========== Display Management ==========

@router.post("/displays", response_model=KitchenDisplayResponse)
async def create_display(
    display_data: KitchenDisplayCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new display for a station"""
    service = KDSService(db)
    
    try:
        display = service.create_display(display_data)
        return display
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/displays/{display_id}", response_model=KitchenDisplayResponse)
async def update_display(
    display_id: int,
    update_data: KitchenDisplayUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update a kitchen display"""
    service = KDSService(db)
    
    try:
        display = service.update_display(display_id, update_data)
        return display
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/displays/{display_id}/heartbeat")
async def update_display_heartbeat(
    display_id: int,
    db: Session = Depends(get_db)
):
    """Update display heartbeat (no auth required for displays)"""
    service = KDSService(db)
    service.update_display_heartbeat(display_id)
    return {"status": "ok", "timestamp": datetime.utcnow()}

# ========== Station Assignments ==========

@router.post("/assignments", response_model=StationAssignmentResponse)
async def create_station_assignment(
    assignment_data: StationAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a station assignment rule"""
    routing_service = KDSOrderRoutingService(db)
    
    try:
        assignment = routing_service.create_station_assignment(assignment_data)
        return assignment
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/assignments", response_model=List[StationAssignmentResponse])
async def list_station_assignments(
    station_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """List station assignment rules"""
    routing_service = KDSOrderRoutingService(db)
    assignments = routing_service.get_station_assignments(station_id)
    return assignments

@router.delete("/assignments/{assignment_id}")
async def delete_station_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete a station assignment rule"""
    routing_service = KDSOrderRoutingService(db)
    
    try:
        routing_service.delete_station_assignment(assignment_id)
        return {"message": "Assignment deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# ========== Menu Item Station Mapping ==========

@router.post("/menu-items/stations", response_model=MenuItemStationResponse)
async def assign_menu_item_to_station(
    assignment_data: MenuItemStationCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Assign a menu item to a station"""
    routing_service = KDSOrderRoutingService(db)
    
    try:
        assignment = routing_service.assign_menu_item_to_station(assignment_data)
        return assignment
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/menu-items/{menu_item_id}/stations", response_model=List[MenuItemStationResponse])
async def get_menu_item_stations(
    menu_item_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all station assignments for a menu item"""
    routing_service = KDSOrderRoutingService(db)
    assignments = routing_service.get_menu_item_stations(menu_item_id)
    return assignments

# ========== Order Item Management ==========

@router.get("/stations/{station_id}/items", response_model=List[KDSOrderItemResponse])
async def get_station_items(
    station_id: int,
    status: Optional[List[DisplayStatus]] = Query(None),
    limit: int = Query(50, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get order items for a station"""
    service = KDSService(db)
    items = service.get_station_items(station_id, status, limit)
    
    # Enrich with order data
    responses = []
    for item in items:
        response = KDSOrderItemResponse.from_orm(item)
        if item.order_item and item.order_item.order:
            response.order_id = item.order_item.order.id
            response.table_number = item.order_item.order.table_no
            # Note: server_name would need to be fetched from staff member
        responses.append(response)
    
    return responses

@router.post("/items/{item_id}/acknowledge")
async def acknowledge_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Acknowledge an order item"""
    service = KDSService(db)
    
    try:
        item = service.acknowledge_item(item_id, current_user["id"])
        
        # Broadcast item update
        await ws_manager.broadcast_item_update(item.station_id, item_id, {
            "action": "acknowledged",
            "item": KDSOrderItemResponse.from_orm(item).dict()
        })
        
        return {"message": "Item acknowledged"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/items/{item_id}/start")
async def start_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Mark an item as started"""
    service = KDSService(db)
    
    try:
        item = service.start_item(item_id, current_user["id"])
        
        # Broadcast item update
        await ws_manager.broadcast_item_update(item.station_id, item_id, {
            "action": "started",
            "item": KDSOrderItemResponse.from_orm(item).dict()
        })
        
        return {"message": "Item started"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/items/{item_id}/complete")
async def complete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Mark an item as completed"""
    service = KDSService(db)
    
    try:
        item = service.complete_item(item_id, current_user["id"])
        
        # Broadcast item update
        await ws_manager.broadcast_item_update(item.station_id, item_id, {
            "action": "completed",
            "item": KDSOrderItemResponse.from_orm(item).dict()
        })
        
        return {"message": "Item completed"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/items/{item_id}/recall")
async def recall_item(
    item_id: int,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Recall a completed item"""
    service = KDSService(db)
    
    try:
        item = service.recall_item(item_id, reason)
        
        # Broadcast item update
        await ws_manager.broadcast_item_update(item.station_id, item_id, {
            "action": "recalled",
            "item": KDSOrderItemResponse.from_orm(item).dict()
        })
        
        return {"message": "Item recalled"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ========== Station Statistics ==========

@router.get("/stations/{station_id}/summary", response_model=StationSummary)
async def get_station_summary(
    station_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get summary statistics for a station"""
    service = KDSService(db)
    
    try:
        summary = service.get_station_summary(station_id)
        return summary
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/stations/summaries", response_model=List[StationSummary])
async def get_all_station_summaries(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get summaries for all active stations"""
    service = KDSService(db)
    summaries = service.get_all_station_summaries()
    return summaries

# ========== WebSocket Endpoints ==========

@router.websocket("/ws/{station_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    station_id: int,
    db: Session = Depends(get_db)
):
    """WebSocket connection for real-time KDS updates"""
    await ws_manager.connect(websocket, station_id)
    
    try:
        # Send initial data
        service = KDSService(db)
        items = service.get_station_items(station_id)
        
        await websocket.send_json({
            "type": "initial_data",
            "data": {
                "items": [KDSOrderItemResponse.from_orm(item).dict() for item in items]
            }
        })
        
        # Keep connection alive
        while True:
            # Wait for messages from client
            data = await websocket.receive_text()
            
            # Handle heartbeat
            if data == "ping":
                await websocket.send_text("pong")
            else:
                # Process other messages if needed
                pass
                
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, station_id)
        logger.info(f"WebSocket disconnected for station {station_id}")
    except Exception as e:
        logger.error(f"WebSocket error for station {station_id}: {str(e)}")
        ws_manager.disconnect(websocket, station_id)

# ========== Order Integration ==========

@router.post("/orders/{order_id}/route")
async def route_order_to_stations(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Route an order's items to appropriate kitchen stations"""
    routing_service = KDSOrderRoutingService(db)
    
    try:
        routed_items = routing_service.route_order_to_stations(order_id)
        
        # Broadcast new items to relevant stations
        for item in routed_items:
            await ws_manager.broadcast_new_item(item.station_id, {
                "item": KDSOrderItemResponse.from_orm(item).dict()
            })
        
        return {
            "message": "Order routed successfully",
            "items_routed": len(routed_items)
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))