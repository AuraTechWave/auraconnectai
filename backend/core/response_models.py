"""
Standard API Response Models

Provides consistent response envelope for all API endpoints.
"""

from typing import TypeVar, Generic, Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


T = TypeVar('T')


class PaginationMeta(BaseModel):
    """Standard pagination metadata"""
    current_page: int = Field(description="Current page number (1-indexed)")
    per_page: int = Field(description="Number of items per page")
    total: int = Field(description="Total number of items")
    total_pages: int = Field(description="Total number of pages")
    has_next: bool = Field(description="Whether there is a next page")
    has_prev: bool = Field(description="Whether there is a previous page")
    
    class Config:
        json_schema_extra = {
            "example": {
                "current_page": 1,
                "per_page": 20,
                "total": 100,
                "total_pages": 5,
                "has_next": True,
                "has_prev": False
            }
        }


class ResponseMeta(BaseModel):
    """Metadata for API responses"""
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    request_id: Optional[str] = Field(None, description="Request tracking ID")
    pagination: Optional[PaginationMeta] = Field(None, description="Pagination information if applicable")
    processing_time_ms: Optional[float] = Field(None, description="Request processing time in milliseconds")
    version: str = Field(default="1.0", description="API version")
    
    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-08-14T12:00:00Z",
                "request_id": "req_123456",
                "version": "1.0"
            }
        }


class ErrorDetail(BaseModel):
    """Detailed error information"""
    code: str = Field(description="Error code for programmatic handling")
    message: str = Field(description="Human-readable error message")
    field: Optional[str] = Field(None, description="Field that caused the error (for validation errors)")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional error context")
    
    class Config:
        json_schema_extra = {
            "example": {
                "code": "VALIDATION_ERROR",
                "message": "Email format is invalid",
                "field": "email"
            }
        }


class StandardResponse(BaseModel, Generic[T]):
    """
    Standard response envelope for all API endpoints
    
    Usage:
        return StandardResponse.success(data=user_data)
        return StandardResponse.error(message="User not found", code="NOT_FOUND")
    """
    success: bool = Field(description="Whether the request was successful")
    data: Optional[T] = Field(None, description="Response payload")
    meta: ResponseMeta = Field(default_factory=ResponseMeta, description="Response metadata")
    errors: List[ErrorDetail] = Field(default_factory=list, description="List of errors if any")
    message: Optional[str] = Field(None, description="Optional status message")
    
    @classmethod
    def success(
        cls,
        data: Optional[T] = None,
        message: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
        pagination: Optional[PaginationMeta] = None
    ) -> "StandardResponse[T]":
        """Create a successful response"""
        response_meta = ResponseMeta()
        if meta:
            for key, value in meta.items():
                if hasattr(response_meta, key):
                    setattr(response_meta, key, value)
        if pagination:
            response_meta.pagination = pagination
            
        return cls(
            success=True,
            data=data,
            meta=response_meta,
            errors=[],
            message=message
        )
    
    @classmethod
    def error(
        cls,
        message: str,
        code: str = "ERROR",
        errors: Optional[List[ErrorDetail]] = None,
        meta: Optional[Dict[str, Any]] = None
    ) -> "StandardResponse[None]":
        """Create an error response"""
        error_list = errors or []
        if not error_list:
            error_list = [ErrorDetail(code=code, message=message)]
            
        response_meta = ResponseMeta()
        if meta:
            for key, value in meta.items():
                if hasattr(response_meta, key):
                    setattr(response_meta, key, value)
                    
        return cls(
            success=False,
            data=None,
            meta=response_meta,
            errors=error_list,
            message=message
        )
    
    @classmethod
    def paginated(
        cls,
        data: List[T],
        page: int,
        per_page: int,
        total: int,
        message: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None
    ) -> "StandardResponse[List[T]]":
        """Create a paginated response"""
        total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0
        
        pagination = PaginationMeta(
            current_page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )
        
        return cls.success(
            data=data,
            message=message,
            meta=meta,
            pagination=pagination
        )
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"id": 1, "name": "Example"},
                "meta": {
                    "timestamp": "2025-08-14T12:00:00Z",
                    "request_id": "req_123456",
                    "version": "1.0"
                },
                "errors": [],
                "message": "Operation completed successfully"
            }
        }


class ListResponse(StandardResponse[List[T]], Generic[T]):
    """Specialized response for list endpoints"""
    pass


class SingleResponse(StandardResponse[T], Generic[T]):
    """Specialized response for single item endpoints"""
    pass


class EmptyResponse(StandardResponse[None]):
    """Response with no data payload"""
    pass


# Common error responses
class ValidationErrorResponse(StandardResponse[None]):
    """Response for validation errors"""
    
    @classmethod
    def from_validation_errors(cls, errors: Dict[str, List[str]]) -> "ValidationErrorResponse":
        """Create from validation errors dictionary"""
        error_details = []
        for field, messages in errors.items():
            for message in messages:
                error_details.append(
                    ErrorDetail(
                        code="VALIDATION_ERROR",
                        message=message,
                        field=field
                    )
                )
        
        return cls(
            success=False,
            data=None,
            errors=error_details,
            message="Validation failed"
        )


class NotFoundResponse(StandardResponse[None]):
    """Response for resource not found"""
    
    @classmethod
    def create(cls, resource: str, identifier: Any) -> "NotFoundResponse":
        """Create a not found response"""
        return cls.error(
            message=f"{resource} with ID {identifier} not found",
            code="NOT_FOUND"
        )


class UnauthorizedResponse(StandardResponse[None]):
    """Response for unauthorized access"""
    
    @classmethod
    def create(cls, message: str = "Unauthorized access") -> "UnauthorizedResponse":
        """Create an unauthorized response"""
        return cls.error(
            message=message,
            code="UNAUTHORIZED"
        )


class ForbiddenResponse(StandardResponse[None]):
    """Response for forbidden access"""
    
    @classmethod
    def create(cls, message: str = "Access forbidden") -> "ForbiddenResponse":
        """Create a forbidden response"""
        return cls.error(
            message=message,
            code="FORBIDDEN"
        )