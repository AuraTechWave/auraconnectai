# backend/modules/equipment/routes/equipment_routes_improved.py

"""
Improved Equipment routes with comprehensive error handling and validation.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import get_current_user
from core.error_handling import handle_api_errors, NotFoundError, ValidationError as APIValidationError
from modules.auth.models import User
from modules.auth.permissions import Permission, check_permission

from ..services import EquipmentService
from ..schemas import (
    Equipment, EquipmentCreate, EquipmentUpdate, EquipmentWithMaintenance,
    EquipmentSearchParams, EquipmentListResponse,
    MaintenanceRecord, MaintenanceRecordCreate, MaintenanceRecordUpdate,
    MaintenanceRecordComplete, MaintenanceSearchParams, MaintenanceListResponse,
    MaintenanceSummary
)

router = APIRouter(prefix="/equipment", tags=["equipment"])


# Equipment endpoints with improved error handling
@router.post("/", response_model=Equipment, status_code=status.HTTP_201_CREATED)
@handle_api_errors
async def create_equipment(
    equipment_data: EquipmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create new equipment with validation and error handling.
    
    Returns:
        Created equipment object
        
    Raises:
        403: Insufficient permissions
        422: Validation error
        409: Duplicate equipment
    """
    # Permission check
    check_permission(current_user, Permission.EQUIPMENT_CREATE)
    
    # Additional validation
    if equipment_data.purchase_date and equipment_data.warranty_expiry:
        if equipment_data.purchase_date > equipment_data.warranty_expiry:
            raise APIValidationError(
                "Warranty expiry date must be after purchase date",
                {"field": "warranty_expiry"}
            )
    
    service = EquipmentService(db)
    return service.create_equipment(equipment_data, current_user.id)


