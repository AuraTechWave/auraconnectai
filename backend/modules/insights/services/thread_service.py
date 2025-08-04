# backend/modules/insights/services/thread_service.py

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, update
from sqlalchemy.orm import selectinload
import logging
import hashlib
import json
from decimal import Decimal

from ..models.insight_models import Insight, InsightThread, InsightStatus
from ..metrics.insight_metrics import insight_metrics
from core.exceptions import BusinessLogicError, ResourceNotFoundError

logger = logging.getLogger(__name__)


class InsightThreadService:
    """Service for managing insight threads and grouping"""
    
    def __init__(self):
        self.thread_categories = [
            "recurring_issue",
            "trend_pattern",
            "seasonal_event",
            "optimization_series",
            "anomaly_cluster"
        ]
    
    async def create_or_update_thread(
        self,
        db: AsyncSession,
        insight: Insight,
        force_new: bool = False
    ) -> Optional[InsightThread]:
        """Create or update thread for an insight"""
        
        if force_new or not insight.thread_id:
            # Generate thread ID based on insight characteristics
            thread_id = self._generate_thread_id(insight)
        else:
            thread_id = insight.thread_id
        
        # Check if thread exists
        existing_thread = await db.execute(
            select(InsightThread).where(
                InsightThread.thread_id == thread_id
            )
        )
        thread = existing_thread.scalar_one_or_none()
        
        if thread:
            # Update existing thread
            thread.last_insight_date = datetime.utcnow()
            thread.total_insights += 1
            
            if insight.estimated_value:
                thread.total_value = (thread.total_value or 0) + insight.estimated_value
            
            # Check for recurrence pattern
            if thread.total_insights >= 3:
                thread.is_recurring = await self._detect_recurrence_pattern(
                    db, thread_id
                )
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
                total_value=insight.estimated_value or 0,
                is_active=True
            )
            db.add(thread)
        
        # Update insight with thread ID
        insight.thread_id = thread_id
        
        await db.commit()
        
        # Record metrics
        if thread.total_insights > 0:
            insight_metrics.record_thread_length(
                thread.category or "unknown",
                thread.total_insights
            )
        
        return thread
    
    async def find_similar_insights(
        self,
        db: AsyncSession,
        insight: Insight,
        similarity_threshold: float = 0.7
    ) -> List[Insight]:
        """Find similar insights that could be part of the same thread"""
        
        # Get recent insights of same type and domain
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        query = select(Insight).where(
            and_(
                Insight.restaurant_id == insight.restaurant_id,
                Insight.type == insight.type,
                Insight.domain == insight.domain,
                Insight.id != insight.id,
                Insight.created_at >= cutoff_date
            )
        )
        
        result = await db.execute(query)
        candidates = result.scalars().all()
        
        similar_insights = []
        
        for candidate in candidates:
            similarity = self._calculate_similarity(insight, candidate)
            if similarity >= similarity_threshold:
                similar_insights.append({
                    "insight": candidate,
                    "similarity": similarity
                })
        
        # Sort by similarity
        similar_insights.sort(key=lambda x: x["similarity"], reverse=True)
        
        return [item["insight"] for item in similar_insights]
    
    async def merge_threads(
        self,
        db: AsyncSession,
        restaurant_id: int,
        thread_ids: List[str]
    ) -> InsightThread:
        """Merge multiple threads into one"""
        
        if len(thread_ids) < 2:
            raise BusinessLogicError("At least 2 threads required for merging")
        
        # Get all threads
        threads_result = await db.execute(
            select(InsightThread).where(
                and_(
                    InsightThread.restaurant_id == restaurant_id,
                    InsightThread.thread_id.in_(thread_ids)
                )
            )
        )
        threads = threads_result.scalars().all()
        
        if len(threads) != len(thread_ids):
            raise ResourceNotFoundError("One or more threads not found")
        
        # Select primary thread (one with most insights)
        primary_thread = max(threads, key=lambda t: t.total_insights)
        other_threads = [t for t in threads if t.thread_id != primary_thread.thread_id]
        
        # Update all insights to point to primary thread
        for thread in other_threads:
            await db.execute(
                update(Insight).where(
                    Insight.thread_id == thread.thread_id
                ).values(thread_id=primary_thread.thread_id)
            )
            
            # Aggregate metrics
            primary_thread.total_insights += thread.total_insights
            primary_thread.total_value = (
                (primary_thread.total_value or 0) + (thread.total_value or 0)
            )
            
            # Update date range
            if thread.first_insight_date < primary_thread.first_insight_date:
                primary_thread.first_insight_date = thread.first_insight_date
            if thread.last_insight_date > primary_thread.last_insight_date:
                primary_thread.last_insight_date = thread.last_insight_date
            
            # Delete merged thread
            await db.delete(thread)
        
        # Update primary thread
        primary_thread.title = f"Merged Thread: {primary_thread.title}"
        primary_thread.description = (
            f"Merged from {len(threads)} threads. " + 
            (primary_thread.description or "")
        )
        
        await db.commit()
        await db.refresh(primary_thread)
        
        return primary_thread
    
    async def split_thread(
        self,
        db: AsyncSession,
        restaurant_id: int,
        thread_id: str,
        insight_ids: List[int]
    ) -> Tuple[InsightThread, InsightThread]:
        """Split insights from a thread into a new thread"""
        
        # Get original thread
        original_thread = await self._get_thread(db, thread_id, restaurant_id)
        
        # Validate insights belong to thread
        insights_result = await db.execute(
            select(Insight).where(
                and_(
                    Insight.restaurant_id == restaurant_id,
                    Insight.thread_id == thread_id,
                    Insight.id.in_(insight_ids)
                )
            )
        )
        insights_to_split = insights_result.scalars().all()
        
        if len(insights_to_split) != len(insight_ids):
            raise BusinessLogicError("Some insights not found in thread")
        
        # Create new thread
        new_thread_id = f"{thread_id}_split_{datetime.utcnow().timestamp()}"
        new_thread = InsightThread(
            thread_id=new_thread_id,
            restaurant_id=restaurant_id,
            title=f"Split from: {original_thread.title}",
            description="Thread created from split operation",
            category=original_thread.category,
            first_insight_date=min(i.created_at for i in insights_to_split),
            last_insight_date=max(i.created_at for i in insights_to_split),
            total_insights=len(insights_to_split),
            total_value=sum(i.estimated_value or 0 for i in insights_to_split),
            is_active=True
        )
        db.add(new_thread)
        
        # Update insights
        for insight in insights_to_split:
            insight.thread_id = new_thread_id
        
        # Update original thread metrics
        original_thread.total_insights -= len(insights_to_split)
        original_thread.total_value = (
            (original_thread.total_value or 0) - 
            sum(i.estimated_value or 0 for i in insights_to_split)
        )
        
        await db.commit()
        await db.refresh(original_thread)
        await db.refresh(new_thread)
        
        return original_thread, new_thread
    
    async def get_thread_timeline(
        self,
        db: AsyncSession,
        restaurant_id: int,
        thread_id: str
    ) -> Dict[str, Any]:
        """Get timeline view of insights in a thread"""
        
        thread = await self._get_thread(db, thread_id, restaurant_id)
        
        # Get all insights in thread
        insights_result = await db.execute(
            select(Insight).where(
                and_(
                    Insight.restaurant_id == restaurant_id,
                    Insight.thread_id == thread_id
                )
            ).order_by(Insight.created_at)
        )
        insights = insights_result.scalars().all()
        
        # Build timeline
        timeline = []
        cumulative_value = Decimal(0)
        
        for insight in insights:
            if insight.estimated_value:
                cumulative_value += insight.estimated_value
            
            timeline.append({
                "id": insight.id,
                "date": insight.created_at,
                "title": insight.title,
                "severity": insight.severity,
                "status": insight.status,
                "impact_score": float(insight.impact_score) if insight.impact_score else None,
                "estimated_value": float(insight.estimated_value) if insight.estimated_value else None,
                "cumulative_value": float(cumulative_value)
            })
        
        # Calculate patterns
        patterns = await self._analyze_thread_patterns(insights)
        
        return {
            "thread": {
                "id": thread.thread_id,
                "title": thread.title,
                "category": thread.category,
                "total_insights": thread.total_insights,
                "total_value": float(thread.total_value) if thread.total_value else 0,
                "is_recurring": thread.is_recurring
            },
            "timeline": timeline,
            "patterns": patterns,
            "summary": {
                "duration_days": (thread.last_insight_date - thread.first_insight_date).days,
                "avg_insights_per_week": (
                    thread.total_insights / max(1, (thread.last_insight_date - thread.first_insight_date).days / 7)
                ),
                "resolution_rate": sum(
                    1 for i in insights if i.status == InsightStatus.RESOLVED
                ) / len(insights) if insights else 0
            }
        }
    
    async def get_active_threads(
        self,
        db: AsyncSession,
        restaurant_id: int,
        category: Optional[str] = None,
        min_insights: int = 2
    ) -> List[Dict[str, Any]]:
        """Get active threads with summary"""
        
        query = select(InsightThread).where(
            and_(
                InsightThread.restaurant_id == restaurant_id,
                InsightThread.is_active == True,
                InsightThread.total_insights >= min_insights
            )
        )
        
        if category:
            query = query.where(InsightThread.category == category)
        
        query = query.order_by(InsightThread.last_insight_date.desc())
        
        result = await db.execute(query)
        threads = result.scalars().all()
        
        thread_summaries = []
        
        for thread in threads:
            # Get latest insight
            latest_insight_result = await db.execute(
                select(Insight).where(
                    and_(
                        Insight.restaurant_id == restaurant_id,
                        Insight.thread_id == thread.thread_id
                    )
                ).order_by(Insight.created_at.desc()).limit(1)
            )
            latest_insight = latest_insight_result.scalar_one_or_none()
            
            thread_summaries.append({
                "thread_id": thread.thread_id,
                "title": thread.title,
                "category": thread.category,
                "total_insights": thread.total_insights,
                "total_value": float(thread.total_value) if thread.total_value else 0,
                "is_recurring": thread.is_recurring,
                "first_date": thread.first_insight_date,
                "last_date": thread.last_insight_date,
                "latest_insight": {
                    "id": latest_insight.id,
                    "title": latest_insight.title,
                    "severity": latest_insight.severity
                } if latest_insight else None
            })
        
        return thread_summaries
    
    def _generate_thread_id(self, insight: Insight) -> str:
        """Generate thread ID based on insight characteristics"""
        
        # Create hash from key characteristics
        components = [
            str(insight.restaurant_id),
            insight.type.value,
            insight.domain.value,
            insight.related_entity_type or "none"
        ]
        
        # Add metrics pattern if available
        if insight.metrics:
            metric_keys = sorted(insight.metrics.keys())
            components.extend(metric_keys[:3])  # Top 3 metric keys
        
        hash_input = "|".join(components)
        return hashlib.md5(hash_input.encode()).hexdigest()[:16]
    
    def _generate_thread_title(self, insight: Insight) -> str:
        """Generate descriptive thread title"""
        
        return f"{insight.type.value.title()} - {insight.domain.value.title()}"
    
    def _determine_thread_category(self, insight: Insight) -> str:
        """Determine thread category based on insight"""
        
        if insight.type.value in ["trend", "pattern"]:
            return "trend_pattern"
        elif insight.type.value == "anomaly":
            return "anomaly_cluster"
        elif insight.type.value == "optimization":
            return "optimization_series"
        elif "seasonal" in insight.title.lower():
            return "seasonal_event"
        else:
            return "recurring_issue"
    
    def _calculate_similarity(self, insight1: Insight, insight2: Insight) -> float:
        """Calculate similarity score between two insights"""
        
        score = 0.0
        
        # Type and domain match (40%)
        if insight1.type == insight2.type:
            score += 0.2
        if insight1.domain == insight2.domain:
            score += 0.2
        
        # Entity match (20%)
        if (insight1.related_entity_type == insight2.related_entity_type and
            insight1.related_entity_id == insight2.related_entity_id):
            score += 0.2
        
        # Metric overlap (20%)
        if insight1.metrics and insight2.metrics:
            keys1 = set(insight1.metrics.keys())
            keys2 = set(insight2.metrics.keys())
            overlap = len(keys1.intersection(keys2))
            total = len(keys1.union(keys2))
            if total > 0:
                score += 0.2 * (overlap / total)
        
        # Title similarity (20%)
        title_similarity = self._text_similarity(insight1.title, insight2.title)
        score += 0.2 * title_similarity
        
        return score
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Simple text similarity using word overlap"""
        
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    async def _detect_recurrence_pattern(
        self,
        db: AsyncSession,
        thread_id: str
    ) -> bool:
        """Detect if insights in thread follow a recurrence pattern"""
        
        # Get insight dates
        result = await db.execute(
            select(Insight.created_at).where(
                Insight.thread_id == thread_id
            ).order_by(Insight.created_at)
        )
        
        dates = [row[0] for row in result]
        
        if len(dates) < 3:
            return False
        
        # Calculate intervals
        intervals = []
        for i in range(1, len(dates)):
            interval = (dates[i] - dates[i-1]).days
            intervals.append(interval)
        
        # Check for regular intervals (within 20% variance)
        if intervals:
            avg_interval = sum(intervals) / len(intervals)
            variance = sum(abs(i - avg_interval) for i in intervals) / len(intervals)
            
            return variance / avg_interval < 0.2 if avg_interval > 0 else False
        
        return False
    
    async def _analyze_thread_patterns(
        self,
        insights: List[Insight]
    ) -> Dict[str, Any]:
        """Analyze patterns in thread insights"""
        
        if not insights:
            return {}
        
        # Time patterns
        dates = [i.created_at for i in insights]
        intervals = []
        for i in range(1, len(dates)):
            intervals.append((dates[i] - dates[i-1]).days)
        
        # Severity patterns
        severities = [i.severity.value for i in insights]
        severity_changes = []
        for i in range(1, len(severities)):
            if severities[i] != severities[i-1]:
                severity_changes.append({
                    "from": severities[i-1],
                    "to": severities[i],
                    "date": dates[i]
                })
        
        # Value trends
        values = [float(i.estimated_value) if i.estimated_value else 0 for i in insights]
        value_trend = "stable"
        if len(values) >= 3:
            first_half_avg = sum(values[:len(values)//2]) / (len(values)//2)
            second_half_avg = sum(values[len(values)//2:]) / (len(values) - len(values)//2)
            
            if second_half_avg > first_half_avg * 1.2:
                value_trend = "increasing"
            elif second_half_avg < first_half_avg * 0.8:
                value_trend = "decreasing"
        
        return {
            "avg_interval_days": sum(intervals) / len(intervals) if intervals else 0,
            "min_interval_days": min(intervals) if intervals else 0,
            "max_interval_days": max(intervals) if intervals else 0,
            "severity_changes": severity_changes,
            "value_trend": value_trend,
            "common_recommendations": self._find_common_recommendations(insights)
        }
    
    def _find_common_recommendations(self, insights: List[Insight]) -> List[str]:
        """Find common recommendations across insights"""
        
        all_recommendations = []
        for insight in insights:
            if insight.recommendations:
                all_recommendations.extend(insight.recommendations)
        
        # Count occurrences
        rec_counts = {}
        for rec in all_recommendations:
            rec_counts[rec] = rec_counts.get(rec, 0) + 1
        
        # Return most common (appearing in >30% of insights)
        threshold = len(insights) * 0.3
        common = [
            rec for rec, count in rec_counts.items()
            if count >= threshold
        ]
        
        return sorted(common, key=lambda r: rec_counts[r], reverse=True)[:5]
    
    async def _get_thread(
        self,
        db: AsyncSession,
        thread_id: str,
        restaurant_id: int
    ) -> InsightThread:
        """Get thread with validation"""
        
        result = await db.execute(
            select(InsightThread).where(
                and_(
                    InsightThread.thread_id == thread_id,
                    InsightThread.restaurant_id == restaurant_id
                )
            )
        )
        thread = result.scalar_one_or_none()
        
        if not thread:
            raise ResourceNotFoundError(f"Thread {thread_id} not found")
        
        return thread


# Create singleton service
insight_thread_service = InsightThreadService()