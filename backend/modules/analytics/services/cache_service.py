# backend/modules/analytics/services/cache_service.py

"""
Caching service for analytics module.

Provides in-memory and Redis-based caching for frequently accessed data.
"""

import json
import logging
from typing import Optional, Any, Dict, List
from datetime import datetime, timedelta
import hashlib
import pickle
from functools import wraps

try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

from backend.modules.analytics.constants import (
    CACHE_TTL_SECONDS, REPORT_CACHE_TTL, MODEL_CACHE_TTL
)
from backend.modules.analytics.exceptions import CacheError

logger = logging.getLogger(__name__)


class CacheService:
    """Handles caching for analytics data and models"""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.redis_client = None
        
        if redis_url and HAS_REDIS:
            try:
                self.redis_client = redis.from_url(redis_url)
                self.redis_client.ping()
                logger.info("Redis cache connected successfully")
            except Exception as e:
                logger.warning(f"Redis connection failed, using memory cache: {e}")
                self.redis_client = None
    
    def _generate_key(self, prefix: str, params: Dict[str, Any]) -> str:
        """Generate cache key from parameters"""
        # Sort params for consistent keys
        sorted_params = json.dumps(params, sort_keys=True)
        param_hash = hashlib.md5(sorted_params.encode()).hexdigest()
        return f"{prefix}:{param_hash}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            # Try Redis first
            if self.redis_client:
                try:
                    value = self.redis_client.get(key)
                    if value:
                        return pickle.loads(value)
                except Exception as e:
                    logger.debug(f"Redis get failed for {key}: {e}")
            
            # Fall back to memory cache
            if key in self.memory_cache:
                entry = self.memory_cache[key]
                if datetime.now() < entry['expires_at']:
                    logger.debug(f"Cache hit (memory): {key}")
                    return entry['value']
                else:
                    # Expired, remove it
                    del self.memory_cache[key]
            
            logger.debug(f"Cache miss: {key}")
            return None
            
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            raise CacheError("get", str(e))
    
    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None
    ) -> None:
        """Set value in cache with TTL"""
        try:
            ttl = ttl_seconds or CACHE_TTL_SECONDS
            
            # Try Redis first
            if self.redis_client:
                try:
                    serialized = pickle.dumps(value)
                    self.redis_client.setex(key, ttl, serialized)
                    logger.debug(f"Cached in Redis: {key} (TTL: {ttl}s)")
                    return
                except Exception as e:
                    logger.debug(f"Redis set failed for {key}: {e}")
            
            # Fall back to memory cache
            self.memory_cache[key] = {
                'value': value,
                'expires_at': datetime.now() + timedelta(seconds=ttl)
            }
            logger.debug(f"Cached in memory: {key} (TTL: {ttl}s)")
            
            # Clean up old entries periodically
            if len(self.memory_cache) > 1000:
                self._cleanup_memory_cache()
                
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            raise CacheError("set", str(e))
    
    def delete(self, key: str) -> None:
        """Delete value from cache"""
        try:
            if self.redis_client:
                self.redis_client.delete(key)
            
            if key in self.memory_cache:
                del self.memory_cache[key]
                
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            raise CacheError("delete", str(e))
    
    def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        count = 0
        
        try:
            # Clear from Redis
            if self.redis_client:
                for key in self.redis_client.scan_iter(match=pattern):
                    self.redis_client.delete(key)
                    count += 1
            
            # Clear from memory cache
            keys_to_delete = [
                k for k in self.memory_cache.keys()
                if pattern.replace('*', '') in k
            ]
            for key in keys_to_delete:
                del self.memory_cache[key]
                count += 1
            
            logger.info(f"Cleared {count} cache entries matching {pattern}")
            return count
            
        except Exception as e:
            logger.error(f"Cache clear pattern error: {e}")
            raise CacheError("clear_pattern", str(e))
    
    def _cleanup_memory_cache(self) -> None:
        """Remove expired entries from memory cache"""
        now = datetime.now()
        expired_keys = [
            k for k, v in self.memory_cache.items()
            if v['expires_at'] < now
        ]
        
        for key in expired_keys:
            del self.memory_cache[key]
        
        logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    # Decorator for caching function results
    def cache_result(
        self,
        prefix: str,
        ttl_seconds: Optional[int] = None,
        key_params: Optional[List[str]] = None
    ):
        """Decorator to cache function results"""
        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Generate cache key
                cache_params = {}
                if key_params:
                    for param in key_params:
                        if param in kwargs:
                            cache_params[param] = kwargs[param]
                
                cache_key = self._generate_key(prefix, cache_params)
                
                # Check cache
                cached_value = self.get(cache_key)
                if cached_value is not None:
                    return cached_value
                
                # Call function
                result = await func(*args, **kwargs)
                
                # Cache result
                self.set(cache_key, result, ttl_seconds)
                
                return result
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                # Generate cache key
                cache_params = {}
                if key_params:
                    for param in key_params:
                        if param in kwargs:
                            cache_params[param] = kwargs[param]
                
                cache_key = self._generate_key(prefix, cache_params)
                
                # Check cache
                cached_value = self.get(cache_key)
                if cached_value is not None:
                    return cached_value
                
                # Call function
                result = func(*args, **kwargs)
                
                # Cache result
                self.set(cache_key, result, ttl_seconds)
                
                return result
            
            # Return appropriate wrapper based on function type
            import asyncio
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
                
        return decorator


