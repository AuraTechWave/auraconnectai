# backend/modules/payments/schemas/payment_schemas.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from decimal import Decimal
from datetime import datetime
from ..models.payment_models import (
    PaymentGateway, PaymentStatus, PaymentMethod,
    RefundStatus
)


class PaymentCreate(BaseModel):
    """Schema for creating a payment"""
    order_id: int
    gateway: PaymentGateway
    amount: Optional[Decimal] = Field(None, description="Payment amount (defaults to order total)")
    currency: str = Field("USD", description="Currency code")
    payment_method_id: Optional[str] = Field(None, description="Saved payment method ID")
    save_payment_method: bool = Field(False, description="Save payment method for future use")
    return_url: Optional[str] = Field(None, description="URL to redirect after payment (PayPal)")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    model_config = ConfigDict(from_attributes=True)


class PaymentResponse(BaseModel):
    """Basic payment response"""
    id: int
    payment_id: str
    order_id: int
    gateway: PaymentGateway
    gateway_payment_id: Optional[str] = None
    amount: Decimal
    currency: str
    status: PaymentStatus
    payment_method: Optional[PaymentMethod] = None
    requires_action: bool = False
    action_url: Optional[str] = None
    gateway_config: Optional[Dict[str, Any]] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class PaymentDetail(PaymentResponse):
    """Detailed payment response with additional information"""
    payment_method_details: Optional[Dict[str, Any]] = None
    fee_amount: Optional[Decimal] = None
    net_amount: Optional[Decimal] = None
    processed_at: Optional[datetime] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    refunds: List['RefundResponse'] = Field(default_factory=list)
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class RefundCreate(BaseModel):
    """Schema for creating a refund"""
    amount: Optional[Decimal] = Field(None, description="Refund amount (None for full refund)")
    reason: Optional[str] = Field(None, description="Refund reason")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    model_config = ConfigDict(from_attributes=True)


class RefundResponse(BaseModel):
    """Refund response schema"""
    id: int
    refund_id: str
    payment_id: int
    gateway_refund_id: Optional[str] = None
    amount: Decimal
    currency: str
    status: RefundStatus
    reason: Optional[str] = None
    processed_at: Optional[datetime] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class PaymentMethodCreate(BaseModel):
    """Schema for saving a payment method"""
    customer_id: int
    gateway: PaymentGateway
    payment_method_token: str = Field(..., description="Token from frontend SDK")
    set_as_default: bool = Field(False, description="Set as default payment method")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    model_config = ConfigDict(from_attributes=True)


class PaymentMethodResponse(BaseModel):
    """Saved payment method response"""
    id: int
    customer_id: int
    gateway: PaymentGateway
    method_type: PaymentMethod
    display_name: Optional[str] = None
    card_last4: Optional[str] = None
    card_brand: Optional[str] = None
    card_exp_month: Optional[int] = None
    card_exp_year: Optional[int] = None
    is_default: bool
    is_active: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class PaymentGatewayConfig(BaseModel):
    """Public gateway configuration"""
    gateway: PaymentGateway
    config: Dict[str, Any]
    
    model_config = ConfigDict(from_attributes=True)


class PaymentWebhookResponse(BaseModel):
    """Webhook processing response"""
    status: str
    message: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class PaymentSummary(BaseModel):
    """Payment summary for order"""
    total_amount: Decimal
    paid_amount: Decimal
    refunded_amount: Decimal
    pending_amount: Decimal
    payment_status: str
    payments: List[PaymentResponse]
    
    model_config = ConfigDict(from_attributes=True)


class PaymentFilter(BaseModel):
    """Filter parameters for payment queries"""
    order_id: Optional[int] = None
    customer_id: Optional[int] = None
    gateway: Optional[PaymentGateway] = None
    status: Optional[PaymentStatus] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    
    model_config = ConfigDict(from_attributes=True)


class PaymentStats(BaseModel):
    """Payment statistics"""
    total_payments: int
    total_amount: Decimal
    successful_payments: int
    successful_amount: Decimal
    failed_payments: int
    refunded_amount: Decimal
    average_payment: Decimal
    gateway_breakdown: Dict[str, Dict[str, Any]]
    
    model_config = ConfigDict(from_attributes=True)