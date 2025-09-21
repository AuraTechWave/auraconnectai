"""Compatibility wrapper for rate limiting utilities."""

from core.rate_limiting import rate_limit, RateLimiter, RateLimitMiddleware  # noqa: F401

__all__ = ["rate_limit", "RateLimiter", "RateLimitMiddleware"]
