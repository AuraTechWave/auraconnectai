"""
Enhanced Redis cache service with compression and multi-level caching.

Integrates compression, memory caching, and pattern analysis
for improved performance.
"""

import json
import time
import logging
from typing import Any, Optional, Dict, List, Union, Callable
from functools import wraps

from .redis_cache import RedisCacheService, redis_cache as base_redis_cache
from .memory_cache import memory_cache
from .cache_compression import CacheCompressor, CompressedCacheValue, CompressionAlgorithm
from .cache_preloader import pattern_analyzer

logger = logging.getLogger(__name__)


class EnhancedRedisCacheService(RedisCacheService):
    """
    Enhanced Redis cache with compression and multi-level caching.
    
    Features:
    - Automatic compression for large values
    - Local memory cache layer (L1)
    - Usage pattern tracking
    - Improved performance metrics
    """
    
    def __init__(
        self,
        *args,
        enable_compression: bool = True,
        compression_threshold: int = 1024,
        enable_memory_cache: bool = True,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.enable_compression = enable_compression
        self.compression_threshold = compression_threshold
        self.enable_memory_cache = enable_memory_cache
        
        # Enhanced stats
        self.compression_stats = {
            "compressed_count": 0,
            "uncompressed_count": 0,
            "bytes_saved": 0
        }
    
    async def get(
        self,
        key: str,
        namespace: Optional[str] = None,
        default: Any = None
    ) -> Any:
        """Enhanced get with multi-level caching."""
        start_time = time.time()
        full_key = self._make_key(key, namespace)
        
        # Level 1: Memory cache
        if self.enable_memory_cache:
            cached = await memory_cache.get(key, namespace or "default")
            if cached is not None:
                latency = (time.time() - start_time) * 1000
                pattern_analyzer.record_access(
                    key, namespace or "default", True, latency
                )
                return cached
        
        # Level 2: Redis cache
        value = await super().get(key, namespace, default)
        
        if value != default:
            # Check if it's a compressed value
            if isinstance(value, dict) and value.get("_compressed"):
                compressed_value = CompressedCacheValue.from_dict(value)
                if compressed_value:
                    value = json.loads(compressed_value.decompress().decode())
                    self.compression_stats["bytes_saved"] += compressed_value.compression_stats["space_saved"]
            
            # Store in memory cache for next time
            if self.enable_memory_cache and value != default:
                await memory_cache.set(key, value, namespace=namespace or "default")
                memory_cache.record_l2_hit()
            elif self.enable_memory_cache:
                memory_cache.record_l2_miss()
        
        # Record access pattern
        latency = (time.time() - start_time) * 1000
        pattern_analyzer.record_access(
            key, namespace or "default", value != default, latency
        )
        
        return value
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: Optional[str] = None,
        tags: Optional[List[str]] = None,
        compress: Optional[bool] = None
    ) -> bool:
        """Enhanced set with compression and multi-level caching."""
        # Determine if we should compress
        should_compress = compress if compress is not None else self.enable_compression
        
        if should_compress:
            # Serialize value first
            serialized = json.dumps(value).encode()
            
            if len(serialized) >= self.compression_threshold:
                # Compress the data
                compressed_data, algorithm = CacheCompressor.compress(
                    serialized,
                    CompressionAlgorithm.GZIP
                )
                
                if algorithm != CompressionAlgorithm.NONE.value:
                    # Create compressed value wrapper
                    compressed_value = CompressedCacheValue(
                        data=compressed_data,
                        algorithm=algorithm,
                        original_size=len(serialized),
                        compressed_size=len(compressed_data)
                    )
                    
                    # Store compressed value
                    value = compressed_value.to_dict()
                    self.compression_stats["compressed_count"] += 1
                else:
                    self.compression_stats["uncompressed_count"] += 1
            else:
                self.compression_stats["uncompressed_count"] += 1
        
        # Store in Redis
        success = await super().set(key, value, ttl, namespace, tags)
        
        # Also store in memory cache
        if success and self.enable_memory_cache:
            # Store the uncompressed value in memory cache
            original_value = value
            if isinstance(value, dict) and value.get("_compressed"):
                # Don't store compressed version in memory cache
                # We'll decompress on get
                pass
            else:
                await memory_cache.set(
                    key,
                    original_value,
                    ttl,
                    namespace or "default"
                )
        
        return success
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get enhanced statistics including compression and memory cache."""
        base_stats = await super().get_stats()
        
        # Add compression stats
        total_compressed = self.compression_stats["compressed_count"]
        total_uncompressed = self.compression_stats["uncompressed_count"]
        compression_ratio = (
            (total_compressed / (total_compressed + total_uncompressed) * 100)
            if (total_compressed + total_uncompressed) > 0
            else 0
        )
        
        # Add memory cache stats
        memory_stats = await memory_cache.get_stats() if self.enable_memory_cache else {}
        
        return {
            **base_stats,
            "compression": {
                **self.compression_stats,
                "compression_ratio": f"{compression_ratio:.2f}%",
                "mb_saved": round(self.compression_stats["bytes_saved"] / 1024 / 1024, 2)
            },
            "memory_cache": memory_stats
        }
    
    async def invalidate_pattern(self, pattern: str, namespace: Optional[str] = None):
        """Invalidate pattern in both Redis and memory cache."""
        # Invalidate in Redis
        await super().invalidate_pattern(pattern)
        
        # Also clear from memory cache
        if self.enable_memory_cache and namespace:
            await memory_cache.clear_namespace(namespace)
    
    async def clear_namespace(self, namespace: str) -> int:
        """Clear namespace in both caches."""
        # Clear Redis
        count = await super().clear_namespace(namespace)
        
        # Clear memory cache
        if self.enable_memory_cache:
            await memory_cache.clear_namespace(namespace)
        
        return count


# Create enhanced global instance
enhanced_cache = EnhancedRedisCacheService(
    enable_compression=True,
    compression_threshold=1024,  # 1KB
    enable_memory_cache=True
)


def cached_with_compression(
    key_func: Optional[Callable] = None,
    ttl: Optional[int] = None,
    namespace: Optional[str] = None,
    tags: Optional[List[str]] = None,
    compress: bool = True,
    memory_cache_ttl: Optional[int] = None
):
    """
    Enhanced decorator with compression and multi-level caching.
    
    Example:
        @cached_with_compression(
            namespace="analytics",
            ttl=3600,
            compress=True,
            memory_cache_ttl=60
        )
        async def get_large_report(report_id: int):
            # Generate large report
            return large_data
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = ":".join(key_parts)
            
            # Check cache bypass
            if kwargs.get("bypass_cache", False):
                return await func(*args, **kwargs)
            
            # Try to get from cache
            cached_value = await enhanced_cache.get(cache_key, namespace)
            if cached_value is not None:
                return cached_value
            
            # Compute value
            result = await func(*args, **kwargs)
            
            # Cache with compression
            await enhanced_cache.set(
                cache_key,
                result,
                ttl=ttl,
                namespace=namespace,
                tags=tags,
                compress=compress
            )
            
            return result
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            # For sync functions, return original
            return func
    
    return decorator


