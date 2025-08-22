# backend/modules/analytics/utils/cache_manager.py

"""
Advanced caching utilities for analytics queries.

Provides intelligent caching with TTL, invalidation strategies,
and cache warming capabilities.
"""

import json
import hashlib
import asyncio
from typing import Any, Optional, Callable, Dict, List, Union
from datetime import datetime, timedelta
from functools import wraps
import logging

from core.cache import cache_service

logger = logging.getLogger(__name__)


class AnalyticsCacheManager:
    """Manages caching for analytics queries with advanced features"""
    
    def __init__(self):
        self.cache_prefix = "analytics"
        self.default_ttl = 300  # 5 minutes
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "invalidations": 0,
            "errors": 0
        }
    
    def generate_cache_key(
        self,
        namespace: str,
        *args,
        **kwargs
    ) -> str:
        """Generate a unique cache key based on function arguments"""
        # Create a string representation of all arguments
        key_parts = [self.cache_prefix, namespace]
        
        # Add positional arguments
        for arg in args:
            if hasattr(arg, '__dict__'):
                # For objects, use their dict representation
                key_parts.append(str(sorted(arg.__dict__.items())))
            else:
                key_parts.append(str(arg))
        
        # Add keyword arguments
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        
        # Create hash of the key parts
        key_string = ":".join(key_parts)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()[:16]
        
        return f"{self.cache_prefix}:{namespace}:{key_hash}"
    
    async def get_or_compute(
        self,
        key: str,
        compute_func: Callable,
        ttl: Optional[int] = None,
        force_refresh: bool = False
    ) -> Any:
        """Get value from cache or compute it if not present"""
        if not force_refresh:
            # Try to get from cache
            cached_value = await cache_service.get(key)
            if cached_value is not None:
                self.cache_stats["hits"] += 1
                try:
                    return json.loads(cached_value)
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode cached value for key: {key}")
                    self.cache_stats["errors"] += 1
        
        # Cache miss or force refresh
        self.cache_stats["misses"] += 1
        
        # Compute the value
        try:
            if asyncio.iscoroutinefunction(compute_func):
                value = await compute_func()
            else:
                value = compute_func()
            
            # Cache the result
            cache_ttl = ttl or self.default_ttl
            await cache_service.set(key, json.dumps(value), ttl=cache_ttl)
            
            return value
        except Exception as e:
            logger.error(f"Error computing value for cache key {key}: {e}")
            self.cache_stats["errors"] += 1
            raise
    
    async def invalidate_pattern(self, pattern: str):
        """Invalidate all cache entries matching a pattern"""
        try:
            await cache_service.delete_pattern(f"{self.cache_prefix}:{pattern}*")
            self.cache_stats["invalidations"] += 1
        except Exception as e:
            logger.error(f"Error invalidating cache pattern {pattern}: {e}")
            self.cache_stats["errors"] += 1
    
    async def invalidate_namespace(self, namespace: str):
        """Invalidate all cache entries in a namespace"""
        await self.invalidate_pattern(namespace)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = (self.cache_stats["hits"] / total * 100) if total > 0 else 0
        
        return {
            **self.cache_stats,
            "total_requests": total,
            "hit_rate": f"{hit_rate:.2f}%"
        }


# Global cache manager instance
analytics_cache = AnalyticsCacheManager()


