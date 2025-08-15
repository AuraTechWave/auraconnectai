# backend/modules/menu/services/recipe_cache_service.py

"""
Recipe Cache Service for performance optimization.
Provides Redis-based caching for recipe cost analysis and compliance reports.
"""

from typing import Dict, Any, Optional, Union
from datetime import datetime, timedelta
import json
import hashlib
from redis import Redis
from core.config import settings
from core.redis_config import get_redis_client
import logging

logger = logging.getLogger(__name__)


class RecipeCacheService:
    """
    Service for caching recipe-related data using Redis.
    Provides automatic serialization/deserialization and TTL management.
    """

    def __init__(self, redis_client: Optional[Redis] = None):
        """Initialize cache service with Redis client"""
        self.redis = redis_client
        self._local_cache = {}  # Fallback to local cache if Redis unavailable
        self._cache_ttl = {
            "cost_analysis": 300,  # 5 minutes
            "compliance_report": 600,  # 10 minutes
            "recipe_validation": 300,  # 5 minutes
            "bulk_cost_calculation": 1800,  # 30 minutes
        }

    def _get_cache_key(self, key_type: str, *args) -> str:
        """Generate a consistent cache key"""
        key_parts = [key_type] + [str(arg) for arg in args]
        key_string = ":".join(key_parts)
        return f"recipe_cache:{key_string}"

    def _serialize_value(self, value: Any) -> str:
        """Serialize value for storage"""
        if isinstance(value, (dict, list)):
            return json.dumps(value, default=str)
        return json.dumps({"value": value}, default=str)

    def _deserialize_value(self, value: str) -> Any:
        """Deserialize value from storage"""
        try:
            data = json.loads(value)
            if isinstance(data, dict) and "value" in data and len(data) == 1:
                return data["value"]
            return data
        except json.JSONDecodeError:
            return value

    def get(self, key_type: str, *args) -> Optional[Any]:
        """Get value from cache"""
        cache_key = self._get_cache_key(key_type, *args)

        try:
            if self.redis:
                value = self.redis.get(cache_key)
                if value:
                    return self._deserialize_value(value.decode("utf-8"))
            else:
                # Fallback to local cache
                if cache_key in self._local_cache:
                    value, expiry = self._local_cache[cache_key]
                    if datetime.utcnow() < expiry:
                        return value
                    else:
                        del self._local_cache[cache_key]
        except Exception as e:
            logger.warning(f"Cache get error: {e}")

        return None

    def set(self, key_type: str, value: Any, *args, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL override"""
        cache_key = self._get_cache_key(key_type, *args)
        ttl = ttl or self._cache_ttl.get(key_type, 300)

        try:
            serialized_value = self._serialize_value(value)

            if self.redis:
                self.redis.setex(cache_key, ttl, serialized_value)
                return True
            else:
                # Fallback to local cache
                expiry = datetime.utcnow() + timedelta(seconds=ttl)
                self._local_cache[cache_key] = (value, expiry)
                return True
        except Exception as e:
            logger.warning(f"Cache set error: {e}")
            return False

    def delete(self, key_type: str, *args) -> bool:
        """Delete value from cache"""
        cache_key = self._get_cache_key(key_type, *args)

        try:
            if self.redis:
                self.redis.delete(cache_key)
            else:
                self._local_cache.pop(cache_key, None)
            return True
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        deleted_count = 0

        try:
            if self.redis:
                # Use SCAN to avoid blocking
                cursor = 0
                while True:
                    cursor, keys = self.redis.scan(
                        cursor, match=f"recipe_cache:{pattern}*", count=100
                    )
                    if keys:
                        deleted_count += self.redis.delete(*keys)
                    if cursor == 0:
                        break
            else:
                # Fallback for local cache
                keys_to_delete = [
                    k
                    for k in self._local_cache.keys()
                    if k.startswith(f"recipe_cache:{pattern}")
                ]
                for key in keys_to_delete:
                    del self._local_cache[key]
                    deleted_count += 1
        except Exception as e:
            logger.warning(f"Cache delete pattern error: {e}")

        return deleted_count

    def invalidate_recipe_cache(self, recipe_id: int):
        """Invalidate all cache entries for a specific recipe"""
        patterns = [
            f"cost_analysis:{recipe_id}",
            f"recipe_validation:{recipe_id}",
            f"recipe_details:{recipe_id}",
        ]

        for pattern in patterns:
            self.delete_pattern(pattern)

    def invalidate_compliance_cache(self):
        """Invalidate compliance report cache"""
        self.delete("compliance_report", "full")
        self.delete_pattern("compliance_report:category:")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {
            "type": "redis" if self.redis else "local",
            "entries": 0,
            "memory_usage": 0,
        }

        try:
            if self.redis:
                info = self.redis.info()
                stats["entries"] = self.redis.dbsize()
                stats["memory_usage"] = info.get("used_memory", 0)
                stats["hit_rate"] = info.get("keyspace_hits", 0) / max(
                    1, info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0)
                )
            else:
                stats["entries"] = len(self._local_cache)
                # Estimate memory usage for local cache
                stats["memory_usage"] = sum(
                    len(str(k)) + len(str(v)) for k, (v, _) in self._local_cache.items()
                )
        except Exception as e:
            logger.warning(f"Error getting cache stats: {e}")

        return stats


# Singleton instance
_cache_service_instance = None


def get_recipe_cache_service(
    redis_client: Optional[Redis] = None,
) -> RecipeCacheService:
    """Get or create the singleton cache service instance"""
    global _cache_service_instance

    if _cache_service_instance is None:
        # Use provided client or get from config
        client = redis_client or get_redis_client()
        _cache_service_instance = RecipeCacheService(client)

    return _cache_service_instance
