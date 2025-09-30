"""Tenant Context Management for Multi-Tenant Isolation.

This module provides middleware and utilities for enforcing tenant isolation
across all database queries and API operations in the AuraConnect system.
"""

import logging
from typing import Optional, Dict, Any, Type, List
from contextvars import ContextVar
from datetime import datetime
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, Query
from sqlalchemy import event, and_
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from core.auth import TokenData, verify_token
from core.auth_context import (
    AuthContextData,
    clear_auth_context,
    set_auth_context,
)

logger = logging.getLogger(__name__)

# Context variable to store current tenant information
_tenant_context: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "tenant_context", default=None
)


class TenantContext:
    """Manages tenant context for the current request"""

    @staticmethod
    def set(
        restaurant_id: Optional[int] = None,
        location_id: Optional[int] = None,
        user_id: Optional[int] = None,
        tenant_id: Optional[int] = None,
        tenant_ids: Optional[List[int]] = None,
        roles: Optional[List[str]] = None,
        username: Optional[str] = None,
    ):
        """Set the tenant context for the current request."""
        effective_restaurant_id = restaurant_id if restaurant_id is not None else tenant_id
        context = {
            "restaurant_id": effective_restaurant_id,
            "location_id": location_id,
            "tenant_id": tenant_id or effective_restaurant_id,
            "tenant_ids": tenant_ids or [],
            "roles": roles or [],
            "user_id": user_id,
            "username": username,
            "timestamp": datetime.utcnow(),
        }
        _tenant_context.set(context)
        return context

    @staticmethod
    def get() -> Optional[Dict[str, Any]]:
        """Get the current tenant context"""
        return _tenant_context.get()

    @staticmethod
    def get_restaurant_id() -> Optional[int]:
        """Get the current restaurant ID from context"""
        context = _tenant_context.get()
        if not context:
            return None
        restaurant_id = context.get("restaurant_id")
        if restaurant_id is None:
            restaurant_id = context.get("tenant_id")
        return restaurant_id

    @staticmethod
    def get_location_id() -> Optional[int]:
        """Get the current location ID from context"""
        context = _tenant_context.get()
        return context.get("location_id") if context else None

    @staticmethod
    def get_user_id() -> Optional[int]:
        """Get the current user ID from context"""
        context = _tenant_context.get()
        return context.get("user_id") if context else None

    @staticmethod
    def get_tenant_id() -> Optional[int]:
        """Get the current tenant ID from context."""
        context = _tenant_context.get()
        return context.get("tenant_id") if context else None

    @staticmethod
    def clear():
        """Clear the tenant context"""
        _tenant_context.set(None)

    @staticmethod
    def require_context():
        """Ensure tenant context is set, raise exception if not"""
        context = _tenant_context.get()
        if not context or (
            context.get("restaurant_id") is None
            and context.get("location_id") is None
            and context.get("tenant_id") is None
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant context not established. Access denied.",
            )
        return context


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce tenant isolation on all requests"""

    # Paths that don't require tenant context
    EXEMPT_PATHS = [
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
    ]

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request, enforce authentication and establish tenant context."""

        # Always clear any prior context at the start of a request
        TenantContext.clear()
        clear_auth_context()

        # Skip tenant isolation for exempt paths
        if any(request.url.path.startswith(path) for path in self.EXEMPT_PATHS):
            return await call_next(request)

        try:
            token_data = await self._extract_token_data(request)
            if token_data is None:
                logger.warning(
                    "Tenant context denied for %s %s (missing or invalid token)",
                    request.method,
                    request.url.path,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Tenant context required for this operation",
                )

            active_tenant_id = self._resolve_active_tenant_id(request, token_data)
            if active_tenant_id is None:
                logger.warning(
                    "Unable to resolve tenant for user %s on %s %s",
                    token_data.user_id,
                    request.method,
                    request.url.path,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Valid tenant selection required",
                )

            roles = token_data.roles or []
            tenant_ids = token_data.tenant_ids or []

            # Persist tenant context for downstream code paths
            TenantContext.set(
                restaurant_id=active_tenant_id,
                tenant_id=active_tenant_id,
                tenant_ids=tenant_ids,
                roles=roles,
                user_id=token_data.user_id,
                username=token_data.username,
            )

            # Store auth context so services can retrieve roles/tenant data
            set_auth_context(
                AuthContextData(
                    user_id=token_data.user_id,
                    username=token_data.username or "",
                    roles=roles,
                    tenant_ids=tenant_ids,
                    active_tenant_id=active_tenant_id,
                    email=getattr(token_data, "email", None),
                )
            )

            # Populate request state for middleware that inspects it later
            request.state.user_id = token_data.user_id
            request.state.user_roles = roles
            request.state.user_role = roles[0] if roles else None
            request.state.tenant_id = active_tenant_id
            request.state.tenant_ids = tenant_ids
            request.state.username = token_data.username

            logger.info(
                "Tenant context established for user %s (tenant %s) on %s %s",
                token_data.username or token_data.user_id,
                active_tenant_id,
                request.method,
                request.url.path,
            )

            response = await call_next(request)
            return response

        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Error in tenant isolation middleware: %s", exc)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"},
            )
        finally:
            # Ensure contexts are cleared once the response is generated
            TenantContext.clear()
            clear_auth_context()

    async def _extract_token_data(self, request: Request) -> Optional[TokenData]:
        """Extract and validate the JWT token from the incoming request."""

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return None

        token = auth_header.split(" ", 1)[1].strip()
        token_data = verify_token(token)
        if token_data is None or token_data.user_id is None:
            return None
        return token_data

    def _resolve_active_tenant_id(
        self, request: Request, token_data: TokenData
    ) -> Optional[int]:
        """Determine which tenant should be active for this request."""

        candidate = self._extract_candidate_tenant(request)
        token_tenants = token_data.tenant_ids or []

        if candidate is not None:
            if candidate in token_tenants:
                return candidate
            logger.warning(
                "Tenant override %s rejected for user %s", candidate, token_data.user_id
            )
            return None

        if token_tenants:
            return token_tenants[0]

        return None

    @staticmethod
    def _extract_candidate_tenant(request: Request) -> Optional[int]:
        """Read tenant overrides from headers or query parameters."""

        header_value = request.headers.get("X-Tenant-ID")
        if header_value:
            try:
                return int(header_value)
            except ValueError:
                logger.warning("Invalid X-Tenant-ID header value: %s", header_value)
                return None

        query_value = request.query_params.get("tenant_id")
        if query_value:
            try:
                return int(query_value)
            except ValueError:
                logger.warning("Invalid tenant_id query parameter: %s", query_value)
                return None

        return None


