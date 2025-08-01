# backend/modules/feedback/models/feedback_models.py

from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, JSON, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid
import enum

from core.database import Base
from core.mixins import TimestampMixin


# Enums for various feedback and review types
class ReviewType(str, enum.Enum):
    """Types of reviews"""
    PRODUCT = "product"
    SERVICE = "service"
    ORDER = "order"
    DELIVERY = "delivery"
    SUPPORT = "support"
    GENERAL = "general"


class ReviewStatus(str, enum.Enum):
    """Review status for moderation"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FLAGGED = "flagged"
    HIDDEN = "hidden"
    ARCHIVED = "archived"


class FeedbackType(str, enum.Enum):
    """Types of feedback"""
    COMPLAINT = "complaint"
    SUGGESTION = "suggestion"
    COMPLIMENT = "compliment"
    BUG_REPORT = "bug_report"
    FEATURE_REQUEST = "feature_request"
    GENERAL_INQUIRY = "general_inquiry"


class FeedbackStatus(str, enum.Enum):
    """Feedback processing status"""
    NEW = "new"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ESCALATED = "escalated"


class FeedbackPriority(str, enum.Enum):
    """Feedback priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class SentimentScore(str, enum.Enum):
    """Sentiment analysis results"""
    VERY_NEGATIVE = "very_negative"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    VERY_POSITIVE = "very_positive"


class ReviewSource(str, enum.Enum):
    """Source of the review"""
    WEBSITE = "website"
    MOBILE_APP = "mobile_app"
    EMAIL = "email"
    SMS = "sms"
    PHONE = "phone"
    SOCIAL_MEDIA = "social_media"
    THIRD_PARTY = "third_party"


# Database Models
class Review(Base, TimestampMixin):
    """Main review model for products, services, and orders"""
    __tablename__ = "reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True)
    
    # Review identification
    review_type = Column(ENUM(ReviewType), nullable=False, index=True)
    status = Column(ENUM(ReviewStatus), default=ReviewStatus.PENDING, index=True)
    source = Column(ENUM(ReviewSource), default=ReviewSource.WEBSITE, index=True)
    
    # Customer and target information
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    product_id = Column(Integer, nullable=True, index=True)  # References product system
    service_id = Column(Integer, nullable=True, index=True)  # References service system
    
    # Review content
    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    rating = Column(Float, nullable=False, index=True)  # 1.0 to 5.0
    
    # Review metadata
    is_verified_purchase = Column(Boolean, default=False, index=True)
    is_anonymous = Column(Boolean, default=False)
    reviewer_name = Column(String(100), nullable=True)  # Custom name if anonymous
    
    # Moderation and verification
    moderated_at = Column(DateTime, nullable=True)
    moderated_by = Column(Integer, nullable=True)  # Staff user ID
    moderation_notes = Column(Text, nullable=True)
    is_featured = Column(Boolean, default=False, index=True)
    
    # Engagement metrics
    helpful_votes = Column(Integer, default=0)
    not_helpful_votes = Column(Integer, default=0)
    total_votes = Column(Integer, default=0)
    helpful_percentage = Column(Float, default=0.0)
    
    # Sentiment analysis
    sentiment_score = Column(ENUM(SentimentScore), nullable=True, index=True)
    sentiment_confidence = Column(Float, nullable=True)  # 0.0 to 1.0
    sentiment_analysis_data = Column(JSON, nullable=True)
    
    # Additional data
    review_metadata = Column(JSON, nullable=True)  # Flexible metadata storage
    tags = Column(JSON, nullable=True)  # Review tags/categories
    
    # Media attachments
    has_images = Column(Boolean, default=False)
    has_videos = Column(Boolean, default=False)
    media_count = Column(Integer, default=0)
    
    # Response tracking
    has_business_response = Column(Boolean, default=False)
    business_response_at = Column(DateTime, nullable=True)
    
    # Relationships
    customer = relationship("Customer", back_populates="reviews")
    order = relationship("Order", back_populates="reviews")
    media_attachments = relationship("ReviewMedia", back_populates="review", cascade="all, delete-orphan")
    votes = relationship("ReviewVote", back_populates="review", cascade="all, delete-orphan")
    business_responses = relationship("BusinessResponse", back_populates="review", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_review_customer_rating', 'customer_id', 'rating'),
        Index('idx_review_product_status', 'product_id', 'status'),
        Index('idx_review_order_verified', 'order_id', 'is_verified_purchase'),
        Index('idx_review_sentiment_rating', 'sentiment_score', 'rating'),
        Index('idx_review_created_rating', 'created_at', 'rating'),
    )


