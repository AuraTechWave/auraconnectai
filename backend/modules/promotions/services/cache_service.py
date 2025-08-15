# backend/modules/promotions/services/cache_service.py

import json
import redis
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timedelta
import hashlib
import logging
from functools import wraps

from core.config import settings

logger = logging.getLogger(__name__)


class PromotionCacheService:
    """Redis-based caching service for promotion system"""

    def __init__(self):
        self.redis_client = None
        self.cache_enabled = getattr(settings, "REDIS_ENABLED", False)

        if self.cache_enabled:
            try:
                self.redis_client = redis.Redis(
                    host=getattr(settings, "REDIS_HOST", "localhost"),
                    port=getattr(settings, "REDIS_PORT", 6379),
                    db=getattr(settings, "REDIS_DB", 0),
                    password=getattr(settings, "REDIS_PASSWORD", None),
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True,
                )
                # Test connection
                self.redis_client.ping()
                logger.info("Redis cache connection established")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}. Caching disabled.")
                self.cache_enabled = False
                self.redis_client = None

    def _generate_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate a unique cache key"""
        key_data = f"{prefix}:{':'.join(str(arg) for arg in args)}"
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            kwargs_str = ":".join(f"{k}={v}" for k, v in sorted_kwargs)
            key_data += f":{kwargs_str}"

        # Hash long keys to avoid Redis key length limits
        if len(key_data) > 200:
            key_hash = hashlib.md5(key_data.encode()).hexdigest()
            return f"{prefix}:hash:{key_hash}"

        return key_data

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.cache_enabled:
            return None

        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")

        return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache with TTL"""
        if not self.cache_enabled:
            return False

        try:
            serialized_value = json.dumps(value, default=str)
            return self.redis_client.setex(key, ttl, serialized_value)
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.cache_enabled:
            return False

        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        if not self.cache_enabled:
            return 0

        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
        except Exception as e:
            logger.error(f"Cache delete pattern error for {pattern}: {e}")

        return 0

    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        if not self.cache_enabled:
            return False

        try:
            return bool(self.redis_client.exists(key))
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False

    def increment(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> int:
        """Increment counter in cache"""
        if not self.cache_enabled:
            return 0

        try:
            pipe = self.redis_client.pipeline()
            pipe.incr(key, amount)
            if ttl:
                pipe.expire(key, ttl)
            results = pipe.execute()
            return results[0]
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {e}")
            return 0

    def get_or_set(self, key: str, func, ttl: int = 3600, *args, **kwargs) -> Any:
        """Get from cache or execute function and cache result"""
        # Try to get from cache first
        cached_value = self.get(key)
        if cached_value is not None:
            return cached_value

        # Execute function and cache result
        try:
            value = func(*args, **kwargs)
            self.set(key, value, ttl)
            return value
        except Exception as e:
            logger.error(f"Error in get_or_set for key {key}: {e}")
            raise

    # Promotion-specific cache methods

    def cache_active_promotions(self, promotions: List[Dict], ttl: int = 300) -> bool:
        """Cache active promotions list"""
        key = self._generate_cache_key("promotions", "active")
        return self.set(key, promotions, ttl)

    def get_active_promotions(self) -> Optional[List[Dict]]:
        """Get cached active promotions"""
        key = self._generate_cache_key("promotions", "active")
        return self.get(key)

    def cache_promotion_eligibility(
        self,
        promotion_id: int,
        customer_id: int,
        is_eligible: bool,
        reason: str,
        ttl: int = 600,
    ) -> bool:
        """Cache promotion eligibility result"""
        key = self._generate_cache_key("eligibility", promotion_id, customer_id)
        value = {
            "is_eligible": is_eligible,
            "reason": reason,
            "cached_at": datetime.utcnow().isoformat(),
        }
        return self.set(key, value, ttl)

    def get_promotion_eligibility(
        self, promotion_id: int, customer_id: int
    ) -> Optional[Dict]:
        """Get cached promotion eligibility"""
        key = self._generate_cache_key("eligibility", promotion_id, customer_id)
        return self.get(key)

    def cache_discount_calculation(
        self,
        promotion_id: int,
        order_hash: str,
        discount_amount: float,
        ttl: int = 1800,
    ) -> bool:
        """Cache discount calculation result"""
        key = self._generate_cache_key("discount", promotion_id, order_hash)
        value = {
            "discount_amount": discount_amount,
            "calculated_at": datetime.utcnow().isoformat(),
        }
        return self.set(key, value, ttl)

    def get_discount_calculation(
        self, promotion_id: int, order_hash: str
    ) -> Optional[Dict]:
        """Get cached discount calculation"""
        key = self._generate_cache_key("discount", promotion_id, order_hash)
        return self.get(key)

    def cache_coupon_validation(
        self,
        coupon_code: str,
        customer_id: int,
        is_valid: bool,
        reason: str,
        ttl: int = 300,
    ) -> bool:
        """Cache coupon validation result"""
        key = self._generate_cache_key("coupon", "validation", coupon_code, customer_id)
        value = {
            "is_valid": is_valid,
            "reason": reason,
            "validated_at": datetime.utcnow().isoformat(),
        }
        return self.set(key, value, ttl)

    def get_coupon_validation(
        self, coupon_code: str, customer_id: int
    ) -> Optional[Dict]:
        """Get cached coupon validation"""
        key = self._generate_cache_key("coupon", "validation", coupon_code, customer_id)
        return self.get(key)

    def cache_customer_promotions(
        self, customer_id: int, promotions: List[Dict], ttl: int = 600
    ) -> bool:
        """Cache eligible promotions for a customer"""
        key = self._generate_cache_key("customer", "promotions", customer_id)
        return self.set(key, promotions, ttl)

    def get_customer_promotions(self, customer_id: int) -> Optional[List[Dict]]:
        """Get cached promotions for a customer"""
        key = self._generate_cache_key("customer", "promotions", customer_id)
        return self.get(key)

    def cache_analytics_report(
        self, report_type: str, parameters_hash: str, report_data: Dict, ttl: int = 1800
    ) -> bool:
        """Cache analytics report"""
        key = self._generate_cache_key("analytics", report_type, parameters_hash)
        return self.set(key, report_data, ttl)

    def get_analytics_report(
        self, report_type: str, parameters_hash: str
    ) -> Optional[Dict]:
        """Get cached analytics report"""
        key = self._generate_cache_key("analytics", report_type, parameters_hash)
        return self.get(key)

    # Cache invalidation methods

    def invalidate_promotion_cache(self, promotion_id: int) -> None:
        """Invalidate all cache entries related to a promotion"""
        patterns = [
            f"promotions:active*",
            f"eligibility:{promotion_id}:*",
            f"discount:{promotion_id}:*",
            f"customer:promotions:*",  # Customer-specific promotion lists
        ]

        for pattern in patterns:
            deleted_count = self.delete_pattern(pattern)
            if deleted_count > 0:
                logger.info(
                    f"Invalidated {deleted_count} cache entries for pattern: {pattern}"
                )

    def invalidate_customer_cache(self, customer_id: int) -> None:
        """Invalidate all cache entries related to a customer"""
        patterns = [
            f"eligibility:*:{customer_id}",
            f"coupon:validation:*:{customer_id}",
            f"customer:promotions:{customer_id}",
        ]

        for pattern in patterns:
            deleted_count = self.delete_pattern(pattern)
            if deleted_count > 0:
                logger.info(
                    f"Invalidated {deleted_count} cache entries for pattern: {pattern}"
                )

    def invalidate_coupon_cache(self, coupon_code: str) -> None:
        """Invalidate all cache entries related to a coupon"""
        pattern = f"coupon:validation:{coupon_code}:*"
        deleted_count = self.delete_pattern(pattern)
        if deleted_count > 0:
            logger.info(
                f"Invalidated {deleted_count} cache entries for coupon: {coupon_code}"
            )

    def invalidate_analytics_cache(self) -> None:
        """Invalidate all analytics cache entries"""
        pattern = "analytics:*"
        deleted_count = self.delete_pattern(pattern)
        if deleted_count > 0:
            logger.info(f"Invalidated {deleted_count} analytics cache entries")

    # Rate limiting methods

    def check_rate_limit(
        self, identifier: str, limit: int, window_seconds: int, action: str = "request"
    ) -> Dict[str, Any]:
        """Check and enforce rate limiting"""
        if not self.cache_enabled:
            return {"allowed": True, "remaining": limit, "reset_time": None}

        key = self._generate_cache_key("rate_limit", action, identifier)

        try:
            current_count = self.increment(key, 1, window_seconds)

            if current_count <= limit:
                remaining = limit - current_count
                reset_time = datetime.utcnow() + timedelta(seconds=window_seconds)
                return {
                    "allowed": True,
                    "remaining": remaining,
                    "reset_time": reset_time.isoformat(),
                    "current_count": current_count,
                }
            else:
                # Get TTL for reset time calculation
                ttl = self.redis_client.ttl(key)
                reset_time = (
                    datetime.utcnow() + timedelta(seconds=ttl) if ttl > 0 else None
                )

                return {
                    "allowed": False,
                    "remaining": 0,
                    "reset_time": reset_time.isoformat() if reset_time else None,
                    "current_count": current_count,
                }

        except Exception as e:
            logger.error(f"Rate limit check error for {identifier}: {e}")
            # On error, allow the request but log it
            return {
                "allowed": True,
                "remaining": limit,
                "reset_time": None,
                "error": str(e),
            }

    # Utility methods

    def warm_up_cache(self, db_session) -> Dict[str, int]:
        """Warm up cache with frequently accessed data"""
        if not self.cache_enabled:
            return {"status": "disabled"}

        warmed_items = {"promotions": 0, "customers": 0, "analytics": 0}

        try:
            # Warm up active promotions
            from modules.promotions.services.promotion_service import PromotionService

            promotion_service = PromotionService(db_session)

            active_promotions = promotion_service.get_active_promotions()
            if active_promotions:
                promotions_data = [
                    {
                        "id": p.id,
                        "name": p.name,
                        "discount_type": p.discount_type,
                        "discount_value": p.discount_value,
                        "minimum_order_amount": p.minimum_order_amount,
                        "priority": p.priority,
                    }
                    for p in active_promotions
                ]

                if self.cache_active_promotions(promotions_data):
                    warmed_items["promotions"] = len(promotions_data)

            # Could add more warm-up operations here
            logger.info(f"Cache warm-up completed: {warmed_items}")

        except Exception as e:
            logger.error(f"Cache warm-up error: {e}")

        return warmed_items

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics and health info"""
        if not self.cache_enabled:
            return {"status": "disabled"}

        try:
            info = self.redis_client.info()
            return {
                "status": "enabled",
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": round(
                    info.get("keyspace_hits", 0)
                    / max(
                        info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0), 1
                    )
                    * 100,
                    2,
                ),
                "total_keys": sum(
                    info.get(f"db{i}", {}).get("keys", 0) for i in range(16)
                ),
                "redis_version": info.get("redis_version", "unknown"),
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"status": "error", "error": str(e)}


# Cache decorator for easy caching of function results
def cached(
    ttl: int = 3600,
    key_prefix: str = "func",
    cache_service: Optional[PromotionCacheService] = None,
):
    """Decorator to cache function results"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if cache_service is None:
                # Create default cache service if none provided
                cache = PromotionCacheService()
            else:
                cache = cache_service

            # Generate cache key from function name and arguments
            func_name = func.__name__
            cache_key = cache._generate_cache_key(
                key_prefix, func_name, *args, **kwargs
            )

            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator


# Global cache service instance
cache_service = PromotionCacheService()


# Helper function to generate order hash for caching
def generate_order_hash(order_items: List[Dict]) -> str:
    """Generate a hash for order items to use as cache key"""
    order_str = json.dumps(order_items, sort_keys=True)
    return hashlib.md5(order_str.encode()).hexdigest()[:16]
