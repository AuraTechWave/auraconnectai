# backend/core/rate_limiting.py

from fastapi import HTTPException, Request
from typing import Dict, Optional, Callable, Any
import time
import asyncio
from collections import defaultdict, deque
from datetime import datetime, timedelta
import logging
import redis
from functools import wraps

logger = logging.getLogger(__name__)


class RateLimiter:
    """Advanced rate limiting system with multiple strategies"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.local_storage = defaultdict(lambda: defaultdict(deque))
        self.blocked_ips = set()
        
    def sliding_window_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        identifier: str = "default"
    ) -> Dict[str, Any]:
        """
        Sliding window rate limiting implementation
        Returns rate limit status and remaining requests
        """
        now = time.time()
        window_start = now - window_seconds
        
        if self.redis_client:
            return self._redis_sliding_window(key, limit, window_seconds, now, window_start)
        else:
            return self._local_sliding_window(key, limit, window_seconds, now, window_start)
    
    def _redis_sliding_window(self, key: str, limit: int, window_seconds: int, now: float, window_start: float) -> Dict[str, Any]:
        """Redis-based sliding window implementation"""
        try:
            pipe = self.redis_client.pipeline()
            
            # Remove old entries
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current entries
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(now): now})
            
            # Set expiration
            pipe.expire(key, window_seconds + 1)
            
            results = pipe.execute()
            current_count = results[1] + 1  # +1 for the current request
            
            remaining = max(0, limit - current_count)
            
            return {
                "allowed": current_count <= limit,
                "current_count": current_count,
                "limit": limit,
                "remaining": remaining,
                "reset_time": now + window_seconds,
                "retry_after": max(0, window_seconds - (now - window_start)) if current_count > limit else 0
            }
            
        except Exception as e:
            logger.error(f"Redis rate limiting error: {str(e)}")
            # Fallback to local storage
            return self._local_sliding_window(key, limit, window_seconds, now, window_start)
    
    def _local_sliding_window(self, key: str, limit: int, window_seconds: int, now: float, window_start: float) -> Dict[str, Any]:
        """Local memory-based sliding window implementation"""
        requests = self.local_storage[key]["requests"]
        
        # Remove old requests
        while requests and requests[0] < window_start:
            requests.popleft()
        
        # Add current request
        requests.append(now)
        
        current_count = len(requests)
        remaining = max(0, limit - current_count)
        
        return {
            "allowed": current_count <= limit,
            "current_count": current_count,
            "limit": limit,
            "remaining": remaining,
            "reset_time": now + window_seconds,
            "retry_after": 0 if current_count <= limit else window_seconds
        }
    
    def token_bucket_rate_limit(
        self,
        key: str,
        tokens_per_second: float,
        bucket_size: int,
        tokens_requested: int = 1
    ) -> Dict[str, Any]:
        """
        Token bucket rate limiting implementation
        Good for burst traffic management
        """
        now = time.time()
        
        if self.redis_client:
            return self._redis_token_bucket(key, tokens_per_second, bucket_size, tokens_requested, now)
        else:
            return self._local_token_bucket(key, tokens_per_second, bucket_size, tokens_requested, now)
    
    def _redis_token_bucket(self, key: str, tokens_per_second: float, bucket_size: int, tokens_requested: int, now: float) -> Dict[str, Any]:
        """Redis-based token bucket implementation"""
        try:
            bucket_key = f"bucket:{key}"
            last_refill_key = f"bucket_refill:{key}"
            
            pipe = self.redis_client.pipeline()
            pipe.get(bucket_key)
            pipe.get(last_refill_key)
            current_tokens, last_refill = pipe.execute()
            
            current_tokens = float(current_tokens) if current_tokens else bucket_size
            last_refill = float(last_refill) if last_refill else now
            
            # Refill tokens based on time passed
            time_passed = now - last_refill
            tokens_to_add = time_passed * tokens_per_second
            current_tokens = min(bucket_size, current_tokens + tokens_to_add)
            
            # Check if request can be fulfilled
            allowed = current_tokens >= tokens_requested
            
            if allowed:
                current_tokens -= tokens_requested
            
            # Update Redis
            pipe = self.redis_client.pipeline()
            pipe.set(bucket_key, current_tokens, ex=3600)  # 1 hour expiry
            pipe.set(last_refill_key, now, ex=3600)
            pipe.execute()
            
            return {
                "allowed": allowed,
                "tokens_remaining": int(current_tokens),
                "bucket_size": bucket_size,
                "refill_rate": tokens_per_second,
                "retry_after": max(0, (tokens_requested - current_tokens) / tokens_per_second) if not allowed else 0
            }
            
        except Exception as e:
            logger.error(f"Redis token bucket error: {str(e)}")
            return self._local_token_bucket(key, tokens_per_second, bucket_size, tokens_requested, now)
    
    def _local_token_bucket(self, key: str, tokens_per_second: float, bucket_size: int, tokens_requested: int, now: float) -> Dict[str, Any]:
        """Local memory-based token bucket implementation"""
        bucket_data = self.local_storage[key]["bucket"]
        
        if not bucket_data:
            bucket_data.update({
                "tokens": bucket_size,
                "last_refill": now
            })
        
        # Refill tokens
        time_passed = now - bucket_data["last_refill"]
        tokens_to_add = time_passed * tokens_per_second
        bucket_data["tokens"] = min(bucket_size, bucket_data["tokens"] + tokens_to_add)
        bucket_data["last_refill"] = now
        
        # Check if request can be fulfilled
        allowed = bucket_data["tokens"] >= tokens_requested
        
        if allowed:
            bucket_data["tokens"] -= tokens_requested
        
        return {
            "allowed": allowed,
            "tokens_remaining": int(bucket_data["tokens"]),
            "bucket_size": bucket_size,
            "refill_rate": tokens_per_second,
            "retry_after": max(0, (tokens_requested - bucket_data["tokens"]) / tokens_per_second) if not allowed else 0
        }
    
    def adaptive_rate_limit(
        self,
        key: str,
        base_limit: int,
        window_seconds: int,
        error_threshold: float = 0.1,
        success_bonus: float = 1.2
    ) -> Dict[str, Any]:
        """
        Adaptive rate limiting that adjusts based on success/error rates
        Reduces limits for clients with high error rates, increases for successful clients
        """
        now = time.time()
        
        # Get recent request history
        history_key = f"adaptive:{key}"
        
        if self.redis_client:
            # Redis implementation would go here
            pass
        
        # Local implementation
        history = self.local_storage[history_key]["history"]
        
        # Clean old entries
        cutoff = now - window_seconds
        history[:] = [(timestamp, success) for timestamp, success in history if timestamp > cutoff]
        
        # Calculate success rate
        if len(history) < 10:  # Not enough data, use base limit
            current_limit = base_limit
        else:
            success_rate = sum(1 for _, success in history if success) / len(history)
            
            if success_rate < (1 - error_threshold):
                # High error rate, reduce limit
                current_limit = max(1, int(base_limit * 0.5))
            elif success_rate > 0.95:
                # High success rate, increase limit
                current_limit = int(base_limit * success_bonus)
            else:
                current_limit = base_limit
        
        # Apply sliding window with adaptive limit
        result = self.sliding_window_rate_limit(key, current_limit, window_seconds)
        result["adaptive_limit"] = current_limit
        result["base_limit"] = base_limit
        
        return result
    
    def record_request_result(self, key: str, success: bool):
        """Record the result of a request for adaptive rate limiting"""
        now = time.time()
        history_key = f"adaptive:{key}"
        history = self.local_storage[history_key]["history"]
        history.append((now, success))
        
        # Keep only recent history (last 1000 requests or 24 hours)
        if len(history) > 1000:
            history.popleft()
    
    def block_ip(self, ip: str, duration_seconds: int = 3600):
        """Block an IP address for a specified duration"""
        self.blocked_ips.add(ip)
        
        # Schedule unblock
        async def unblock_later():
            await asyncio.sleep(duration_seconds)
            self.blocked_ips.discard(ip)
            logger.info(f"Unblocked IP: {ip}")
        
        asyncio.create_task(unblock_later())
        logger.warning(f"Blocked IP: {ip} for {duration_seconds} seconds")
    
    def is_ip_blocked(self, ip: str) -> bool:
        """Check if an IP address is blocked"""
        return ip in self.blocked_ips


# Rate limiting decorators
def rate_limit(
    limit: int,
    window: int = 60,
    per: str = "ip",
    key_func: Optional[Callable] = None,
    limiter: Optional[RateLimiter] = None
):
    """
    Decorator for rate limiting FastAPI endpoints
    
    Args:
        limit: Number of requests allowed
        window: Time window in seconds
        per: What to rate limit by ("ip", "user", "endpoint")
        key_func: Custom function to generate rate limit key
        limiter: Custom rate limiter instance
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get request from kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                for value in kwargs.values():
                    if isinstance(value, Request):
                        request = value
                        break
            
            if not request:
                # No request found, skip rate limiting
                return await func(*args, **kwargs)
            
            # Use provided limiter or create default
            rate_limiter = limiter or getattr(wrapper, '_rate_limiter', None)
            if not rate_limiter:
                rate_limiter = RateLimiter()
                wrapper._rate_limiter = rate_limiter
            
            # Check if IP is blocked
            client_ip = request.client.host
            if rate_limiter.is_ip_blocked(client_ip):
                raise HTTPException(status_code=429, detail="IP address is blocked")
            
            # Generate rate limit key
            if key_func:
                key = key_func(request)
            elif per == "ip":
                key = f"ip:{client_ip}"
            elif per == "user":
                # Try to get user ID from request
                user_id = getattr(request.state, 'user_id', None) or client_ip
                key = f"user:{user_id}"
            elif per == "endpoint":
                key = f"endpoint:{request.url.path}:{client_ip}"
            else:
                key = f"custom:{per}:{client_ip}"
            
            # Check rate limit
            result = rate_limiter.sliding_window_rate_limit(key, limit, window)
            
            if not result["allowed"]:
                # Add rate limit headers
                headers = {
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": str(result["remaining"]),
                    "X-RateLimit-Reset": str(int(result["reset_time"])),
                    "Retry-After": str(int(result["retry_after"]))
                }
                
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Try again in {result['retry_after']:.0f} seconds.",
                    headers=headers
                )
            
            # Execute the function
            try:
                response = await func(*args, **kwargs)
                
                # Record successful request for adaptive limiting
                if hasattr(rate_limiter, 'record_request_result'):
                    rate_limiter.record_request_result(key, True)
                
                return response
                
            except Exception as e:
                # Record failed request for adaptive limiting
                if hasattr(rate_limiter, 'record_request_result'):
                    rate_limiter.record_request_result(key, False)
                raise
        
        return wrapper
    return decorator