class ReviewMedia(Base, TimestampMixin):
    """Media attachments for reviews (images, videos)"""
    __tablename__ = "review_media"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True)
    
    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False, index=True)
    
    # Media information
    media_type = Column(String(50), nullable=False)  # image, video
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=True)  # Size in bytes
    mime_type = Column(String(100), nullable=True)
    
    # Media metadata
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    duration = Column(Integer, nullable=True)  # For videos, in seconds
    
    # Processing status
    is_processed = Column(Boolean, default=False)
    is_approved = Column(Boolean, default=True)
    processing_metadata = Column(JSON, nullable=True)
    
    # Relationships
    review = relationship("Review", back_populates="media_attachments")


class ReviewVote(Base, TimestampMixin):
    """Customer votes on review helpfulness"""
    __tablename__ = "review_votes"
    
    id = Column(Integer, primary_key=True, index=True)
    
    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    
    is_helpful = Column(Boolean, nullable=False)  # True = helpful, False = not helpful
    
    # Relationships
    review = relationship("Review", back_populates="votes")
    customer = relationship("Customer")
    
    # Ensure one vote per customer per review
    __table_args__ = (
        Index('idx_unique_review_vote', 'review_id', 'customer_id', unique=True),
    )


class BusinessResponse(Base, TimestampMixin):
    """Business responses to customer reviews"""
    __tablename__ = "business_responses"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True)
    
    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False, index=True)
    
    # Response content
    content = Column(Text, nullable=False)
    responder_name = Column(String(100), nullable=False)
    responder_title = Column(String(100), nullable=True)
    responder_id = Column(Integer, nullable=True)  # Staff user ID
    
    # Response metadata
    is_published = Column(Boolean, default=True)
    response_metadata = Column(JSON, nullable=True)
    
    # Relationships
    review = relationship("Review", back_populates="business_responses")


class Feedback(Base, TimestampMixin):
    """Customer feedback collection system"""
    __tablename__ = "feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True)
    
    # Feedback identification
    feedback_type = Column(ENUM(FeedbackType), nullable=False, index=True)
    status = Column(ENUM(FeedbackStatus), default=FeedbackStatus.NEW, index=True)
    priority = Column(ENUM(FeedbackPriority), default=FeedbackPriority.MEDIUM, index=True)
    source = Column(ENUM(ReviewSource), default=ReviewSource.WEBSITE, index=True)
    
    # Customer information
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)  # Can be anonymous
    customer_email = Column(String(255), nullable=True)
    customer_name = Column(String(100), nullable=True)
    customer_phone = Column(String(20), nullable=True)
    
    # Related entities
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    product_id = Column(Integer, nullable=True, index=True)
    
    # Feedback content
    subject = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    category = Column(String(100), nullable=True, index=True)
    subcategory = Column(String(100), nullable=True)
    
    # Processing information
    assigned_to = Column(Integer, nullable=True)  # Staff user ID
    assigned_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    
    # Sentiment analysis
    sentiment_score = Column(ENUM(SentimentScore), nullable=True, index=True)
    sentiment_confidence = Column(Float, nullable=True)
    sentiment_analysis_data = Column(JSON, nullable=True)
    
    # Tracking
    follow_up_required = Column(Boolean, default=False)
    follow_up_date = Column(DateTime, nullable=True)
    escalated_at = Column(DateTime, nullable=True)
    escalated_to = Column(Integer, nullable=True)
    
    # Additional data
    response_metadata = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)
    
    # Relationships
    customer = relationship("Customer", back_populates="feedback")
    order = relationship("Order", back_populates="feedback")
    responses = relationship("FeedbackResponse", back_populates="feedback", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_feedback_customer_status', 'customer_id', 'status'),
        Index('idx_feedback_type_priority', 'feedback_type', 'priority'),
        Index('idx_feedback_assigned_status', 'assigned_to', 'status'),
        Index('idx_feedback_created_priority', 'created_at', 'priority'),
    )


class FeedbackResponse(Base, TimestampMixin):
    """Responses to customer feedback"""
    __tablename__ = "feedback_responses"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True)
    
    feedback_id = Column(Integer, ForeignKey("feedback.id"), nullable=False, index=True)
    
    # Response content
    message = Column(Text, nullable=False)
    responder_id = Column(Integer, nullable=False)  # Staff user ID
    responder_name = Column(String(100), nullable=False)
    
    # Response type
    is_internal = Column(Boolean, default=False)  # Internal note vs customer response
    is_resolution = Column(Boolean, default=False)  # Marks feedback as resolved
    
    # Metadata
    response_metadata = Column(JSON, nullable=True)
    
    # Relationships
    feedback = relationship("Feedback", back_populates="responses")


