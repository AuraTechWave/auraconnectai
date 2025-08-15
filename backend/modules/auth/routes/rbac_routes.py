"""
RBAC Management Routes

This module provides REST API endpoints for managing the Role-Based Access Control
system, including user management, role assignment, permission management, and
session operations.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from core.database import get_db
from core.auth import get_current_user, require_admin
from core.rbac_service import RBACService, get_rbac_service
from core.auth import User, RBACRole, RBACPermission, RBACSession
from datetime import datetime, timedelta

router = APIRouter(prefix="/rbac", tags=["RBAC Management"])


# Pydantic Models for Request/Response


class UserCreateRequest(BaseModel):
    username: str
    email: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    accessible_tenant_ids: List[int] = []
    default_tenant_id: Optional[int] = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    is_active: bool
    is_email_verified: bool
    created_at: datetime
    last_login: Optional[datetime]
    accessible_tenant_ids: List[int]
    default_tenant_id: Optional[int]

    class Config:
        from_attributes = True


class RoleCreateRequest(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None
    parent_role_id: Optional[int] = None
    tenant_ids: List[int] = []


class RoleResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str]
    parent_role_id: Optional[int]
    is_active: bool
    is_system_role: bool
    created_at: datetime
    tenant_ids: List[int]

    class Config:
        from_attributes = True


class PermissionResponse(BaseModel):
    id: int
    key: str
    name: str
    description: Optional[str]
    resource: str
    action: str
    is_active: bool
    is_system_permission: bool
    tenant_ids: List[int]

    class Config:
        from_attributes = True


class RoleAssignmentRequest(BaseModel):
    user_id: int
    role_id: int
    tenant_id: Optional[int] = None
    expires_at: Optional[datetime] = None


class PermissionAssignmentRequest(BaseModel):
    role_id: int
    permission_id: int


class DirectPermissionRequest(BaseModel):
    user_id: int
    permission_key: str
    tenant_id: Optional[int] = None
    resource_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    reason: Optional[str] = None


class BulkUserOperationRequest(BaseModel):
    user_ids: List[int]


class BulkRoleAssignmentRequest(BaseModel):
    user_ids: List[int]
    role_id: int
    tenant_id: Optional[int] = None


class UserPermissionsResponse(BaseModel):
    user_id: int
    username: str
    tenant_id: Optional[int]
    permissions: List[str]
    roles: List[str]


class PermissionCheckRequest(BaseModel):
    user_id: int
    permission_key: str
    tenant_id: Optional[int] = None
    resource_id: Optional[str] = None


class PermissionCheckResponse(BaseModel):
    user_id: int
    permission_key: str
    has_permission: bool
    granted_by: Optional[str] = None  # "role:role_name" or "direct"


class AuditLogEntry(BaseModel):
    id: int
    action: str
    entity_type: str
    entity_id: Optional[int]
    details: Optional[str]
    performed_by_user_id: int
    performed_by_username: str
    tenant_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    entries: List[AuditLogEntry]
    total_count: int
    page: int
    page_size: int


# User Management Endpoints


@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreateRequest,
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin),
):
    """Create a new user."""
    try:
        user = rbac_service.create_user(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            accessible_tenant_ids=user_data.accessible_tenant_ids,
            default_tenant_id=user_data.default_tenant_id,
        )
        return UserResponse.from_orm(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class PaginatedUserResponse(BaseModel):
    items: List[UserResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int


@router.get("/users", response_model=PaginatedUserResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin),
):
    """List users with pagination, search, and filtering."""

    # Verify current user has user:read permission
    if not rbac_service.check_user_permission(current_user.id, "user:read"):
        raise HTTPException(
            status_code=403, detail="Insufficient permissions: user:read required"
        )

    query = rbac_service.db.query(User)

    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (User.username.ilike(search_term))
            | (User.email.ilike(search_term))
            | (User.first_name.ilike(search_term))
            | (User.last_name.ilike(search_term))
        )

    # Apply active status filter
    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    # Count total results
    total_count = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    users = query.offset(offset).limit(page_size).all()

    total_pages = (total_count + page_size - 1) // page_size

    return PaginatedUserResponse(
        items=[UserResponse.from_orm(user) for user in users],
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin),
):
    """Get user by ID."""
    user = rbac_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.from_orm(user)


@router.get("/users/{user_id}/permissions", response_model=UserPermissionsResponse)
async def get_user_permissions(
    user_id: int,
    tenant_id: Optional[int] = Query(None),
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin),
):
    """Get all permissions for a user."""
    user = rbac_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    permissions = rbac_service.get_user_permissions(user_id, tenant_id)
    roles = rbac_service.get_user_roles(user_id, tenant_id)
    role_names = [role.name for role in roles]

    return UserPermissionsResponse(
        user_id=user_id,
        username=user.username,
        tenant_id=tenant_id,
        permissions=permissions,
        roles=role_names,
    )


# Role Management Endpoints


@router.post("/roles", response_model=RoleResponse)
async def create_role(
    role_data: RoleCreateRequest,
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin),
):
    """Create a new role."""
    try:
        role = rbac_service.create_role(
            name=role_data.name,
            display_name=role_data.display_name,
            description=role_data.description,
            parent_role_id=role_data.parent_role_id,
            tenant_ids=role_data.tenant_ids,
        )
        return RoleResponse.from_orm(role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin),
):
    """List all roles."""
    roles = rbac_service.db.query(RBACRole).offset(skip).limit(limit).all()
    return [RoleResponse.from_orm(role) for role in roles]


@router.get("/roles/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: int,
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin),
):
    """Get role by ID."""
    role = rbac_service.get_role_by_id(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return RoleResponse.from_orm(role)


# Permission Management Endpoints


@router.get("/permissions", response_model=List[PermissionResponse])
async def list_permissions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    resource: Optional[str] = Query(None),
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin),
):
    """List all permissions."""
    query = rbac_service.db.query(RBACPermission)

    if resource:
        query = query.filter(RBACPermission.resource == resource)

    permissions = query.offset(skip).limit(limit).all()
    return [PermissionResponse.from_orm(perm) for perm in permissions]


@router.get("/permissions/{permission_id}", response_model=PermissionResponse)
async def get_permission(
    permission_id: int,
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin),
):
    """Get permission by ID."""
    permission = (
        rbac_service.db.query(RBACPermission)
        .filter(RBACPermission.id == permission_id)
        .first()
    )

    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")

    return PermissionResponse.from_orm(permission)


# Role Assignment Endpoints


@router.post("/assign-role")
async def assign_role_to_user(
    assignment: RoleAssignmentRequest,
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin),
):
    """Assign a role to a user."""

    # Verify user exists
    user = rbac_service.get_user_by_id(assignment.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify role exists
    role = rbac_service.get_role_by_id(assignment.role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    success = rbac_service.assign_role_to_user(
        user_id=assignment.user_id,
        role_id=assignment.role_id,
        tenant_id=assignment.tenant_id,
        granted_by_user_id=current_user.id,
        expires_at=assignment.expires_at,
    )

    if not success:
        raise HTTPException(status_code=400, detail="Failed to assign role")

    return {"message": f"Role {role.name} assigned to user {user.username}"}


@router.post("/remove-role")
async def remove_role_from_user(
    assignment: RoleAssignmentRequest,
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin),
):
    """Remove a role from a user."""

    success = rbac_service.remove_role_from_user(
        user_id=assignment.user_id, role_id=assignment.role_id
    )

    if not success:
        raise HTTPException(status_code=404, detail="Role assignment not found")

    return {"message": "Role removed from user"}


# Permission Assignment Endpoints


@router.post("/assign-permission")
async def assign_permission_to_role(
    assignment: PermissionAssignmentRequest,
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin),
):
    """Assign a permission to a role."""

    # Verify role exists
    role = rbac_service.get_role_by_id(assignment.role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # Verify permission exists
    permission = (
        rbac_service.db.query(RBACPermission)
        .filter(RBACPermission.id == assignment.permission_id)
        .first()
    )
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")

    success = rbac_service.assign_permission_to_role(
        role_id=assignment.role_id,
        permission_id=assignment.permission_id,
        granted_by_user_id=current_user.id,
    )

    if not success:
        raise HTTPException(status_code=400, detail="Failed to assign permission")

    return {"message": f"Permission {permission.key} assigned to role {role.name}"}


@router.post("/remove-permission")
async def remove_permission_from_role(
    assignment: PermissionAssignmentRequest,
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin),
):
    """Remove a permission from a role."""

    success = rbac_service.remove_permission_from_role(
        role_id=assignment.role_id, permission_id=assignment.permission_id
    )

    if not success:
        raise HTTPException(status_code=404, detail="Permission assignment not found")

    return {"message": "Permission removed from role"}


# Direct Permission Management


@router.post("/grant-direct-permission")
async def grant_direct_permission(
    permission_grant: DirectPermissionRequest,
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin),
):
    """Grant a direct permission to a user."""

    # Verify user exists
    user = rbac_service.get_user_by_id(permission_grant.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_permission = rbac_service.grant_direct_permission(
        user_id=permission_grant.user_id,
        permission_key=permission_grant.permission_key,
        tenant_id=permission_grant.tenant_id,
        resource_id=permission_grant.resource_id,
        granted_by_user_id=current_user.id,
        expires_at=permission_grant.expires_at,
        reason=permission_grant.reason,
    )

    return {
        "message": f"Direct permission {permission_grant.permission_key} granted to user {user.username}",
        "permission_id": user_permission.id,
    }


# Permission Checking Endpoints


@router.post("/check-permission", response_model=PermissionCheckResponse)
async def check_user_permission(
    check_request: PermissionCheckRequest,
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin),
):
    """Check if a user has a specific permission."""

    has_permission = rbac_service.check_user_permission(
        user_id=check_request.user_id,
        permission_key=check_request.permission_key,
        tenant_id=check_request.tenant_id,
        resource_id=check_request.resource_id,
    )

    # TODO: Add logic to determine how permission was granted (role vs direct)
    granted_by = "role" if has_permission else None

    return PermissionCheckResponse(
        user_id=check_request.user_id,
        permission_key=check_request.permission_key,
        has_permission=has_permission,
        granted_by=granted_by,
    )


# System Management Endpoints


@router.post("/setup-defaults")
async def setup_default_permissions(
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin),
):
    """Set up default role-permission assignments."""

    rbac_service.setup_default_roles_and_permissions()

    return {"message": "Default role-permission assignments completed"}


@router.get("/system-info")
async def get_system_info(
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin),
):
    """Get RBAC system information."""

    user_count = rbac_service.db.query(User).count()
    role_count = rbac_service.db.query(RBACRole).count()
    permission_count = rbac_service.db.query(RBACPermission).count()

    return {
        "users": user_count,
        "roles": role_count,
        "permissions": permission_count,
        "system_version": "1.0.0",
    }


# Audit Log Endpoints


@router.get("/audit-logs", response_model=AuditLogResponse)
async def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    user_id: Optional[int] = Query(None),
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin),
):
    """Get audit logs with filtering."""

    query = rbac_service.db.query(RBACSession).join(
        User, RBACSession.user_id == User.id
    )

    # Apply filters
    if action:
        query = query.filter(RBACSession.action == action)
    if entity_type:
        query = query.filter(RBACSession.entity_type == entity_type)
    if start_date:
        query = query.filter(RBACSession.created_at >= start_date)
    if end_date:
        query = query.filter(RBACSession.created_at <= end_date)
    if user_id:
        query = query.filter(RBACSession.user_id == user_id)

    # Count total
    total_count = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    sessions = (
        query.order_by(RBACSession.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    # Transform to audit log entries
    entries = []
    for session in sessions:
        entries.append(
            AuditLogEntry(
                id=session.id,
                action=session.action or "session_created",
                entity_type=session.entity_type or "session",
                entity_id=session.id,
                details=session.details,
                performed_by_user_id=session.user_id,
                performed_by_username=session.user.username,
                tenant_id=session.tenant_id,
                created_at=session.created_at,
            )
        )

    return AuditLogResponse(
        entries=entries, total_count=total_count, page=page, page_size=page_size
    )


# Bulk Operations Endpoints


@router.post("/users/bulk-delete")
async def bulk_delete_users(
    request: BulkUserOperationRequest,
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin),
):
    """Bulk delete users. Requires admin privileges and user:delete permission."""

    # Verify current user has user:delete permission
    if not rbac_service.check_user_permission(current_user.id, "user:delete"):
        raise HTTPException(
            status_code=403, detail="Insufficient permissions: user:delete required"
        )

    # Prevent self-deletion
    if current_user.id in request.user_ids:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    deleted_count = 0
    errors = []

    for user_id in request.user_ids:
        try:
            user = rbac_service.get_user_by_id(user_id)
            if not user:
                errors.append(f"User {user_id} not found")
                continue

            # Prevent deletion of system users
            if user.username in ["admin", "system"]:
                errors.append(f"Cannot delete system user: {user.username}")
                continue

            # TODO: Implement soft delete or proper user deletion
            # For now, just deactivate the user
            user.is_active = False
            rbac_service.db.commit()
            deleted_count += 1

        except Exception as e:
            errors.append(f"Failed to delete user {user_id}: {str(e)}")

    return {
        "message": f"Bulk operation completed: {deleted_count} users deleted",
        "deleted_count": deleted_count,
        "errors": errors,
    }


@router.post("/users/bulk-activate")
async def bulk_activate_users(
    request: BulkUserOperationRequest,
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin),
):
    """Bulk activate users. Requires admin privileges and user:write permission."""

    # Verify current user has user:write permission
    if not rbac_service.check_user_permission(current_user.id, "user:write"):
        raise HTTPException(
            status_code=403, detail="Insufficient permissions: user:write required"
        )

    activated_count = 0
    errors = []

    for user_id in request.user_ids:
        try:
            user = rbac_service.get_user_by_id(user_id)
            if not user:
                errors.append(f"User {user_id} not found")
                continue

            if user.is_active:
                continue  # Already active

            user.is_active = True
            rbac_service.db.commit()
            activated_count += 1

        except Exception as e:
            errors.append(f"Failed to activate user {user_id}: {str(e)}")

    return {
        "message": f"Bulk operation completed: {activated_count} users activated",
        "activated_count": activated_count,
        "errors": errors,
    }


@router.post("/users/bulk-deactivate")
async def bulk_deactivate_users(
    request: BulkUserOperationRequest,
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin),
):
    """Bulk deactivate users. Requires admin privileges and user:write permission."""

    # Verify current user has user:write permission
    if not rbac_service.check_user_permission(current_user.id, "user:write"):
        raise HTTPException(
            status_code=403, detail="Insufficient permissions: user:write required"
        )

    # Prevent self-deactivation
    if current_user.id in request.user_ids:
        raise HTTPException(
            status_code=400, detail="Cannot deactivate your own account"
        )

    deactivated_count = 0
    errors = []

    for user_id in request.user_ids:
        try:
            user = rbac_service.get_user_by_id(user_id)
            if not user:
                errors.append(f"User {user_id} not found")
                continue

            # Prevent deactivation of system users
            if user.username in ["admin", "system"]:
                errors.append(f"Cannot deactivate system user: {user.username}")
                continue

            if not user.is_active:
                continue  # Already inactive

            user.is_active = False
            rbac_service.db.commit()
            deactivated_count += 1

        except Exception as e:
            errors.append(f"Failed to deactivate user {user_id}: {str(e)}")

    return {
        "message": f"Bulk operation completed: {deactivated_count} users deactivated",
        "deactivated_count": deactivated_count,
        "errors": errors,
    }


@router.post("/users/bulk-assign-role")
async def bulk_assign_role_to_users(
    request: BulkRoleAssignmentRequest,
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin),
):
    """Bulk assign role to users. Requires admin privileges and user:manage_roles permission."""

    # Verify current user has user:manage_roles permission
    if not rbac_service.check_user_permission(current_user.id, "user:manage_roles"):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions: user:manage_roles required",
        )

    # Verify role exists
    role = rbac_service.get_role_by_id(request.role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # Prevent assignment of admin role to non-admin users (unless current user is super admin)
    if role.name in ["admin", "super_admin"]:
        if not rbac_service.check_user_permission(current_user.id, "role:assign_admin"):
            raise HTTPException(
                status_code=403, detail="Insufficient permissions to assign admin roles"
            )

    assigned_count = 0
    errors = []

    for user_id in request.user_ids:
        try:
            user = rbac_service.get_user_by_id(user_id)
            if not user:
                errors.append(f"User {user_id} not found")
                continue

            # Check if user already has this role
            existing_roles = rbac_service.get_user_roles(user_id, request.tenant_id)
            if any(r.id == request.role_id for r in existing_roles):
                continue  # Already has role

            success = rbac_service.assign_role_to_user(
                user_id=user_id,
                role_id=request.role_id,
                tenant_id=request.tenant_id,
                granted_by_user_id=current_user.id,
            )

            if success:
                assigned_count += 1
            else:
                errors.append(f"Failed to assign role to user {user_id}")

        except Exception as e:
            errors.append(f"Failed to assign role to user {user_id}: {str(e)}")

    return {
        "message": f"Bulk operation completed: {assigned_count} role assignments",
        "assigned_count": assigned_count,
        "role_name": role.name,
        "errors": errors,
    }
