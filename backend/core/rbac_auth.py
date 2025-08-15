"""
Enhanced Authentication with RBAC Integration

This module provides authentication dependencies and decorators that integrate
with the RBAC system for fine-grained permission checking.
"""

from typing import List, Optional, Callable, Union
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import logging

from .auth import verify_token, TokenData
from .database import get_db
from .rbac_service import RBACService, get_rbac_service
from .rbac_models import RBACUser
from .config import settings

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


class RBACDependency:
    """
    FastAPI dependency class for RBAC-based authentication and authorization.

    This provides a more flexible and powerful alternative to the simple role checking
    in the original auth.py module.
    """

    def __init__(
        self,
        required_permissions: List[str] = None,
        required_roles: List[str] = None,
        require_all_permissions: bool = True,
        require_all_roles: bool = False,
        allow_admin_override: bool = True,
        tenant_aware: bool = False,
    ):
        """
        Initialize RBAC dependency.

        Args:
            required_permissions: List of permission keys required
            required_roles: List of role names required
            require_all_permissions: If True, user must have ALL permissions
            require_all_roles: If True, user must have ALL roles
            allow_admin_override: If True, admin role bypasses all checks
            tenant_aware: If True, check permissions within tenant context
        """
        self.required_permissions = required_permissions or []
        self.required_roles = required_roles or []
        self.require_all_permissions = require_all_permissions
        self.require_all_roles = require_all_roles
        self.allow_admin_override = allow_admin_override
        self.tenant_aware = tenant_aware

    def __call__(
        self,
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        rbac_service: RBACService = Depends(get_rbac_service),
    ) -> RBACUser:
        """
        Dependency function that validates authentication and authorization.

        Returns:
            RBACUser: The authenticated and authorized user

        Raises:
            HTTPException: If authentication or authorization fails
        """

        # Check authentication
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verify JWT token
        token_data = verify_token(credentials.credentials)
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Get user from RBAC system
        user = rbac_service.get_user_by_id(token_data.user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        # Extract tenant context if needed
        tenant_id = None
        if self.tenant_aware:
            # Try to get tenant from request state first
            tenant_id = getattr(request.state, "tenant_id", None)

            # Fallback to user's default tenant if not specified
            if tenant_id is None:
                tenant_id = user.default_tenant_id
                if tenant_id:
                    logger.warning(
                        f"No tenant_id in request state for user {user.username}, "
                        f"falling back to default tenant {tenant_id}"
                    )
                else:
                    logger.warning(
                        f"No tenant_id in request state and no default tenant for user {user.username}"
                    )

        # Admin override check (controlled by environment configuration)
        if (
            self.allow_admin_override
            and settings.rbac_admin_override_enabled
            and user.has_role("admin", tenant_id)
        ):
            logger.debug(f"Admin override for user {user.username}")
            return user

        # Check required roles
        if self.required_roles:
            user_roles = [
                role.name for role in rbac_service.get_user_roles(user.id, tenant_id)
            ]

            if self.require_all_roles:
                missing_roles = set(self.required_roles) - set(user_roles)
                if missing_roles:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Missing required roles: {list(missing_roles)}",
                    )
            else:
                if not any(role in user_roles for role in self.required_roles):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Requires one of these roles: {self.required_roles}",
                    )

        # Check required permissions
        if self.required_permissions:
            if self.require_all_permissions:
                for permission in self.required_permissions:
                    if not rbac_service.check_user_permission(
                        user.id, permission, tenant_id
                    ):
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Missing required permission: {permission}",
                        )
            else:
                has_any_permission = any(
                    rbac_service.check_user_permission(user.id, permission, tenant_id)
                    for permission in self.required_permissions
                )
                if not has_any_permission:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Requires one of these permissions: {self.required_permissions}",
                    )

        logger.debug(f"RBAC check passed for user {user.username}")
        return user


# Convenience dependency functions


def require_permission(permission: str, tenant_aware: bool = True) -> Callable:
    """Require a single permission."""
    return RBACDependency(required_permissions=[permission], tenant_aware=tenant_aware)


def require_permissions(
    permissions: List[str], require_all: bool = True, tenant_aware: bool = True
) -> Callable:
    """Require multiple permissions."""
    return RBACDependency(
        required_permissions=permissions,
        require_all_permissions=require_all,
        tenant_aware=tenant_aware,
    )


