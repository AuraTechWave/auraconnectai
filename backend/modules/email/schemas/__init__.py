# backend/modules/email/schemas/__init__.py

from .email_schemas import (
    EmailSendRequest,
    EmailBulkSendRequest,
    EmailMessageResponse,
    EmailTemplateCreate,
    EmailTemplateUpdate,
    EmailTemplateResponse,
    EmailStatusUpdate,
    EmailUnsubscribeRequest,
    EmailStatistics,
    EmailAttachmentInfo
)

__all__ = [
    "EmailSendRequest",
    "EmailBulkSendRequest",
    "EmailMessageResponse",
    "EmailTemplateCreate",
    "EmailTemplateUpdate", 
    "EmailTemplateResponse",
    "EmailStatusUpdate",
    "EmailUnsubscribeRequest",
    "EmailStatistics",
    "EmailAttachmentInfo"
]