# backend/modules/tables/routers/table_layout_router.py

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from core.database import get_db
from core.auth import get_current_user, require_permission, User
from ..schemas.table_schemas import (
    FloorCreate, FloorUpdate, FloorResponse,
    TableCreate, TableUpdate, TableResponse,
    BulkTableCreate, BulkTableUpdate,
    TableLayoutCreate, TableLayoutUpdate, TableLayoutResponse
)
from ..services.layout_service import layout_service

router = APIRouter(prefix="/table-layout", tags=["Table Layout"])


# Floor Management Endpoints
@router.post("/floors", response_model=FloorResponse)
@require_permission("tables.manage_layout")
async def create_floor(
    floor_data: FloorCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new floor/section
    
    Requires permission: tables.manage_layout
    """
    return await layout_service.create_floor(
        db, current_user.restaurant_id, floor_data
    )


@router.get("/floors", response_model=List[FloorResponse])
async def get_floors(
    include_inactive: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all floors for the restaurant"""
    return await layout_service.get_floors(
        db, current_user.restaurant_id, include_inactive
    )


@router.get("/floors/{floor_id}", response_model=FloorResponse)
async def get_floor(
    floor_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get floor details by ID"""
    return await layout_service.get_floor(
        db, current_user.restaurant_id, floor_id
    )


@router.put("/floors/{floor_id}", response_model=FloorResponse)
@require_permission("tables.manage_layout")
async def update_floor(
    floor_id: int,
    update_data: FloorUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update floor details
    
    Requires permission: tables.manage_layout
    """
    return await layout_service.update_floor(
        db, current_user.restaurant_id, floor_id, update_data
    )


@router.delete("/floors/{floor_id}")
@require_permission("tables.manage_layout")
async def delete_floor(
    floor_id: int,
    force: bool = Query(False, description="Force delete even if tables exist"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a floor
    
    Requires permission: tables.manage_layout
    """
    await layout_service.delete_floor(
        db, current_user.restaurant_id, floor_id, force
    )
    return {"success": True, "message": "Floor deleted successfully"}


# Table Management Endpoints
@router.post("/tables", response_model=TableResponse)
@require_permission("tables.manage_layout")
async def create_table(
    table_data: TableCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new table
    
    Requires permission: tables.manage_layout
    """
    return await layout_service.create_table(
        db, current_user.restaurant_id, table_data
    )


@router.post("/tables/bulk", response_model=List[TableResponse])
@require_permission("tables.manage_layout")
async def bulk_create_tables(
    bulk_data: BulkTableCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create multiple tables at once
    
    Requires permission: tables.manage_layout
    """
    return await layout_service.bulk_create_tables(
        db, current_user.restaurant_id, bulk_data
    )


@router.get("/tables", response_model=List[TableResponse])
async def get_tables(
    floor_id: Optional[int] = Query(None),
    section: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    include_inactive: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all tables with optional filters"""
    return await layout_service.get_tables(
        db, 
        current_user.restaurant_id,
        floor_id=floor_id,
        section=section,
        status=status,
        include_inactive=include_inactive
    )


@router.get("/tables/{table_id}", response_model=TableResponse)
async def get_table(
    table_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get table details by ID"""
    return await layout_service.get_table(
        db, current_user.restaurant_id, table_id
    )


@router.put("/tables/{table_id}", response_model=TableResponse)
@require_permission("tables.manage_layout")
async def update_table(
    table_id: int,
    update_data: TableUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update table details
    
    Requires permission: tables.manage_layout
    """
    return await layout_service.update_table(
        db, current_user.restaurant_id, table_id, update_data
    )


@router.put("/tables/bulk", response_model=List[TableResponse])
@require_permission("tables.manage_layout")
async def bulk_update_tables(
    bulk_data: BulkTableUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update multiple tables at once
    
    Requires permission: tables.manage_layout
    """
    return await layout_service.bulk_update_tables(
        db, current_user.restaurant_id, bulk_data
    )


@router.delete("/tables/{table_id}")
@require_permission("tables.manage_layout")
async def delete_table(
    table_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a table
    
    Requires permission: tables.manage_layout
    """
    await layout_service.delete_table(
        db, current_user.restaurant_id, table_id
    )
    return {"success": True, "message": "Table deleted successfully"}


# Layout Configuration Endpoints
@router.post("/layouts", response_model=TableLayoutResponse)
@require_permission("tables.manage_layout")
async def create_layout(
    layout_data: TableLayoutCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Save a table layout configuration
    
    Requires permission: tables.manage_layout
    """
    return await layout_service.create_layout(
        db, current_user.restaurant_id, layout_data
    )


@router.get("/layouts", response_model=List[TableLayoutResponse])
async def get_layouts(
    include_inactive: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all saved layouts"""
    return await layout_service.get_layouts(
        db, current_user.restaurant_id, include_inactive
    )


@router.get("/layouts/active", response_model=TableLayoutResponse)
async def get_active_layout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get currently active layout"""
    layout = await layout_service.get_active_layout(
        db, current_user.restaurant_id
    )
    if not layout:
        raise HTTPException(status_code=404, detail="No active layout found")
    return layout


@router.get("/layouts/{layout_id}", response_model=TableLayoutResponse)
async def get_layout(
    layout_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get layout details by ID"""
    return await layout_service.get_layout(
        db, current_user.restaurant_id, layout_id
    )


@router.put("/layouts/{layout_id}", response_model=TableLayoutResponse)
@require_permission("tables.manage_layout")
async def update_layout(
    layout_id: int,
    update_data: TableLayoutUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update layout configuration
    
    Requires permission: tables.manage_layout
    """
    return await layout_service.update_layout(
        db, current_user.restaurant_id, layout_id, update_data
    )


@router.post("/layouts/{layout_id}/activate", response_model=TableLayoutResponse)
@require_permission("tables.manage_layout")
async def activate_layout(
    layout_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Activate a saved layout
    
    Requires permission: tables.manage_layout
    """
    return await layout_service.activate_layout(
        db, current_user.restaurant_id, layout_id
    )


@router.post("/layouts/{layout_id}/apply", response_model=Dict[str, Any])
@require_permission("tables.manage_layout")
async def apply_layout(
    layout_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Apply a saved layout (update actual table positions)
    
    Requires permission: tables.manage_layout
    """
    result = await layout_service.apply_layout(
        db, current_user.restaurant_id, layout_id
    )
    return result


@router.delete("/layouts/{layout_id}")
@require_permission("tables.manage_layout")
async def delete_layout(
    layout_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a layout
    
    Requires permission: tables.manage_layout
    """
    await layout_service.delete_layout(
        db, current_user.restaurant_id, layout_id
    )
    return {"success": True, "message": "Layout deleted successfully"}


# Export/Import Endpoints
@router.get("/export")
@require_permission("tables.manage_layout")
async def export_layout(
    format: str = Query("json", regex="^(json|csv)$"),
    floor_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Export current table layout
    
    Requires permission: tables.manage_layout
    """
    export_data = await layout_service.export_layout(
        db, current_user.restaurant_id, format, floor_id
    )
    
    if format == "csv":
        from fastapi.responses import Response
        return Response(
            content=export_data,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=table_layout_{datetime.utcnow().strftime('%Y%m%d')}.csv"
            }
        )
    
    return export_data


@router.post("/import")
@require_permission("tables.manage_layout")
async def import_layout(
    layout_data: Dict[str, Any],
    merge: bool = Query(False, description="Merge with existing tables"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Import table layout configuration
    
    Requires permission: tables.manage_layout
    """
    result = await layout_service.import_layout(
        db, current_user.restaurant_id, layout_data, merge
    )
    return result


# Utility Endpoints
@router.post("/generate-qr-codes")
@require_permission("tables.manage_layout")
async def generate_qr_codes(
    table_ids: Optional[List[int]] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate QR codes for tables
    
    Requires permission: tables.manage_layout
    """
    result = await layout_service.generate_qr_codes(
        db, current_user.restaurant_id, table_ids
    )
    return result


@router.get("/validate-layout")
async def validate_layout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Validate current table layout for issues"""
    issues = await layout_service.validate_layout(
        db, current_user.restaurant_id
    )
    return {
        "valid": len(issues) == 0,
        "issues": issues
    }