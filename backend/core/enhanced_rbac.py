# backend/core/enhanced_rbac.py

from fastapi import HTTPException, Depends, Request
from typing import List, Dict, Any, Optional, Callable, Union
from functools import wraps
from enum import Enum
import logging
from datetime import datetime, timedelta

from backend.core.rbac_models import RBACUser, RBACRole, RBACPermission
from backend.core.auth import get_current_user

logger = logging.getLogger(__name__)


class ResourceType(str, Enum):
    """Types of resources that can be protected"""
    CUSTOMER = "customer"
    ORDER = "order"
    MENU = "menu"
    REWARD = "reward"
    LOYALTY = "loyalty"
    ANALYTICS = "analytics"
    ADMIN = "admin"
    STAFF = "staff"
    TENANT = "tenant"


class ActionType(str, Enum):
    """Types of actions that can be performed"""
    READ = "read"
    WRITE = "write"
    UPDATE = "update"
    DELETE = "delete"
    CREATE = "create"
    EXECUTE = "execute"
    ADMIN = "admin"
    APPROVE = "approve"
    ISSUE = "issue"
    REDEEM = "redeem"
    PROCESS = "process"


class PermissionScope(str, Enum):
    """Scope of permissions"""
    GLOBAL = "global"          # All tenants
    TENANT = "tenant"          # Specific tenant
    LOCATION = "location"      # Specific location
    DEPARTMENT = "department"  # Specific department
    SELF = "self"             # Own resources only


