"""
API Rate Limiting middleware for AuraConnect.

Provides protection against abuse, DDoS attacks, and ensures fair
resource usage across different client types.
"""

import time
import asyncio
import logging
import os
from typing import Dict, Optional, Callable, Any
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque
from dataclasses import dataclass
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse

# Configure loggers for rate limiting
logger = logging.getLogger("core.rate_limiter")
security_logger = logging.getLogger("security.rate_limit")
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
            
            # Determine effective limit (with burst tolerance if configured)
            effective_limit = rule.requests
            if rule.burst is not None:
                # Allow burst up to the specified amount
                effective_limit = min(rule.requests + rule.burst, rule.requests * 2)
            
            # Check if under effective limit
            if len(client_requests) < effective_limit:
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
        self._lua_script_sha: Optional[str] = None
        
        # Lua script for atomic rate limiting operations
        self._lua_script = """
        local key = KEYS[1]
        local window = tonumber(ARGV[1])
        local limit = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local window_start = now - window
        
        -- Remove expired entries
        redis.call('ZREMRANGEBYSCORE', key, 0, window_start)
        
        -- Count current requests
        local current = redis.call('ZCARD', key)
        
        -- Check if under limit
        if current < limit then
            -- Add current request
            redis.call('ZADD', key, now, now)
            -- Set expiry
            redis.call('EXPIRE', key, window)
            return {1, 0}  -- allowed, retry_after
        else
            -- Get oldest request for retry calculation
            local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
            if #oldest > 0 then
                local retry_after = math.ceil(oldest[2] + window - now)
                return {0, retry_after}  -- not allowed, retry_after
            else
                return {0, window}  -- not allowed, retry_after = window
            end
        end
        """
    
    async def connect(self):
        """Connect to Redis and load Lua script."""
        if not self.redis_client:
            self.redis_client = redis.from_url(self.redis_url)
            # Load Lua script for atomic operations
            self._lua_script_sha = await self.redis_client.script_load(self._lua_script)
    
    async def disconnect(self):
        """Disconnect from Redis and close connection pool."""
        if self.redis_client:
            await self.redis_client.aclose()
            self.redis_client = None
    
    async def is_allowed(self, key: str, rule: RateLimitRule) -> tuple[bool, int]:
        """Check if request is allowed using Redis sliding window with Lua script for atomicity."""
        if not self.redis_client:
            await self.connect()
        
        now = time.time()
        
        # Determine effective limit (with burst tolerance if configured)
        effective_limit = rule.requests
        if rule.burst is not None:
            # Allow burst up to the specified amount
            effective_limit = min(rule.requests + rule.burst, rule.requests * 2)
        
        try:
            # Use Lua script for atomic operation
            result = await self.redis_client.evalsha(
                self._lua_script_sha,
                1,  # Number of keys
                key,  # Key
                rule.window,  # Window size
                effective_limit,  # Request limit
                now  # Current timestamp
            )
            
            allowed = bool(result[0])
            retry_after = int(result[1]) if result[1] > 0 else 0
            return allowed, retry_after
            
        except redis.exceptions.NoScriptError:
            # Script not loaded, reload and retry
            self._lua_script_sha = await self.redis_client.script_load(self._lua_script)
            return await self.is_allowed(key, rule)


