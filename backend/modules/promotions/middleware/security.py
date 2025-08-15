# backend/modules/promotions/middleware/security.py

from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import hashlib
import hmac
import time
import logging
from datetime import datetime, timedelta

from core.database import get_db
from modules.promotions.services.cache_service import cache_service

logger = logging.getLogger(__name__)
security = HTTPBearer()


class PromotionSecurityMiddleware:
    """Security middleware for promotion endpoints"""

    def __init__(self):
        self.cache = cache_service

    def generate_request_signature(self, data: str, timestamp: str, secret: str) -> str:
        """Generate HMAC signature for request validation"""
        message = f"{timestamp}:{data}"
        return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

    def validate_request_signature(
        self,
        data: str,
        timestamp: str,
        signature: str,
        secret: str,
        max_age_seconds: int = 300,
    ) -> bool:
        """Validate request signature and timestamp"""
        try:
            # Check timestamp is within acceptable range
            request_time = datetime.fromtimestamp(float(timestamp))
            current_time = datetime.utcnow()

            if abs((current_time - request_time).total_seconds()) > max_age_seconds:
                logger.warning(f"Request timestamp too old: {timestamp}")
                return False

            # Validate signature
            expected_signature = self.generate_request_signature(
                data, timestamp, secret
            )

            # Use hmac.compare_digest to prevent timing attacks
            return hmac.compare_digest(signature, expected_signature)

        except Exception as e:
            logger.error(f"Error validating request signature: {e}")
            return False


def rate_limit_dependency(
    limit: int = 100, window_seconds: int = 3600, action: str = "api_request"
):
    """Dependency for rate limiting"""

    def rate_limiter(request: Request):
        # Get client identifier (IP + User-Agent for anonymous, user_id for authenticated)
        client_ip = request.client.host
        user_agent = request.headers.get("user-agent", "unknown")
        user_id = getattr(request.state, "user_id", None)

        if user_id:
            identifier = f"user:{user_id}"
        else:
            identifier = (
                f"ip:{client_ip}:{hashlib.md5(user_agent.encode()).hexdigest()[:8]}"
            )

        # Check rate limit
        rate_limit_result = cache_service.check_rate_limit(
            identifier=identifier,
            limit=limit,
            window_seconds=window_seconds,
            action=action,
        )

        if not rate_limit_result["allowed"]:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "retry_after": rate_limit_result.get("reset_time"),
                    "limit": limit,
                    "window_seconds": window_seconds,
                },
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": str(rate_limit_result["remaining"]),
                    "X-RateLimit-Reset": rate_limit_result.get("reset_time", ""),
                    "Retry-After": str(window_seconds),
                },
            )

        # Add rate limit headers to response
        request.state.rate_limit_headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(rate_limit_result["remaining"]),
            "X-RateLimit-Reset": rate_limit_result.get("reset_time", ""),
        }

        return rate_limit_result

    return rate_limiter


def coupon_rate_limit_dependency():
    """Strict rate limiting for coupon operations to prevent brute force"""
    return rate_limit_dependency(
        limit=10,  # Only 10 coupon operations per hour per client
        window_seconds=3600,
        action="coupon_operation",
    )


def discount_calculation_rate_limit():
    """Rate limiting for discount calculations"""
    return rate_limit_dependency(
        limit=50,  # 50 discount calculations per hour
        window_seconds=3600,
        action="discount_calculation",
    )


def bulk_operation_rate_limit():
    """Rate limiting for bulk operations"""
    return rate_limit_dependency(
        limit=5,  # Only 5 bulk operations per hour
        window_seconds=3600,
        action="bulk_operation",
    )


class IdempotencyMiddleware:
    """Middleware to ensure idempotent operations"""

    def __init__(self):
        self.cache = cache_service

    def get_idempotency_key(self, request: Request) -> Optional[str]:
        """Extract idempotency key from request headers"""
        return request.headers.get("Idempotency-Key")

    def check_idempotency(
        self, idempotency_key: str, request_hash: str, ttl: int = 3600
    ) -> Optional[Dict[str, Any]]:
        """Check if request has been processed before"""
        cache_key = f"idempotency:{idempotency_key}"

        cached_result = self.cache.get(cache_key)
        if cached_result:
            # Verify request hasn't changed
            if cached_result.get("request_hash") == request_hash:
                return cached_result.get("response")
            else:
                # Same idempotency key but different request - this is an error
                raise HTTPException(
                    status_code=422,
                    detail="Idempotency key reused with different request parameters",
                )

        return None

    def store_idempotent_result(
        self,
        idempotency_key: str,
        request_hash: str,
        response: Dict[str, Any],
        ttl: int = 3600,
    ):
        """Store result for idempotency checking"""
        cache_key = f"idempotency:{idempotency_key}"
        cache_data = {
            "request_hash": request_hash,
            "response": response,
            "created_at": datetime.utcnow().isoformat(),
        }

        self.cache.set(cache_key, cache_data, ttl)

    def generate_request_hash(self, request_data: Any) -> str:
        """Generate hash of request data for comparison"""
        import json

        request_str = json.dumps(request_data, sort_keys=True, default=str)
        return hashlib.sha256(request_str.encode()).hexdigest()


