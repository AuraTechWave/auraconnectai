from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List
from core.database import get_db
from ..controllers.inventory_controller import (
    get_inventory_by_id,
    check_low_stock,
    list_inventory,
    update_inventory,
)
from ..schemas.inventory_schemas import InventoryOut, InventoryUpdate

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("/", response_model=List[InventoryOut])
async def get_inventory(
    limit: int = Query(100, ge=1, le=1000, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    db: Session = Depends(get_db),
):
    """
    Retrieve a list of inventory items with pagination.
    """
    return await list_inventory(db, limit, offset)


@router.get("/{id}", response_model=InventoryOut)
async def get_inventory_item(id: int, db: Session = Depends(get_db)):
    return await get_inventory_by_id(db, id)


@router.put("/{inventory_id}", response_model=dict)
async def update_existing_inventory(
    inventory_id: int, inventory_data: InventoryUpdate, db: Session = Depends(get_db)
):
    return await update_inventory(inventory_id, inventory_data, db)


@router.get("/alerts/low-stock", response_model=List[dict])
async def get_low_stock_alerts(db: Session = Depends(get_db)):
    """
    Get inventory items that are below their threshold levels.
    """
    return await check_low_stock(db)
