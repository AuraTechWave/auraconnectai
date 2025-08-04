# backend/modules/insights/services/rating_service.py

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, case
from sqlalchemy.orm import selectinload
import logging

from ..models.insight_models import (
    Insight, InsightRating, InsightAction, InsightStatus
)
from ..schemas.insight_schemas import InsightRatingCreate, InsightActionCreate
from ..metrics.insight_metrics import insight_metrics
from core.exceptions import BusinessLogicError, ResourceNotFoundError

logger = logging.getLogger(__name__)


class InsightRatingService:
    """Service for managing insight ratings and feedback"""
    
    RATING_OPTIONS = ["useful", "irrelevant", "needs_followup"]
    ACTION_TYPES = ["viewed", "shared", "exported", "implemented", "discussed"]
    
    async def rate_insight(
        self,
        db: AsyncSession,
        restaurant_id: int,
        insight_id: int,
        user_id: int,
        rating_data: InsightRatingCreate
    ) -> InsightRating:
        """Rate an insight"""
        
        # Validate insight exists and belongs to restaurant
        insight = await self._get_insight(db, insight_id, restaurant_id)
        
        # Validate rating value
        if rating_data.rating not in self.RATING_OPTIONS:
            raise BusinessLogicError(
                f"Invalid rating. Must be one of: {', '.join(self.RATING_OPTIONS)}"
            )
        
        # Check if user already rated this insight
        existing_rating = await db.execute(
            select(InsightRating).where(
                and_(
                    InsightRating.insight_id == insight_id,
                    InsightRating.user_id == user_id
                )
            )
        )
        existing = existing_rating.scalar_one_or_none()
        
        if existing:
            # Update existing rating
            existing.rating = rating_data.rating
            existing.comment = rating_data.comment
            rating = existing
        else:
            # Create new rating
            rating = InsightRating(
                insight_id=insight_id,
                user_id=user_id,
                rating=rating_data.rating,
                comment=rating_data.comment
            )
            db.add(rating)
        
        await db.commit()
        await db.refresh(rating)
        
        # Record metrics
        insight_metrics.record_insight_rating(
            rating_data.rating,
            insight.type,
            insight.domain
        )
        
        # Update insight status based on ratings
        await self._update_insight_status_from_ratings(db, insight)
        
        return rating
    
    async def record_action(
        self,
        db: AsyncSession,
        restaurant_id: int,
        insight_id: int,
        user_id: int,
        action_data: InsightActionCreate
    ) -> InsightAction:
        """Record an action taken on an insight"""
        
        # Validate insight
        insight = await self._get_insight(db, insight_id, restaurant_id)
        
        # Validate action type
        if action_data.action_type not in self.ACTION_TYPES:
            raise BusinessLogicError(
                f"Invalid action type. Must be one of: {', '.join(self.ACTION_TYPES)}"
            )
        
        # Create action record
        action = InsightAction(
            insight_id=insight_id,
            user_id=user_id,
            action_type=action_data.action_type,
            action_details=action_data.action_details or {}
        )
        
        db.add(action)
        
        # Auto-acknowledge insight on first view
        if action_data.action_type == "viewed" and not insight.acknowledged_at:
            insight.acknowledged_by_id = user_id
            insight.acknowledged_at = datetime.utcnow()
            
            # Record acknowledgment metrics
            time_to_ack = (datetime.utcnow() - insight.created_at).total_seconds() / 3600
            insight_metrics.record_insight_acknowledged(
                insight.type,
                insight.severity,
                insight.domain,
                time_to_ack
            )
        
        # Mark as resolved if implemented
        if action_data.action_type == "implemented" and insight.status != InsightStatus.RESOLVED:
            insight.status = InsightStatus.RESOLVED
            insight.resolved_by_id = user_id
            insight.resolved_at = datetime.utcnow()
            insight.resolution_notes = action_data.action_details.get("notes", "Implemented")
            
            # Record resolution metrics
            time_to_resolve = (datetime.utcnow() - insight.created_at).total_seconds() / 3600
            insight_metrics.record_insight_resolved(
                insight.type,
                insight.severity,
                insight.domain,
                time_to_resolve
            )
        
        await db.commit()
        await db.refresh(action)
        
        return action
    
    async def get_insight_ratings(
        self,
        db: AsyncSession,
        restaurant_id: int,
        insight_id: int
    ) -> Dict[str, Any]:
        """Get all ratings for an insight"""
        
        # Validate insight
        await self._get_insight(db, insight_id, restaurant_id)
        
        # Get ratings
        result = await db.execute(
            select(InsightRating).where(
                InsightRating.insight_id == insight_id
            ).options(selectinload(InsightRating.user))
        )
        ratings = result.scalars().all()
        
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
    
    async def get_insight_actions(
        self,
        db: AsyncSession,
        restaurant_id: int,
        insight_id: int
    ) -> List[Dict[str, Any]]:
        """Get action history for an insight"""
        
        # Validate insight
        await self._get_insight(db, insight_id, restaurant_id)
        
        # Get actions
        result = await db.execute(
            select(InsightAction).where(
                InsightAction.insight_id == insight_id
            ).options(
                selectinload(InsightAction.user)
            ).order_by(InsightAction.created_at.desc())
        )
        actions = result.scalars().all()
        
        return [
            {
                "id": action.id,
                "user_id": action.user_id,
                "user_name": action.user.name if action.user else "Unknown",
                "action_type": action.action_type,
                "action_details": action.action_details,
                "created_at": action.created_at
            }
            for action in actions
        ]
    
    async def get_user_insight_history(
        self,
        db: AsyncSession,
        restaurant_id: int,
        user_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get user's interaction history with insights"""
        
        since_date = datetime.utcnow() - timedelta(days=days)
        
        # Get ratings
        ratings_result = await db.execute(
            select(
                InsightRating.rating,
                func.count(InsightRating.id).label('count')
            ).join(
                Insight
            ).where(
                and_(
                    Insight.restaurant_id == restaurant_id,
                    InsightRating.user_id == user_id,
                    InsightRating.created_at >= since_date
                )
            ).group_by(InsightRating.rating)
        )
        
        ratings_summary = {
            row.rating: row.count 
            for row in ratings_result
        }
        
        # Get actions
        actions_result = await db.execute(
            select(
                InsightAction.action_type,
                func.count(InsightAction.id).label('count')
            ).join(
                Insight
            ).where(
                and_(
                    Insight.restaurant_id == restaurant_id,
                    InsightAction.user_id == user_id,
                    InsightAction.created_at >= since_date
                )
            ).group_by(InsightAction.action_type)
        )
        
        actions_summary = {
            row.action_type: row.count 
            for row in actions_result
        }
        
        # Get insights created by user interactions
        insights_result = await db.execute(
            select(func.count(func.distinct(InsightAction.insight_id))).join(
                Insight
            ).where(
                and_(
                    Insight.restaurant_id == restaurant_id,
                    InsightAction.user_id == user_id,
                    InsightAction.created_at >= since_date
                )
            )
        )
        
        total_insights_interacted = insights_result.scalar() or 0
        
        return {
            "user_id": user_id,
            "period_days": days,
            "ratings_given": ratings_summary,
            "actions_taken": actions_summary,
            "total_insights_interacted": total_insights_interacted,
            "engagement_score": self._calculate_engagement_score(
                ratings_summary, actions_summary
            )
        }
    
    async def get_rating_analytics(
        self,
        db: AsyncSession,
        restaurant_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get analytics on insight ratings"""
        
        query = select(
            InsightRating.rating,
            Insight.type,
            Insight.domain,
            func.count(InsightRating.id).label('count')
        ).join(
            Insight
        ).where(
            Insight.restaurant_id == restaurant_id
        )
        
        if start_date:
            query = query.where(InsightRating.created_at >= start_date)
        if end_date:
            query = query.where(InsightRating.created_at <= end_date)
        
        query = query.group_by(
            InsightRating.rating,
            Insight.type,
            Insight.domain
        )
        
        result = await db.execute(query)
        
        # Organize data
        by_rating = {}
        by_type = {}
        by_domain = {}
        
        for row in result:
            # By rating
            if row.rating not in by_rating:
                by_rating[row.rating] = 0
            by_rating[row.rating] += row.count
            
            # By type
            if row.type not in by_type:
                by_type[row.type] = {"total": 0, "by_rating": {}}
            by_type[row.type]["total"] += row.count
            if row.rating not in by_type[row.type]["by_rating"]:
                by_type[row.type]["by_rating"][row.rating] = 0
            by_type[row.type]["by_rating"][row.rating] += row.count
            
            # By domain
            if row.domain not in by_domain:
                by_domain[row.domain] = {"total": 0, "by_rating": {}}
            by_domain[row.domain]["total"] += row.count
            if row.rating not in by_domain[row.domain]["by_rating"]:
                by_domain[row.domain]["by_rating"][row.rating] = 0
            by_domain[row.domain]["by_rating"][row.rating] += row.count
        
        # Calculate acceptance rates
        total_ratings = sum(by_rating.values())
        useful_count = by_rating.get("useful", 0)
        
        # Update metrics
        for insight_type, type_data in by_type.items():
            for domain, domain_data in by_domain.items():
                useful = domain_data["by_rating"].get("useful", 0)
                total = domain_data["total"]
                
                rates = {
                    "24h": useful / total if total > 0 else 0,  # Simplified
                    "7d": useful / total if total > 0 else 0,
                    "30d": useful / total if total > 0 else 0
                }
                
                insight_metrics.update_acceptance_rates({
                    (insight_type, domain): rates
                })
        
        return {
            "period": {
                "start": start_date,
                "end": end_date
            },
            "total_ratings": total_ratings,
            "overall_acceptance_rate": useful_count / total_ratings if total_ratings > 0 else 0,
            "by_rating": by_rating,
            "by_type": by_type,
            "by_domain": by_domain
        }
    
    async def _update_insight_status_from_ratings(
        self,
        db: AsyncSession,
        insight: Insight
    ):
        """Update insight status based on ratings"""
        
        # Get all ratings
        result = await db.execute(
            select(
                InsightRating.rating,
                func.count(InsightRating.id).label('count')
            ).where(
                InsightRating.insight_id == insight.id
            ).group_by(InsightRating.rating)
        )
        
        rating_counts = {row.rating: row.count for row in result}
        total_ratings = sum(rating_counts.values())
        
        if total_ratings >= 3:  # Minimum ratings threshold
            irrelevant_count = rating_counts.get("irrelevant", 0)
            
            # Auto-dismiss if majority find it irrelevant
            if irrelevant_count / total_ratings > 0.6:
                if insight.status == InsightStatus.ACTIVE:
                    insight.status = InsightStatus.DISMISSED
                    
                    # Record dismissal
                    insight_metrics.record_insight_dismissed(
                        insight.type,
                        insight.severity,
                        insight.domain
                    )
                    
                    logger.info(
                        f"Insight {insight.id} auto-dismissed due to {irrelevant_count}/{total_ratings} "
                        f"irrelevant ratings"
                    )
    
    def _calculate_engagement_score(
        self,
        ratings: Dict[str, int],
        actions: Dict[str, int]
    ) -> float:
        """Calculate user engagement score (0-100)"""
        
        # Weighted scoring
        score = 0
        
        # Ratings (max 40 points)
        total_ratings = sum(ratings.values())
        if total_ratings > 0:
            score += min(40, total_ratings * 4)
        
        # Actions (max 60 points)
        action_weights = {
            "viewed": 2,
            "shared": 5,
            "exported": 5,
            "implemented": 20,
            "discussed": 8
        }
        
        for action_type, count in actions.items():
            weight = action_weights.get(action_type, 1)
            score += min(60, count * weight)
        
        return min(100, score)
    
    async def _get_insight(
        self,
        db: AsyncSession,
        insight_id: int,
        restaurant_id: int
    ) -> Insight:
        """Get insight with validation"""
        
        result = await db.execute(
            select(Insight).where(
                and_(
                    Insight.id == insight_id,
                    Insight.restaurant_id == restaurant_id
                )
            )
        )
        insight = result.scalar_one_or_none()
        
        if not insight:
            raise ResourceNotFoundError(f"Insight {insight_id} not found")
        
        return insight


# Create singleton service
insight_rating_service = InsightRatingService()