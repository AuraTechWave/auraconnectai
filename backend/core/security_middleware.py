"""
Security middleware for production hardening.

This middleware implements:
- Security headers
- Request/Response sanitization
- Audit logging
- API version warnings
"""

import json
import time
import logging
from typing import Callable, Optional
from datetime import datetime
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .security_config import (
    apply_security_headers,
    get_client_ip,
    sanitize_log_data,
    AUDIT_LOG_ENABLED,
    AUDIT_LOG_SENSITIVE_OPERATIONS,
    DEPRECATED_API_VERSIONS,
    DISABLED_API_VERSIONS,
    IS_PRODUCTION
)
from .audit_logger import AuditLogger

logger = logging.getLogger(__name__)
audit_logger = AuditLogger()


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive security middleware for production hardening.
    """
    
    def __init__(self, app, exclude_paths: Optional[list] = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/docs", "/redoc", "/openapi.json", 
            "/health", "/metrics", "/favicon.ico"
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip middleware for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Start timing
        start_time = time.time()
        
        # Extract request metadata
        client_ip = get_client_ip(request)
        request_id = request.headers.get("X-Request-ID", str(time.time()))
        
        # Store metadata in request state for downstream use
        request.state.client_ip = client_ip
        request.state.request_id = request_id
        request.state.request_time = datetime.utcnow()
        
        # Check API version
        api_version = self._extract_api_version(request.url.path)
        if api_version:
            # Block disabled API versions
            if api_version in DISABLED_API_VERSIONS:
                return JSONResponse(
                    status_code=410,
                    content={
                        "error": "API version no longer supported",
                        "message": f"API {api_version} has been discontinued. Please upgrade to the latest version.",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
            
            # Add deprecation warning for deprecated versions
            if api_version in DEPRECATED_API_VERSIONS:
                request.state.api_deprecation_warning = (
                    f"API {api_version} is deprecated and will be removed in future releases. "
                    "Please upgrade to the latest version."
                )
        
        # Log sensitive operations
        operation_type = self._identify_operation(request)
        if operation_type and AUDIT_LOG_ENABLED:
            # Capture request body for audit
            body = await self._get_request_body(request)
            await audit_logger.log_operation_start(
                operation_type=operation_type,
                user_id=getattr(request.state, "user_id", None),
                client_ip=client_ip,
                request_id=request_id,
                request_data=sanitize_log_data(body) if body else None
            )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Apply security headers
            if isinstance(response, JSONResponse):
                response = apply_security_headers(response)
            else:
                # Apply headers to any response type
                for header, value in apply_security_headers(JSONResponse(content={})).headers.items():
                    if header not in response.headers:
                        response.headers[header] = value
            
            # Add API deprecation warning if applicable
            if hasattr(request.state, "api_deprecation_warning"):
                response.headers["X-API-Deprecation-Warning"] = request.state.api_deprecation_warning
            
            # Log operation completion for sensitive operations
            if operation_type and AUDIT_LOG_ENABLED:
                await audit_logger.log_operation_complete(
                    operation_type=operation_type,
                    request_id=request_id,
                    status_code=response.status_code,
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            
            # Add security metadata to response headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{int((time.time() - start_time) * 1000)}ms"
            
            # Remove server header in production
            if IS_PRODUCTION and "server" in response.headers:
                del response.headers["server"]
            
            return response
            
        except Exception as e:
            # Log operation failure for sensitive operations
            if operation_type and AUDIT_LOG_ENABLED:
                await audit_logger.log_operation_failure(
                    operation_type=operation_type,
                    request_id=request_id,
                    error=str(e),
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            
            # Re-raise the exception
            raise
    
    def _extract_api_version(self, path: str) -> Optional[str]:
        """Extract API version from URL path."""
        parts = path.split("/")
        for i, part in enumerate(parts):
            if part == "api" and i + 1 < len(parts):
                version = parts[i + 1]
                if version.startswith("v"):
                    return version
        return None
    
    def _identify_operation(self, request: Request) -> Optional[str]:
        """Identify if this is a sensitive operation that needs audit logging."""
        path = request.url.path.lower()
        method = request.method.upper()
        
        # Map endpoints to operation types
        operation_mappings = {
            # User management
            ("POST", "/api/v1/auth/users"): "user_create",
            ("DELETE", "/api/v1/auth/users"): "user_delete",
            ("PUT", "/api/v1/auth/users/role"): "user_role_change",
            ("PATCH", "/api/v1/auth/users/role"): "user_role_change",
            
            # Payment operations
            ("POST", "/api/v1/payments/process"): "payment_process",
            ("POST", "/api/v1/payments/refund"): "payment_refund",
            
            # Payroll operations
            ("POST", "/api/v1/payroll/process"): "payroll_process",
            ("POST", "/api/v1/payroll/export"): "payroll_export",
            
            # Settings
            ("PUT", "/api/v1/settings"): "settings_update",
            ("PATCH", "/api/v1/settings"): "settings_update",
            
            # Webhook configuration
            ("POST", "/api/v1/webhooks"): "webhook_config_change",
            ("PUT", "/api/v1/webhooks"): "webhook_config_change",
            ("DELETE", "/api/v1/webhooks"): "webhook_config_change",
            
            # Data operations
            ("POST", "/api/v1/export"): "data_export",
            ("POST", "/api/v1/import"): "data_import",
        }
        
        # Check exact matches
        for (op_method, op_path), operation in operation_mappings.items():
            if method == op_method and path.startswith(op_path):
                return operation
        
        # Check pattern matches
        if method == "DELETE" and "/users/" in path:
            return "user_delete"
        if method in ["PUT", "PATCH"] and "/users/" in path and "/role" in path:
            return "user_role_change"
        if method == "POST" and "/payroll/" in path and "/process" in path:
            return "payroll_process"
        if method == "POST" and "/payroll/" in path and "/export" in path:
            return "payroll_export"
        
        return None
    
    async def _get_request_body(self, request: Request) -> Optional[dict]:
        """Safely get request body for audit logging."""
        try:
            # Only capture body for certain content types
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                # Read body (this consumes the stream, so we need to restore it)
                body = await request.body()
                
                # Parse JSON
                if body:
                    body_json = json.loads(body)
                    
                    # Restore body for downstream processing
                    async def receive():
                        return {"type": "http.request", "body": body}
                    request._receive = receive
                    
                    return body_json
        except Exception as e:
            logger.warning(f"Failed to capture request body for audit: {e}")
        
        return None