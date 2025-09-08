"""
Order splitting schemas for handling split orders and payments.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum


class SplitType(str, Enum):
    """Types of order splits"""

    TICKET = "ticket"  # Split for different kitchen tickets
    DELIVERY = "delivery"  # Split for separate deliveries
    PAYMENT = "payment"  # Split for payment purposes


class PaymentStatus(str, Enum):
    """Payment status for split payments"""

    PENDING = "pending"
    PAID = "paid"
    PARTIAL = "partial"
    FAILED = "failed"
    REFUNDED = "refunded"


class OrderItemSplitRequest(BaseModel):
    """Request to split specific items from an order"""

    item_id: int = Field(..., description="ID of the order item to split")
    quantity: int = Field(..., gt=0, description="Quantity to split")
    notes: Optional[str] = Field(None, description="Notes for this split item")


class OrderSplitRequest(BaseModel):
    """Request to split an order"""

    split_type: SplitType = Field(..., description="Type of split operation")
    items: List[OrderItemSplitRequest] = Field(
        ..., min_items=1, description="Items to split"
    )
    split_reason: Optional[str] = Field(None, description="Reason for splitting")
    customer_id: Optional[int] = Field(
        None, description="Customer ID for the split order"
    )
    table_no: Optional[int] = Field(None, description="Table number for split order")
    delivery_address: Optional[Dict[str, Any]] = Field(
        None, description="Delivery address if splitting for delivery"
    )
    scheduled_time: Optional[datetime] = Field(
        None, description="Scheduled time for split order"
    )

    @field_validator("items", mode="after")
    def validate_unique_items(cls, v):
        """Ensure no duplicate item IDs in split request"""
        item_ids = [item.item_id for item in v]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Duplicate item IDs in split request")
        return v


class PaymentSplitRequest(BaseModel):
    """Request to split payment for an order"""

    splits: List[Dict[str, Any]] = Field(
        ..., min_items=2, description="Payment split details"
    )

    @field_validator("splits", mode="after")
    def validate_splits(cls, v):
        """Validate payment splits"""
        for split in v:
            if "amount" not in split or split["amount"] <= 0:
                raise ValueError("Each split must have a positive amount")
            if "customer_id" not in split and "payment_method" not in split:
                raise ValueError(
                    "Each split must have either customer_id or payment_method"
                )
        return v


class OrderSplitResponse(BaseModel):
    """Response after splitting an order"""

    success: bool
    message: str
    parent_order_id: int
    split_order_ids: List[int]
    split_details: List[Dict[str, Any]]

    class Config:
        from_attributes = True


class OrderSplitDetail(BaseModel):
    """Detailed information about an order split"""

    id: int
    parent_order_id: int
    split_order_id: int
    split_type: SplitType
    split_reason: Optional[str]
    split_by: int
    created_at: datetime
    split_metadata: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


class SplitPaymentDetail(BaseModel):
    """Detailed information about split payment"""

    id: int
    parent_order_id: int
    split_order_id: int
    amount: Decimal
    payment_method: Optional[str]
    payment_status: PaymentStatus
    payment_reference: Optional[str]
    paid_by_customer_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SplitOrderSummary(BaseModel):
    """Summary of all splits for an order"""

    parent_order_id: int
    total_splits: int
    split_orders: List[OrderSplitDetail]
    payment_splits: List[SplitPaymentDetail]
    total_amount: Decimal
    paid_amount: Decimal
    pending_amount: Decimal

    class Config:
        from_attributes = True


class MergeSplitRequest(BaseModel):
    """Request to merge split orders back together"""

    split_order_ids: List[int] = Field(
        ..., min_items=2, description="Split order IDs to merge"
    )
    merge_reason: Optional[str] = Field(None, description="Reason for merging")
    keep_original: bool = Field(True, description="Keep original parent order")


class BulkSplitRequest(BaseModel):
    """Request to split an order into multiple parts at once"""

    split_type: SplitType
    split_strategy: str = Field(
        ..., description="Strategy: 'by_station', 'by_customer', 'by_course'"
    )
    split_configs: List[Dict[str, Any]] = Field(
        ..., description="Configuration for each split"
    )

    @field_validator("split_strategy", mode="after")
    def validate_strategy(cls, v, values):
        """Validate split strategy based on split type"""
        valid_strategies = {
            SplitType.TICKET: ["by_station", "by_course", "by_preparation_time"],
            SplitType.DELIVERY: ["by_address", "by_time", "by_customer"],
            SplitType.PAYMENT: ["by_customer", "equal_split", "by_items"],
        }

        split_type = values.get("split_type")
        if split_type and v not in valid_strategies.get(split_type, []):
            raise ValueError(f"Invalid strategy '{v}' for split type '{split_type}'")
        return v


class SplitValidationResponse(BaseModel):
    """Response for split validation"""

    can_split: bool
    reason: Optional[str] = None
    splittable_items: List[Dict[str, Any]]
    warnings: List[str] = Field(default_factory=list)
    estimated_totals: Dict[str, Decimal]
