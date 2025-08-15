# backend/modules/menu/routes/inventory_routes.py

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from math import ceil

from core.database import get_db
from core.menu_service import MenuService
from core.menu_schemas import (
    Inventory,
    InventoryCreate,
    InventoryUpdate,
    InventorySearchParams,
    InventoryResponse,
)
from core.auth import require_permission, User


router = APIRouter(prefix="/inventory", tags=["Inventory Management"])


def get_menu_service(db: Session = Depends(get_db)) -> MenuService:
    """Dependency to get menu service instance"""
    return MenuService(db)


@router.post("/", response_model=Inventory, status_code=status.HTTP_201_CREATED)
async def create_inventory_item(
    inventory_data: InventoryCreate,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: User = Depends(require_permission("inventory:create")),
):
    """Create a new inventory item"""
    from core.inventory_models import Inventory as InventoryModel
    from core.database import get_db

    # Use the existing inventory service or create directly
    db = next(get_db())
    try:
        # Check SKU uniqueness if provided
        if inventory_data.sku:
            existing_item = (
                db.query(InventoryModel)
                .filter(
                    InventoryModel.sku == inventory_data.sku,
                    InventoryModel.deleted_at.is_(None),
                )
                .first()
            )
            if existing_item:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="SKU already exists"
                )

        inventory_item = InventoryModel(**inventory_data.dict())
        db.add(inventory_item)
        db.commit()
        db.refresh(inventory_item)
        return inventory_item
    finally:
        db.close()


@router.get("/", response_model=InventoryResponse)
async def get_inventory_items(
    query: Optional[str] = Query(None, description="Search query"),
    low_stock: Optional[bool] = Query(None, description="Show only low stock items"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    vendor_id: Optional[int] = Query(None, description="Filter by vendor"),
    limit: int = Query(50, ge=1, le=500, description="Items per page"),
    offset: int = Query(0, ge=0, description="Items to skip"),
    sort_by: str = Query(
        "item_name", pattern=r"^(item_name|quantity|threshold|created_at)$"
    ),
    sort_order: str = Query("asc", pattern=r"^(asc|desc)$"),
    menu_service: MenuService = Depends(get_menu_service),
    current_user: User = Depends(require_permission("inventory:read")),
):
    """Get inventory items with search and pagination"""
    params = InventorySearchParams(
        query=query,
        low_stock=low_stock,
        is_active=is_active,
        vendor_id=vendor_id,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    items, total = menu_service.get_inventory(params)
    pages = ceil(total / limit) if total > 0 else 0
    page = (offset // limit) + 1 if limit > 0 else 1

    return InventoryResponse(
        items=items, total=total, page=page, size=limit, pages=pages
    )


@router.get("/low-stock", response_model=List[Inventory])
async def get_low_stock_items(
    menu_service: MenuService = Depends(get_menu_service),
    current_user: User = Depends(require_permission("inventory:read")),
):
    """Get items that are below their reorder threshold"""
    return menu_service.get_low_stock_items()


@router.get("/{inventory_id}", response_model=Inventory)
async def get_inventory_item_by_id(
    inventory_id: int,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: User = Depends(require_permission("inventory:read")),
):
    """Get an inventory item by ID"""
    item = menu_service.get_inventory_by_id(inventory_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found"
        )
    return item


@router.put("/{inventory_id}", response_model=Inventory)
async def update_inventory_item(
    inventory_id: int,
    inventory_data: InventoryUpdate,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: User = Depends(require_permission("inventory:update")),
):
    """Update an inventory item"""
    from core.inventory_models import Inventory as InventoryModel
    from core.database import get_db

    db = next(get_db())
    try:
        item = (
            db.query(InventoryModel)
            .filter(
                InventoryModel.id == inventory_id, InventoryModel.deleted_at.is_(None)
            )
            .first()
        )

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found"
            )

        # Check SKU uniqueness if being updated
        if inventory_data.sku and inventory_data.sku != item.sku:
            existing_item = (
                db.query(InventoryModel)
                .filter(
                    InventoryModel.sku == inventory_data.sku,
                    InventoryModel.id != inventory_id,
                    InventoryModel.deleted_at.is_(None),
                )
                .first()
            )
            if existing_item:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="SKU already exists"
                )

        update_data = inventory_data.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(item, key, value)

        db.commit()
        db.refresh(item)
        return item
    finally:
        db.close()


@router.delete("/{inventory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_inventory_item(
    inventory_id: int,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: User = Depends(require_permission("inventory:delete")),
):
    """Soft delete an inventory item"""
    from core.inventory_models import Inventory as InventoryModel
    from core.database import get_db
    from datetime import datetime

    db = next(get_db())
    try:
        item = (
            db.query(InventoryModel)
            .filter(
                InventoryModel.id == inventory_id, InventoryModel.deleted_at.is_(None)
            )
            .first()
        )

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found"
            )

        item.deleted_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()


@router.post("/{inventory_id}/adjust-quantity")
async def adjust_inventory_quantity(
    inventory_id: int,
    adjustment: float,
    reason: str = Query(..., description="Reason for adjustment"),
    menu_service: MenuService = Depends(get_menu_service),
    current_user: User = Depends(require_permission("inventory:update")),
):
    """Adjust inventory quantity (positive for increase, negative for decrease)"""
    from core.inventory_models import Inventory as InventoryModel
    from core.database import get_db

    db = next(get_db())
    try:
        item = (
            db.query(InventoryModel)
            .filter(
                InventoryModel.id == inventory_id, InventoryModel.deleted_at.is_(None)
            )
            .first()
        )

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found"
            )

        new_quantity = item.quantity + adjustment
        if new_quantity < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Adjustment would result in negative quantity",
            )

        item.quantity = new_quantity
        db.commit()
        db.refresh(item)

        # TODO: Log this adjustment in an audit table

        return {
            "message": "Quantity adjusted successfully",
            "old_quantity": item.quantity - adjustment,
            "new_quantity": item.quantity,
            "adjustment": adjustment,
            "reason": reason,
        }
    finally:
        db.close()


@router.get("/alerts/low-stock-count")
async def get_low_stock_count(
    menu_service: MenuService = Depends(get_menu_service),
    current_user: User = Depends(require_permission("inventory:read")),
):
    """Get count of items below reorder threshold"""
    low_stock_items = menu_service.get_low_stock_items()
    return {"count": len(low_stock_items)}


@router.get("/reports/usage")
async def get_inventory_usage_report(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    menu_service: MenuService = Depends(get_menu_service),
    current_user: User = Depends(require_permission("inventory:read")),
):
    """Get inventory usage report (placeholder for future implementation)"""
    # TODO: Implement inventory usage tracking and reporting
    return {
        "message": "Inventory usage reporting will be implemented in future version",
        "start_date": start_date,
        "end_date": end_date,
    }
