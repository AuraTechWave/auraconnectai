from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum
from ..enums.order_enums import OrderStatus, MultiItemRuleType


class AuditAction(str, Enum):
    STATUS_CHANGE = "status_change"
    CREATION = "creation"
    MODIFICATION = "modification"
    DELETION = "deletion"


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


class TagBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None


class TagCreate(TagBase):
    pass


class TagOut(TagBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None


class CategoryCreate(CategoryBase):
    pass


class CategoryOut(CategoryBase):
    id: int
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
    tags: Optional[List[TagOut]] = []
    category: Optional[CategoryOut] = None

    class Config:
        from_attributes = True


class MultiItemRuleRequest(BaseModel):
    order_items: List[OrderItemUpdate]
    rule_types: Optional[List[MultiItemRuleType]] = None


class RuleValidationResult(BaseModel):
    is_valid: bool
    message: Optional[str] = None
    modified_items: Optional[List[OrderItemOut]] = None


class OrderTagRequest(BaseModel):
    tag_ids: List[int]


class OrderCategoryRequest(BaseModel):
    category_id: Optional[int] = None


class ArchiveOrderRequest(BaseModel):
    pass


class ArchiveOrderResponse(BaseModel):
    message: str
    data: OrderOut


class ArchivedOrdersFilter(BaseModel):
    staff_id: Optional[int] = None
    table_no: Optional[int] = None
    limit: int = 100
    offset: int = 0


class OrderAuditEvent(BaseModel):
    id: int = Field(..., description="Audit log ID")
    order_id: int
    action: str = Field(..., description="Type of action performed")
    previous_status: Optional[OrderStatus] = None
    new_status: OrderStatus
    user_id: int
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class OrderAuditResponse(BaseModel):
    events: List[OrderAuditEvent]
    total_count: int
    has_more: bool = Field(..., description="Whether there are more records")
    
    @validator('has_more', always=True)
    def calculate_has_more(cls, v, values):
        events = values.get('events', [])
        total_count = values.get('total_count', 0)
        return len(events) < total_count

    class Config:
        from_attributes = True
