from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from ..enums.order_enums import (
    OrderStatus, MultiItemRuleType, SpecialInstructionType
)


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
