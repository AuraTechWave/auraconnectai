# backend/modules/analytics/middleware/rate_limiter.py

"""
Rate limiting middleware for analytics endpoints.

Implements token bucket algorithm for rate limiting.
"""

import time
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from functools import wraps
import asyncio

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse

from modules.analytics.constants import RATE_LIMIT_REQUESTS_PER_MINUTE
from modules.analytics.exceptions import RateLimitError

logger = logging.getLogger(__name__)


class TokenBucket:
    """Token bucket implementation for rate limiting"""
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket.
        
        Args:
            capacity: Maximum number of tokens
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self._lock = asyncio.Lock()
    
    async def consume(self, tokens: int = 1) -> Tuple[bool, float]:
        """
        Try to consume tokens from bucket.
        
        Returns:
            Tuple of (success, wait_time_if_failed)
        """
        async with self._lock:
            now = time.time()
            
            # Refill tokens based on time elapsed
            elapsed = now - self.last_refill
            tokens_to_add = elapsed * self.refill_rate
            self.tokens = min(self.capacity, self.tokens + tokens_to_add)
            self.last_refill = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True, 0.0
            else:
                # Calculate wait time
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.refill_rate
                return False, wait_time


class RateLimiter:
    """Rate limiter for API endpoints"""
    
    def __init__(self):
        self.buckets: Dict[str, Dict[str, TokenBucket]] = {}
        self._cleanup_interval = 3600  # 1 hour
        self._last_cleanup = time.time()
    
    def _get_bucket_key(self, request: Request, endpoint: str) -> str:
        """Generate bucket key from request"""
        # Use user ID if authenticated, otherwise IP
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"user:{user_id}:{endpoint}"
        else:
            client_ip = request.client.host
            return f"ip:{client_ip}:{endpoint}"
    
    def _get_or_create_bucket(
        self,
        key: str,
        endpoint: str
    ) -> TokenBucket:
        """Get or create token bucket for key"""
        if endpoint not in self.buckets:
            self.buckets[endpoint] = {}
        
        if key not in self.buckets[endpoint]:
            # Get rate limit for endpoint
            requests_per_minute = RATE_LIMIT_REQUESTS_PER_MINUTE.get(
                endpoint,
                60  # Default to 60 requests per minute
            )
            
            # Create bucket with capacity = requests_per_minute
            # and refill_rate = requests_per_minute / 60 (per second)
            self.buckets[endpoint][key] = TokenBucket(
                capacity=requests_per_minute,
                refill_rate=requests_per_minute / 60.0
            )
        
        return self.buckets[endpoint][key]
    
    async def check_rate_limit(
        self,
        request: Request,
        endpoint: str,
        tokens: int = 1
    ) -> None:
        """
        Check rate limit for request.
        
        Raises:
            RateLimitError if rate limit exceeded
        """
        # Periodic cleanup
        if time.time() - self._last_cleanup > self._cleanup_interval:
            self._cleanup_old_buckets()
        
        key = self._get_bucket_key(request, endpoint)
        bucket = self._get_or_create_bucket(key, endpoint)
        
        success, wait_time = await bucket.consume(tokens)
        
        if not success:
            retry_after = int(wait_time) + 1  # Round up
            raise RateLimitError(
                endpoint=endpoint,
                limit=bucket.capacity,
                window="minute",
                retry_after=retry_after
            )
    
    def _cleanup_old_buckets(self):
        """Remove inactive buckets to prevent memory leak"""
        now = time.time()
        
        for endpoint in list(self.buckets.keys()):
            for key in list(self.buckets[endpoint].keys()):
                bucket = self.buckets[endpoint][key]
                # Remove buckets that haven't been used in 1 hour
                if now - bucket.last_refill > 3600:
                    del self.buckets[endpoint][key]
            
            # Remove empty endpoint entries
            if not self.buckets[endpoint]:
                del self.buckets[endpoint]
        
        self._last_cleanup = now
        logger.debug("Cleaned up old rate limit buckets")


# Global rate limiter instance
_rate_limiter = RateLimiter()


def rate_limit(endpoint: str, tokens: int = 1):
    """
    Decorator for rate limiting endpoints.
    
    Args:
        endpoint: Endpoint name for rate limit lookup
        tokens: Number of tokens to consume per request
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(request: Request, *args, **kwargs):
            try:
                await _rate_limiter.check_rate_limit(request, endpoint, tokens)
            except RateLimitError as e:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": e.message,
                            "retry_after": e.details["retry_after"]
                        }
                    },
                    headers={
                        "Retry-After": str(e.details["retry_after"]),
                        "X-RateLimit-Limit": str(e.details["limit"]),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(
                            int(time.time()) + e.details["retry_after"]
                        )
                    }
                )
            
            # Add rate limit headers to response
            response = await func(request, *args, **kwargs)
            
            # Get bucket to check remaining tokens
            key = _rate_limiter._get_bucket_key(request, endpoint)
            bucket = _rate_limiter._get_or_create_bucket(key, endpoint)
            
            if isinstance(response, Response):
                response.headers["X-RateLimit-Limit"] = str(bucket.capacity)
                response.headers["X-RateLimit-Remaining"] = str(int(bucket.tokens))
                response.headers["X-RateLimit-Reset"] = str(
                    int(bucket.last_refill + 60)  # Reset in 1 minute
                )
            
            return response
        
        return async_wrapper
    
    return decorator


# Middleware for global rate limiting
async def rate_limit_middleware(request: Request, call_next):
    """
    Global rate limiting middleware.
    
    This can be used for overall API rate limiting across all endpoints.
    """
    try:
        # Check global rate limit (optional)
        # await _rate_limiter.check_rate_limit(request, "global", 1)
        
        response = await call_next(request)
        return response
        
    except RateLimitError as e:
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": e.message,
                    "retry_after": e.details["retry_after"]
                }
            },
            headers={
                "Retry-After": str(e.details["retry_after"])
            }
        )