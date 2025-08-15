# backend/modules/staff/services/schedule_cache_service.py

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import json
import hashlib
from redis import asyncio as aioredis
import logging

from core.config_validation import config as settings

logger = logging.getLogger(__name__)


class ScheduleCacheService:
    """Service for caching schedule previews and computations"""

    def __init__(self):
        self.redis_url = settings.REDIS_URL or "redis://localhost:6379"
        self.cache_ttl = 3600  # 1 hour default TTL
        self.preview_cache_prefix = "schedule:preview:"
        self.computation_cache_prefix = "schedule:computation:"
        self._redis: Optional[aioredis.Redis] = None

    async def get_redis(self) -> aioredis.Redis:
        """Get or create Redis connection"""
        if not self._redis:
            self._redis = await aioredis.from_url(
                self.redis_url, encoding="utf-8", decode_responses=True
            )
        return self._redis

    async def close(self):
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()
            self._redis = None

    def _generate_preview_key(
        self,
        restaurant_id: int,
        start_date: datetime,
        end_date: datetime,
        filters: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate cache key for preview"""
        # Create deterministic key from parameters
        key_data = {
            "restaurant_id": restaurant_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "filters": filters or {},
        }

        # Sort filters to ensure consistent key generation
        key_string = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()[:12]

        return f"{self.preview_cache_prefix}{restaurant_id}:{key_hash}"

    async def get_preview_cache(
        self,
        restaurant_id: int,
        start_date: datetime,
        end_date: datetime,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get cached preview data"""
        try:
            redis = await self.get_redis()
            key = self._generate_preview_key(
                restaurant_id, start_date, end_date, filters
            )

            cached_data = await redis.get(key)
            if cached_data:
                logger.info(f"Cache hit for preview key: {key}")
                return json.loads(cached_data)

            logger.info(f"Cache miss for preview key: {key}")
            return None

        except Exception as e:
            logger.error(f"Error getting preview cache: {e}")
            return None

    async def set_preview_cache(
        self,
        restaurant_id: int,
        start_date: datetime,
        end_date: datetime,
        data: Dict[str, Any],
        filters: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None,
    ):
        """Set preview cache data"""
        try:
            redis = await self.get_redis()
            key = self._generate_preview_key(
                restaurant_id, start_date, end_date, filters
            )

            # Add cache metadata
            cache_data = {
                **data,
                "_cached_at": datetime.utcnow().isoformat(),
                "_cache_key": key,
            }

            ttl = ttl or self.cache_ttl
            await redis.setex(key, ttl, json.dumps(cache_data))

            # Track cache keys for this restaurant
            tracker_key = f"{self.preview_cache_prefix}tracker:{restaurant_id}"
            await redis.sadd(tracker_key, key)
            await redis.expire(tracker_key, 86400)  # 24 hour expiry for tracker

            logger.info(f"Cached preview data with key: {key}, TTL: {ttl}s")

        except Exception as e:
            logger.error(f"Error setting preview cache: {e}")

    async def invalidate_restaurant_cache(self, restaurant_id: int):
        """Invalidate all cache entries for a restaurant"""
        try:
            redis = await self.get_redis()

            # Get all cache keys for this restaurant
            tracker_key = f"{self.preview_cache_prefix}tracker:{restaurant_id}"
            cache_keys = await redis.smembers(tracker_key)

            if cache_keys:
                # Delete all cache entries
                await redis.delete(*cache_keys)
                # Delete the tracker
                await redis.delete(tracker_key)

                logger.info(
                    f"Invalidated {len(cache_keys)} cache entries for restaurant {restaurant_id}"
                )

        except Exception as e:
            logger.error(f"Error invalidating restaurant cache: {e}")

    async def cache_computation_result(
        self,
        computation_id: str,
        result: Dict[str, Any],
        ttl: int = 7200,  # 2 hours default
    ):
        """Cache expensive computation results"""
        try:
            redis = await self.get_redis()
            key = f"{self.computation_cache_prefix}{computation_id}"

            cache_data = {
                **result,
                "_cached_at": datetime.utcnow().isoformat(),
                "_computation_id": computation_id,
            }

            await redis.setex(key, ttl, json.dumps(cache_data))
            logger.info(f"Cached computation result: {computation_id}")

        except Exception as e:
            logger.error(f"Error caching computation result: {e}")

    async def get_computation_result(
        self, computation_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached computation result"""
        try:
            redis = await self.get_redis()
            key = f"{self.computation_cache_prefix}{computation_id}"

            cached_data = await redis.get(key)
            if cached_data:
                logger.info(f"Cache hit for computation: {computation_id}")
                return json.loads(cached_data)

            return None

        except Exception as e:
            logger.error(f"Error getting computation cache: {e}")
            return None

    async def warm_cache_for_week(
        self, restaurant_id: int, week_start: datetime, generate_preview_func
    ):
        """Pre-warm cache for a week's worth of previews"""
        try:
            # Cache daily previews for the week
            for day in range(7):
                date = week_start + timedelta(days=day)

                # Check if already cached
                existing = await self.get_preview_cache(restaurant_id, date, date)

                if not existing:
                    # Generate and cache
                    preview_data = await generate_preview_func(
                        restaurant_id, date, date
                    )

                    await self.set_preview_cache(
                        restaurant_id,
                        date,
                        date,
                        preview_data,
                        ttl=86400,  # 24 hours for daily previews
                    )

            logger.info(
                f"Warmed cache for restaurant {restaurant_id}, week of {week_start}"
            )

        except Exception as e:
            logger.error(f"Error warming cache: {e}")

    async def get_cache_stats(self, restaurant_id: int) -> Dict[str, Any]:
        """Get cache statistics for a restaurant"""
        try:
            redis = await self.get_redis()

            # Get cache keys
            tracker_key = f"{self.preview_cache_prefix}tracker:{restaurant_id}"
            cache_keys = await redis.smembers(tracker_key)

            stats = {
                "total_cached_previews": len(cache_keys),
                "cache_keys": list(cache_keys),
                "oldest_cache": None,
                "newest_cache": None,
                "total_size_bytes": 0,
            }

            if cache_keys:
                # Get cache details
                cache_times = []
                for key in cache_keys:
                    data = await redis.get(key)
                    if data:
                        stats["total_size_bytes"] += len(data)
                        parsed = json.loads(data)
                        if "_cached_at" in parsed:
                            cache_times.append(parsed["_cached_at"])

                if cache_times:
                    cache_times.sort()
                    stats["oldest_cache"] = cache_times[0]
                    stats["newest_cache"] = cache_times[-1]

            return stats

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}


# Create singleton service
schedule_cache_service = ScheduleCacheService()


# Context manager for auto-cleanup
class ScheduleCacheContext:
    """Context manager for schedule cache with auto-cleanup"""

    def __init__(self, cache_service: ScheduleCacheService):
        self.cache_service = cache_service

    async def __aenter__(self):
        return self.cache_service

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cache_service.close()
