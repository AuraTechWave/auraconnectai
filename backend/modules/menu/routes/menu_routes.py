# backend/modules/menu/routes/menu_routes.py

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from math import ceil

from backend.core.database import get_db
from backend.core.menu_service import MenuService
from backend.core.menu_schemas import (
    MenuCategory, MenuCategoryCreate, MenuCategoryUpdate, MenuCategoryWithItems,
    MenuItem, MenuItemCreate, MenuItemUpdate, MenuItemWithDetails,
    ModifierGroup, ModifierGroupCreate, ModifierGroupUpdate, ModifierGroupWithModifiers,
    Modifier, ModifierCreate, ModifierUpdate,
    MenuItemModifier, MenuItemModifierCreate, MenuItemModifierUpdate,
    MenuItemInventory, MenuItemInventoryCreate, MenuItemInventoryUpdate,
    MenuSearchParams, BulkMenuItemUpdate, BulkCategoryUpdate,
    MenuItemResponse, MenuCategoryResponse, PaginatedResponse
)
from backend.core.rbac_auth import require_permission
from backend.core.rbac_models import RBACUser


router = APIRouter(prefix="/menu", tags=["Menu Management"])


def get_menu_service(db: Session = Depends(get_db)) -> MenuService:
    """Dependency to get menu service instance"""
    return MenuService(db)


# Menu Categories
@router.post("/categories", response_model=MenuCategory, status_code=status.HTTP_201_CREATED)
async def create_category(
    category_data: MenuCategoryCreate,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:create"))
):
    """Create a new menu category"""
    return menu_service.create_category(category_data, current_user.id)


@router.get("/categories", response_model=List[MenuCategory])
async def get_categories(
    active_only: bool = Query(True, description="Filter by active categories only"),
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:read"))
):
    """Get all menu categories"""
    return menu_service.get_categories(active_only)


@router.get("/categories/{category_id}", response_model=MenuCategoryWithItems)
async def get_category_by_id(
    category_id: int,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:read"))
):
    """Get a category by ID with its items"""
    category = menu_service.get_category_by_id(category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    return category


@router.put("/categories/{category_id}", response_model=MenuCategory)
async def update_category(
    category_id: int,
    category_data: MenuCategoryUpdate,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:update"))
):
    """Update a menu category"""
    return menu_service.update_category(category_id, category_data, current_user.id)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:delete"))
):
    """Delete a menu category"""
    menu_service.delete_category(category_id, current_user.id)


@router.put("/categories/bulk", response_model=List[MenuCategory])
async def bulk_update_categories(
    bulk_data: BulkCategoryUpdate,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:update"))
):
    """Bulk update menu categories"""
    updated_categories = []
    for category_id in bulk_data.category_ids:
        try:
            category = menu_service.update_category(category_id, bulk_data.updates, current_user.id)
            updated_categories.append(category)
        except HTTPException:
            continue  # Skip non-existent categories
    return updated_categories


# Menu Items
@router.post("/items", response_model=MenuItem, status_code=status.HTTP_201_CREATED)
async def create_menu_item(
    item_data: MenuItemCreate,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:create"))
):
    """Create a new menu item"""
    return menu_service.create_menu_item(item_data, current_user.id)


