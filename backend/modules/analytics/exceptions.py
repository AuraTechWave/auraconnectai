# backend/modules/analytics/exceptions.py

"""
Custom exceptions for analytics module.

Provides specific exception types for better error handling and debugging.
"""

from typing import Optional, Dict, Any, List


class AnalyticsBaseException(Exception):
    """Base exception for all analytics errors"""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class InsufficientDataError(AnalyticsBaseException):
    """Raised when there's not enough historical data for analysis"""
    
    def __init__(
        self,
        required_points: int,
        available_points: int,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None
    ):
        message = (
            f"Insufficient data for analysis. "
            f"Required: {required_points} points, Available: {available_points} points"
        )
        details = {
            "required_points": required_points,
            "available_points": available_points,
            "entity_type": entity_type,
            "entity_id": entity_id
        }
        super().__init__(message, "INSUFFICIENT_DATA", details)


class ForecastModelError(AnalyticsBaseException):
    """Raised when forecast model fails"""
    
    def __init__(
        self,
        model_type: str,
        reason: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None
    ):
        message = f"Forecast model '{model_type}' failed: {reason}"
        details = {
            "model_type": model_type,
            "reason": reason,
            "entity_type": entity_type,
            "entity_id": entity_id
        }
        super().__init__(message, "FORECAST_MODEL_ERROR", details)


class OptimizationError(AnalyticsBaseException):
    """Raised when optimization algorithms fail"""
    
    def __init__(
        self,
        optimization_type: str,
        reason: str,
        product_ids: Optional[List[int]] = None
    ):
        message = f"Optimization '{optimization_type}' failed: {reason}"
        details = {
            "optimization_type": optimization_type,
            "reason": reason,
            "product_ids": product_ids
        }
        super().__init__(message, "OPTIMIZATION_ERROR", details)


class DataQualityError(AnalyticsBaseException):
    """Raised when data quality issues are detected"""
    
    def __init__(
        self,
        issue_type: str,
        description: str,
        affected_data: Optional[Dict[str, Any]] = None
    ):
        message = f"Data quality issue '{issue_type}': {description}"
        details = {
            "issue_type": issue_type,
            "description": description,
            "affected_data": affected_data
        }
        super().__init__(message, "DATA_QUALITY_ERROR", details)


class ModelNotFoundError(AnalyticsBaseException):
    """Raised when a requested model doesn't exist"""
    
    def __init__(
        self,
        model_type: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None
    ):
        message = f"Model '{model_type}' not found"
        details = {
            "model_type": model_type,
            "entity_type": entity_type,
            "entity_id": entity_id
        }
        super().__init__(message, "MODEL_NOT_FOUND", details)


class CacheError(AnalyticsBaseException):
    """Raised when cache operations fail"""
    
    def __init__(self, operation: str, reason: str):
        message = f"Cache {operation} failed: {reason}"
        details = {
            "operation": operation,
            "reason": reason
        }
        super().__init__(message, "CACHE_ERROR", details)


class ExternalServiceError(AnalyticsBaseException):
    """Raised when external service integration fails"""
    
    def __init__(
        self,
        service_name: str,
        reason: str,
        retry_after: Optional[int] = None
    ):
        message = f"External service '{service_name}' error: {reason}"
        details = {
            "service_name": service_name,
            "reason": reason,
            "retry_after": retry_after
        }
        super().__init__(message, "EXTERNAL_SERVICE_ERROR", details)


class RateLimitError(AnalyticsBaseException):
    """Raised when rate limits are exceeded"""
    
    def __init__(
        self,
        endpoint: str,
        limit: int,
        window: str,
        retry_after: int
    ):
        message = f"Rate limit exceeded for {endpoint}: {limit} requests per {window}"
        details = {
            "endpoint": endpoint,
            "limit": limit,
            "window": window,
            "retry_after": retry_after
        }
        super().__init__(message, "RATE_LIMIT_ERROR", details)


class ValidationError(AnalyticsBaseException):
    """Raised when input validation fails"""
    
    def __init__(
        self,
        field: str,
        value: Any,
        constraint: str
    ):
        message = f"Validation failed for '{field}': {constraint}"
        details = {
            "field": field,
            "value": value,
            "constraint": constraint
        }
        super().__init__(message, "VALIDATION_ERROR", details)


class PermissionError(AnalyticsBaseException):
    """Raised when user lacks required permissions"""
    
    def __init__(
        self,
        required_permission: str,
        user_id: int,
        resource: Optional[str] = None
    ):
        message = f"Permission '{required_permission}' required"
        details = {
            "required_permission": required_permission,
            "user_id": user_id,
            "resource": resource
        }
        super().__init__(message, "PERMISSION_ERROR", details)


# Error handler utility
def handle_analytics_exception(exc: AnalyticsBaseException) -> Dict[str, Any]:
    """Convert analytics exception to API response format"""
    return {
        "error": {
            "code": exc.error_code,
            "message": exc.message,
            "details": exc.details
        }
    }