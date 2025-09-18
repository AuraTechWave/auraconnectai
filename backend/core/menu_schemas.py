# backend/core/menu_schemas.py

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class SelectionType(str, Enum):
    single = "single"
    multiple = "multiple"


class PriceType(str, Enum):
    fixed = "fixed"
    percentage = "percentage"


# Base schemas
class MenuCategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    display_order: int = Field(default=0, ge=0)
    is_active: bool = True
    parent_category_id: Optional[int] = None
    image_url: Optional[str] = Field(None, max_length=500)


class MenuCategoryCreate(MenuCategoryBase):
    pass


class MenuCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    display_order: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None
    parent_category_id: Optional[int] = None
    image_url: Optional[str] = Field(None, max_length=500)


class MenuCategory(MenuCategoryBase):
    id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MenuCategoryWithItems(MenuCategory):
    subcategories: List[MenuCategory] = []
    menu_items: List["MenuItem"] = []


# Menu Item schemas
class MenuItemBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    category_id: int
    sku: Optional[str] = Field(None, max_length=50)
    is_active: bool = True
    is_available: bool = True
    availability_start_time: Optional[str] = Field(
        None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$"
    )
    availability_end_time: Optional[str] = Field(
        None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$"
    )
    calories: Optional[int] = Field(None, ge=0)
    allergens: Optional[List[str]] = []
    dietary_tags: Optional[List[str]] = []
    prep_time_minutes: Optional[int] = Field(None, ge=0)
    serving_size: Optional[str] = Field(None, max_length=50)
    image_url: Optional[str] = Field(None, max_length=500)
    images: Optional[List[str]] = []
    display_order: int = Field(default=0, ge=0)


class MenuItemCreate(MenuItemBase):
    pass


class MenuItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    category_id: Optional[int] = None
    sku: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None
    is_available: Optional[bool] = None
    availability_start_time: Optional[str] = Field(
        None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$"
    )
    availability_end_time: Optional[str] = Field(
        None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$"
    )
    calories: Optional[int] = Field(None, ge=0)
    allergens: Optional[List[str]] = None
    dietary_tags: Optional[List[str]] = None
    prep_time_minutes: Optional[int] = Field(None, ge=0)
    serving_size: Optional[str] = Field(None, max_length=50)
    image_url: Optional[str] = Field(None, max_length=500)
    images: Optional[List[str]] = None
    display_order: Optional[int] = Field(None, ge=0)


class MenuItem(MenuItemBase):
    id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MenuItemWithDetails(MenuItem):
    category: MenuCategory
    modifiers: List["MenuItemModifier"] = []


# Modifier Group schemas
class ModifierGroupBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    selection_type: SelectionType = SelectionType.single
    min_selections: int = Field(default=0, ge=0)
    max_selections: Optional[int] = Field(None, ge=0)
    is_required: bool = False
    display_order: int = Field(default=0, ge=0)
    is_active: bool = True

    @field_validator("max_selections", mode="after")
    def validate_max_selections(cls, v, values):
        if v is not None and "min_selections" in values:
            if v < values["min_selections"]:
                raise ValueError("max_selections must be >= min_selections")
        return v


class ModifierGroupCreate(ModifierGroupBase):
    pass


class ModifierGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    selection_type: Optional[SelectionType] = None
    min_selections: Optional[int] = Field(None, ge=0)
    max_selections: Optional[int] = Field(None, ge=0)
    is_required: Optional[bool] = None
    display_order: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class ModifierGroup(ModifierGroupBase):
    id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ModifierGroupWithModifiers(ModifierGroup):
    modifiers: List["Modifier"] = []


# Modifier schemas
class ModifierBase(BaseModel):
    modifier_group_id: int
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    price_adjustment: float = 0.0
    price_type: PriceType = PriceType.fixed
    is_active: bool = True
    is_available: bool = True
    display_order: int = Field(default=0, ge=0)


class ModifierCreate(ModifierBase):
    pass


class ModifierUpdate(BaseModel):
    modifier_group_id: Optional[int] = None
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    price_adjustment: Optional[float] = None
    price_type: Optional[PriceType] = None
    is_active: Optional[bool] = None
    is_available: Optional[bool] = None
    display_order: Optional[int] = Field(None, ge=0)


class Modifier(ModifierBase):
    id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ModifierWithGroup(Modifier):
    modifier_group: ModifierGroup


# Menu Item Modifier schemas
class MenuItemModifierBase(BaseModel):
    menu_item_id: int
    modifier_group_id: int
    is_required: Optional[bool] = None
    min_selections: Optional[int] = Field(None, ge=0)
    max_selections: Optional[int] = Field(None, ge=0)
    display_order: int = Field(default=0, ge=0)


