from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from ..enums.order_enums import OrderStatus


class OrderItemOut(BaseModel):
    id: int
    order_id: int
    menu_item_id: int
    quantity: int
    price: Decimal
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class OrderBase(BaseModel):
    staff_id: int
    status: OrderStatus


class OrderCreate(OrderBase):
    pass


class OrderOut(OrderBase):
    id: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    order_items: List[OrderItemOut] = []

    class Config:
        orm_mode = True
