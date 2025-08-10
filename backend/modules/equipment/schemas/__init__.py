# backend/modules/equipment/schemas/__init__.py
"""Equipment schemas module"""

from .equipment_schemas import (
    EquipmentBase,
    EquipmentCreate,
    EquipmentUpdate,
    Equipment,
    MaintenanceRecordBase,
    MaintenanceRecordCreate,
    MaintenanceRecordUpdate,
    MaintenanceRecordComplete,
    MaintenanceRecord,
    EquipmentWithMaintenance,
    EquipmentSearchParams,
    MaintenanceSearchParams,
    EquipmentListResponse,
    MaintenanceListResponse,
    MaintenanceSummary
)

from .equipment_schemas_improved import (
    EquipmentBase as EquipmentBaseImproved,
    EquipmentCreate as EquipmentCreateImproved,
    EquipmentUpdate as EquipmentUpdateImproved,
    Equipment as EquipmentImproved,
    MaintenanceRecordBase as MaintenanceRecordBaseImproved,
    MaintenanceRecordCreate as MaintenanceRecordCreateImproved,
    MaintenanceRecordUpdate as MaintenanceRecordUpdateImproved,
    MaintenanceRecordComplete as MaintenanceRecordCompleteImproved,
    MaintenanceRecord as MaintenanceRecordImproved,
    EquipmentWithMaintenance as EquipmentWithMaintenanceImproved,
    EquipmentSearchParams as EquipmentSearchParamsImproved,
    MaintenanceSearchParams as MaintenanceSearchParamsImproved,
    EquipmentListResponse as EquipmentListResponseImproved,
    MaintenanceListResponse as MaintenanceListResponseImproved,
    MaintenanceSummary as MaintenanceSummaryImproved
)

__all__ = [
    # Original schemas
    "EquipmentBase",
    "EquipmentCreate",
    "EquipmentUpdate",
    "Equipment",
    "MaintenanceRecordBase",
    "MaintenanceRecordCreate",
    "MaintenanceRecordUpdate",
    "MaintenanceRecordComplete",
    "MaintenanceRecord",
    "EquipmentWithMaintenance",
    "EquipmentSearchParams",
    "MaintenanceSearchParams",
    "EquipmentListResponse",
    "MaintenanceListResponse",
    "MaintenanceSummary",
    # Improved schemas
    "EquipmentBaseImproved",
    "EquipmentCreateImproved",
    "EquipmentUpdateImproved",
    "EquipmentImproved",
    "MaintenanceRecordBaseImproved",
    "MaintenanceRecordCreateImproved",
    "MaintenanceRecordUpdateImproved",
    "MaintenanceRecordCompleteImproved",
    "MaintenanceRecordImproved",
    "EquipmentWithMaintenanceImproved",
    "EquipmentSearchParamsImproved",
    "MaintenanceSearchParamsImproved",
    "EquipmentListResponseImproved",
    "MaintenanceListResponseImproved",
    "MaintenanceSummaryImproved"
]