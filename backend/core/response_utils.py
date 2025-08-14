"""
Response Utilities

Helper functions for creating standardized API responses.
"""

from typing import Any, Dict, List, Optional, TypeVar, Callable
from fastapi import Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Query as SQLQuery
from datetime import datetime
import time
import uuid
import json
from functools import wraps

from .response_models import (
    StandardResponse,
    PaginationMeta,
    ErrorDetail,
    ValidationErrorResponse,
    NotFoundResponse
)


T = TypeVar('T')


class PaginationParams:
    """Standard pagination parameters for API endpoints"""
    
    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        per_page: int = Query(20, ge=1, le=100, description="Items per page")
    ):
        self.page = page
        self.per_page = per_page
        self.skip = (page - 1) * per_page
        self.limit = per_page
    
    def paginate_query(self, query: SQLQuery) -> tuple[List[Any], int]:
        """Apply pagination to SQLAlchemy query and return items and total count"""
        total = query.count()
        items = query.offset(self.skip).limit(self.limit).all()
        return items, total
    
    def create_pagination_meta(self, total: int) -> PaginationMeta:
        """Create pagination metadata"""
        total_pages = (total + self.per_page - 1) // self.per_page if self.per_page > 0 else 0
        
        return PaginationMeta(
            current_page=self.page,
            per_page=self.per_page,
            total=total,
            total_pages=total_pages,
            has_next=self.page < total_pages,
            has_prev=self.page > 1
        )


def create_response(
    data: Any = None,
    message: Optional[str] = None,
    pagination: Optional[PaginationMeta] = None,
    request_id: Optional[str] = None,
    processing_time_ms: Optional[float] = None
) -> StandardResponse:
    """Create a standard successful response"""
    meta = {}
    if request_id:
        meta['request_id'] = request_id
    if processing_time_ms:
        meta['processing_time_ms'] = processing_time_ms
        
    return StandardResponse.success(
        data=data,
        message=message,
        meta=meta,
        pagination=pagination
    )


def create_error_response(
    message: str,
    code: str = "ERROR",
    status_code: int = 400,
    errors: Optional[List[ErrorDetail]] = None,
    request_id: Optional[str] = None
) -> JSONResponse:
    """Create a standard error response"""
    meta = {}
    if request_id:
        meta['request_id'] = request_id
        
    response = StandardResponse.error(
        message=message,
        code=code,
        errors=errors,
        meta=meta
    )
    
    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(exclude_none=True)
    )


def create_paginated_response(
    items: List[Any],
    pagination_params: PaginationParams,
    total: int,
    message: Optional[str] = None,
    request_id: Optional[str] = None,
    processing_time_ms: Optional[float] = None
) -> StandardResponse:
    """Create a paginated response"""
    pagination_meta = pagination_params.create_pagination_meta(total)
    
    meta = {}
    if request_id:
        meta['request_id'] = request_id
    if processing_time_ms:
        meta['processing_time_ms'] = processing_time_ms
        
    return StandardResponse.paginated(
        data=items,
        page=pagination_params.page,
        per_page=pagination_params.per_page,
        total=total,
        message=message,
        meta=meta
    )


