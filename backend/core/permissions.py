# backend/core/permissions.py

"""
Core permissions module
"""

from enum import Enum
from typing import List, Optional
from fastapi import HTTPException, status
from .rbac_models import RBACUser as User


class Permission(str, Enum):
    """System permissions"""
    
    # Order permissions
    ORDER_VIEW = "order:view"
    ORDER_CREATE = "order:create"
    ORDER_UPDATE = "order:update"
    ORDER_DELETE = "order:delete"
    ORDER_QUEUE_MANAGE = "order:queue:manage"
    ORDER_PRIORITY_MANAGE = "order:priority:manage"
    
    # Staff permissions
    STAFF_VIEW = "staff:view"
    STAFF_CREATE = "staff:create"
    STAFF_UPDATE = "staff:update"
    STAFF_DELETE = "staff:delete"
    
    # Admin permissions
    ADMIN_ACCESS = "admin:access"
    ADMIN_SETTINGS = "admin:settings"
    

def check_permission(user: User, permission: Permission) -> None:
    """
    Check if user has required permission
    
    Args:
        user: Current user
        permission: Required permission
        
    Raises:
        HTTPException: If user lacks permission
    """
    # Super admin bypass
    if hasattr(user, 'is_superuser') and user.is_superuser:
        return
    
    # Check user's permissions
    user_permissions = set()
    
    # Add direct permissions
    if hasattr(user, 'permissions'):
        user_permissions.update(p.name for p in user.permissions)
    
    # Add role permissions  
    if hasattr(user, 'roles'):
        for role in user.roles:
            if hasattr(role, 'permissions'):
                user_permissions.update(p.name for p in role.permissions)
    
    # Check if user has permission
    if permission.value not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You don't have permission to perform this action: {permission.value}"
        )


def has_permission(user: User, permission: Permission) -> bool:
    """
    Check if user has permission (returns bool instead of raising exception)
    
    Args:
        user: Current user
        permission: Required permission
        
    Returns:
        bool: True if user has permission, False otherwise
    """
    try:
        check_permission(user, permission)
        return True
    except HTTPException:
        return False