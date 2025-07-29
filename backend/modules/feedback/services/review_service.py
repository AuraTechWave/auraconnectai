# backend/modules/feedback/services/review_service.py

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
import uuid
import logging

from backend.modules.feedback.models.feedback_models import (
    Review, ReviewMedia, ReviewVote, BusinessResponse, ReviewAggregate,
    ReviewTemplate, ReviewInvitation, ReviewStatus, ReviewType, SentimentScore
)
from backend.modules.feedback.schemas.feedback_schemas import (
    ReviewCreate, ReviewUpdate, ReviewModeration, ReviewResponse,
    ReviewSummary, ReviewFilters, BusinessResponseCreate,
    ReviewMediaCreate, ReviewVoteCreate, PaginatedResponse
)
from backend.core.exceptions import ValidationError, NotFoundError, PermissionError

logger = logging.getLogger(__name__)


class ReviewService:
    """Service for managing reviews and review-related operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_review(
        self,
        review_data: ReviewCreate,
        auto_verify: bool = False
    ) -> ReviewResponse:
        """Create a new review"""
        
        try:
            # Validate review eligibility
            self._validate_review_eligibility(review_data)
            
            # Check for existing review
            existing_review = self._check_duplicate_review(review_data)
            if existing_review:
                raise ValidationError("Customer has already reviewed this item")
            
            # Create review instance
            review = Review(
                uuid=uuid.uuid4(),
                review_type=review_data.review_type,
                customer_id=review_data.customer_id,
                order_id=review_data.order_id,
                product_id=review_data.product_id,
                service_id=review_data.service_id,
                title=review_data.title,
                content=review_data.content,
                rating=review_data.rating,
                is_anonymous=review_data.is_anonymous,
                reviewer_name=review_data.reviewer_name,
                source=review_data.source,
                metadata=review_data.metadata or {},
                tags=review_data.tags or [],
                status=ReviewStatus.APPROVED if auto_verify else ReviewStatus.PENDING
            )
            
            # Set verification status
            if review_data.order_id and self._verify_purchase(
                review_data.customer_id, 
                review_data.order_id, 
                review_data.product_id
            ):
                review.is_verified_purchase = True
            
            self.db.add(review)
            self.db.flush()
            
            # Initialize engagement metrics
            review.helpful_votes = 0
            review.not_helpful_votes = 0
            review.total_votes = 0
            review.helpful_percentage = 0.0
            
            self.db.commit()
            
            logger.info(f"Created review {review.id} for customer {review_data.customer_id}")
            
            # Schedule sentiment analysis
            self._schedule_sentiment_analysis(review.id)
            
            # Update aggregates if approved
            if review.status == ReviewStatus.APPROVED:
                self._update_review_aggregates(review)
            
            return self._format_review_response(review)
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating review: {e}")
            raise
    
    def get_review(self, review_id: int) -> ReviewResponse:
        """Get a specific review by ID"""
        
        review = self.db.query(Review).filter(Review.id == review_id).first()
        if not review:
            raise NotFoundError(f"Review {review_id} not found")
        
        return self._format_review_response(review)
    
    def get_review_by_uuid(self, review_uuid: str) -> ReviewResponse:
        """Get a review by UUID"""
        
        review = self.db.query(Review).filter(Review.uuid == review_uuid).first()
        if not review:
            raise NotFoundError(f"Review {review_uuid} not found")
        
        return self._format_review_response(review)
    
    def update_review(
        self,
        review_id: int,
        update_data: ReviewUpdate,
        customer_id: Optional[int] = None
    ) -> ReviewResponse:
        """Update an existing review"""
        
        review = self.db.query(Review).filter(Review.id == review_id).first()
        if not review:
            raise NotFoundError(f"Review {review_id} not found")
        
        # Check permissions
        if customer_id and review.customer_id != customer_id:
            raise PermissionError("Cannot update another customer's review")
        
        # Update allowed fields
        if update_data.title is not None:
            review.title = update_data.title
        if update_data.content is not None:
            review.content = update_data.content
        if update_data.rating is not None:
            old_rating = review.rating
            review.rating = update_data.rating
            # If rating changed significantly, re-analyze sentiment
            if abs(old_rating - review.rating) >= 1.0:
                self._schedule_sentiment_analysis(review.id)
        if update_data.is_anonymous is not None:
            review.is_anonymous = update_data.is_anonymous
        if update_data.reviewer_name is not None:
            review.reviewer_name = update_data.reviewer_name
        if update_data.metadata is not None:
            review.metadata = {**(review.metadata or {}), **update_data.metadata}
        if update_data.tags is not None:
            review.tags = update_data.tags
        
        # Reset moderation status if content changed
        if update_data.content or update_data.rating:
            review.status = ReviewStatus.PENDING
            review.moderated_at = None
            review.moderated_by = None
            review.moderation_notes = None
        
        self.db.commit()
        
        logger.info(f"Updated review {review_id}")
        
        return self._format_review_response(review)
    
    def moderate_review(
        self,
        review_id: int,
        moderation_data: ReviewModeration,
        moderator_id: int
    ) -> ReviewResponse:
        """Moderate a review (approve, reject, etc.)"""
        
        review = self.db.query(Review).filter(Review.id == review_id).first()
        if not review:
            raise NotFoundError(f"Review {review_id} not found")
        
        old_status = review.status
        
        # Update moderation fields
        review.status = moderation_data.status
        review.moderated_at = datetime.utcnow()
        review.moderated_by = moderator_id
        review.moderation_notes = moderation_data.moderation_notes
        
        if moderation_data.is_featured is not None:
            review.is_featured = moderation_data.is_featured
        
        self.db.commit()
        
        # Update aggregates if status changed to/from approved
        if (old_status != ReviewStatus.APPROVED and review.status == ReviewStatus.APPROVED) or \
           (old_status == ReviewStatus.APPROVED and review.status != ReviewStatus.APPROVED):
            self._update_review_aggregates(review)
        
        logger.info(f"Moderated review {review_id}: {old_status} -> {review.status}")
        
        return self._format_review_response(review)
    
    def delete_review(
        self,
        review_id: int,
        customer_id: Optional[int] = None,
        soft_delete: bool = True
    ) -> Dict[str, Any]:
        """Delete or hide a review"""
        
        review = self.db.query(Review).filter(Review.id == review_id).first()
        if not review:
            raise NotFoundError(f"Review {review_id} not found")
        
        # Check permissions
        if customer_id and review.customer_id != customer_id:
            raise PermissionError("Cannot delete another customer's review")
        
        if soft_delete:
            # Soft delete - just hide the review
            review.status = ReviewStatus.HIDDEN
            self.db.commit()
            logger.info(f"Soft deleted review {review_id}")
        else:
            # Hard delete - remove from database
            self.db.delete(review)
            self.db.commit()
            logger.info(f"Hard deleted review {review_id}")
        
        # Update aggregates
        self._update_review_aggregates(review)
        
        return {"success": True, "message": "Review deleted successfully"}
    
    def list_reviews(
        self,
        filters: Optional[ReviewFilters] = None,
        page: int = 1,
        per_page: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> PaginatedResponse:
        """List reviews with filtering and pagination"""
        
        query = self.db.query(Review)
        
        # Apply filters
        if filters:
            if filters.review_type:
                query = query.filter(Review.review_type == filters.review_type)
            if filters.status:
                query = query.filter(Review.status == filters.status)
            if filters.rating_min:
                query = query.filter(Review.rating >= filters.rating_min)
            if filters.rating_max:
                query = query.filter(Review.rating <= filters.rating_max)
            if filters.verified_only:
                query = query.filter(Review.is_verified_purchase == True)
            if filters.with_media:
                query = query.filter(Review.media_count > 0)
            if filters.sentiment:
                query = query.filter(Review.sentiment_score == filters.sentiment)
            if filters.date_from:
                query = query.filter(Review.created_at >= filters.date_from)
            if filters.date_to:
                query = query.filter(Review.created_at <= filters.date_to)
            if filters.customer_id:
                query = query.filter(Review.customer_id == filters.customer_id)
            if filters.product_id:
                query = query.filter(Review.product_id == filters.product_id)
            if filters.order_id:
                query = query.filter(Review.order_id == filters.order_id)
            if filters.tags:
                # Filter by tags (JSON contains any of the specified tags)
                tag_conditions = [
                    func.json_extract(Review.tags, f'$[{i}]').in_(filters.tags)
                    for i in range(10)  # Check first 10 tag positions
                ]
                query = query.filter(or_(*tag_conditions))
        
        # Apply sorting
        if hasattr(Review, sort_by):
            sort_column = getattr(Review, sort_by)
            if sort_order.lower() == "desc":
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * per_page
        reviews = query.offset(offset).limit(per_page).all()
        
        # Format response
        items = [self._format_review_summary(review) for review in reviews]
        
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page,
            has_next=page * per_page < total,
            has_prev=page > 1
        )
    
    def vote_on_review(
        self,
        review_id: int,
        customer_id: int,
        vote_data: ReviewVoteCreate
    ) -> Dict[str, Any]:
        """Vote on review helpfulness"""
        
        review = self.db.query(Review).filter(Review.id == review_id).first()
        if not review:
            raise NotFoundError(f"Review {review_id} not found")
        
        # Check for existing vote
        existing_vote = self.db.query(ReviewVote).filter(
            and_(
                ReviewVote.review_id == review_id,
                ReviewVote.customer_id == customer_id
            )
        ).first()
        
        if existing_vote:
            # Update existing vote
            old_helpful = existing_vote.is_helpful
            existing_vote.is_helpful = vote_data.is_helpful
            
            # Update review metrics
            if old_helpful != vote_data.is_helpful:
                if vote_data.is_helpful:
                    review.helpful_votes += 1
                    review.not_helpful_votes -= 1
                else:
                    review.helpful_votes -= 1
                    review.not_helpful_votes += 1
        else:
            # Create new vote
            vote = ReviewVote(
                review_id=review_id,
                customer_id=customer_id,
                is_helpful=vote_data.is_helpful
            )
            self.db.add(vote)
            
            # Update review metrics
            if vote_data.is_helpful:
                review.helpful_votes += 1
            else:
                review.not_helpful_votes += 1
            
            review.total_votes += 1
        
        # Recalculate helpful percentage
        if review.total_votes > 0:
            review.helpful_percentage = (review.helpful_votes / review.total_votes) * 100
        
        self.db.commit()
        
        logger.info(f"Recorded vote on review {review_id} by customer {customer_id}")
        
        return {
            "success": True,
            "helpful_votes": review.helpful_votes,
            "not_helpful_votes": review.not_helpful_votes,
            "total_votes": review.total_votes,
            "helpful_percentage": review.helpful_percentage
        }
    
    def add_business_response(
        self,
        review_id: int,
        response_data: BusinessResponseCreate
    ) -> Dict[str, Any]:
        """Add business response to a review"""
        
        review = self.db.query(Review).filter(Review.id == review_id).first()
        if not review:
            raise NotFoundError(f"Review {review_id} not found")
        
        # Check if business response already exists
        existing_response = self.db.query(BusinessResponse).filter(
            BusinessResponse.review_id == review_id
        ).first()
        
        if existing_response:
            raise ValidationError("Business response already exists for this review")
        
        # Create business response
        response = BusinessResponse(
            uuid=uuid.uuid4(),
            review_id=review_id,
            content=response_data.content,
            responder_name=response_data.responder_name,
            responder_title=response_data.responder_title,
            responder_id=response_data.responder_id,
            is_published=response_data.is_published,
            metadata=response_data.metadata or {}
        )
        
        self.db.add(response)
        
        # Update review
        review.has_business_response = True
        review.business_response_at = datetime.utcnow()
        
        self.db.commit()
        
        logger.info(f"Added business response to review {review_id}")
        
        return {
            "success": True,
            "response_id": response.id,
            "response_uuid": str(response.uuid),
            "message": "Business response added successfully"
        }
    
    def add_review_media(
        self,
        review_id: int,
        media_data: List[ReviewMediaCreate],
        customer_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Add media attachments to a review"""
        
        review = self.db.query(Review).filter(Review.id == review_id).first()
        if not review:
            raise NotFoundError(f"Review {review_id} not found")
        
        # Check permissions
        if customer_id and review.customer_id != customer_id:
            raise PermissionError("Cannot add media to another customer's review")
        
        media_items = []
        for media_item in media_data:
            media = ReviewMedia(
                uuid=uuid.uuid4(),
                review_id=review_id,
                media_type=media_item.media_type,
                file_path=media_item.file_path,
                file_name=media_item.file_name,
                file_size=media_item.file_size,
                mime_type=media_item.mime_type,
                width=media_item.width,
                height=media_item.height,
                duration=media_item.duration,
                is_processed=False,
                is_approved=True  # Auto-approve for now
            )
            
            self.db.add(media)
            media_items.append(media)
        
        # Update review media flags
        review.media_count = len(media_data)
        review.has_images = any(m.media_type == "image" for m in media_data)
        review.has_videos = any(m.media_type == "video" for m in media_data)
        
        self.db.commit()
        
        logger.info(f"Added {len(media_data)} media items to review {review_id}")
        
        return {
            "success": True,
            "media_count": len(media_items),
            "media_ids": [media.id for media in media_items],
            "message": "Media added successfully"
        }
    
    def get_review_aggregates(
        self,
        entity_type: str,
        entity_id: int,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Get aggregated review statistics for an entity"""
        
        # Try to get existing aggregates
        aggregate = self.db.query(ReviewAggregate).filter(
            and_(
                ReviewAggregate.entity_type == entity_type,
                ReviewAggregate.entity_id == entity_id
            )
        ).first()
        
        # Check if refresh is needed
        if not aggregate or force_refresh or \
           (aggregate.last_calculated_at < datetime.utcnow() - timedelta(hours=1)):
            
            # Calculate fresh aggregates
            aggregate = self._calculate_review_aggregates(entity_type, entity_id)
        
        return {
            "entity_type": aggregate.entity_type,
            "entity_id": aggregate.entity_id,
            "total_reviews": aggregate.total_reviews,
            "average_rating": aggregate.average_rating,
            "rating_distribution": aggregate.rating_distribution or {},
            "rating_counts": {
                "1": aggregate.rating_1_count,
                "2": aggregate.rating_2_count,
                "3": aggregate.rating_3_count,
                "4": aggregate.rating_4_count,
                "5": aggregate.rating_5_count
            },
            "verified_reviews_count": aggregate.verified_reviews_count,
            "featured_reviews_count": aggregate.featured_reviews_count,
            "with_media_count": aggregate.with_media_count,
            "sentiment_distribution": aggregate.sentiment_distribution or {},
            "positive_sentiment_percentage": aggregate.positive_sentiment_percentage,
            "last_calculated_at": aggregate.last_calculated_at
        }
    
    # Private helper methods
    
    def _validate_review_eligibility(self, review_data: ReviewCreate) -> None:
        """Validate if customer can create this review"""
        
        # Add custom validation logic here
        if review_data.order_id:
            # Validate order exists and belongs to customer
            # This would integrate with the orders system
            pass
        
        if review_data.product_id:
            # Validate product exists
            # This would integrate with the products system
            pass
    
    def _check_duplicate_review(self, review_data: ReviewCreate) -> Optional[Review]:
        """Check if customer already reviewed this item"""
        
        filters = [Review.customer_id == review_data.customer_id]
        
        if review_data.product_id:
            filters.append(Review.product_id == review_data.product_id)
        elif review_data.service_id:
            filters.append(Review.service_id == review_data.service_id)
        elif review_data.order_id:
            filters.append(Review.order_id == review_data.order_id)
        
        return self.db.query(Review).filter(and_(*filters)).first()
    
    def _verify_purchase(
        self,
        customer_id: int,
        order_id: int,
        product_id: Optional[int]
    ) -> bool:
        """Verify that customer actually purchased the product"""
        
        # This would integrate with the orders system
        # For now, return True if order_id is provided
        return order_id is not None
    
    def _schedule_sentiment_analysis(self, review_id: int) -> None:
        """Schedule sentiment analysis for a review"""
        
        # This would integrate with a sentiment analysis service
        # For now, just log the action
        logger.info(f"Scheduled sentiment analysis for review {review_id}")
    
    def _update_review_aggregates(self, review: Review) -> None:
        """Update review aggregates for the reviewed entity"""
        
        if review.product_id:
            self._calculate_review_aggregates("product", review.product_id)
        elif review.service_id:
            self._calculate_review_aggregates("service", review.service_id)
    
    def _calculate_review_aggregates(
        self,
        entity_type: str,
        entity_id: int
    ) -> ReviewAggregate:
        """Calculate and store review aggregates"""
        
        # Build base query for approved reviews
        base_query = self.db.query(Review).filter(Review.status == ReviewStatus.APPROVED)
        
        if entity_type == "product":
            base_query = base_query.filter(Review.product_id == entity_id)
        elif entity_type == "service":
            base_query = base_query.filter(Review.service_id == entity_id)
        else:
            raise ValueError(f"Unsupported entity type: {entity_type}")
        
        # Calculate metrics
        total_reviews = base_query.count()
        
        if total_reviews == 0:
            # Create empty aggregate
            aggregate_data = {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "total_reviews": 0,
                "average_rating": 0.0,
                "rating_1_count": 0,
                "rating_2_count": 0,
                "rating_3_count": 0,
                "rating_4_count": 0,
                "rating_5_count": 0,
                "verified_reviews_count": 0,
                "featured_reviews_count": 0,
                "with_media_count": 0,
                "positive_sentiment_percentage": 0.0
            }
        else:
            # Calculate actual metrics
            avg_rating = base_query.with_entities(func.avg(Review.rating)).scalar() or 0.0
            
            rating_counts = {
                1: base_query.filter(Review.rating >= 1.0, Review.rating < 2.0).count(),
                2: base_query.filter(Review.rating >= 2.0, Review.rating < 3.0).count(),
                3: base_query.filter(Review.rating >= 3.0, Review.rating < 4.0).count(),
                4: base_query.filter(Review.rating >= 4.0, Review.rating < 5.0).count(),
                5: base_query.filter(Review.rating == 5.0).count()
            }
            
            verified_count = base_query.filter(Review.is_verified_purchase == True).count()
            featured_count = base_query.filter(Review.is_featured == True).count()
            with_media_count = base_query.filter(Review.media_count > 0).count()
            
            # Calculate sentiment distribution
            positive_sentiments = base_query.filter(
                Review.sentiment_score.in_([SentimentScore.POSITIVE, SentimentScore.VERY_POSITIVE])
            ).count()
            positive_percentage = (positive_sentiments / total_reviews) * 100 if total_reviews > 0 else 0.0
            
            aggregate_data = {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "total_reviews": total_reviews,
                "average_rating": round(avg_rating, 2),
                "rating_distribution": rating_counts,
                "rating_1_count": rating_counts[1],
                "rating_2_count": rating_counts[2],
                "rating_3_count": rating_counts[3],
                "rating_4_count": rating_counts[4],
                "rating_5_count": rating_counts[5],
                "verified_reviews_count": verified_count,
                "featured_reviews_count": featured_count,
                "with_media_count": with_media_count,
                "positive_sentiment_percentage": round(positive_percentage, 2)
            }
        
        # Get or create aggregate record
        aggregate = self.db.query(ReviewAggregate).filter(
            and_(
                ReviewAggregate.entity_type == entity_type,
                ReviewAggregate.entity_id == entity_id
            )
        ).first()
        
        if aggregate:
            # Update existing aggregate
            for key, value in aggregate_data.items():
                setattr(aggregate, key, value)
        else:
            # Create new aggregate
            aggregate = ReviewAggregate(**aggregate_data)
            self.db.add(aggregate)
        
        aggregate.last_calculated_at = datetime.utcnow()
        self.db.commit()
        
        return aggregate
    
    def _format_review_response(self, review: Review) -> ReviewResponse:
        """Format review for API response"""
        
        return ReviewResponse(
            id=review.id,
            uuid=str(review.uuid),
            review_type=review.review_type,
            status=review.status,
            source=review.source,
            customer_id=review.customer_id,
            order_id=review.order_id,
            product_id=review.product_id,
            service_id=review.service_id,
            title=review.title,
            content=review.content,
            rating=review.rating,
            is_verified_purchase=review.is_verified_purchase,
            is_anonymous=review.is_anonymous,
            reviewer_name=review.reviewer_name,
            helpful_votes=review.helpful_votes,
            not_helpful_votes=review.not_helpful_votes,
            total_votes=review.total_votes,
            helpful_percentage=review.helpful_percentage,
            sentiment_score=review.sentiment_score,
            sentiment_confidence=review.sentiment_confidence,
            is_featured=review.is_featured,
            has_images=review.has_images,
            has_videos=review.has_videos,
            media_count=review.media_count,
            has_business_response=review.has_business_response,
            business_response_at=review.business_response_at,
            created_at=review.created_at,
            updated_at=review.updated_at
        )
    
    def _format_review_summary(self, review: Review) -> ReviewSummary:
        """Format review summary for list responses"""
        
        return ReviewSummary(
            id=review.id,
            uuid=str(review.uuid),
            review_type=review.review_type,
            status=review.status,
            title=review.title,
            rating=review.rating,
            customer_id=review.customer_id,
            product_id=review.product_id,
            is_verified_purchase=review.is_verified_purchase,
            helpful_votes=review.helpful_votes,
            sentiment_score=review.sentiment_score,
            created_at=review.created_at
        )