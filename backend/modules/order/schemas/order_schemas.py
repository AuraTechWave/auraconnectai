from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class OrderItemBase(BaseModel):
    item_name: str
    station: Optional[str] = None


class OrderItemCreate(OrderItemBase):
    pass


class OrderItemOut(OrderItemBase):
    id: int
    order_id: int
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class OrderBase(BaseModel):
    table_no: int
    customer_id: Optional[int] = None


class OrderCreate(OrderBase):
    staff_id: int
    order_items: List[OrderItemCreate]


class OrderOut(OrderBase):
    id: int
    status: str
    created_at: datetime
    order_items: List[OrderItemOut] = []

    class Config:
        orm_mode = True
