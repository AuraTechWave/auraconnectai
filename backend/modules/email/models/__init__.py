# backend/modules/email/models/__init__.py

from .email_models import (
    EmailMessage,
    EmailTemplate,
    EmailProvider,
    EmailStatus,
    EmailDirection,
    EmailTemplateCategory,
    EmailAttachment,
    EmailUnsubscribe,
    EmailBounce
)

__all__ = [
    "EmailMessage",
    "EmailTemplate",
    "EmailProvider",
    "EmailStatus",
    "EmailDirection",
    "EmailTemplateCategory",
    "EmailAttachment",
    "EmailUnsubscribe",
    "EmailBounce"
]