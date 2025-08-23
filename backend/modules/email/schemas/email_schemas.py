# backend/modules/email/schemas/email_schemas.py

from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from modules.email.models.email_models import (
    EmailProvider, EmailStatus, EmailTemplateCategory
)


class EmailAttachmentInfo(BaseModel):
    """Schema for email attachment"""
    filename: str
    content_type: str
    content_base64: str
    content_id: Optional[str] = None


class EmailSendRequest(BaseModel):
    """Request schema for sending an email"""
    to_email: EmailStr
    to_name: Optional[str] = None
    cc_emails: Optional[List[EmailStr]] = None
    bcc_emails: Optional[List[EmailStr]] = None
    reply_to_email: Optional[EmailStr] = None
    
    # Content (either direct or template)
    subject: Optional[str] = None
    html_body: Optional[str] = None
    text_body: Optional[str] = None
    
    # Template option
    template_id: Optional[int] = None
    template_variables: Optional[Dict[str, Any]] = None
    
    # Associations
    customer_id: Optional[int] = None
    order_id: Optional[int] = None
    reservation_id: Optional[int] = None
    
    # Options
    schedule_at: Optional[datetime] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    attachments: Optional[List[EmailAttachmentInfo]] = None
    
    model_config = ConfigDict(from_attributes=True)


class EmailBulkSendRequest(BaseModel):
    """Request schema for sending bulk emails"""
    recipients: List[EmailSendRequest]
    provider: Optional[EmailProvider] = EmailProvider.SENDGRID
    
    model_config = ConfigDict(from_attributes=True)


class EmailMessageResponse(BaseModel):
    """Response schema for email message"""
    id: int
    provider: EmailProvider
    status: EmailStatus
    from_email: str
    from_name: Optional[str]
    to_email: str
    to_name: Optional[str]
    subject: str
    
    provider_message_id: Optional[str]
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    opened_at: Optional[datetime]
    clicked_at: Optional[datetime]
    
    customer_id: Optional[int]
    order_id: Optional[int]
    reservation_id: Optional[int]
    
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class EmailTemplateCreate(BaseModel):
    """Schema for creating email template"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: EmailTemplateCategory
    
    subject_template: str = Field(..., min_length=1, max_length=500)
    html_body_template: str = Field(..., min_length=1)
    text_body_template: Optional[str] = None
    
    sendgrid_template_id: Optional[str] = None
    ses_template_name: Optional[str] = None
    
    variables: Optional[List[str]] = None
    default_values: Optional[Dict[str, Any]] = None
    
    is_active: bool = True
    is_transactional: bool = True
    
    model_config = ConfigDict(from_attributes=True)


class EmailTemplateUpdate(BaseModel):
    """Schema for updating email template"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[EmailTemplateCategory] = None
    
    subject_template: Optional[str] = Field(None, min_length=1, max_length=500)
    html_body_template: Optional[str] = Field(None, min_length=1)
    text_body_template: Optional[str] = None
    
    sendgrid_template_id: Optional[str] = None
    ses_template_name: Optional[str] = None
    
    variables: Optional[List[str]] = None
    default_values: Optional[Dict[str, Any]] = None
    
    is_active: Optional[bool] = None
    is_transactional: Optional[bool] = None
    
    model_config = ConfigDict(from_attributes=True)


class EmailTemplateResponse(BaseModel):
    """Response schema for email template"""
    id: int
    name: str
    description: Optional[str]
    category: EmailTemplateCategory
    
    subject_template: str
    html_body_template: str
    text_body_template: Optional[str]
    
    sendgrid_template_id: Optional[str]
    ses_template_name: Optional[str]
    
    variables: Optional[List[str]]
    default_values: Optional[Dict[str, Any]]
    
    is_active: bool
    is_transactional: bool
    
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class EmailStatusUpdate(BaseModel):
    """Schema for updating email status (webhook)"""
    provider_message_id: str
    status: EmailStatus
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    bounced_at: Optional[datetime] = None
    complained_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    provider_response: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(from_attributes=True)


class EmailUnsubscribeRequest(BaseModel):
    """Schema for unsubscribe request"""
    email: EmailStr
    unsubscribe_all: bool = False
    categories: Optional[List[EmailTemplateCategory]] = None
    reason: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class EmailStatistics(BaseModel):
    """Schema for email statistics"""
    total_emails: int
    sent: int
    delivered: int
    opened: int
    clicked: int
    bounced: int
    complained: int
    failed: int
    
    delivery_rate: float
    open_rate: float
    click_rate: float
    bounce_rate: float
    complaint_rate: float
    
    by_status: Dict[str, int]
    by_category: Dict[str, int]
    
    model_config = ConfigDict(from_attributes=True)