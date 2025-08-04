# backend/modules/ai_recommendations/services/feedback_analytics_service.py

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.orm import joinedload
import logging
import json
import csv
from io import StringIO
from collections import defaultdict

from ..models.feedback_models import SuggestionFeedback
from ..models.suggestion_models import AISuggestion
from ..schemas.admin_schemas import (
    FeedbackSummaryResponse,
    ModelPerformanceResponse,
    DomainInsightsResponse,
    FeedbackTrendResponse,
    ImprovementRecommendation
)

logger = logging.getLogger(__name__)


class FeedbackAnalyticsService:
    """Service for analyzing AI feedback and generating insights"""
    
    async def get_feedback_summary(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime,
        model_type: Optional[str] = None,
        domain: Optional[str] = None
    ) -> FeedbackSummaryResponse:
        """Get comprehensive feedback summary"""
        
        # Base query
        query = select(SuggestionFeedback).join(AISuggestion).where(
            and_(
                SuggestionFeedback.created_at >= start_date,
                SuggestionFeedback.created_at <= end_date
            )
        )
        
        if model_type:
            query = query.where(AISuggestion.model_type == model_type)
        if domain:
            query = query.where(AISuggestion.domain == domain)
        
        result = await db.execute(query)
        feedback_entries = result.scalars().all()
        
        # Calculate statistics
        total_count = len(feedback_entries)
        unique_users = len(set(f.user_id for f in feedback_entries if f.user_id))
        
        rating_distribution = defaultdict(int)
        feedback_by_type = defaultdict(int)
        ratings = []
        
        for feedback in feedback_entries:
            rating_distribution[str(feedback.rating)] += 1
            feedback_by_type[feedback.feedback_type] += 1
            ratings.append(feedback.rating)
        
        avg_rating = sum(ratings) / len(ratings) if ratings else 0
        
        # Get top comments
        positive_comments = sorted(
            [f for f in feedback_entries if f.rating >= 4 and f.comment],
            key=lambda x: x.rating,
            reverse=True
        )[:5]
        
        negative_comments = sorted(
            [f for f in feedback_entries if f.rating <= 2 and f.comment],
            key=lambda x: x.rating
        )[:5]
        
        # Model breakdown
        model_stats = await self._get_model_breakdown(db, start_date, end_date)
        
        # Domain breakdown
        domain_stats = await self._get_domain_breakdown(db, start_date, end_date)
        
        return FeedbackSummaryResponse(
            time_period={"start": start_date, "end": end_date},
            total_feedback_count=total_count,
            unique_users=unique_users,
            average_rating=avg_rating,
            rating_distribution=dict(rating_distribution),
            feedback_by_type=dict(feedback_by_type),
            top_positive_comments=[
                {
                    "rating": f.rating,
                    "comment": f.comment,
                    "model_type": f.suggestion.model_type,
                    "domain": f.suggestion.domain
                }
                for f in positive_comments
            ],
            top_negative_comments=[
                {
                    "rating": f.rating,
                    "comment": f.comment,
                    "model_type": f.suggestion.model_type,
                    "domain": f.suggestion.domain
                }
                for f in negative_comments
            ],
            model_breakdown=model_stats,
            domain_breakdown=domain_stats
        )
    
    async def _get_model_breakdown(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get feedback breakdown by model"""
        
        query = select(
            AISuggestion.model_type,
            func.count(SuggestionFeedback.id).label('feedback_count'),
            func.avg(SuggestionFeedback.rating).label('avg_rating'),
            func.sum(case((SuggestionFeedback.rating >= 4, 1), else_=0)).label('positive_count')
        ).join(
            SuggestionFeedback
        ).where(
            and_(
                SuggestionFeedback.created_at >= start_date,
                SuggestionFeedback.created_at <= end_date
            )
        ).group_by(AISuggestion.model_type)
        
        result = await db.execute(query)
        
        return [
            {
                "model_type": row.model_type,
                "feedback_count": row.feedback_count,
                "average_rating": float(row.avg_rating) if row.avg_rating else 0,
                "positive_feedback_rate": row.positive_count / row.feedback_count if row.feedback_count > 0 else 0
            }
            for row in result
        ]
    
    async def _get_domain_breakdown(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get feedback breakdown by domain"""
        
        query = select(
            AISuggestion.domain,
            func.count(SuggestionFeedback.id).label('feedback_count'),
            func.avg(SuggestionFeedback.rating).label('avg_rating'),
            func.count(func.distinct(SuggestionFeedback.user_id)).label('unique_users')
        ).join(
            SuggestionFeedback
        ).where(
            and_(
                SuggestionFeedback.created_at >= start_date,
                SuggestionFeedback.created_at <= end_date
            )
        ).group_by(AISuggestion.domain)
        
        result = await db.execute(query)
        
        return [
            {
                "domain": row.domain,
                "feedback_count": row.feedback_count,
                "average_rating": float(row.avg_rating) if row.avg_rating else 0,
                "unique_users": row.unique_users
            }
            for row in result
        ]
    
    async def get_model_performance(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime,
        group_by: str = "model_type",
        min_requests: int = 10
    ) -> List[ModelPerformanceResponse]:
        """Get model performance metrics"""
        
        # This would integrate with actual model request tracking
        # For now, using feedback data as proxy
        
        group_field = getattr(AISuggestion, group_by)
        
        query = select(
            group_field,
            func.count(AISuggestion.id).label('total_requests'),
            func.count(SuggestionFeedback.id).label('feedback_count'),
            func.avg(SuggestionFeedback.rating).label('avg_rating'),
            func.avg(AISuggestion.confidence_score).label('avg_confidence')
        ).outerjoin(
            SuggestionFeedback
        ).where(
            and_(
                AISuggestion.created_at >= start_date,
                AISuggestion.created_at <= end_date
            )
        ).group_by(group_field).having(
            func.count(AISuggestion.id) >= min_requests
        )
        
        result = await db.execute(query)
        
        performance_data = []
        for row in result:
            # Calculate derived metrics
            feedback_rate = row.feedback_count / row.total_requests if row.total_requests > 0 else 0
            
            performance = ModelPerformanceResponse(
                model_type=row[0] if group_by == "model_type" else "various",
                domain=row[0] if group_by == "domain" else None,
                endpoint=row[0] if group_by == "endpoint" else None,
                total_requests=row.total_requests,
                successful_requests=row.total_requests,  # Would need actual success tracking
                failed_requests=0,
                success_rate=1.0,  # Placeholder
                avg_response_time=0.5,  # Placeholder
                p95_response_time=1.0,  # Placeholder
                avg_confidence_score=float(row.avg_confidence) if row.avg_confidence else 0.5,
                feedback_count=row.feedback_count,
                average_rating=float(row.avg_rating) if row.avg_rating else None,
                positive_feedback_rate=None,  # Would calculate from actual data
                adoption_rate=feedback_rate
            )
            
            performance_data.append(performance)
        
        return performance_data
    
    async def get_domain_insights(
        self,
        db: AsyncSession,
        domain: str,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[DomainInsightsResponse]:
        """Get detailed insights for a domain"""
        
        # Get suggestions for domain
        query = select(AISuggestion).where(
            and_(
                AISuggestion.domain == domain,
                AISuggestion.created_at >= start_date,
                AISuggestion.created_at <= end_date
            )
        ).options(joinedload(AISuggestion.feedback))
        
        result = await db.execute(query)
        suggestions = result.scalars().all()
        
        if not suggestions:
            return None
        
        # Calculate insights
        total_suggestions = len(suggestions)
        unique_users = len(set(s.user_id for s in suggestions if s.user_id))
        suggestions_per_user = total_suggestions / unique_users if unique_users > 0 else 0
        
        # Peak usage hour
        hour_counts = defaultdict(int)
        for suggestion in suggestions:
            hour_counts[suggestion.created_at.hour] += 1
        peak_hour = max(hour_counts.items(), key=lambda x: x[1])[0]
        
        # Model usage
        model_counts = defaultdict(int)
        for suggestion in suggestions:
            model_counts[suggestion.model_type] += 1
        
        models_used = list(model_counts.keys())
        primary_model = max(model_counts.items(), key=lambda x: x[1])[0]
        
        # Feedback analysis
        all_feedback = [f for s in suggestions for f in s.feedback]
        avg_rating = sum(f.rating for f in all_feedback) / len(all_feedback) if all_feedback else 0
        
        # Sentiment analysis (simplified)
        sentiment = {
            "positive": len([f for f in all_feedback if f.rating >= 4]) / len(all_feedback) if all_feedback else 0,
            "neutral": len([f for f in all_feedback if f.rating == 3]) / len(all_feedback) if all_feedback else 0,
            "negative": len([f for f in all_feedback if f.rating <= 2]) / len(all_feedback) if all_feedback else 0
        }
        
        # Get model performance
        model_performance = await self.get_model_performance(
            db, start_date, end_date, "model_type", 1
        )
        
        return DomainInsightsResponse(
            domain=domain,
            analysis_period={"start": start_date, "end": end_date},
            total_suggestions=total_suggestions,
            unique_users=unique_users,
            suggestions_per_user=suggestions_per_user,
            peak_usage_hour=peak_hour,
            models_used=models_used,
            primary_model=primary_model,
            model_performance=[m for m in model_performance if m.model_type in models_used],
            overall_satisfaction=avg_rating,
            feedback_sentiment=sentiment,
            top_use_cases=[],  # Would analyze from actual data
            common_issues=[],  # Would analyze from feedback comments
            improvement_suggestions=[],  # Would generate from analysis
            usage_trend="stable",  # Would calculate from time series
            satisfaction_trend="stable"  # Would calculate from time series
        )
    
    async def get_feedback_trends(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime,
        interval: str = "daily",
        model_type: Optional[str] = None,
        domain: Optional[str] = None
    ) -> FeedbackTrendResponse:
        """Get feedback trends over time"""
        
        # Determine grouping interval
        if interval == "hourly":
            date_trunc = func.date_trunc('hour', SuggestionFeedback.created_at)
        elif interval == "weekly":
            date_trunc = func.date_trunc('week', SuggestionFeedback.created_at)
        else:  # daily
            date_trunc = func.date_trunc('day', SuggestionFeedback.created_at)
        
        # Build query
        query = select(
            date_trunc.label('time_bucket'),
            func.count(SuggestionFeedback.id).label('feedback_count'),
            func.avg(SuggestionFeedback.rating).label('avg_rating'),
            func.count(func.distinct(SuggestionFeedback.user_id)).label('unique_users')
        ).join(AISuggestion).where(
            and_(
                SuggestionFeedback.created_at >= start_date,
                SuggestionFeedback.created_at <= end_date
            )
        )
        
        if model_type:
            query = query.where(AISuggestion.model_type == model_type)
        if domain:
            query = query.where(AISuggestion.domain == domain)
        
        query = query.group_by(date_trunc).order_by(date_trunc)
        
        result = await db.execute(query)
        
        trends = [
            {
                "timestamp": row.time_bucket,
                "feedback_count": row.feedback_count,
                "average_rating": float(row.avg_rating) if row.avg_rating else 0,
                "unique_users": row.unique_users
            }
            for row in result
        ]
        
        # Calculate summary stats
        all_ratings = [t["average_rating"] for t in trends if t["average_rating"] > 0]
        
        summary_stats = {
            "total_periods": len(trends),
            "avg_feedback_per_period": sum(t["feedback_count"] for t in trends) / len(trends) if trends else 0,
            "rating_variance": self._calculate_variance(all_ratings),
            "trend_direction": self._detect_trend(all_ratings)
        }
        
        # Detect significant changes
        significant_changes = self._detect_significant_changes(trends)
        
        return FeedbackTrendResponse(
            time_range={"start": start_date, "end": end_date},
            interval=interval,
            trends=trends,
            summary_stats=summary_stats,
            significant_changes=significant_changes
        )
    
    def _calculate_variance(self, values: List[float]) -> float:
        """Calculate variance of values"""
        if not values:
            return 0
        mean = sum(values) / len(values)
        return sum((x - mean) ** 2 for x in values) / len(values)
    
    def _detect_trend(self, values: List[float]) -> str:
        """Detect trend in values"""
        if len(values) < 3:
            return "insufficient_data"
        
        # Simple linear regression
        n = len(values)
        x = list(range(n))
        
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return "stable"
        
        slope = numerator / denominator
        
        if slope > 0.01:
            return "increasing"
        elif slope < -0.01:
            return "decreasing"
        else:
            return "stable"
    
    def _detect_significant_changes(self, trends: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect significant changes in trends"""
        changes = []
        
        if len(trends) < 2:
            return changes
        
        for i in range(1, len(trends)):
            prev = trends[i-1]
            curr = trends[i]
            
            # Check for significant rating changes
            if prev["average_rating"] > 0 and curr["average_rating"] > 0:
                rating_change = abs(curr["average_rating"] - prev["average_rating"])
                if rating_change > 0.5:
                    changes.append({
                        "timestamp": curr["timestamp"],
                        "type": "rating_change",
                        "previous_value": prev["average_rating"],
                        "new_value": curr["average_rating"],
                        "change_percentage": (rating_change / prev["average_rating"]) * 100
                    })
            
            # Check for significant volume changes
            if prev["feedback_count"] > 0:
                volume_change = abs(curr["feedback_count"] - prev["feedback_count"])
                change_percentage = (volume_change / prev["feedback_count"]) * 100
                if change_percentage > 50:
                    changes.append({
                        "timestamp": curr["timestamp"],
                        "type": "volume_change",
                        "previous_value": prev["feedback_count"],
                        "new_value": curr["feedback_count"],
                        "change_percentage": change_percentage
                    })
        
        return changes
    
    async def export_metrics(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime,
        format: str = "json",
        include_feedback: bool = True,
        include_performance: bool = True
    ) -> Any:
        """Export metrics in requested format"""
        
        export_data = {
            "export_date": datetime.utcnow().isoformat(),
            "time_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }
        
        if include_feedback:
            summary = await self.get_feedback_summary(db, start_date, end_date)
            export_data["feedback_summary"] = summary.dict()
        
        if include_performance:
            performance = await self.get_model_performance(db, start_date, end_date)
            export_data["model_performance"] = [p.dict() for p in performance]
        
        if format == "csv":
            return self._convert_to_csv(export_data)
        
        return export_data
    
    def _convert_to_csv(self, data: Dict[str, Any]) -> str:
        """Convert data to CSV format"""
        output = StringIO()
        
        # Write feedback summary
        if "feedback_summary" in data:
            writer = csv.writer(output)
            writer.writerow(["Feedback Summary"])
            writer.writerow(["Metric", "Value"])
            
            summary = data["feedback_summary"]
            writer.writerow(["Total Feedback", summary["total_feedback_count"]])
            writer.writerow(["Unique Users", summary["unique_users"]])
            writer.writerow(["Average Rating", summary["average_rating"]])
            writer.writerow([])
        
        # Write model performance
        if "model_performance" in data:
            writer.writerow(["Model Performance"])
            if data["model_performance"]:
                headers = list(data["model_performance"][0].keys())
                writer.writerow(headers)
                
                for row in data["model_performance"]:
                    writer.writerow([row.get(h, "") for h in headers])
        
        return output.getvalue()
    
    async def get_improvement_recommendations(
        self,
        db: AsyncSession,
        min_feedback_count: int = 50
    ) -> List[ImprovementRecommendation]:
        """Generate AI improvement recommendations based on feedback"""
        
        # Get recent feedback summary
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        
        summary = await self.get_feedback_summary(db, start_date, end_date)
        
        recommendations = []
        
        # Check for low average rating
        if summary.average_rating < 3.0:
            recommendations.append(
                ImprovementRecommendation(
                    priority="high",
                    category="model_accuracy",
                    title="Improve Model Accuracy",
                    description="Average user rating is below 3.0, indicating dissatisfaction with suggestions",
                    affected_models=["all"],
                    affected_domains=["all"],
                    expected_impact={
                        "rating_improvement": "+1.0 to +1.5",
                        "user_satisfaction": "+30%"
                    },
                    implementation_steps=[
                        "Analyze negative feedback comments for patterns",
                        "Retrain models with updated datasets",
                        "Implement A/B testing for model improvements",
                        "Add confidence thresholds for suggestions"
                    ],
                    estimated_effort="high",
                    supporting_data={
                        "current_rating": summary.average_rating,
                        "negative_feedback_rate": summary.feedback_by_type.get("negative", 0) / summary.total_feedback_count
                    }
                )
            )
        
        # Check for low feedback rate
        if summary.total_feedback_count < min_feedback_count:
            recommendations.append(
                ImprovementRecommendation(
                    priority="medium",
                    category="user_experience",
                    title="Increase Feedback Collection",
                    description="Low feedback volume makes it difficult to assess model performance",
                    affected_models=["all"],
                    affected_domains=["all"],
                    expected_impact={
                        "feedback_rate": "+200%",
                        "data_quality": "significantly improved"
                    },
                    implementation_steps=[
                        "Simplify feedback UI with one-click ratings",
                        "Add incentives for providing feedback",
                        "Show feedback prompt at optimal times",
                        "Implement passive feedback collection"
                    ],
                    estimated_effort="medium",
                    supporting_data={
                        "current_feedback_count": summary.total_feedback_count,
                        "feedback_per_user": summary.total_feedback_count / summary.unique_users if summary.unique_users > 0 else 0
                    }
                )
            )
        
        # Check for domain-specific issues
        for domain_stat in summary.domain_breakdown:
            if domain_stat["average_rating"] < 2.5:
                recommendations.append(
                    ImprovementRecommendation(
                        priority="high",
                        category="model_accuracy",
                        title=f"Improve {domain_stat['domain']} Domain Performance",
                        description=f"The {domain_stat['domain']} domain has significantly lower ratings",
                        affected_models=["all"],
                        affected_domains=[domain_stat['domain']],
                        expected_impact={
                            "domain_rating": "+1.5",
                            "domain_usage": "+50%"
                        },
                        implementation_steps=[
                            f"Review {domain_stat['domain']}-specific training data",
                            "Interview users about pain points",
                            "Consider domain-specific model fine-tuning",
                            "Add domain expert validation"
                        ],
                        estimated_effort="medium",
                        supporting_data=domain_stat
                    )
                )
        
        return recommendations
    
    async def configure_alerts(
        self,
        db: AsyncSession,
        user_id: int,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Configure alert settings (would save to database)"""
        
        # In a real implementation, this would save to a configuration table
        logger.info(f"Alert configuration updated for user {user_id}: {config}")
        
        return {
            "user_id": user_id,
            "config": config,
            "updated_at": datetime.utcnow().isoformat()
        }


# Create singleton service
feedback_analytics_service = FeedbackAnalyticsService()