"""
Redis Client with Connection Pool

Manages Redis connections and provides low-level cache operations.
"""

import redis
from redis import ConnectionPool, Redis
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
from typing import Optional, Any, Dict, List, Union
import json
import pickle
import logging
from datetime import timedelta
from functools import lru_cache

from core.config import get_settings

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Redis client with connection pooling and error handling
    """
    
    _pool: Optional[ConnectionPool] = None
    _client: Optional[Redis] = None
    
    @classmethod
    def get_pool(cls) -> ConnectionPool:
        """Get or create Redis connection pool"""
        if cls._pool is None:
            settings = get_settings()
            
            pool_kwargs = {
                'host': settings.REDIS_HOST,
                'port': settings.REDIS_PORT,
                'db': settings.REDIS_DB,
                'password': settings.REDIS_PASSWORD,
                'decode_responses': False,  # We'll handle encoding/decoding
                'max_connections': 50,
                'socket_connect_timeout': 5,
                'socket_timeout': 5,
                'retry_on_timeout': True,
                'health_check_interval': 30,
            }
            
            # Use URL if provided, otherwise use individual settings
            if settings.redis_url:
                cls._pool = redis.ConnectionPool.from_url(
                    settings.redis_url,
                    **{k: v for k, v in pool_kwargs.items() if k not in ['host', 'port', 'db', 'password']}
                )
            else:
                cls._pool = redis.ConnectionPool(**pool_kwargs)
                
            logger.info(f"Redis connection pool created: {settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}")
        
        return cls._pool
    
    @classmethod
    def get_client(cls) -> Redis:
        """Get Redis client instance"""
        if cls._client is None:
            cls._client = Redis(connection_pool=cls.get_pool())
        return cls._client
    
    @classmethod
    def close(cls):
        """Close Redis connection pool"""
        if cls._pool:
            cls._pool.disconnect()
            cls._pool = None
            cls._client = None
            logger.info("Redis connection pool closed")


class RedisCache:
    """
    High-level Redis cache operations with serialization support
    """
    
    def __init__(self, prefix: str = "cache", serializer: str = "json"):
        """
        Initialize Redis cache
        
        Args:
            prefix: Key prefix for namespacing
            serializer: Serialization method ('json' or 'pickle')
        """
        self.client = RedisClient.get_client()
        self.prefix = prefix
        self.serializer = serializer
        
    def _make_key(self, key: str) -> str:
        """Create namespaced key"""
        return f"{self.prefix}:{key}"
    
    def _serialize(self, value: Any) -> bytes:
        """Serialize value for storage"""
        if self.serializer == "json":
            return json.dumps(value, default=str).encode('utf-8')
        elif self.serializer == "pickle":
            return pickle.dumps(value)
        else:
            raise ValueError(f"Unknown serializer: {self.serializer}")
    
    def _deserialize(self, value: bytes) -> Any:
        """Deserialize value from storage"""
        if value is None:
            return None
            
        try:
            if self.serializer == "json":
                return json.loads(value.decode('utf-8'))
            elif self.serializer == "pickle":
                return pickle.loads(value)
            else:
                raise ValueError(f"Unknown serializer: {self.serializer}")
        except Exception as e:
            logger.error(f"Failed to deserialize value: {e}")
            return None
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            full_key = self._make_key(key)
            value = self.client.get(full_key)
            return self._deserialize(value)
        except RedisError as e:
            logger.error(f"Redis GET error for key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            
        Returns:
            Success status
        """
        try:
            full_key = self._make_key(key)
            serialized = self._serialize(value)
            
            if ttl:
                return self.client.setex(full_key, ttl, serialized)
            else:
                return self.client.set(full_key, serialized)
        except RedisError as e:
            logger.error(f"Redis SET error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            full_key = self._make_key(key)
            return bool(self.client.delete(full_key))
        except RedisError as e:
            logger.error(f"Redis DELETE error for key {key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        try:
            full_pattern = self._make_key(pattern)
            keys = self.client.keys(full_pattern)
            if keys:
                return self.client.delete(*keys)
            return 0
        except RedisError as e:
            logger.error(f"Redis DELETE pattern error for {pattern}: {e}")
            return 0
    
    def exists(self, key: str) -> bool:
        """Check if key exists"""
        try:
            full_key = self._make_key(key)
            return bool(self.client.exists(full_key))
        except RedisError as e:
            logger.error(f"Redis EXISTS error for key {key}: {e}")
            return False
    
    def expire(self, key: str, ttl: int) -> bool:
        """Set expiration on existing key"""
        try:
            full_key = self._make_key(key)
            return bool(self.client.expire(full_key, ttl))
        except RedisError as e:
            logger.error(f"Redis EXPIRE error for key {key}: {e}")
            return False
    
    def ttl(self, key: str) -> int:
        """Get remaining TTL for key"""
        try:
            full_key = self._make_key(key)
            return self.client.ttl(full_key)
        except RedisError as e:
            logger.error(f"Redis TTL error for key {key}: {e}")
            return -2  # Key doesn't exist
    
    def mget(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values"""
        try:
            full_keys = [self._make_key(k) for k in keys]
            values = self.client.mget(full_keys)
            return {
                key: self._deserialize(value)
                for key, value in zip(keys, values)
                if value is not None
            }
        except RedisError as e:
            logger.error(f"Redis MGET error: {e}")
            return {}
    
    def mset(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple values"""
        try:
            # Serialize all values
            serialized_mapping = {
                self._make_key(k): self._serialize(v)
                for k, v in mapping.items()
            }
            
            if ttl:
                # Use pipeline for atomic operation with TTL
                pipe = self.client.pipeline()
                for key, value in serialized_mapping.items():
                    pipe.setex(key, ttl, value)
                pipe.execute()
                return True
            else:
                return self.client.mset(serialized_mapping)
        except RedisError as e:
            logger.error(f"Redis MSET error: {e}")
            return False
    
    def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment counter"""
        try:
            full_key = self._make_key(key)
            return self.client.incr(full_key, amount)
        except RedisError as e:
            logger.error(f"Redis INCR error for key {key}: {e}")
            return None
    
    def decr(self, key: str, amount: int = 1) -> Optional[int]:
        """Decrement counter"""
        try:
            full_key = self._make_key(key)
            return self.client.decr(full_key, amount)
        except RedisError as e:
            logger.error(f"Redis DECR error for key {key}: {e}")
            return None
    
    def clear_namespace(self) -> int:
        """Clear all keys in this namespace"""
        try:
            pattern = f"{self.prefix}:*"
            keys = self.client.keys(pattern)
            if keys:
                return self.client.delete(*keys)
            return 0
        except RedisError as e:
            logger.error(f"Redis CLEAR namespace error: {e}")
            return 0
    
    def ping(self) -> bool:
        """Check Redis connection"""
        try:
            return self.client.ping()
        except RedisError:
            return False
    
    def info(self) -> Dict[str, Any]:
        """Get Redis server info"""
        try:
            return self.client.info()
        except RedisError as e:
            logger.error(f"Redis INFO error: {e}")
            return {}
    
    def memory_usage(self, key: str) -> Optional[int]:
        """Get memory usage of a key in bytes"""
        try:
            full_key = self._make_key(key)
            return self.client.memory_usage(full_key)
        except RedisError as e:
            logger.error(f"Redis MEMORY USAGE error for key {key}: {e}")
            return None


# Singleton instances for different cache namespaces
@lru_cache(maxsize=None)
def get_cache(namespace: str = "default", serializer: str = "json") -> RedisCache:
    """Get or create cache instance for namespace"""
    return RedisCache(prefix=f"aura:{namespace}", serializer=serializer)