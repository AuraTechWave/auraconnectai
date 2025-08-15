"""
Cache Manager

Manages different cache strategies and TTLs for various data types.
"""

from enum import Enum
from typing import Optional, Any, Dict, List, Callable
from datetime import datetime, timedelta
import hashlib
import json
import logging
from dataclasses import dataclass

from .redis_client import get_cache, RedisCache

logger = logging.getLogger(__name__)


class CacheTTL(Enum):
    """Standard cache TTL values in seconds"""
    MENU_ITEMS = 3600  # 1 hour
    USER_PERMISSIONS = 300  # 5 minutes
    RESTAURANT_SETTINGS = 600  # 10 minutes
    ANALYTICS_AGGREGATIONS = 300  # 5 minutes
    
    # Additional cache TTLs
    USER_SESSION = 1800  # 30 minutes
    API_RESPONSE = 60  # 1 minute
    SEARCH_RESULTS = 180  # 3 minutes
    REPORT_DATA = 900  # 15 minutes
    STATIC_CONTENT = 86400  # 24 hours
    TEMPORARY = 30  # 30 seconds
    
    # No expiration (use with caution)
    PERMANENT = None


@dataclass
class CacheStats:
    """Cache statistics"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    errors: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'hits': self.hits,
            'misses': self.misses,
            'sets': self.sets,
            'deletes': self.deletes,
            'errors': self.errors,
            'hit_rate': f"{self.hit_rate:.2f}%"
        }


class CacheManager:
    """
    Central cache management with monitoring and invalidation
    """
    
    def __init__(self):
        """Initialize cache manager"""
        self.caches: Dict[str, RedisCache] = {}
        self.stats: Dict[str, CacheStats] = {}
        self._initialize_caches()
    
    def _initialize_caches(self):
        """Initialize cache namespaces"""
        namespaces = [
            'menu',
            'permissions',
            'settings',
            'analytics',
            'sessions',
            'api',
            'search',
            'reports',
            'static'
        ]
        
        for namespace in namespaces:
            self.caches[namespace] = get_cache(namespace)
            self.stats[namespace] = CacheStats()
    
    def _get_cache_and_ttl(self, cache_type: str) -> tuple[RedisCache, Optional[int]]:
        """Get cache instance and TTL for cache type"""
        cache_map = {
            'menu': ('menu', CacheTTL.MENU_ITEMS.value),
            'menu_items': ('menu', CacheTTL.MENU_ITEMS.value),
            'menu_categories': ('menu', CacheTTL.MENU_ITEMS.value),
            'permissions': ('permissions', CacheTTL.USER_PERMISSIONS.value),
            'user_permissions': ('permissions', CacheTTL.USER_PERMISSIONS.value),
            'settings': ('settings', CacheTTL.RESTAURANT_SETTINGS.value),
            'restaurant_settings': ('settings', CacheTTL.RESTAURANT_SETTINGS.value),
            'analytics': ('analytics', CacheTTL.ANALYTICS_AGGREGATIONS.value),
            'analytics_aggregations': ('analytics', CacheTTL.ANALYTICS_AGGREGATIONS.value),
            'session': ('sessions', CacheTTL.USER_SESSION.value),
            'api': ('api', CacheTTL.API_RESPONSE.value),
            'search': ('search', CacheTTL.SEARCH_RESULTS.value),
            'report': ('reports', CacheTTL.REPORT_DATA.value),
            'static': ('static', CacheTTL.STATIC_CONTENT.value),
        }
        
        namespace, ttl = cache_map.get(cache_type, ('api', CacheTTL.API_RESPONSE.value))
        cache = self.caches.get(namespace, self.caches['api'])
        
        return cache, ttl
    
    def generate_key(
        self,
        cache_type: str,
        *args,
        tenant_id: Optional[int] = None,
        user_id: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        Generate cache key with tenant and user isolation
        
        Args:
            cache_type: Type of cache (menu, permissions, etc.)
            *args: Positional arguments for key
            tenant_id: Tenant ID for multi-tenancy
            user_id: User ID for user-specific caching
            **kwargs: Additional key parameters
            
        Returns:
            Generated cache key
        """
        key_parts = [cache_type]
        
        # Add tenant isolation
        if tenant_id is not None:
            key_parts.append(f"t{tenant_id}")
        
        # Add user isolation
        if user_id is not None:
            key_parts.append(f"u{user_id}")
        
        # Add positional arguments
        for arg in args:
            if arg is not None:
                key_parts.append(str(arg))
        
        # Add keyword arguments (sorted for consistency)
        for k, v in sorted(kwargs.items()):
            if v is not None:
                key_parts.append(f"{k}:{v}")
        
        return ":".join(key_parts)
    
    def get(
        self,
        cache_type: str,
        key: str,
        fetch_func: Optional[Callable] = None,
        ttl: Optional[int] = None,
        force_refresh: bool = False
    ) -> Optional[Any]:
        """
        Get value from cache with optional fetch function
        
        Args:
            cache_type: Type of cache
            key: Cache key
            fetch_func: Function to fetch data if not in cache
            ttl: Override default TTL
            force_refresh: Force refresh from source
            
        Returns:
            Cached or fetched value
        """
        cache, default_ttl = self._get_cache_and_ttl(cache_type)
        namespace = cache.prefix.split(':')[-1]
        
        # Force refresh if requested
        if force_refresh and fetch_func:
            value = fetch_func()
            if value is not None:
                cache.set(key, value, ttl or default_ttl)
                self.stats[namespace].sets += 1
            return value
        
        # Try to get from cache
        value = cache.get(key)
        
        if value is not None:
            self.stats[namespace].hits += 1
            logger.debug(f"Cache HIT: {cache_type}/{key}")
            return value
        
        self.stats[namespace].misses += 1
        logger.debug(f"Cache MISS: {cache_type}/{key}")
        
        # Fetch if function provided
        if fetch_func:
            try:
                value = fetch_func()
                if value is not None:
                    cache.set(key, value, ttl or default_ttl)
                    self.stats[namespace].sets += 1
                    logger.debug(f"Cache SET: {cache_type}/{key}")
                return value
            except Exception as e:
                self.stats[namespace].errors += 1
                logger.error(f"Error fetching data for cache {cache_type}/{key}: {e}")
                return None
        
        return None
    
    def set(
        self,
        cache_type: str,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in cache"""
        cache, default_ttl = self._get_cache_and_ttl(cache_type)
        namespace = cache.prefix.split(':')[-1]
        
        result = cache.set(key, value, ttl or default_ttl)
        if result:
            self.stats[namespace].sets += 1
            logger.debug(f"Cache SET: {cache_type}/{key}")
        else:
            self.stats[namespace].errors += 1
        
        return result
    
    def delete(self, cache_type: str, key: str) -> bool:
        """Delete value from cache"""
        cache, _ = self._get_cache_and_ttl(cache_type)
        namespace = cache.prefix.split(':')[-1]
        
        result = cache.delete(key)
        if result:
            self.stats[namespace].deletes += 1
            logger.debug(f"Cache DELETE: {cache_type}/{key}")
        
        return result
    
    def invalidate_pattern(self, cache_type: str, pattern: str) -> int:
        """Invalidate all keys matching pattern"""
        cache, _ = self._get_cache_and_ttl(cache_type)
        namespace = cache.prefix.split(':')[-1]
        
        count = cache.delete_pattern(pattern)
        self.stats[namespace].deletes += count
        logger.info(f"Cache INVALIDATE: {cache_type}/{pattern} ({count} keys)")
        
        return count
    
    def invalidate_menu(self, tenant_id: int, menu_item_id: Optional[int] = None):
        """Invalidate menu cache"""
        if menu_item_id:
            # Invalidate specific menu item
            pattern = f"menu:t{tenant_id}:item:{menu_item_id}*"
        else:
            # Invalidate all menu items for tenant
            pattern = f"menu:t{tenant_id}*"
        
        return self.invalidate_pattern('menu', pattern)
    
    def invalidate_permissions(self, user_id: int):
        """Invalidate user permissions cache"""
        pattern = f"permissions:u{user_id}*"
        return self.invalidate_pattern('permissions', pattern)
    
    def invalidate_settings(self, tenant_id: int):
        """Invalidate restaurant settings cache"""
        pattern = f"settings:t{tenant_id}*"
        return self.invalidate_pattern('settings', pattern)
    
    def invalidate_analytics(self, tenant_id: int, date: Optional[datetime] = None):
        """Invalidate analytics cache"""
        if date:
            # Invalidate specific date
            date_str = date.strftime('%Y-%m-%d')
            pattern = f"analytics:t{tenant_id}:{date_str}*"
        else:
            # Invalidate all analytics for tenant
            pattern = f"analytics:t{tenant_id}*"
        
        return self.invalidate_pattern('analytics', pattern)
    
    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Get cache statistics"""
        if namespace:
            return self.stats.get(namespace, CacheStats()).to_dict()
        
        # Aggregate all stats
        total = CacheStats()
        for stats in self.stats.values():
            total.hits += stats.hits
            total.misses += stats.misses
            total.sets += stats.sets
            total.deletes += stats.deletes
            total.errors += stats.errors
        
        return {
            'total': total.to_dict(),
            'namespaces': {
                name: stats.to_dict()
                for name, stats in self.stats.items()
            }
        }
    
    def reset_stats(self, namespace: Optional[str] = None):
        """Reset cache statistics"""
        if namespace:
            if namespace in self.stats:
                self.stats[namespace] = CacheStats()
        else:
            for namespace in self.stats:
                self.stats[namespace] = CacheStats()
    
    def health_check(self) -> Dict[str, Any]:
        """Check cache health"""
        health = {
            'status': 'healthy',
            'connected': False,
            'namespaces': [],
            'stats': self.get_stats()
        }
        
        try:
            # Check Redis connection
            cache = self.caches.get('api')
            if cache and cache.ping():
                health['connected'] = True
                health['namespaces'] = list(self.caches.keys())
                
                # Get Redis info
                info = cache.info()
                health['redis_info'] = {
                    'version': info.get('redis_version'),
                    'used_memory': info.get('used_memory_human'),
                    'connected_clients': info.get('connected_clients'),
                    'uptime_days': info.get('uptime_in_days')
                }
            else:
                health['status'] = 'unhealthy'
                health['error'] = 'Redis connection failed'
        except Exception as e:
            health['status'] = 'unhealthy'
            health['error'] = str(e)
        
        return health


# Global cache manager instance
cache_manager = CacheManager()