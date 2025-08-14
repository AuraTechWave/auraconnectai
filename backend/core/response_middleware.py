"""
Response Standardization Middleware

Middleware to ensure all API responses follow the standard format.
"""

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import json
import time
import uuid
import traceback
from typing import Callable, Any

from .response_models import StandardResponse, ErrorDetail


class ResponseStandardizationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to standardize all API responses
    
    Features:
    - Wraps all responses in standard envelope
    - Adds request tracking ID
    - Measures processing time
    - Handles uncaught exceptions
    """
    
    def __init__(self, app: ASGIApp, exclude_paths: list = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/docs", "/redoc", "/openapi.json", "/health"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and standardize response"""
        
        # Skip middleware for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Generate request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        
        # Track processing time
        start_time = time.time()
        
        try:
            # Process the request
            response = await call_next(request)
            
            # Calculate processing time
            processing_time_ms = (time.time() - start_time) * 1000
            
            # For streaming responses, return as is
            if hasattr(response, "body_iterator"):
                return response
            
            # Read response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            # Try to decode JSON response
            try:
                if body:
                    response_data = json.loads(body.decode())
                else:
                    response_data = None
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Not JSON, return original response
                return Response(
                    content=body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type
                )
            
            # Check if response is already in standard format
            if isinstance(response_data, dict) and "success" in response_data and "meta" in response_data:
                # Update meta with request ID and processing time
                response_data["meta"]["request_id"] = request_id
                response_data["meta"]["processing_time_ms"] = processing_time_ms
                
                return JSONResponse(
                    content=response_data,
                    status_code=response.status_code,
                    headers=dict(response.headers)
                )
            
            # Wrap non-standard responses
            if response.status_code >= 400:
                # Error response
                standard_response = StandardResponse.error(
                    message=response_data.get("detail", "An error occurred") if isinstance(response_data, dict) else str(response_data),
                    code=self._get_error_code(response.status_code),
                    meta={
                        "request_id": request_id,
                        "processing_time_ms": processing_time_ms
                    }
                )
            else:
                # Success response
                standard_response = StandardResponse.success(
                    data=response_data,
                    meta={
                        "request_id": request_id,
                        "processing_time_ms": processing_time_ms
                    }
                )
            
            return JSONResponse(
                content=standard_response.model_dump(exclude_none=True),
                status_code=response.status_code,
                headers=dict(response.headers)
            )
            
        except Exception as e:
            # Handle uncaught exceptions
            processing_time_ms = (time.time() - start_time) * 1000
            
            # Log the error
            print(f"Unhandled exception in request {request_id}: {str(e)}")
            print(traceback.format_exc())
            
            # Create error response
            error_response = StandardResponse.error(
                message="An unexpected error occurred",
                code="INTERNAL_ERROR",
                errors=[
                    ErrorDetail(
                        code="INTERNAL_ERROR",
                        message=str(e) if request.app.debug else "Internal server error"
                    )
                ],
                meta={
                    "request_id": request_id,
                    "processing_time_ms": processing_time_ms
                }
            )
            
            return JSONResponse(
                content=error_response.model_dump(exclude_none=True),
                status_code=500
            )
    
    def _get_error_code(self, status_code: int) -> str:
        """Map HTTP status code to error code"""
        error_codes = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            409: "CONFLICT",
            422: "VALIDATION_ERROR",
            429: "TOO_MANY_REQUESTS",
            500: "INTERNAL_ERROR",
            502: "BAD_GATEWAY",
            503: "SERVICE_UNAVAILABLE",
            504: "GATEWAY_TIMEOUT"
        }
        return error_codes.get(status_code, "ERROR")


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Middleware specifically for handling errors and exceptions
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and handle errors"""
        try:
            response = await call_next(request)
            return response
        except ValueError as e:
            # Handle validation errors
            return JSONResponse(
                status_code=422,
                content=StandardResponse.error(
                    message="Validation error",
                    code="VALIDATION_ERROR",
                    errors=[ErrorDetail(code="VALIDATION_ERROR", message=str(e))],
                    meta={"request_id": getattr(request.state, "request_id", None)}
                ).model_dump(exclude_none=True)
            )
        except PermissionError as e:
            # Handle permission errors
            return JSONResponse(
                status_code=403,
                content=StandardResponse.error(
                    message="Permission denied",
                    code="FORBIDDEN",
                    errors=[ErrorDetail(code="FORBIDDEN", message=str(e))],
                    meta={"request_id": getattr(request.state, "request_id", None)}
                ).model_dump(exclude_none=True)
            )
        except KeyError as e:
            # Handle missing key errors
            return JSONResponse(
                status_code=400,
                content=StandardResponse.error(
                    message=f"Missing required field: {str(e)}",
                    code="BAD_REQUEST",
                    errors=[ErrorDetail(code="MISSING_FIELD", message=f"Field {str(e)} is required")],
                    meta={"request_id": getattr(request.state, "request_id", None)}
                ).model_dump(exclude_none=True)
            )
        except Exception as e:
            # Handle all other exceptions
            print(f"Unhandled exception: {str(e)}")
            print(traceback.format_exc())
            
            return JSONResponse(
                status_code=500,
                content=StandardResponse.error(
                    message="An unexpected error occurred",
                    code="INTERNAL_ERROR",
                    errors=[ErrorDetail(code="INTERNAL_ERROR", message="Internal server error")],
                    meta={"request_id": getattr(request.state, "request_id", None)}
                ).model_dump(exclude_none=True)
            )