class MenuItemModifierCreate(MenuItemModifierBase):
    pass


class MenuItemModifierUpdate(BaseModel):
    is_required: Optional[bool] = None
    min_selections: Optional[int] = Field(None, ge=0)
    max_selections: Optional[int] = Field(None, ge=0)
    display_order: Optional[int] = Field(None, ge=0)


class MenuItemModifier(MenuItemModifierBase):
    id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MenuItemModifierWithDetails(MenuItemModifier):
    modifier_group: ModifierGroupWithModifiers


# Inventory schemas (enhanced)
class InventoryBase(BaseModel):
    item_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    sku: Optional[str] = Field(None, max_length=50)
    quantity: float = Field(..., ge=0)
    unit: str = Field(..., min_length=1, max_length=20)
    threshold: float = Field(..., ge=0)
    reorder_quantity: Optional[float] = Field(None, ge=0)
    cost_per_unit: Optional[float] = Field(None, ge=0)
    last_purchase_price: Optional[float] = Field(None, ge=0)
    vendor_id: Optional[int] = None
    vendor_item_code: Optional[str] = Field(None, max_length=100)
    storage_location: Optional[str] = Field(None, max_length=100)
    expiration_days: Optional[int] = Field(None, ge=0)
    is_active: bool = True


class InventoryCreate(InventoryBase):
    pass


class InventoryUpdate(BaseModel):
    item_name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    sku: Optional[str] = Field(None, max_length=50)
    quantity: Optional[float] = Field(None, ge=0)
    unit: Optional[str] = Field(None, min_length=1, max_length=20)
    threshold: Optional[float] = Field(None, ge=0)
    reorder_quantity: Optional[float] = Field(None, ge=0)
    cost_per_unit: Optional[float] = Field(None, ge=0)
    last_purchase_price: Optional[float] = Field(None, ge=0)
    vendor_id: Optional[int] = None
    vendor_item_code: Optional[str] = Field(None, max_length=100)
    storage_location: Optional[str] = Field(None, max_length=100)
    expiration_days: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class Inventory(InventoryBase):
    id: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Menu Item Inventory schemas
class MenuItemInventoryBase(BaseModel):
    menu_item_id: int
    inventory_id: int
    quantity_needed: float = Field(..., gt=0)
    unit: Optional[str] = Field(None, max_length=20)


class MenuItemInventoryCreate(MenuItemInventoryBase):
    pass


class MenuItemInventoryUpdate(BaseModel):
    quantity_needed: Optional[float] = Field(None, gt=0)
    unit: Optional[str] = Field(None, max_length=20)


class MenuItemInventory(MenuItemInventoryBase):
    id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MenuItemInventoryWithDetails(MenuItemInventory):
    inventory_item: Inventory


# Bulk operation schemas
class BulkMenuItemUpdate(BaseModel):
    item_ids: List[int]
    updates: MenuItemUpdate


class BulkCategoryUpdate(BaseModel):
    category_ids: List[int]
    updates: MenuCategoryUpdate


# Search and filter schemas
class MenuSearchParams(BaseModel):
    query: Optional[str] = None
    category_id: Optional[int] = None
    is_active: Optional[bool] = None
    is_available: Optional[bool] = None
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    dietary_tags: Optional[List[str]] = None
    allergens: Optional[List[str]] = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
    sort_by: Optional[str] = Field(
        default="display_order", pattern=r"^(name|price|created_at|display_order)$"
    )
    sort_order: Optional[str] = Field(default="asc", pattern=r"^(asc|desc)$")


class InventorySearchParams(BaseModel):
    query: Optional[str] = None
    low_stock: Optional[bool] = None  # Items below threshold
    is_active: Optional[bool] = None
    vendor_id: Optional[int] = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
    sort_by: Optional[str] = Field(
        default="item_name", pattern=r"^(item_name|quantity|threshold|created_at)$"
    )
    sort_order: Optional[str] = Field(default="asc", pattern=r"^(asc|desc)$")


# Response schemas
class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    size: int
    pages: int


class MenuItemResponse(PaginatedResponse):
    items: List[MenuItem]


class MenuCategoryResponse(PaginatedResponse):
    items: List[MenuCategory]


class InventoryResponse(PaginatedResponse):
    items: List[Inventory]


# Update forward references
MenuCategoryWithItems.model_rebuild()
MenuItemWithDetails.model_rebuild()
ModifierGroupWithModifiers.model_rebuild()
MenuItemModifierWithDetails.model_rebuild()
MenuItemInventoryWithDetails.model_rebuild()
