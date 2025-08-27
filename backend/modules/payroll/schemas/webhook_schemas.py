# backend/modules/payroll/schemas/webhook_schemas.py

"""
Webhook schemas for payroll event notifications.

Defines request/response models for webhook management
and event notification payloads.
"""

from pydantic import BaseModel, Field, validator, HttpUrl, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class WebhookEventType(str, Enum):
    """Supported webhook event types."""

    # Payroll processing events
    PAYROLL_STARTED = "payroll.started"
    PAYROLL_COMPLETED = "payroll.completed"
    PAYROLL_FAILED = "payroll.failed"

    # Payment events
    PAYMENT_PROCESSED = "payment.processed"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_APPROVED = "payment.approved"
    PAYMENT_CANCELLED = "payment.cancelled"

    # Tax events
    TAX_RULE_UPDATED = "tax_rule.updated"
    TAX_CALCULATION_FAILED = "tax_calculation.failed"

    # Employee events
    EMPLOYEE_PAYROLL_UPDATED = "employee.payroll_updated"
    EMPLOYEE_PAY_RATE_CHANGED = "employee.pay_rate_changed"

    # Batch processing events
    BATCH_JOB_STARTED = "batch.started"
    BATCH_JOB_COMPLETED = "batch.completed"
    BATCH_JOB_FAILED = "batch.failed"

    # Export events
    EXPORT_COMPLETED = "export.completed"
    EXPORT_FAILED = "export.failed"


class WebhookSubscriptionRequest(BaseModel):
    """Request schema for creating/updating webhook subscriptions."""

    webhook_url: HttpUrl = Field(
        ..., description="URL to receive webhook notifications"
    )
    event_types: List[WebhookEventType] = Field(
        ..., description="List of event types to subscribe to", min_items=1
    )
    active: bool = Field(True, description="Whether the subscription is active")
    description: Optional[str] = Field(
        None, description="Optional description of the webhook", max_length=500
    )
    headers: Optional[Dict[str, str]] = Field(
        None, description="Optional custom headers to include in webhook requests"
    )
    retry_policy: Optional[Dict[str, Any]] = Field(
        None, description="Optional retry policy configuration"
    )

    @field_validator("event_types")
    @classmethod
    def validate_event_types(cls, v):
        if len(set(v)) != len(v):
            raise ValueError("event_types cannot contain duplicates")
        return v

    @field_validator("headers")
    @classmethod
    def validate_headers(cls, v):
        if v:
            # Prevent overriding critical headers
            reserved_headers = {
                "x-webhook-signature",
                "x-webhook-timestamp",
                "x-webhook-event",
            }
            if any(key.lower() in reserved_headers for key in v.keys()):
                raise ValueError("Cannot override reserved webhook headers")
        return v


class WebhookSubscriptionResponse(BaseModel):
    """Response schema for webhook subscription."""

    id: int = Field(..., description="Unique subscription ID")
    webhook_url: str = Field(..., description="Webhook URL")
    event_types: List[str] = Field(..., description="Subscribed event types")
    secret_key: str = Field(
        ..., description="Secret key for webhook signature validation"
    )
    active: bool = Field(..., description="Whether the subscription is active")
    description: Optional[str] = Field(None, description="Webhook description")
    created_at: datetime = Field(..., description="Subscription creation timestamp")
    last_triggered_at: Optional[datetime] = Field(
        None, description="Last time webhook was triggered"
    )
    failure_count: int = Field(0, description="Number of consecutive failures")
    total_events_sent: int = Field(0, description="Total number of events sent")


class WebhookTestRequest(BaseModel):
    """Request schema for testing webhook."""

    subscription_id: int = Field(..., description="ID of subscription to test")
    event_type: WebhookEventType = Field(..., description="Event type to simulate")
    custom_payload: Optional[Dict[str, Any]] = Field(
        None, description="Optional custom payload data"
    )


class WebhookTestResponse(BaseModel):
    """Response schema for webhook test."""

    test_id: str = Field(..., description="Unique test ID")
    subscription_id: int = Field(..., description="Tested subscription ID")
    webhook_url: str = Field(..., description="Webhook URL that was tested")
    event_type: str = Field(..., description="Event type that was simulated")
    status: str = Field(..., description="Test status (queued, sent, failed)")
    test_payload: Dict[str, Any] = Field(..., description="Payload that was sent")
    response_status: Optional[int] = Field(
        None, description="HTTP response status code"
    )
    response_body: Optional[str] = Field(None, description="Response body from webhook")
    error_message: Optional[str] = Field(
        None, description="Error message if test failed"
    )


