"""Rate Limiting Module for AuraConnect API

This module provides comprehensive rate limiting functionality using Redis as a backend.
It supports IP-based and user-based rate limiting with configurable limits per endpoint.
"""

import time
import hashlib
import logging
from typing import Optional, Dict, Any, Tuple, Union, Callable
from datetime import datetime, timedelta
from functools import wraps
from enum import Enum

import redis
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from core.config import get_settings

logger = logging.getLogger(__name__)


class RateLimitType(Enum):
    """Types of rate limiting"""
    IP_BASED = "ip"
    USER_BASED = "user"
    COMBINED = "combined"  # Both IP and user limits apply


class RateLimitConfig:
    """Configuration for rate limits"""
    
    # Default limits (requests per minute)
    DEFAULT_ANONYMOUS_LIMIT = 60  # 1 request per second for anonymous users
    DEFAULT_AUTHENTICATED_LIMIT = 300  # 5 requests per second for authenticated users
    DEFAULT_ADMIN_LIMIT = 0  # Unlimited for admins (0 means no limit)
    
    # Specific endpoint limits (override defaults)
    ENDPOINT_LIMITS = {
        # Auth endpoints - more restrictive
        "/api/v1/auth/login": {"anonymous": 5, "authenticated": 10, "window": 60},
        "/api/v1/auth/register": {"anonymous": 3, "authenticated": 5, "window": 60},
        "/api/v1/auth/password/reset": {"anonymous": 3, "authenticated": 5, "window": 60},
        
        # Analytics endpoints - expensive operations
        "/api/v1/analytics/sales-report": {"anonymous": 0, "authenticated": 30, "window": 60},
        "/api/v1/analytics/ai-insights": {"anonymous": 0, "authenticated": 10, "window": 60},
        "/api/v1/analytics/export": {"anonymous": 0, "authenticated": 5, "window": 60},
        
        # Order endpoints - high traffic allowed
        "/api/v1/orders": {"anonymous": 0, "authenticated": 600, "window": 60},
        "/api/v1/orders/create": {"anonymous": 0, "authenticated": 120, "window": 60},
        
        # Menu endpoints - read-heavy, allow more
        "/api/v1/menu": {"anonymous": 120, "authenticated": 600, "window": 60},
        "/api/v1/menu/recommendations": {"anonymous": 30, "authenticated": 180, "window": 60},
        
        # Webhook endpoints - special handling
        "/api/v1/webhooks": {"anonymous": 100, "authenticated": 500, "window": 60},
    }
    
    # Burst allowance (temporary spike handling)
    BURST_MULTIPLIER = 1.5  # Allow 50% more requests in burst
    BURST_WINDOW = 10  # seconds
    
    # Penalty for violations
    VIOLATION_PENALTY_MINUTES = 5  # Block for 5 minutes after repeated violations
    VIOLATION_THRESHOLD = 3  # Number of violations before penalty


