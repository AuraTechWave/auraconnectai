# backend/modules/feedback/services/aggregation_service.py

import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc, text
from dataclasses import dataclass
import json

from backend.modules.feedback.models.feedback_models import (
    Review, ReviewAggregate, ReviewStatus, SentimentScore, ReviewType
)
from backend.modules.feedback.services.sentiment_service import sentiment_service

logger = logging.getLogger(__name__)


@dataclass
class AggregationResult:
    """Result of review aggregation calculation"""
    entity_type: str
    entity_id: int
    total_reviews: int
    average_rating: float
    rating_distribution: Dict[str, int]
    sentiment_distribution: Dict[str, int]
    quality_score: float
    trending_score: float
    last_updated: datetime


class ReviewAggregationService:
    """Service for aggregating and scoring review data"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def calculate_aggregates_for_entity(
        self,
        entity_type: str,
        entity_id: int,
        force_recalculation: bool = False
    ) -> AggregationResult:
        """Calculate comprehensive aggregates for a specific entity"""
        
        # Check if we need to recalculate
        existing_aggregate = self.db.query(ReviewAggregate).filter(
            and_(
                ReviewAggregate.entity_type == entity_type,
                ReviewAggregate.entity_id == entity_id
            )
        ).first()
        
        if not force_recalculation and existing_aggregate:
            # Check if data is fresh (within last hour)
            if existing_aggregate.last_calculated_at > datetime.utcnow() - timedelta(hours=1):
                return self._format_aggregation_result(existing_aggregate)
        
        # Get all approved reviews for this entity
        reviews_query = self._get_entity_reviews_query(entity_type, entity_id)
        reviews = reviews_query.all()
        
        if not reviews:
            # Create empty aggregate
            return self._create_empty_aggregate(entity_type, entity_id)
        
        # Calculate all metrics
        basic_metrics = self._calculate_basic_metrics(reviews)
        sentiment_metrics = self._calculate_sentiment_metrics(reviews)
        quality_metrics = self._calculate_quality_metrics(reviews)
        trending_metrics = self._calculate_trending_metrics(reviews)
        
        # Combine all metrics
        aggregate_data = {
            **basic_metrics,
            **sentiment_metrics,
            **quality_metrics,
            **trending_metrics
        }
        
        # Update or create aggregate record
        if existing_aggregate:
            for key, value in aggregate_data.items():
                setattr(existing_aggregate, key, value)
            existing_aggregate.last_calculated_at = datetime.utcnow()
            aggregate = existing_aggregate
        else:
            aggregate_data.update({
                "entity_type": entity_type,
                "entity_id": entity_id,
                "last_calculated_at": datetime.utcnow()
            })
            aggregate = ReviewAggregate(**aggregate_data)
            self.db.add(aggregate)
        
        self.db.commit()
        
        logger.info(f"Updated aggregates for {entity_type} {entity_id}: {basic_metrics['total_reviews']} reviews")
        
        return self._format_aggregation_result(aggregate)
    
    def bulk_update_aggregates(
        self,
        entity_type: str,
        entity_ids: List[int] = None,
        batch_size: int = 50
    ) -> Dict[str, Any]:
        """Update aggregates for multiple entities in batches"""
        
        start_time = datetime.utcnow()
        
        # Get entity IDs to update if not provided
        if entity_ids is None:
            entity_ids = self._get_entities_needing_update(entity_type)
        
        if not entity_ids:
            return {
                "success": True,
                "message": "No entities need updating",
                "updated_count": 0,
                "processing_time_seconds": 0
            }
        
        # Process in batches
        updated_count = 0
        errors = []
        
        for i in range(0, len(entity_ids), batch_size):
            batch = entity_ids[i:i + batch_size]
            
            try:
                batch_results = self._update_batch_aggregates(entity_type, batch)
                updated_count += batch_results["updated_count"]
                errors.extend(batch_results.get("errors", []))
                
            except Exception as e:
                logger.error(f"Error updating batch {i//batch_size + 1}: {e}")
                errors.append(f"Batch {i//batch_size + 1}: {str(e)}")
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        return {
            "success": True,
            "updated_count": updated_count,
            "total_requested": len(entity_ids),
            "batches_processed": (len(entity_ids) + batch_size - 1) // batch_size,
            "processing_time_seconds": processing_time,
            "errors": errors
        }
    
    def get_top_rated_entities(
        self,
        entity_type: str,
        limit: int = 10,
        min_reviews: int = 5
    ) -> List[Dict[str, Any]]:
        """Get top-rated entities with minimum review count"""
        
        aggregates = self.db.query(ReviewAggregate).filter(
            and_(
                ReviewAggregate.entity_type == entity_type,
                ReviewAggregate.total_reviews >= min_reviews
            )
        ).order_by(
            desc(ReviewAggregate.average_rating),
            desc(ReviewAggregate.total_reviews)
        ).limit(limit).all()
        
        return [
            {
                "entity_id": agg.entity_id,
                "entity_type": agg.entity_type,
                "average_rating": agg.average_rating,
                "total_reviews": agg.total_reviews,
                "positive_sentiment_percentage": agg.positive_sentiment_percentage,
                "last_updated": agg.last_calculated_at
            }
            for agg in aggregates
        ]
    
    def get_trending_entities(
        self,
        entity_type: str,
        limit: int = 10,
        days_back: int = 7
    ) -> List[Dict[str, Any]]:
        """Get trending entities based on recent activity and ratings"""
        
        # Calculate trending score based on recent reviews and rating momentum
        trending_query = text("""
            SELECT 
                CASE 
                    WHEN :entity_type = 'product' THEN r.product_id
                    WHEN :entity_type = 'service' THEN r.service_id
                    ELSE 0
                END as entity_id,
                COUNT(*) as recent_reviews,
                AVG(r.rating) as recent_avg_rating,
                COUNT(CASE WHEN r.created_at >= :week_ago THEN 1 END) as last_week_reviews,
                COUNT(CASE WHEN r.created_at >= :two_weeks_ago AND r.created_at < :week_ago THEN 1 END) as prev_week_reviews
            FROM reviews r
            WHERE r.status = 'approved'
                AND r.created_at >= :cutoff_date
                AND (
                    (:entity_type = 'product' AND r.product_id IS NOT NULL) OR
                    (:entity_type = 'service' AND r.service_id IS NOT NULL)
                )
            GROUP BY entity_id
            HAVING entity_id IS NOT NULL AND entity_id > 0
            ORDER BY 
                (recent_reviews * recent_avg_rating * 
                 CASE WHEN prev_week_reviews > 0 THEN last_week_reviews / prev_week_reviews ELSE last_week_reviews END
                ) DESC
            LIMIT :limit
        """)
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        week_ago = datetime.utcnow() - timedelta(days=7)
        two_weeks_ago = datetime.utcnow() - timedelta(days=14)
        
        result = self.db.execute(trending_query, {
            "entity_type": entity_type,
            "cutoff_date": cutoff_date,
            "week_ago": week_ago,
            "two_weeks_ago": two_weeks_ago,
            "limit": limit
        })
        
        trending_items = []
        for row in result:
            # Get full aggregate data for each trending item
            aggregate = self.db.query(ReviewAggregate).filter(
                and_(
                    ReviewAggregate.entity_type == entity_type,
                    ReviewAggregate.entity_id == row.entity_id
                )
            ).first()
            
            if aggregate:
                growth_rate = 0
                if row.prev_week_reviews > 0:
                    growth_rate = ((row.last_week_reviews - row.prev_week_reviews) / row.prev_week_reviews) * 100
                
                trending_items.append({
                    "entity_id": row.entity_id,
                    "entity_type": entity_type,
                    "average_rating": aggregate.average_rating,
                    "total_reviews": aggregate.total_reviews,
                    "recent_reviews": row.recent_reviews,
                    "recent_avg_rating": float(row.recent_avg_rating),
                    "growth_rate": round(growth_rate, 2),
                    "trending_score": row.recent_reviews * row.recent_avg_rating
                })
        
        return trending_items
    
    def get_review_insights(
        self,
        entity_type: str,
        entity_id: int
    ) -> Dict[str, Any]:
        """Get detailed insights for an entity's reviews"""
        
        reviews = self._get_entity_reviews_query(entity_type, entity_id).all()
        
        if not reviews:
            return {"error": "No reviews found for this entity"}
        
        # Basic insights
        total_reviews = len(reviews)
        avg_rating = sum(r.rating for r in reviews) / total_reviews
        
        # Rating distribution
        rating_dist = {}
        for i in range(1, 6):
            count = sum(1 for r in reviews if int(r.rating) == i)
            rating_dist[str(i)] = count
        
        # Sentiment analysis
        sentiment_counts = {}
        for review in reviews:
            if review.sentiment_score:
                sentiment = review.sentiment_score.value
                sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
        
        # Temporal trends (last 6 months by month)
        monthly_trends = []
        for i in range(6):
            month_start = datetime.utcnow().replace(day=1) - timedelta(days=30*i)
            month_end = month_start + timedelta(days=31)
            
            month_reviews = [
                r for r in reviews 
                if month_start <= r.created_at < month_end
            ]
            
            if month_reviews:
                monthly_trends.append({
                    "month": month_start.strftime("%Y-%m"),
                    "review_count": len(month_reviews),
                    "average_rating": sum(r.rating for r in month_reviews) / len(month_reviews)
                })
        
        monthly_trends.reverse()  # Oldest to newest
        
        # Common keywords from positive and negative reviews
        positive_reviews = [r for r in reviews if r.rating >= 4.0]
        negative_reviews = [r for r in reviews if r.rating <= 2.0]
        
        positive_keywords = self._extract_keywords([r.content for r in positive_reviews])
        negative_keywords = self._extract_keywords([r.content for r in negative_reviews])
        
        # Verification insights
        verified_reviews = [r for r in reviews if r.is_verified_purchase]
        verification_rate = len(verified_reviews) / total_reviews * 100 if total_reviews > 0 else 0
        
        verified_avg_rating = sum(r.rating for r in verified_reviews) / len(verified_reviews) if verified_reviews else 0
        unverified_avg_rating = sum(r.rating for r in reviews if not r.is_verified_purchase) / (total_reviews - len(verified_reviews)) if (total_reviews - len(verified_reviews)) > 0 else 0
        
        return {
            "overview": {
                "total_reviews": total_reviews,
                "average_rating": round(avg_rating, 2),
                "verification_rate": round(verification_rate, 1),
                "verified_avg_rating": round(verified_avg_rating, 2),
                "unverified_avg_rating": round(unverified_avg_rating, 2)
            },
            "rating_distribution": rating_dist,
            "sentiment_distribution": sentiment_counts,
            "temporal_trends": monthly_trends,
            "keyword_insights": {
                "positive_keywords": positive_keywords[:10],
                "negative_keywords": negative_keywords[:10]
            },
            "quality_metrics": {
                "reviews_with_media": sum(1 for r in reviews if r.media_count > 0),
                "average_content_length": sum(len(r.content) for r in reviews) / total_reviews,
                "helpful_reviews": sum(1 for r in reviews if r.helpful_votes > r.not_helpful_votes)
            }
        }
    
    async def update_aggregates_async(
        self,
        entity_type: str,
        entity_ids: List[int],
        batch_size: int = 20
    ) -> Dict[str, Any]:
        """Asynchronously update aggregates for better performance"""
        
        start_time = datetime.utcnow()
        
        # Process in smaller batches asynchronously
        tasks = []
        for i in range(0, len(entity_ids), batch_size):
            batch = entity_ids[i:i + batch_size]
            task = asyncio.create_task(
                self._update_batch_async(entity_type, batch)
            )
            tasks.append(task)
        
        # Wait for all batches to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Aggregate results
        total_updated = 0
        errors = []
        
        for result in results:
            if isinstance(result, Exception):
                errors.append(str(result))
            else:
                total_updated += result.get("updated_count", 0)
                errors.extend(result.get("errors", []))
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        return {
            "success": True,
            "updated_count": total_updated,
            "total_requested": len(entity_ids),
            "processing_time_seconds": processing_time,
            "errors": errors
        }
    
    # Private helper methods
    
    def _get_entity_reviews_query(self, entity_type: str, entity_id: int):
        """Get query for reviews of a specific entity"""
        
        query = self.db.query(Review).filter(Review.status == ReviewStatus.APPROVED)
        
        if entity_type == "product":
            query = query.filter(Review.product_id == entity_id)
        elif entity_type == "service":
            query = query.filter(Review.service_id == entity_id)
        else:
            raise ValueError(f"Unsupported entity type: {entity_type}")
        
        return query.order_by(Review.created_at.desc())
    
    def _calculate_basic_metrics(self, reviews: List[Review]) -> Dict[str, Any]:
        """Calculate basic review metrics"""
        
        total_reviews = len(reviews)
        
        if total_reviews == 0:
            return {
                "total_reviews": 0,
                "average_rating": 0.0,
                "rating_1_count": 0,
                "rating_2_count": 0,
                "rating_3_count": 0,
                "rating_4_count": 0,
                "rating_5_count": 0,
                "verified_reviews_count": 0,
                "featured_reviews_count": 0,
                "with_media_count": 0
            }
        
        # Calculate average rating
        total_rating = sum(review.rating for review in reviews)
        average_rating = total_rating / total_reviews
        
        # Count ratings by star level
        rating_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for review in reviews:
            star_level = min(5, max(1, int(round(review.rating))))
            rating_counts[star_level] += 1
        
        # Count special types
        verified_count = sum(1 for review in reviews if review.is_verified_purchase)
        featured_count = sum(1 for review in reviews if review.is_featured)
        with_media_count = sum(1 for review in reviews if review.media_count > 0)
        
        # Calculate rating distribution
        rating_distribution = {str(k): v for k, v in rating_counts.items()}
        
        return {
            "total_reviews": total_reviews,
            "average_rating": round(average_rating, 2),
            "rating_distribution": rating_distribution,
            "rating_1_count": rating_counts[1],
            "rating_2_count": rating_counts[2],
            "rating_3_count": rating_counts[3],
            "rating_4_count": rating_counts[4],
            "rating_5_count": rating_counts[5],
            "verified_reviews_count": verified_count,
            "featured_reviews_count": featured_count,
            "with_media_count": with_media_count
        }
    
    def _calculate_sentiment_metrics(self, reviews: List[Review]) -> Dict[str, Any]:
        """Calculate sentiment-based metrics"""
        
        if not reviews:
            return {
                "sentiment_distribution": {},
                "positive_sentiment_percentage": 0.0
            }
        
        # Count sentiments
        sentiment_counts = {}
        for review in reviews:
            if review.sentiment_score:
                sentiment = review.sentiment_score.value
                sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
        
        # Calculate positive sentiment percentage
        positive_sentiments = sentiment_counts.get("positive", 0) + sentiment_counts.get("very_positive", 0)
        positive_percentage = (positive_sentiments / len(reviews)) * 100
        
        return {
            "sentiment_distribution": sentiment_counts,
            "positive_sentiment_percentage": round(positive_percentage, 2)
        }
    
    def _calculate_quality_metrics(self, reviews: List[Review]) -> Dict[str, Any]:
        """Calculate quality-based metrics"""
        
        if not reviews:
            return {}
        
        # Average content length
        avg_content_length = sum(len(review.content) for review in reviews) / len(reviews)
        
        # Helpful review ratio
        helpful_reviews = sum(1 for review in reviews if review.helpful_votes > review.not_helpful_votes)
        helpful_ratio = helpful_reviews / len(reviews) * 100
        
        # Reviews with business responses
        business_response_count = sum(1 for review in reviews if review.has_business_response)
        business_response_rate = business_response_count / len(reviews) * 100
        
        return {
            "quality_metrics": {
                "average_content_length": round(avg_content_length, 1),
                "helpful_review_percentage": round(helpful_ratio, 1),
                "business_response_rate": round(business_response_rate, 1)
            }
        }
    
    def _calculate_trending_metrics(self, reviews: List[Review]) -> Dict[str, Any]:
        """Calculate trending and momentum metrics"""
        
        if not reviews:
            return {"trending_score": 0.0}
        
        # Recent activity (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_reviews = [r for r in reviews if r.created_at >= thirty_days_ago]
        
        # Rating momentum (comparing recent vs older reviews)
        if len(recent_reviews) >= 3 and len(reviews) > len(recent_reviews):
            recent_avg = sum(r.rating for r in recent_reviews) / len(recent_reviews)
            older_reviews = [r for r in reviews if r.created_at < thirty_days_ago]
            older_avg = sum(r.rating for r in older_reviews) / len(older_reviews)
            momentum = recent_avg - older_avg
        else:
            momentum = 0.0
        
        # Calculate trending score (volume + recency + momentum)
        volume_score = min(len(recent_reviews) / 10, 1.0)  # Normalize to 0-1
        recency_score = len(recent_reviews) / len(reviews)
        momentum_score = max(0, momentum / 5.0)  # Normalize momentum
        
        trending_score = (volume_score * 0.4) + (recency_score * 0.4) + (momentum_score * 0.2)
        
        return {
            "trending_score": round(trending_score, 3),
            "recent_reviews_count": len(recent_reviews),
            "rating_momentum": round(momentum, 2)
        }
    
    def _create_empty_aggregate(self, entity_type: str, entity_id: int) -> AggregationResult:
        """Create empty aggregate for entities with no reviews"""
        
        empty_data = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "total_reviews": 0,
            "average_rating": 0.0,
            "rating_distribution": {},
            "rating_1_count": 0,
            "rating_2_count": 0,
            "rating_3_count": 0,
            "rating_4_count": 0,
            "rating_5_count": 0,
            "verified_reviews_count": 0,
            "featured_reviews_count": 0,
            "with_media_count": 0,
            "sentiment_distribution": {},
            "positive_sentiment_percentage": 0.0,
            "last_calculated_at": datetime.utcnow()
        }
        
        # Check if aggregate already exists
        existing = self.db.query(ReviewAggregate).filter(
            and_(
                ReviewAggregate.entity_type == entity_type,
                ReviewAggregate.entity_id == entity_id
            )
        ).first()
        
        if existing:
            for key, value in empty_data.items():
                if key not in ["entity_type", "entity_id"]:
                    setattr(existing, key, value)
        else:
            aggregate = ReviewAggregate(**empty_data)
            self.db.add(aggregate)
        
        self.db.commit()
        
        return AggregationResult(
            entity_type=entity_type,
            entity_id=entity_id,
            total_reviews=0,
            average_rating=0.0,
            rating_distribution={},
            sentiment_distribution={},
            quality_score=0.0,
            trending_score=0.0,
            last_updated=datetime.utcnow()
        )
    
    def _get_entities_needing_update(self, entity_type: str) -> List[int]:
        """Get entities that need aggregate updates"""
        
        # Get entities with reviews but stale aggregates (older than 6 hours)
        cutoff_time = datetime.utcnow() - timedelta(hours=6)
        
        if entity_type == "product":
            field = "product_id"
        elif entity_type == "service":
            field = "service_id"
        else:
            return []
        
        # Find entities with recent reviews but stale aggregates
        query = text(f"""
            SELECT DISTINCT r.{field} as entity_id
            FROM reviews r
            LEFT JOIN review_aggregates ra ON ra.entity_type = :entity_type 
                AND ra.entity_id = r.{field}
            WHERE r.{field} IS NOT NULL
                AND r.status = 'approved'
                AND (ra.last_calculated_at IS NULL OR ra.last_calculated_at < :cutoff_time)
                AND r.updated_at >= :cutoff_time
        """)
        
        result = self.db.execute(query, {
            "entity_type": entity_type,
            "cutoff_time": cutoff_time
        })
        
        return [row.entity_id for row in result]
    
    def _update_batch_aggregates(self, entity_type: str, entity_ids: List[int]) -> Dict[str, Any]:
        """Update aggregates for a batch of entities"""
        
        updated_count = 0
        errors = []
        
        for entity_id in entity_ids:
            try:
                self.calculate_aggregates_for_entity(entity_type, entity_id, force_recalculation=True)
                updated_count += 1
            except Exception as e:
                logger.error(f"Error updating {entity_type} {entity_id}: {e}")
                errors.append(f"{entity_type} {entity_id}: {str(e)}")
        
        return {
            "updated_count": updated_count,
            "errors": errors
        }
    
    async def _update_batch_async(self, entity_type: str, entity_ids: List[int]) -> Dict[str, Any]:
        """Async version of batch update"""
        
        # For now, just wrap the sync version
        # In production, this could use async database operations
        return await asyncio.get_event_loop().run_in_executor(
            None,
            self._update_batch_aggregates,
            entity_type,
            entity_ids
        )
    
    def _extract_keywords(self, texts: List[str]) -> List[str]:
        """Extract common keywords from review texts"""
        
        if not texts:
            return []
        
        # Simple keyword extraction
        all_words = []
        for text in texts:
            # Clean and split text
            words = text.lower().split()
            # Filter out common words and short words
            filtered_words = [
                word for word in words 
                if len(word) > 3 and word not in {
                    "the", "and", "for", "are", "but", "not", "you", "all", "can", "had", "was", "one", "our", "out", "day", "get", "has", "him", "his", "how", "its", "may", "new", "now", "old", "see", "two", "way", "who", "boy", "did", "she", "use", "her", "now", "air", "any", "ask", "big", "end", "far", "got", "lot", "man", "new", "old", "put", "run", "say", "set", "try", "use", "way", "win", "yes", "yet"
                }
            ]
            all_words.extend(filtered_words)
        
        # Count word frequency
        word_counts = {}
        for word in all_words:
            word_counts[word] = word_counts.get(word, 0) + 1
        
        # Return top keywords
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        return [word for word, count in sorted_words if count > 1]
    
    def _format_aggregation_result(self, aggregate: ReviewAggregate) -> AggregationResult:
        """Format aggregate model for response"""
        
        return AggregationResult(
            entity_type=aggregate.entity_type,
            entity_id=aggregate.entity_id,
            total_reviews=aggregate.total_reviews,
            average_rating=aggregate.average_rating,
            rating_distribution=aggregate.rating_distribution or {},
            sentiment_distribution=aggregate.sentiment_distribution or {},
            quality_score=0.0,  # Could be calculated from quality metrics
            trending_score=0.0,  # Could be calculated from trending metrics
            last_updated=aggregate.last_calculated_at
        )


# Service factory function
def create_aggregation_service(db: Session) -> ReviewAggregationService:
    """Create an aggregation service instance"""
    return ReviewAggregationService(db)