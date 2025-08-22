"""
Production security configuration and hardening utilities.

This module provides centralized security configuration for the application,
including debug endpoint protection, security headers, and production-safe defaults.
"""

import os
from typing import Dict, List, Optional, Set
from functools import wraps
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

# Security configuration based on environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
IS_PRODUCTION = ENVIRONMENT == "production"
IS_STAGING = ENVIRONMENT == "staging"
IS_DEVELOPMENT = ENVIRONMENT == "development"

# Debug endpoint configuration
DEBUG_ENDPOINTS_ENABLED = os.getenv("DEBUG_ENDPOINTS_ENABLED", "false").lower() == "true"
DEBUG_ENDPOINTS_WHITELIST = set(os.getenv("DEBUG_ENDPOINTS_WHITELIST", "").split(",")) if os.getenv("DEBUG_ENDPOINTS_WHITELIST") else set()

# Security headers configuration
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}

# CSP configuration for production
if IS_PRODUCTION:
    SECURITY_HEADERS["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://api.auraconnect.ai wss://api.auraconnect.ai; "
        "frame-ancestors 'none';"
    )

# HSTS configuration for production
if IS_PRODUCTION or IS_STAGING:
    SECURITY_HEADERS["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

# Rate limiting configuration
RATE_LIMIT_CONFIG = {
    "auth_endpoints": {
        "login": {"requests": 5, "window": 300},  # 5 requests per 5 minutes
        "register": {"requests": 3, "window": 3600},  # 3 requests per hour
        "password_reset": {"requests": 3, "window": 3600},  # 3 requests per hour
        "refresh_token": {"requests": 10, "window": 600},  # 10 requests per 10 minutes
    },
    "api_endpoints": {
        "default": {"requests": 100, "window": 60},  # 100 requests per minute
        "heavy": {"requests": 10, "window": 60},  # 10 requests per minute for heavy endpoints
    }
}

# Webhook signature configuration
WEBHOOK_SIGNATURE_REQUIRED = IS_PRODUCTION or IS_STAGING
WEBHOOK_SIGNATURE_HEADER = "X-Webhook-Signature"
WEBHOOK_TIMESTAMP_HEADER = "X-Webhook-Timestamp"
WEBHOOK_TIMESTAMP_TOLERANCE = 300  # 5 minutes

# API versioning security
DEPRECATED_API_VERSIONS: Set[str] = {"v1"}  # Versions to warn about
DISABLED_API_VERSIONS: Set[str] = set()  # Versions to block completely

# Audit logging configuration
AUDIT_LOG_ENABLED = IS_PRODUCTION or IS_STAGING
AUDIT_LOG_SENSITIVE_OPERATIONS = {
    "user_create",
    "user_delete",
    "user_role_change",
    "payment_process",
    "payment_refund",
    "payroll_process",
    "payroll_export",
    "settings_update",
    "webhook_config_change",
    "data_export",
    "data_import",
}


def protect_debug_endpoint(allowed_envs: Optional[List[str]] = None):
    """
    Decorator to protect debug endpoints in production.
    
    Args:
        allowed_envs: List of environments where the endpoint is allowed.
                     Defaults to ["development"] if not specified.
    """
    if allowed_envs is None:
        allowed_envs = ["development"]
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Check if we're in an allowed environment
            if ENVIRONMENT not in allowed_envs:
                # Check if debug endpoints are explicitly enabled
                if not DEBUG_ENDPOINTS_ENABLED:
                    raise HTTPException(status_code=404, detail="Not found")
                
                # Check if the specific endpoint is whitelisted
                endpoint_name = func.__name__
                if endpoint_name not in DEBUG_ENDPOINTS_WHITELIST:
                    raise HTTPException(status_code=404, detail="Not found")
            
            # Execute the original function
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def apply_security_headers(response: JSONResponse) -> JSONResponse:
    """Apply security headers to a response."""
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value
    return response


def get_client_ip(request: Request) -> str:
    """
    Get the client's IP address, handling proxy headers.
    
    Args:
        request: The FastAPI request object
        
    Returns:
        The client's IP address
    """
    # Check X-Forwarded-For header (common proxy header)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain
        return forwarded_for.split(",")[0].strip()
    
    # Check X-Real-IP header (nginx proxy header)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fall back to direct connection IP
    if request.client:
        return request.client.host
    
    return "unknown"


def sanitize_log_data(data: Dict) -> Dict:
    """
    Sanitize sensitive data before logging.
    
    Args:
        data: Dictionary containing log data
        
    Returns:
        Sanitized dictionary safe for logging
    """
    sensitive_fields = {
        "password", "token", "secret", "api_key", "credit_card",
        "ssn", "social_security", "bank_account", "routing_number"
    }
    
    sanitized = {}
    for key, value in data.items():
        # Check if field name contains sensitive keywords
        if any(sensitive in key.lower() for sensitive in sensitive_fields):
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, dict):
            # Recursively sanitize nested dictionaries
            sanitized[key] = sanitize_log_data(value)
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            # Sanitize lists of dictionaries
            sanitized[key] = [sanitize_log_data(item) for item in value]
        else:
            sanitized[key] = value
    
    return sanitized


# Production configuration overrides
def apply_production_overrides(app_config: Dict) -> Dict:
    """
    Apply production-specific configuration overrides.
    
    Args:
        app_config: The application configuration dictionary
        
    Returns:
        Updated configuration with production overrides
    """
    if IS_PRODUCTION:
        # Disable debug mode
        app_config["debug"] = False
        
        # Ensure strong session configuration
        app_config["session_cookie_secure"] = True
        app_config["session_cookie_httponly"] = True
        app_config["session_cookie_samesite"] = "strict"
        
        # Disable auto-reload
        app_config["reload"] = False
        
        # Set production log level
        if app_config.get("log_level", "").upper() == "DEBUG":
            app_config["log_level"] = "INFO"
    
    return app_config