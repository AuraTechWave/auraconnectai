"""
Custom exception handlers for consistent API error responses.

This module provides custom exceptions and handlers to maintain
consistent error responses across the API, even when using
standard Python exceptions internally.
"""

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class APIError(HTTPException):
    """Base API error with consistent structure"""

    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: Optional[str] = None,
        headers: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.error_code = error_code


class NotFoundError(APIError):
    """Resource not found error"""

    def __init__(
        self, detail: str = "Resource not found", error_code: str = "NOT_FOUND"
    ):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND, detail=detail, error_code=error_code
        )


class ValidationError(APIError):
    """Validation error"""

    def __init__(
        self, detail: str = "Validation failed", error_code: str = "VALIDATION_ERROR"
    ):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code=error_code,
        )


class AuthenticationError(APIError):
    """Authentication error"""

    def __init__(
        self, detail: str = "Authentication failed", error_code: str = "AUTH_FAILED"
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code=error_code,
        )


class PermissionError(APIError):
    """Permission denied error"""

    def __init__(
        self, detail: str = "Permission denied", error_code: str = "PERMISSION_DENIED"
    ):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN, detail=detail, error_code=error_code
        )


class ConflictError(APIError):
    """Resource conflict error"""

    def __init__(self, detail: str = "Resource conflict", error_code: str = "CONFLICT"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT, detail=detail, error_code=error_code
        )


async def handle_key_error(request: Request, exc: KeyError) -> JSONResponse:
    """Convert KeyError to consistent API response"""
    logger.warning(f"KeyError at {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "detail": f"Resource not found: {str(exc)}",
            "error_code": "NOT_FOUND",
            "path": str(request.url.path),
        },
    )


async def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
    """Convert ValueError to consistent API response"""
    logger.warning(f"ValueError at {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": str(exc),
            "error_code": "VALIDATION_ERROR",
            "path": str(request.url.path),
        },
    )


async def handle_permission_error(
    request: Request, exc: PermissionError
) -> JSONResponse:
    """Convert PermissionError to consistent API response"""
    logger.warning(f"PermissionError at {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "detail": str(exc) or "Permission denied",
            "error_code": "PERMISSION_DENIED",
            "path": str(request.url.path),
        },
    )


async def handle_api_error(request: Request, exc: APIError) -> JSONResponse:
    """Handle custom API errors"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error_code": exc.error_code,
            "path": str(request.url.path),
        },
        headers=exc.headers,
    )


def register_exception_handlers(app):
    """Register all exception handlers with the FastAPI app"""
    app.add_exception_handler(KeyError, handle_key_error)
    app.add_exception_handler(ValueError, handle_value_error)
    app.add_exception_handler(PermissionError, handle_permission_error)
    app.add_exception_handler(APIError, handle_api_error)
