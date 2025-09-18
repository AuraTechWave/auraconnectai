"""
Local memory cache layer for multi-level caching.

Provides an in-memory LRU cache that sits in front of Redis
for frequently accessed data.
"""

import time
import asyncio
import logging
from typing import Any, Optional, Dict, Callable
from collections import OrderedDict
from functools import wraps
import sys

logger = logging.getLogger(__name__)


class LRUCache:
    """Thread-safe LRU (Least Recently Used) cache implementation."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 60):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self.lock = asyncio.Lock()
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "expirations": 0
        }
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        async with self.lock:
            if key not in self.cache:
                self.stats["misses"] += 1
                return None
            
            value, expiry_time = self.cache[key]
            
            # Check if expired
            if time.time() > expiry_time:
                del self.cache[key]
                self.stats["expirations"] += 1
                self.stats["misses"] += 1
                return None
            
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            self.stats["hits"] += 1
            return value
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache."""
        async with self.lock:
            ttl = ttl or self.ttl_seconds
            expiry_time = time.time() + ttl
            
            # Remove oldest items if at capacity
            while len(self.cache) >= self.max_size:
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                self.stats["evictions"] += 1
            
            self.cache[key] = (value, expiry_time)
            self.cache.move_to_end(key)
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        async with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self.lock:
            self.cache.clear()
    
    async def size(self) -> int:
        """Get current cache size."""
        async with self.lock:
            return len(self.cache)
    
    async def memory_usage(self) -> int:
        """Estimate memory usage in bytes."""
        async with self.lock:
            total_size = sys.getsizeof(self.cache)
            for key, (value, _) in self.cache.items():
                total_size += sys.getsizeof(key)
                total_size += sys.getsizeof(value)
            return total_size
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (
            (self.stats["hits"] / total_requests * 100)
            if total_requests > 0
            else 0
        )
        
        return {
            **self.stats,
            "size": len(self.cache),
            "max_size": self.max_size,
            "hit_rate": f"{hit_rate:.2f}%"
        }


class MemoryCacheLayer:
    """
    Local memory cache layer that sits in front of Redis.
    
    Provides fast access to frequently used data without
    network overhead.
    """
    
    def __init__(
        self,
        max_size_per_namespace: int = 1000,
        default_ttl: int = 60,
        enabled: bool = True
    ):
        self.enabled = enabled
        self.max_size_per_namespace = max_size_per_namespace
        self.default_ttl = default_ttl
        self.namespaces: Dict[str, LRUCache] = {}
        self.global_stats = {
            "l1_hits": 0,
            "l1_misses": 0,
            "l2_hits": 0,
            "l2_misses": 0
        }
    
    def get_or_create_namespace(self, namespace: str) -> LRUCache:
        """Get or create cache for namespace."""
        if namespace not in self.namespaces:
            self.namespaces[namespace] = LRUCache(
                max_size=self.max_size_per_namespace,
                ttl_seconds=self.default_ttl
            )
        return self.namespaces[namespace]
    
    async def get(
        self,
        key: str,
        namespace: str = "default"
    ) -> Optional[Any]:
        """Get from memory cache (L1)."""
        if not self.enabled:
            return None
        
        cache = self.get_or_create_namespace(namespace)
        value = await cache.get(key)
        
        if value is not None:
            self.global_stats["l1_hits"] += 1
        else:
            self.global_stats["l1_misses"] += 1
        
        return value
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: str = "default"
    ) -> None:
        """Set in memory cache."""
        if not self.enabled:
            return
        
        cache = self.get_or_create_namespace(namespace)
        await cache.set(key, value, ttl)
    
    async def delete(self, key: str, namespace: str = "default") -> bool:
        """Delete from memory cache."""
        if not self.enabled:
            return False
        
        cache = self.get_or_create_namespace(namespace)
        return await cache.delete(key)
    
    async def clear_namespace(self, namespace: str) -> None:
        """Clear all entries in a namespace."""
        if namespace in self.namespaces:
            await self.namespaces[namespace].clear()
    
    async def clear_all(self) -> None:
        """Clear all memory caches."""
        for cache in self.namespaces.values():
            await cache.clear()
    
    def record_l2_hit(self):
        """Record a hit in L2 (Redis) cache."""
        self.global_stats["l2_hits"] += 1
    
    def record_l2_miss(self):
        """Record a miss in L2 (Redis) cache."""
        self.global_stats["l2_misses"] += 1
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        namespace_stats = {}
        total_memory = 0
        total_size = 0
        
        for name, cache in self.namespaces.items():
            stats = cache.get_stats()
            memory = await cache.memory_usage()
            namespace_stats[name] = {
                **stats,
                "memory_bytes": memory
            }
            total_memory += memory
            total_size += stats["size"]
        
        # Calculate multi-level hit rates
        l1_total = self.global_stats["l1_hits"] + self.global_stats["l1_misses"]
        l1_hit_rate = (
            (self.global_stats["l1_hits"] / l1_total * 100)
            if l1_total > 0
            else 0
        )
        
        l2_total = self.global_stats["l2_hits"] + self.global_stats["l2_misses"]
        l2_hit_rate = (
            (self.global_stats["l2_hits"] / l2_total * 100)
            if l2_total > 0
            else 0
        )
        
        # Overall hit rate (considering both levels)
        total_requests = l1_total
        total_hits = self.global_stats["l1_hits"] + self.global_stats["l2_hits"]
        overall_hit_rate = (
            (total_hits / total_requests * 100)
            if total_requests > 0
            else 0
        )
        
        return {
            "enabled": self.enabled,
            "global_stats": {
                **self.global_stats,
                "l1_hit_rate": f"{l1_hit_rate:.2f}%",
                "l2_hit_rate": f"{l2_hit_rate:.2f}%",
                "overall_hit_rate": f"{overall_hit_rate:.2f}%"
            },
            "totals": {
                "namespaces": len(self.namespaces),
                "total_entries": total_size,
                "total_memory_bytes": total_memory,
                "total_memory_mb": round(total_memory / 1024 / 1024, 2)
            },
            "namespaces": namespace_stats
        }


# Global memory cache instance
memory_cache = MemoryCacheLayer()


def with_memory_cache(
    namespace: str = "default",
    ttl: Optional[int] = None
):
    """
    Decorator to add memory caching to a function.
    
    This should be used in conjunction with Redis caching
    for multi-level caching.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            key_parts = [func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)
            
            # Try memory cache first (L1)
            cached = await memory_cache.get(cache_key, namespace)
            if cached is not None:
                return cached
            
            # Call the function
            result = await func(*args, **kwargs)
            
            # Cache the result in memory
            await memory_cache.set(cache_key, result, ttl, namespace)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we can't use async memory cache
            # Just call the function directly
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Export public interface
__all__ = [
    "memory_cache",
    "with_memory_cache",
    "MemoryCacheLayer",
    "LRUCache"
]