# Convenience functions for common operations
async def cache_large_object(
    key: str,
    value: Any,
    namespace: str = "large_objects",
    ttl: int = 3600
) -> bool:
    """Cache a large object with automatic compression."""
    return await enhanced_cache.set(
        key,
        value,
        ttl=ttl,
        namespace=namespace,
        compress=True
    )


async def get_large_object(
    key: str,
    namespace: str = "large_objects"
) -> Any:
    """Get a large object with automatic decompression."""
    return await enhanced_cache.get(key, namespace)


async def get_cache_performance_report() -> Dict[str, Any]:
    """Get comprehensive cache performance report."""
    stats = await enhanced_cache.get_stats()
    preload_stats = await cache_preloader.get_preload_stats()
    
    return {
        "cache_stats": stats,
        "preload_stats": preload_stats,
        "recommendations": {
            "compression": "Enable for objects > 1KB" if stats["compression"]["compression_ratio"] else "Already optimized",
            "memory_cache": "Increase size" if stats.get("memory_cache", {}).get("global_stats", {}).get("l1_hit_rate", "0%").replace("%", "") > "80" else "Current size is adequate",
            "preloading": f"{len(preload_stats.get('high_priority_keys', []))} keys recommended for preloading"
        }
    }


# Export enhanced interface
__all__ = [
    "enhanced_cache",
    "cached_with_compression",
    "cache_large_object",
    "get_large_object",
    "get_cache_performance_report",
    "EnhancedRedisCacheService"
]