def idempotency_dependency():
    """Dependency for idempotent operations"""
    idempotency_middleware = IdempotencyMiddleware()

    def check_idempotency(request: Request, idempotency_key: Optional[str] = None):
        if not idempotency_key:
            # Idempotency is optional - generate from request if not provided
            return None

        # For POST/PUT requests, include body in hash
        request_data = {
            "method": request.method,
            "url": str(request.url),
            "headers": dict(request.headers),
        }

        # Note: In real implementation, you'd need to capture request body
        # This is a simplified version
        request_hash = idempotency_middleware.generate_request_hash(request_data)

        # Check if we've seen this request before
        cached_response = idempotency_middleware.check_idempotency(
            idempotency_key, request_hash
        )

        if cached_response:
            # Return cached response
            return cached_response

        # Store middleware instance for later use
        request.state.idempotency_middleware = idempotency_middleware
        request.state.idempotency_key = idempotency_key
        request.state.request_hash = request_hash

        return None

    return check_idempotency


def validate_json_input(max_size: int = 1024 * 1024):  # 1MB default
    """Validate JSON input size and structure"""

    def validator(request: Request):
        content_length = request.headers.get("content-length")

        if content_length:
            if int(content_length) > max_size:
                raise HTTPException(
                    status_code=413,
                    detail=f"Request body too large. Maximum size: {max_size} bytes",
                )

        return True

    return validator


def validate_promotion_access(
    promotion_id: int,
    db: Session = Depends(get_db),
    current_user=None,  # Would depend on your auth system
):
    """Validate user has access to promotion"""
    from modules.promotions.models.promotion_models import Promotion

    promotion = db.query(Promotion).filter(Promotion.id == promotion_id).first()
    if not promotion:
        raise HTTPException(status_code=404, detail="Promotion not found")

    # Add access control logic here based on your requirements
    # For example, check if user owns the promotion or has admin rights

    return promotion


class SecurityHeaders:
    """Security headers for promotion API responses"""

    @staticmethod
    def add_security_headers(response):
        """Add security headers to response"""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"

        return response


def audit_log_dependency():
    """Dependency to log sensitive operations"""

    def audit_logger(request: Request):
        # Log sensitive operations for audit trail
        sensitive_paths = ["/promotions/", "/coupons/", "/referrals/", "/ab-testing/"]

        path = request.url.path
        if any(sensitive_path in path for sensitive_path in sensitive_paths):
            audit_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "method": request.method,
                "path": path,
                "client_ip": request.client.host,
                "user_agent": request.headers.get("user-agent"),
                "user_id": getattr(request.state, "user_id", None),
            }

            # In production, this would go to a secure audit log system
            logger.info(f"AUDIT: {audit_data}")

        return True

    return audit_logger


def sanitize_input(input_data: Any) -> Any:
    """Sanitize input data to prevent injection attacks"""
    if isinstance(input_data, str):
        # Remove potentially dangerous characters
        dangerous_chars = ["<", ">", "&", '"', "'", "/", "\\"]
        for char in dangerous_chars:
            input_data = input_data.replace(char, "")

        # Limit string length
        if len(input_data) > 1000:
            input_data = input_data[:1000]

    elif isinstance(input_data, dict):
        return {k: sanitize_input(v) for k, v in input_data.items()}

    elif isinstance(input_data, list):
        return [sanitize_input(item) for item in input_data]

    return input_data


def validate_coupon_code_format(coupon_code: str) -> bool:
    """Validate coupon code format to prevent injection"""
    import re

    # Only allow alphanumeric characters and common safe symbols
    pattern = r"^[A-Z0-9\-_]{3,20}$"

    if not re.match(pattern, coupon_code):
        raise HTTPException(
            status_code=400,
            detail="Invalid coupon code format. Only alphanumeric characters, hyphens, and underscores allowed.",
        )

    return True


def prevent_timing_attacks():
    """Add consistent delay to prevent timing-based attacks"""
    import time
    import random

    def timing_protector():
        # Add small random delay (10-50ms) to prevent timing analysis
        delay = random.uniform(0.01, 0.05)
        time.sleep(delay)
        return True

    return timing_protector


class PromotionSecurityConfig:
    """Security configuration for promotion system"""

    # Rate limiting configurations
    RATE_LIMITS = {
        "coupon_validation": {"limit": 10, "window": 3600},
        "discount_calculation": {"limit": 50, "window": 3600},
        "bulk_operations": {"limit": 5, "window": 3600},
        "api_requests": {"limit": 100, "window": 3600},
    }

    # Security settings
    MAX_REQUEST_SIZE = 1024 * 1024  # 1MB
    IDEMPOTENCY_TTL = 3600  # 1 hour
    SIGNATURE_MAX_AGE = 300  # 5 minutes

    # Validation rules
    MAX_COUPON_CODE_LENGTH = 20
    MAX_PROMOTION_NAME_LENGTH = 200
    MAX_BULK_OPERATION_SIZE = 10000

    # Audit settings
    LOG_SENSITIVE_OPERATIONS = True
    REQUIRE_IDEMPOTENCY_FOR_MUTATIONS = True

    @classmethod
    def get_rate_limit_config(cls, operation: str) -> Dict[str, int]:
        """Get rate limit configuration for operation"""
        return cls.RATE_LIMITS.get(operation, cls.RATE_LIMITS["api_requests"])