class CrossTenantAccessLogger:
    """Logger for detecting and recording cross-tenant access attempts"""

    def __init__(self, db: Session):
        self.db = db

    def log_access_attempt(
        self,
        requested_tenant_id: int,
        actual_tenant_id: int,
        resource_type: str,
        resource_id: Any,
        action: str,
        user_id: Optional[int] = None,
        success: bool = False,
    ):
        """Log a cross-tenant access attempt"""

        if requested_tenant_id != actual_tenant_id:
            log_entry = {
                "timestamp": datetime.utcnow(),
                "user_id": user_id or TenantContext.get_user_id(),
                "requested_tenant_id": requested_tenant_id,
                "actual_tenant_id": actual_tenant_id,
                "resource_type": resource_type,
                "resource_id": str(resource_id),
                "action": action,
                "success": success,
                "severity": "CRITICAL" if success else "WARNING",
            }

            # Log to application logger
            logger.critical(
                f"CROSS-TENANT ACCESS ATTEMPT: User {log_entry['user_id']} tried to {action} "
                f"{resource_type}:{resource_id} from tenant {actual_tenant_id} "
                f"while in context of tenant {requested_tenant_id}. "
                f"Success: {success}"
            )

            # TODO: Store in database audit table
            # self.db.add(CrossTenantAccessLog(**log_entry))
            # self.db.commit()

            # Raise alert if successful breach
            if success:
                self._raise_security_alert(log_entry)

    def _raise_security_alert(self, log_entry: Dict[str, Any]):
        """Raise immediate security alert for successful cross-tenant access"""
        # TODO: Integrate with alerting system (email, Slack, PagerDuty, etc.)
        logger.critical(
            f"SECURITY ALERT: Successful cross-tenant data breach detected! {log_entry}"
        )


