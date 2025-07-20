from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class OrderItemBase(BaseModel):
    order_id: int
    menu_item_id: int
    quantity: int
    price: float
    notes: Optional[str] = None


class OrderItemCreate(OrderItemBase):
    pass


class OrderItemOut(OrderItemBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