class RateLimiter:
    """Core rate limiting implementation using Redis"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """Initialize rate limiter with Redis connection"""
        self.redis_client = redis_client or self._get_redis_client()
        self.config = RateLimitConfig()
        
    def _get_redis_client(self) -> redis.Redis:
        """Get Redis client from settings"""
        settings = get_settings()
        return redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True
        )
    
    def _get_key(self, identifier: str, endpoint: str, window: int) -> str:
        """Generate Redis key for rate limiting"""
        # Use sliding window timestamp to create time-based buckets
        window_start = int(time.time() // window) * window
        return f"rate_limit:{endpoint}:{identifier}:{window_start}"
    
    def _get_violation_key(self, identifier: str) -> str:
        """Generate Redis key for tracking violations"""
        return f"rate_limit:violations:{identifier}"
    
    def check_rate_limit(
        self,
        identifier: str,
        endpoint: str,
        limit: int,
        window: int = 60,
        identifier_type: str = "ip"
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limit
        
        Args:
            identifier: IP address or user ID
            endpoint: API endpoint path
            limit: Maximum requests allowed
            window: Time window in seconds
            identifier_type: Type of identifier (ip/user)
            
        Returns:
            Tuple of (allowed, metadata)
        """
        
        if limit == 0:  # No limit (admin bypass)
            return True, {
                "limit": "unlimited",
                "remaining": "unlimited",
                "reset": None
            }
        
        try:
            # Check if identifier is blocked due to violations
            if self._is_blocked(identifier):
                return False, {
                    "limit": limit,
                    "remaining": 0,
                    "reset": self._get_block_expiry(identifier),
                    "blocked": True
                }
            
            key = self._get_key(identifier, endpoint, window)
            pipe = self.redis_client.pipeline()
            
            # Increment counter
            pipe.incr(key)
            pipe.expire(key, window)
            results = pipe.execute()
            
            current_count = results[0]
            
            # Calculate metadata
            window_start = int(time.time() // window) * window
            reset_time = window_start + window
            remaining = max(0, limit - current_count)
            
            metadata = {
                "limit": limit,
                "remaining": remaining,
                "reset": reset_time,
                "current": current_count
            }
            
            # Check if over limit
            if current_count > limit:
                # Track violation
                self._track_violation(identifier)
                
                # Check burst allowance
                if self._check_burst_allowance(identifier, endpoint, limit):
                    metadata["burst"] = True
                    return True, metadata
                
                return False, metadata
            
            return True, metadata
            
        except redis.RedisError as e:
            logger.error(f"Redis error in rate limiting: {e}")
            # Fail open on Redis errors (allow request)
            return True, {"error": "Rate limiting unavailable"}
    
    def _check_burst_allowance(self, identifier: str, endpoint: str, base_limit: int) -> bool:
        """Check if request can be allowed under burst conditions"""
        burst_key = f"rate_limit:burst:{endpoint}:{identifier}"
        burst_limit = int(base_limit * self.config.BURST_MULTIPLIER)
        
        try:
            pipe = self.redis_client.pipeline()
            pipe.incr(burst_key)
            pipe.expire(burst_key, self.config.BURST_WINDOW)
            results = pipe.execute()
            
            burst_count = results[0]
            return burst_count <= burst_limit
            
        except redis.RedisError:
            return False
    
    def _track_violation(self, identifier: str):
        """Track rate limit violations"""
        violation_key = self._get_violation_key(identifier)
        
        try:
            pipe = self.redis_client.pipeline()
            pipe.incr(violation_key)
            pipe.expire(violation_key, 3600)  # Track violations for 1 hour
            results = pipe.execute()
            
            violation_count = results[0]
            
            # Block identifier if threshold exceeded
            if violation_count >= self.config.VIOLATION_THRESHOLD:
                self._block_identifier(identifier)
                
        except redis.RedisError as e:
            logger.error(f"Error tracking violation: {e}")
    
    def _block_identifier(self, identifier: str):
        """Block an identifier for penalty period"""
        block_key = f"rate_limit:blocked:{identifier}"
        try:
            self.redis_client.setex(
                block_key,
                timedelta(minutes=self.config.VIOLATION_PENALTY_MINUTES),
                "blocked"
            )
            logger.warning(f"Blocked identifier {identifier} for {self.config.VIOLATION_PENALTY_MINUTES} minutes")
        except redis.RedisError as e:
            logger.error(f"Error blocking identifier: {e}")
    
    def _is_blocked(self, identifier: str) -> bool:
        """Check if identifier is blocked"""
        block_key = f"rate_limit:blocked:{identifier}"
        try:
            return self.redis_client.exists(block_key) > 0
        except redis.RedisError:
            return False
    
    def _get_block_expiry(self, identifier: str) -> Optional[int]:
        """Get block expiry timestamp"""
        block_key = f"rate_limit:blocked:{identifier}"
        try:
            ttl = self.redis_client.ttl(block_key)
            if ttl > 0:
                return int(time.time()) + ttl
            return None
        except redis.RedisError:
            return None
    
    def reset_limits(self, identifier: str, endpoint: Optional[str] = None):
        """Reset rate limits for an identifier"""
        try:
            if endpoint:
                # Reset specific endpoint
                pattern = f"rate_limit:{endpoint}:{identifier}:*"
            else:
                # Reset all endpoints for identifier
                pattern = f"rate_limit:*:{identifier}:*"
            
            # Also clear violations and blocks
            violation_key = self._get_violation_key(identifier)
            block_key = f"rate_limit:blocked:{identifier}"
            
            pipe = self.redis_client.pipeline()
            
            # Delete rate limit keys
            for key in self.redis_client.scan_iter(match=pattern):
                pipe.delete(key)
            
            # Delete violation and block keys
            pipe.delete(violation_key)
            pipe.delete(block_key)
            
            pipe.execute()
            
        except redis.RedisError as e:
            logger.error(f"Error resetting limits: {e}")
    
    def get_rate_limit_headers(self, metadata: Dict[str, Any]) -> Dict[str, str]:
        """Generate rate limit headers for response"""
        headers = {}
        
        if "limit" in metadata:
            headers["X-RateLimit-Limit"] = str(metadata["limit"])
        
        if "remaining" in metadata:
            headers["X-RateLimit-Remaining"] = str(metadata["remaining"])
        
        if "reset" in metadata and metadata["reset"]:
            headers["X-RateLimit-Reset"] = str(metadata["reset"])
        
        if metadata.get("blocked"):
            headers["X-RateLimit-Blocked"] = "true"
        
        return headers


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting"""
    
    def __init__(self, app, rate_limiter: Optional[RateLimiter] = None):
        super().__init__(app)
        self.rate_limiter = rate_limiter or RateLimiter()
        self.config = RateLimitConfig()
    
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request with rate limiting"""
        
        # Skip rate limiting for health checks and docs
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)
        
        # Get identifier (IP address or user ID)
        identifier, identifier_type = self._get_identifier(request)
        
        # Get rate limit for endpoint
        limit_config = self._get_endpoint_limit(request.url.path, identifier_type)
        
        # Check rate limit
        allowed, metadata = self.rate_limiter.check_rate_limit(
            identifier=identifier,
            endpoint=request.url.path,
            limit=limit_config["limit"],
            window=limit_config["window"],
            identifier_type=identifier_type
        )
        
        if not allowed:
            # Log rate limit violation
            logger.warning(
                f"Rate limit exceeded for {identifier} on {request.url.path} "
                f"(current: {metadata.get('current')}, limit: {metadata.get('limit')})"
            )
            
            # Return 429 response with headers
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": metadata.get("reset", 60)
                },
                headers=self._get_rate_limit_headers(metadata)
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        for key, value in self._get_rate_limit_headers(metadata).items():
            response.headers[key] = value
        
        return response
    
    def _get_identifier(self, request: Request) -> Tuple[str, str]:
        """Get identifier from request (IP or user ID)"""
        
        # Try to get user ID from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            # Check if user is admin
            user_role = getattr(request.state, "user_role", None)
            if user_role == "admin":
                return f"admin:{user_id}", "admin"
            return f"user:{user_id}", "user"
        
        # Fall back to IP address
        client_ip = request.client.host if request.client else "unknown"
        
        # Check for X-Forwarded-For header (proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Get the first IP in the chain
            client_ip = forwarded_for.split(",")[0].strip()
        
        return f"ip:{client_ip}", "ip"
    
    def _get_endpoint_limit(self, path: str, identifier_type: str) -> Dict[str, Any]:
        """Get rate limit configuration for endpoint"""
        
        # Check for exact match
        if path in self.config.ENDPOINT_LIMITS:
            config = self.config.ENDPOINT_LIMITS[path]
        else:
            # Check for pattern match (e.g., /api/v1/orders/*)
            config = None
            for pattern, limit_config in self.config.ENDPOINT_LIMITS.items():
                if path.startswith(pattern.rstrip("*")):
                    config = limit_config
                    break
        
        if config:
            if identifier_type == "admin":
                limit = self.config.DEFAULT_ADMIN_LIMIT
            elif identifier_type == "user":
                limit = config.get("authenticated", self.config.DEFAULT_AUTHENTICATED_LIMIT)
            else:
                limit = config.get("anonymous", self.config.DEFAULT_ANONYMOUS_LIMIT)
            
            return {
                "limit": limit,
                "window": config.get("window", 60)
            }
        
        # Use defaults
        if identifier_type == "admin":
            limit = self.config.DEFAULT_ADMIN_LIMIT
        elif identifier_type == "user":
            limit = self.config.DEFAULT_AUTHENTICATED_LIMIT
        else:
            limit = self.config.DEFAULT_ANONYMOUS_LIMIT
        
        return {"limit": limit, "window": 60}
    
    def _get_rate_limit_headers(self, metadata: Dict[str, Any]) -> Dict[str, str]:
        """Generate rate limit headers for response"""
        headers = {}
        
        if "limit" in metadata:
            headers["X-RateLimit-Limit"] = str(metadata["limit"])
        
        if "remaining" in metadata:
            headers["X-RateLimit-Remaining"] = str(metadata["remaining"])
        
        if "reset" in metadata and metadata["reset"]:
            headers["X-RateLimit-Reset"] = str(metadata["reset"])
        
        if metadata.get("blocked"):
            headers["X-RateLimit-Blocked"] = "true"
        
        return headers