def adaptive_rate_limit(base_limit: int, window: int = 60, per: str = "ip"):
    """Decorator for adaptive rate limiting"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Implementation similar to rate_limit decorator
            # but using adaptive_rate_limit method
            pass
        return wrapper
    return decorator


# Middleware for global rate limiting
class RateLimitMiddleware:
    """Middleware for applying rate limits globally"""
    
    def __init__(self, limiter: RateLimiter, global_limit: int = 1000, window: int = 3600):
        self.limiter = limiter
        self.global_limit = global_limit
        self.window = window
    
    async def __call__(self, request: Request, call_next):
        client_ip = request.client.host
        
        # Check if IP is blocked
        if self.limiter.is_ip_blocked(client_ip):
            raise HTTPException(status_code=429, detail="IP address is blocked")
        
        # Apply global rate limit
        key = f"global:{client_ip}"
        result = self.limiter.sliding_window_rate_limit(key, self.global_limit, self.window)
        
        if not result["allowed"]:
            raise HTTPException(
                status_code=429,
                detail="Global rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(self.global_limit),
                    "X-RateLimit-Remaining": str(result["remaining"]),
                    "Retry-After": str(int(result["retry_after"]))
                }
            )
        
        response = await call_next(request)
        
        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(self.global_limit)
        response.headers["X-RateLimit-Remaining"] = str(result["remaining"])
        response.headers["X-RateLimit-Reset"] = str(int(result["reset_time"]))
        
        return response