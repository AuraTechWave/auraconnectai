# backend/modules/feedback/schemas/feedback_schemas.py

from pydantic import BaseModel, Field, validator, EmailStr, field_validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum

from modules.feedback.models.feedback_models import (
    ReviewType,
    ReviewStatus,
    FeedbackType,
    FeedbackStatus,
    FeedbackPriority,
    SentimentScore,
    ReviewSource,
)


# Base schemas
class ReviewBase(BaseModel):
    """Base review schema"""

    review_type: ReviewType
    title: Optional[str] = Field(None, max_length=255)
    content: str = Field(..., min_length=10, max_length=5000)
    rating: float = Field(..., ge=1.0, le=5.0)
    is_anonymous: bool = False
    reviewer_name: Optional[str] = Field(None, max_length=100)
    product_id: Optional[int] = None
    service_id: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class ReviewCreate(ReviewBase):
    """Schema for creating a review"""

    customer_id: int
    order_id: Optional[int] = None
    source: ReviewSource = ReviewSource.WEBSITE

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v):
        # Round to nearest 0.5
        return round(v * 2) / 2

    @field_validator("content")
    @classmethod
    def validate_content(cls, v):
        if len(v.strip()) < 10:
            raise ValueError("Review content must be at least 10 characters")
        return v.strip()


class ReviewUpdate(BaseModel):
    """Schema for updating a review"""

    title: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = Field(None, min_length=10, max_length=5000)
    rating: Optional[float] = Field(None, ge=1.0, le=5.0)
    is_anonymous: Optional[bool] = None
    reviewer_name: Optional[str] = Field(None, max_length=100)
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class ReviewModeration(BaseModel):
    """Schema for review moderation"""

    status: ReviewStatus
    moderation_notes: Optional[str] = Field(None, max_length=1000)
    is_featured: Optional[bool] = False


class ReviewResponse(BaseModel):
    """Schema for review responses"""

    id: int
    uuid: str
    review_type: ReviewType
    status: ReviewStatus
    source: ReviewSource
    customer_id: int
    order_id: Optional[int]
    product_id: Optional[int]
    service_id: Optional[int]
    title: Optional[str]
    content: str
    rating: float
    is_verified_purchase: bool
    is_anonymous: bool
    reviewer_name: Optional[str]
    helpful_votes: int
    not_helpful_votes: int
    total_votes: int
    helpful_percentage: float
    sentiment_score: Optional[SentimentScore]
    sentiment_confidence: Optional[float]
    is_featured: bool
    has_images: bool
    has_videos: bool
    media_count: int
    has_business_response: bool
    business_response_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReviewSummary(BaseModel):
    """Summary schema for review listings"""

    id: int
    uuid: str
    review_type: ReviewType
    status: ReviewStatus
    title: Optional[str]
    rating: float
    customer_id: int
    product_id: Optional[int]
    is_verified_purchase: bool
    helpful_votes: int
    sentiment_score: Optional[SentimentScore]
    created_at: datetime

    class Config:
        from_attributes = True


# Business Response schemas
class BusinessResponseCreate(BaseModel):
    """Schema for creating business responses"""

    content: str = Field(..., min_length=10, max_length=2000)
    responder_name: str = Field(..., max_length=100)
    responder_title: Optional[str] = Field(None, max_length=100)
    responder_id: Optional[int] = None
    is_published: bool = True
    metadata: Optional[Dict[str, Any]] = None


class BusinessResponseResponse(BaseModel):
    """Schema for business response responses"""

    id: int
    uuid: str
    review_id: int
    content: str
    responder_name: str
    responder_title: Optional[str]
    is_published: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Review Media schemas
class ReviewMediaCreate(BaseModel):
    """Schema for review media creation"""

    media_type: str = Field(..., pattern="^(image|video)$")
    file_path: str
    file_name: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[int] = None


class ReviewMediaResponse(BaseModel):
    """Schema for review media responses"""

    id: int
    uuid: str
    review_id: int
    media_type: str
    file_path: str
    file_name: str
    file_size: Optional[int]
    mime_type: Optional[str]
    width: Optional[int]
    height: Optional[int]
    duration: Optional[int]
    is_processed: bool
    is_approved: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Review Vote schemas
class ReviewVoteCreate(BaseModel):
    """Schema for voting on review helpfulness"""

    is_helpful: bool


class ReviewVoteResponse(BaseModel):
    """Schema for review vote responses"""

    id: int
    review_id: int
    customer_id: int
    is_helpful: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Feedback schemas
