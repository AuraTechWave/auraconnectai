# backend/modules/auth/permissions.py

from enum import Enum
from typing import List, Optional
from fastapi import HTTPException, status

from modules.auth.models import User


class Permission(str, Enum):
    """System permissions"""

    # Analytics permissions
    VIEW_DASHBOARD = "analytics:view_dashboard"
    VIEW_PREDICTIONS = "analytics:view_predictions"

    # Menu permissions
    MENU_VIEW = "menu:read"
    MENU_CREATE = "menu:create"
    MENU_UPDATE = "menu:update"
    MENU_DELETE = "menu:delete"

    # Order permissions
    ORDER_VIEW = "order:read"
    ORDER_CREATE = "order:create"
    ORDER_UPDATE = "order:update"
    ORDER_DELETE = "order:delete"

    # Equipment permissions
    EQUIPMENT_VIEW = "equipment:view"
    EQUIPMENT_CREATE = "equipment:create"
    EQUIPMENT_UPDATE = "equipment:update"
    EQUIPMENT_DELETE = "equipment:delete"

    # Staff permissions
    STAFF_VIEW = "staff:view"
    STAFF_CREATE = "staff:create"
    STAFF_UPDATE = "staff:update"
    STAFF_DELETE = "staff:delete"

    # Payroll permissions
    PAYROLL_VIEW = "payroll:view"
    PAYROLL_PROCESS = "payroll:process"
    PAYROLL_APPROVE = "payroll:approve"

    # Inventory permissions
    INVENTORY_VIEW = "inventory:view"
    INVENTORY_CREATE = "inventory:create"
    INVENTORY_UPDATE = "inventory:update"
    INVENTORY_DELETE = "inventory:delete"

    # Customer permissions
    CUSTOMER_VIEW = "customer:view"
    CUSTOMER_CREATE = "customer:create"
    CUSTOMER_UPDATE = "customer:update"
    CUSTOMER_DELETE = "customer:delete"

    # Admin permissions
    ADMIN_ACCESS = "admin:access"
    ADMIN_USERS = "admin:users"
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
    if user.is_superuser:
        return

    # Check user's direct permissions
    user_permissions = set()
    if hasattr(user, "permissions"):
        user_permissions.update(p.name for p in user.permissions)

    # Check role permissions
    if hasattr(user, "roles"):
        for role in user.roles:
            if hasattr(role, "permissions"):
                user_permissions.update(p.name for p in role.permissions)

    # Check if user has permission
    if permission.value not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You don't have permission to perform this action: {permission.value}",
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


def get_user_permissions(user: User) -> List[str]:
    """
    Get all permissions for a user

    Args:
        user: User to get permissions for

    Returns:
        List of permission strings
    """
    if user.is_superuser:
        # Return all permissions for superuser
        return [p.value for p in Permission]

    permissions = set()

    # Add direct permissions
    if hasattr(user, "permissions"):
        permissions.update(p.name for p in user.permissions)

    # Add role permissions
    if hasattr(user, "roles"):
        for role in user.roles:
            if hasattr(role, "permissions"):
                permissions.update(p.name for p in role.permissions)

    return list(permissions)
