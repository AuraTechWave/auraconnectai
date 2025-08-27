"""
Enhanced Redis-based cache service for production use.

Provides distributed caching with:
- Automatic serialization/deserialization
- TTL support with configurable defaults
- Cache namespacing and tagging
- Pattern-based invalidation
- Cache statistics and monitoring
- Circuit breaker for Redis failures
"""

import json
import pickle
import hashlib
import asyncio
import logging
from typing import Any, Optional, Dict, List, Union, Callable, Set
from datetime import datetime, timedelta
from functools import wraps
from contextlib import asynccontextmanager
import redis.asyncio as redis
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CircuitBreaker:
    """Circuit breaker pattern for Redis failures."""
    
    def __init__(
        self, 
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = RedisError
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
        
    def call_succeeded(self):
        """Reset failure count on successful call."""
        self.failure_count = 0
        self.state = "closed"
        
    def call_failed(self):
        """Increment failure count and potentially open circuit."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )
            
    def can_attempt_call(self) -> bool:
        """Check if we can attempt a call."""
        if self.state == "closed":
            return True
            
        if self.state == "open":
            # Check if we should try half-open
            if self.last_failure_time:
                time_since_failure = (
                    datetime.utcnow() - self.last_failure_time
                ).total_seconds()
                if time_since_failure > self.recovery_timeout:
                    self.state = "half-open"
                    return True
            return False
            
        # half-open state
        return True


class RedisCacheService:
    """
    Production-ready Redis cache service with advanced features.
    """
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        default_ttl: int = 300,
        key_prefix: str = "auraconnect",
        max_connections: int = 50,
        socket_timeout: int = 5,
        socket_connect_timeout: int = 5,
        decode_responses: bool = False,
    ):
        self.redis_url = redis_url or settings.redis_url or "redis://localhost:6379/0"
        self.default_ttl = default_ttl
        self.key_prefix = key_prefix
        self.redis_client = None
        self.circuit_breaker = CircuitBreaker()
        
        # Connection pool configuration
        self.pool_kwargs = {
            "max_connections": max_connections,
            "socket_timeout": socket_timeout,
            "socket_connect_timeout": socket_connect_timeout,
            "decode_responses": decode_responses,
            "retry_on_timeout": True,
            "retry_on_error": [RedisConnectionError],
        }
        
        # Cache statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "circuit_breaker_trips": 0,
        }
        
        # Tag tracking for invalidation
        self.tag_store = {}  # In production, this should be in Redis too
        
    async def initialize(self):
        """Initialize Redis connection pool."""
        try:
            self.redis_client = redis.Redis.from_url(
                self.redis_url,
                **self.pool_kwargs
            )
            # Test connection
            await self.redis_client.ping()
            logger.info(f"Redis cache connected to {self.redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            # Don't raise - allow graceful degradation
            
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            
    def _make_key(self, key: str, namespace: Optional[str] = None) -> str:
        """Generate a namespaced cache key."""
        parts = [self.key_prefix]
        if namespace:
            parts.append(namespace)
        parts.append(key)
        return ":".join(parts)
        
    def _serialize(self, value: Any) -> bytes:
        """Serialize value for storage."""
        try:
            # Try JSON first (for better debugging)
            return json.dumps(value).encode("utf-8")
        except (TypeError, ValueError):
            # Fall back to pickle for complex objects
            return pickle.dumps(value)
            
    def _deserialize(self, data: bytes) -> Any:
        """Deserialize value from storage."""
        try:
            # Try JSON first
            return json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Fall back to pickle
            return pickle.loads(data)
            
    async def get(
        self, 
        key: str, 
        namespace: Optional[str] = None,
        default: Any = None
    ) -> Any:
        """Get value from cache."""
        if not self.circuit_breaker.can_attempt_call():
            self.stats["circuit_breaker_trips"] += 1
            return default
            
        if not self.redis_client:
            return default
            
        full_key = self._make_key(key, namespace)
        
        try:
            data = await self.redis_client.get(full_key)
            
            if data is None:
                self.stats["misses"] += 1
                self.circuit_breaker.call_succeeded()
                return default
                
            self.stats["hits"] += 1
            self.circuit_breaker.call_succeeded()
            return self._deserialize(data)
            
        except Exception as e:
            self.stats["errors"] += 1
            self.circuit_breaker.call_failed()
            logger.error(f"Cache get error for {full_key}: {e}")
            return default
            
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> bool:
        """Set value in cache with optional tags."""
        if not self.circuit_breaker.can_attempt_call():
            self.stats["circuit_breaker_trips"] += 1
            return False
            
        if not self.redis_client:
            return False
            
        full_key = self._make_key(key, namespace)
        ttl = ttl or self.default_ttl
        
        try:
            serialized = self._serialize(value)
            await self.redis_client.setex(full_key, ttl, serialized)
            
            # Track tags for invalidation
            if tags:
                for tag in tags:
                    tag_key = f"{self.key_prefix}:tags:{tag}"
                    await self.redis_client.sadd(tag_key, full_key)
                    await self.redis_client.expire(tag_key, ttl)
                    
            self.circuit_breaker.call_succeeded()
            return True
            
        except Exception as e:
            self.stats["errors"] += 1
            self.circuit_breaker.call_failed()
            logger.error(f"Cache set error for {full_key}: {e}")
            return False
            
    async def delete(self, key: str, namespace: Optional[str] = None) -> bool:
        """Delete a key from cache."""
        if not self.redis_client:
            return False
            
        full_key = self._make_key(key, namespace)
        
        try:
            result = await self.redis_client.delete(full_key)
            return bool(result)
        except Exception as e:
            logger.error(f"Cache delete error for {full_key}: {e}")
            return False
            
    async def delete_pattern(
        self, 
        pattern: str, 
        namespace: Optional[str] = None
    ) -> int:
        """Delete all keys matching a pattern."""
        if not self.redis_client:
            return 0
            
        full_pattern = self._make_key(pattern, namespace)
        deleted_count = 0
        
        try:
            # Use SCAN for better performance
            cursor = 0
            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor, 
                    match=full_pattern, 
                    count=100
                )
                
                if keys:
                    deleted_count += await self.redis_client.delete(*keys)
                    
                if cursor == 0:
                    break
                    
            return deleted_count
            
        except Exception as e:
            logger.error(f"Cache delete pattern error for {full_pattern}: {e}")
            return 0
            
    async def invalidate_tag(self, tag: str) -> int:
        """Invalidate all keys with a specific tag."""
        if not self.redis_client:
            return 0
            
        tag_key = f"{self.key_prefix}:tags:{tag}"
        deleted_count = 0
        
        try:
            # Get all keys with this tag
            keys = await self.redis_client.smembers(tag_key)
            
            if keys:
                # Delete all tagged keys
                deleted_count = await self.redis_client.delete(*keys)
                
            # Delete the tag set itself
            await self.redis_client.delete(tag_key)
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Cache invalidate tag error for {tag}: {e}")
            return 0
            
    async def get_or_set(
        self,
        key: str,
        factory: Callable,
        ttl: Optional[int] = None,
        namespace: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Any:
        """Get from cache or compute and set if missing."""
        # Try to get from cache first
        cached = await self.get(key, namespace)
        if cached is not None:
            return cached
            
        # Compute value
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()
            
        # Cache the result
        await self.set(key, value, ttl, namespace, tags)
        
        return value
        
    async def clear_namespace(self, namespace: str) -> int:
        """Clear all keys in a namespace."""
        return await self.delete_pattern("*", namespace)
        
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (
            (self.stats["hits"] / total_requests * 100) 
            if total_requests > 0 
            else 0
        )
        
        info = {"client_stats": {**self.stats, "hit_rate": f"{hit_rate:.2f}%"}}
        
        # Add Redis server info if available
        if self.redis_client and self.circuit_breaker.can_attempt_call():
            try:
                redis_info = await self.redis_client.info()
                info["redis_info"] = {
                    "version": redis_info.get("redis_version"),
                    "connected_clients": redis_info.get("connected_clients"),
                    "used_memory_human": redis_info.get("used_memory_human"),
                    "uptime_in_days": redis_info.get("uptime_in_days"),
                }
            except Exception:
                pass
                
        return info
        
    @asynccontextmanager
    async def lock(
        self, 
        name: str, 
        timeout: int = 10,
        blocking_timeout: Optional[float] = None
    ):
        """Distributed lock using Redis."""
        if not self.redis_client:
            # No Redis, just yield without locking
            yield
            return
            
        lock_key = f"{self.key_prefix}:locks:{name}"
        lock = self.redis_client.lock(
            lock_key,
            timeout=timeout,
            blocking_timeout=blocking_timeout
        )
        
        try:
            acquired = await lock.acquire()
            if not acquired:
                raise TimeoutError(f"Could not acquire lock: {name}")
            yield
        finally:
            try:
                await lock.release()
            except Exception:
                # Lock may have expired
                pass


# Global cache instance
redis_cache = RedisCacheService()


def cached(
    key_func: Optional[Callable] = None,
    ttl: Optional[int] = None,
    namespace: Optional[str] = None,
    tags: Optional[List[str]] = None,
):
    """
    Decorator for caching function results.
    
    Args:
        key_func: Function to generate cache key from arguments
        ttl: Time to live in seconds
        namespace: Cache namespace
        tags: Tags for cache invalidation
        
    Example:
        @cached(namespace="recipes", ttl=3600, tags=["menu"])
        async def get_recipe_cost(recipe_id: int):
            # Expensive calculation
            return cost
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = ":".join(key_parts)
                
            # Check for cache bypass
            if kwargs.get("bypass_cache", False):
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
                    
            # Use get_or_set for atomic operation
            return await redis_cache.get_or_set(
                cache_key,
                lambda: func(*args, **kwargs),
                ttl=ttl,
                namespace=namespace,
                tags=tags
            )
            
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, create an event loop
            try:
                loop = asyncio.get_running_loop()
                # Already in async context, just call the function
                return func(*args, **kwargs)
            except RuntimeError:
                # No event loop, create one
                return asyncio.run(async_wrapper(*args, **kwargs))
                
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator


# Export public interface
__all__ = ["redis_cache", "cached", "RedisCacheService"]