@router.get("/items", response_model=MenuItemResponse)
async def get_menu_items(
    query: Optional[str] = Query(None, description="Search query"),
    category_id: Optional[int] = Query(None, description="Filter by category"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_available: Optional[bool] = Query(None, description="Filter by availability"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price"),
    dietary_tags: Optional[List[str]] = Query(None, description="Filter by dietary tags"),
    allergens: Optional[List[str]] = Query(None, description="Exclude allergens"),
    limit: int = Query(50, ge=1, le=500, description="Items per page"),
    offset: int = Query(0, ge=0, description="Items to skip"),
    sort_by: str = Query("display_order", regex=r'^(name|price|created_at|display_order)$'),
    sort_order: str = Query("asc", regex=r'^(asc|desc)$'),
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:read"))
):
    """Get menu items with search and pagination"""
    params = MenuSearchParams(
        query=query,
        category_id=category_id,
        is_active=is_active,
        is_available=is_available,
        min_price=min_price,
        max_price=max_price,
        dietary_tags=dietary_tags,
        allergens=allergens,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    items, total = menu_service.get_menu_items(params)
    pages = ceil(total / limit) if total > 0 else 0
    page = (offset // limit) + 1 if limit > 0 else 1
    
    return MenuItemResponse(
        items=items,
        total=total,
        page=page,
        size=limit,
        pages=pages
    )


@router.get("/items/{item_id}", response_model=MenuItemWithDetails)
async def get_menu_item_by_id(
    item_id: int,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:read"))
):
    """Get a menu item by ID with details"""
    item = menu_service.get_menu_item_by_id(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )
    return item


@router.put("/items/{item_id}", response_model=MenuItem)
async def update_menu_item(
    item_id: int,
    item_data: MenuItemUpdate,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:update"))
):
    """Update a menu item"""
    return menu_service.update_menu_item(item_id, item_data, current_user.id)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_menu_item(
    item_id: int,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:delete"))
):
    """Delete a menu item"""
    menu_service.delete_menu_item(item_id, current_user.id)


@router.put("/items/bulk", response_model=List[MenuItem])
async def bulk_update_menu_items(
    bulk_data: BulkMenuItemUpdate,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:update"))
):
    """Bulk update menu items"""
    return menu_service.bulk_update_items(bulk_data.item_ids, bulk_data.updates, current_user.id)


# Modifier Groups
@router.post("/modifier-groups", response_model=ModifierGroup, status_code=status.HTTP_201_CREATED)
async def create_modifier_group(
    group_data: ModifierGroupCreate,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:create"))
):
    """Create a new modifier group"""
    return menu_service.create_modifier_group(group_data, current_user.id)


@router.get("/modifier-groups", response_model=List[ModifierGroup])
async def get_modifier_groups(
    active_only: bool = Query(True, description="Filter by active groups only"),
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:read"))
):
    """Get all modifier groups"""
    return menu_service.get_modifier_groups(active_only)


@router.get("/modifier-groups/{group_id}", response_model=ModifierGroupWithModifiers)
async def get_modifier_group_by_id(
    group_id: int,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:read"))
):
    """Get a modifier group by ID with its modifiers"""
    group = menu_service.get_modifier_group_by_id(group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Modifier group not found"
        )
    return group


@router.put("/modifier-groups/{group_id}", response_model=ModifierGroup)
async def update_modifier_group(
    group_id: int,
    group_data: ModifierGroupUpdate,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:update"))
):
    """Update a modifier group"""
    return menu_service.update_modifier_group(group_id, group_data, current_user.id)


@router.delete("/modifier-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_modifier_group(
    group_id: int,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:delete"))
):
    """Delete a modifier group"""
    menu_service.delete_modifier_group(group_id, current_user.id)


# Modifiers
@router.post("/modifiers", response_model=Modifier, status_code=status.HTTP_201_CREATED)
async def create_modifier(
    modifier_data: ModifierCreate,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:create"))
):
    """Create a new modifier"""
    return menu_service.create_modifier(modifier_data, current_user.id)


@router.get("/modifier-groups/{group_id}/modifiers", response_model=List[Modifier])
async def get_modifiers_by_group(
    group_id: int,
    active_only: bool = Query(True, description="Filter by active modifiers only"),
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:read"))
):
    """Get modifiers by group ID"""
    return menu_service.get_modifiers_by_group(group_id, active_only)


@router.get("/modifiers/{modifier_id}", response_model=Modifier)
async def get_modifier_by_id(
    modifier_id: int,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:read"))
):
    """Get a modifier by ID"""
    modifier = menu_service.get_modifier_by_id(modifier_id)
    if not modifier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Modifier not found"
        )
    return modifier


@router.put("/modifiers/{modifier_id}", response_model=Modifier)
async def update_modifier(
    modifier_id: int,
    modifier_data: ModifierUpdate,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:update"))
):
    """Update a modifier"""
    return menu_service.update_modifier(modifier_id, modifier_data, current_user.id)


@router.delete("/modifiers/{modifier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_modifier(
    modifier_id: int,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:delete"))
):
    """Delete a modifier"""
    menu_service.delete_modifier(modifier_id, current_user.id)


# Menu Item Modifiers
@router.post("/items/{item_id}/modifiers", response_model=MenuItemModifier, status_code=status.HTTP_201_CREATED)
async def add_modifier_to_item(
    item_id: int,
    link_data: MenuItemModifierCreate,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:update"))
):
    """Add a modifier group to a menu item"""
    # Ensure the item_id matches
    link_data.menu_item_id = item_id
    return menu_service.add_modifier_to_item(link_data, current_user.id)


@router.get("/items/{item_id}/modifiers", response_model=List[MenuItemModifier])
async def get_item_modifiers(
    item_id: int,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:read"))
):
    """Get all modifier groups for a menu item"""
    return menu_service.get_item_modifiers(item_id)


@router.delete("/items/{item_id}/modifiers/{modifier_group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_modifier_from_item(
    item_id: int,
    modifier_group_id: int,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:update"))
):
    """Remove a modifier group from a menu item"""
    menu_service.remove_modifier_from_item(item_id, modifier_group_id, current_user.id)


# Menu Item Inventory
@router.post("/items/{item_id}/inventory", response_model=MenuItemInventory, status_code=status.HTTP_201_CREATED)
async def add_inventory_to_item(
    item_id: int,
    link_data: MenuItemInventoryCreate,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:update"))
):
    """Link an inventory item to a menu item"""
    # Ensure the item_id matches
    link_data.menu_item_id = item_id
    return menu_service.add_inventory_to_item(link_data, current_user.id)


# Analytics and Stats
@router.get("/stats")
async def get_menu_stats(
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:read"))
):
    """Get menu statistics"""
    return menu_service.get_menu_stats()


# Public endpoints (no authentication required)
@router.get("/public/categories", response_model=List[MenuCategory])
async def get_public_categories(
    menu_service: MenuService = Depends(get_menu_service)
):
    """Get active menu categories for public use"""
    return menu_service.get_categories(active_only=True)


@router.get("/public/items", response_model=MenuItemResponse)
async def get_public_menu_items(
    category_id: Optional[int] = Query(None, description="Filter by category"),
    dietary_tags: Optional[List[str]] = Query(None, description="Filter by dietary tags"),
    allergens: Optional[List[str]] = Query(None, description="Exclude allergens"),
    limit: int = Query(50, ge=1, le=500, description="Items per page"),
    offset: int = Query(0, ge=0, description="Items to skip"),
    menu_service: MenuService = Depends(get_menu_service)
):
    """Get available menu items for public use"""
    params = MenuSearchParams(
        category_id=category_id,
        is_active=True,
        is_available=True,
        dietary_tags=dietary_tags,
        allergens=allergens,
        limit=limit,
        offset=offset,
        sort_by="display_order",
        sort_order="asc"
    )
    
    items, total = menu_service.get_menu_items(params)
    pages = ceil(total / limit) if total > 0 else 0
    page = (offset // limit) + 1 if limit > 0 else 1
    
    return MenuItemResponse(
        items=items,
        total=total,
        page=page,
        size=limit,
        pages=pages
    )


@router.get("/public/items/{item_id}", response_model=MenuItemWithDetails)
async def get_public_menu_item(
    item_id: int,
    menu_service: MenuService = Depends(get_menu_service)
):
    """Get a menu item for public use"""
    item = menu_service.get_menu_item_by_id(item_id)
    if not item or not item.is_active or not item.is_available:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found or not available"
        )
    return item


# Bulk operations with versioning integration
@router.post("/items/bulk-update")
async def bulk_update_menu_items(
    item_ids: List[int],
    updates: dict,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:update"))
):
    """Bulk update multiple menu items and create version if significant changes"""
    
    result = menu_service.bulk_update_items(item_ids, updates, current_user.id)
    
    return {
        "message": f"Updated {result['updated']} items",
        "details": result,
        "version_info": {
            "version_created": result.get("version_created", False),
            "version_id": result.get("version_id")
        } if result.get("version_created") else None
    }


@router.post("/items/bulk-activate")
async def bulk_activate_menu_items(
    item_ids: List[int],
    active: bool = True,
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:update"))
):
    """Bulk activate or deactivate multiple menu items"""
    
    result = menu_service.bulk_activate_items(item_ids, active, current_user.id)
    
    action = "activated" if active else "deactivated"
    return {
        "message": f"{action.capitalize()} {result['updated']} items",
        "details": result,
        "version_info": {
            "version_created": result.get("version_created", False),
            "version_id": result.get("version_id")
        } if result.get("version_created") else None
    }


@router.post("/items/bulk-price-update")
async def bulk_update_prices(
    price_updates: List[dict],  # [{"item_id": 1, "price": 10.99}, ...]
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:update"))
):
    """Bulk update item prices - always creates a version due to criticality"""
    
    result = menu_service.bulk_update_prices(price_updates, current_user.id)
    
    return {
        "message": f"Updated prices for {result['updated']} items",
        "details": result,
        "version_info": {
            "version_created": True,  # Always true for price changes
            "version_id": result.get("version_id"),
            "note": "Price changes always trigger version creation for audit purposes"
        }
    }


@router.delete("/items/bulk-delete")
async def bulk_delete_menu_items(
    item_ids: List[int],
    menu_service: MenuService = Depends(get_menu_service),
    current_user: RBACUser = Depends(require_permission("menu:delete"))
):
    """Bulk soft-delete multiple menu items"""
    
    result = menu_service.bulk_delete_items(item_ids, current_user.id)
    
    return {
        "message": f"Deleted {result['deleted']} items",
        "details": result,
        "version_info": {
            "version_created": result.get("version_created", False),
            "version_id": result.get("version_id")
        } if result.get("version_created") else None
    }