class EnhancedRBACService:
    """Enhanced RBAC service with advanced permission checking"""
    
    def __init__(self):
        self.permission_cache = {}
        self.cache_ttl = 300  # 5 minutes
    
    def check_permission(
        self,
        user: RBACUser,
        resource: Union[ResourceType, str],
        action: Union[ActionType, str],
        tenant_id: Optional[int] = None,
        resource_id: Optional[int] = None,
        scope: Optional[PermissionScope] = None
    ) -> bool:
        """
        Enhanced permission checking with caching and detailed logging
        """
        # Use default tenant if not specified
        if tenant_id is None:
            tenant_id = user.default_tenant_id
        
        # Generate permission key
        permission_key = f"{resource}:{action}"
        cache_key = f"{user.id}:{permission_key}:{tenant_id}:{resource_id}"
        
        # Check cache first
        cached_result = self._get_cached_permission(cache_key)
        if cached_result is not None:
            return cached_result
        
        # Perform permission check
        has_permission = self._perform_permission_check(
            user, resource, action, tenant_id, resource_id, scope
        )
        
        # Cache result
        self._cache_permission(cache_key, has_permission)
        
        # Log permission check
        logger.info(
            f"Permission check - User: {user.id}, Resource: {resource}, "
            f"Action: {action}, Tenant: {tenant_id}, "
            f"Resource ID: {resource_id}, Result: {has_permission}"
        )
        
        return has_permission
    
    def _perform_permission_check(
        self,
        user: RBACUser,
        resource: Union[ResourceType, str],
        action: Union[ActionType, str],
        tenant_id: int,
        resource_id: Optional[int],
        scope: Optional[PermissionScope]
    ) -> bool:
        """Perform the actual permission check"""
        
        # Check if user is active
        if not user.is_active:
            return False
        
        # Super admin bypass
        if user.is_super_admin:
            return True
        
        # Check tenant membership
        if not self._is_user_in_tenant(user, tenant_id):
            return False
        
        # Build permission string
        permission_str = f"{resource}:{action}"
        
        # Check direct permissions
        if self._has_direct_permission(user, permission_str, tenant_id):
            return True
        
        # Check role-based permissions
        if self._has_role_permission(user, permission_str, tenant_id):
            return True
        
        # Check resource-specific permissions
        if resource_id and self._has_resource_permission(user, permission_str, resource_id, tenant_id):
            return True
        
        # Check hierarchical permissions (e.g., admin implies read/write)
        if self._has_hierarchical_permission(user, resource, action, tenant_id):
            return True
        
        # Check time-based permissions
        if self._has_time_based_permission(user, permission_str, tenant_id):
            return True
        
        return False
    
    def _is_user_in_tenant(self, user: RBACUser, tenant_id: int) -> bool:
        """Check if user belongs to the tenant"""
        return any(
            membership.tenant_id == tenant_id and membership.is_active
            for membership in user.tenant_memberships
        )
    
    def _has_direct_permission(self, user: RBACUser, permission: str, tenant_id: int) -> bool:
        """Check if user has direct permission"""
        return user.has_permission(permission, tenant_id)
    
    def _has_role_permission(self, user: RBACUser, permission: str, tenant_id: int) -> bool:
        """Check if user has permission through roles"""
        user_roles = self._get_user_roles(user, tenant_id)
        
        for role in user_roles:
            if any(perm.name == permission for perm in role.permissions):
                return True
        
        return False
    
    def _has_resource_permission(self, user: RBACUser, permission: str, resource_id: int, tenant_id: int) -> bool:
        """Check resource-specific permissions"""
        # Implementation for resource-specific permissions
        # This would check if user has permission for specific resource instances
        return False
    
    def _has_hierarchical_permission(self, user: RBACUser, resource: str, action: str, tenant_id: int) -> bool:
        """Check hierarchical permissions (admin implies lower permissions)"""
        hierarchy = {
            "admin": ["read", "write", "update", "delete", "create", "execute"],
            "write": ["read"],
            "update": ["read"],
            "delete": ["read"],
            "create": ["read"],
            "approve": ["read", "write"],
            "process": ["read", "write"]
        }
        
        # Check if user has higher-level permission
        for higher_action, implied_actions in hierarchy.items():
            if action in implied_actions:
                higher_permission = f"{resource}:{higher_action}"
                if self._has_direct_permission(user, higher_permission, tenant_id) or \
                   self._has_role_permission(user, higher_permission, tenant_id):
                    return True
        
        return False
    
    def _has_time_based_permission(self, user: RBACUser, permission: str, tenant_id: int) -> bool:
        """Check time-based permissions (business hours, temporary access)"""
        # This would implement time-based access control
        # For now, return False as it's not implemented
        return False
    
    def _get_user_roles(self, user: RBACUser, tenant_id: int) -> List[RBACRole]:
        """Get user roles for specific tenant"""
        return [
            role for role in user.roles
            if any(
                assignment for assignment in user.role_assignments
                if assignment.role_id == role.id and
                assignment.tenant_id == tenant_id and
                assignment.is_active
            )
        ]
    
    def _get_cached_permission(self, cache_key: str) -> Optional[bool]:
        """Get cached permission result"""
        if cache_key in self.permission_cache:
            cached_data = self.permission_cache[cache_key]
            if datetime.utcnow() - cached_data['timestamp'] < timedelta(seconds=self.cache_ttl):
                return cached_data['result']
            else:
                # Cache expired, remove it
                del self.permission_cache[cache_key]
        return None
    
    def _cache_permission(self, cache_key: str, result: bool):
        """Cache permission result"""
        self.permission_cache[cache_key] = {
            'result': result,
            'timestamp': datetime.utcnow()
        }
    
    def clear_user_cache(self, user_id: int):
        """Clear cached permissions for a user"""
        keys_to_remove = [key for key in self.permission_cache.keys() if key.startswith(f"{user_id}:")]
        for key in keys_to_remove:
            del self.permission_cache[key]
    
    def get_user_permissions_summary(self, user: RBACUser, tenant_id: int) -> Dict[str, Any]:
        """Get comprehensive summary of user permissions"""
        roles = self._get_user_roles(user, tenant_id)
        
        # Collect all permissions
        direct_permissions = [perm.name for perm in user.permissions]
        role_permissions = []
        
        for role in roles:
            role_permissions.extend([perm.name for perm in role.permissions])
        
        all_permissions = list(set(direct_permissions + role_permissions))
        
        return {
            "user_id": user.id,
            "tenant_id": tenant_id,
            "is_super_admin": user.is_super_admin,
            "roles": [{"id": role.id, "name": role.name, "description": role.description} for role in roles],
            "direct_permissions": direct_permissions,
            "role_permissions": role_permissions,
            "all_permissions": sorted(all_permissions),
            "permission_count": len(all_permissions)
        }


# Global RBAC service instance
rbac_service = EnhancedRBACService()


