# backend/modules/insights/services/thread_service.py

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func
import logging
import hashlib

from ..models.insight_models import Insight, InsightThread
from ..schemas.insight_schemas import ThreadFilters

logger = logging.getLogger(__name__)


class InsightThreadService:
    """Service for managing insight threads and grouping"""

    def __init__(self, db: Session):
        self.db = db
        self.thread_categories = [
            "recurring_issue",
            "trend_pattern",
            "seasonal_event",
            "optimization_series",
            "anomaly_cluster",
        ]

    def create_or_update_thread(
        self, insight: Insight, force_new: bool = False
    ) -> Optional[InsightThread]:
        """Create or update thread for an insight"""

        if force_new or not insight.thread_id:
            # Generate thread ID based on insight characteristics
            thread_id = self._generate_thread_id(insight)
        else:
            thread_id = insight.thread_id

        # Check if thread exists
        thread = (
            self.db.query(InsightThread)
            .filter(InsightThread.thread_id == thread_id)
            .first()
        )

        if thread:
            # Update existing thread
            thread.last_insight_date = datetime.utcnow()
            thread.total_insights += 1

            if insight.estimated_value:
                thread.total_value = float(thread.total_value or 0) + float(
                    insight.estimated_value
                )

            # Check for recurrence pattern
            if thread.total_insights >= 3:
                thread.is_recurring = self._detect_recurrence_pattern(thread_id)
        else:
            # Create new thread
            thread = InsightThread(
                thread_id=thread_id,
                restaurant_id=insight.restaurant_id,
                title=self._generate_thread_title(insight),
                description=f"Thread for {insight.type.value} insights in {insight.domain.value}",
                category=self._determine_thread_category(insight),
                first_insight_date=datetime.utcnow(),
                last_insight_date=datetime.utcnow(),
                total_insights=1,
                total_value=(
                    float(insight.estimated_value) if insight.estimated_value else 0
                ),
                is_active=True,
            )
            self.db.add(thread)

        # Update insight with thread ID
        insight.thread_id = thread_id

        self.db.commit()

        return thread

    def get_thread(self, thread_id: str, restaurant_id: int) -> Optional[InsightThread]:
        """Get thread by ID"""
        return (
            self.db.query(InsightThread)
            .filter(
                InsightThread.thread_id == thread_id,
                InsightThread.restaurant_id == restaurant_id,
            )
            .first()
        )

    def list_threads(
        self, filters: ThreadFilters, skip: int = 0, limit: int = 50
    ) -> List[InsightThread]:
        """List threads with filters"""
        query = self.db.query(InsightThread)

        if filters.restaurant_id:
            query = query.filter(InsightThread.restaurant_id == filters.restaurant_id)

        if filters.is_active is not None:
            query = query.filter(InsightThread.is_active == filters.is_active)

        if filters.is_recurring is not None:
            query = query.filter(InsightThread.is_recurring == filters.is_recurring)

        if filters.category:
            query = query.filter(InsightThread.category == filters.category)

        # Order by last activity
        query = query.order_by(InsightThread.last_insight_date.desc())

        return query.offset(skip).limit(limit).all()

    def get_thread_timeline(self, thread_id: str, restaurant_id: int) -> Dict[str, Any]:
        """Get timeline of insights in a thread"""

        thread = self.get_thread(thread_id, restaurant_id)
        if not thread:
            return None

        # Get all insights in thread
        insights = (
            self.db.query(Insight)
            .filter(
                Insight.thread_id == thread_id, Insight.restaurant_id == restaurant_id
            )
            .order_by(Insight.created_at)
            .all()
        )

        # Build timeline
        timeline = []
        for insight in insights:
            timeline.append(
                {
                    "id": insight.id,
                    "created_at": insight.created_at,
                    "type": insight.type.value,
                    "severity": insight.severity.value,
                    "title": insight.title,
                    "status": insight.status.value,
                    "impact_score": (
                        float(insight.impact_score) if insight.impact_score else 0
                    ),
                    "estimated_value": (
                        float(insight.estimated_value) if insight.estimated_value else 0
                    ),
                }
            )

        # Analyze patterns
        patterns = self._analyze_thread_patterns(insights)

        return {
            "thread": {
                "id": thread.id,
                "thread_id": thread.thread_id,
                "title": thread.title,
                "category": thread.category,
                "is_recurring": thread.is_recurring,
                "total_insights": thread.total_insights,
                "total_value": float(thread.total_value),
            },
            "timeline": timeline,
            "patterns": patterns,
            "summary": {
                "first_date": thread.first_insight_date,
                "last_date": thread.last_insight_date,
                "duration_days": (
                    thread.last_insight_date - thread.first_insight_date
                ).days,
                "average_interval_days": self._calculate_average_interval(insights),
            },
        }

    def _generate_thread_id(self, insight: Insight) -> str:
        """Generate thread ID based on insight characteristics"""
        # Create a unique ID based on type, domain, and related entity
        components = [
            str(insight.restaurant_id),
            insight.type.value,
            insight.domain.value,
            insight.related_entity_type or "general",
            str(insight.related_entity_id or 0),
        ]

        # Hash the components
        hash_input = "-".join(components)
        return hashlib.md5(hash_input.encode()).hexdigest()[:16]

    def _generate_thread_title(self, insight: Insight) -> str:
        """Generate descriptive title for thread"""
        if insight.related_entity_type:
            return f"{insight.type.value.title()} - {insight.domain.value.title()} ({insight.related_entity_type})"
        else:
            return f"{insight.type.value.title()} - {insight.domain.value.title()}"

    def _determine_thread_category(self, insight: Insight) -> str:
        """Determine thread category based on insight type"""
        if insight.type.value in ["anomaly", "warning"]:
            return "anomaly_cluster"
        elif insight.type.value == "trend":
            return "trend_pattern"
        elif insight.type.value == "optimization":
            return "optimization_series"
        else:
            return "recurring_issue"

    def _detect_recurrence_pattern(self, thread_id: str) -> bool:
        """Detect if insights follow a recurring pattern"""
        # Get recent insights
        recent_insights = (
            self.db.query(Insight)
            .filter(Insight.thread_id == thread_id)
            .order_by(Insight.created_at.desc())
            .limit(5)
            .all()
        )

        if len(recent_insights) < 3:
            return False

        # Check for regular intervals
        intervals = []
        for i in range(1, len(recent_insights)):
            interval = (
                recent_insights[i - 1].created_at - recent_insights[i].created_at
            ).days
            intervals.append(interval)

        # Check if intervals are consistent (within 20% variance)
        if intervals:
            avg_interval = sum(intervals) / len(intervals)
            variance = sum(abs(i - avg_interval) for i in intervals) / len(intervals)

            # Consider recurring if variance is less than 20% of average
            return variance < (avg_interval * 0.2)

        return False

    def _analyze_thread_patterns(self, insights: List[Insight]) -> Dict[str, Any]:
        """Analyze patterns in thread insights"""
        if not insights:
            return {}

        # Time patterns
        time_gaps = []
        for i in range(1, len(insights)):
            gap = (insights[i].created_at - insights[i - 1].created_at).days
            time_gaps.append(gap)

        # Value trends
        values = [float(i.estimated_value) for i in insights if i.estimated_value]
        value_trend = (
            "increasing" if len(values) >= 2 and values[-1] > values[0] else "stable"
        )

        # Severity distribution
        severity_counts = {}
        for insight in insights:
            severity = insight.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        return {
            "frequency": {
                "average_gap_days": sum(time_gaps) / len(time_gaps) if time_gaps else 0,
                "min_gap_days": min(time_gaps) if time_gaps else 0,
                "max_gap_days": max(time_gaps) if time_gaps else 0,
            },
            "value_trend": value_trend,
            "total_value": sum(values),
            "severity_distribution": severity_counts,
        }

    def _calculate_average_interval(self, insights: List[Insight]) -> float:
        """Calculate average interval between insights"""
        if len(insights) < 2:
            return 0

        intervals = []
        for i in range(1, len(insights)):
            interval = (insights[i].created_at - insights[i - 1].created_at).days
            intervals.append(interval)

        return sum(intervals) / len(intervals) if intervals else 0
