"""
Enhanced rate limiting for authentication endpoints.

Provides specialized rate limiting for auth endpoints with:
- Per-IP and per-user rate limiting
- Exponential backoff for repeated failures
- Distributed rate limiting using Redis
"""

import time
import hashlib
import logging
from typing import Optional, Tuple
from datetime import datetime, timedelta
from fastapi import Request, HTTPException
import redis.asyncio as redis

from .security_config import RATE_LIMIT_CONFIG, IS_PRODUCTION
from .audit_logger import audit_logger

logger = logging.getLogger(__name__)


class AuthRateLimiter:
    """
    Enhanced rate limiter for authentication endpoints.
    
    Features:
    - Per-IP rate limiting
    - Per-user rate limiting
    - Failed attempt tracking with exponential backoff
    - Distributed rate limiting using Redis
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or "redis://localhost:6379/1"
        self.redis_client = None
        self.config = RATE_LIMIT_CONFIG["auth_endpoints"]
        
        # Failed attempt multipliers for exponential backoff
        self.backoff_multipliers = {
            1: 1,     # First failure: normal rate
            2: 2,     # Second failure: 2x wait
            3: 4,     # Third failure: 4x wait
            4: 8,     # Fourth failure: 8x wait
            5: 16,    # Fifth+ failures: 16x wait
        }
    
    async def initialize(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Auth rate limiter initialized with Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis for rate limiting: {e}")
            # Continue without Redis (degraded mode)
    
    async def check_rate_limit(
        self,
        request: Request,
        endpoint: str,
        user_identifier: Optional[str] = None
    ) -> Tuple[bool, Optional[int]]:
        """
        Check if request should be rate limited.
        
        Args:
            request: FastAPI request object
            endpoint: The endpoint being accessed (login, register, etc)
            user_identifier: Optional user identifier (username, email)
            
        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        # Get client IP
        client_ip = self._get_client_ip(request)
        
        # Get rate limit configuration for endpoint
        limit_config = self.config.get(endpoint, self.config.get("default"))
        if not limit_config:
            return True, None  # No rate limit configured
        
        max_requests = limit_config["requests"]
        window_seconds = limit_config["window"]
        
        # Check IP-based rate limit
        ip_key = f"auth_rate:{endpoint}:ip:{client_ip}"
        ip_allowed, ip_retry_after = await self._check_limit(
            ip_key, max_requests, window_seconds
        )
        
        if not ip_allowed:
            # Log rate limit violation
            await audit_logger.log_security_event(
                event_type="auth_rate_limit_exceeded",
                severity="medium",
                description=f"Rate limit exceeded for {endpoint} from IP {client_ip}",
                client_ip=client_ip,
                metadata={"endpoint": endpoint, "limit_type": "ip"}
            )
            return False, ip_retry_after
        
        # Check user-based rate limit if identifier provided
        if user_identifier:
            user_key = f"auth_rate:{endpoint}:user:{self._hash_identifier(user_identifier)}"
            user_allowed, user_retry_after = await self._check_limit(
                user_key, max_requests, window_seconds
            )
            
            if not user_allowed:
                # Log rate limit violation
                await audit_logger.log_security_event(
                    event_type="auth_rate_limit_exceeded",
                    severity="medium",
                    description=f"Rate limit exceeded for {endpoint} for user",
                    client_ip=client_ip,
                    metadata={"endpoint": endpoint, "limit_type": "user"}
                )
                return False, user_retry_after
        
        return True, None
    
    async def record_failed_attempt(
        self,
        request: Request,
        endpoint: str,
        user_identifier: Optional[str] = None
    ):
        """
        Record a failed authentication attempt.
        
        This increases the backoff period for subsequent attempts.
        """
        client_ip = self._get_client_ip(request)
        
        # Track failed attempts by IP
        ip_failure_key = f"auth_failures:{endpoint}:ip:{client_ip}"
        ip_failures = await self._increment_failures(ip_failure_key)
        
        # Track failed attempts by user if identifier provided
        user_failures = 0
        if user_identifier:
            user_failure_key = f"auth_failures:{endpoint}:user:{self._hash_identifier(user_identifier)}"
            user_failures = await self._increment_failures(user_failure_key)
        
        # Log security event for multiple failures
        max_failures = max(ip_failures, user_failures)
        if max_failures >= 3:
            severity = "high" if max_failures >= 5 else "medium"
            await audit_logger.log_security_event(
                event_type="repeated_auth_failures",
                severity=severity,
                description=f"Multiple failed {endpoint} attempts ({max_failures} failures)",
                client_ip=client_ip,
                metadata={
                    "endpoint": endpoint,
                    "ip_failures": ip_failures,
                    "user_failures": user_failures
                }
            )
    
    async def record_successful_attempt(
        self,
        request: Request,
        endpoint: str,
        user_identifier: Optional[str] = None
    ):
        """
        Record a successful authentication attempt.
        
        This resets the failure counter.
        """
        client_ip = self._get_client_ip(request)
        
        # Clear failure counters
        if self.redis_client:
            try:
                # Clear IP failures
                ip_failure_key = f"auth_failures:{endpoint}:ip:{client_ip}"
                await self.redis_client.delete(ip_failure_key)
                
                # Clear user failures if identifier provided
                if user_identifier:
                    user_failure_key = f"auth_failures:{endpoint}:user:{self._hash_identifier(user_identifier)}"
                    await self.redis_client.delete(user_failure_key)
            except Exception as e:
                logger.error(f"Failed to clear failure counters: {e}")
    
    async def _check_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> Tuple[bool, Optional[int]]:
        """Check rate limit for a specific key."""
        if not self.redis_client:
            # Degraded mode - allow all requests
            return True, None
        
        try:
            # Get current request count
            current = await self.redis_client.get(key)
            current_count = int(current) if current else 0
            
            # Check for failed attempts (affects rate limit)
            failure_key = key.replace("auth_rate:", "auth_failures:")
            failures = await self.redis_client.get(failure_key)
            failure_count = int(failures) if failures else 0
            
            # Apply backoff multiplier based on failures
            multiplier = self.backoff_multipliers.get(
                min(failure_count, 5), 
                self.backoff_multipliers[5]
            )
            effective_window = window_seconds * multiplier
            
            # Check if limit exceeded
            if current_count >= max_requests:
                # Get TTL for retry-after header
                ttl = await self.redis_client.ttl(key)
                return False, max(ttl, 1)
            
            # Increment counter
            pipe = self.redis_client.pipeline()
            pipe.incr(key)
            pipe.expire(key, effective_window)
            await pipe.execute()
            
            return True, None
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # On error, fail open in development, fail closed in production
            return not IS_PRODUCTION, None
    
    async def _increment_failures(self, key: str) -> int:
        """Increment failure counter and return new count."""
        if not self.redis_client:
            return 0
        
        try:
            # Increment with 24-hour expiry
            pipe = self.redis_client.pipeline()
            pipe.incr(key)
            pipe.expire(key, 86400)  # 24 hours
            results = await pipe.execute()
            return results[0]  # Return new count
        except Exception as e:
            logger.error(f"Failed to increment failure counter: {e}")
            return 0
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        # Check forwarded headers
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        
        # Fallback to direct connection
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _hash_identifier(self, identifier: str) -> str:
        """Hash user identifier for privacy."""
        return hashlib.sha256(identifier.encode()).hexdigest()[:16]


# Dependency for FastAPI routes
async def check_auth_rate_limit(
    request: Request,
    endpoint: str,
    user_identifier: Optional[str] = None
):
    """
    FastAPI dependency to check authentication rate limits.
    
    Usage:
        @app.post("/login")
        async def login(
            request: Request,
            _: None = Depends(lambda req: check_auth_rate_limit(req, "login"))
        ):
            ...
    """
    # Get rate limiter from app state
    rate_limiter: AuthRateLimiter = request.app.state.auth_rate_limiter
    
    # Check rate limit
    allowed, retry_after = await rate_limiter.check_rate_limit(
        request, endpoint, user_identifier
    )
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": str(retry_after)} if retry_after else None
        )