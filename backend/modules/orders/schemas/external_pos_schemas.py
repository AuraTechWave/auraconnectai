# backend/modules/orders/schemas/external_pos_schemas.py

"""
Pydantic schemas for external POS webhook management.
"""

from pydantic import BaseModel, Field, HttpUrl, validator
from typing import Dict, Any, Optional, List
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from modules.orders.enums.external_pos_enums import (
    ExternalPOSProvider,
    ExternalPOSEventType,
    WebhookProcessingStatus,
    PaymentStatus,
    PaymentMethod,
    AuthenticationType,
)


# Provider Configuration Schemas


class ExternalPOSProviderCreate(BaseModel):
    """Schema for creating an external POS provider"""

    provider_code: str = Field(..., min_length=2, max_length=50)
    provider_name: str = Field(..., min_length=2, max_length=100)
    webhook_endpoint_id: str = Field(..., min_length=2, max_length=100)
    auth_type: AuthenticationType
    auth_config: Dict[str, Any] = Field(..., description="Authentication configuration")
    settings: Optional[Dict[str, Any]] = None
    supported_events: List[str] = Field(default_factory=list)
    rate_limit_per_minute: int = Field(default=60, ge=1, le=1000)

    @validator("auth_config")
    def validate_auth_config(cls, v, values):
        auth_type = values.get("auth_type")
        if auth_type == AuthenticationType.HMAC_SHA256:
            if "webhook_secret" not in v:
                raise ValueError("webhook_secret required for HMAC authentication")
        elif auth_type == AuthenticationType.API_KEY:
            if "api_key" not in v:
                raise ValueError("api_key required for API key authentication")
        return v


class ExternalPOSProviderUpdate(BaseModel):
    """Schema for updating an external POS provider"""

    provider_name: Optional[str] = Field(None, min_length=2, max_length=100)
    is_active: Optional[bool] = None
    auth_config: Optional[Dict[str, Any]] = None
    settings: Optional[Dict[str, Any]] = None
    supported_events: Optional[List[str]] = None
    rate_limit_per_minute: Optional[int] = Field(None, ge=1, le=1000)


class ExternalPOSProviderResponse(BaseModel):
    """Response schema for external POS provider"""

    id: int
    provider_code: str
    provider_name: str
    webhook_endpoint_id: str
    webhook_url: str
    is_active: bool
    auth_type: str
    supported_events: List[str]
    rate_limit_per_minute: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Webhook Event Schemas


class WebhookEventResponse(BaseModel):
    """Response schema for webhook events"""

    id: int
    event_id: UUID
    provider_code: str
    event_type: str
    event_timestamp: datetime
    processing_status: WebhookProcessingStatus
    is_verified: bool
    processed_at: Optional[datetime]
    processing_attempts: int
    last_error: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class WebhookEventDetailResponse(WebhookEventResponse):
    """Detailed response for webhook event including payload"""

    request_headers: Dict[str, Any]
    request_body: Dict[str, Any]
    verification_details: Optional[Dict[str, Any]]
    payment_updates: List["PaymentUpdateResponse"]


# Payment Update Schemas


class PaymentUpdateResponse(BaseModel):
    """Response schema for payment updates"""

    id: int
    webhook_event_id: int
    external_transaction_id: str
    external_order_id: Optional[str]
    external_payment_id: Optional[str]
    order_id: Optional[int]
    payment_status: PaymentStatus
    payment_method: PaymentMethod
    payment_amount: Decimal
    currency: str
    tip_amount: Optional[Decimal]
    tax_amount: Optional[Decimal]
    discount_amount: Optional[Decimal]
    card_last_four: Optional[str]
    card_brand: Optional[str]
    is_processed: bool
    processed_at: Optional[datetime]
    processing_notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# Webhook Log Schemas


class WebhookLogResponse(BaseModel):
    """Response schema for webhook logs"""

    id: int
    webhook_event_id: int
    log_level: str
    log_type: str
    message: str
    details: Optional[Dict[str, Any]]
    occurred_at: datetime

    class Config:
        from_attributes = True


# Webhook Statistics Schemas


class WebhookStatistics(BaseModel):
    """Statistics for webhook processing"""

    provider_code: str
    total_events: int
    processed_events: int
    failed_events: int
    pending_events: int
    duplicate_events: int
    success_rate: float
    average_processing_time_ms: Optional[float]
    last_event_at: Optional[datetime]


class WebhookHealthStatus(BaseModel):
    """Health status for webhook system"""

    status: str  # healthy, degraded, unhealthy
    providers: List[Dict[str, Any]]
    retry_scheduler_status: Dict[str, Any]
    recent_errors: List[Dict[str, Any]]
    recommendations: List[str]


# Test Webhook Schemas


class TestWebhookRequest(BaseModel):
    """Request to test a webhook endpoint"""

    event_type: ExternalPOSEventType = ExternalPOSEventType.PAYMENT_COMPLETED
    payment_amount: Decimal = Field(default=Decimal("10.00"), ge=0)
    order_id: Optional[str] = None
    custom_data: Optional[Dict[str, Any]] = None


class TestWebhookResponse(BaseModel):
    """Response for webhook test"""

    webhook_url: str
    headers: Dict[str, str]
    body: Dict[str, Any]
    instructions: str


# Configuration Management Schemas


class WebhookConfigurationRequest(BaseModel):
    """Request to configure webhook settings"""

    retry_enabled: bool = True
    max_retry_attempts: int = Field(default=3, ge=1, le=10)
    retry_delay_seconds: List[int] = Field(default=[60, 300, 900])
    webhook_timeout_seconds: int = Field(default=30, ge=5, le=60)
    duplicate_window_minutes: int = Field(default=60, ge=5, le=1440)
    retention_days: int = Field(default=30, ge=7, le=365)


class WebhookConfigurationResponse(BaseModel):
    """Response for webhook configuration"""

    retry_enabled: bool
    max_retry_attempts: int
    retry_delay_seconds: List[int]
    webhook_timeout_seconds: int
    duplicate_window_minutes: int
    retention_days: int
    updated_at: datetime


# Order Matching Schemas


class OrderMatchingRequest(BaseModel):
    """Request to manually match a payment to an order"""

    payment_update_id: int
    order_id: int
    notes: Optional[str] = None


class OrderMatchingResponse(BaseModel):
    """Response for order matching"""

    success: bool
    payment_update_id: int
    order_id: int
    reconciliation_id: Optional[int]
    message: str


# Update forward references
WebhookEventDetailResponse.model_rebuild()
