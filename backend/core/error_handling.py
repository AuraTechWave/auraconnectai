# backend/core/error_handling.py

"""
Comprehensive error handling utilities for API routes.
"""

from typing import Callable, Type, Dict, Any, Optional
from functools import wraps
import logging
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, DataError, OperationalError
from pydantic import ValidationError
import traceback

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base exception for API errors"""
    def __init__(
        self, 
        message: str, 
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(APIError):
    """Resource not found error"""
    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} with identifier {identifier} not found",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource": resource, "identifier": str(identifier)}
        )


class ConflictError(APIError):
    """Resource conflict error"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details=details
        )


class ValidationError(APIError):
    """Input validation error"""
    def __init__(self, message: str, errors: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"validation_errors": errors} if errors else {}
        )


class AuthorizationError(APIError):
    """Authorization error"""
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN
        )


def handle_api_errors(func: Callable) -> Callable:
    """
    Decorator to handle common API errors with proper status codes and messages.
    
    Usage:
        @router.get("/items/{item_id}")
        @handle_api_errors
        async def get_item(item_id: int, db: Session = Depends(get_db)):
            # Your code here
            pass
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
            
        except APIError as e:
            # Handle custom API errors
            logger.warning(f"API Error in {func.__name__}: {e.message}", extra={
                "status_code": e.status_code,
                "details": e.details
            })
            raise HTTPException(
                status_code=e.status_code,
                detail={
                    "message": e.message,
                    "details": e.details
                }
            )
            
        except ValueError as e:
            # Handle service-level validation errors
            logger.warning(f"Validation error in {func.__name__}: {str(e)}")
            
            # Check for common patterns
            error_message = str(e).lower()
            if "not found" in error_message:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"message": str(e)}
                )
            elif "already exists" in error_message or "duplicate" in error_message:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"message": str(e)}
                )
            elif "invalid" in error_message or "must be" in error_message:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"message": str(e)}
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"message": str(e)}
                )
                
        except PermissionError as e:
            # Handle permission errors
            logger.warning(f"Permission denied in {func.__name__}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"message": str(e) or "Insufficient permissions"}
            )
            
        except IntegrityError as e:
            # Handle database integrity errors
            logger.error(f"Database integrity error in {func.__name__}: {str(e.orig)}")
            
            error_info = str(e.orig).lower() if e.orig else str(e).lower()
            if "foreign key" in error_info:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "message": "Referenced resource does not exist or cannot be deleted due to existing references",
                        "type": "foreign_key_violation"
                    }
                )
            elif "unique" in error_info or "duplicate" in error_info:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "message": "Resource already exists with the provided unique values",
                        "type": "unique_violation"
                    }
                )
            elif "not null" in error_info:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "message": "Required field is missing",
                        "type": "not_null_violation"
                    }
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "message": "Database constraint violation",
                        "type": "integrity_error"
                    }
                )
                
        except DataError as e:
            # Handle data type errors
            logger.error(f"Data error in {func.__name__}: {str(e.orig)}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Invalid data format or type",
                    "type": "data_error"
                }
            )
            
        except OperationalError as e:
            # Handle database operational errors
            logger.error(f"Database operational error in {func.__name__}: {str(e.orig)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "message": "Database service temporarily unavailable",
                    "type": "operational_error"
                }
            )
            
        except ValidationError as e:
            # Handle Pydantic validation errors
            logger.warning(f"Pydantic validation error in {func.__name__}: {e.errors()}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Request validation failed",
                    "errors": e.errors()
                }
            )
            
        except HTTPException:
            # Re-raise FastAPI HTTP exceptions
            raise
            
        except Exception as e:
            # Handle unexpected errors
            logger.error(
                f"Unexpected error in {func.__name__}: {str(e)}\n{traceback.format_exc()}"
            )
            
            # In production, don't expose internal error details
            if logger.level > logging.DEBUG:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={
                        "message": "An unexpected error occurred",
                        "request_id": kwargs.get("request_id", "unknown")
                    }
                )
            else:
                # In development, include more details
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={
                        "message": "An unexpected error occurred",
                        "error": str(e),
                        "type": type(e).__name__
                    }
                )
    
    # Handle both sync and async functions
    if asyncio.iscoroutinefunction(func):
        return wrapper
    else:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(wrapper(*args, **kwargs))
        return sync_wrapper


def create_error_response(
    status_code: int,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> JSONResponse:
    """
    Create a standardized error response.
    
    Args:
        status_code: HTTP status code
        message: Error message
        details: Additional error details
        request_id: Request tracking ID
    
    Returns:
        JSONResponse with error information
    """
    content = {
        "error": {
            "message": message,
            "status_code": status_code,
            "timestamp": datetime.utcnow().isoformat(),
        }
    }
    
    if details:
        content["error"]["details"] = details
        
    if request_id:
        content["error"]["request_id"] = request_id
        
    return JSONResponse(
        status_code=status_code,
        content=content
    )


class ErrorHandlingMiddleware:
    """
    Middleware for global error handling and logging.
    """
    
    def __init__(self, app):
        self.app = app
        
    async def __call__(self, request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        try:
            response = await call_next(request)
            return response
            
        except Exception as e:
            logger.error(
                f"Unhandled exception: {str(e)}\n{traceback.format_exc()}",
                extra={
                    "request_id": request_id,
                    "path": request.url.path,
                    "method": request.method
                }
            )
            
            return create_error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="An unexpected error occurred",
                request_id=request_id
            )


# Error handlers for specific scenarios

def handle_database_errors(error: Exception) -> HTTPException:
    """
    Convert database errors to appropriate HTTP exceptions.
    """
    if isinstance(error, IntegrityError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Database constraint violation"
        )
    elif isinstance(error, DataError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid data format"
        )
    elif isinstance(error, OperationalError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable"
        )
    else:
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )


def validate_request_data(
    data: Dict[str, Any],
    required_fields: List[str],
    optional_fields: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Validate request data contains required fields.
    
    Args:
        data: Request data dictionary
        required_fields: List of required field names
        optional_fields: List of optional field names
        
    Returns:
        Validated data dictionary
        
    Raises:
        ValidationError: If validation fails
    """
    errors = {}
    
    # Check required fields
    for field in required_fields:
        if field not in data or data[field] is None:
            errors[field] = "This field is required"
            
    # Check for unknown fields
    allowed_fields = set(required_fields)
    if optional_fields:
        allowed_fields.update(optional_fields)
        
    unknown_fields = set(data.keys()) - allowed_fields
    if unknown_fields:
        errors["unknown_fields"] = list(unknown_fields)
        
    if errors:
        raise ValidationError(
            message="Request validation failed",
            errors=errors
        )
        
    return data


# Import required modules
import asyncio
import uuid
from datetime import datetime
from typing import List