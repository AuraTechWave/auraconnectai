# backend/modules/insights/services/insights_service.py

"""
Core service for managing business insights.
"""

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc, asc
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, date, timedelta
import json
import logging
from decimal import Decimal

from ..models.insight_models import (
    Insight, InsightRating, InsightAction, InsightThread,
    InsightType, InsightSeverity, InsightStatus, InsightDomain
)
from ..schemas.insight_schemas import (
    InsightCreate, InsightUpdate, InsightFilters,
    InsightActionCreate, InsightSummary
)
from modules.core.models import Restaurant

logger = logging.getLogger(__name__)


class InsightsService:
    """Service for managing business insights"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_insight(
        self,
        insight_data: InsightCreate,
        generated_by: str = "system"
    ) -> Insight:
        """Create a new insight"""
        insight = Insight(
            restaurant_id=insight_data.restaurant_id,
            type=insight_data.type,
            severity=insight_data.severity,
            domain=insight_data.domain,
            title=insight_data.title,
            description=insight_data.description,
            impact_score=insight_data.impact_score,
            estimated_value=insight_data.estimated_value,
            recommendations=insight_data.recommendations or [],
            metrics=insight_data.metrics or {},
            trend_data=insight_data.trend_data or {},
            comparison_data=insight_data.comparison_data or {},
            related_entity_type=insight_data.related_entity_type,
            related_entity_id=insight_data.related_entity_id,
            time_period=insight_data.time_period or {},
            thread_id=insight_data.thread_id,
            parent_insight_id=insight_data.parent_insight_id,
            generated_by=generated_by,
            confidence_score=insight_data.confidence_score,
            expires_at=insight_data.expires_at,
            notification_config=insight_data.notification_config or {}
        )
        
        self.db.add(insight)
        self.db.commit()
        self.db.refresh(insight)
        
        # Update thread if applicable
        if insight.thread_id:
            self._update_thread_stats(insight.thread_id)
        
        logger.info(f"Created insight {insight.id} for restaurant {insight.restaurant_id}")
        return insight
    
    def get_insight(self, insight_id: int) -> Optional[Insight]:
        """Get insight by ID"""
        return self.db.query(Insight).filter(
            Insight.id == insight_id
        ).options(
            joinedload(Insight.ratings),
            joinedload(Insight.actions)
        ).first()
    
    def list_insights(
        self,
        filters: InsightFilters,
        skip: int = 0,
        limit: int = 50,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Tuple[List[Insight], int]:
        """List insights with filters"""
        query = self.db.query(Insight)
        
        # Apply filters
        if filters.restaurant_id:
            query = query.filter(Insight.restaurant_id == filters.restaurant_id)
        
        if filters.domain:
            query = query.filter(Insight.domain == filters.domain)
        
        if filters.type:
            query = query.filter(Insight.type == filters.type)
        
        if filters.severity:
            query = query.filter(Insight.severity == filters.severity)
        
        if filters.status:
            query = query.filter(Insight.status == filters.status)
        
        if filters.thread_id:
            query = query.filter(Insight.thread_id == filters.thread_id)
        
        if filters.date_from:
            query = query.filter(Insight.created_at >= filters.date_from)
        
        if filters.date_to:
            query = query.filter(Insight.created_at <= filters.date_to)
        
        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    Insight.title.ilike(search_term),
                    Insight.description.ilike(search_term)
                )
            )
        
        # Get total count
        total = query.count()
        
        # Apply sorting
        if sort_by == "severity":
            # Custom severity ordering
            severity_order = {
                InsightSeverity.CRITICAL: 1,
                InsightSeverity.HIGH: 2,
                InsightSeverity.MEDIUM: 3,
                InsightSeverity.LOW: 4,
                InsightSeverity.INFO: 5
            }
            insights = query.all()
            insights.sort(
                key=lambda x: (severity_order.get(x.severity, 999), x.created_at),
                reverse=(sort_order == "desc")
            )
            # Apply pagination after sorting
            insights = insights[skip:skip + limit]
        else:
            # Regular sorting
            sort_column = getattr(Insight, sort_by, Insight.created_at)
            if sort_order == "desc":
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))
            
            # Apply pagination
            insights = query.offset(skip).limit(limit).all()
        
        return insights, total
    
    def update_insight(
        self,
        insight_id: int,
        update_data: InsightUpdate,
        user_id: int
    ) -> Optional[Insight]:
        """Update an insight"""
        insight = self.get_insight(insight_id)
        if not insight:
            return None
        
        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        
        # Handle status changes
        if "status" in update_dict:
            new_status = update_dict["status"]
            if new_status == InsightStatus.ACKNOWLEDGED:
                insight.acknowledged_by_id = user_id
                insight.acknowledged_at = datetime.utcnow()
            elif new_status == InsightStatus.RESOLVED:
                insight.resolved_by_id = user_id
                insight.resolved_at = datetime.utcnow()
        
        # Update other fields
        for field, value in update_dict.items():
            if hasattr(insight, field):
                setattr(insight, field, value)
        
        insight.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(insight)
        
        return insight
    
    def delete_insight(self, insight_id: int) -> bool:
        """Soft delete an insight"""
        insight = self.get_insight(insight_id)
        if not insight:
            return False
        
        insight.status = InsightStatus.DISMISSED
        insight.updated_at = datetime.utcnow()
        
        self.db.commit()
        return True
    
    def acknowledge_insight(self, insight_id: int, user_id: int) -> Optional[Insight]:
        """Acknowledge an insight"""
        return self.update_insight(
            insight_id,
            InsightUpdate(status=InsightStatus.ACKNOWLEDGED),
            user_id
        )
    
    def dismiss_insight(self, insight_id: int, user_id: int) -> Optional[Insight]:
        """Dismiss an insight"""
        return self.update_insight(
            insight_id,
            InsightUpdate(status=InsightStatus.DISMISSED),
            user_id
        )
    
    def log_action(
        self,
        insight_id: int,
        user_id: int,
        action_data: InsightActionCreate
    ) -> InsightAction:
        """Log an action taken on an insight"""
        action = InsightAction(
            insight_id=insight_id,
            user_id=user_id,
            action_type=action_data.action_type,
            action_details=action_data.action_details or {}
        )
        
        self.db.add(action)
        self.db.commit()
        self.db.refresh(action)
        
        return action
    
    def get_insights_summary(
        self,
        restaurant_id: int,
        domain: Optional[InsightDomain] = None,
        days: int = 30
    ) -> InsightSummary:
        """Get summary statistics for insights"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Base query
        query = self.db.query(Insight).filter(
            Insight.restaurant_id == restaurant_id,
            Insight.created_at >= start_date
        )
        
        if domain:
            query = query.filter(Insight.domain == domain)
        
        # Get counts by status
        status_counts = {}
        for status in InsightStatus:
            count = query.filter(Insight.status == status).count()
            status_counts[status.value] = count
        
        # Get counts by severity
        severity_counts = {}
        for severity in InsightSeverity:
            count = query.filter(Insight.severity == severity).count()
            severity_counts[severity.value] = count
        
        # Get total estimated value
        total_value = self.db.query(
            func.sum(Insight.estimated_value)
        ).filter(
            Insight.restaurant_id == restaurant_id,
            Insight.created_at >= start_date,
            Insight.status.in_([InsightStatus.ACTIVE, InsightStatus.ACKNOWLEDGED])
        ).scalar() or 0
        
        # Get average impact score
        avg_impact = self.db.query(
            func.avg(Insight.impact_score)
        ).filter(
            Insight.restaurant_id == restaurant_id,
            Insight.created_at >= start_date
        ).scalar() or 0
        
        # Get trend data (insights per day)
        trend_data = []
        for i in range(days):
            day = start_date + timedelta(days=i)
            next_day = day + timedelta(days=1)
            
            count = self.db.query(func.count(Insight.id)).filter(
                Insight.restaurant_id == restaurant_id,
                Insight.created_at >= day,
                Insight.created_at < next_day
            ).scalar()
            
            trend_data.append({
                "date": day.date().isoformat(),
                "count": count
            })
        
        return InsightSummary(
            total_insights=query.count(),
            status_breakdown=status_counts,
            severity_breakdown=severity_counts,
            total_estimated_value=float(total_value),
            average_impact_score=float(avg_impact),
            trend_data=trend_data,
            period_days=days
        )
    
    def get_thread_insights(self, thread_id: str) -> List[Insight]:
        """Get all insights in a thread"""
        return self.db.query(Insight).filter(
            Insight.thread_id == thread_id
        ).order_by(Insight.created_at.desc()).all()
    
    def get_trend_analysis(
        self,
        restaurant_id: int,
        domain: Optional[InsightDomain] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Analyze insight trends"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Base query
        query = self.db.query(Insight).filter(
            Insight.restaurant_id == restaurant_id,
            Insight.created_at >= start_date
        )
        
        if domain:
            query = query.filter(Insight.domain == domain)
        
        insights = query.all()
        
        # Analyze patterns
        daily_counts = {}
        severity_trends = {s.value: [] for s in InsightSeverity}
        domain_distribution = {}
        
        for insight in insights:
            # Daily counts
            day_key = insight.created_at.date().isoformat()
            daily_counts[day_key] = daily_counts.get(day_key, 0) + 1
            
            # Severity trends
            severity_trends[insight.severity.value].append({
                "date": insight.created_at.isoformat(),
                "impact_score": float(insight.impact_score) if insight.impact_score else 0
            })
            
            # Domain distribution
            domain_distribution[insight.domain.value] = domain_distribution.get(insight.domain.value, 0) + 1
        
        # Calculate growth rate
        if len(daily_counts) >= 2:
            sorted_days = sorted(daily_counts.keys())
            first_week_avg = sum(daily_counts.get(d, 0) for d in sorted_days[:7]) / 7
            last_week_avg = sum(daily_counts.get(d, 0) for d in sorted_days[-7:]) / 7
            growth_rate = ((last_week_avg - first_week_avg) / first_week_avg * 100) if first_week_avg > 0 else 0
        else:
            growth_rate = 0
        
        return {
            "daily_counts": daily_counts,
            "severity_trends": severity_trends,
            "domain_distribution": domain_distribution,
            "growth_rate": round(growth_rate, 2),
            "total_insights": len(insights),
            "average_daily": round(len(insights) / days, 2)
        }
    
    def get_impact_analysis(
        self,
        restaurant_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Analyze business impact of insights"""
        query = self.db.query(Insight).filter(
            Insight.restaurant_id == restaurant_id
        )
        
        if start_date:
            query = query.filter(Insight.created_at >= start_date)
        if end_date:
            query = query.filter(Insight.created_at <= end_date)
        
        insights = query.all()
        
        # Calculate impact metrics
        total_value = sum(float(i.estimated_value) for i in insights if i.estimated_value)
        implemented_value = sum(
            float(i.estimated_value) for i in insights 
            if i.estimated_value and i.status == InsightStatus.RESOLVED
        )
        
        # Domain impact
        domain_impact = {}
        for insight in insights:
            if insight.estimated_value:
                domain = insight.domain.value
                if domain not in domain_impact:
                    domain_impact[domain] = {
                        "total_value": 0,
                        "implemented_value": 0,
                        "count": 0
                    }
                
                domain_impact[domain]["total_value"] += float(insight.estimated_value)
                domain_impact[domain]["count"] += 1
                
                if insight.status == InsightStatus.RESOLVED:
                    domain_impact[domain]["implemented_value"] += float(insight.estimated_value)
        
        # Calculate ROI indicators
        high_impact_insights = [
            {
                "id": i.id,
                "title": i.title,
                "estimated_value": float(i.estimated_value),
                "impact_score": float(i.impact_score),
                "status": i.status.value
            }
            for i in insights
            if i.estimated_value and float(i.estimated_value) > 1000
        ]
        high_impact_insights.sort(key=lambda x: x["estimated_value"], reverse=True)
        
        return {
            "total_estimated_value": round(total_value, 2),
            "implemented_value": round(implemented_value, 2),
            "implementation_rate": round(implemented_value / total_value * 100, 2) if total_value > 0 else 0,
            "domain_impact": domain_impact,
            "high_impact_insights": high_impact_insights[:10],  # Top 10
            "insights_analyzed": len(insights)
        }
    
    async def export_insights(
        self,
        filters: InsightFilters,
        format: str,
        user_id: int
    ) -> str:
        """Export insights to file"""
        # Get all insights with filters
        insights, _ = self.list_insights(filters, skip=0, limit=10000)
        
        # Prepare data for export
        export_data = []
        for insight in insights:
            export_data.append({
                "id": insight.id,
                "created_at": insight.created_at.isoformat(),
                "type": insight.type.value,
                "severity": insight.severity.value,
                "domain": insight.domain.value,
                "status": insight.status.value,
                "title": insight.title,
                "description": insight.description,
                "impact_score": float(insight.impact_score) if insight.impact_score else 0,
                "estimated_value": float(insight.estimated_value) if insight.estimated_value else 0,
                "recommendations": json.dumps(insight.recommendations),
                "acknowledged_at": insight.acknowledged_at.isoformat() if insight.acknowledged_at else "",
                "resolved_at": insight.resolved_at.isoformat() if insight.resolved_at else ""
            })
        
        # TODO: Implement actual file generation and upload
        # For now, return a placeholder URL
        file_name = f"insights_export_{user_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{format}"
        
        logger.info(f"Exported {len(export_data)} insights to {file_name}")
        
        return f"/exports/{file_name}"
    
    def _update_thread_stats(self, thread_id: str):
        """Update thread statistics"""
        thread = self.db.query(InsightThread).filter(
            InsightThread.thread_id == thread_id
        ).first()
        
        if not thread:
            return
        
        # Get thread insights
        insights = self.get_thread_insights(thread_id)
        
        if insights:
            thread.first_insight_date = min(i.created_at for i in insights)
            thread.last_insight_date = max(i.created_at for i in insights)
            thread.total_insights = len(insights)
            thread.total_value = sum(
                float(i.estimated_value) for i in insights 
                if i.estimated_value
            )
        
        self.db.commit()