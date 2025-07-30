# backend/modules/analytics/middleware/__init__.py

"""
Middleware for analytics module.
"""

from .rate_limiter import rate_limit, rate_limit_middleware

__all__ = ["rate_limit", "rate_limit_middleware"]