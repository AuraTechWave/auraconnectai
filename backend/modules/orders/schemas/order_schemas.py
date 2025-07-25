from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from ..enums.order_enums import (OrderStatus, MultiItemRuleType,
                                 FraudCheckStatus, FraudRiskLevel,
                                 CheckpointType, SpecialInstructionType)


class SpecialInstructionBase(BaseModel):
    instruction_type: SpecialInstructionType
    description: str
    priority: Optional[int] = None
    target_station: Optional[str] = None

    class Config:
        from_attributes = True


class OrderItemUpdate(BaseModel):
    id: Optional[int] = None
    menu_item_id: int
    quantity: int
    price: float
    notes: Optional[str] = None
    special_instructions: Optional[List[SpecialInstructionBase]] = None


class OrderItemOut(BaseModel):
    id: int
    order_id: int
    menu_item_id: int
    quantity: int
    price: Decimal
    notes: Optional[str] = None
    special_instructions: Optional[List[SpecialInstructionBase]] = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_with_instructions(cls, orm_obj):
        """Create OrderItemOut with parsed special_instructions from JSON"""
        data = cls.model_validate(orm_obj)
        if orm_obj.special_instructions:
            data.special_instructions = [
                SpecialInstructionBase(**instr)
                for instr in orm_obj.special_instructions
            ]
        return data

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


class OrderAttachmentOut(BaseModel):
    id: int
    order_id: int
    file_name: str
    file_url: str
    file_type: str
    file_size: int
    description: Optional[str] = None
    is_public: bool = False
    uploaded_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AttachmentResponse(BaseModel):
    success: bool
    message: str
    data: Optional[OrderAttachmentOut] = None


class OrderAttachmentCreate(BaseModel):
    file_name: str
    file_url: str
    file_type: str
    file_size: int


class CustomerNotesUpdate(BaseModel):
    customer_notes: Optional[str] = None


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
    customer_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    scheduled_fulfillment_time: Optional[datetime] = None
    delay_reason: Optional[str] = None
    delay_requested_at: Optional[datetime] = None
    order_items: Optional[List[OrderItemOut]] = []
    tags: Optional[List[TagOut]] = []
    category: Optional[CategoryOut] = None
    attachments: Optional[List[OrderAttachmentOut]] = []

    class Config:
        from_attributes = True


class MultiItemRuleRequest(BaseModel):
    order_items: List[OrderItemUpdate]
    rule_types: Optional[List[MultiItemRuleType]] = None


class RuleValidationResult(BaseModel):
    is_valid: bool
    message: Optional[str] = None
    modified_items: Optional[List[OrderItemOut]] = None


class FraudCheckRequest(BaseModel):
    order_id: int
    checkpoint_types: Optional[List[CheckpointType]] = None
    force_recheck: bool = False


class FraudCheckResponse(BaseModel):
    order_id: int
    risk_score: float
    risk_level: FraudRiskLevel
    status: FraudCheckStatus
    flags: Optional[List[str]] = None
    checked_at: datetime

    class Config:
        from_attributes = True


class FraudAlertCreate(BaseModel):
    order_id: int
    alert_type: str
    severity: FraudRiskLevel
    description: str
    metadata: Optional[dict] = None


class FraudAlertOut(BaseModel):
    id: int
    order_id: int
    alert_type: str
    severity: FraudRiskLevel
    description: str
    resolved: bool
    created_at: datetime

    class Config:
        from_attributes = True


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


class KitchenPrintRequest(BaseModel):
    order_id: int = Field(..., gt=0, description="Order ID must be positive")
    printer_options: Optional[Dict[str, Any]] = Field(default_factory=dict)
    station_id: Optional[int] = Field(None, ge=1, description="Station ID must be positive")
    format_options: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @validator('printer_options', 'format_options')
    def validate_options(cls, v):
        if v is None:
            return {}
        return v


class KitchenPrintResponse(BaseModel):
    success: bool
    message: str
    ticket_id: Optional[str] = None
    print_timestamp: Optional[datetime] = None
    error_code: Optional[str] = None


class KitchenTicketFormat(BaseModel):
    order_id: int
    table_no: Optional[int] = None
    items: List[Dict[str, Any]]
    station_name: Optional[str] = None
    timestamp: datetime
    special_instructions: Optional[str] = None
    priority_level: Optional[int] = Field(None, ge=1, le=5, description="Priority level 1-5")

    class Config:
        from_attributes = True
