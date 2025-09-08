from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum
from ..enums.order_enums import (
    OrderStatus,
    MultiItemRuleType,
    OrderPriority,
    FraudCheckStatus,
    FraudRiskLevel,
    CheckpointType,
    SpecialInstructionType,
)


class SpecialInstructionBase(BaseModel):
    instruction_type: SpecialInstructionType
    description: str
    priority: Optional[int] = None
    target_station: Optional[str] = None

    class Config:
        from_attributes = True


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
    priority: OrderPriority = OrderPriority.NORMAL
    priority_updated_at: Optional[datetime] = None
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


class OrderPriorityUpdate(BaseModel):
    priority: OrderPriority = Field(..., description="New priority level for the order")
    reason: Optional[str] = Field(
        None, max_length=500, description="Reason for priority change"
    )

    @field_validator("reason")
    def validate_reason(cls, v):
        if v and len(v.strip()) == 0:
            return None
        return v


class OrderPriorityResponse(BaseModel):
    message: str
    previous_priority: str
    new_priority: str
    updated_at: datetime
    reason: Optional[str] = None
    data: OrderOut

    model_config = {"from_attributes": True}


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

    @field_validator("has_more")
    def calculate_has_more(cls, v, info):
        events = info.data.get("events", [])
        total_count = info.data.get("total_count", 0)
        return len(events) < total_count

    class Config:
        from_attributes = True


class KitchenPrintRequest(BaseModel):
    order_id: int = Field(..., gt=0, description="Order ID must be positive")
    printer_options: Optional[Dict[str, Any]] = Field(default_factory=dict)
    station_id: Optional[int] = Field(
        None, ge=1, description="Station ID must be positive"
    )
    format_options: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @field_validator("printer_options", "format_options")
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
    priority_level: Optional[int] = Field(
        None, ge=1, le=5, description="Priority level 1-5"
    )

    class Config:
        from_attributes = True


class AutoCancellationConfigBase(BaseModel):
    tenant_id: Optional[int] = None
    team_id: Optional[int] = None
    status: OrderStatus
    threshold_minutes: int = Field(..., gt=0, description="Time threshold in minutes")
    enabled: bool = True
    updated_by: int

    @field_validator("status")
    def validate_cancellable_status(cls, v):
        cancellable_statuses = [
            OrderStatus.PENDING,
            OrderStatus.IN_PROGRESS,
            OrderStatus.IN_KITCHEN,
        ]
        if v not in cancellable_statuses:
            raise ValueError(
                f"Status {v} cannot be auto-cancelled. "
                f"Only {[s.value for s in cancellable_statuses]} are allowed."
            )
        return v


class AutoCancellationConfigCreate(AutoCancellationConfigBase):
    pass


class AutoCancellationConfigUpdate(BaseModel):
    threshold_minutes: Optional[int] = Field(None, gt=0)
    enabled: Optional[bool] = None
    updated_by: int


class AutoCancellationConfigOut(AutoCancellationConfigBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StaleCancellationResponse(BaseModel):
    cancelled_count: int
    cancelled_orders: List[int]
    message: str


# Order Inventory Integration Schemas
class OrderCompleteRequest(BaseModel):
    order_id: int
    payment_status: str = "paid"
    notes: Optional[str] = None


class OrderCompleteResponse(BaseModel):
    order_id: int
    status: str
    inventory_updated: bool
    deducted_items: List[Dict[str, Any]]
    message: str


class OrderCancelRequest(BaseModel):
    order_id: int
    reason: str
    refund_amount: Optional[float] = None


class OrderCancelResponse(BaseModel):
    order_id: int
    status: str
    inventory_restored: bool
    restored_items: List[Dict[str, Any]]
    message: str


class PartialFulfillmentRequest(BaseModel):
    order_id: int
    fulfilled_items: List[Dict[str, int]]  # [{"item_id": 1, "quantity": 2}]
    reason: Optional[str] = None


class PartialFulfillmentResponse(BaseModel):
    order_id: int
    status: str
    fulfilled_items: List[Dict[str, Any]]
    remaining_items: List[Dict[str, Any]]
    inventory_updated: bool
    message: str


class InventoryAvailabilityResponse(BaseModel):
    available: bool
    unavailable_items: List[Dict[str, Any]]
    warnings: List[str]
    message: str