def rate_limit(
    requests: int = 60,
    window: int = 60,
    key_func: Optional[Callable] = None,
    bypass_admin: bool = True
):
    """
    Decorator for applying rate limits to specific endpoints
    
    Args:
        requests: Maximum number of requests allowed
        window: Time window in seconds
        key_func: Function to generate rate limit key
        bypass_admin: Whether to bypass rate limiting for admin users
    """
    
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Initialize rate limiter
            rate_limiter = RateLimiter()
            
            # Get identifier
            if key_func:
                identifier = key_func(request)
            else:
                # Default to IP or user ID
                user_id = getattr(request.state, "user_id", None)
                if user_id:
                    # Check admin bypass
                    if bypass_admin:
                        user_role = getattr(request.state, "user_role", None)
                        if user_role == "admin":
                            # No rate limiting for admins
                            return await func(request, *args, **kwargs)
                    identifier = f"user:{user_id}"
                else:
                    client_ip = request.client.host if request.client else "unknown"
                    identifier = f"ip:{client_ip}"
            
            # Check rate limit
            allowed, metadata = rate_limiter.check_rate_limit(
                identifier=identifier,
                endpoint=request.url.path,
                limit=requests,
                window=window
            )
            
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                    headers=rate_limiter.get_rate_limit_headers(metadata)
                )
            
            # Add headers to response
            response = await func(request, *args, **kwargs)
            if isinstance(response, Response):
                for key, value in rate_limiter.get_rate_limit_headers(metadata).items():
                    response.headers[key] = value
            
            return response
        
        return wrapper
    return decorator