def apply_tenant_filter(query: Query, model_class: Type) -> Query:
    """Apply tenant filtering to a SQLAlchemy query based on current context"""

    context = TenantContext.get()
    if not context:
        # No context means no access
        logger.warning(
            f"Query attempted without tenant context for model {model_class.__name__}"
        )
        # Return a query that will return no results
        return query.filter(False)

    restaurant_id = context.get("restaurant_id")
    location_id = context.get("location_id")

    # Map model to appropriate tenant field
    tenant_fields = {
        "Order": ["restaurant_id", "location_id"],
        "Customer": ["restaurant_id"],
        "MenuItem": ["restaurant_id"],
        "StaffMember": ["location_id"],
        "Inventory": ["location_id"],
        "CustomerSegment": ["restaurant_id"],
        "SalesAnalyticsSnapshot": ["restaurant_id", "location_id"],
        "Promotion": ["restaurant_id"],
        "LoyaltyProgram": ["restaurant_id"],
        "Feedback": ["restaurant_id", "location_id"],
    }

    model_name = model_class.__name__
    fields = tenant_fields.get(model_name, [])

    filters = []
    for field in fields:
        if (
            field == "restaurant_id"
            and restaurant_id is not None
            and hasattr(model_class, "restaurant_id")
        ):
            filters.append(model_class.restaurant_id == restaurant_id)
        elif (
            field == "location_id"
            and location_id is not None
            and hasattr(model_class, "location_id")
        ):
            filters.append(model_class.location_id == location_id)

    if filters:
        query = query.filter(and_(*filters))
    else:
        # Log models without tenant fields
        logger.warning(f"Model {model_name} has no tenant isolation fields configured")

    return query


def validate_tenant_access(entity: Any, raise_on_violation: bool = True) -> bool:
    """Validate that an entity belongs to the current tenant context"""

    context = TenantContext.get()
    if not context:
        if raise_on_violation:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tenant context established",
            )
        return False

    restaurant_id = context.get("restaurant_id")
    location_id = context.get("location_id")

    # Check if entity has tenant fields and they match context
    valid = True

    if hasattr(entity, "restaurant_id") and entity.restaurant_id is not None:
        if restaurant_id is not None and entity.restaurant_id != restaurant_id:
            valid = False
            logger.warning(
                f"Tenant violation: Entity {entity.__class__.__name__}:{entity.id if hasattr(entity, 'id') else 'unknown'} "
                f"restaurant_id {entity.restaurant_id} != context {restaurant_id}"
            )

    if hasattr(entity, "location_id") and entity.location_id is not None:
        if location_id is not None and entity.location_id != location_id:
            valid = False
            logger.warning(
                f"Tenant violation: Entity {entity.__class__.__name__}:{entity.id if hasattr(entity, 'id') else 'unknown'} "
                f"location_id {entity.location_id} != context {location_id}"
            )

    if not valid and raise_on_violation:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Resource belongs to different tenant",
        )

    return valid


def tenant_scope_dependency(db: Session):
    """FastAPI dependency to ensure tenant context and return scoped query helper"""

    context = TenantContext.require_context()

    def scoped_query(model_class: Type) -> Query:
        """Create a tenant-scoped query for the given model"""
        query = db.query(model_class)
        return apply_tenant_filter(query, model_class)

    return scoped_query


# SQLAlchemy event listeners for automatic tenant filtering
def setup_tenant_filtering():
    """Setup SQLAlchemy event listeners for automatic tenant filtering"""

    @event.listens_for(Query, "before_compile", propagate=True)
    def receive_before_compile(query, compile_context):
        """Automatically apply tenant filters to queries"""
        # This is a more advanced implementation that would require
        # deeper integration with SQLAlchemy's query compilation
        pass
