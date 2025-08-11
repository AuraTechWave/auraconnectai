# backend/modules/insights/services/rating_service.py

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, case
import logging

from ..models.insight_models import (
    Insight, InsightRating, InsightAction, InsightStatus
)
from ..schemas.insight_schemas import InsightRatingCreate, InsightActionCreate
from core.error_handling import NotFoundError, ConflictError

logger = logging.getLogger(__name__)


class InsightRatingService:
    """Service for managing insight ratings and feedback"""
    
    RATING_OPTIONS = ["useful", "irrelevant", "needs_followup"]
    ACTION_TYPES = ["viewed", "shared", "exported", "implemented", "discussed"]
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_rating(
        self,
        insight_id: int,
        user_id: int,
        rating_data: InsightRatingCreate
    ) -> InsightRating:
        """Create or update a rating for an insight"""
        
        # Check if user already rated this insight
        existing_rating = self.db.query(InsightRating).filter(
            InsightRating.insight_id == insight_id,
            InsightRating.user_id == user_id
        ).first()
        
        if existing_rating:
            raise ConflictError(
                "You have already rated this insight",
                {"existing_rating": existing_rating.rating}
            )
        
        # Create new rating
        rating = InsightRating(
            insight_id=insight_id,
            user_id=user_id,
            rating=rating_data.rating,
            comment=rating_data.comment
        )
        
        self.db.add(rating)
        self.db.commit()
        self.db.refresh(rating)
        
        # Update insight status based on ratings
        self._update_insight_status_from_ratings(insight_id)
        
        return rating
    
    def get_insight_ratings(self, insight_id: int) -> Dict[str, Any]:
        """Get all ratings for an insight"""
        
        ratings = self.db.query(InsightRating).filter(
            InsightRating.insight_id == insight_id
        ).options(joinedload(InsightRating.user)).all()
        
        # Aggregate ratings
        rating_counts = {rating: 0 for rating in self.RATING_OPTIONS}
        rating_details = []
        
        for rating in ratings:
            rating_counts[rating.rating] += 1
            rating_details.append({
                "user_id": rating.user_id,
                "user_name": rating.user.name if rating.user else "Unknown",
                "rating": rating.rating,
                "comment": rating.comment,
                "created_at": rating.created_at
            })
        
        total_ratings = sum(rating_counts.values())
        
        return {
            "total_ratings": total_ratings,
            "rating_counts": rating_counts,
            "rating_percentages": {
                rating: (count / total_ratings * 100) if total_ratings > 0 else 0
                for rating, count in rating_counts.items()
            },
            "ratings": rating_details
        }
    
    def _update_insight_status_from_ratings(self, insight_id: int):
        """Update insight status based on ratings"""
        
        # Get rating counts
        rating_counts = self.db.query(
            InsightRating.rating,
            func.count(InsightRating.id).label('count')
        ).filter(
            InsightRating.insight_id == insight_id
        ).group_by(InsightRating.rating).all()
        
        rating_dict = {row.rating: row.count for row in rating_counts}
        total_ratings = sum(rating_dict.values())
        
        if total_ratings >= 3:  # Minimum ratings threshold
            irrelevant_count = rating_dict.get("irrelevant", 0)
            
            # Auto-dismiss if majority find it irrelevant
            if irrelevant_count / total_ratings > 0.6:
                insight = self.db.query(Insight).filter(
                    Insight.id == insight_id
                ).first()
                
                if insight and insight.status == InsightStatus.ACTIVE:
                    insight.status = InsightStatus.DISMISSED
                    self.db.commit()
                    
                    logger.info(
                        f"Insight {insight_id} auto-dismissed due to {irrelevant_count}/{total_ratings} "
                        f"irrelevant ratings"
                    )