class RateLimitMonitor:
    """Monitor and alert on rate limiting events"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client or self._get_redis_client()
        
    def _get_redis_client(self) -> redis.Redis:
        """Get Redis client from settings"""
        settings = get_settings()
        return redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True
        )
    
    def log_violation(self, identifier: str, endpoint: str, metadata: Dict[str, Any]):
        """Log rate limit violation for monitoring"""
        
        violation_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "identifier": identifier,
            "endpoint": endpoint,
            "metadata": metadata
        }
        
        # Store in Redis for real-time monitoring
        key = f"rate_limit:monitor:violations:{datetime.utcnow().strftime('%Y%m%d')}"
        try:
            self.redis_client.lpush(key, str(violation_data))
            self.redis_client.expire(key, 86400 * 7)  # Keep for 7 days
        except redis.RedisError as e:
            logger.error(f"Error logging violation: {e}")
        
        # Check for alert conditions
        self._check_alerts(identifier, endpoint)
    
    def _check_alerts(self, identifier: str, endpoint: str):
        """Check if alerts should be triggered"""
        
        # Count recent violations
        try:
            pattern = f"rate_limit:monitor:violations:*"
            violation_count = 0
            
            for key in self.redis_client.scan_iter(match=pattern, count=100):
                violations = self.redis_client.lrange(key, 0, -1)
                for v in violations:
                    if identifier in v:
                        violation_count += 1
            
            # Alert thresholds
            if violation_count > 100:
                self._send_alert(
                    f"High rate limit violations from {identifier}: {violation_count} in last 24h",
                    severity="high"
                )
            elif violation_count > 50:
                self._send_alert(
                    f"Moderate rate limit violations from {identifier}: {violation_count} in last 24h",
                    severity="medium"
                )
                
        except redis.RedisError as e:
            logger.error(f"Error checking alerts: {e}")
    
    def _send_alert(self, message: str, severity: str = "medium"):
        """Send alert (implement based on alerting system)"""
        logger.warning(f"RATE LIMIT ALERT [{severity}]: {message}")
        # TODO: Integrate with actual alerting system (email, Slack, PagerDuty, etc.)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get rate limiting statistics"""
        
        try:
            stats = {
                "total_violations_today": 0,
                "blocked_identifiers": [],
                "top_violators": [],
                "endpoint_violations": {}
            }
            
            # Count violations today
            today_key = f"rate_limit:monitor:violations:{datetime.utcnow().strftime('%Y%m%d')}"
            stats["total_violations_today"] = self.redis_client.llen(today_key)
            
            # Get blocked identifiers
            for key in self.redis_client.scan_iter(match="rate_limit:blocked:*", count=100):
                identifier = key.split(":")[-1]
                ttl = self.redis_client.ttl(key)
                stats["blocked_identifiers"].append({
                    "identifier": identifier,
                    "expires_in": ttl
                })
            
            return stats
            
        except redis.RedisError as e:
            logger.error(f"Error getting statistics: {e}")
            return {}