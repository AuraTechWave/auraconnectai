# backend/modules/ai_recommendations/models/suggestion_models.py

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Boolean,
    Float,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from core.database import Base
from core.mixins import TimestampMixin
from datetime import datetime
from enum import Enum


class SuggestionType(str, Enum):
    """Types of AI suggestions"""

    MENU_ITEM = "menu_item"
    STAFF_SCHEDULE = "staff_schedule"
    PROMOTION = "promotion"
    INVENTORY = "inventory"
    CUSTOMER_ENGAGEMENT = "customer_engagement"
    OPERATIONAL = "operational"


class SuggestionStatus(str, Enum):
    """Status of AI suggestions"""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"
    EXPIRED = "expired"


class AISuggestion(Base, TimestampMixin):
    """Model for AI-generated suggestions"""

    __tablename__ = "ai_suggestions"

    id = Column(Integer, primary_key=True, index=True)

    # Type and category
    suggestion_type = Column(SQLEnum(SuggestionType), nullable=False, index=True)
    category = Column(String, nullable=True)

    # Suggestion details
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    reasoning = Column(Text, nullable=True)

    # Target entity
    target_entity_type = Column(String, nullable=True)  # menu_item, staff, etc.
    target_entity_id = Column(Integer, nullable=True)

    # Suggestion data
    suggestion_data = Column(JSONB, nullable=False)
    suggestion_metadata = Column(JSONB, nullable=True)

    # AI model info
    model_name = Column(String, nullable=True)
    model_version = Column(String, nullable=True)
    confidence_score = Column(Float, nullable=True)

    # Status and tracking
    status = Column(
        SQLEnum(SuggestionStatus), default=SuggestionStatus.PENDING, index=True
    )
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    implemented_at = Column(DateTime, nullable=True)

    # Impact metrics
    estimated_impact = Column(JSONB, nullable=True)
    actual_impact = Column(JSONB, nullable=True)

    # Validity
    valid_from = Column(DateTime, default=datetime.utcnow)
    valid_until = Column(DateTime, nullable=True)

    # Relations
    reviewer = relationship("User", backref="reviewed_suggestions")
    feedbacks = relationship(
        "SuggestionFeedback",
        backref="suggestion",
        foreign_keys="[SuggestionFeedback.suggestion_id]",
        primaryjoin="AISuggestion.id==foreign(SuggestionFeedback.suggestion_id)",
    )
