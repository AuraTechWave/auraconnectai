# backend/modules/kds/routes/kds_routes_improved.py

"""
Improved KDS routes with comprehensive error handling and validation.
"""

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from core.database import get_db
from core.auth import get_current_user
from core.error_handling import handle_api_errors, NotFoundError, APIValidationError, ConflictError
from modules.auth.models import User
from modules.auth.permissions import Permission, check_permission

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
from ..schemas.kds_bulk_schemas import (
    BulkStationStatusUpdateRequest,
    BulkStationStatusUpdateResponse,
    OrderRoutingResponse
)
from ..models.kds_models import DisplayStatus, StationType, StationStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/kds", tags=["Kitchen Display System"])

# WebSocket manager instance
ws_manager = KDSWebSocketManager()

# ========== Station Management ==========

@router.post("/stations", response_model=StationResponse, status_code=status.HTTP_201_CREATED)
@handle_api_errors
async def create_station(
    station_data: StationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new kitchen station with validation.
    
    Returns:
        Created station object
        
    Raises:
        403: Insufficient permissions
        409: Station with same name already exists
        422: Validation error
    """
    check_permission(current_user, Permission.KDS_MANAGE)
    
    service = KDSService(db)
    
    # Check for duplicate station name
    existing = service.get_station_by_name(station_data.name)
    if existing:
        raise ConflictError(
            f"Station with name '{station_data.name}' already exists",
            {"existing_id": existing.id}
        )
    
    station = service.create_station(station_data)
    
    # Broadcast station update
    await ws_manager.broadcast_station_update(station.id, {
        "action": "created",
        "station": StationResponse.from_orm(station).dict()
    })
    
    return station

@router.get("/stations", response_model=List[StationResponse])
@handle_api_errors
async def list_stations(
    include_inactive: bool = Query(False, description="Include inactive stations"),
    station_type: Optional[StationType] = Query(None, description="Filter by station type"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=200, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List kitchen stations with pagination and filters.
    
    Returns:
        Paginated list of stations with counts
        
    Raises:
        403: Insufficient permissions
        422: Invalid query parameters
    """
    check_permission(current_user, Permission.KDS_VIEW)
    
    service = KDSService(db)
    
    # Apply filters
    if station_type:
        stations = service.get_stations_by_type(station_type)
    else:
        stations = service.get_all_stations(include_inactive)
    
    # Apply pagination
    start_idx = (page - 1) * size
    end_idx = start_idx + size
    paginated_stations = stations[start_idx:end_idx]
    
    # Add computed fields
    responses = []
    for station in paginated_stations:
        response = StationResponse.from_orm(station)
        
        # Get active and pending counts safely
        try:
            items = service.get_station_items(station.id)
            response.active_items_count = sum(1 for item in items if item.status == DisplayStatus.IN_PROGRESS)
            response.pending_items_count = sum(1 for item in items if item.status == DisplayStatus.PENDING)
        except Exception as e:
            logger.warning(f"Error getting item counts for station {station.id}: {e}")
            response.active_items_count = 0
            response.pending_items_count = 0
        
        responses.append(response)
    
    return responses

@router.get("/stations/{station_id}", response_model=StationResponse)
@handle_api_errors
async def get_station(
    station_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific kitchen station.
    
    Returns:
        Station details with item counts
        
    Raises:
        403: Insufficient permissions
        404: Station not found
    """
    check_permission(current_user, Permission.KDS_VIEW)
    
    service = KDSService(db)
    station = service.get_station(station_id)
    
    if not station:
        raise NotFoundError("Station", station_id)
    
    response = StationResponse.from_orm(station)
    
    # Add computed fields safely
    try:
        items = service.get_station_items(station.id)
        response.active_items_count = sum(1 for item in items if item.status == DisplayStatus.IN_PROGRESS)
        response.pending_items_count = sum(1 for item in items if item.status == DisplayStatus.PENDING)
    except Exception as e:
        logger.warning(f"Error getting item counts for station {station.id}: {e}")
        response.active_items_count = 0
        response.pending_items_count = 0
    
    return response

@router.put("/stations/{station_id}", response_model=StationResponse)
@handle_api_errors
async def update_station(
    station_id: int,
    update_data: StationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a kitchen station.
    
    Returns:
        Updated station
        
    Raises:
        403: Insufficient permissions
        404: Station not found
        409: Name conflict
        422: Validation error
    """
    check_permission(current_user, Permission.KDS_MANAGE)
    
    service = KDSService(db)
    
    # Check station exists
    existing = service.get_station(station_id)
    if not existing:
        raise NotFoundError("Station", station_id)
    
    # Check for name conflict if updating name
    if update_data.name and update_data.name != existing.name:
        duplicate = service.get_station_by_name(update_data.name)
        if duplicate:
            raise ConflictError(
                f"Station with name '{update_data.name}' already exists",
                {"existing_id": duplicate.id}
            )
    
    station = service.update_station(station_id, update_data)
    
    # Broadcast station update
    await ws_manager.broadcast_station_update(station_id, {
        "action": "updated",
        "station": StationResponse.from_orm(station).dict()
    })
    
    return station

@router.delete("/stations/{station_id}", status_code=status.HTTP_204_NO_CONTENT)
@handle_api_errors
async def delete_station(
    station_id: int,
    force: bool = Query(False, description="Force delete even with active items"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a kitchen station (soft delete).
    
    Returns:
        No content on success
        
    Raises:
        403: Insufficient permissions
        404: Station not found
        409: Station has active items (unless force=true)
    """
    check_permission(current_user, Permission.KDS_MANAGE)
    
    service = KDSService(db)
    
    station = service.get_station(station_id)
    if not station:
        raise NotFoundError("Station", station_id)
    
    # Check for active items unless force delete
    if not force:
        items = service.get_station_items(station_id, [DisplayStatus.PENDING, DisplayStatus.IN_PROGRESS])
        if items:
            raise ConflictError(
                "Cannot delete station with active items",
                {"active_items": len(items)}
            )
    
    # Soft delete by marking as inactive
    update_data = StationUpdate(status=StationStatus.INACTIVE)
    service.update_station(station_id, update_data)
    
    # Broadcast station update
    await ws_manager.broadcast_station_update(station_id, {
        "action": "deleted",
        "station_id": station_id
    })

# ========== Display Management ==========

@router.post("/displays", response_model=KitchenDisplayResponse, status_code=status.HTTP_201_CREATED)
@handle_api_errors
async def create_display(
    display_data: KitchenDisplayCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new display for a station.
    
    Returns:
        Created display object
        
    Raises:
        403: Insufficient permissions
        404: Station not found
        409: Display name already exists
        422: Validation error
    """
    check_permission(current_user, Permission.KDS_MANAGE)
    
    service = KDSService(db)
    
    # Validate station exists
    station = service.get_station(display_data.station_id)
    if not station:
        raise NotFoundError("Station", display_data.station_id)
    
    # Check for duplicate display name
    existing = service.get_display_by_name(display_data.name)
    if existing:
        raise ConflictError(
            f"Display with name '{display_data.name}' already exists",
            {"existing_id": existing.id}
        )
    
    display = service.create_display(display_data)
    return display

@router.put("/displays/{display_id}", response_model=KitchenDisplayResponse)
@handle_api_errors
async def update_display(
    display_id: int,
    update_data: KitchenDisplayUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a kitchen display.
    
    Returns:
        Updated display
        
    Raises:
        403: Insufficient permissions
        404: Display not found
        409: Name conflict
        422: Validation error
    """
    check_permission(current_user, Permission.KDS_MANAGE)
    
    service = KDSService(db)
    
    existing = service.get_display(display_id)
    if not existing:
        raise NotFoundError("Display", display_id)
    
    # Check for name conflict if updating name
    if update_data.name and update_data.name != existing.name:
        duplicate = service.get_display_by_name(update_data.name)
        if duplicate:
            raise ConflictError(
                f"Display with name '{update_data.name}' already exists",
                {"existing_id": duplicate.id}
            )
    
    display = service.update_display(display_id, update_data)
    return display

@router.post("/displays/{display_id}/heartbeat", status_code=status.HTTP_204_NO_CONTENT)
@handle_api_errors
async def update_display_heartbeat(
    display_id: int,
    db: Session = Depends(get_db)
):
    """
    Update display heartbeat (no auth required for displays).
    
    Returns:
        No content on success
        
    Raises:
        404: Display not found
    """
    service = KDSService(db)
    
    display = service.get_display(display_id)
    if not display:
        raise NotFoundError("Display", display_id)
    
    service.update_display_heartbeat(display_id)

# ========== Station Assignments ==========

@router.post("/assignments", response_model=StationAssignmentResponse, status_code=status.HTTP_201_CREATED)
@handle_api_errors
async def create_station_assignment(
    assignment_data: StationAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a station assignment rule.
    
    Returns:
        Created assignment
        
    Raises:
        403: Insufficient permissions
        404: Station not found
        409: Assignment already exists
        422: Validation error
    """
    check_permission(current_user, Permission.KDS_MANAGE)
    
    routing_service = KDSOrderRoutingService(db)
    service = KDSService(db)
    
    # Validate station exists
    station = service.get_station(assignment_data.station_id)
    if not station:
        raise NotFoundError("Station", assignment_data.station_id)
    
    # Check for duplicate assignment
    existing = routing_service.get_existing_assignment(
        assignment_data.station_id,
        assignment_data.assignment_type,
        assignment_data.assignment_value
    )
    if existing:
        raise ConflictError(
            "Assignment already exists",
            {"existing_id": existing.id}
        )
    
    assignment = routing_service.create_station_assignment(assignment_data)
    return assignment

@router.get("/assignments", response_model=List[StationAssignmentResponse])
@handle_api_errors
async def list_station_assignments(
    station_id: Optional[int] = Query(None, description="Filter by station ID"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List station assignment rules with pagination.
    
    Returns:
        Paginated list of assignments
        
    Raises:
        403: Insufficient permissions
        404: Station not found (if station_id provided)
    """
    check_permission(current_user, Permission.KDS_VIEW)
    
    routing_service = KDSOrderRoutingService(db)
    
    # Validate station if provided
    if station_id:
        service = KDSService(db)
        station = service.get_station(station_id)
        if not station:
            raise NotFoundError("Station", station_id)
    
    assignments = routing_service.get_station_assignments(station_id)
    
    # Apply pagination
    start_idx = (page - 1) * size
    end_idx = start_idx + size
    
    return assignments[start_idx:end_idx]

@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
@handle_api_errors
async def delete_station_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a station assignment rule.
    
    Returns:
        No content on success
        
    Raises:
        403: Insufficient permissions
        404: Assignment not found
    """
    check_permission(current_user, Permission.KDS_MANAGE)
    
    routing_service = KDSOrderRoutingService(db)
    
    assignment = routing_service.get_assignment(assignment_id)
    if not assignment:
        raise NotFoundError("Assignment", assignment_id)
    
    routing_service.delete_station_assignment(assignment_id)

# ========== Menu Item Station Mapping ==========

@router.post("/menu-items/stations", response_model=MenuItemStationResponse, status_code=status.HTTP_201_CREATED)
@handle_api_errors
async def assign_menu_item_to_station(
    assignment_data: MenuItemStationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Assign a menu item to a station.
    
    Returns:
        Created assignment
        
    Raises:
        403: Insufficient permissions
        404: Station or menu item not found
        409: Assignment already exists
        422: Validation error
    """
    check_permission(current_user, Permission.KDS_MANAGE)
    
    routing_service = KDSOrderRoutingService(db)
    service = KDSService(db)
    
    # Validate station exists
    station = service.get_station(assignment_data.station_id)
    if not station:
        raise NotFoundError("Station", assignment_data.station_id)
    
    # TODO: Validate menu item exists when menu module is available
    
    # Check for duplicate assignment
    existing = routing_service.get_menu_item_station_assignment(
        assignment_data.menu_item_id,
        assignment_data.station_id
    )
    if existing:
        raise ConflictError(
            "Menu item already assigned to this station",
            {"existing_id": existing.id}
        )
    
    assignment = routing_service.assign_menu_item_to_station(assignment_data)
    return assignment

@router.get("/menu-items/{menu_item_id}/stations", response_model=List[MenuItemStationResponse])
@handle_api_errors
async def get_menu_item_stations(
    menu_item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all station assignments for a menu item.
    
    Returns:
        List of station assignments
        
    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.KDS_VIEW)
    
    routing_service = KDSOrderRoutingService(db)
    assignments = routing_service.get_menu_item_stations(menu_item_id)
    return assignments

# ========== Order Item Management ==========

@router.get("/stations/{station_id}/items", response_model=List[KDSOrderItemResponse])
@handle_api_errors
async def get_station_items(
    station_id: int,
    status: Optional[List[DisplayStatus]] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum items to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get order items for a station.
    
    Returns:
        List of order items with details
        
    Raises:
        403: Insufficient permissions
        404: Station not found
    """
    check_permission(current_user, Permission.KDS_VIEW)
    
    service = KDSService(db)
    
    # Validate station exists
    station = service.get_station(station_id)
    if not station:
        raise NotFoundError("Station", station_id)
    
    items = service.get_station_items(station_id, status, limit)
    
    # Enrich with order data safely
    responses = []
    for item in items:
        try:
            response = KDSOrderItemResponse.from_orm(item)
            if item.order_item and item.order_item.order:
                response.order_id = item.order_item.order.id
                response.table_number = item.order_item.order.table_no
            responses.append(response)
        except Exception as e:
            logger.warning(f"Error enriching item {item.id}: {e}")
            responses.append(KDSOrderItemResponse.from_orm(item))
    
    return responses

@router.post("/items/{item_id}/acknowledge", status_code=status.HTTP_204_NO_CONTENT)
@handle_api_errors
async def acknowledge_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Acknowledge an order item.
    
    Returns:
        No content on success
        
    Raises:
        403: Insufficient permissions
        404: Item not found
        409: Invalid state transition
    """
    check_permission(current_user, Permission.KDS_OPERATE)
    
    service = KDSService(db)
    
    item = service.get_item(item_id)
    if not item:
        raise NotFoundError("Item", item_id)
    
    if item.status != DisplayStatus.PENDING:
        raise ConflictError(
            "Can only acknowledge pending items",
            {"current_status": item.status}
        )
    
    item = service.acknowledge_item(item_id, current_user.id)
    
    # Broadcast item update
    await ws_manager.broadcast_item_update(item.station_id, item_id, {
        "action": "acknowledged",
        "item": KDSOrderItemResponse.from_orm(item).dict()
    })

@router.post("/items/{item_id}/start", status_code=status.HTTP_204_NO_CONTENT)
@handle_api_errors
async def start_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark an item as started.
    
    Returns:
        No content on success
        
    Raises:
        403: Insufficient permissions
        404: Item not found
        409: Invalid state transition
    """
    check_permission(current_user, Permission.KDS_OPERATE)
    
    service = KDSService(db)
    
    item = service.get_item(item_id)
    if not item:
        raise NotFoundError("Item", item_id)
    
    if item.status not in [DisplayStatus.PENDING, DisplayStatus.ACKNOWLEDGED]:
        raise ConflictError(
            "Can only start pending or acknowledged items",
            {"current_status": item.status}
        )
    
    item = service.start_item(item_id, current_user.id)
    
    # Broadcast item update
    await ws_manager.broadcast_item_update(item.station_id, item_id, {
        "action": "started",
        "item": KDSOrderItemResponse.from_orm(item).dict()
    })

@router.post("/items/{item_id}/complete", status_code=status.HTTP_204_NO_CONTENT)
@handle_api_errors
async def complete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark an item as completed.
    
    Returns:
        No content on success
        
    Raises:
        403: Insufficient permissions
        404: Item not found
        409: Invalid state transition
    """
    check_permission(current_user, Permission.KDS_OPERATE)
    
    service = KDSService(db)
    
    item = service.get_item(item_id)
    if not item:
        raise NotFoundError("Item", item_id)
    
    if item.status != DisplayStatus.IN_PROGRESS:
        raise ConflictError(
            "Can only complete items that are in progress",
            {"current_status": item.status}
        )
    
    item = service.complete_item(item_id, current_user.id)
    
    # Broadcast item update
    await ws_manager.broadcast_item_update(item.station_id, item_id, {
        "action": "completed",
        "item": KDSOrderItemResponse.from_orm(item).dict()
    })

@router.post("/items/{item_id}/recall", status_code=status.HTTP_204_NO_CONTENT)
@handle_api_errors
async def recall_item(
    item_id: int,
    reason: Optional[str] = Query(None, max_length=500, description="Reason for recall"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Recall a completed item.
    
    Returns:
        No content on success
        
    Raises:
        403: Insufficient permissions
        404: Item not found
        409: Item not completed
    """
    check_permission(current_user, Permission.KDS_OPERATE)
    
    service = KDSService(db)
    
    item = service.get_item(item_id)
    if not item:
        raise NotFoundError("Item", item_id)
    
    if item.status != DisplayStatus.COMPLETED:
        raise ConflictError(
            "Can only recall completed items",
            {"current_status": item.status}
        )
    
    item = service.recall_item(item_id, reason)
    
    # Broadcast item update
    await ws_manager.broadcast_item_update(item.station_id, item_id, {
        "action": "recalled",
        "item": KDSOrderItemResponse.from_orm(item).dict(),
        "reason": reason
    })

# ========== Station Statistics ==========

@router.get("/stations/{station_id}/summary", response_model=StationSummary)
@handle_api_errors
async def get_station_summary(
    station_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get summary statistics for a station.
    
    Returns:
        Station summary with metrics
        
    Raises:
        403: Insufficient permissions
        404: Station not found
    """
    check_permission(current_user, Permission.KDS_VIEW)
    
    service = KDSService(db)
    
    station = service.get_station(station_id)
    if not station:
        raise NotFoundError("Station", station_id)
    
    summary = service.get_station_summary(station_id)
    return summary

@router.get("/stations/summaries", response_model=List[StationSummary])
@handle_api_errors
async def get_all_station_summaries(
    include_inactive: bool = Query(False, description="Include inactive stations"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get summaries for all stations.
    
    Returns:
        List of station summaries
        
    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.KDS_VIEW)
    
    service = KDSService(db)
    summaries = service.get_all_station_summaries(include_inactive)
    return summaries

# ========== WebSocket Endpoints ==========

@router.websocket("/ws/{station_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    station_id: int,
    db: Session = Depends(get_db)
):
    """
    WebSocket connection for real-time KDS updates.
    
    Note: WebSocket connections handle their own error responses.
    """
    # Validate station exists
    service = KDSService(db)
    station = service.get_station(station_id)
    
    if not station:
        await websocket.close(code=4004, reason=f"Station {station_id} not found")
        return
    
    await ws_manager.connect(websocket, station_id)
    
    try:
        # Send initial data
        items = service.get_station_items(station_id)
        
        await websocket.send_json({
            "type": "initial_data",
            "data": {
                "station": StationResponse.from_orm(station).dict(),
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
                try:
                    # Parse and validate message
                    import json
                    message = json.loads(data)
                    logger.debug(f"Received WebSocket message: {message}")
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid JSON format"
                    })
                
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, station_id)
        logger.info(f"WebSocket disconnected for station {station_id}")
    except Exception as e:
        logger.error(f"WebSocket error for station {station_id}: {str(e)}")
        ws_manager.disconnect(websocket, station_id)
        await websocket.close(code=4000, reason="Internal error")

# ========== Order Integration ==========

@router.post("/orders/{order_id}/route", response_model=OrderRoutingResponse)
@handle_api_errors
async def route_order_to_stations(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Route an order's items to appropriate kitchen stations.
    
    Returns:
        Routing summary
        
    Raises:
        403: Insufficient permissions
        404: Order not found
        422: No routing rules configured
    """
    check_permission(current_user, Permission.KDS_OPERATE)
    
    routing_service = KDSOrderRoutingService(db)
    
    # TODO: Validate order exists when orders module is available
    
    try:
        routed_items = routing_service.route_order_to_stations(order_id)
        
        if not routed_items:
            raise APIValidationError(
                "No items could be routed. Check station assignments and menu item mappings.",
                {"order_id": order_id}
            )
        
        # Broadcast new items to relevant stations
        station_items = {}
        for item in routed_items:
            if item.station_id not in station_items:
                station_items[item.station_id] = []
            station_items[item.station_id].append(item)
        
        for station_id, items in station_items.items():
            await ws_manager.broadcast_new_items(station_id, {
                "items": [KDSOrderItemResponse.from_orm(item).dict() for item in items]
            })
        
        return OrderRoutingResponse(
            message="Order routed successfully",
            items_routed=len(routed_items),
            stations_affected=len(station_items),
            routing_summary={
                str(station_id): len(items) 
                for station_id, items in station_items.items()
            }
        )
        
    except ValueError as e:
        if "not found" in str(e).lower():
            raise NotFoundError("Order", order_id)
        raise APIValidationError(str(e))

# ========== Bulk Operations ==========

@router.post("/stations/bulk/update-status", response_model=BulkStationStatusUpdateResponse)
@handle_api_errors
async def bulk_update_station_status(
    request: BulkStationStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update status for multiple stations.
    
    Returns:
        Update summary
        
    Raises:
        403: Insufficient permissions
        422: Invalid station IDs
    """
    check_permission(current_user, Permission.KDS_MANAGE)
    
    station_ids = request.station_ids
    status = request.status
    service = KDSService(db)
    
    updated_count = 0
    errors = []
    updated_stations = []
    
    for station_id in station_ids:
        try:
            station = service.get_station(station_id)
            if not station:
                errors.append({"station_id": station_id, "error": "Not found"})
                continue
            
            service.update_station(station_id, StationUpdate(status=status))
            updated_count += 1
            updated_stations.append(station_id)
            
            # Broadcast update
            await ws_manager.broadcast_station_update(station_id, {
                "action": "status_updated",
                "status": status
            })
            
        except Exception as e:
            errors.append({"station_id": station_id, "error": str(e)})
    
    return BulkStationStatusUpdateResponse(
        message=f"Updated {updated_count} stations",
        updated_count=updated_count,
        errors=errors if errors else None,
        updated_stations=updated_stations
    )