def require_role(role: str, tenant_aware: bool = True) -> Callable:
    """Require a single role."""
    return RBACDependency(required_roles=[role], tenant_aware=tenant_aware)


def require_roles(
    roles: List[str], require_all: bool = False, tenant_aware: bool = True
) -> Callable:
    """Require multiple roles."""
    return RBACDependency(
        required_roles=roles, require_all_roles=require_all, tenant_aware=tenant_aware
    )


def require_admin(tenant_aware: bool = False) -> Callable:
    """Require admin role."""
    return RBACDependency(required_roles=["admin"], tenant_aware=tenant_aware)


# Resource-specific permission dependencies

# Staff Management
require_staff_read = require_permission("staff:read")
require_staff_write = require_permission("staff:write")
require_staff_delete = require_permission("staff:delete")
require_staff_schedule = require_permission("staff:manage_schedule")

# Payroll Management
require_payroll_read = require_permission("payroll:read")
require_payroll_write = require_permission("payroll:write")
require_payroll_approve = require_permission("payroll:approve")
require_payroll_export = require_permission("payroll:export")

# Order Management
require_order_read = require_permission("order:read")
require_order_write = require_permission("order:write")
require_order_delete = require_permission("order:delete")
require_kitchen_access = require_permission("order:manage_kitchen")

# User Management
require_user_read = require_permission("user:read")
require_user_write = require_permission("user:write")
require_user_delete = require_permission("user:delete")
require_user_role_management = require_permission("user:manage_roles")

# System Administration
require_system_read = require_permission("system:read")
require_system_write = require_permission("system:write")
require_system_audit = require_permission("system:audit")


# Enhanced authentication for optional access


async def get_current_user_rbac(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    rbac_service: RBACService = Depends(get_rbac_service),
) -> Optional[RBACUser]:
    """
    Get current user with RBAC support, but don't require authentication.

    Returns None if not authenticated, RBACUser if authenticated.
    """
    if not credentials:
        return None

    token_data = verify_token(credentials.credentials)
    if not token_data:
        return None

    user = rbac_service.get_user_by_id(token_data.user_id)
    if not user or not user.is_active:
        return None

    return user


async def get_current_user_required_rbac(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    rbac_service: RBACService = Depends(get_rbac_service),
) -> RBACUser:
    """
    Get current user with RBAC support, require authentication.

    Raises HTTPException if not authenticated.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = verify_token(credentials.credentials)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = rbac_service.get_user_by_id(token_data.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


# Tenant context management


class TenantContextManager:
    """Manages tenant context for multi-tenant RBAC operations."""

    def __init__(self, request: Request):
        self.request = request

    def get_tenant_id(self) -> Optional[int]:
        """Extract tenant ID from request context."""

        # Try to get from request state (set by middleware)
        if hasattr(self.request.state, "tenant_id"):
            return self.request.state.tenant_id

        # Try to get from headers
        tenant_header = self.request.headers.get("X-Tenant-ID")
        if tenant_header:
            try:
                return int(tenant_header)
            except ValueError:
                pass

        # Try to get from query parameters
        tenant_query = self.request.query_params.get("tenant_id")
        if tenant_query:
            try:
                return int(tenant_query)
            except ValueError:
                pass

        return None

    def set_tenant_id(self, tenant_id: int):
        """Set tenant ID in request state."""
        self.request.state.tenant_id = tenant_id


def get_tenant_context(request: Request) -> TenantContextManager:
    """Get tenant context manager for request."""
    return TenantContextManager(request)


# Middleware for automatic tenant detection


class TenantDetectionMiddleware:
    """Middleware to automatically detect and set tenant context."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope, receive)

            # Extract tenant from various sources
            tenant_id = None

            # From JWT token if available
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                token_data = verify_token(token)
                if token_data and token_data.tenant_ids:
                    # Use first tenant ID or default
                    tenant_id = token_data.tenant_ids[0]

            # Override with explicit tenant header
            explicit_tenant = request.headers.get("X-Tenant-ID")
            if explicit_tenant:
                try:
                    tenant_id = int(explicit_tenant)
                except ValueError:
                    pass

            # Set in request state
            if tenant_id:
                scope["state"] = scope.get("state", {})
                scope["state"]["tenant_id"] = tenant_id

        await self.app(scope, receive, send)