# Enhanced permission decorators
def require_permission(
    resource: Union[ResourceType, str],
    action: Union[ActionType, str],
    tenant_id_param: Optional[str] = None,
    resource_id_param: Optional[str] = None,
    scope: Optional[PermissionScope] = None,
    error_message: Optional[str] = None
):
    """
    Enhanced decorator for requiring specific permissions
    
    Args:
        resource: The resource type being accessed
        action: The action being performed
        tenant_id_param: Parameter name containing tenant ID
        resource_id_param: Parameter name containing resource ID
        scope: Permission scope
        error_message: Custom error message
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get current user
            current_user = None
            for arg in args:
                if isinstance(arg, RBACUser):
                    current_user = arg
                    break
            
            if not current_user:
                current_user = kwargs.get('current_user')
            
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            # Extract tenant_id and resource_id from parameters
            tenant_id = None
            if tenant_id_param:
                tenant_id = kwargs.get(tenant_id_param) or getattr(args[0] if args else None, tenant_id_param, None)
            
            resource_id = None
            if resource_id_param:
                resource_id = kwargs.get(resource_id_param) or getattr(args[0] if args else None, resource_id_param, None)
            
            # Check permission
            has_permission = rbac_service.check_permission(
                user=current_user,
                resource=resource,
                action=action,
                tenant_id=tenant_id,
                resource_id=resource_id,
                scope=scope
            )
            
            if not has_permission:
                default_message = f"Insufficient permissions for {resource}:{action}"
                raise HTTPException(
                    status_code=403,
                    detail=error_message or default_message
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_any_permission(*permission_sets):
    """
    Decorator that requires ANY of the specified permission sets
    
    Args:
        permission_sets: Tuples of (resource, action) pairs
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            # Check each permission set
            for resource, action in permission_sets:
                if rbac_service.check_permission(
                    user=current_user,
                    resource=resource,
                    action=action,
                    tenant_id=current_user.default_tenant_id
                ):
                    return await func(*args, **kwargs)
            
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions - none of the required permissions found"
            )
        
        return wrapper
    return decorator


def require_all_permissions(*permission_sets):
    """
    Decorator that requires ALL of the specified permission sets
    
    Args:
        permission_sets: Tuples of (resource, action) pairs
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            # Check all permission sets
            for resource, action in permission_sets:
                if not rbac_service.check_permission(
                    user=current_user,
                    resource=resource,
                    action=action,
                    tenant_id=current_user.default_tenant_id
                ):
                    raise HTTPException(
                        status_code=403,
                        detail=f"Missing required permission: {resource}:{action}"
                    )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_role(role_name: str, tenant_id: Optional[int] = None):
    """
    Decorator that requires a specific role
    
    Args:
        role_name: Name of the required role
        tenant_id: Specific tenant ID (uses default if not provided)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            effective_tenant_id = tenant_id or current_user.default_tenant_id
            user_roles = rbac_service._get_user_roles(current_user, effective_tenant_id)
            
            if not any(role.name == role_name for role in user_roles):
                raise HTTPException(
                    status_code=403,
                    detail=f"Required role '{role_name}' not found"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def owner_or_permission(
    resource: Union[ResourceType, str],
    action: Union[ActionType, str],
    owner_field: str = "user_id"
):
    """
    Decorator that allows access if user is owner OR has permission
    
    Args:
        resource: Resource type
        action: Action type
        owner_field: Field name that contains the owner ID
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            # Check if user is owner
            resource_owner_id = kwargs.get(owner_field)
            if resource_owner_id == current_user.id:
                return await func(*args, **kwargs)
            
            # Check permission
            has_permission = rbac_service.check_permission(
                user=current_user,
                resource=resource,
                action=action,
                tenant_id=current_user.default_tenant_id
            )
            
            if not has_permission:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied - not owner and insufficient permissions"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# Helper functions for permission checking
def check_user_permission(
    user: RBACUser,
    resource: Union[ResourceType, str],
    action: Union[ActionType, str],
    tenant_id: Optional[int] = None
) -> bool:
    """Helper function to check user permission"""
    return rbac_service.check_permission(user, resource, action, tenant_id)


def get_user_permissions_for_tenant(user: RBACUser, tenant_id: int) -> Dict[str, Any]:
    """Helper function to get user permissions summary"""
    return rbac_service.get_user_permissions_summary(user, tenant_id)


# Permission constants for common operations
class CommonPerms:
    # Customer permissions
    CUSTOMER_READ = (ResourceType.CUSTOMER, ActionType.READ)
    CUSTOMER_WRITE = (ResourceType.CUSTOMER, ActionType.WRITE)
    CUSTOMER_CREATE = (ResourceType.CUSTOMER, ActionType.CREATE)
    CUSTOMER_DELETE = (ResourceType.CUSTOMER, ActionType.DELETE)
    
    # Order permissions
    ORDER_READ = (ResourceType.ORDER, ActionType.READ)
    ORDER_WRITE = (ResourceType.ORDER, ActionType.WRITE)
    ORDER_PROCESS = (ResourceType.ORDER, ActionType.PROCESS)
    
    # Reward permissions
    REWARD_READ = (ResourceType.REWARD, ActionType.READ)
    REWARD_ISSUE = (ResourceType.REWARD, ActionType.ISSUE)
    REWARD_REDEEM = (ResourceType.REWARD, ActionType.REDEEM)
    REWARD_ADMIN = (ResourceType.REWARD, ActionType.ADMIN)
    
    # Analytics permissions
    ANALYTICS_READ = (ResourceType.ANALYTICS, ActionType.READ)
    ANALYTICS_ADMIN = (ResourceType.ANALYTICS, ActionType.ADMIN)