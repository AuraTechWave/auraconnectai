# backend/modules/feedback/tests/conftest.py

import pytest
import asyncio
from typing import Generator, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient
import uuid

from backend.core.database import Base, get_db
from backend.modules.feedback.models.feedback_models import (
    Review, Feedback, ReviewAggregate, ReviewTemplate, ReviewInvitation,
    ReviewMedia, ReviewVote, BusinessResponse, FeedbackResponse,
    FeedbackCategory, ReviewStatus, FeedbackStatus, ReviewType,
    FeedbackType, FeedbackPriority, SentimentScore, ReviewSource
)
from backend.modules.feedback.services.review_service import ReviewService
from backend.modules.feedback.services.feedback_service import FeedbackService
from backend.modules.feedback.services.sentiment_service import SentimentAnalysisService
from backend.modules.feedback.services.moderation_service import ContentModerationService
from backend.modules.feedback.services.aggregation_service import ReviewAggregationService
from backend.modules.feedback.services.analytics_service import FeedbackAnalyticsService
from backend.modules.feedback.services.notification_service import NotificationService


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_feedback.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def create_test_database():
    """Create test database tables."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Create a test database session."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def override_get_db(db_session: Session):
    """Override the get_db dependency for testing."""
    def _override_get_db():
        yield db_session
    
    return _override_get_db


@pytest.fixture
def client(override_get_db):
    """Create a test client."""
    from backend.main import app
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


# Service fixtures
@pytest.fixture
def review_service(db_session: Session) -> ReviewService:
    """Create a review service instance."""
    return ReviewService(db_session)


@pytest.fixture
def feedback_service(db_session: Session) -> FeedbackService:
    """Create a feedback service instance."""
    return FeedbackService(db_session)


@pytest.fixture
def sentiment_service() -> SentimentAnalysisService:
    """Create a sentiment analysis service instance."""
    return SentimentAnalysisService()


@pytest.fixture
def moderation_service(db_session: Session) -> ContentModerationService:
    """Create a moderation service instance."""
    return ContentModerationService(db_session)


@pytest.fixture
def aggregation_service(db_session: Session) -> ReviewAggregationService:
    """Create an aggregation service instance."""
    return ReviewAggregationService(db_session)


@pytest.fixture
def analytics_service(db_session: Session) -> FeedbackAnalyticsService:
    """Create an analytics service instance."""
    return FeedbackAnalyticsService(db_session)


@pytest.fixture
def notification_service(db_session: Session) -> NotificationService:
    """Create a notification service instance."""
    return NotificationService(db_session)


# Mock data fixtures
@pytest.fixture
def sample_customer() -> Dict[str, Any]:
    """Sample customer data."""
    return {
        "id": 1,
        "name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "+1234567890"
    }


@pytest.fixture
def sample_staff_user() -> Dict[str, Any]:
    """Sample staff user data."""
    return {
        "id": 100,
        "name": "Staff Member",
        "email": "staff@company.com",
        "role": "moderator"
    }


@pytest.fixture
def sample_review_data() -> Dict[str, Any]:
    """Sample review data for testing."""
    return {
        "review_type": ReviewType.PRODUCT,
        "customer_id": 1,
        "product_id": 101,
        "order_id": 201,
        "title": "Great product!",
        "content": "I really enjoyed using this product. It works exactly as described and the quality is excellent.",
        "rating": 4.5,
        "is_anonymous": False,
        "reviewer_name": "John D.",
        "source": ReviewSource.WEBSITE,
        "metadata": {"purchase_verified": True},
        "tags": ["quality", "recommended"]
    }


@pytest.fixture
def sample_feedback_data() -> Dict[str, Any]:
    """Sample feedback data for testing."""
    return {
        "feedback_type": FeedbackType.SUGGESTION,
        "customer_id": 1,
        "customer_email": "john.doe@example.com",
        "customer_name": "John Doe",
        "subject": "Suggestion for improvement",
        "message": "It would be great if you could add a dark mode to the application interface.",
        "category": "feature_request",
        "priority": FeedbackPriority.MEDIUM,
        "source": ReviewSource.WEBSITE,
        "metadata": {"page": "/settings"},
        "tags": ["ui", "dark-mode"]
    }


@pytest.fixture
def sample_review(db_session: Session, sample_review_data: Dict[str, Any]) -> Review:
    """Create a sample review in the database."""
    review = Review(
        uuid=uuid.uuid4(),
        review_type=sample_review_data["review_type"],
        customer_id=sample_review_data["customer_id"],
        product_id=sample_review_data["product_id"],
        order_id=sample_review_data["order_id"],
        title=sample_review_data["title"],
        content=sample_review_data["content"],
        rating=sample_review_data["rating"],
        is_anonymous=sample_review_data["is_anonymous"],
        reviewer_name=sample_review_data["reviewer_name"],
        source=sample_review_data["source"],
        status=ReviewStatus.APPROVED,
        is_verified_purchase=True,
        metadata=sample_review_data["metadata"],
        tags=sample_review_data["tags"],
        helpful_votes=5,
        not_helpful_votes=1,
        total_votes=6,
        helpful_percentage=83.3
    )
    
    db_session.add(review)
    db_session.commit()
    db_session.refresh(review)
    
    return review


@pytest.fixture
def sample_feedback(db_session: Session, sample_feedback_data: Dict[str, Any]) -> Feedback:
    """Create a sample feedback in the database."""
    feedback = Feedback(
        uuid=uuid.uuid4(),
        feedback_type=sample_feedback_data["feedback_type"],
        customer_id=sample_feedback_data["customer_id"],
        customer_email=sample_feedback_data["customer_email"],
        customer_name=sample_feedback_data["customer_name"],
        subject=sample_feedback_data["subject"],
        message=sample_feedback_data["message"],
        category=sample_feedback_data["category"],
        priority=sample_feedback_data["priority"],
        source=sample_feedback_data["source"],
        status=FeedbackStatus.NEW,
        metadata=sample_feedback_data["metadata"],
        tags=sample_feedback_data["tags"],
        follow_up_required=False
    )
    
    db_session.add(feedback)
    db_session.commit()
    db_session.refresh(feedback)
    
    return feedback


@pytest.fixture
def multiple_reviews(db_session: Session) -> list[Review]:
    """Create multiple reviews with different ratings and sentiments."""
    reviews = []
    
    # Create reviews with varying characteristics
    review_data = [
        {
            "rating": 5.0,
            "content": "Absolutely amazing product! Exceeded all my expectations. Highly recommend!",
            "sentiment": SentimentScore.VERY_POSITIVE,
            "product_id": 101,
            "customer_id": 1
        },
        {
            "rating": 4.0,
            "content": "Good product overall. Works well and good value for money.",
            "sentiment": SentimentScore.POSITIVE,
            "product_id": 101,
            "customer_id": 2
        },
        {
            "rating": 3.0,
            "content": "It's okay. Does what it's supposed to do but nothing special.",
            "sentiment": SentimentScore.NEUTRAL,
            "product_id": 101,
            "customer_id": 3
        },
        {
            "rating": 2.0,
            "content": "Not very satisfied. The quality could be much better.",
            "sentiment": SentimentScore.NEGATIVE,
            "product_id": 101,
            "customer_id": 4
        },
        {
            "rating": 1.0,
            "content": "Terrible product. Complete waste of money. Would not recommend.",
            "sentiment": SentimentScore.VERY_NEGATIVE,
            "product_id": 101,
            "customer_id": 5
        },
        {
            "rating": 4.5,
            "content": "Really good product for a different item. Very satisfied with the purchase.",
            "sentiment": SentimentScore.POSITIVE,
            "product_id": 102,
            "customer_id": 6
        }
    ]
    
    for i, data in enumerate(review_data):
        review = Review(
            uuid=uuid.uuid4(),
            review_type=ReviewType.PRODUCT,
            customer_id=data["customer_id"],
            product_id=data["product_id"],
            title=f"Review {i+1}",
            content=data["content"],
            rating=data["rating"],
            status=ReviewStatus.APPROVED,
            source=ReviewSource.WEBSITE,
            is_verified_purchase=True,
            sentiment_score=data["sentiment"]
        )
        
        db_session.add(review)
        reviews.append(review)
    
    db_session.commit()
    
    for review in reviews:
        db_session.refresh(review)
    
    return reviews


@pytest.fixture
def multiple_feedback(db_session: Session) -> list[Feedback]:
    """Create multiple feedback items with different types and priorities."""
    feedback_items = []
    
    feedback_data = [
        {
            "type": FeedbackType.COMPLAINT,
            "priority": FeedbackPriority.HIGH,
            "subject": "Product defect",
            "message": "The product I received has a defect and doesn't work properly.",
            "status": FeedbackStatus.NEW
        },
        {
            "type": FeedbackType.SUGGESTION,
            "priority": FeedbackPriority.MEDIUM,
            "subject": "Feature request",
            "message": "Please add a search filter option to make finding products easier.",
            "status": FeedbackStatus.IN_PROGRESS
        },
        {
            "type": FeedbackType.COMPLIMENT,
            "priority": FeedbackPriority.LOW,
            "subject": "Great service",
            "message": "Excellent customer service! Very helpful and responsive.",
            "status": FeedbackStatus.RESOLVED
        },
        {
            "type": FeedbackType.BUG_REPORT,
            "priority": FeedbackPriority.URGENT,
            "subject": "Website error",
            "message": "The checkout page is not working. Getting error 500.",
            "status": FeedbackStatus.ESCALATED
        }
    ]
    
    for i, data in enumerate(feedback_data):
        feedback = Feedback(
            uuid=uuid.uuid4(),
            feedback_type=data["type"],
            customer_id=i + 1,
            customer_email=f"customer{i+1}@example.com",
            customer_name=f"Customer {i+1}",
            subject=data["subject"],
            message=data["message"],
            priority=data["priority"],
            status=data["status"],
            source=ReviewSource.WEBSITE,
            category="general"
        )
        
        db_session.add(feedback)
        feedback_items.append(feedback)
    
    db_session.commit()
    
    for feedback in feedback_items:
        db_session.refresh(feedback)
    
    return feedback_items


@pytest.fixture
def review_template(db_session: Session) -> ReviewTemplate:
    """Create a sample review template."""
    template = ReviewTemplate(
        uuid=uuid.uuid4(),
        name="Product Review Template",
        review_type=ReviewType.PRODUCT,
        is_active=True,
        title="Share your experience",
        description="Help other customers by sharing your experience with this product",
        custom_questions=[
            {"question": "How would you rate the quality?", "type": "rating"},
            {"question": "Would you recommend this product?", "type": "boolean"}
        ],
        rating_labels={
            "1": "Very Poor",
            "2": "Poor",
            "3": "Average",
            "4": "Good",
            "5": "Excellent"
        },
        requires_purchase=True,
        allows_anonymous=False,
        allows_media=True,
        max_media_files=5,
        auto_request_after_days=7,
        reminder_enabled=True,
        reminder_days=14
    )
    
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    
    return template


@pytest.fixture
def feedback_category(db_session: Session) -> FeedbackCategory:
    """Create a sample feedback category."""
    category = FeedbackCategory(
        name="Product Issues",
        description="Issues related to product quality or functionality",
        is_active=True,
        sort_order=1,
        auto_assign_keywords=["defect", "broken", "not working", "quality"],
        auto_escalate=True,
        escalation_priority=FeedbackPriority.HIGH,
        escalation_conditions={"keywords": ["broken", "defect"]}
    )
    
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    
    return category


# Authentication fixtures
@pytest.fixture
def auth_headers_customer() -> Dict[str, str]:
    """Authentication headers for customer user."""
    return {"Authorization": "Bearer customer_token"}


@pytest.fixture
def auth_headers_staff() -> Dict[str, str]:
    """Authentication headers for staff user."""
    return {"Authorization": "Bearer staff_token"}


# Utility fixtures
@pytest.fixture
def mock_current_time():
    """Mock current time for consistent testing."""
    return datetime(2024, 1, 15, 12, 0, 0)


@pytest.fixture
def time_range():
    """Time range for testing analytics."""
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 1, 31)
    return {"start_date": start_date, "end_date": end_date}


# Performance testing fixtures
@pytest.fixture
def large_dataset(db_session: Session):
    """Create a large dataset for performance testing."""
    reviews = []
    
    # Create 1000 reviews
    for i in range(1000):
        review = Review(
            uuid=uuid.uuid4(),
            review_type=ReviewType.PRODUCT,
            customer_id=(i % 100) + 1,  # 100 unique customers
            product_id=(i % 50) + 1,    # 50 unique products
            title=f"Review {i}",
            content=f"This is review number {i}. " * 10,  # Longer content
            rating=((i % 5) + 1),  # Ratings 1-5
            status=ReviewStatus.APPROVED,
            source=ReviewSource.WEBSITE,
            is_verified_purchase=i % 3 == 0,  # 1/3 verified
            created_at=datetime.utcnow() - timedelta(days=i % 365)  # Spread over a year
        )
        reviews.append(review)
    
    db_session.add_all(reviews)
    db_session.commit()
    
    return reviews


# Mock external services
@pytest.fixture
def mock_email_service():
    """Mock email service for testing notifications."""
    class MockEmailService:
        def __init__(self):
            self.sent_emails = []
        
        async def send_email(self, to: str, subject: str, content: str):
            self.sent_emails.append({
                "to": to,
                "subject": subject,
                "content": content,
                "sent_at": datetime.utcnow()
            })
            return {"success": True, "message_id": f"mock_{len(self.sent_emails)}"}
    
    return MockEmailService()


@pytest.fixture
def mock_sentiment_api():
    """Mock sentiment analysis API."""
    def mock_analyze(text: str):
        # Simple mock based on keywords
        text_lower = text.lower()
        if any(word in text_lower for word in ["excellent", "amazing", "love", "great"]):
            return {"sentiment": "positive", "confidence": 0.9}
        elif any(word in text_lower for word in ["terrible", "awful", "hate", "worst"]):
            return {"sentiment": "negative", "confidence": 0.9}
        else:
            return {"sentiment": "neutral", "confidence": 0.6}
    
    return mock_analyze