# backend/modules/analytics/services/pos_trends_service.py

"""
Service for POS analytics trends.

Handles trend analysis and time-series data.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta, date
from decimal import Decimal
import logging

from core.cache import cache_service
from modules.analytics.models.pos_analytics_models import POSAnalyticsSnapshot
from .pos.base_service import POSAnalyticsBaseService

logger = logging.getLogger(__name__)


class POSTrendsService(POSAnalyticsBaseService):
    """Service for POS trends analysis"""
    
    CACHE_TTL = 600  # 10 minutes cache for trends
    
    async def get_transaction_trends(
        self,
        start_date: datetime,
        end_date: datetime,
        provider_id: Optional[int] = None,
        terminal_id: Optional[str] = None,
        granularity: str = "hourly"
    ) -> List[Dict[str, Any]]:
        """Get transaction trend data with caching"""
        
        # Generate cache key
        cache_key = f"trends:transactions:{granularity}:{start_date.date()}:{end_date.date()}"
        if provider_id:
            cache_key += f":provider_{provider_id}"
        if terminal_id:
            cache_key += f":terminal_{terminal_id}"
        
        # Try cache first
        cached_data = await cache_service.get(cache_key)
        if cached_data:
            import json
            return json.loads(cached_data)
        
        # Generate fresh data
        trends = await self._generate_transaction_trends(
            start_date, end_date, provider_id, terminal_id, granularity
        )
        
        # Cache the result
        import json
        await cache_service.set(cache_key, json.dumps(trends), ttl=self.CACHE_TTL)
        
        return trends
    
    async def _generate_transaction_trends(
        self,
        start_date: datetime,
        end_date: datetime,
        provider_id: Optional[int],
        terminal_id: Optional[str],
        granularity: str
    ) -> List[Dict[str, Any]]:
        """Generate transaction trend data"""
        
        # Build base query
        if granularity == "hourly":
            query = self.db.query(
                POSAnalyticsSnapshot.snapshot_date,
                POSAnalyticsSnapshot.snapshot_hour,
                func.sum(POSAnalyticsSnapshot.total_transactions).label("count"),
                func.sum(POSAnalyticsSnapshot.total_transaction_value).label("value"),
                func.sum(POSAnalyticsSnapshot.successful_transactions).label("successful")
            )
        else:
            query = self.db.query(
                POSAnalyticsSnapshot.snapshot_date,
                func.sum(POSAnalyticsSnapshot.total_transactions).label("count"),
                func.sum(POSAnalyticsSnapshot.total_transaction_value).label("value"),
                func.sum(POSAnalyticsSnapshot.successful_transactions).label("successful")
            )
        
        # Apply filters
        query = query.filter(
            POSAnalyticsSnapshot.snapshot_date >= start_date.date(),
            POSAnalyticsSnapshot.snapshot_date <= end_date.date()
        )
        
        if provider_id:
            query = query.filter(POSAnalyticsSnapshot.provider_id == provider_id)
        
        if terminal_id:
            query = query.filter(POSAnalyticsSnapshot.terminal_id == terminal_id)
        
        # Group and order
        if granularity == "hourly":
            query = query.group_by(
                POSAnalyticsSnapshot.snapshot_date,
                POSAnalyticsSnapshot.snapshot_hour
            ).order_by(
                POSAnalyticsSnapshot.snapshot_date,
                POSAnalyticsSnapshot.snapshot_hour
            )
        elif granularity == "daily":
            query = query.group_by(
                POSAnalyticsSnapshot.snapshot_date
            ).order_by(
                POSAnalyticsSnapshot.snapshot_date
            )
        elif granularity == "weekly":
            # Group by week
            query = self.db.query(
                func.date_trunc('week', POSAnalyticsSnapshot.snapshot_date).label("week"),
                func.sum(POSAnalyticsSnapshot.total_transactions).label("count"),
                func.sum(POSAnalyticsSnapshot.total_transaction_value).label("value"),
                func.sum(POSAnalyticsSnapshot.successful_transactions).label("successful")
            ).filter(
                POSAnalyticsSnapshot.snapshot_date >= start_date.date(),
                POSAnalyticsSnapshot.snapshot_date <= end_date.date()
            )
            
            if provider_id:
                query = query.filter(POSAnalyticsSnapshot.provider_id == provider_id)
            if terminal_id:
                query = query.filter(POSAnalyticsSnapshot.terminal_id == terminal_id)
            
            query = query.group_by("week").order_by("week")
        
        results = query.all()
        
        # Format results
        trends = []
        for row in results:
            if granularity == "hourly":
                timestamp = datetime.combine(row.snapshot_date, datetime.min.time()) + timedelta(hours=row.snapshot_hour)
            elif granularity == "daily":
                timestamp = datetime.combine(row.snapshot_date, datetime.min.time())
            else:  # weekly
                timestamp = row.week
            
            count = row.count or 0
            successful = row.successful or 0
            value = float(row.value or 0)
            
            trends.append({
                "timestamp": timestamp.isoformat(),
                "transaction_count": count,
                "transaction_value": value,
                "success_rate": (successful / count * 100) if count > 0 else 0.0,
                "average_value": value / count if count > 0 else 0.0
            })
        
        return trends
    
    async def get_performance_trends(
        self,
        metric: str,
        start_date: datetime,
        end_date: datetime,
        provider_id: Optional[int] = None,
        granularity: str = "daily"
    ) -> List[Dict[str, Any]]:
        """Get performance metric trends"""
        
        # Cache key
        cache_key = f"trends:{metric}:{granularity}:{start_date.date()}:{end_date.date()}"
        if provider_id:
            cache_key += f":provider_{provider_id}"
        
        # Try cache
        cached_data = await cache_service.get(cache_key)
        if cached_data:
            import json
            return json.loads(cached_data)
        
        # Generate based on metric
        if metric == "response_time":
            trends = await self._get_response_time_trends(
                start_date, end_date, provider_id, granularity
            )
        elif metric == "success_rate":
            trends = await self._get_success_rate_trends(
                start_date, end_date, provider_id, granularity
            )
        elif metric == "error_rate":
            trends = await self._get_error_rate_trends(
                start_date, end_date, provider_id, granularity
            )
        else:
            trends = []
        
        # Cache result
        import json
        await cache_service.set(cache_key, json.dumps(trends), ttl=self.CACHE_TTL)
        
        return trends
    
    async def _get_response_time_trends(
        self,
        start_date: datetime,
        end_date: datetime,
        provider_id: Optional[int],
        granularity: str
    ) -> List[Dict[str, Any]]:
        """Get response time trends"""
        
        if granularity == "hourly":
            query = self.db.query(
                POSAnalyticsSnapshot.snapshot_date,
                POSAnalyticsSnapshot.snapshot_hour,
                func.avg(POSAnalyticsSnapshot.response_time_p50).label("p50"),
                func.avg(POSAnalyticsSnapshot.response_time_p95).label("p95"),
                func.avg(POSAnalyticsSnapshot.response_time_p99).label("p99")
            )
        else:
            query = self.db.query(
                POSAnalyticsSnapshot.snapshot_date,
                func.avg(POSAnalyticsSnapshot.response_time_p50).label("p50"),
                func.avg(POSAnalyticsSnapshot.response_time_p95).label("p95"),
                func.avg(POSAnalyticsSnapshot.response_time_p99).label("p99")
            )
        
        query = query.filter(
            POSAnalyticsSnapshot.snapshot_date >= start_date.date(),
            POSAnalyticsSnapshot.snapshot_date <= end_date.date()
        )
        
        if provider_id:
            query = query.filter(POSAnalyticsSnapshot.provider_id == provider_id)
        
        if granularity == "hourly":
            query = query.group_by(
                POSAnalyticsSnapshot.snapshot_date,
                POSAnalyticsSnapshot.snapshot_hour
            ).order_by(
                POSAnalyticsSnapshot.snapshot_date,
                POSAnalyticsSnapshot.snapshot_hour
            )
        else:
            query = query.group_by(
                POSAnalyticsSnapshot.snapshot_date
            ).order_by(
                POSAnalyticsSnapshot.snapshot_date
            )
        
        results = query.all()
        
        trends = []
        for row in results:
            if granularity == "hourly":
                timestamp = datetime.combine(row.snapshot_date, datetime.min.time()) + timedelta(hours=row.snapshot_hour)
            else:
                timestamp = datetime.combine(row.snapshot_date, datetime.min.time())
            
            trends.append({
                "timestamp": timestamp.isoformat(),
                "p50": row.p50 or 0.0,
                "p95": row.p95 or 0.0,
                "p99": row.p99 or 0.0
            })
        
        return trends
    
    async def _get_success_rate_trends(
        self,
        start_date: datetime,
        end_date: datetime,
        provider_id: Optional[int],
        granularity: str
    ) -> List[Dict[str, Any]]:
        """Get success rate trends"""
        
        query = self.db.query(
            POSAnalyticsSnapshot.snapshot_date,
            func.sum(POSAnalyticsSnapshot.successful_transactions).label("successful"),
            func.sum(POSAnalyticsSnapshot.total_transactions).label("total"),
            func.sum(POSAnalyticsSnapshot.successful_syncs).label("sync_successful"),
            func.sum(POSAnalyticsSnapshot.total_syncs).label("sync_total"),
            func.sum(POSAnalyticsSnapshot.successful_webhooks).label("webhook_successful"),
            func.sum(POSAnalyticsSnapshot.total_webhooks).label("webhook_total")
        )
        
        query = query.filter(
            POSAnalyticsSnapshot.snapshot_date >= start_date.date(),
            POSAnalyticsSnapshot.snapshot_date <= end_date.date()
        )
        
        if provider_id:
            query = query.filter(POSAnalyticsSnapshot.provider_id == provider_id)
        
        query = query.group_by(
            POSAnalyticsSnapshot.snapshot_date
        ).order_by(
            POSAnalyticsSnapshot.snapshot_date
        )
        
        results = query.all()
        
        trends = []
        for row in results:
            timestamp = datetime.combine(row.snapshot_date, datetime.min.time())
            
            # Calculate rates
            tx_rate = (row.successful / row.total * 100) if row.total > 0 else 0.0
            sync_rate = (row.sync_successful / row.sync_total * 100) if row.sync_total > 0 else 0.0
            webhook_rate = (row.webhook_successful / row.webhook_total * 100) if row.webhook_total > 0 else 0.0
            
            trends.append({
                "timestamp": timestamp.isoformat(),
                "transaction_success_rate": tx_rate,
                "sync_success_rate": sync_rate,
                "webhook_success_rate": webhook_rate,
                "overall_success_rate": (tx_rate + sync_rate + webhook_rate) / 3
            })
        
        return trends
    
    async def _get_error_rate_trends(
        self,
        start_date: datetime,
        end_date: datetime,
        provider_id: Optional[int],
        granularity: str
    ) -> List[Dict[str, Any]]:
        """Get error rate trends"""
        
        query = self.db.query(
            POSAnalyticsSnapshot.snapshot_date,
            func.sum(POSAnalyticsSnapshot.total_errors).label("errors"),
            func.sum(POSAnalyticsSnapshot.total_transactions).label("transactions"),
            func.sum(POSAnalyticsSnapshot.failed_syncs).label("sync_errors"),
            func.sum(POSAnalyticsSnapshot.failed_webhooks).label("webhook_errors")
        )
        
        query = query.filter(
            POSAnalyticsSnapshot.snapshot_date >= start_date.date(),
            POSAnalyticsSnapshot.snapshot_date <= end_date.date()
        )
        
        if provider_id:
            query = query.filter(POSAnalyticsSnapshot.provider_id == provider_id)
        
        query = query.group_by(
            POSAnalyticsSnapshot.snapshot_date
        ).order_by(
            POSAnalyticsSnapshot.snapshot_date
        )
        
        results = query.all()
        
        trends = []
        for row in results:
            timestamp = datetime.combine(row.snapshot_date, datetime.min.time())
            
            total_operations = row.transactions or 1  # Avoid division by zero
            error_rate = (row.errors / total_operations * 100) if total_operations > 0 else 0.0
            
            trends.append({
                "timestamp": timestamp.isoformat(),
                "error_rate": error_rate,
                "total_errors": row.errors or 0,
                "sync_errors": row.sync_errors or 0,
                "webhook_errors": row.webhook_errors or 0
            })
        
        return trends