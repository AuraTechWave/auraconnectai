from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from ..enums.order_enums import OrderStatus


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

    class Config:
        orm_mode = True
