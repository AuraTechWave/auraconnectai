"""
API Rate Limiting middleware for AuraConnect.

Provides protection against abuse, DDoS attacks, and ensures fair
resource usage across different client types.
"""

import time
import asyncio
from typing import Dict, Optional, Callable, Any
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import redis.asyncio as redis
import json
import os


@dataclass
class RateLimitRule:
    """Rate limiting rule configuration."""
    requests: int  # Number of requests allowed
    window: int    # Time window in seconds
    burst: Optional[int] = None  # Burst allowance
    

class RateLimitExceeded(HTTPException):
    """Custom exception for rate limit exceeded."""
    
    def __init__(self, retry_after: int):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "retry_after": retry_after,
                "message": f"Too many requests. Please try again in {retry_after} seconds."
            },
            headers={"Retry-After": str(retry_after)}
        )


class MemoryRateLimiter:
    """In-memory rate limiter using sliding window algorithm."""
    
    def __init__(self):
        self.clients: Dict[str, deque] = defaultdict(lambda: deque())
        self.lock = asyncio.Lock()
    
    async def is_allowed(self, key: str, rule: RateLimitRule) -> tuple[bool, int]:
        """Check if request is allowed under rate limit."""
        async with self.lock:
            now = time.time()
            window_start = now - rule.window
            
            # Clean old requests outside the window
            client_requests = self.clients[key]
            while client_requests and client_requests[0] < window_start:
                client_requests.popleft()
            
            # Check if under limit
            if len(client_requests) < rule.requests:
                client_requests.append(now)
                return True, 0
            
            # Calculate retry after time
            oldest_request = client_requests[0]
            retry_after = int(oldest_request + rule.window - now) + 1
            return False, retry_after


class RedisRateLimiter:
    """Redis-based rate limiter for distributed environments."""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
    
    async def connect(self):
        """Connect to Redis."""
        if not self.redis_client:
            self.redis_client = redis.from_url(self.redis_url)
    
    async def is_allowed(self, key: str, rule: RateLimitRule) -> tuple[bool, int]:
        """Check if request is allowed using Redis sliding window."""
        if not self.redis_client:
            await self.connect()
        
        now = time.time()
        window_start = now - rule.window
        
        # Use Redis pipeline for atomic operations
        pipe = self.redis_client.pipeline()
        
        # Remove expired entries
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count current requests
        pipe.zcard(key)
        
        # Add current request with score as timestamp
        pipe.zadd(key, {str(now): now})
        
        # Set expiry for the key
        pipe.expire(key, rule.window)
        
        results = await pipe.execute()
        current_requests = results[1]
        
        if current_requests < rule.requests:
            return True, 0
        
        # Get oldest request to calculate retry time
        oldest = await self.redis_client.zrange(key, 0, 0, withscores=True)
        if oldest:
            oldest_timestamp = oldest[0][1]
            retry_after = int(oldest_timestamp + rule.window - now) + 1
            return False, retry_after
        
        return False, rule.window


class RateLimiter:
    """Main rate limiter with configurable backend."""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.rules: Dict[str, RateLimitRule] = {}
        
        if redis_url:
            self.backend = RedisRateLimiter(redis_url)
        else:
            self.backend = MemoryRateLimiter()
    
    def add_rule(self, pattern: str, requests: int, window: int, burst: Optional[int] = None):
        """Add a rate limiting rule."""
        self.rules[pattern] = RateLimitRule(requests, window, burst)
    
    def get_client_key(self, request: Request) -> str:
        """Generate client key for rate limiting."""
        # Try to get authenticated user ID first
        user_id = getattr(request.state, 'user_id', None)
        if user_id:
            return f"user:{user_id}"
        
        # Fall back to IP address
        client_ip = self._get_client_ip(request)
        return f"ip:{client_ip}"
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        # Check for forwarded headers (for load balancers/proxies)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to direct client IP
        return request.client.host if request.client else "unknown"
    
    def get_rule_for_endpoint(self, request: Request) -> Optional[RateLimitRule]:
        """Get rate limiting rule for the current endpoint."""
        path = request.url.path
        method = request.method
        
        # Check for exact matches first
        for pattern, rule in self.rules.items():
            if pattern == f"{method} {path}":
                return rule
            elif pattern == path:
                return rule
        
        # Check for pattern matches
        for pattern, rule in self.rules.items():
            if pattern.startswith('/') and path.startswith(pattern):
                return rule
            elif pattern == method:
                return rule
        
        # Default rule
        return self.rules.get('default')
    
    async def check_rate_limit(self, request: Request) -> Optional[JSONResponse]:
        """Check rate limit for the request."""
        rule = self.get_rule_for_endpoint(request)
        if not rule:
            return None
        
        client_key = self.get_client_key(request)
        endpoint_key = f"{client_key}:{request.url.path}"
        
        allowed, retry_after = await self.backend.is_allowed(endpoint_key, rule)
        
        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Please try again in {retry_after} seconds.",
                    "retry_after": retry_after
                },
                headers={"Retry-After": str(retry_after)}
            )
        
        return None


# Global rate limiter instance
rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global rate_limiter
    if rate_limiter is None:
        redis_url = os.getenv("REDIS_URL")
        rate_limiter = RateLimiter(redis_url)
        _configure_default_rules(rate_limiter)
    return rate_limiter


def _configure_default_rules(limiter: RateLimiter):
    """Configure default rate limiting rules."""
    # General API limits
    limiter.add_rule('default', requests=100, window=60)  # 100 req/min default
    
    # Authentication endpoints (more restrictive)
    limiter.add_rule('POST /auth/login', requests=5, window=60)  # 5 login attempts per minute
    limiter.add_rule('POST /auth/register', requests=3, window=300)  # 3 registrations per 5 minutes
    
    # Payroll endpoints (moderate limits)
    limiter.add_rule('/api/v1/payrolls', requests=50, window=60)  # 50 req/min for payroll
    limiter.add_rule('POST /api/v1/payrolls/run', requests=10, window=300)  # 10 payroll runs per 5 minutes
    
    # Order endpoints (higher limits for real-time operations)
    limiter.add_rule('/api/v1/orders', requests=200, window=60)  # 200 req/min for orders
    
    # File upload endpoints
    limiter.add_rule('POST', requests=20, window=60)  # 20 POST requests per minute
    
    # Admin endpoints (very restrictive)
    limiter.add_rule('/api/v1/admin', requests=20, window=60)  # 20 req/min for admin
    
    # Health check (unlimited)
    limiter.add_rule('/health', requests=1000, window=60)  # High limit for health checks


async def rate_limit_middleware(request: Request, call_next: Callable) -> Any:
    """Rate limiting middleware for FastAPI."""
    limiter = get_rate_limiter()
    
    # Check rate limit
    rate_limit_response = await limiter.check_rate_limit(request)
    if rate_limit_response:
        return rate_limit_response
    
    # Process request
    response = await call_next(request)
    
    # Add rate limit headers to response
    rule = limiter.get_rule_for_endpoint(request)
    if rule:
        response.headers["X-RateLimit-Limit"] = str(rule.requests)
        response.headers["X-RateLimit-Window"] = str(rule.window)
    
    return response


def rate_limit(requests: int, window: int):
    """Decorator for custom rate limiting on specific endpoints."""
    def decorator(func):
        func._rate_limit_rule = RateLimitRule(requests, window)
        return func
    return decorator