# backend/modules/insights/__init__.py

"""
Insights module for business intelligence and analytics.
"""

from .routes.insights_routes import router as insights_router
from .models.insight_models import (
    Insight, InsightRating, InsightAction, 
    InsightNotificationRule, InsightThread
)
from .services.insights_service import InsightsService
from .services.notification_service import InsightNotificationService
from .services.rating_service import InsightRatingService
from .services.thread_service import InsightThreadService

__all__ = [
    "insights_router",
    "Insight",
    "InsightRating", 
    "InsightAction",
    "InsightNotificationRule",
    "InsightThread",
    "InsightsService",
    "InsightNotificationService",
    "InsightRatingService",
    "InsightThreadService"
]