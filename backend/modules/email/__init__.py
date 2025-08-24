# backend/modules/email/__init__.py

from .routers import email_router
from .services import (
    EmailService,
    EmailTemplateService,
    UnsubscribeService,
    EmailTrackingService
)
from .models import (
    EmailMessage,
    EmailTemplate,
    EmailProvider,
    EmailStatus,
    EmailTemplateCategory
)

__all__ = [
    "email_router",
    "EmailService",
    "EmailTemplateService",
    "UnsubscribeService",
    "EmailTrackingService",
    "EmailMessage",
    "EmailTemplate",
    "EmailProvider",
    "EmailStatus",
    "EmailTemplateCategory"
]