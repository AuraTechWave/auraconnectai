# backend/core/cache_service.py

import json
import hashlib
import logging
from typing import Any, Optional, Callable, Union
from datetime import datetime, timedelta
from functools import wraps
import redis
from redis.exceptions import RedisError
from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CacheService:
    """Service for caching query results and other data"""
    
    def __init__(self):
        self.redis_client = None
        self.connect()
    
    def connect(self):
        """Connect to Redis server"""
        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD if hasattr(settings, 'REDIS_PASSWORD') else None,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            logger.info("Connected to Redis cache")
        except (RedisError, Exception) as e:
            logger.warning(f"Redis connection failed: {e}. Caching disabled.")
            self.redis_client = None
    
    def is_available(self) -> bool:
        """Check if cache service is available"""
        if not self.redis_client:
            return False
        try:
            self.redis_client.ping()
            return True
        except:
            return False
    
    def generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate a cache key from prefix and parameters"""
        # Create a unique key from arguments
        key_data = {
            'args': args,
            'kwargs': kwargs
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_str.encode()).hexdigest()
        return f"{prefix}:{key_hash}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.is_available():
            return None
        
        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.debug(f"Cache get error for key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with TTL (default 5 minutes)"""
        if not self.is_available():
            return False
        
        try:
            serialized = json.dumps(value, default=str)
            self.redis_client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.debug(f"Cache set error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.is_available():
            return False
        
        try:
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.debug(f"Cache delete error for key {key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        if not self.is_available():
            return 0
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.debug(f"Cache delete pattern error for {pattern}: {e}")
            return 0
    
    def invalidate_customer_cache(self, customer_id: int):
        """Invalidate all cache entries for a customer"""
        patterns = [
            f"customer:{customer_id}:*",
            f"customers:search:*",  # Invalidate search results
            f"customer_orders:{customer_id}:*"
        ]
        for pattern in patterns:
            self.delete_pattern(pattern)
    
    def invalidate_order_cache(self, order_id: int, customer_id: Optional[int] = None):
        """Invalidate cache entries for an order"""
        patterns = [
            f"order:{order_id}:*",
            f"orders:list:*",  # Invalidate list results
        ]
        if customer_id:
            patterns.append(f"customer_orders:{customer_id}:*")
        
        for pattern in patterns:
            self.delete_pattern(pattern)
    
    def invalidate_menu_cache(self):
        """Invalidate all menu-related cache"""
        patterns = [
            "menu:*",
            "menu_items:*",
            "menu_categories:*"
        ]
        for pattern in patterns:
            self.delete_pattern(pattern)


# Singleton instance
cache_service = CacheService()


def cached(prefix: str, ttl: int = 300):
    """
    Decorator for caching function results
    
    Args:
        prefix: Cache key prefix
        ttl: Time to live in seconds (default 5 minutes)
    
    Example:
        @cached("customer_orders", ttl=600)
        def get_customer_orders(customer_id: int):
            return fetch_orders_from_db(customer_id)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Skip caching if explicitly requested
            if kwargs.pop('skip_cache', False):
                return func(*args, **kwargs)
            
            # Generate cache key
            cache_key = cache_service.generate_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached_value = cache_service.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {cache_key}")
                return cached_value
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_service.set(cache_key, result, ttl)
            logger.debug(f"Cache miss for {cache_key}, cached for {ttl}s")
            
            return result
        
        # Add method to invalidate cache for this function
        def invalidate(*args, **kwargs):
            cache_key = cache_service.generate_key(prefix, *args, **kwargs)
            cache_service.delete(cache_key)
        
        wrapper.invalidate_cache = invalidate
        return wrapper
    
    return decorator


def invalidate_on_change(*cache_prefixes: str):
    """
    Decorator to invalidate cache when a mutation occurs
    
    Args:
        cache_prefixes: Cache key prefixes to invalidate
    
    Example:
        @invalidate_on_change("customer:*", "customers:search:*")
        def update_customer(customer_id: int, data: dict):
            # Update customer in database
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # Invalidate specified cache patterns
            for prefix in cache_prefixes:
                cache_service.delete_pattern(prefix)
            
            return result
        
        return wrapper
    
    return decorator