# Specialized cache services
class HistoricalDataCache(CacheService):
    """Cache for historical demand and sales data"""
    
    def cache_historical_data(
        self,
        entity_type: str,
        entity_id: Optional[int],
        granularity: str,
        data: Any,
        ttl_seconds: Optional[int] = None
    ) -> None:
        """Cache historical data with structured key"""
        key = f"historical:{entity_type}:{entity_id or 'all'}:{granularity}"
        self.set(key, data, ttl_seconds or CACHE_TTL_SECONDS)
    
    def get_historical_data(
        self,
        entity_type: str,
        entity_id: Optional[int],
        granularity: str
    ) -> Optional[Any]:
        """Retrieve cached historical data"""
        key = f"historical:{entity_type}:{entity_id or 'all'}:{granularity}"
        return self.get(key)


class ModelCache(CacheService):
    """Cache for trained forecasting models"""
    
    def cache_model(
        self,
        entity_type: str,
        entity_id: Optional[int],
        model_type: str,
        model: Any,
        ttl_seconds: Optional[int] = None
    ) -> None:
        """Cache trained model"""
        key = f"model:{entity_type}:{entity_id or 'all'}:{model_type}"
        self.set(key, model, ttl_seconds or MODEL_CACHE_TTL)
    
    def get_model(
        self,
        entity_type: str,
        entity_id: Optional[int],
        model_type: str
    ) -> Optional[Any]:
        """Retrieve cached model"""
        key = f"model:{entity_type}:{entity_id or 'all'}:{model_type}"
        return self.get(key)
    
    def invalidate_models(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None
    ) -> int:
        """Invalidate cached models"""
        if entity_type and entity_id:
            pattern = f"model:{entity_type}:{entity_id}:*"
        elif entity_type:
            pattern = f"model:{entity_type}:*"
        else:
            pattern = "model:*"
        
        return self.clear_pattern(pattern)


# Global cache instances
_cache_service = None
_historical_cache = None
_model_cache = None


def get_cache_service() -> CacheService:
    """Get global cache service instance"""
    global _cache_service
    if _cache_service is None:
        # TODO: Get Redis URL from config
        _cache_service = CacheService()
    return _cache_service


def get_historical_cache() -> HistoricalDataCache:
    """Get historical data cache instance"""
    global _historical_cache
    if _historical_cache is None:
        _historical_cache = HistoricalDataCache()
    return _historical_cache


def get_model_cache() -> ModelCache:
    """Get model cache instance"""
    global _model_cache
    if _model_cache is None:
        _model_cache = ModelCache()
    return _model_cache