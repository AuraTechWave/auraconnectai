from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class InventoryBase(BaseModel):
    item_name: str
    quantity: float
    unit: str
    threshold: float
    vendor_id: Optional[int] = None


class InventoryCreate(InventoryBase):
    pass


class InventoryUpdate(BaseModel):
    item_name: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    threshold: Optional[float] = None
    vendor_id: Optional[int] = None

    class Config:
        from_attributes = True


class InventoryOut(InventoryBase):
    id: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MenuItemInventoryBase(BaseModel):
    menu_item_id: int
    inventory_id: int
    quantity_needed: float


class MenuItemInventoryCreate(MenuItemInventoryBase):
    pass


class MenuItemInventoryOut(MenuItemInventoryBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LowStockAlert(BaseModel):
    id: int
    item_name: str
    current_quantity: float
    threshold: float
    unit: str
