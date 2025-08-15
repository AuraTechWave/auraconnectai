# backend/modules/feedback/services/analytics_service.py

import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, text, case
from dataclasses import dataclass
import json
from collections import defaultdict

from modules.feedback.models.feedback_models import (
    Review,
    Feedback,
    ReviewAggregate,
    ReviewStatus,
    FeedbackStatus,
    SentimentScore,
    ReviewType,
    FeedbackType,
    FeedbackPriority,
)
from modules.feedback.services.sentiment_service import sentiment_service

logger = logging.getLogger(__name__)


@dataclass
class AnalyticsTimeframe:
    """Analytics timeframe configuration"""

    start_date: datetime
    end_date: datetime
    period_type: str  # daily, weekly, monthly
    periods: int


class FeedbackAnalyticsService:
    """Comprehensive analytics service for feedback and reviews"""

    def __init__(self, db: Session):
        self.db = db

    def generate_executive_summary(
        self, timeframe: AnalyticsTimeframe
    ) -> Dict[str, Any]:
        """Generate executive summary of feedback and review performance"""

        # Get key metrics for the period
        review_metrics = self._get_review_metrics(timeframe)
        feedback_metrics = self._get_feedback_metrics(timeframe)
        satisfaction_metrics = self._get_satisfaction_metrics(timeframe)
        trend_analysis = self._get_trend_analysis(timeframe)

        # Generate insights and recommendations
        insights = self._generate_insights(
            review_metrics, feedback_metrics, satisfaction_metrics
        )
        recommendations = self._generate_recommendations(insights, trend_analysis)

        return {
            "period": {
                "start_date": timeframe.start_date.isoformat(),
                "end_date": timeframe.end_date.isoformat(),
                "duration_days": (timeframe.end_date - timeframe.start_date).days,
            },
            "key_metrics": {
                "review_metrics": review_metrics,
                "feedback_metrics": feedback_metrics,
                "satisfaction_metrics": satisfaction_metrics,
            },
            "trend_analysis": trend_analysis,
            "insights": insights,
            "recommendations": recommendations,
            "generated_at": datetime.utcnow().isoformat(),
        }

    def get_review_performance_report(
        self,
        timeframe: AnalyticsTimeframe,
        entity_type: Optional[str] = None,
        entity_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Generate detailed review performance report"""

        base_query = self._build_review_base_query(timeframe, entity_type, entity_ids)

        # Volume metrics
        volume_metrics = self._calculate_review_volume_metrics(base_query, timeframe)

        # Rating metrics
        rating_metrics = self._calculate_rating_metrics(base_query)

        # Engagement metrics
        engagement_metrics = self._calculate_engagement_metrics(base_query)

        # Quality metrics
        quality_metrics = self._calculate_review_quality_metrics(base_query)

        # Temporal trends
        temporal_trends = self._calculate_temporal_trends(base_query, timeframe)

        # Top performers and problem areas
        performance_analysis = self._analyze_performance_outliers(
            entity_type, entity_ids, timeframe
        )

        return {
            "report_metadata": {
                "timeframe": {
                    "start_date": timeframe.start_date.isoformat(),
                    "end_date": timeframe.end_date.isoformat(),
                    "period_type": timeframe.period_type,
                },
                "scope": {
                    "entity_type": entity_type,
                    "entity_count": len(entity_ids) if entity_ids else "all",
                    "total_reviews": volume_metrics["total_reviews"],
                },
            },
            "volume_metrics": volume_metrics,
            "rating_metrics": rating_metrics,
            "engagement_metrics": engagement_metrics,
            "quality_metrics": quality_metrics,
            "temporal_trends": temporal_trends,
            "performance_analysis": performance_analysis,
            "generated_at": datetime.utcnow().isoformat(),
        }

    def get_feedback_analysis_report(
        self, timeframe: AnalyticsTimeframe, include_resolution_analysis: bool = True
    ) -> Dict[str, Any]:
        """Generate comprehensive feedback analysis report"""

        base_query = self._build_feedback_base_query(timeframe)

        # Volume and categorization
        volume_metrics = self._calculate_feedback_volume_metrics(base_query, timeframe)
        category_analysis = self._analyze_feedback_categories(base_query)

        # Resolution performance
        resolution_metrics = {}
        if include_resolution_analysis:
            resolution_metrics = self._calculate_resolution_metrics(
                base_query, timeframe
            )

        # Sentiment and priority analysis
        sentiment_analysis = self._analyze_feedback_sentiment(base_query)
        priority_analysis = self._analyze_feedback_priorities(base_query)

        # Staff performance
        staff_performance = self._analyze_staff_performance(base_query, timeframe)

        # Trends and patterns
        trend_analysis = self._analyze_feedback_trends(base_query, timeframe)

        return {
            "report_metadata": {
                "timeframe": {
                    "start_date": timeframe.start_date.isoformat(),
                    "end_date": timeframe.end_date.isoformat(),
                },
                "total_feedback": volume_metrics["total_feedback"],
            },
            "volume_metrics": volume_metrics,
            "category_analysis": category_analysis,
            "resolution_metrics": resolution_metrics,
            "sentiment_analysis": sentiment_analysis,
            "priority_analysis": priority_analysis,
            "staff_performance": staff_performance,
            "trend_analysis": trend_analysis,
            "generated_at": datetime.utcnow().isoformat(),
        }

    def get_satisfaction_trends(
        self, timeframe: AnalyticsTimeframe, granularity: str = "daily"
    ) -> Dict[str, Any]:
        """Analyze customer satisfaction trends over time"""

        # Calculate satisfaction scores over time
        satisfaction_trends = self._calculate_satisfaction_over_time(
            timeframe, granularity
        )

        # Identify significant changes
        change_points = self._identify_satisfaction_change_points(satisfaction_trends)

        # Calculate satisfaction drivers
        satisfaction_drivers = self._analyze_satisfaction_drivers(timeframe)

        # Segment analysis
        segment_analysis = self._analyze_satisfaction_by_segments(timeframe)

        return {
            "timeframe": {
                "start_date": timeframe.start_date.isoformat(),
                "end_date": timeframe.end_date.isoformat(),
                "granularity": granularity,
            },
            "satisfaction_trends": satisfaction_trends,
            "change_points": change_points,
            "satisfaction_drivers": satisfaction_drivers,
            "segment_analysis": segment_analysis,
            "overall_satisfaction": {
                "current_score": (
                    satisfaction_trends[-1]["satisfaction_score"]
                    if satisfaction_trends
                    else 0
                ),
                "trend_direction": self._calculate_trend_direction(satisfaction_trends),
                "volatility": self._calculate_satisfaction_volatility(
                    satisfaction_trends
                ),
            },
        }

    def get_competitive_analysis(
        self,
        timeframe: AnalyticsTimeframe,
        benchmark_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate competitive analysis report"""

        # Internal performance metrics
        internal_metrics = {
            "average_rating": self._get_average_rating(timeframe),
            "review_volume": self._get_review_volume(timeframe),
            "response_rate": self._get_response_rate(timeframe),
            "satisfaction_score": self._get_satisfaction_score(timeframe),
            "resolution_time": self._get_average_resolution_time(timeframe),
        }

        # Benchmark comparison (if provided)
        benchmark_comparison = {}
        if benchmark_data:
            benchmark_comparison = self._compare_to_benchmarks(
                internal_metrics, benchmark_data
            )

        # Strengths and weaknesses analysis
        performance_analysis = self._analyze_competitive_position(
            internal_metrics, benchmark_data
        )

        return {
            "analysis_period": {
                "start_date": timeframe.start_date.isoformat(),
                "end_date": timeframe.end_date.isoformat(),
            },
            "internal_metrics": internal_metrics,
            "benchmark_comparison": benchmark_comparison,
            "performance_analysis": performance_analysis,
            "recommendations": self._generate_competitive_recommendations(
                performance_analysis
            ),
        }

    def generate_custom_report(self, report_config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate custom analytics report based on configuration"""

        timeframe = AnalyticsTimeframe(
            start_date=datetime.fromisoformat(report_config["start_date"]),
            end_date=datetime.fromisoformat(report_config["end_date"]),
            period_type=report_config.get("period_type", "daily"),
            periods=report_config.get("periods", 30),
        )

        report_data = {}

        # Include requested sections
        if report_config.get("include_reviews", True):
            report_data["reviews"] = self.get_review_performance_report(
                timeframe,
                report_config.get("entity_type"),
                report_config.get("entity_ids"),
            )

        if report_config.get("include_feedback", True):
            report_data["feedback"] = self.get_feedback_analysis_report(
                timeframe, report_config.get("include_resolution_analysis", True)
            )

        if report_config.get("include_satisfaction", False):
            report_data["satisfaction"] = self.get_satisfaction_trends(
                timeframe, report_config.get("satisfaction_granularity", "daily")
            )

        if report_config.get("include_executive_summary", False):
            report_data["executive_summary"] = self.generate_executive_summary(
                timeframe
            )

        return {
            "report_config": report_config,
            "data": report_data,
            "generated_at": datetime.utcnow().isoformat(),
        }

    async def generate_real_time_dashboard(self) -> Dict[str, Any]:
        """Generate real-time dashboard data"""

        current_time = datetime.utcnow()

        # Last 24 hours data
        last_24h = AnalyticsTimeframe(
            start_date=current_time - timedelta(hours=24),
            end_date=current_time,
            period_type="hourly",
            periods=24,
        )

        # Last 7 days data
        last_7d = AnalyticsTimeframe(
            start_date=current_time - timedelta(days=7),
            end_date=current_time,
            period_type="daily",
            periods=7,
        )

        # Real-time metrics
        real_time_metrics = await self._get_real_time_metrics()

        # Recent activity
        recent_activity = self._get_recent_activity(hours=2)

        # Alert conditions
        alerts = self._check_alert_conditions()

        # Quick stats
        quick_stats = {
            "last_24h": {
                "new_reviews": self._count_new_reviews(last_24h),
                "new_feedback": self._count_new_feedback(last_24h),
                "avg_rating": self._get_average_rating(last_24h),
                "pending_moderation": self._count_pending_moderation(),
            },
            "last_7d": {
                "review_trend": self._calculate_review_trend(last_7d),
                "satisfaction_trend": self._calculate_satisfaction_trend(last_7d),
                "resolution_rate": self._calculate_resolution_rate(last_7d),
            },
        }

        return {
            "timestamp": current_time.isoformat(),
            "real_time_metrics": real_time_metrics,
            "quick_stats": quick_stats,
            "recent_activity": recent_activity,
            "alerts": alerts,
            "refresh_rate": 30,  # seconds
        }

    # Private helper methods

    def _build_review_base_query(
        self,
        timeframe: AnalyticsTimeframe,
        entity_type: Optional[str] = None,
        entity_ids: Optional[List[int]] = None,
    ):
        """Build base query for review analytics"""

        query = self.db.query(Review).filter(
            and_(
                Review.created_at >= timeframe.start_date,
                Review.created_at <= timeframe.end_date,
                Review.status == ReviewStatus.APPROVED,
            )
        )

        if entity_type and entity_ids:
            if entity_type == "product":
                query = query.filter(Review.product_id.in_(entity_ids))
            elif entity_type == "service":
                query = query.filter(Review.service_id.in_(entity_ids))

        return query

    def _build_feedback_base_query(self, timeframe: AnalyticsTimeframe):
        """Build base query for feedback analytics"""

        return self.db.query(Feedback).filter(
            and_(
                Feedback.created_at >= timeframe.start_date,
                Feedback.created_at <= timeframe.end_date,
            )
        )

    def _get_review_metrics(self, timeframe: AnalyticsTimeframe) -> Dict[str, Any]:
        """Get key review metrics for the timeframe"""

        query = self._build_review_base_query(timeframe)
        reviews = query.all()

        if not reviews:
            return {
                "total_reviews": 0,
                "average_rating": 0.0,
                "rating_distribution": {},
                "sentiment_distribution": {},
                "verification_rate": 0.0,
            }

        total_reviews = len(reviews)
        avg_rating = sum(r.rating for r in reviews) / total_reviews

        # Rating distribution
        rating_dist = defaultdict(int)
        for review in reviews:
            rating_dist[int(review.rating)] += 1

        # Sentiment distribution
        sentiment_dist = defaultdict(int)
        for review in reviews:
            if review.sentiment_score:
                sentiment_dist[review.sentiment_score.value] += 1

        # Verification rate
        verified_count = sum(1 for r in reviews if r.is_verified_purchase)
        verification_rate = (verified_count / total_reviews) * 100

        return {
            "total_reviews": total_reviews,
            "average_rating": round(avg_rating, 2),
            "rating_distribution": dict(rating_dist),
            "sentiment_distribution": dict(sentiment_dist),
            "verification_rate": round(verification_rate, 1),
            "growth_rate": self._calculate_review_growth_rate(timeframe),
        }

    def _get_feedback_metrics(self, timeframe: AnalyticsTimeframe) -> Dict[str, Any]:
        """Get key feedback metrics for the timeframe"""

        query = self._build_feedback_base_query(timeframe)
        feedback_items = query.all()

        if not feedback_items:
            return {
                "total_feedback": 0,
                "by_type": {},
                "by_status": {},
                "by_priority": {},
                "resolution_rate": 0.0,
                "avg_resolution_time": 0.0,
            }

        total_feedback = len(feedback_items)

        # Distribution by type
        type_dist = defaultdict(int)
        for fb in feedback_items:
            type_dist[fb.feedback_type.value] += 1

        # Distribution by status
        status_dist = defaultdict(int)
        for fb in feedback_items:
            status_dist[fb.status.value] += 1

        # Distribution by priority
        priority_dist = defaultdict(int)
        for fb in feedback_items:
            priority_dist[fb.priority.value] += 1

        # Resolution metrics
        resolved_feedback = [
            fb for fb in feedback_items if fb.status == FeedbackStatus.RESOLVED
        ]
        resolution_rate = (len(resolved_feedback) / total_feedback) * 100

        # Average resolution time
        resolution_times = []
        for fb in resolved_feedback:
            if fb.resolved_at:
                resolution_time = (
                    fb.resolved_at - fb.created_at
                ).total_seconds() / 3600  # hours
                resolution_times.append(resolution_time)

        avg_resolution_time = (
            sum(resolution_times) / len(resolution_times) if resolution_times else 0
        )

        return {
            "total_feedback": total_feedback,
            "by_type": dict(type_dist),
            "by_status": dict(status_dist),
            "by_priority": dict(priority_dist),
            "resolution_rate": round(resolution_rate, 1),
            "avg_resolution_time": round(avg_resolution_time, 2),
            "growth_rate": self._calculate_feedback_growth_rate(timeframe),
        }

    def _get_satisfaction_metrics(
        self, timeframe: AnalyticsTimeframe
    ) -> Dict[str, Any]:
        """Calculate overall satisfaction metrics"""

        # Get reviews for satisfaction calculation
        review_query = self._build_review_base_query(timeframe)
        reviews = review_query.all()

        # Get feedback for satisfaction impact
        feedback_query = self._build_feedback_base_query(timeframe)
        feedback_items = feedback_query.all()

        if not reviews:
            return {
                "overall_satisfaction": 0.0,
                "satisfaction_trend": "stable",
                "positive_sentiment_rate": 0.0,
                "detractor_rate": 0.0,
            }

        # Calculate NPS-style satisfaction score
        ratings = [r.rating for r in reviews]
        promoters = sum(1 for r in ratings if r >= 4.0)
        detractors = sum(1 for r in ratings if r <= 2.0)

        satisfaction_score = ((promoters - detractors) / len(ratings)) * 100

        # Positive sentiment rate
        positive_sentiments = sum(
            1
            for r in reviews
            if r.sentiment_score
            in [SentimentScore.POSITIVE, SentimentScore.VERY_POSITIVE]
        )
        positive_sentiment_rate = (positive_sentiments / len(reviews)) * 100

        # Calculate trend
        satisfaction_trend = self._calculate_satisfaction_trend_direction(timeframe)

        return {
            "overall_satisfaction": round(satisfaction_score, 1),
            "satisfaction_trend": satisfaction_trend,
            "positive_sentiment_rate": round(positive_sentiment_rate, 1),
            "detractor_rate": round((detractors / len(ratings)) * 100, 1),
            "complaint_rate": self._calculate_complaint_rate(feedback_items),
        }

    def _get_trend_analysis(self, timeframe: AnalyticsTimeframe) -> Dict[str, Any]:
        """Analyze trends over the timeframe"""

        # Split timeframe into periods for trend analysis
        period_length = (timeframe.end_date - timeframe.start_date) / 4  # 4 periods
        periods = []

        current_start = timeframe.start_date
        for i in range(4):
            period_end = current_start + period_length
            periods.append(
                {
                    "start": current_start,
                    "end": period_end,
                    "reviews": self._count_reviews_in_period(current_start, period_end),
                    "avg_rating": self._get_avg_rating_in_period(
                        current_start, period_end
                    ),
                    "feedback": self._count_feedback_in_period(
                        current_start, period_end
                    ),
                }
            )
            current_start = period_end

        # Calculate trends
        review_trend = self._calculate_trend([p["reviews"] for p in periods])
        rating_trend = self._calculate_trend([p["avg_rating"] for p in periods])
        feedback_trend = self._calculate_trend([p["feedback"] for p in periods])

        return {
            "periods": [
                {
                    "period": f"Period {i+1}",
                    "reviews": periods[i]["reviews"],
                    "avg_rating": periods[i]["avg_rating"],
                    "feedback": periods[i]["feedback"],
                }
                for i in range(4)
            ],
            "trends": {
                "review_volume": review_trend,
                "rating_average": rating_trend,
                "feedback_volume": feedback_trend,
            },
        }

    def _generate_insights(
        self,
        review_metrics: Dict[str, Any],
        feedback_metrics: Dict[str, Any],
        satisfaction_metrics: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Generate actionable insights from metrics"""

        insights = []

        # Review insights
        if review_metrics["average_rating"] >= 4.0:
            insights.append(
                {
                    "type": "positive",
                    "category": "reviews",
                    "title": "Strong Review Performance",
                    "description": f"Average rating of {review_metrics['average_rating']} indicates high customer satisfaction",
                    "impact": "high",
                }
            )
        elif review_metrics["average_rating"] <= 3.0:
            insights.append(
                {
                    "type": "concern",
                    "category": "reviews",
                    "title": "Review Ratings Below Expectations",
                    "description": f"Average rating of {review_metrics['average_rating']} suggests room for improvement",
                    "impact": "high",
                }
            )

        # Feedback insights
        if feedback_metrics["resolution_rate"] < 80:
            insights.append(
                {
                    "type": "concern",
                    "category": "feedback",
                    "title": "Low Feedback Resolution Rate",
                    "description": f"Only {feedback_metrics['resolution_rate']}% of feedback is being resolved",
                    "impact": "medium",
                }
            )

        if feedback_metrics["avg_resolution_time"] > 48:
            insights.append(
                {
                    "type": "concern",
                    "category": "feedback",
                    "title": "Slow Feedback Resolution",
                    "description": f"Average resolution time of {feedback_metrics['avg_resolution_time']} hours exceeds target",
                    "impact": "medium",
                }
            )

        # Satisfaction insights
        if satisfaction_metrics["overall_satisfaction"] > 50:
            insights.append(
                {
                    "type": "positive",
                    "category": "satisfaction",
                    "title": "Positive Customer Sentiment",
                    "description": f"Satisfaction score of {satisfaction_metrics['overall_satisfaction']} indicates more promoters than detractors",
                    "impact": "high",
                }
            )

        return insights

    def _generate_recommendations(
        self, insights: List[Dict[str, Any]], trend_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate actionable recommendations"""

        recommendations = []

        # Based on insights
        concern_insights = [i for i in insights if i["type"] == "concern"]

        for insight in concern_insights:
            if (
                insight["category"] == "reviews"
                and "rating" in insight["title"].lower()
            ):
                recommendations.append(
                    {
                        "priority": "high",
                        "category": "product_improvement",
                        "title": "Focus on Product/Service Quality",
                        "description": "Investigate common complaints in low-rated reviews and address underlying issues",
                        "expected_impact": "Increase average rating by 0.5-1.0 points",
                        "timeline": "2-3 months",
                    }
                )

            elif (
                insight["category"] == "feedback"
                and "resolution" in insight["title"].lower()
            ):
                recommendations.append(
                    {
                        "priority": "medium",
                        "category": "process_improvement",
                        "title": "Optimize Feedback Resolution Process",
                        "description": "Implement automated routing and staff training to improve resolution efficiency",
                        "expected_impact": "Reduce resolution time by 30-50%",
                        "timeline": "1-2 months",
                    }
                )

        # Based on trends
        if trend_analysis["trends"]["review_volume"] == "declining":
            recommendations.append(
                {
                    "priority": "medium",
                    "category": "engagement",
                    "title": "Increase Review Collection",
                    "description": "Implement review request campaigns and incentive programs",
                    "expected_impact": "20-40% increase in review volume",
                    "timeline": "1 month",
                }
            )

        return recommendations

    def _calculate_review_volume_metrics(
        self, query, timeframe: AnalyticsTimeframe
    ) -> Dict[str, Any]:
        """Calculate review volume metrics"""

        total_reviews = query.count()

        # Daily average
        days = (timeframe.end_date - timeframe.start_date).days
        daily_average = total_reviews / max(days, 1)

        # Growth rate compared to previous period
        prev_period_start = timeframe.start_date - (
            timeframe.end_date - timeframe.start_date
        )
        prev_period_reviews = (
            self.db.query(Review)
            .filter(
                and_(
                    Review.created_at >= prev_period_start,
                    Review.created_at < timeframe.start_date,
                    Review.status == ReviewStatus.APPROVED,
                )
            )
            .count()
        )

        growth_rate = 0
        if prev_period_reviews > 0:
            growth_rate = (
                (total_reviews - prev_period_reviews) / prev_period_reviews
            ) * 100

        return {
            "total_reviews": total_reviews,
            "daily_average": round(daily_average, 2),
            "growth_rate": round(growth_rate, 2),
            "previous_period_reviews": prev_period_reviews,
        }

    def _calculate_rating_metrics(self, query) -> Dict[str, Any]:
        """Calculate detailed rating metrics"""

        reviews = query.all()
        if not reviews:
            return {}

        ratings = [r.rating for r in reviews]

        # Basic statistics
        avg_rating = sum(ratings) / len(ratings)
        min_rating = min(ratings)
        max_rating = max(ratings)

        # Rating distribution
        rating_counts = defaultdict(int)
        for rating in ratings:
            rating_counts[int(rating)] += 1

        # Percentiles
        sorted_ratings = sorted(ratings)
        median_rating = sorted_ratings[len(sorted_ratings) // 2]

        return {
            "average_rating": round(avg_rating, 2),
            "median_rating": median_rating,
            "min_rating": min_rating,
            "max_rating": max_rating,
            "rating_distribution": dict(rating_counts),
            "standard_deviation": self._calculate_std_dev(ratings, avg_rating),
        }

    def _calculate_engagement_metrics(self, query) -> Dict[str, Any]:
        """Calculate review engagement metrics"""

        reviews = query.all()
        if not reviews:
            return {}

        total_votes = sum(r.total_votes for r in reviews)
        helpful_votes = sum(r.helpful_votes for r in reviews)

        # Response rate
        responses = sum(1 for r in reviews if r.has_business_response)
        response_rate = (responses / len(reviews)) * 100

        # Media usage
        with_media = sum(1 for r in reviews if r.media_count > 0)
        media_rate = (with_media / len(reviews)) * 100

        return {
            "total_votes": total_votes,
            "helpful_votes": helpful_votes,
            "helpful_percentage": round((helpful_votes / max(total_votes, 1)) * 100, 1),
            "business_response_rate": round(response_rate, 1),
            "media_usage_rate": round(media_rate, 1),
            "average_votes_per_review": round(total_votes / len(reviews), 2),
        }

    def _calculate_review_quality_metrics(self, query) -> Dict[str, Any]:
        """Calculate review quality metrics"""

        reviews = query.all()
        if not reviews:
            return {}

        # Content length analysis
        content_lengths = [len(r.content) for r in reviews]
        avg_content_length = sum(content_lengths) / len(content_lengths)

        # Verification rate
        verified = sum(1 for r in reviews if r.is_verified_purchase)
        verification_rate = (verified / len(reviews)) * 100

        # Sentiment quality
        positive_sentiment = sum(
            1
            for r in reviews
            if r.sentiment_score
            in [SentimentScore.POSITIVE, SentimentScore.VERY_POSITIVE]
        )
        positive_rate = (positive_sentiment / len(reviews)) * 100

        return {
            "average_content_length": round(avg_content_length, 1),
            "verification_rate": round(verification_rate, 1),
            "positive_sentiment_rate": round(positive_rate, 1),
            "featured_reviews": sum(1 for r in reviews if r.is_featured),
        }

    def _calculate_temporal_trends(
        self, query, timeframe: AnalyticsTimeframe
    ) -> List[Dict[str, Any]]:
        """Calculate temporal trends for the timeframe"""

        # Group by day/week/month based on timeframe
        if timeframe.period_type == "daily":
            date_format = "%Y-%m-%d"
            date_trunc = "day"
        elif timeframe.period_type == "weekly":
            date_format = "%Y-W%U"
            date_trunc = "week"
        else:  # monthly
            date_format = "%Y-%m"
            date_trunc = "month"

        # SQL query to group by time period
        temporal_query = text(
            f"""
            SELECT 
                DATE_TRUNC('{date_trunc}', created_at) as period,
                COUNT(*) as review_count,
                AVG(rating) as avg_rating,
                COUNT(CASE WHEN sentiment_score IN ('positive', 'very_positive') THEN 1 END) as positive_reviews
            FROM reviews 
            WHERE created_at >= :start_date 
                AND created_at <= :end_date 
                AND status = 'approved'
            GROUP BY DATE_TRUNC('{date_trunc}', created_at)
            ORDER BY period
        """
        )

        result = self.db.execute(
            temporal_query,
            {"start_date": timeframe.start_date, "end_date": timeframe.end_date},
        )

        trends = []
        for row in result:
            trends.append(
                {
                    "period": row.period.strftime(date_format),
                    "review_count": row.review_count,
                    "avg_rating": round(float(row.avg_rating), 2),
                    "positive_reviews": row.positive_reviews,
                    "positive_rate": (
                        round((row.positive_reviews / row.review_count) * 100, 1)
                        if row.review_count > 0
                        else 0
                    ),
                }
            )

        return trends

    # Additional helper methods for calculations

    def _calculate_std_dev(self, values: List[float], mean: float) -> float:
        """Calculate standard deviation"""
        if len(values) <= 1:
            return 0.0

        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return round(variance**0.5, 3)

    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction from a series of values"""
        if len(values) < 2:
            return "stable"

        # Simple linear trend
        increases = 0
        decreases = 0

        for i in range(1, len(values)):
            if values[i] > values[i - 1]:
                increases += 1
            elif values[i] < values[i - 1]:
                decreases += 1

        if increases > decreases:
            return "increasing"
        elif decreases > increases:
            return "declining"
        else:
            return "stable"

    def _count_reviews_in_period(self, start: datetime, end: datetime) -> int:
        """Count reviews in a specific period"""
        return (
            self.db.query(Review)
            .filter(
                and_(
                    Review.created_at >= start,
                    Review.created_at <= end,
                    Review.status == ReviewStatus.APPROVED,
                )
            )
            .count()
        )

    def _get_avg_rating_in_period(self, start: datetime, end: datetime) -> float:
        """Get average rating in a specific period"""
        result = (
            self.db.query(func.avg(Review.rating))
            .filter(
                and_(
                    Review.created_at >= start,
                    Review.created_at <= end,
                    Review.status == ReviewStatus.APPROVED,
                )
            )
            .scalar()
        )

        return round(float(result or 0), 2)

    def _count_feedback_in_period(self, start: datetime, end: datetime) -> int:
        """Count feedback in a specific period"""
        return (
            self.db.query(Feedback)
            .filter(and_(Feedback.created_at >= start, Feedback.created_at <= end))
            .count()
        )

    async def _get_real_time_metrics(self) -> Dict[str, Any]:
        """Get real-time metrics for dashboard"""

        current_time = datetime.utcnow()

        # Last hour activity
        last_hour = current_time - timedelta(hours=1)

        metrics = {
            "reviews_last_hour": self._count_reviews_in_period(last_hour, current_time),
            "feedback_last_hour": self._count_feedback_in_period(
                last_hour, current_time
            ),
            "avg_rating_last_hour": self._get_avg_rating_in_period(
                last_hour, current_time
            ),
            "pending_moderation": self._count_pending_moderation(),
            "active_users": self._count_active_users(hours=1),
        }

        return metrics

    def _count_pending_moderation(self) -> int:
        """Count items pending moderation"""
        reviews_pending = (
            self.db.query(Review)
            .filter(Review.status.in_([ReviewStatus.PENDING, ReviewStatus.FLAGGED]))
            .count()
        )

        feedback_pending = (
            self.db.query(Feedback)
            .filter(Feedback.status == FeedbackStatus.NEW)
            .count()
        )

        return reviews_pending + feedback_pending

    def _count_active_users(self, hours: int = 24) -> int:
        """Count active users in the last N hours"""
        since = datetime.utcnow() - timedelta(hours=hours)

        # Count unique customers who created reviews or feedback
        review_customers = (
            self.db.query(Review.customer_id)
            .filter(Review.created_at >= since)
            .distinct()
        )

        feedback_customers = (
            self.db.query(Feedback.customer_id)
            .filter(
                and_(Feedback.created_at >= since, Feedback.customer_id.isnot(None))
            )
            .distinct()
        )

        # Combine and count unique
        all_customers = set()
        for customer in review_customers:
            all_customers.add(customer[0])
        for customer in feedback_customers:
            all_customers.add(customer[0])

        return len(all_customers)


# Service factory function
def create_analytics_service(db: Session) -> FeedbackAnalyticsService:
    """Create an analytics service instance"""
    return FeedbackAnalyticsService(db)
