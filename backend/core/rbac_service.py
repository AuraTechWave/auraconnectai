"""
RBAC Service Layer

This service provides high-level operations for Role-Based Access Control,
including user management, role assignment, permission checking, and
session management with RBAC context.
"""

from typing import List, Optional, Dict, Set, Union
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timedelta
import logging

from .rbac_models import (
    RBACUser,
    RBACRole,
    RBACPermission,
    UserPermission,
    RBACSession,
    user_roles,
    role_permissions,
)
from .database import get_db
from .auth import get_password_hash, verify_password
from .config import settings

logger = logging.getLogger(__name__)


class RBACService:
    """Service class for RBAC operations."""

    def __init__(self, db: Session):
        self.db = db

    # User Management

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        accessible_tenant_ids: List[int] = None,
        default_tenant_id: Optional[int] = None,
    ) -> RBACUser:
        """Create a new user."""

        # Check if user already exists
        existing = (
            self.db.query(RBACUser)
            .filter(or_(RBACUser.username == username, RBACUser.email == email))
            .first()
        )

        if existing:
            raise ValueError("User with this username or email already exists")

        hashed_password = get_password_hash(password)

        user = RBACUser(
            username=username,
            email=email,
            hashed_password=hashed_password,
            first_name=first_name,
            last_name=last_name,
            accessible_tenant_ids=accessible_tenant_ids or [],
            default_tenant_id=default_tenant_id,
            is_active=True,
            is_email_verified=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            password_changed_at=datetime.utcnow(),
            failed_login_attempts=0,
        )

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        logger.info(f"Created user: {username}")
        return user

    def get_user_by_username(self, username: str) -> Optional[RBACUser]:
        """Get user by username."""
        return self.db.query(RBACUser).filter(RBACUser.username == username).first()

    def get_user_by_id(self, user_id: int) -> Optional[RBACUser]:
        """Get user by ID."""
        return self.db.query(RBACUser).filter(RBACUser.id == user_id).first()

    def authenticate_user(self, username: str, password: str) -> Optional[RBACUser]:
        """Authenticate user with username and password."""
        user = self.get_user_by_username(username)
        if not user or not user.is_active:
            return None

        if user.locked_until and user.locked_until > datetime.utcnow():
            logger.warning(f"Login attempt for locked user: {username}")
            return None

        if not verify_password(password, user.hashed_password):
            # Increment failed attempts
            user.failed_login_attempts += 1

            # Lock account after 5 failed attempts
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.utcnow() + timedelta(minutes=30)
                logger.warning(f"Account locked due to failed attempts: {username}")

            self.db.commit()
            return None

        # Reset failed attempts on successful login
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.utcnow()
        self.db.commit()

        return user

    # Role Management

    def create_role(
        self,
        name: str,
        display_name: str,
        description: Optional[str] = None,
        parent_role_id: Optional[int] = None,
        tenant_ids: List[int] = None,
    ) -> RBACRole:
        """Create a new role."""

        existing = self.db.query(RBACRole).filter(RBACRole.name == name).first()
        if existing:
            raise ValueError("Role with this name already exists")

        role = RBACRole(
            name=name,
            display_name=display_name,
            description=description,
            parent_role_id=parent_role_id,
            tenant_ids=tenant_ids or [],
            is_active=True,
            is_system_role=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.db.add(role)
        self.db.commit()
        self.db.refresh(role)

        logger.info(f"Created role: {name}")
        return role

    def get_role_by_name(self, name: str) -> Optional[RBACRole]:
        """Get role by name."""
        return self.db.query(RBACRole).filter(RBACRole.name == name).first()

    def get_role_by_id(self, role_id: int) -> Optional[RBACRole]:
        """Get role by ID."""
        return self.db.query(RBACRole).filter(RBACRole.id == role_id).first()

    def assign_role_to_user(
        self,
        user_id: int,
        role_id: int,
        tenant_id: Optional[int] = None,
        granted_by_user_id: Optional[int] = None,
        expires_at: Optional[datetime] = None,
    ) -> bool:
        """Assign a role to a user."""

        # Check if assignment already exists
        existing = (
            self.db.query(user_roles)
            .filter(
                and_(user_roles.c.user_id == user_id, user_roles.c.role_id == role_id)
            )
            .first()
        )

        if existing:
            # Update existing assignment
            self.db.execute(
                user_roles.update()
                .where(
                    and_(
                        user_roles.c.user_id == user_id, user_roles.c.role_id == role_id
                    )
                )
                .values(
                    tenant_id=tenant_id,
                    granted_at=datetime.utcnow(),
                    granted_by=granted_by_user_id,
                    expires_at=expires_at,
                    is_active=True,
                )
            )
        else:
            # Create new assignment
            self.db.execute(
                user_roles.insert().values(
                    user_id=user_id,
                    role_id=role_id,
                    tenant_id=tenant_id,
                    granted_at=datetime.utcnow(),
                    granted_by=granted_by_user_id,
                    expires_at=expires_at,
                    is_active=True,
                )
            )

        self.db.commit()
        logger.info(f"Assigned role {role_id} to user {user_id}")
        return True

    def remove_role_from_user(self, user_id: int, role_id: int) -> bool:
        """Remove a role from a user."""

        result = self.db.execute(
            user_roles.delete().where(
                and_(user_roles.c.user_id == user_id, user_roles.c.role_id == role_id)
            )
        )

        self.db.commit()

        if result.rowcount > 0:
            logger.info(f"Removed role {role_id} from user {user_id}")
            return True
        return False

    # Permission Management

    def create_permission(
        self,
        key: str,
        name: str,
        description: Optional[str] = None,
        resource: str = None,
        action: str = None,
        tenant_ids: List[int] = None,
    ) -> RBACPermission:
        """Create a new permission."""

        existing = (
            self.db.query(RBACPermission).filter(RBACPermission.key == key).first()
        )
        if existing:
            raise ValueError("Permission with this key already exists")

        # Parse resource and action from key if not provided
        if not resource or not action:
            parts = key.split(":", 1)
            if len(parts) == 2:
                resource = resource or parts[0]
                action = action or parts[1]
            else:
                raise ValueError(
                    "Invalid permission key format. Expected 'resource:action'"
                )

        permission = RBACPermission(
            key=key,
            name=name,
            description=description,
            resource=resource,
            action=action,
            tenant_ids=tenant_ids or [],
            is_active=True,
            is_system_permission=False,
            created_at=datetime.utcnow(),
        )

        self.db.add(permission)
        self.db.commit()
        self.db.refresh(permission)

        logger.info(f"Created permission: {key}")
        return permission

    def get_permission_by_key(self, key: str) -> Optional[RBACPermission]:
        """Get permission by key."""
        return self.db.query(RBACPermission).filter(RBACPermission.key == key).first()

    def assign_permission_to_role(
        self, role_id: int, permission_id: int, granted_by_user_id: Optional[int] = None
    ) -> bool:
        """Assign a permission to a role."""

        # Check if assignment already exists
        existing = (
            self.db.query(role_permissions)
            .filter(
                and_(
                    role_permissions.c.role_id == role_id,
                    role_permissions.c.permission_id == permission_id,
                )
            )
            .first()
        )

        if existing:
            return True  # Already assigned

        # Create new assignment
        self.db.execute(
            role_permissions.insert().values(
                role_id=role_id,
                permission_id=permission_id,
                granted_at=datetime.utcnow(),
                granted_by=granted_by_user_id,
            )
        )

        self.db.commit()
        logger.info(f"Assigned permission {permission_id} to role {role_id}")
        return True

    def remove_permission_from_role(self, role_id: int, permission_id: int) -> bool:
        """Remove a permission from a role."""

        result = self.db.execute(
            role_permissions.delete().where(
                and_(
                    role_permissions.c.role_id == role_id,
                    role_permissions.c.permission_id == permission_id,
                )
            )
        )

        self.db.commit()

        if result.rowcount > 0:
            logger.info(f"Removed permission {permission_id} from role {role_id}")
            return True
        return False

    def grant_direct_permission(
        self,
        user_id: int,
        permission_key: str,
        tenant_id: Optional[int] = None,
        resource_id: Optional[str] = None,
        granted_by_user_id: Optional[int] = None,
        expires_at: Optional[datetime] = None,
        reason: Optional[str] = None,
    ) -> UserPermission:
        """Grant a direct permission to a user."""

        user_permission = UserPermission(
            user_id=user_id,
            permission_key=permission_key,
            tenant_id=tenant_id,
            resource_id=resource_id,
            is_active=True,
            is_grant=True,
            granted_at=datetime.utcnow(),
            granted_by=granted_by_user_id,
            expires_at=expires_at,
            reason=reason,
        )

        self.db.add(user_permission)
        self.db.commit()
        self.db.refresh(user_permission)

        logger.info(f"Granted direct permission {permission_key} to user {user_id}")
        return user_permission

    # Permission Checking

    def check_user_permission(
        self,
        user_id: int,
        permission_key: str,
        tenant_id: Optional[int] = None,
        resource_id: Optional[str] = None,
    ) -> bool:
        """Check if a user has a specific permission."""

        user = self.get_user_by_id(user_id)
        if not user or not user.is_active:
            return False

        # Check direct permissions first
        direct_perms = self.db.query(UserPermission).filter(
            and_(
                UserPermission.user_id == user_id,
                UserPermission.permission_key == permission_key,
                UserPermission.is_active == True,
                or_(
                    UserPermission.expires_at.is_(None),
                    UserPermission.expires_at > datetime.utcnow(),
                ),
            )
        )

        if tenant_id is not None:
            direct_perms = direct_perms.filter(
                or_(
                    UserPermission.tenant_id.is_(None),
                    UserPermission.tenant_id == tenant_id,
                )
            )

        if resource_id is not None:
            direct_perms = direct_perms.filter(
                or_(
                    UserPermission.resource_id.is_(None),
                    UserPermission.resource_id == resource_id,
                )
            )

        # Check for explicit deny first
        deny_perm = direct_perms.filter(UserPermission.is_grant == False).first()
        if deny_perm:
            return False

        # Check for explicit grant
        grant_perm = direct_perms.filter(UserPermission.is_grant == True).first()
        if grant_perm:
            return True

        # Check role-based permissions
        return user.has_permission(permission_key, tenant_id)

    def get_user_permissions(
        self, user_id: int, tenant_id: Optional[int] = None
    ) -> List[str]:
        """Get all effective permissions for a user."""

        user = self.get_user_by_id(user_id)
        if not user or not user.is_active:
            return []

        return user.get_effective_permissions(tenant_id)

    def get_user_roles(
        self, user_id: int, tenant_id: Optional[int] = None
    ) -> List[RBACRole]:
        """Get all roles for a user."""

        query = (
            self.db.query(RBACRole)
            .join(user_roles)
            .filter(
                and_(
                    user_roles.c.user_id == user_id,
                    user_roles.c.is_active == True,
                    RBACRole.is_active == True,
                )
            )
        )

        if tenant_id is not None:
            query = query.filter(
                or_(
                    user_roles.c.tenant_id.is_(None),
                    user_roles.c.tenant_id == tenant_id,
                )
            )

        return query.all()

    # Session Management

    def create_rbac_session(
        self,
        session_id: str,
        user_id: int,
        expires_at: datetime,
        active_tenant_id: Optional[int] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> RBACSession:
        """Create an RBAC session."""

        # Get user's active roles for the tenant
        active_role_ids = []
        user_roles_query = self.db.query(user_roles).filter(
            and_(user_roles.c.user_id == user_id, user_roles.c.is_active == True)
        )

        if active_tenant_id is not None:
            user_roles_query = user_roles_query.filter(
                or_(
                    user_roles.c.tenant_id.is_(None),
                    user_roles.c.tenant_id == active_tenant_id,
                )
            )

        for role_assignment in user_roles_query.all():
            active_role_ids.append(role_assignment.role_id)

        # Cache permissions for performance
        cached_permissions = {}
        if active_tenant_id is not None:
            permissions = self.get_user_permissions(user_id, active_tenant_id)
            cached_permissions[str(active_tenant_id)] = permissions

        session = RBACSession(
            id=session_id,
            user_id=user_id,
            active_tenant_id=active_tenant_id,
            active_role_ids=active_role_ids,
            cached_permissions=cached_permissions,
            cache_expires_at=datetime.utcnow()
            + timedelta(minutes=settings.rbac_session_cache_ttl_minutes),
            created_at=datetime.utcnow(),
            last_accessed=datetime.utcnow(),
            expires_at=expires_at,
            is_active=True,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        return session

    def get_rbac_session(self, session_id: str) -> Optional[RBACSession]:
        """Get RBAC session by ID."""
        return (
            self.db.query(RBACSession)
            .filter(
                and_(
                    RBACSession.id == session_id,
                    RBACSession.is_active == True,
                    RBACSession.expires_at > datetime.utcnow(),
                )
            )
            .first()
        )

    def refresh_session_cache(self, session_id: str) -> bool:
        """Refresh the permission cache for a session."""

        session = self.get_rbac_session(session_id)
        if not session:
            return False

        # Update cached permissions
        cached_permissions = {}
        if session.active_tenant_id is not None:
            permissions = self.get_user_permissions(
                session.user_id, session.active_tenant_id
            )
            cached_permissions[str(session.active_tenant_id)] = permissions

        session.cached_permissions = cached_permissions
        session.cache_expires_at = datetime.utcnow() + timedelta(
            minutes=settings.rbac_session_cache_ttl_minutes
        )
        session.last_accessed = datetime.utcnow()

        self.db.commit()
        return True

    # Utility Methods

    def setup_default_roles_and_permissions(self) -> None:
        """Set up default role-permission assignments for system roles."""

        # Define role-permission mappings
        role_permissions_map = {
            "super_admin": [
                "user:read",
                "user:write",
                "user:delete",
                "user:manage_roles",
                "role:read",
                "role:write",
                "role:delete",
                "role:manage_permissions",
                "permission:read",
                "permission:write",
                "staff:read",
                "staff:write",
                "staff:delete",
                "staff:manage_schedule",
                "payroll:read",
                "payroll:write",
                "payroll:approve",
                "payroll:export",
                "order:read",
                "order:write",
                "order:delete",
                "order:manage_kitchen",
                "system:read",
                "system:write",
                "system:audit",
                "system:backup",
            ],
            "admin": [
                "user:read",
                "user:write",
                "user:manage_roles",
                "role:read",
                "staff:read",
                "staff:write",
                "staff:manage_schedule",
                "payroll:read",
                "payroll:write",
                "payroll:approve",
                "payroll:export",
                "order:read",
                "order:write",
                "order:delete",
                "order:manage_kitchen",
                "system:read",
            ],
            "payroll_manager": [
                "staff:read",
                "payroll:read",
                "payroll:write",
                "payroll:approve",
                "payroll:export",
            ],
            "payroll_clerk": ["staff:read", "payroll:read", "payroll:write"],
            "staff_manager": [
                "staff:read",
                "staff:write",
                "staff:manage_schedule",
                "order:read",
            ],
            "kitchen_manager": [
                "order:read",
                "order:write",
                "order:manage_kitchen",
                "staff:read",
            ],
            "manager": ["staff:read", "order:read", "order:write", "payroll:read"],
            "server": ["order:read", "order:write"],
            "viewer": ["staff:read", "order:read", "payroll:read"],
        }

        # Assign permissions to roles
        for role_name, permission_keys in role_permissions_map.items():
            role = self.get_role_by_name(role_name)
            if not role:
                continue

            for permission_key in permission_keys:
                permission = self.get_permission_by_key(permission_key)
                if permission:
                    try:
                        self.assign_permission_to_role(role.id, permission.id)
                    except Exception as e:
                        logger.warning(
                            f"Failed to assign {permission_key} to {role_name}: {e}"
                        )

        logger.info("Default role-permission assignments completed")


# Dependency function for FastAPI
def get_rbac_service(db: Session = None) -> RBACService:
    """Get RBAC service instance."""
    if db is None:
        db = next(get_db())
    return RBACService(db)
