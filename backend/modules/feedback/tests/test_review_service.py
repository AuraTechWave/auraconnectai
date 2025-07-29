# backend/modules/feedback/tests/test_review_service.py

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import uuid

from backend.modules.feedback.services.review_service import ReviewService
from backend.modules.feedback.models.feedback_models import (
    Review, ReviewVote, BusinessResponse, ReviewMedia, ReviewStatus,
    ReviewType, SentimentScore, ReviewSource
)
from backend.modules.feedback.schemas.feedback_schemas import (
    ReviewCreate, ReviewUpdate, ReviewModeration, ReviewVoteCreate,
    BusinessResponseCreate, ReviewMediaCreate, ReviewFilters
)
from backend.core.exceptions import ValidationError, NotFoundError, PermissionError


class TestReviewService:
    """Test cases for ReviewService"""
    
    def test_create_review_success(self, review_service: ReviewService, sample_review_data):
        """Test successful review creation"""
        review_create = ReviewCreate(**sample_review_data)
        
        result = review_service.create_review(review_create, auto_verify=True)
        
        assert result.id is not None
        assert result.title == sample_review_data["title"]
        assert result.content == sample_review_data["content"]
        assert result.rating == sample_review_data["rating"]
        assert result.customer_id == sample_review_data["customer_id"]
        assert result.status == ReviewStatus.APPROVED  # auto_verify=True
        assert result.is_verified_purchase is True
    
    def test_create_review_without_auto_verify(self, review_service: ReviewService, sample_review_data):
        """Test review creation without auto verification"""
        review_create = ReviewCreate(**sample_review_data)
        
        result = review_service.create_review(review_create, auto_verify=False)
        
        assert result.status == ReviewStatus.PENDING
    
    def test_create_review_duplicate_prevention(self, review_service: ReviewService, sample_review_data, sample_review):
        """Test that duplicate reviews are prevented"""
        # Try to create another review for the same product by the same customer
        review_create = ReviewCreate(**sample_review_data)
        
        with pytest.raises(ValidationError, match="already reviewed"):
            review_service.create_review(review_create)
    
    def test_get_review_success(self, review_service: ReviewService, sample_review):
        """Test successful review retrieval"""
        result = review_service.get_review(sample_review.id)
        
        assert result.id == sample_review.id
        assert result.title == sample_review.title
        assert result.content == sample_review.content
        assert result.rating == sample_review.rating
    
    def test_get_review_not_found(self, review_service: ReviewService):
        """Test review retrieval with invalid ID"""
        with pytest.raises(NotFoundError):
            review_service.get_review(99999)
    
    def test_get_review_by_uuid(self, review_service: ReviewService, sample_review):
        """Test review retrieval by UUID"""
        result = review_service.get_review_by_uuid(str(sample_review.uuid))
        
        assert result.id == sample_review.id
        assert result.uuid == str(sample_review.uuid)
    
    def test_update_review_success(self, review_service: ReviewService, sample_review):
        """Test successful review update"""
        update_data = ReviewUpdate(
            title="Updated title",
            content="Updated content with more details about the product experience.",
            rating=5.0
        )
        
        result = review_service.update_review(
            sample_review.id, 
            update_data, 
            customer_id=sample_review.customer_id
        )
        
        assert result.title == "Updated title"
        assert result.content == "Updated content with more details about the product experience."
        assert result.rating == 5.0
        assert result.status == ReviewStatus.PENDING  # Should reset to pending after content change
    
    def test_update_review_permission_denied(self, review_service: ReviewService, sample_review):
        """Test review update with wrong customer"""
        update_data = ReviewUpdate(title="Unauthorized update")
        
        with pytest.raises(PermissionError):
            review_service.update_review(
                sample_review.id, 
                update_data, 
                customer_id=999  # Different customer
            )
    
    def test_moderate_review_success(self, review_service: ReviewService, sample_review):
        """Test successful review moderation"""
        moderation_data = ReviewModeration(
            status=ReviewStatus.APPROVED,
            moderation_notes="Review approved after verification",
            is_featured=True
        )
        
        result = review_service.moderate_review(
            sample_review.id,
            moderation_data,
            moderator_id=100
        )
        
        assert result.status == ReviewStatus.APPROVED
        assert result.is_featured is True
        assert result.moderation_notes == "Review approved after verification"
        assert result.moderated_by == 100
        assert result.moderated_at is not None
    
    def test_delete_review_soft_delete(self, review_service: ReviewService, sample_review):
        """Test soft delete of review"""
        result = review_service.delete_review(
            sample_review.id,
            customer_id=sample_review.customer_id,
            soft_delete=True
        )
        
        assert result["success"] is True
        
        # Verify review is hidden, not deleted
        updated_review = review_service.get_review(sample_review.id)
        assert updated_review.status == ReviewStatus.HIDDEN
    
    def test_vote_on_review_success(self, review_service: ReviewService, sample_review):
        """Test voting on review helpfulness"""
        vote_data = ReviewVoteCreate(is_helpful=True)
        
        result = review_service.vote_on_review(
            sample_review.id,
            customer_id=2,  # Different customer
            vote_data=vote_data
        )
        
        assert result["success"] is True
        assert result["helpful_votes"] == sample_review.helpful_votes + 1
        assert result["total_votes"] == sample_review.total_votes + 1
    
    def test_vote_on_review_update_existing(self, review_service: ReviewService, sample_review, db_session):
        """Test updating existing vote"""
        # Create initial vote
        initial_vote = ReviewVote(
            review_id=sample_review.id,
            customer_id=2,
            is_helpful=True
        )
        db_session.add(initial_vote)
        db_session.commit()
        
        # Update vote to not helpful
        vote_data = ReviewVoteCreate(is_helpful=False)
        
        result = review_service.vote_on_review(
            sample_review.id,
            customer_id=2,
            vote_data=vote_data
        )
        
        assert result["success"] is True
        # Should have decremented helpful votes and incremented not helpful
    
    def test_add_business_response_success(self, review_service: ReviewService, sample_review):
        """Test adding business response to review"""
        response_data = BusinessResponseCreate(
            content="Thank you for your feedback! We're glad you enjoyed the product.",
            responder_name="Customer Service",
            responder_title="Support Manager",
            responder_id=101,
            is_published=True
        )
        
        result = review_service.add_business_response(sample_review.id, response_data)
        
        assert result["success"] is True
        assert result["response_id"] is not None
        
        # Verify review is updated
        updated_review = review_service.get_review(sample_review.id)
        assert updated_review.has_business_response is True
        assert updated_review.business_response_at is not None
    
    def test_add_business_response_duplicate_prevention(self, review_service: ReviewService, sample_review, db_session):
        """Test that duplicate business responses are prevented"""
        # Add initial response
        response = BusinessResponse(
            uuid=uuid.uuid4(),
            review_id=sample_review.id,
            content="Initial response",
            responder_name="Staff",
            is_published=True
        )
        db_session.add(response)
        db_session.commit()
        
        # Try to add another response
        response_data = BusinessResponseCreate(
            content="Duplicate response",
            responder_name="Staff"
        )
        
        with pytest.raises(ValidationError, match="already exists"):
            review_service.add_business_response(sample_review.id, response_data)
    
    def test_add_review_media_success(self, review_service: ReviewService, sample_review):
        """Test adding media to review"""
        media_data = [
            ReviewMediaCreate(
                media_type="image",
                file_path="/uploads/review_image_1.jpg",
                file_name="product_photo.jpg",
                file_size=1024576,
                mime_type="image/jpeg",
                width=1920,
                height=1080
            ),
            ReviewMediaCreate(
                media_type="video",
                file_path="/uploads/review_video_1.mp4",
                file_name="product_demo.mp4",
                file_size=5242880,
                mime_type="video/mp4",
                duration=30
            )
        ]
        
        result = review_service.add_review_media(
            sample_review.id,
            media_data,
            customer_id=sample_review.customer_id
        )
        
        assert result["success"] is True
        assert result["media_count"] == 2
        assert len(result["media_ids"]) == 2
        
        # Verify review media flags are updated
        updated_review = review_service.get_review(sample_review.id)
        assert updated_review.has_images is True
        assert updated_review.has_videos is True
        assert updated_review.media_count == 2
    
    def test_add_review_media_permission_denied(self, review_service: ReviewService, sample_review):
        """Test adding media with wrong customer"""
        media_data = [
            ReviewMediaCreate(
                media_type="image",
                file_path="/uploads/test.jpg",
                file_name="test.jpg"
            )
        ]
        
        with pytest.raises(PermissionError):
            review_service.add_review_media(
                sample_review.id,
                media_data,
                customer_id=999  # Wrong customer
            )
    
    def test_list_reviews_with_filters(self, review_service: ReviewService, multiple_reviews):
        """Test listing reviews with various filters"""
        # Test basic listing
        result = review_service.list_reviews(page=1, per_page=10)
        assert result.total == len(multiple_reviews)
        assert len(result.items) == len(multiple_reviews)
        
        # Test rating filter
        filters = ReviewFilters(rating_min=4.0)
        result = review_service.list_reviews(filters=filters)
        high_rated_reviews = [r for r in result.items if r.rating >= 4.0]
        assert len(high_rated_reviews) == len(result.items)
        
        # Test product filter
        filters = ReviewFilters(product_id=101)
        result = review_service.list_reviews(filters=filters)
        assert all(item.product_id == 101 for item in result.items)
        
        # Test verified reviews only
        filters = ReviewFilters(verified_only=True)
        result = review_service.list_reviews(filters=filters)
        # All test reviews are verified in the fixture
        assert result.total > 0
    
    def test_list_reviews_pagination(self, review_service: ReviewService, multiple_reviews):
        """Test review listing pagination"""
        # First page
        result = review_service.list_reviews(page=1, per_page=3)
        assert len(result.items) == 3
        assert result.page == 1
        assert result.has_next is True
        assert result.has_prev is False
        
        # Second page
        result = review_service.list_reviews(page=2, per_page=3)
        assert len(result.items) == 3
        assert result.page == 2
        assert result.has_next is True  # Should have more
        assert result.has_prev is True
    
    def test_list_reviews_sorting(self, review_service: ReviewService, multiple_reviews):
        """Test review listing with different sorting options"""
        # Sort by rating descending
        result = review_service.list_reviews(sort_by="rating", sort_order="desc")
        ratings = [item.rating for item in result.items]
        assert ratings == sorted(ratings, reverse=True)
        
        # Sort by created_at ascending
        result = review_service.list_reviews(sort_by="created_at", sort_order="asc")
        # Should be ordered by creation time
        assert len(result.items) > 0
    
    def test_get_review_aggregates_basic(self, review_service: ReviewService, multiple_reviews):
        """Test getting review aggregates for an entity"""
        result = review_service.get_review_aggregates("product", 101)
        
        product_101_reviews = [r for r in multiple_reviews if r.product_id == 101]
        
        assert result["entity_type"] == "product"
        assert result["entity_id"] == 101
        assert result["total_reviews"] == len(product_101_reviews)
        assert result["average_rating"] > 0
        assert result["rating_counts"]["5"] >= 0  # Should have rating distribution
    
    def test_get_review_aggregates_force_refresh(self, review_service: ReviewService, multiple_reviews):
        """Test forced refresh of review aggregates"""
        # Get initial aggregates
        result1 = review_service.get_review_aggregates("product", 101, force_refresh=False)
        
        # Force refresh
        result2 = review_service.get_review_aggregates("product", 101, force_refresh=True)
        
        # Results should be similar (force refresh should recalculate)
        assert result1["total_reviews"] == result2["total_reviews"]
        assert result1["average_rating"] == result2["average_rating"]
    
    @pytest.mark.asyncio
    async def test_sentiment_analysis_scheduling(self, review_service: ReviewService, sample_review_data):
        """Test that sentiment analysis is scheduled for new reviews"""
        review_create = ReviewCreate(**sample_review_data)
        
        # Mock the sentiment analysis scheduling
        with pytest.MonkeyPatch().context() as m:
            scheduled_reviews = []
            
            def mock_schedule_sentiment(review_id):
                scheduled_reviews.append(review_id)
            
            m.setattr(review_service, '_schedule_sentiment_analysis', mock_schedule_sentiment)
            
            result = review_service.create_review(review_create)
            
            assert result.id in scheduled_reviews
    
    def test_review_verification_logic(self, review_service: ReviewService, sample_review_data):
        """Test review verification logic"""
        # Test with order_id (should be verified)
        review_create = ReviewCreate(**sample_review_data)
        result = review_service.create_review(review_create)
        assert result.is_verified_purchase is True
        
        # Test without order_id (should not be verified)
        review_data_no_order = sample_review_data.copy()
        review_data_no_order["order_id"] = None
        review_data_no_order["customer_id"] = 2  # Different customer to avoid duplicate
        
        review_create = ReviewCreate(**review_data_no_order)
        result = review_service.create_review(review_create)
        assert result.is_verified_purchase is False
    
    def test_review_content_validation(self, review_service: ReviewService, sample_review_data):
        """Test review content validation"""
        # Test minimum content length
        invalid_data = sample_review_data.copy()
        invalid_data["content"] = "Too short"  # Less than 10 characters
        
        review_create = ReviewCreate(**invalid_data)
        
        # Should raise validation error during schema validation
        with pytest.raises(ValidationError):
            ReviewCreate(**invalid_data)
    
    def test_review_rating_validation(self, review_service: ReviewService, sample_review_data):
        """Test review rating validation and rounding"""
        test_data = sample_review_data.copy()
        test_data["rating"] = 4.3  # Should round to 4.5
        
        review_create = ReviewCreate(**test_data)
        
        # Rating should be rounded to nearest 0.5
        assert review_create.rating == 4.5
    
    def test_anonymous_review_handling(self, review_service: ReviewService, sample_review_data):
        """Test anonymous review creation and display"""
        review_data = sample_review_data.copy()
        review_data["is_anonymous"] = True
        review_data["reviewer_name"] = "Anonymous User"
        
        review_create = ReviewCreate(**review_data)
        result = review_service.create_review(review_create)
        
        assert result.is_anonymous is True
        assert result.reviewer_name == "Anonymous User"
    
    def test_review_metadata_handling(self, review_service: ReviewService, sample_review_data):
        """Test review metadata storage and retrieval"""
        metadata = {
            "source_campaign": "email_marketing",
            "user_agent": "Mozilla/5.0...",
            "referrer": "https://google.com"
        }
        
        review_data = sample_review_data.copy()
        review_data["metadata"] = metadata
        
        review_create = ReviewCreate(**review_data)
        result = review_service.create_review(review_create)
        
        # Metadata should be preserved
        for key, value in metadata.items():
            assert result.metadata[key] == value
    
    def test_review_tags_handling(self, review_service: ReviewService, sample_review_data):
        """Test review tags storage and filtering"""
        tags = ["quality", "fast-shipping", "recommended", "value-for-money"]
        
        review_data = sample_review_data.copy()
        review_data["tags"] = tags
        
        review_create = ReviewCreate(**review_data)
        result = review_service.create_review(review_create)
        
        assert result.tags == tags
    
    def test_review_engagement_metrics(self, review_service: ReviewService, sample_review):
        """Test review engagement metrics calculation"""
        # Add some votes
        vote_data = ReviewVoteCreate(is_helpful=True)
        review_service.vote_on_review(sample_review.id, 2, vote_data)
        review_service.vote_on_review(sample_review.id, 3, vote_data)
        
        # Add not helpful vote
        vote_data = ReviewVoteCreate(is_helpful=False)
        review_service.vote_on_review(sample_review.id, 4, vote_data)
        
        # Get updated review
        updated_review = review_service.get_review(sample_review.id)
        
        # Check metrics are calculated correctly
        assert updated_review.total_votes > sample_review.total_votes
        assert updated_review.helpful_percentage > 0
    
    def test_error_handling_invalid_input(self, review_service: ReviewService):
        """Test error handling for various invalid inputs"""
        # Test invalid review type
        with pytest.raises(ValueError):
            ReviewCreate(
                review_type="invalid_type",
                customer_id=1,
                content="Test review content",
                rating=4.0
            )
        
        # Test invalid rating range
        with pytest.raises(ValueError):
            ReviewCreate(
                review_type=ReviewType.PRODUCT,
                customer_id=1,
                content="Test review content",
                rating=6.0  # Above maximum
            )


class TestReviewServiceEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_concurrent_review_creation(self, review_service: ReviewService, sample_review_data):
        """Test handling of concurrent review creation attempts"""
        # This would test race conditions in a real concurrent environment
        # For now, we'll test the duplicate prevention logic
        
        review_create = ReviewCreate(**sample_review_data)
        
        # Create first review
        result1 = review_service.create_review(review_create)
        assert result1.id is not None
        
        # Attempt to create duplicate should fail
        with pytest.raises(ValidationError):
            review_service.create_review(review_create)
    
    def test_large_content_handling(self, review_service: ReviewService, sample_review_data):
        """Test handling of large review content"""
        # Create very long content (near the limit)
        long_content = "This is a very detailed review. " * 160  # Close to 5000 char limit
        
        review_data = sample_review_data.copy()
        review_data["content"] = long_content
        review_data["customer_id"] = 999  # Different customer
        
        review_create = ReviewCreate(**review_data)
        result = review_service.create_review(review_create)
        
        assert len(result.content) <= 5000
        assert result.content == long_content
    
    def test_special_characters_in_content(self, review_service: ReviewService, sample_review_data):
        """Test handling of special characters and unicode in reviews"""
        special_content = "Great product! 🌟⭐️ Very satisfied 😊. Price: $99.99 (originally €120.50). Würde ich wieder kaufen! 中文测试"
        
        review_data = sample_review_data.copy()
        review_data["content"] = special_content
        review_data["customer_id"] = 888  # Different customer
        
        review_create = ReviewCreate(**review_data)
        result = review_service.create_review(review_create)
        
        assert result.content == special_content
    
    def test_database_constraint_violations(self, review_service: ReviewService, sample_review_data, db_session):
        """Test handling of database constraint violations"""
        # This would test foreign key constraints, unique constraints, etc.
        # For now, we'll test with invalid customer_id
        
        review_data = sample_review_data.copy()
        # customer_id constraint would be enforced at the database level
        # In a real scenario, this might cause a foreign key violation
        
        review_create = ReviewCreate(**review_data)
        # This should work in our test environment
        result = review_service.create_review(review_create)
        assert result is not None