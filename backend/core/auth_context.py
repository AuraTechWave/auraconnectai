"""Request-scoped authentication context utilities.

Provides helpers to store and retrieve the authenticated user and
associated tenant metadata using ``contextvars`` so downstream services
have reliable access to the auth claims extracted from JWTs.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class AuthContextData:
    """Represents the authenticated user and tenant context for a request."""

    user_id: int
    username: str
    roles: List[str]
    tenant_ids: List[int]
    active_tenant_id: Optional[int] = None
    email: Optional[str] = None

    def has_role(self, role: str) -> bool:
        """Return ``True`` if the user currently holds the specified role."""
        return role in self.roles


_auth_context: ContextVar[Optional[AuthContextData]] = ContextVar(
    "auth_context", default=None
)


def set_auth_context(context: AuthContextData) -> None:
    """Persist the authentication context for the active request."""
    _auth_context.set(context)


def get_auth_context() -> Optional[AuthContextData]:
    """Fetch the current authentication context if one has been established."""
    return _auth_context.get()


def clear_auth_context() -> None:
    """Clear any stored authentication context for the active request."""
    _auth_context.set(None)