class WebhookEventLog(BaseModel):
    """Log entry for webhook event."""

    event_id: str = Field(..., description="Unique event ID")
    subscription_id: int = Field(..., description="Subscription ID")
    event_type: str = Field(..., description="Event type")
    timestamp: datetime = Field(..., description="Event timestamp")
    status: str = Field(..., description="Delivery status (success, failed, pending)")
    attempts: int = Field(..., description="Number of delivery attempts")
    response_status: Optional[int] = Field(None, description="HTTP response status")
    response_time_ms: Optional[float] = Field(
        None, description="Response time in milliseconds"
    )
    error_message: Optional[str] = Field(None, description="Error message if failed")
    payload_size: int = Field(..., description="Size of payload in bytes")


# Webhook payload schemas for different event types


class BaseWebhookPayload(BaseModel):
    """Base webhook payload structure."""

    event_id: str = Field(..., description="Unique event identifier")
    event_type: str = Field(..., description="Type of event")
    timestamp: datetime = Field(..., description="Event timestamp")
    tenant_id: Optional[int] = Field(
        None, description="Tenant ID for multi-tenant environments"
    )


class PayrollStartedPayload(BaseWebhookPayload):
    """Payload for payroll.started event."""

    data: Dict[str, Any] = Field(
        ..., description="Event data containing job_id, employee_count, pay_period"
    )


class PayrollCompletedPayload(BaseWebhookPayload):
    """Payload for payroll.completed event."""

    data: Dict[str, Any] = Field(
        ..., description="Event data containing job_id, results summary"
    )


class PaymentProcessedPayload(BaseWebhookPayload):
    """Payload for payment.processed event."""

    data: Dict[str, Any] = Field(
        ..., description="Event data containing payment_id, employee_id, amounts"
    )


class TaxRuleUpdatedPayload(BaseWebhookPayload):
    """Payload for tax_rule.updated event."""

    data: Dict[str, Any] = Field(
        ..., description="Event data containing rule_id, changes, effective_date"
    )


class ExportCompletedPayload(BaseWebhookPayload):
    """Payload for export.completed event."""

    data: Dict[str, Any] = Field(
        ..., description="Event data containing export_id, download_url, expiry"
    )


# Webhook configuration schemas


class WebhookRetryPolicy(BaseModel):
    """Webhook retry policy configuration."""

    max_retries: int = Field(
        3, ge=0, le=10, description="Maximum number of retry attempts"
    )
    initial_delay_seconds: int = Field(
        60, ge=1, le=3600, description="Initial delay before first retry"
    )
    backoff_multiplier: float = Field(
        2.0, ge=1.0, le=10.0, description="Backoff multiplier for subsequent retries"
    )
    max_delay_seconds: int = Field(
        3600, ge=60, le=86400, description="Maximum delay between retries"
    )


class WebhookSecurityConfig(BaseModel):
    """Webhook security configuration."""

    signature_algorithm: str = Field(
        "hmac-sha256",
        pattern="^(hmac-sha256|hmac-sha512)$",
        description="Signature algorithm",
    )
    include_timestamp: bool = Field(True, description="Include timestamp in signature")
    timestamp_tolerance_seconds: int = Field(
        300, ge=60, le=3600, description="Timestamp validation tolerance"
    )
    ip_whitelist: Optional[List[str]] = Field(
        None, description="Optional IP whitelist for webhook endpoints"
    )


# Export all schemas
__all__ = [
    "WebhookEventType",
    "WebhookSubscriptionRequest",
    "WebhookSubscriptionResponse",
    "WebhookTestRequest",
    "WebhookTestResponse",
    "WebhookEventLog",
    "BaseWebhookPayload",
    "PayrollStartedPayload",
    "PayrollCompletedPayload",
    "PaymentProcessedPayload",
    "TaxRuleUpdatedPayload",
    "ExportCompletedPayload",
    "WebhookRetryPolicy",
    "WebhookSecurityConfig",
]
