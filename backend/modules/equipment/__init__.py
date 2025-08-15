# backend/modules/equipment/__init__.py
"""Equipment maintenance module for restaurant equipment tracking and maintenance scheduling."""

from .routes import router, router_improved
from .services import EquipmentService
from .models import (
    Equipment,
    MaintenanceRecord,
    EquipmentStatus,
    MaintenanceStatus,
    MaintenanceType,
)
from .schemas import (
    EquipmentCreate,
    EquipmentUpdate,
    Equipment as EquipmentSchema,
    MaintenanceRecordCreate,
    MaintenanceRecordUpdate,
    MaintenanceRecord as MaintenanceRecordSchema,
)

__all__ = [
    "router",
    "router_improved",
    "EquipmentService",
    "Equipment",
    "MaintenanceRecord",
    "EquipmentStatus",
    "MaintenanceStatus",
    "MaintenanceType",
    "EquipmentCreate",
    "EquipmentUpdate",
    "EquipmentSchema",
    "MaintenanceRecordCreate",
    "MaintenanceRecordUpdate",
    "MaintenanceRecordSchema",
]
