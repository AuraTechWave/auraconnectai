# backend/modules/tables/routers/table_state_router.py

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import json

from core.database import get_db
from core.auth import get_current_user, require_permission
from core.schemas import User
from ..schemas.table_schemas import (
    TableSessionCreate, TableSessionUpdate, TableSessionResponse,
    TableStatusUpdate, BulkTableStatusUpdate,
    TableReservationCreate, TableReservationUpdate, TableReservationResponse,
    FloorHeatmapData, TableUtilizationStats
)
from ..services.table_state_service import table_state_service
from ..services.reservation_service import reservation_service
from ..models.table_models import ReservationStatus

router = APIRouter(prefix="/table-state", tags=["Table State Management"])


# Session Management Endpoints
@router.post("/sessions", response_model=TableSessionResponse)
@require_permission("tables.manage_sessions")
async def start_session(
    session_data: TableSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Start a new table session
    
    Requires permission: tables.manage_sessions
    """
    return await table_state_service.start_table_session(
        db, current_user.restaurant_id, session_data, current_user.id
    )


@router.put("/sessions/{session_id}", response_model=TableSessionResponse)
@require_permission("tables.manage_sessions")
async def update_session(
    session_id: int,
    update_data: TableSessionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update an active session
    
    Requires permission: tables.manage_sessions
    """
    # TODO: Implement session update
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/sessions/{session_id}/end", response_model=TableSessionResponse)
@require_permission("tables.manage_sessions")
async def end_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    End a table session
    
    Requires permission: tables.manage_sessions
    """
    return await table_state_service.end_table_session(
        db, current_user.restaurant_id, session_id, current_user.id
    )


@router.get("/sessions/active", response_model=List[TableSessionResponse])
async def get_active_sessions(
    floor_id: Optional[int] = Query(None),
    server_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all active table sessions"""
    # TODO: Implement with filters
    raise HTTPException(status_code=501, detail="Not implemented")


# Table Status Management
@router.put("/tables/{table_id}/status")
@require_permission("tables.update_status")
async def update_table_status(
    table_id: int,
    status_update: TableStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update table status
    
    Requires permission: tables.update_status
    """
    table = await table_state_service.update_table_status(
        db, current_user.restaurant_id, table_id, status_update, current_user.id
    )
    return {
        "success": True,
        "table_id": table.id,
        "table_number": table.table_number,
        "new_status": table.status
    }


@router.put("/tables/bulk/status")
@require_permission("tables.update_status")
async def bulk_update_status(
    bulk_update: BulkTableStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update multiple tables status
    
    Requires permission: tables.update_status
    """
    tables = await table_state_service.bulk_update_table_status(
        db, current_user.restaurant_id, bulk_update, current_user.id
    )
    return {
        "success": True,
        "updated_count": len(tables),
        "updated_tables": [
            {
                "table_id": t.id,
                "table_number": t.table_number,
                "new_status": t.status
            }
            for t in tables
        ]
    }


# Availability and Floor Status
@router.get("/availability")
async def check_availability(
    datetime_from: datetime = Query(...),
    datetime_to: datetime = Query(...),
    guest_count: Optional[int] = Query(None, gt=0),
    floor_id: Optional[int] = Query(None),
    section: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Check table availability for a time range"""
    return await table_state_service.get_table_availability(
        db,
        current_user.restaurant_id,
        datetime_from,
        datetime_to,
        guest_count,
        floor_id,
        section
    )


@router.get("/floor-status")
async def get_floor_status(
    floor_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current status of all tables on floor(s)"""
    return await table_state_service.get_floor_status(
        db, current_user.restaurant_id, floor_id
    )


# Reservation Management
@router.post("/reservations", response_model=TableReservationResponse)
async def create_reservation(
    reservation_data: TableReservationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new reservation"""
    return await reservation_service.create_reservation(
        db, current_user.restaurant_id, reservation_data
    )


@router.get("/reservations", response_model=List[TableReservationResponse])
async def get_reservations(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    status: Optional[ReservationStatus] = Query(None),
    customer_id: Optional[int] = Query(None),
    table_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get reservations with filters"""
    return await reservation_service.get_reservations(
        db,
        current_user.restaurant_id,
        date_from,
        date_to,
        status,
        customer_id,
        table_id
    )


@router.get("/reservations/{reservation_id}", response_model=TableReservationResponse)
async def get_reservation(
    reservation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get reservation details"""
    return await reservation_service._get_reservation(
        db, reservation_id, current_user.restaurant_id
    )


@router.put("/reservations/{reservation_id}", response_model=TableReservationResponse)
async def update_reservation(
    reservation_id: int,
    update_data: TableReservationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update reservation details"""
    return await reservation_service.update_reservation(
        db, current_user.restaurant_id, reservation_id, update_data
    )


@router.post("/reservations/{reservation_id}/confirm", response_model=TableReservationResponse)
@require_permission("tables.manage_reservations")
async def confirm_reservation(
    reservation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Confirm a pending reservation
    
    Requires permission: tables.manage_reservations
    """
    return await reservation_service.confirm_reservation(
        db, current_user.restaurant_id, reservation_id
    )


@router.post("/reservations/{reservation_id}/cancel", response_model=TableReservationResponse)
async def cancel_reservation(
    reservation_id: int,
    reason: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Cancel a reservation"""
    return await reservation_service.cancel_reservation(
        db, current_user.restaurant_id, reservation_id, reason
    )


@router.post("/reservations/{reservation_id}/seat")
@require_permission("tables.manage_sessions")
async def seat_reservation(
    reservation_id: int,
    server_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Convert reservation to active session
    
    Requires permission: tables.manage_sessions
    """
    reservation, session = await reservation_service.seat_reservation(
        db, current_user.restaurant_id, reservation_id, server_id
    )
    return {
        "success": True,
        "reservation_id": reservation.id,
        "session_id": session.id,
        "table_number": session.table.table_number
    }


@router.post("/reservations/{reservation_id}/no-show", response_model=TableReservationResponse)
@require_permission("tables.manage_reservations")
async def mark_no_show(
    reservation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark reservation as no-show
    
    Requires permission: tables.manage_reservations
    """
    return await reservation_service.mark_no_show(
        db, current_user.restaurant_id, reservation_id
    )


@router.post("/reservations/send-reminders")
@require_permission("tables.manage_reservations")
async def send_reservation_reminders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Send reminders for upcoming reservations
    
    Requires permission: tables.manage_reservations
    """
    reminded = await reservation_service.send_reminders(
        db, current_user.restaurant_id
    )
    return {
        "success": True,
        "reminders_sent": len(reminded),
        "reservation_codes": [r.reservation_code for r in reminded]
    }


# Analytics Endpoints
@router.get("/analytics/utilization")
@require_permission("tables.view_analytics")
async def get_table_utilization(
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    table_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get table utilization analytics
    
    Requires permission: tables.view_analytics
    """
    return await table_state_service.get_table_analytics(
        db, current_user.restaurant_id, start_date, end_date, table_id
    )


@router.get("/analytics/heatmap", response_model=List[FloorHeatmapData])
@require_permission("tables.view_analytics")
async def get_floor_heatmap(
    period: str = Query("today", regex="^(today|week|month)$"),
    floor_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get floor utilization heatmap data
    
    Requires permission: tables.view_analytics
    """
    # TODO: Implement heatmap generation
    raise HTTPException(status_code=501, detail="Not implemented")


# WebSocket for Real-time Updates
@router.websocket("/ws/{restaurant_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    restaurant_id: int,
    db: AsyncSession = Depends(get_db)
):
    """WebSocket endpoint for real-time table status updates"""
    await websocket.accept()
    
    # TODO: Implement authentication for WebSocket
    # TODO: Implement pub/sub for real-time updates
    
    try:
        while True:
            # Send current floor status periodically
            floor_status = await table_state_service.get_floor_status(
                db, restaurant_id
            )
            
            await websocket.send_json({
                "type": "floor_status",
                "data": floor_status,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Wait for 5 seconds before next update
            await asyncio.sleep(5)
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await websocket.close()