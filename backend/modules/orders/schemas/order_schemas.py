from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from ..enums.order_enums import (OrderStatus, MultiItemRuleType,
                                 FraudCheckStatus, FraudRiskLevel,
                                 CheckpointType)


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


class OrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None
    order_items: Optional[List[OrderItemUpdate]] = None

    class Config:
        from_attributes = True


class OrderOut(OrderBase):
    id: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
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
