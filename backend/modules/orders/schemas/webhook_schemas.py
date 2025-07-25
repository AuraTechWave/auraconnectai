from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime
from ..enums.webhook_enums import WebhookEventType, WebhookStatus, WebhookDeliveryStatus


class WebhookConfigurationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    url: HttpUrl
    event_types: List[WebhookEventType]
    secret: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    timeout_seconds: int = Field(default=30, ge=1, le=300)


class WebhookConfigurationCreate(WebhookConfigurationBase):
    pass


class WebhookConfigurationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    url: Optional[HttpUrl] = None
    event_types: Optional[List[WebhookEventType]] = None
    secret: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    timeout_seconds: Optional[int] = Field(None, ge=1, le=300)
    is_active: Optional[bool] = None


class WebhookConfigurationOut(WebhookConfigurationBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WebhookPayload(BaseModel):
    event_type: WebhookEventType
    timestamp: datetime
    order_id: int
    order_data: Dict[str, Any]
    previous_status: Optional[str] = None
    new_status: Optional[str] = None


class WebhookDeliveryLogOut(BaseModel):
    id: int
    webhook_config_id: int
    order_id: int
    event_type: WebhookEventType
    status: WebhookStatus
    delivery_status: Optional[WebhookDeliveryStatus]
    payload: Dict[str, Any]
    response_status_code: Optional[int]
    response_body: Optional[str]
    error_message: Optional[str]
    attempt_count: int
    max_retries: int
    next_retry_at: Optional[datetime]
    delivered_at: Optional[datetime]
    failed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WebhookTestRequest(BaseModel):
    webhook_config_id: int


class WebhookTestResponse(BaseModel):
    success: bool
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
