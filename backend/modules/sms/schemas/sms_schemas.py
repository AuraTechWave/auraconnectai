# backend/modules/sms/schemas/sms_schemas.py

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

from modules.sms.models.sms_models import (
    SMSProvider, SMSStatus, SMSDirection, SMSTemplateCategory
)


class SMSMessageBase(BaseModel):
    """Base schema for SMS messages"""
    to_number: str = Field(..., description="Recipient phone number in E.164 format")
    message_body: str = Field(..., min_length=1, max_length=1600)
    template_id: Optional[int] = None
    template_variables: Optional[Dict[str, Any]] = None
    customer_id: Optional[int] = None
    order_id: Optional[int] = None
    reservation_id: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator('to_number', mode="after")
    def validate_phone_number(cls, v):
        # Basic E.164 format validation
        if not v.startswith('+'):
            raise ValueError('Phone number must be in E.164 format (starting with +)')
        if not v[1:].isdigit():
            raise ValueError('Phone number must contain only digits after +')
        if len(v) < 10 or len(v) > 16:
            raise ValueError('Invalid phone number length')
        return v


class SMSMessageCreate(SMSMessageBase):
    """Schema for creating SMS messages"""
    provider: Optional[SMSProvider] = SMSProvider.TWILIO
    from_number: Optional[str] = None  # Will use default if not provided


class SMSMessageUpdate(BaseModel):
    """Schema for updating SMS messages"""
    status: Optional[SMSStatus] = None
    delivered_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    provider_response: Optional[Dict[str, Any]] = None
    provider_error: Optional[str] = None
    cost_amount: Optional[float] = None
    segments_count: Optional[int] = None


class SMSMessageResponse(SMSMessageBase):
    """Schema for SMS message response"""
    id: int
    provider: SMSProvider
    direction: SMSDirection
    status: SMSStatus
    from_number: str
    provider_message_id: Optional[str] = None
    segments_count: int
    cost_amount: Optional[float] = None
    cost_currency: str
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    retry_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SMSTemplateBase(BaseModel):
    """Base schema for SMS templates"""
    name: str = Field(..., min_length=1, max_length=100)
    category: SMSTemplateCategory
    description: Optional[str] = None
    template_body: str = Field(..., min_length=1)
    variables: Optional[List[str]] = None
    max_length: int = Field(default=160, gt=0)

    @field_validator('template_body', mode="after")
    def validate_template_variables(cls, v, values):
        # Check for variable placeholders in template
        import re
        placeholders = re.findall(r'\{\{(\w+)\}\}', v)
        if placeholders and 'variables' in values:
            if not values['variables']:
                raise ValueError(f'Template contains variables {placeholders} but no variables list provided')
            missing = set(placeholders) - set(values['variables'] or [])
            if missing:
                raise ValueError(f'Template contains undefined variables: {missing}')
        return v


class SMSTemplateCreate(SMSTemplateBase):
    """Schema for creating SMS templates"""
    is_active: bool = True


class SMSTemplateUpdate(BaseModel):
    """Schema for updating SMS templates"""
    name: Optional[str] = None
    description: Optional[str] = None
    template_body: Optional[str] = None
    variables: Optional[List[str]] = None
    is_active: Optional[bool] = None
    max_length: Optional[int] = None


class SMSTemplateResponse(SMSTemplateBase):
    """Schema for SMS template response"""
    id: int
    is_active: bool
    estimated_segments: int
    usage_count: int
    last_used_at: Optional[datetime] = None
    version: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SMSOptOutBase(BaseModel):
    """Base schema for SMS opt-out"""
    phone_number: str = Field(..., description="Phone number in E.164 format")
    opt_out_reason: Optional[str] = None
    categories_opted_out: Optional[List[SMSTemplateCategory]] = None


class SMSOptOutCreate(SMSOptOutBase):
    """Schema for creating opt-out record"""
    customer_id: Optional[int] = None
    opt_out_method: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class SMSOptOutUpdate(BaseModel):
    """Schema for updating opt-out record"""
    opted_out: bool
    opt_in_method: Optional[str] = None
    categories_opted_out: Optional[List[SMSTemplateCategory]] = None


class SMSOptOutResponse(SMSOptOutBase):
    """Schema for opt-out response"""
    id: int
    customer_id: Optional[int] = None
    opted_out: bool
    opt_out_date: datetime
    opt_out_method: Optional[str] = None
    opted_in_date: Optional[datetime] = None
    opt_in_method: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SMSCostBase(BaseModel):
    """Base schema for SMS costs"""
    billing_period_start: datetime
    billing_period_end: datetime
    provider: SMSProvider
    total_messages: int
    total_segments: int
    outbound_cost: float
    inbound_cost: float
    total_cost: float
    currency: str = "USD"


class SMSCostCreate(SMSCostBase):
    """Schema for creating cost record"""
    phone_number_cost: Optional[float] = 0.0
    additional_fees: Optional[float] = 0.0
    cost_by_category: Optional[Dict[str, Dict[str, Any]]] = None
    provider_invoice_id: Optional[str] = None
    provider_invoice_url: Optional[str] = None


class SMSCostResponse(SMSCostBase):
    """Schema for cost response"""
    id: int
    phone_number_cost: float
    additional_fees: float
    cost_by_category: Optional[Dict[str, Dict[str, Any]]] = None
    provider_invoice_id: Optional[str] = None
    provider_invoice_url: Optional[str] = None
    is_paid: bool
    paid_at: Optional[datetime] = None
    payment_reference: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SMSSendRequest(BaseModel):
    """Request schema for sending single SMS"""
    to_number: str = Field(..., description="Recipient phone number")
    message: Optional[str] = Field(None, description="Direct message text")
    template_id: Optional[int] = Field(None, description="Template ID to use")
    template_variables: Optional[Dict[str, Any]] = Field(None, description="Variables for template")
    customer_id: Optional[int] = None
    order_id: Optional[int] = None
    reservation_id: Optional[int] = None
    schedule_at: Optional[datetime] = Field(None, description="Schedule message for future")

    @field_validator('message', mode="after")
    def validate_message_or_template(cls, v, values):
        if not v and not values.get('template_id'):
            raise ValueError('Either message or template_id must be provided')
        return v


class SMSBulkSendRequest(BaseModel):
    """Request schema for sending bulk SMS"""
    recipients: List[SMSSendRequest]
    batch_name: Optional[str] = None
    send_immediately: bool = True


class SMSDeliveryStatus(BaseModel):
    """Webhook schema for delivery status updates"""
    provider_message_id: str
    status: SMSStatus
    delivered_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class SMSStatusUpdate(BaseModel):
    """Schema for updating message status"""
    message_id: int
    status: SMSStatus
    delivered_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class SMSCostSummary(BaseModel):
    """Schema for cost summary report"""
    period_start: datetime
    period_end: datetime
    total_messages: int
    total_segments: int
    total_cost: float
    currency: str
    cost_by_provider: Dict[str, float]
    cost_by_category: Dict[str, Dict[str, Any]]
    average_cost_per_message: float
    comparison_to_previous: Optional[Dict[str, Any]] = None