@router.get("/search", response_model=EquipmentListResponse)
@handle_api_errors
async def search_equipment(
    query: Optional[str] = Query(None, description="Search query for equipment name, type, manufacturer, etc."),
    equipment_type: Optional[str] = Query(None, description="Filter by equipment type"),
    status: Optional[str] = Query(None, description="Filter by status", regex="^(operational|maintenance|out_of_service)$"),
    location: Optional[str] = Query(None, description="Filter by location"),
    is_critical: Optional[bool] = Query(None, description="Filter by critical equipment"),
    needs_maintenance: Optional[bool] = Query(None, description="Filter equipment needing maintenance"),
    sort_by: str = Query("equipment_name", regex="^(equipment_name|next_due_date|status|created_at)$"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=500, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Search equipment with filters, pagination, and proper error handling.
    
    Returns:
        Paginated list of equipment
        
    Raises:
        403: Insufficient permissions
        422: Invalid query parameters
    """
    check_permission(current_user, Permission.EQUIPMENT_VIEW)
    
    # Build search params with validation
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
        pages=(total + size - 1) // size if size > 0 else 0
    )


@router.get("/{equipment_id}", response_model=EquipmentWithMaintenance)
@handle_api_errors
async def get_equipment(
    equipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get equipment by ID with maintenance history.
    
    Returns:
        Equipment with maintenance records
        
    Raises:
        403: Insufficient permissions
        404: Equipment not found
    """
    check_permission(current_user, Permission.EQUIPMENT_VIEW)
    
    service = EquipmentService(db)
    equipment = service.get_equipment(equipment_id)
    
    if not equipment:
        raise NotFoundError("Equipment", equipment_id)
    
    # Calculate maintenance statistics safely
    completed_records = [r for r in equipment.maintenance_records if r.status == "completed"]
    total_count = len(completed_records)
    total_cost = sum(r.cost or 0 for r in completed_records)
    
    downtime_hours = [r.downtime_hours for r in completed_records if r.downtime_hours and r.downtime_hours > 0]
    avg_downtime = sum(downtime_hours) / len(downtime_hours) if downtime_hours else 0.0
    
    return EquipmentWithMaintenance(
        **equipment.__dict__,
        maintenance_records=equipment.maintenance_records,
        total_maintenance_count=total_count,
        total_maintenance_cost=float(total_cost),
        average_downtime_hours=round(avg_downtime, 2)
    )


@router.put("/{equipment_id}", response_model=Equipment)
@handle_api_errors
async def update_equipment(
    equipment_id: int,
    update_data: EquipmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update equipment with validation.
    
    Returns:
        Updated equipment
        
    Raises:
        403: Insufficient permissions
        404: Equipment not found
        409: Concurrent update conflict
        422: Validation error
    """
    check_permission(current_user, Permission.EQUIPMENT_UPDATE)
    
    # Validate status transitions if status is being updated
    if update_data.status:
        service = EquipmentService(db)
        existing = service.get_equipment(equipment_id)
        if not existing:
            raise NotFoundError("Equipment", equipment_id)
            
        # Example: Can't go from out_of_service directly to operational
        if existing.status == "out_of_service" and update_data.status == "operational":
            raise APIValidationError(
                "Equipment must go through maintenance before returning to operational status",
                {"current_status": existing.status, "requested_status": update_data.status}
            )
    
    service = EquipmentService(db)
    return service.update_equipment(equipment_id, update_data, current_user.id)


@router.delete("/{equipment_id}", status_code=status.HTTP_204_NO_CONTENT)
@handle_api_errors
async def delete_equipment(
    equipment_id: int,
    force: bool = Query(False, description="Force delete even with active maintenance"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete equipment (soft delete) with validation.
    
    Returns:
        No content on success
        
    Raises:
        403: Insufficient permissions
        404: Equipment not found
        409: Cannot delete due to active maintenance
    """
    check_permission(current_user, Permission.EQUIPMENT_DELETE)
    
    service = EquipmentService(db)
    
    # Check for active maintenance unless force delete
    if not force:
        equipment = service.get_equipment(equipment_id)
        if not equipment:
            raise NotFoundError("Equipment", equipment_id)
            
        active_maintenance = [
            r for r in equipment.maintenance_records 
            if r.status in ["scheduled", "in_progress"]
        ]
        if active_maintenance:
            raise APIValidationError(
                "Cannot delete equipment with active maintenance records",
                {"active_records": len(active_maintenance)}
            )
    
    service.delete_equipment(equipment_id)


# Maintenance record endpoints
@router.post("/maintenance", response_model=MaintenanceRecord, status_code=status.HTTP_201_CREATED)
@handle_api_errors
async def create_maintenance_record(
    record_data: MaintenanceRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create maintenance record with validation.
    
    Returns:
        Created maintenance record
        
    Raises:
        403: Insufficient permissions
        404: Equipment not found
        422: Validation error
    """
    check_permission(current_user, Permission.EQUIPMENT_UPDATE)
    
    # Validate equipment exists
    service = EquipmentService(db)
    equipment = service.get_equipment(record_data.equipment_id)
    if not equipment:
        raise NotFoundError("Equipment", record_data.equipment_id)
    
    # Validate scheduled date is in the future
    from datetime import datetime
    if record_data.scheduled_date and record_data.scheduled_date < datetime.now().date():
        raise APIValidationError(
            "Scheduled date must be in the future",
            {"scheduled_date": str(record_data.scheduled_date)}
        )
    
    return service.create_maintenance_record(record_data, current_user.id)


@router.get("/maintenance/search", response_model=MaintenanceListResponse)
@handle_api_errors
async def search_maintenance_records(
    equipment_id: Optional[int] = Query(None, description="Filter by equipment ID"),
    maintenance_type: Optional[str] = Query(None, regex="^(preventive|repair|inspection|calibration)$"),
    status: Optional[str] = Query(None, regex="^(scheduled|in_progress|completed|cancelled)$"),
    date_from: Optional[str] = Query(None, description="Filter by date from (ISO format)"),
    date_to: Optional[str] = Query(None, description="Filter by date to (ISO format)"),
    performed_by: Optional[str] = Query(None, description="Filter by person who performed maintenance"),
    sort_by: str = Query("scheduled_date", regex="^(scheduled_date|date_performed|status|cost)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Search maintenance records with comprehensive filters.
    
    Returns:
        Paginated maintenance records
        
    Raises:
        403: Insufficient permissions
        422: Invalid date format or parameters
    """
    check_permission(current_user, Permission.EQUIPMENT_VIEW)
    
    # Parse and validate dates
    from datetime import datetime
    try:
        date_from_parsed = datetime.fromisoformat(date_from) if date_from else None
        date_to_parsed = datetime.fromisoformat(date_to) if date_to else None
        
        # Validate date range
        if date_from_parsed and date_to_parsed and date_from_parsed > date_to_parsed:
            raise APIValidationError(
                "date_from must be before date_to",
                {"date_from": date_from, "date_to": date_to}
            )
    except ValueError as e:
        raise APIValidationError(
            "Invalid date format. Use ISO format (YYYY-MM-DD)",
            {"error": str(e)}
        )
    
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
        pages=(total + size - 1) // size if size > 0 else 0
    )


@router.put("/maintenance/{record_id}", response_model=MaintenanceRecord)
@handle_api_errors
async def update_maintenance_record(
    record_id: int,
    update_data: MaintenanceRecordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update maintenance record with validation.
    
    Returns:
        Updated maintenance record
        
    Raises:
        403: Insufficient permissions
        404: Record not found
        422: Invalid status transition
    """
    check_permission(current_user, Permission.EQUIPMENT_UPDATE)
    
    service = EquipmentService(db)
    
    # Validate status transitions
    if update_data.status:
        existing = service.get_maintenance_record(record_id)
        if not existing:
            raise NotFoundError("Maintenance record", record_id)
            
        # Define valid transitions
        valid_transitions = {
            "scheduled": ["in_progress", "cancelled"],
            "in_progress": ["completed", "cancelled"],
            "completed": [],  # Cannot change from completed
            "cancelled": []   # Cannot change from cancelled
        }
        
        if update_data.status not in valid_transitions.get(existing.status, []):
            raise APIValidationError(
                f"Invalid status transition from {existing.status} to {update_data.status}",
                {"current_status": existing.status, "requested_status": update_data.status}
            )
    
    return service.update_maintenance_record(record_id, update_data, current_user.id)


@router.post("/maintenance/{record_id}/complete", response_model=MaintenanceRecord)
@handle_api_errors
async def complete_maintenance_record(
    record_id: int,
    completion_data: MaintenanceRecordComplete,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Complete a maintenance record with validation.
    
    Returns:
        Completed maintenance record
        
    Raises:
        403: Insufficient permissions
        404: Record not found
        409: Record not in correct status
        422: Validation error
    """
    check_permission(current_user, Permission.EQUIPMENT_UPDATE)
    
    service = EquipmentService(db)
    existing = service.get_maintenance_record(record_id)
    
    if not existing:
        raise NotFoundError("Maintenance record", record_id)
        
    if existing.status != "in_progress":
        raise APIValidationError(
            "Can only complete records that are in progress",
            {"current_status": existing.status}
        )
    
    # Validate completion data
    if completion_data.date_performed > datetime.now():
        raise APIValidationError(
            "Completion date cannot be in the future",
            {"date_performed": str(completion_data.date_performed)}
        )
    
    return service.complete_maintenance_record(record_id, completion_data, current_user.id)


@router.get("/maintenance/summary", response_model=MaintenanceSummary)
@handle_api_errors
async def get_maintenance_summary(
    location: Optional[str] = Query(None, description="Filter by location"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get maintenance summary statistics with proper error handling.
    
    Returns:
        Maintenance summary statistics
        
    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.EQUIPMENT_VIEW)
    
    service = EquipmentService(db)
    return service.get_maintenance_summary(location)


# Bulk operations
@router.post("/bulk/schedule-maintenance")
@handle_api_errors
async def bulk_schedule_maintenance(
    equipment_ids: List[int],
    maintenance_data: MaintenanceRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Schedule maintenance for multiple equipment items.
    
    Returns:
        List of created maintenance records
        
    Raises:
        403: Insufficient permissions
        404: One or more equipment not found
        422: Validation error
    """
    check_permission(current_user, Permission.EQUIPMENT_UPDATE)
    
    if not equipment_ids:
        raise APIValidationError("At least one equipment ID must be provided")
    
    if len(equipment_ids) > 100:
        raise APIValidationError("Cannot schedule maintenance for more than 100 items at once")
    
    service = EquipmentService(db)
    
    # Validate all equipment exists
    missing_ids = []
    for eq_id in equipment_ids:
        if not service.get_equipment(eq_id):
            missing_ids.append(eq_id)
    
    if missing_ids:
        raise NotFoundError("Equipment", missing_ids)
    
    # Create maintenance records
    created_records = []
    for eq_id in equipment_ids:
        record_data = maintenance_data.copy()
        record_data.equipment_id = eq_id
        record = service.create_maintenance_record(record_data, current_user.id)
        created_records.append(record)
    
    return {
        "message": f"Successfully scheduled maintenance for {len(created_records)} equipment items",
        "records": created_records
    }


from datetime import datetime