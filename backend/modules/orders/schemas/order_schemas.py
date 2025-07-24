from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from ..enums.order_enums import OrderStatus, MultiItemRuleType, DelayReason


class OrderItemUpdate(BaseModel):
    id: Optional[int] = None
    menu_item_id: int
    quantity: int
    price: float
    notes: Optional[str] = None


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
        from_attributes = True


class OrderBase(BaseModel):
    staff_id: int
    table_no: Optional[int] = None
    status: OrderStatus


class OrderCreate(OrderBase):
    pass


class DelayFulfillmentRequest(BaseModel):
    scheduled_fulfillment_time: datetime
    delay_reason: Optional[str] = None
    additional_notes: Optional[str] = None


class OrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None
    order_items: Optional[List[OrderItemUpdate]] = None

    class Config:
        from_attributes = True


class DelayedOrderUpdate(OrderUpdate):
    scheduled_fulfillment_time: Optional[datetime] = None
    delay_reason: Optional[str] = None


class OrderOut(OrderBase):
    id: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    scheduled_fulfillment_time: Optional[datetime] = None
    delay_reason: Optional[str] = None
    delay_requested_at: Optional[datetime] = None
    order_items: Optional[List[OrderItemOut]] = []

    class Config:
        from_attributes = True


class MultiItemRuleRequest(BaseModel):
    order_items: List[OrderItemUpdate]
    rule_types: Optional[List[MultiItemRuleType]] = None


class RuleValidationResult(BaseModel):
    is_valid: bool
    message: Optional[str] = None
    modified_items: Optional[List[OrderItemOut]] = None