class ReviewTemplate(Base, TimestampMixin):
    """Templates for review requests and forms"""
    __tablename__ = "review_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True)
    
    # Template identification
    name = Column(String(255), nullable=False)
    review_type = Column(ENUM(ReviewType), nullable=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    
    # Template content
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    custom_questions = Column(JSON, nullable=True)  # Additional questions
    rating_labels = Column(JSON, nullable=True)  # Custom rating labels
    
    # Template settings
    requires_purchase = Column(Boolean, default=False)
    allows_anonymous = Column(Boolean, default=True)
    allows_media = Column(Boolean, default=True)
    max_media_files = Column(Integer, default=5)
    
    # Automation settings
    auto_request_after_days = Column(Integer, nullable=True)
    reminder_enabled = Column(Boolean, default=False)
    reminder_days = Column(Integer, default=7)
    
    # Metadata
    response_metadata = Column(JSON, nullable=True)


class ReviewAggregate(Base, TimestampMixin):
    """Aggregated review statistics for products/services"""
    __tablename__ = "review_aggregates"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Target entity
    entity_type = Column(String(50), nullable=False, index=True)  # product, service, etc.
    entity_id = Column(Integer, nullable=False, index=True)
    
    # Aggregate statistics
    total_reviews = Column(Integer, default=0)
    average_rating = Column(Float, default=0.0)
    rating_distribution = Column(JSON, nullable=True)  # {1: count, 2: count, ...}
    
    # Rating counts by score
    rating_1_count = Column(Integer, default=0)
    rating_2_count = Column(Integer, default=0)
    rating_3_count = Column(Integer, default=0)
    rating_4_count = Column(Integer, default=0)
    rating_5_count = Column(Integer, default=0)
    
    # Additional metrics
    verified_reviews_count = Column(Integer, default=0)
    featured_reviews_count = Column(Integer, default=0)
    with_media_count = Column(Integer, default=0)
    
    # Sentiment distribution
    sentiment_distribution = Column(JSON, nullable=True)
    positive_sentiment_percentage = Column(Float, default=0.0)
    
    # Last update tracking
    last_calculated_at = Column(DateTime, default=func.now())
    
    # Unique constraint on entity
    __table_args__ = (
        Index('idx_unique_aggregate', 'entity_type', 'entity_id', unique=True),
        Index('idx_aggregate_rating', 'entity_type', 'average_rating'),
    )


class FeedbackCategory(Base, TimestampMixin):
    """Categories for organizing feedback"""
    __tablename__ = "feedback_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Category information
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    parent_id = Column(Integer, ForeignKey("feedback_categories.id"), nullable=True)
    
    # Category settings
    is_active = Column(Boolean, default=True, index=True)
    sort_order = Column(Integer, default=0)
    auto_assign_keywords = Column(JSON, nullable=True)  # Keywords for auto-categorization
    
    # Escalation rules
    auto_escalate = Column(Boolean, default=False)
    escalation_priority = Column(ENUM(FeedbackPriority), nullable=True)
    escalation_conditions = Column(JSON, nullable=True)
    
    # Relationships
    parent = relationship("FeedbackCategory", remote_side=[id])
    children = relationship("FeedbackCategory")


class ReviewInvitation(Base, TimestampMixin):
    """Track review invitations sent to customers"""
    __tablename__ = "review_invitations"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True)
    
    # Invitation details
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    product_id = Column(Integer, nullable=True, index=True)
    template_id = Column(Integer, ForeignKey("review_templates.id"), nullable=True)
    
    # Invitation tracking
    sent_at = Column(DateTime, default=func.now())
    delivery_method = Column(String(50), nullable=False)  # email, sms, push
    
    # Response tracking
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    review_submitted_at = Column(DateTime, nullable=True)
    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=True)
    
    # Reminder tracking
    reminder_sent_count = Column(Integer, default=0)
    last_reminder_sent = Column(DateTime, nullable=True)
    
    # Status
    is_completed = Column(Boolean, default=False, index=True)
    is_expired = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=True)
    
    # Metadata
    response_metadata = Column(JSON, nullable=True)
    
    # Relationships
    customer = relationship("Customer")
    order = relationship("Order")
    template = relationship("ReviewTemplate")
    review = relationship("Review")
    
    # Indexes
    __table_args__ = (
        Index('idx_invitation_customer_sent', 'customer_id', 'sent_at'),
        Index('idx_invitation_order_completed', 'order_id', 'is_completed'),
    )