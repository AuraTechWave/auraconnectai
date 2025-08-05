# backend/modules/ai_recommendations/models/feedback_models.py

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from core.database import Base
from core.mixins import TimestampMixin
from datetime import datetime
from enum import Enum


class FeedbackType(str, Enum):
    """Types of feedback for AI suggestions"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    
    
class FeedbackStatus(str, Enum):
    """Status of feedback processing"""
    PENDING = "pending"
    PROCESSED = "processed"
    IGNORED = "ignored"


class SuggestionFeedback(Base, TimestampMixin):
    """Model for tracking feedback on AI-generated suggestions"""
    __tablename__ = "suggestion_feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Reference to the suggestion
    suggestion_id = Column(String, nullable=False, index=True)
    suggestion_type = Column(String, nullable=False)  # menu_item, staff_schedule, etc.
    
    # User who provided feedback
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    user_role = Column(String, nullable=True)
    
    # Feedback details
    feedback_type = Column(SQLEnum(FeedbackType), nullable=False)
    feedback_score = Column(Float, nullable=True)  # 1-5 rating
    feedback_text = Column(Text, nullable=True)
    
    # Context when feedback was given
    context_data = Column(JSONB, nullable=True)
    
    # Processing status
    status = Column(SQLEnum(FeedbackStatus), default=FeedbackStatus.PENDING)
    processed_at = Column(DateTime, nullable=True)
    
    # Impact tracking
    was_helpful = Column(Boolean, nullable=True)
    led_to_action = Column(Boolean, default=False)
    action_taken = Column(String, nullable=True)
    
    # Metadata
    model_version = Column(String, nullable=True)
    confidence_score = Column(Float, nullable=True)
    
    # Relations
    user = relationship("User", backref="suggestion_feedbacks")