class FeedbackBase(BaseModel):
    """Base feedback schema"""

    feedback_type: FeedbackType
    subject: str = Field(..., min_length=5, max_length=255)
    message: str = Field(..., min_length=10, max_length=5000)
    category: Optional[str] = Field(None, max_length=100)
    subcategory: Optional[str] = Field(None, max_length=100)
    priority: FeedbackPriority = FeedbackPriority.MEDIUM
    source: ReviewSource = ReviewSource.WEBSITE
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class FeedbackCreate(FeedbackBase):
    """Schema for creating feedback"""

    customer_id: Optional[int] = None
    customer_email: Optional[EmailStr] = None
    customer_name: Optional[str] = Field(None, max_length=100)
    customer_phone: Optional[str] = Field(None, max_length=20)
    order_id: Optional[int] = None
    product_id: Optional[int] = None

    @field_validator("customer_email")
    @classmethod
    def validate_customer_info(cls, v, values):
        # Either customer_id or customer_email must be provided
        if not v and not values.get("customer_id"):
            raise ValueError("Either customer_id or customer_email must be provided")
        return v


class FeedbackUpdate(BaseModel):
    """Schema for updating feedback"""

    subject: Optional[str] = Field(None, min_length=5, max_length=255)
    message: Optional[str] = Field(None, min_length=10, max_length=5000)
    category: Optional[str] = Field(None, max_length=100)
    subcategory: Optional[str] = Field(None, max_length=100)
    priority: Optional[FeedbackPriority] = None
    status: Optional[FeedbackStatus] = None
    assigned_to: Optional[int] = None
    follow_up_required: Optional[bool] = None
    follow_up_date: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class FeedbackResponse(BaseModel):
    """Schema for feedback responses"""

    id: int
    uuid: str
    feedback_type: FeedbackType
    status: FeedbackStatus
    priority: FeedbackPriority
    source: ReviewSource
    customer_id: Optional[int]
    customer_email: Optional[str]
    customer_name: Optional[str]
    customer_phone: Optional[str]
    order_id: Optional[int]
    product_id: Optional[int]
    subject: str
    message: str
    category: Optional[str]
    subcategory: Optional[str]
    assigned_to: Optional[int]
    assigned_at: Optional[datetime]
    resolved_at: Optional[datetime]
    resolution_notes: Optional[str]
    sentiment_score: Optional[SentimentScore]
    sentiment_confidence: Optional[float]
    follow_up_required: bool
    follow_up_date: Optional[datetime]
    escalated_at: Optional[datetime]
    escalated_to: Optional[int]
    tags: Optional[List[str]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FeedbackSummary(BaseModel):
    """Summary schema for feedback listings"""

    id: int
    uuid: str
    feedback_type: FeedbackType
    status: FeedbackStatus
    priority: FeedbackPriority
    subject: str
    customer_id: Optional[int]
    customer_name: Optional[str]
    assigned_to: Optional[int]
    sentiment_score: Optional[SentimentScore]
    created_at: datetime

    class Config:
        from_attributes = True


# Feedback Response schemas
class FeedbackResponseCreate(BaseModel):
    """Schema for creating feedback responses"""

    message: str = Field(..., min_length=5, max_length=2000)
    responder_id: int
    responder_name: str = Field(..., max_length=100)
    is_internal: bool = False
    is_resolution: bool = False
    metadata: Optional[Dict[str, Any]] = None


class FeedbackResponseResponse(BaseModel):
    """Schema for feedback response responses"""

    id: int
    uuid: str
    feedback_id: int
    message: str
    responder_id: int
    responder_name: str
    is_internal: bool
    is_resolution: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Review Template schemas
class ReviewTemplateCreate(BaseModel):
    """Schema for creating review templates"""

    name: str = Field(..., max_length=255)
    review_type: ReviewType
    title: str = Field(..., max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    custom_questions: Optional[List[Dict[str, Any]]] = None
    rating_labels: Optional[Dict[str, str]] = None
    requires_purchase: bool = False
    allows_anonymous: bool = True
    allows_media: bool = True
    max_media_files: int = Field(5, ge=0, le=20)
    auto_request_after_days: Optional[int] = Field(None, ge=0, le=365)
    reminder_enabled: bool = False
    reminder_days: int = Field(7, ge=1, le=90)
    metadata: Optional[Dict[str, Any]] = None


class ReviewTemplateUpdate(BaseModel):
    """Schema for updating review templates"""

    name: Optional[str] = Field(None, max_length=255)
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    custom_questions: Optional[List[Dict[str, Any]]] = None
    rating_labels: Optional[Dict[str, str]] = None
    requires_purchase: Optional[bool] = None
    allows_anonymous: Optional[bool] = None
    allows_media: Optional[bool] = None
    max_media_files: Optional[int] = Field(None, ge=0, le=20)
    auto_request_after_days: Optional[int] = Field(None, ge=0, le=365)
    reminder_enabled: Optional[bool] = None
    reminder_days: Optional[int] = Field(None, ge=1, le=90)
    is_active: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


class ReviewTemplateResponse(BaseModel):
    """Schema for review template responses"""

    id: int
    uuid: str
    name: str
    review_type: ReviewType
    is_active: bool
    title: str
    description: Optional[str]
    custom_questions: Optional[List[Dict[str, Any]]]
    rating_labels: Optional[Dict[str, str]]
    requires_purchase: bool
    allows_anonymous: bool
    allows_media: bool
    max_media_files: int
    auto_request_after_days: Optional[int]
    reminder_enabled: bool
    reminder_days: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Review Aggregate schemas
class ReviewAggregateResponse(BaseModel):
    """Schema for review aggregate responses"""

    id: int
    entity_type: str
    entity_id: int
    total_reviews: int
    average_rating: float
    rating_distribution: Optional[Dict[str, int]]
    rating_1_count: int
    rating_2_count: int
    rating_3_count: int
    rating_4_count: int
    rating_5_count: int
    verified_reviews_count: int
    featured_reviews_count: int
    with_media_count: int
    sentiment_distribution: Optional[Dict[str, int]]
    positive_sentiment_percentage: float
    last_calculated_at: datetime

    class Config:
        from_attributes = True


# Feedback Category schemas
class FeedbackCategoryCreate(BaseModel):
    """Schema for creating feedback categories"""

    name: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    parent_id: Optional[int] = None
    sort_order: int = 0
    auto_assign_keywords: Optional[List[str]] = None
    auto_escalate: bool = False
    escalation_priority: Optional[FeedbackPriority] = None
    escalation_conditions: Optional[Dict[str, Any]] = None


class FeedbackCategoryUpdate(BaseModel):
    """Schema for updating feedback categories"""

    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    parent_id: Optional[int] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None
    auto_assign_keywords: Optional[List[str]] = None
    auto_escalate: Optional[bool] = None
    escalation_priority: Optional[FeedbackPriority] = None
    escalation_conditions: Optional[Dict[str, Any]] = None


class FeedbackCategoryResponse(BaseModel):
    """Schema for feedback category responses"""

    id: int
    name: str
    description: Optional[str]
    parent_id: Optional[int]
    is_active: bool
    sort_order: int
    auto_assign_keywords: Optional[List[str]]
    auto_escalate: bool
    escalation_priority: Optional[FeedbackPriority]
    escalation_conditions: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Review Invitation schemas
class ReviewInvitationCreate(BaseModel):
    """Schema for creating review invitations"""

    customer_id: int
    order_id: Optional[int] = None
    product_id: Optional[int] = None
    template_id: Optional[int] = None
    delivery_method: str = Field(..., pattern="^(email|sms|push)$")
    expires_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class ReviewInvitationResponse(BaseModel):
    """Schema for review invitation responses"""

    id: int
    uuid: str
    customer_id: int
    order_id: Optional[int]
    product_id: Optional[int]
    template_id: Optional[int]
    sent_at: datetime
    delivery_method: str
    opened_at: Optional[datetime]
    clicked_at: Optional[datetime]
    review_submitted_at: Optional[datetime]
    review_id: Optional[int]
    reminder_sent_count: int
    last_reminder_sent: Optional[datetime]
    is_completed: bool
    is_expired: bool
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# Analytics schemas
class ReviewAnalytics(BaseModel):
    """Schema for review analytics"""

    total_reviews: int
    average_rating: float
    rating_distribution: Dict[str, int]
    sentiment_distribution: Dict[str, int]
    review_trends: List[Dict[str, Any]]
    top_keywords: List[Dict[str, Any]]
    response_rate: float
    verification_rate: float


class FeedbackAnalytics(BaseModel):
    """Schema for feedback analytics"""

    total_feedback: int
    feedback_by_type: Dict[str, int]
    feedback_by_status: Dict[str, int]
    feedback_by_priority: Dict[str, int]
    sentiment_distribution: Dict[str, int]
    resolution_time_avg: float
    escalation_rate: float
    feedback_trends: List[Dict[str, Any]]


# Search and filter schemas
class ReviewFilters(BaseModel):
    """Schema for review filtering"""

    review_type: Optional[ReviewType] = None
    status: Optional[ReviewStatus] = None
    rating_min: Optional[float] = Field(None, ge=1.0, le=5.0)
    rating_max: Optional[float] = Field(None, ge=1.0, le=5.0)
    verified_only: Optional[bool] = None
    with_media: Optional[bool] = None
    sentiment: Optional[SentimentScore] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    customer_id: Optional[int] = None
    product_id: Optional[int] = None
    order_id: Optional[int] = None
    tags: Optional[List[str]] = None


class FeedbackFilters(BaseModel):
    """Schema for feedback filtering"""

    feedback_type: Optional[FeedbackType] = None
    status: Optional[FeedbackStatus] = None
    priority: Optional[FeedbackPriority] = None
    category: Optional[str] = None
    assigned_to: Optional[int] = None
    customer_id: Optional[int] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    sentiment: Optional[SentimentScore] = None
    follow_up_required: Optional[bool] = None
    tags: Optional[List[str]] = None


# Pagination schemas
class PaginatedResponse(BaseModel):
    """Base schema for paginated responses"""

    items: List[Any]
    total: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool


class ReviewListResponse(PaginatedResponse):
    """Schema for paginated review responses"""

    items: List[ReviewSummary]


class FeedbackListResponse(PaginatedResponse):
    """Schema for paginated feedback responses"""

    items: List[FeedbackSummary]
