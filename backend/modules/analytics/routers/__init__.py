# backend/modules/analytics/routers/__init__.py

from .analytics_router import router as analytics_router
from .realtime_router import router as realtime_router
from .ai_chat_router import router as ai_chat_router
from .predictive import predictive_router

__all__ = ["analytics_router", "realtime_router", "ai_chat_router", "predictive_router"]