# backend/modules/tables/__init__.py

from .models.table_models import (
    Floor, Table, TableSession, TableCombination,
    TableReservation, TableLayout, TableStateLog,
    TableStatus, TableShape, FloorStatus, ReservationStatus
)

from .schemas.table_schemas import (
    FloorCreate, FloorUpdate, FloorResponse,
    TableCreate, TableUpdate, TableResponse,
    TableSessionCreate, TableSessionUpdate, TableSessionResponse,
    TableReservationCreate, TableReservationUpdate, TableReservationResponse,
    TableLayoutCreate, TableLayoutUpdate, TableLayoutResponse,
    TableStatusUpdate, BulkTableStatusUpdate,
    BulkTableCreate, BulkTableUpdate,
    TableUtilizationStats, FloorHeatmapData
)

from .services.table_state_service import table_state_service
from .services.reservation_service import reservation_service
from .services.layout_service import layout_service

from .routers.table_layout_router import router as layout_router
from .routers.table_state_router import router as state_router

from .websocket.table_websocket import (
    websocket_endpoint,
    manager as websocket_manager,
    notify_table_status_change,
    notify_session_started,
    notify_session_ended,
    notify_reservation_created,
    notify_reservation_cancelled
)

__all__ = [
    # Models
    "Floor", "Table", "TableSession", "TableCombination",
    "TableReservation", "TableLayout", "TableStateLog",
    "TableStatus", "TableShape", "FloorStatus", "ReservationStatus",
    
    # Schemas
    "FloorCreate", "FloorUpdate", "FloorResponse",
    "TableCreate", "TableUpdate", "TableResponse",
    "TableSessionCreate", "TableSessionUpdate", "TableSessionResponse",
    "TableReservationCreate", "TableReservationUpdate", "TableReservationResponse",
    "TableLayoutCreate", "TableLayoutUpdate", "TableLayoutResponse",
    "TableStatusUpdate", "BulkTableStatusUpdate",
    "BulkTableCreate", "BulkTableUpdate",
    "TableUtilizationStats", "FloorHeatmapData",
    
    # Services
    "table_state_service", "reservation_service", "layout_service",
    
    # Routers
    "layout_router", "state_router",
    
    # WebSocket
    "websocket_endpoint", "websocket_manager",
    "notify_table_status_change", "notify_session_started",
    "notify_session_ended", "notify_reservation_created",
    "notify_reservation_cancelled"
]