def cached_query(
    namespace: str,
    ttl: Optional[int] = None,
    key_params: Optional[List[str]] = None
):
    """
    Decorator for caching query results.
    
    Args:
        namespace: Cache namespace for the query
        ttl: Time to live in seconds
        key_params: List of parameter names to include in cache key
    
    Usage:
        @cached_query("sales_summary", ttl=600)
        async def get_sales_summary(self, filters):
            # Query implementation
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Extract key parameters
            cache_key_args = []
            
            # Add self parameter if it's a method
            if args and hasattr(args[0], '__class__'):
                # Skip self for cache key
                cache_key_args = list(args[1:])
            else:
                cache_key_args = list(args)
            
            # Filter kwargs based on key_params
            cache_key_kwargs = kwargs
            if key_params:
                cache_key_kwargs = {k: v for k, v in kwargs.items() if k in key_params}
            
            # Generate cache key
            cache_key = analytics_cache.generate_cache_key(
                namespace,
                *cache_key_args,
                **cache_key_kwargs
            )
            
            # Check if force_refresh is requested
            force_refresh = kwargs.get("force_refresh", False)
            
            # Get or compute the result
            return await analytics_cache.get_or_compute(
                cache_key,
                lambda: func(*args, **kwargs),
                ttl=ttl,
                force_refresh=force_refresh
            )
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            # For synchronous functions, run in event loop
            try:
                # Try to get the current event loop
                loop = asyncio.get_running_loop()
                # If we're already in an async context, we can't block
                # Instead, schedule the task and return a placeholder
                # This is a limitation of mixing sync/async code
                import warnings
                warnings.warn(
                    "Synchronous cache decorator called from async context. "
                    "Consider using the async version of the function.",
                    RuntimeWarning
                )
                # Schedule the task to run but don't wait for it
                asyncio.create_task(async_wrapper(*args, **kwargs))
                # Return the computed result directly without caching
                return func(*args, **kwargs)
            except RuntimeError:
                # No event loop running, safe to use asyncio.run()
                return asyncio.run(async_wrapper(*args, **kwargs))
        
        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class CacheWarmer:
    """Proactively warm cache for frequently accessed queries"""
    
    def __init__(self, db_session):
        self.db = db_session
        self.warming_tasks = []
    
    async def warm_dashboard_cache(self):
        """Warm cache for dashboard queries"""
        logger.info("Starting dashboard cache warming")
        
        # Import here to avoid circular imports
        from ..services.pos_dashboard_service import POSDashboardService
        
        service = POSDashboardService(self.db)
        
        # Common time ranges
        now = datetime.utcnow()
        today = now.date()
        
        time_ranges = [
            (today, today),  # Today
            (today - timedelta(days=7), today),  # Last 7 days
            (today - timedelta(days=30), today),  # Last 30 days
        ]
        
        for start_date, end_date in time_ranges:
            try:
                # Warm the cache by calling the method
                await service.get_dashboard_data(
                    datetime.combine(start_date, datetime.min.time()),
                    datetime.combine(end_date, datetime.max.time())
                )
                logger.info(f"Warmed dashboard cache for {start_date} to {end_date}")
            except Exception as e:
                logger.error(f"Error warming dashboard cache: {e}")
    
    async def warm_sales_report_cache(self):
        """Warm cache for sales report queries"""
        logger.info("Starting sales report cache warming")
        
        # Import here to avoid circular imports
        from ..services.sales_report_service import SalesReportService
        from ..schemas.analytics_schemas import SalesFilterRequest
        
        service = SalesReportService(self.db)
        
        # Common filters
        now = datetime.utcnow()
        today = now.date()
        
        filters = [
            SalesFilterRequest(date_from=today, date_to=today),
            SalesFilterRequest(
                date_from=today - timedelta(days=7),
                date_to=today
            ),
        ]
        
        for filter_req in filters:
            try:
                # Warm the cache
                service.generate_sales_summary(filter_req)
                logger.info(f"Warmed sales cache for {filter_req.date_from} to {filter_req.date_to}")
            except Exception as e:
                logger.error(f"Error warming sales cache: {e}")
    
    async def start_cache_warming(self, interval_minutes: int = 30):
        """Start periodic cache warming"""
        while True:
            try:
                await asyncio.gather(
                    self.warm_dashboard_cache(),
                    self.warm_sales_report_cache(),
                    return_exceptions=True
                )
            except Exception as e:
                logger.error(f"Error in cache warming: {e}")
            
            # Wait for next warming cycle
            await asyncio.sleep(interval_minutes * 60)


class CacheInvalidator:
    """Handle cache invalidation based on data changes"""
    
    @staticmethod
    async def invalidate_pos_analytics(provider_id: Optional[int] = None):
        """Invalidate POS analytics cache"""
        if provider_id:
            await analytics_cache.invalidate_pattern(f"pos_dashboard*provider*{provider_id}*")
        else:
            await analytics_cache.invalidate_namespace("pos_dashboard")
    
    @staticmethod
    async def invalidate_sales_analytics(date_range: Optional[tuple] = None):
        """Invalidate sales analytics cache"""
        if date_range:
            start_date, end_date = date_range
            await analytics_cache.invalidate_pattern(
                f"sales*{start_date.isoformat()}*{end_date.isoformat()}*"
            )
        else:
            await analytics_cache.invalidate_namespace("sales")
    
    @staticmethod
    async def invalidate_customer_analytics(customer_id: Optional[int] = None):
        """Invalidate customer analytics cache"""
        if customer_id:
            await analytics_cache.invalidate_pattern(f"customer*{customer_id}*")
        else:
            await analytics_cache.invalidate_namespace("customer")


# Export commonly used functions
__all__ = [
    "analytics_cache",
    "cached_query",
    "CacheWarmer",
    "CacheInvalidator"
]