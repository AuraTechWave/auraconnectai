# backend/modules/ai_recommendations/models/__init__.py

from .feedback_models import (
    SuggestionFeedback,
    FeedbackType,
    FeedbackStatus
)

from .suggestion_models import (
    AISuggestion,
    SuggestionType,
    SuggestionStatus
)

__all__ = [
    "SuggestionFeedback",
    "FeedbackType", 
    "FeedbackStatus",
    "AISuggestion",
    "SuggestionType",
    "SuggestionStatus"
]