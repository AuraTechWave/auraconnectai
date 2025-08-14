"""Tenant Context Management for Multi-Tenant Isolation

This module provides middleware and utilities for enforcing tenant isolation
across all database queries and API operations in the AuraConnect system.
"""

import logging
from typing import Optional, List, Dict, Any, Type
from contextvars import ContextVar
from datetime import datetime
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, Query, Mapper
from sqlalchemy import event, and_, or_, inspect
from sqlalchemy.sql import Select
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from core.auth import verify_token
from core.database import SessionLocal

logger = logging.getLogger(__name__)

# Context variable to store current tenant information
_tenant_context: ContextVar[Optional[Dict[str, Any]]] = ContextVar('tenant_context', default=None)


class TenantContext:
    """Manages tenant context for the current request"""
    
    @staticmethod
    def set(restaurant_id: Optional[int] = None, location_id: Optional[int] = None, user_id: Optional[int] = None):
        """Set the tenant context for the current request"""
        context = {
            'restaurant_id': restaurant_id,
            'location_id': location_id,
            'user_id': user_id,
            'timestamp': datetime.utcnow()
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
        return context.get('restaurant_id') if context else None
    
    @staticmethod
    def get_location_id() -> Optional[int]:
        """Get the current location ID from context"""
        context = _tenant_context.get()
        return context.get('location_id') if context else None
    
    @staticmethod
    def get_user_id() -> Optional[int]:
        """Get the current user ID from context"""
        context = _tenant_context.get()
        return context.get('user_id') if context else None
    
    @staticmethod
    def clear():
        """Clear the tenant context"""
        _tenant_context.set(None)
    
    @staticmethod
    def require_context():
        """Ensure tenant context is set, raise exception if not"""
        context = _tenant_context.get()
        if not context or not (context.get('restaurant_id') or context.get('location_id')):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant context not established. Access denied."
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
        """Process request and set tenant context"""
        
        # Skip tenant isolation for exempt paths
        if any(request.url.path.startswith(path) for path in self.EXEMPT_PATHS):
            return await call_next(request)
        
        # Clear any previous context
        TenantContext.clear()
        
        try:
            # Extract tenant information from JWT token
            tenant_info = await self._extract_tenant_info(request)
            
            if not tenant_info:
                # Log potential cross-tenant access attempt
                logger.warning(
                    f"No tenant context found for request: {request.method} {request.url.path} "
                    f"from {request.client.host if request.client else 'unknown'}"
                )
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Tenant context required for this operation"}
                )
            
            # Set tenant context
            TenantContext.set(
                restaurant_id=tenant_info.get('restaurant_id'),
                location_id=tenant_info.get('location_id'),
                user_id=tenant_info.get('user_id')
            )
            
            # Log the request with tenant context
            logger.info(
                f"Request with tenant context - Restaurant: {tenant_info.get('restaurant_id')}, "
                f"Location: {tenant_info.get('location_id')}, User: {tenant_info.get('user_id')}, "
                f"Path: {request.method} {request.url.path}"
            )
            
            # Process the request
            response = await call_next(request)
            
            # Clear context after request
            TenantContext.clear()
            
            return response
            
        except HTTPException as e:
            # Clear context on error
            TenantContext.clear()
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail}
            )
        except Exception as e:
            # Clear context on error
            TenantContext.clear()
            logger.error(f"Error in tenant isolation middleware: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"}
            )
    
    async def _extract_tenant_info(self, request: Request) -> Optional[Dict[str, Any]]:
        """Extract tenant information from request (JWT token)"""
        
        # Get authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        
        token = auth_header.split(" ")[1]
        
        try:
            # Verify token and extract payload
            payload = verify_token(token)
            
            # Extract tenant information from token payload
            # This assumes the JWT contains restaurant_id and/or location_id claims
            return {
                'restaurant_id': payload.get('restaurant_id'),
                'location_id': payload.get('location_id'),
                'user_id': payload.get('sub')  # Standard JWT subject claim
            }
        except Exception as e:
            logger.error(f"Error extracting tenant info from token: {str(e)}")
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
        success: bool = False
    ):
        """Log a cross-tenant access attempt"""
        
        if requested_tenant_id != actual_tenant_id:
            log_entry = {
                'timestamp': datetime.utcnow(),
                'user_id': user_id or TenantContext.get_user_id(),
                'requested_tenant_id': requested_tenant_id,
                'actual_tenant_id': actual_tenant_id,
                'resource_type': resource_type,
                'resource_id': str(resource_id),
                'action': action,
                'success': success,
                'severity': 'CRITICAL' if success else 'WARNING'
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
        logger.critical(f"SECURITY ALERT: Successful cross-tenant data breach detected! {log_entry}")


def apply_tenant_filter(query: Query, model_class: Type) -> Query:
    """Apply tenant filtering to a SQLAlchemy query based on current context"""
    
    context = TenantContext.get()
    if not context:
        # No context means no access
        logger.warning(f"Query attempted without tenant context for model {model_class.__name__}")
        # Return a query that will return no results
        return query.filter(False)
    
    restaurant_id = context.get('restaurant_id')
    location_id = context.get('location_id')
    
    # Map model to appropriate tenant field
    tenant_fields = {
        'Order': ['restaurant_id', 'location_id'],
        'Customer': ['restaurant_id'],
        'MenuItem': ['restaurant_id'],
        'StaffMember': ['location_id'],
        'Inventory': ['location_id'],
        'CustomerSegment': ['restaurant_id'],
        'SalesAnalyticsSnapshot': ['restaurant_id', 'location_id'],
        'Promotion': ['restaurant_id'],
        'LoyaltyProgram': ['restaurant_id'],
        'Feedback': ['restaurant_id', 'location_id'],
    }
    
    model_name = model_class.__name__
    fields = tenant_fields.get(model_name, [])
    
    filters = []
    for field in fields:
        if field == 'restaurant_id' and restaurant_id and hasattr(model_class, 'restaurant_id'):
            filters.append(model_class.restaurant_id == restaurant_id)
        elif field == 'location_id' and location_id and hasattr(model_class, 'location_id'):
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
                detail="No tenant context established"
            )
        return False
    
    restaurant_id = context.get('restaurant_id')
    location_id = context.get('location_id')
    
    # Check if entity has tenant fields and they match context
    valid = True
    
    if hasattr(entity, 'restaurant_id') and entity.restaurant_id:
        if restaurant_id and entity.restaurant_id != restaurant_id:
            valid = False
            logger.warning(
                f"Tenant violation: Entity {entity.__class__.__name__}:{entity.id if hasattr(entity, 'id') else 'unknown'} "
                f"restaurant_id {entity.restaurant_id} != context {restaurant_id}"
            )
    
    if hasattr(entity, 'location_id') and entity.location_id:
        if location_id and entity.location_id != location_id:
            valid = False
            logger.warning(
                f"Tenant violation: Entity {entity.__class__.__name__}:{entity.id if hasattr(entity, 'id') else 'unknown'} "
                f"location_id {entity.location_id} != context {location_id}"
            )
    
    if not valid and raise_on_violation:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Resource belongs to different tenant"
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