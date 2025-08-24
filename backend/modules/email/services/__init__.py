# backend/modules/email/services/__init__.py

from .email_service import EmailService
from .sendgrid_service import SendGridService
from .ses_service import SESService
from .template_service import EmailTemplateService
from .unsubscribe_service import UnsubscribeService
from .tracking_service import EmailTrackingService

__all__ = [
    "EmailService",
    "SendGridService",
    "SESService",
    "EmailTemplateService",
    "UnsubscribeService",
    "EmailTrackingService"
]