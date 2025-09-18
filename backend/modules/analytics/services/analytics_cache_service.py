"""
Advanced caching service for analytics operations.

Provides intelligent caching for:
- Dashboard queries
- Sales reports
- Real-time metrics
- AI insights
- POS analytics
"""

import logging
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta, date
from enum import Enum

from core.redis_cache import redis_cache, cached

logger = logging.getLogger(__name__)


class CacheGranularity(Enum):
    """Time granularity for cache keys."""
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class AnalyticsCacheService:
    """
    Advanced caching for analytics with time-based invalidation.
    """
    
    CACHE_NAMESPACE = "analytics"
    
    # Cache TTLs based on data freshness requirements
    TTL_REALTIME = 60  # 1 minute for real-time data
    TTL_RECENT = 300  # 5 minutes for recent data (last hour)
    TTL_TODAY = 900  # 15 minutes for today's data
    TTL_HISTORICAL_DAY = 3600  # 1 hour for historical daily data
    TTL_HISTORICAL_WEEK = 7200  # 2 hours for weekly data
    TTL_HISTORICAL_MONTH = 14400  # 4 hours for monthly data
    TTL_AI_INSIGHTS = 1800  # 30 minutes for AI-generated insights
    TTL_AGGREGATE = 600  # 10 minutes for aggregated metrics
    
    @classmethod
    def get_time_bucket(cls, dt: datetime, granularity: CacheGranularity) -> str:
        """Get time bucket for cache key based on granularity."""
        if granularity == CacheGranularity.MINUTE:
            return dt.strftime("%Y%m%d%H%M")
        elif granularity == CacheGranularity.HOUR:
            return dt.strftime("%Y%m%d%H")
        elif granularity == CacheGranularity.DAY:
            return dt.strftime("%Y%m%d")
        elif granularity == CacheGranularity.WEEK:
            # Get week number
            return dt.strftime("%Y%W")
        elif granularity == CacheGranularity.MONTH:
            return dt.strftime("%Y%m")
            
    @classmethod
    def get_ttl_for_date_range(
        cls,
        start_date: datetime,
        end_date: datetime
    ) -> int:
        """Determine appropriate TTL based on date range."""
        now = datetime.utcnow()
        
        # If end date is in the future, it's probably today/current
        if end_date > now:
            end_date = now
            
        # Calculate age of the most recent data
        data_age = now - end_date
        
        if data_age < timedelta(hours=1):
            return cls.TTL_RECENT
        elif data_age < timedelta(days=1):
            return cls.TTL_TODAY
        elif data_age < timedelta(days=7):
            return cls.TTL_HISTORICAL_DAY
        elif data_age < timedelta(days=30):
            return cls.TTL_HISTORICAL_WEEK
        else:
            return cls.TTL_HISTORICAL_MONTH
            
    @classmethod
    async def cache_dashboard_data(
        cls,
        data: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        filters: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[int] = None
    ) -> bool:
        """Cache dashboard data with smart TTL."""
        # Generate cache key
        key_parts = ["dashboard"]
        key_parts.append(start_date.strftime("%Y%m%d"))
        key_parts.append(end_date.strftime("%Y%m%d"))
        
        if tenant_id:
            key_parts.append(f"t{tenant_id}")
            
        if filters:
            # Sort filters for consistent keys
            filter_str = "_".join(f"{k}={v}" for k, v in sorted(filters.items()))
            key_parts.append(filter_str)
            
        key = ":".join(key_parts)
        
        # Determine TTL
        ttl = cls.get_ttl_for_date_range(start_date, end_date)
        
        # Add metadata
        data["_cached_at"] = datetime.utcnow().isoformat()
        data["_cache_ttl"] = ttl
        
        # Cache with appropriate tags
        tags = ["dashboard"]
        if tenant_id:
            tags.append(f"tenant:{tenant_id}")
            
        # Add time-based tags for easy invalidation
        if end_date.date() == datetime.utcnow().date():
            tags.append("today")
        elif end_date.date() >= (datetime.utcnow() - timedelta(days=7)).date():
            tags.append("recent")
            
        return await redis_cache.set(
            key,
            data,
            ttl=ttl,
            namespace=cls.CACHE_NAMESPACE,
            tags=tags
        )
        
    @classmethod
    async def get_dashboard_data(
        cls,
        start_date: datetime,
        end_date: datetime,
        filters: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get dashboard data from cache."""
        # Generate same key as cache_dashboard_data
        key_parts = ["dashboard"]
        key_parts.append(start_date.strftime("%Y%m%d"))
        key_parts.append(end_date.strftime("%Y%m%d"))
        
        if tenant_id:
            key_parts.append(f"t{tenant_id}")
            
        if filters:
            filter_str = "_".join(f"{k}={v}" for k, v in sorted(filters.items()))
            key_parts.append(filter_str)
            
        key = ":".join(key_parts)
        
        return await redis_cache.get(key, namespace=cls.CACHE_NAMESPACE)
        
    @classmethod
    async def cache_sales_metrics(
        cls,
        metrics: Dict[str, Any],
        date: date,
        granularity: CacheGranularity = CacheGranularity.DAY,
        location_id: Optional[int] = None,
        tenant_id: Optional[int] = None
    ) -> bool:
        """Cache sales metrics with time-based keys."""
        dt = datetime.combine(date, datetime.min.time())
        time_bucket = cls.get_time_bucket(dt, granularity)
        
        key_parts = ["sales", granularity.value, time_bucket]
        
        if location_id:
            key_parts.append(f"loc{location_id}")
        if tenant_id:
            key_parts.append(f"t{tenant_id}")
            
        key = ":".join(key_parts)
        
        # Determine TTL based on data age
        ttl = cls.get_ttl_for_date_range(dt, dt)
        
        tags = ["sales", f"gran:{granularity.value}"]
        if tenant_id:
            tags.append(f"tenant:{tenant_id}")
        if location_id:
            tags.append(f"location:{location_id}")
            
        return await redis_cache.set(
            key,
            metrics,
            ttl=ttl,
            namespace=cls.CACHE_NAMESPACE,
            tags=tags
        )
        
    @classmethod
    async def cache_ai_insights(
        cls,
        insights: Dict[str, Any],
        insight_type: str,
        context: Dict[str, Any],
        tenant_id: Optional[int] = None
    ) -> bool:
        """Cache AI-generated insights."""
        key_parts = ["ai_insights", insight_type]
        
        # Add context to key for uniqueness
        context_str = "_".join(f"{k}={v}" for k, v in sorted(context.items()))
        key_parts.append(context_str)
        
        if tenant_id:
            key_parts.append(f"t{tenant_id}")
            
        key = ":".join(key_parts)
        
        # Add metadata
        insights["_generated_at"] = datetime.utcnow().isoformat()
        insights["_context"] = context
        
        tags = ["ai_insights", f"type:{insight_type}"]
        if tenant_id:
            tags.append(f"tenant:{tenant_id}")
            
        return await redis_cache.set(
            key,
            insights,
            ttl=cls.TTL_AI_INSIGHTS,
            namespace=cls.CACHE_NAMESPACE,
            tags=tags
        )
        
    @classmethod
    async def cache_pos_analytics(
        cls,
        data: Dict[str, Any],
        provider_id: int,
        metric_type: str,
        time_range: Tuple[datetime, datetime],
        tenant_id: Optional[int] = None
    ) -> bool:
        """Cache POS analytics data."""
        start_date, end_date = time_range
        
        key_parts = [
            "pos",
            metric_type,
            f"p{provider_id}",
            start_date.strftime("%Y%m%d"),
            end_date.strftime("%Y%m%d")
        ]
        
        if tenant_id:
            key_parts.append(f"t{tenant_id}")
            
        key = ":".join(key_parts)
        
        ttl = cls.get_ttl_for_date_range(start_date, end_date)
        
        tags = ["pos", f"provider:{provider_id}", f"metric:{metric_type}"]
        if tenant_id:
            tags.append(f"tenant:{tenant_id}")
            
        return await redis_cache.set(
            key,
            data,
            ttl=ttl,
            namespace=cls.CACHE_NAMESPACE,
            tags=tags
        )
        
    @classmethod
    async def invalidate_realtime_data(cls, tenant_id: Optional[int] = None):
        """Invalidate all real-time data caches."""
        await redis_cache.invalidate_tag("realtime")
        if tenant_id:
            await redis_cache.invalidate_tag(f"realtime:tenant:{tenant_id}")
            
    @classmethod
    async def invalidate_today_data(cls, tenant_id: Optional[int] = None):
        """Invalidate today's cached data."""
        await redis_cache.invalidate_tag("today")
        if tenant_id:
            # Also invalidate tenant-specific today data
            pattern = f"*{datetime.utcnow().strftime('%Y%m%d')}*t{tenant_id}*"
            await redis_cache.delete_pattern(pattern, namespace=cls.CACHE_NAMESPACE)
            
    @classmethod
    async def invalidate_sales_data(
        cls,
        date_range: Optional[Tuple[date, date]] = None,
        location_id: Optional[int] = None,
        tenant_id: Optional[int] = None
    ):
        """Invalidate sales data caches."""
        if location_id:
            await redis_cache.invalidate_tag(f"location:{location_id}")
            
        if date_range:
            start_date, end_date = date_range
            # Invalidate date range
            pattern_parts = ["sales", "*"]
            
            # For specific date ranges, we need to be more targeted
            current = start_date
            while current <= end_date:
                for gran in CacheGranularity:
                    time_bucket = cls.get_time_bucket(
                        datetime.combine(current, datetime.min.time()),
                        gran
                    )
                    pattern = f"sales:{gran.value}:{time_bucket}*"
                    await redis_cache.delete_pattern(
                        pattern,
                        namespace=cls.CACHE_NAMESPACE
                    )
                current += timedelta(days=1)
        else:
            # Invalidate all sales data
            await redis_cache.invalidate_tag("sales")
            
    @classmethod
    async def warm_cache_for_date(
        cls,
        target_date: date,
        tenant_id: Optional[int] = None
    ):
        """Proactively warm cache for a specific date."""
        logger.info(f"Warming analytics cache for {target_date}")
        
        # This would typically call the actual services to populate cache
        # For now, it's a placeholder
        pass
        
    @classmethod
    async def get_cache_stats(cls) -> Dict[str, Any]:
        """Get analytics-specific cache statistics."""
        stats = await redis_cache.get_stats()
        
        # Add analytics-specific stats
        namespace_pattern = f"{cls.CACHE_NAMESPACE}:*"
        
        # Count different types of cached data
        # This is a simplified version - in production, you'd want more detail
        
        return {
            **stats,
            "analytics_namespace": cls.CACHE_NAMESPACE,
            "cache_patterns": {
                "dashboard": "dashboard:<start_date>:<end_date>",
                "sales": "sales:<granularity>:<time_bucket>",
                "ai_insights": "ai_insights:<type>:<context>",
                "pos": "pos:<metric>:<provider>:<dates>"
            }
        }


# Decorator for common analytics operations
@cached(
    namespace="analytics",
    ttl=300,
    tags=["sales_summary"]
)
async def get_cached_sales_summary(
    start_date: date,
    end_date: date,
    group_by: str = "day"
) -> Dict[str, Any]:
    """
    Placeholder for cached sales summary.
    The actual implementation would be in the service layer.
    """
    pass


@cached(
    key_func=lambda provider_id, hours=24: f"pos_health:{provider_id}:{hours}",
    namespace="analytics",
    ttl=300,
    tags=["pos_health"]
)
async def get_cached_pos_health(
    provider_id: int,
    hours: int = 24
) -> Dict[str, Any]:
    """
    Placeholder for cached POS health metrics.
    The actual implementation would be in the service layer.
    """
    pass


# Export the service
__all__ = ["AnalyticsCacheService", "CacheGranularity"]