class RateLimiter:
    """Main rate limiter with configurable backend and fallback support."""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.rules: Dict[str, RateLimitRule] = {}
        self._rule_cache: Dict[str, RateLimitRule] = {}  # Cache for computed rules
        self.redis_url = redis_url
        self._fallback_backend = MemoryRateLimiter()  # Fallback for Redis failures
        
        if redis_url:
            self.backend = RedisRateLimiter(redis_url)
        else:
            self.backend = MemoryRateLimiter()
    
    def add_rule(self, pattern: str, requests: int, window: int, burst: Optional[int] = None):
        """Add a rate limiting rule and invalidate cache."""
        self.rules[pattern] = RateLimitRule(requests, window, burst)
        # Clear cache when rules change to ensure consistency
        self._rule_cache.clear()
    
    def remove_rule(self, pattern: str):
        """Remove a rate limiting rule and invalidate cache."""
        if pattern in self.rules:
            del self.rules[pattern]
            # Clear cache when rules change
            self._rule_cache.clear()
    
    def clear_cache(self):
        """Manually clear the rule cache."""
        self._rule_cache.clear()
    
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
        """Get rate limiting rule for the current endpoint with caching."""
        path = request.url.path
        method = request.method
        cache_key = f"{method} {path}"
        
        # Check cache first
        if cache_key in self._rule_cache:
            return self._rule_cache[cache_key]
        
        # Find rule and cache it
        rule = self._compute_rule_for_endpoint(method, path)
        self._rule_cache[cache_key] = rule
        return rule
    
    def _compute_rule_for_endpoint(self, method: str, path: str) -> Optional[RateLimitRule]:
        """Compute rate limiting rule for endpoint (internal method)."""
        # Priority 1: Exact method + path match
        exact_key = f"{method} {path}"
        if exact_key in self.rules:
            return self.rules[exact_key]
        
        # Priority 2: Exact path match
        if path in self.rules:
            return self.rules[path]
        
        # Priority 3: Path prefix matches (longest first)
        path_patterns = [(pattern, rule) for pattern, rule in self.rules.items() 
                        if pattern.startswith('/') and path.startswith(pattern)]
        if path_patterns:
            # Sort by pattern length (longest first for most specific match)
            path_patterns.sort(key=lambda x: len(x[0]), reverse=True)
            return path_patterns[0][1]
        
        # Priority 4: Method-only matches
        if method in self.rules:
            return self.rules[method]
        
        # Priority 5: Default rule
        return self.rules.get('default')
    
    async def check_rate_limit(self, request: Request) -> Optional[JSONResponse]:
        """Check rate limit for the request with Redis fallback support."""
        rule = self.get_rule_for_endpoint(request)
        if not rule:
            return None
        
        client_key = self.get_client_key(request)
        endpoint_key = f"{client_key}:{request.url.path}"
        
        try:
            allowed, retry_after = await self.backend.is_allowed(endpoint_key, rule)
        except Exception as e:
            # Redis connection error - fallback to memory backend
            if self.redis_url:
                logger.warning(
                    f"Redis rate limiter failed, falling back to memory: {e}",
                    extra={"client_key": client_key, "path": request.url.path}
                )
                allowed, retry_after = await self._fallback_backend.is_allowed(endpoint_key, rule)
            else:
                # Re-raise if not a Redis backend
                raise
        
        if not allowed:
            # Security audit logging for rate limit violations
            user_id = getattr(request.state, 'user_id', None)
            ip_address = self._extract_ip_address(request)
            
            security_logger.warning(
                "Rate limit exceeded",
                extra={
                    "event": "rate_limit_exceeded",
                    "client_key": client_key,
                    "user_id": user_id,
                    "ip_address": ip_address,
                    "path": request.url.path,
                    "method": request.method,
                    "user_agent": request.headers.get("User-Agent", "unknown"),
                    "limit": rule.requests,
                    "window": rule.window,
                    "retry_after": retry_after,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
            
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
    
    def _extract_ip_address(self, request: Request) -> str:
        """Extract real IP address from request headers."""
        # Check forwarded headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to direct client IP
        return request.client.host if request.client else "unknown"


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


async def shutdown_rate_limiter():
    """Shutdown rate limiter and cleanup Redis connections."""
    global rate_limiter
    if rate_limiter and hasattr(rate_limiter.backend, 'disconnect'):
        await rate_limiter.backend.disconnect()
        rate_limiter = None


def _configure_default_rules(limiter: RateLimiter):
    """Configure default rate limiting rules using centralized configuration."""
    from core.config import settings
    
    # General API limits (from centralized config)
    limiter.add_rule('default', requests=settings.default_rate_limit, window=60)
    
    # Authentication endpoints (from centralized config, more restrictive)
    limiter.add_rule('POST /auth/login', requests=settings.auth_rate_limit, window=60)
    limiter.add_rule('POST /auth/register', requests=max(settings.auth_rate_limit - 2, 1), window=300)  # Even more restrictive for registration
    
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
    from core.config import settings
    
    # Bypass rate limiting if disabled
    if not settings.rate_limit_enabled:
        return await call_next(request)
    
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