# backend/modules/feedback/tests/test_database_relationships.py

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import uuid

from backend.modules.feedback.models.feedback_models import (
    Review, Feedback, ReviewMedia, ReviewVote, BusinessResponse, 
    FeedbackResponse, ReviewAggregate, ReviewTemplate, ReviewInvitation,
    FeedbackCategory, ReviewStatus, FeedbackStatus, ReviewType, 
    FeedbackType, FeedbackPriority, SentimentScore, ReviewSource
)


class TestDatabaseRelationships:
    """Test database relationships, constraints, and cascading operations"""
    
    def test_review_media_cascade_delete(self, db_session: Session, sample_review):
        """Test that deleting a review cascades to its media files"""
        # Add media to the review
        media1 = ReviewMedia(
            uuid=uuid.uuid4(),
            review_id=sample_review.id,
            media_type="image",
            file_path="/uploads/test1.jpg",
            file_name="test1.jpg",
            display_order=1
        )
        media2 = ReviewMedia(
            uuid=uuid.uuid4(),
            review_id=sample_review.id,
            media_type="image", 
            file_path="/uploads/test2.jpg",
            file_name="test2.jpg",
            display_order=2
        )
        
        db_session.add_all([media1, media2])
        db_session.commit()
        
        # Verify media exists
        media_count = db_session.query(ReviewMedia).filter_by(review_id=sample_review.id).count()
        assert media_count == 2
        
        # Delete the review
        db_session.delete(sample_review)
        db_session.commit()
        
        # Verify media was cascaded
        media_count = db_session.query(ReviewMedia).filter_by(review_id=sample_review.id).count()
        assert media_count == 0
    
    def test_review_votes_cascade_delete(self, db_session: Session, sample_review):
        """Test that deleting a review cascades to its votes"""
        # Add votes to the review
        vote1 = ReviewVote(
            uuid=uuid.uuid4(),
            review_id=sample_review.id,
            customer_id=2,
            is_helpful=True
        )
        vote2 = ReviewVote(
            uuid=uuid.uuid4(),
            review_id=sample_review.id,
            customer_id=3,
            is_helpful=False
        )
        
        db_session.add_all([vote1, vote2])
        db_session.commit()
        
        # Verify votes exist
        votes_count = db_session.query(ReviewVote).filter_by(review_id=sample_review.id).count()
        assert votes_count == 2
        
        # Delete the review
        db_session.delete(sample_review)
        db_session.commit()
        
        # Verify votes were cascaded
        votes_count = db_session.query(ReviewVote).filter_by(review_id=sample_review.id).count()
        assert votes_count == 0
    
    def test_business_response_cascade_delete(self, db_session: Session, sample_review):
        """Test that deleting a review cascades to business responses"""
        # Add business response
        response = BusinessResponse(
            uuid=uuid.uuid4(),
            review_id=sample_review.id,
            content="Thank you for your feedback!",
            responder_name="Customer Service",
            is_published=True
        )
        
        db_session.add(response)
        db_session.commit()
        
        # Verify response exists
        response_count = db_session.query(BusinessResponse).filter_by(review_id=sample_review.id).count()
        assert response_count == 1
        
        # Delete the review
        db_session.delete(sample_review)
        db_session.commit()
        
        # Verify response was cascaded
        response_count = db_session.query(BusinessResponse).filter_by(review_id=sample_review.id).count()
        assert response_count == 0
    
    def test_feedback_responses_cascade_delete(self, db_session: Session, sample_feedback):
        """Test that deleting feedback cascades to its responses"""
        # Add responses to feedback
        response1 = FeedbackResponse(
            uuid=uuid.uuid4(),
            feedback_id=sample_feedback.id,
            responder_id=100,
            responder_name="Support Agent",
            message="We're looking into this issue.",
            is_internal=False,
            is_resolution=False
        )
        response2 = FeedbackResponse(
            uuid=uuid.uuid4(),
            feedback_id=sample_feedback.id,
            responder_id=101,
            responder_name="Manager",
            message="Issue has been resolved.",
            is_internal=False,
            is_resolution=True
        )
        
        db_session.add_all([response1, response2])
        db_session.commit()
        
        # Verify responses exist
        response_count = db_session.query(FeedbackResponse).filter_by(feedback_id=sample_feedback.id).count()
        assert response_count == 2
        
        # Delete the feedback
        db_session.delete(sample_feedback)
        db_session.commit()
        
        # Verify responses were cascaded
        response_count = db_session.query(FeedbackResponse).filter_by(feedback_id=sample_feedback.id).count()
        assert response_count == 0
    
    def test_unique_constraints(self, db_session: Session, sample_review):
        """Test unique constraints are enforced"""
        # Test review vote uniqueness (one vote per customer per review)
        vote1 = ReviewVote(
            uuid=uuid.uuid4(),
            review_id=sample_review.id,
            customer_id=2,
            is_helpful=True
        )
        db_session.add(vote1)
        db_session.commit()
        
        # Try to add another vote from the same customer
        vote2 = ReviewVote(
            uuid=uuid.uuid4(),
            review_id=sample_review.id,
            customer_id=2,  # Same customer
            is_helpful=False
        )
        db_session.add(vote2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
        
        db_session.rollback()
    
    def test_review_aggregate_unique_constraint(self, db_session: Session):
        """Test review aggregate unique constraint (entity_type + entity_id)"""
        # Create first aggregate
        aggregate1 = ReviewAggregate(
            entity_type="product",
            entity_id=101,
            total_reviews=5,
            average_rating=4.2,
            rating_1_count=0,
            rating_2_count=1,
            rating_3_count=1,
            rating_4_count=1,
            rating_5_count=2,
            verified_reviews_count=3,
            featured_reviews_count=1,
            with_images_count=2,
            with_videos_count=0,
            positive_sentiment_count=3,
            negative_sentiment_count=1,
            neutral_sentiment_count=1,
            last_calculated_at=db_session.query(Review).first().created_at
        )
        db_session.add(aggregate1)
        db_session.commit()
        
        # Try to create duplicate aggregate
        aggregate2 = ReviewAggregate(
            entity_type="product",
            entity_id=101,  # Same entity
            total_reviews=3,
            average_rating=3.5,
            rating_1_count=0,
            rating_2_count=0,
            rating_3_count=2,
            rating_4_count=1,
            rating_5_count=0,
            verified_reviews_count=3,
            featured_reviews_count=0,
            with_images_count=0,
            with_videos_count=0,
            positive_sentiment_count=1,
            negative_sentiment_count=1,
            neutral_sentiment_count=1,
            last_calculated_at=db_session.query(Review).first().created_at
        )
        db_session.add(aggregate2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
        
        db_session.rollback()
    
    def test_review_invitation_foreign_keys(self, db_session: Session, sample_review):
        """Test review invitation foreign key relationships"""
        # Create review template
        template = ReviewTemplate(
            uuid=uuid.uuid4(),
            name="Test Template",
            review_type=ReviewType.PRODUCT,
            is_active=True,
            is_default=False,
            title="Share your experience",
            requires_purchase=True,
            allows_anonymous=False,
            allows_media=True,
            reminder_enabled=True
        )
        db_session.add(template)
        db_session.commit()
        
        # Create review invitation
        invitation = ReviewInvitation(
            uuid=uuid.uuid4(),
            customer_id=1,
            customer_email="test@example.com",
            review_type=ReviewType.PRODUCT,
            entity_id=101,
            template_id=template.id,
            invitation_token="test_token_123",
            expires_at=sample_review.created_at,
            review_id=sample_review.id
        )
        db_session.add(invitation)
        db_session.commit()
        
        # Verify relationships
        assert invitation.template_id == template.id
        assert invitation.review_id == sample_review.id
        
        # Test SET NULL on template deletion
        db_session.delete(template)
        db_session.commit()
        
        db_session.refresh(invitation)
        assert invitation.template_id is None
        
        # Test SET NULL on review deletion
        db_session.delete(sample_review)
        db_session.commit()
        
        db_session.refresh(invitation)
        assert invitation.review_id is None
    
    def test_enum_constraints(self, db_session: Session):
        """Test that enum constraints are enforced"""
        # Test invalid review status
        with pytest.raises((ValueError, IntegrityError)):
            review = Review(
                uuid=uuid.uuid4(),
                review_type=ReviewType.PRODUCT,
                customer_id=1,
                content="Test review",
                rating=4.0,
                status="invalid_status",  # Invalid enum value
                is_anonymous=False,
                is_verified_purchase=True,
                source=ReviewSource.WEBSITE
            )
            db_session.add(review)
            db_session.commit()
    
    def test_rating_constraints(self, db_session: Session):
        """Test rating value constraints"""
        # Valid rating should work
        review = Review(
            uuid=uuid.uuid4(),
            review_type=ReviewType.PRODUCT,
            customer_id=1,
            content="Test review with valid rating",
            rating=4.5,
            status=ReviewStatus.APPROVED,
            is_anonymous=False,
            is_verified_purchase=True,
            source=ReviewSource.WEBSITE
        )
        db_session.add(review)
        db_session.commit()
        
        assert review.rating == 4.5
        
        # Note: Database-level constraints for rating bounds would need to be
        # implemented in the migration if required
    
    def test_json_field_storage(self, db_session: Session, sample_review):
        """Test JSON field storage and retrieval"""
        # Add metadata to review
        metadata = {
            "source_campaign": "email_marketing",
            "user_agent": "Mozilla/5.0...",
            "purchase_verified": True,
            "nested_data": {
                "key1": "value1",
                "key2": 123
            }
        }
        
        sample_review.review_metadata = metadata
        sample_review.tags = ["quality", "fast-shipping", "recommended"]
        
        db_session.commit()
        db_session.refresh(sample_review)
        
        # Verify JSON data is stored and retrieved correctly
        assert sample_review.review_metadata == metadata
        assert sample_review.tags == ["quality", "fast-shipping", "recommended"]
        
        # Test nested access
        assert sample_review.review_metadata["nested_data"]["key1"] == "value1"
        assert sample_review.review_metadata["nested_data"]["key2"] == 123
    
    def test_array_field_operations(self, db_session: Session, sample_feedback):
        """Test array field operations"""
        # Add tags to feedback
        tags = ["bug", "ui", "critical", "mobile"]
        sample_feedback.tags = tags
        
        db_session.commit()
        db_session.refresh(sample_feedback)
        
        # Verify array storage
        assert sample_feedback.tags == tags
        assert len(sample_feedback.tags) == 4
        assert "bug" in sample_feedback.tags
        assert "desktop" not in sample_feedback.tags
    
    def test_timestamp_auto_update(self, db_session: Session, sample_review):
        """Test that updated_at timestamp is automatically updated"""
        original_updated_at = sample_review.updated_at
        
        # Wait a moment and update the review
        import time
        time.sleep(0.01)
        
        sample_review.content = "Updated review content"
        db_session.commit()
        db_session.refresh(sample_review)
        
        # Verify updated_at was changed
        assert sample_review.updated_at > original_updated_at
    
    def test_nullable_relationships(self, db_session: Session):
        """Test nullable relationship fields"""
        # Create review without optional relationships
        review = Review(
            uuid=uuid.uuid4(),
            review_type=ReviewType.PRODUCT,
            customer_id=1,
            content="Test review",
            rating=4.0,
            status=ReviewStatus.APPROVED,
            is_anonymous=False,
            is_verified_purchase=True,
            source=ReviewSource.WEBSITE,
            # Optional fields left as None
            product_id=None,
            service_id=None,
            order_id=None,
            title=None
        )
        
        db_session.add(review)
        db_session.commit()
        
        # Verify nullable fields are handled correctly
        assert review.product_id is None
        assert review.service_id is None
        assert review.order_id is None
        assert review.title is None
    
    def test_boolean_defaults(self, db_session: Session):
        """Test boolean field defaults"""
        review = Review(
            uuid=uuid.uuid4(),
            review_type=ReviewType.PRODUCT,
            customer_id=1,
            content="Test review",
            rating=4.0,
            status=ReviewStatus.APPROVED,
            source=ReviewSource.WEBSITE
            # Boolean fields should use defaults
        )
        
        db_session.add(review)
        db_session.commit()
        db_session.refresh(review)
        
        # Verify boolean defaults
        assert review.is_anonymous == False
        assert review.is_verified_purchase == False
        assert review.has_images == False
        assert review.has_videos == False
        assert review.has_business_response == False
        assert review.is_featured == False
        assert review.helpful_votes == 0
        assert review.not_helpful_votes == 0
        assert review.total_votes == 0
        assert review.media_count == 0
    
    def test_computed_fields_consistency(self, db_session: Session, sample_review):
        """Test that computed fields remain consistent"""
        # Add votes to review
        vote1 = ReviewVote(
            uuid=uuid.uuid4(),
            review_id=sample_review.id,
            customer_id=2,
            is_helpful=True
        )
        vote2 = ReviewVote(
            uuid=uuid.uuid4(),
            review_id=sample_review.id,
            customer_id=3,
            is_helpful=True
        )
        vote3 = ReviewVote(
            uuid=uuid.uuid4(),
            review_id=sample_review.id,
            customer_id=4,
            is_helpful=False
        )
        
        db_session.add_all([vote1, vote2, vote3])
        
        # Update review vote counts
        sample_review.helpful_votes = 2
        sample_review.not_helpful_votes = 1
        sample_review.total_votes = 3
        sample_review.helpful_percentage = (2 / 3) * 100  # 66.67%
        
        db_session.commit()
        db_session.refresh(sample_review)
        
        # Verify computed fields
        assert sample_review.helpful_votes == 2
        assert sample_review.not_helpful_votes == 1
        assert sample_review.total_votes == 3
        assert abs(sample_review.helpful_percentage - 66.67) < 0.01  # Allow for floating point precision


class TestDatabaseIndexes:
    """Test that database indexes are working effectively"""
    
    def test_uuid_index_uniqueness(self, db_session: Session):
        """Test UUID index uniqueness"""
        test_uuid = uuid.uuid4()
        
        # Create first review with UUID
        review1 = Review(
            uuid=test_uuid,
            review_type=ReviewType.PRODUCT,
            customer_id=1,
            content="First review",
            rating=4.0,
            status=ReviewStatus.APPROVED,
            is_anonymous=False,
            is_verified_purchase=True,
            source=ReviewSource.WEBSITE
        )
        db_session.add(review1)
        db_session.commit()
        
        # Try to create second review with same UUID
        review2 = Review(
            uuid=test_uuid,  # Same UUID
            review_type=ReviewType.PRODUCT,
            customer_id=2,
            content="Second review",
            rating=3.0,
            status=ReviewStatus.APPROVED,
            is_anonymous=False,
            is_verified_purchase=True,
            source=ReviewSource.WEBSITE
        )
        db_session.add(review2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
        
        db_session.rollback()
    
    def test_query_performance_indexes(self, db_session: Session, large_dataset):
        """Test that indexes improve query performance"""
        import time
        
        # Query by customer_id (should use index)
        start_time = time.time()
        reviews = db_session.query(Review).filter(Review.customer_id == 1).all()
        customer_query_time = time.time() - start_time
        
        # Query by rating (should use index)
        start_time = time.time()
        high_rated = db_session.query(Review).filter(Review.rating >= 4.0).all()
        rating_query_time = time.time() - start_time
        
        # Query by status (should use index)
        start_time = time.time()
        approved = db_session.query(Review).filter(Review.status == ReviewStatus.APPROVED).all()
        status_query_time = time.time() - start_time
        
        # All queries should complete reasonably quickly with indexes
        assert customer_query_time < 1.0  # Should be fast with index
        assert rating_query_time < 1.0    # Should be fast with index
        assert status_query_time < 1.0    # Should be fast with index
        
        # Verify results are reasonable
        assert len(reviews) > 0
        assert len(high_rated) > 0
        assert len(approved) > 0