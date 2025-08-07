# backend/modules/equipment/routes.py

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import get_current_user
from modules.auth.models import User
from modules.auth.permissions import Permission, check_permission

from .service import EquipmentService
from .schemas import (
    Equipment, EquipmentCreate, EquipmentUpdate, EquipmentWithMaintenance,
    EquipmentSearchParams, EquipmentListResponse,
    MaintenanceRecord, MaintenanceRecordCreate, MaintenanceRecordUpdate,
    MaintenanceRecordComplete, MaintenanceSearchParams, MaintenanceListResponse,
    MaintenanceSummary
)

router = APIRouter(prefix="/equipment", tags=["equipment"])


# Equipment endpoints
@router.post("/", response_model=Equipment, status_code=status.HTTP_201_CREATED)
async def create_equipment(
    equipment_data: EquipmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create new equipment"""
    check_permission(current_user, Permission.EQUIPMENT_CREATE)
    service = EquipmentService(db)
    return service.create_equipment(equipment_data, current_user.id)


@router.get("/search", response_model=EquipmentListResponse)
async def search_equipment(
    query: Optional[str] = Query(None, description="Search query for equipment name, type, manufacturer, etc."),
    equipment_type: Optional[str] = Query(None, description="Filter by equipment type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    location: Optional[str] = Query(None, description="Filter by location"),
    is_critical: Optional[bool] = Query(None, description="Filter by critical equipment"),
    needs_maintenance: Optional[bool] = Query(None, description="Filter equipment needing maintenance"),
    sort_by: str = Query("equipment_name", pattern="^(equipment_name|next_due_date|status|created_at)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Search equipment with filters and pagination"""
    check_permission(current_user, Permission.EQUIPMENT_VIEW)
    
    # Build search params
    params = EquipmentSearchParams(
        query=query,
        equipment_type=equipment_type,
        status=status,
        location=location,
        is_critical=is_critical,
        needs_maintenance=needs_maintenance,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=size,
        offset=(page - 1) * size
    )
    
    service = EquipmentService(db)
    items, total = service.search_equipment(params)
    
    return EquipmentListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size
    )


@router.get("/{equipment_id}", response_model=EquipmentWithMaintenance)
async def get_equipment(
    equipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get equipment by ID with maintenance history"""
    check_permission(current_user, Permission.EQUIPMENT_VIEW)
    service = EquipmentService(db)
    equipment = service.get_equipment(equipment_id)
    
    # Calculate maintenance statistics
    total_count = len([r for r in equipment.maintenance_records if r.status == "completed"])
    total_cost = sum(r.cost for r in equipment.maintenance_records if r.status == "completed")
    downtime_hours = [r.downtime_hours for r in equipment.maintenance_records if r.status == "completed" and r.downtime_hours > 0]
    avg_downtime = sum(downtime_hours) / len(downtime_hours) if downtime_hours else 0.0
    
    return EquipmentWithMaintenance(
        **equipment.__dict__,
        maintenance_records=equipment.maintenance_records,
        total_maintenance_count=total_count,
        total_maintenance_cost=total_cost,
        average_downtime_hours=round(avg_downtime, 2)
    )


@router.put("/{equipment_id}", response_model=Equipment)
async def update_equipment(
    equipment_id: int,
    update_data: EquipmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update equipment"""
    check_permission(current_user, Permission.EQUIPMENT_UPDATE)
    service = EquipmentService(db)
    return service.update_equipment(equipment_id, update_data, current_user.id)


@router.delete("/{equipment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_equipment(
    equipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete equipment (soft delete)"""
    check_permission(current_user, Permission.EQUIPMENT_DELETE)
    service = EquipmentService(db)
    service.delete_equipment(equipment_id)


# Maintenance record endpoints
@router.post("/maintenance", response_model=MaintenanceRecord, status_code=status.HTTP_201_CREATED)
async def create_maintenance_record(
    record_data: MaintenanceRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create maintenance record"""
    check_permission(current_user, Permission.EQUIPMENT_UPDATE)
    service = EquipmentService(db)
    return service.create_maintenance_record(record_data, current_user.id)


@router.get("/maintenance/search", response_model=MaintenanceListResponse)
async def search_maintenance_records(
    equipment_id: Optional[int] = Query(None, description="Filter by equipment ID"),
    maintenance_type: Optional[str] = Query(None, description="Filter by maintenance type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    date_from: Optional[str] = Query(None, description="Filter by date from (ISO format)"),
    date_to: Optional[str] = Query(None, description="Filter by date to (ISO format)"),
    performed_by: Optional[str] = Query(None, description="Filter by person who performed maintenance"),
    sort_by: str = Query("scheduled_date", pattern="^(scheduled_date|date_performed|status|cost)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Search maintenance records with filters and pagination"""
    check_permission(current_user, Permission.EQUIPMENT_VIEW)
    
    # Parse dates
    from datetime import datetime
    date_from_parsed = datetime.fromisoformat(date_from) if date_from else None
    date_to_parsed = datetime.fromisoformat(date_to) if date_to else None
    
    # Build search params
    params = MaintenanceSearchParams(
        equipment_id=equipment_id,
        maintenance_type=maintenance_type,
        status=status,
        date_from=date_from_parsed,
        date_to=date_to_parsed,
        performed_by=performed_by,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=size,
        offset=(page - 1) * size
    )
    
    service = EquipmentService(db)
    items, total = service.search_maintenance_records(params)
    
    return MaintenanceListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size
    )


@router.get("/maintenance/summary", response_model=MaintenanceSummary)
async def get_maintenance_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get maintenance summary statistics"""
    check_permission(current_user, Permission.EQUIPMENT_VIEW)
    service = EquipmentService(db)
    return service.get_maintenance_summary()


@router.get("/maintenance/{record_id}", response_model=MaintenanceRecord)
async def get_maintenance_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get maintenance record by ID"""
    check_permission(current_user, Permission.EQUIPMENT_VIEW)
    service = EquipmentService(db)
    return service.get_maintenance_record(record_id)


@router.put("/maintenance/{record_id}", response_model=MaintenanceRecord)
async def update_maintenance_record(
    record_id: int,
    update_data: MaintenanceRecordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update maintenance record"""
    check_permission(current_user, Permission.EQUIPMENT_UPDATE)
    service = EquipmentService(db)
    return service.update_maintenance_record(record_id, update_data)


@router.post("/maintenance/{record_id}/complete", response_model=MaintenanceRecord)
async def complete_maintenance(
    record_id: int,
    completion_data: MaintenanceRecordComplete,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Complete a maintenance record"""
    check_permission(current_user, Permission.EQUIPMENT_UPDATE)
    service = EquipmentService(db)
    return service.complete_maintenance(record_id, completion_data, current_user.id)


@router.delete("/maintenance/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_maintenance_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete maintenance record"""
    check_permission(current_user, Permission.EQUIPMENT_DELETE)
    service = EquipmentService(db)
    service.delete_maintenance_record(record_id)


@router.post("/check-overdue", status_code=status.HTTP_204_NO_CONTENT)
async def check_overdue_maintenance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check and update overdue maintenance (typically called by a scheduled job)"""
    check_permission(current_user, Permission.EQUIPMENT_UPDATE)
    service = EquipmentService(db)
    service.check_and_update_overdue_maintenance()