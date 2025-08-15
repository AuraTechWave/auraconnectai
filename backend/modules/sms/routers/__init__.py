# backend/modules/sms/routers/__init__.py

from .sms_router import router as sms_router
from .template_router import router as template_router
from .opt_out_router import router as opt_out_router
from .webhook_router import router as webhook_router

__all__ = [
    'sms_router',
    'template_router',
    'opt_out_router',
    'webhook_router'
]