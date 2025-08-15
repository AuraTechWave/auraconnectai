"""
Redis Caching Package

Provides caching functionality for the AuraConnect AI platform.
"""

from .redis_client import RedisClient, RedisCache, get_cache
from .cache_manager import CacheManager, CacheTTL, cache_manager
from .decorators import (
    cache,
    cache_menu,
    cache_permissions,
    cache_settings,
    cache_analytics,
    cache_api_response,
    cache_search_results,
    cache_report,
    invalidate_cache,
    trigger_cache_invalidation
)
from .cache_warmer import CacheWarmer, warm_cache_async, schedule_cache_warming
from .monitoring import CacheMonitor, CacheMetric, cache_monitor

__all__ = [
    # Redis Client
    'RedisClient',
    'RedisCache',
    'get_cache',
    
    # Cache Manager
    'CacheManager',
    'CacheTTL',
    'cache_manager',
    
    # Decorators
    'cache',
    'cache_menu',
    'cache_permissions',
    'cache_settings',
    'cache_analytics',
    'cache_api_response',
    'cache_search_results',
    'cache_report',
    'invalidate_cache',
    'trigger_cache_invalidation',
    
    # Cache Warmer
    'CacheWarmer',
    'warm_cache_async',
    'schedule_cache_warming',
    
    # Monitoring
    'CacheMonitor',
    'CacheMetric',
    'cache_monitor',
]