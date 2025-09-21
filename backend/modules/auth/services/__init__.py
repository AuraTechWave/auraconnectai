"""Service-level helpers for authentication.

This package wraps the lower-level helpers in ``core.auth`` so legacy
imports (``modules.auth.services``) continue to function.
"""

from core.auth import (  # noqa: F401
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_current_user,
    logout_user,
    refresh_access_token,
    verify_password,
)

from .auth_service import AuthService  # noqa: F401

__all__ = [
    "authenticate_user",
    "create_access_token",
    "create_refresh_token",
    "get_current_user",
    "logout_user",
    "refresh_access_token",
    "verify_password",
    "AuthService",
]