def response_wrapper(func: Callable) -> Callable:
    """
    Decorator to wrap endpoint responses in standard format
    
    Usage:
        @router.get("/users")
        @response_wrapper
        async def get_users():
            return {"users": [...]}  # Will be wrapped in StandardResponse
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        request_id = str(uuid.uuid4())
        
        try:
            # Get request object if available
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            for key, value in kwargs.items():
                if isinstance(value, Request):
                    request = value
                    break
            
            # Add request ID to request state
            if request:
                request.state.request_id = request_id
            
            # Execute the endpoint function
            result = await func(*args, **kwargs)
            
            # Calculate processing time
            processing_time_ms = (time.time() - start_time) * 1000
            
            # If already a StandardResponse, return as is
            if isinstance(result, StandardResponse):
                result.meta.request_id = request_id
                result.meta.processing_time_ms = processing_time_ms
                return result
            
            # If it's a JSONResponse, return as is
            if isinstance(result, JSONResponse):
                return result
            
            # Otherwise, wrap in StandardResponse
            return create_response(
                data=result,
                request_id=request_id,
                processing_time_ms=processing_time_ms
            )
            
        except Exception as e:
            processing_time_ms = (time.time() - start_time) * 1000
            
            # Handle specific exceptions
            if hasattr(e, 'status_code'):
                return create_error_response(
                    message=str(e),
                    code=getattr(e, 'code', 'ERROR'),
                    status_code=getattr(e, 'status_code', 400),
                    request_id=request_id
                )
            
            # Generic error
            return create_error_response(
                message="An unexpected error occurred",
                code="INTERNAL_ERROR",
                status_code=500,
                errors=[ErrorDetail(code="INTERNAL_ERROR", message=str(e))],
                request_id=request_id
            )
    
    return wrapper


def validate_request_data(data: Dict[str, Any], required_fields: List[str]) -> Optional[ValidationErrorResponse]:
    """
    Validate that required fields are present in request data
    
    Returns ValidationErrorResponse if validation fails, None otherwise
    """
    errors = {}
    
    for field in required_fields:
        if field not in data or data[field] is None:
            errors[field] = [f"{field} is required"]
    
    if errors:
        return ValidationErrorResponse.from_validation_errors(errors)
    
    return None


def format_validation_errors(errors: Dict[str, Any]) -> List[ErrorDetail]:
    """Format validation errors into ErrorDetail objects"""
    error_details = []
    
    for field, messages in errors.items():
        if isinstance(messages, list):
            for message in messages:
                error_details.append(
                    ErrorDetail(
                        code="VALIDATION_ERROR",
                        message=message,
                        field=field
                    )
                )
        else:
            error_details.append(
                ErrorDetail(
                    code="VALIDATION_ERROR",
                    message=str(messages),
                    field=field
                )
            )
    
    return error_details


def handle_database_error(error: Exception, operation: str = "database operation") -> JSONResponse:
    """Handle database errors and return appropriate response"""
    error_message = str(error)
    
    if "duplicate key" in error_message.lower():
        return create_error_response(
            message=f"Duplicate entry detected during {operation}",
            code="DUPLICATE_ENTRY",
            status_code=409
        )
    elif "foreign key" in error_message.lower():
        return create_error_response(
            message=f"Related resource not found during {operation}",
            code="FOREIGN_KEY_ERROR",
            status_code=400
        )
    elif "not found" in error_message.lower():
        return create_error_response(
            message=f"Resource not found during {operation}",
            code="NOT_FOUND",
            status_code=404
        )
    else:
        return create_error_response(
            message=f"Database error during {operation}",
            code="DATABASE_ERROR",
            status_code=500,
            errors=[ErrorDetail(code="DATABASE_ERROR", message=error_message)]
        )


class ResponseBuilder:
    """Builder pattern for creating complex responses"""
    
    def __init__(self):
        self._data = None
        self._message = None
        self._errors = []
        self._meta = {}
        self._pagination = None
        self._success = True
        
    def with_data(self, data: Any) -> "ResponseBuilder":
        """Add data to response"""
        self._data = data
        return self
    
    def with_message(self, message: str) -> "ResponseBuilder":
        """Add message to response"""
        self._message = message
        return self
    
    def with_error(self, code: str, message: str, field: Optional[str] = None) -> "ResponseBuilder":
        """Add error to response"""
        self._success = False
        self._errors.append(ErrorDetail(code=code, message=message, field=field))
        return self
    
    def with_pagination(self, page: int, per_page: int, total: int) -> "ResponseBuilder":
        """Add pagination to response"""
        total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0
        self._pagination = PaginationMeta(
            current_page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )
        return self
    
    def with_meta(self, key: str, value: Any) -> "ResponseBuilder":
        """Add metadata to response"""
        self._meta[key] = value
        return self
    
    def build(self) -> StandardResponse:
        """Build the response"""
        if not self._success:
            return StandardResponse.error(
                message=self._message or "Error occurred",
                errors=self._errors,
                meta=self._meta
            )
        
        return StandardResponse.success(
            data=self._data,
            message=self._message,
            meta=self._meta,
            pagination=self._pagination
        )