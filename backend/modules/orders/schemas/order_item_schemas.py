from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class OrderItemBase(BaseModel, ConfigDict):
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
    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed
