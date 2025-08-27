"""
Role-Based Access Control (RBAC) Models

This module defines the database models for implementing fine-grained
role-based access control throughout the AuraConnect system.

The RBAC system follows these principles:
- Users have Roles
- Roles have Permissions
- Permissions grant access to specific Resources and Actions
- Support for hierarchical roles and permission inheritance
- Multi-tenant permission scoping
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    Table,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from core.database import Base


# Association tables for many-to-many relationships
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("rbac_users.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("rbac_roles.id"), primary_key=True),
    Column(
        "tenant_id", Integer, nullable=True
    ),  # Role can be scoped to specific tenant
    Column("granted_at", DateTime, default=datetime.utcnow),
    Column("granted_by", Integer, ForeignKey("rbac_users.id"), nullable=True),
    Column("expires_at", DateTime, nullable=True),  # Optional role expiration
    Column("is_active", Boolean, default=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("rbac_roles.id"), primary_key=True),
    Column(
        "permission_id", Integer, ForeignKey("rbac_permissions.id"), primary_key=True
    ),
    Column("granted_at", DateTime, default=datetime.utcnow),
    Column("granted_by", Integer, ForeignKey("rbac_users.id"), nullable=True),
)


class RBACUser(Base):
    """
    User model for RBAC system.

    This extends/replaces the simple User model in auth.py with
    proper database backing and RBAC relationships.
    """

    __tablename__ = "rbac_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

    # User status and metadata
    is_active = Column(Boolean, default=True)
    is_email_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Profile information
    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)
    phone = Column(String(20), nullable=True)

    # Multi-tenancy support
    default_tenant_id = Column(Integer, nullable=True)
    accessible_tenant_ids = Column(
        JSONB, default=list
    )  # List of tenant IDs user can access

    # Security metadata
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, default=datetime.utcnow)

    # RBAC relationships
    roles = relationship(
        "RBACRole", secondary=user_roles, back_populates="users", lazy="dynamic"
    )

    # Direct permissions (override role permissions)
    direct_permissions = relationship(
        "UserPermission", back_populates="user", cascade="all, delete-orphan"
    )

    def get_effective_permissions(self, tenant_id=None):
        """Get all effective permissions for user including role-based and direct permissions."""
        permissions = set()

        # Get permissions from roles
        for role in self.roles:
            if tenant_id is None or role.is_applicable_to_tenant(tenant_id):
                for permission in role.permissions:
                    if permission.is_applicable_to_tenant(tenant_id):
                        permissions.add(permission.key)

        # Add direct permissions
        for user_perm in self.direct_permissions:
            if user_perm.is_active and (
                tenant_id is None or user_perm.tenant_id == tenant_id
            ):
                permissions.add(user_perm.permission_key)

        return list(permissions)

    def has_permission(self, permission_key, tenant_id=None):
        """Check if user has specific permission."""
        return permission_key in self.get_effective_permissions(tenant_id)

    def has_role(self, role_name, tenant_id=None):
        """Check if user has specific role."""
        for role in self.roles:
            if role.name == role_name:
                if tenant_id is None or role.is_applicable_to_tenant(tenant_id):
                    return True
        return False

    # Password security relationships
    # TODO: Uncomment these when password models are properly imported
    # password_reset_tokens = relationship(
    #     "PasswordResetToken", back_populates="user", cascade="all, delete-orphan"
    # )

    # password_history = relationship(
    #     "PasswordHistory", back_populates="user", cascade="all, delete-orphan"
    # )

    # security_audit_logs = relationship(
    #     "SecurityAuditLog", back_populates="user", cascade="all, delete-orphan"
    # )


class RBACRole(Base):
    """
    Role model for RBAC system.

    Roles group permissions together and can be assigned to users.
    Supports hierarchical roles and tenant-scoping.
    """

    __tablename__ = "rbac_roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # Role hierarchy
    parent_role_id = Column(Integer, ForeignKey("rbac_roles.id"), nullable=True)
    parent_role = relationship(
        "RBACRole", remote_side=[id], back_populates="child_roles"
    )
    child_roles = relationship("RBACRole", back_populates="parent_role")

    # Role metadata
    is_active = Column(Boolean, default=True)
    is_system_role = Column(Boolean, default=False)  # System roles cannot be deleted
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Multi-tenancy support
    tenant_ids = Column(JSONB, default=list)  # Empty list = available to all tenants

    # RBAC relationships
    users = relationship("RBACUser", secondary=user_roles, back_populates="roles")

    permissions = relationship(
        "RBACPermission", secondary=role_permissions, back_populates="roles"
    )

    def is_applicable_to_tenant(self, tenant_id):
        """Check if role applies to specific tenant."""
        if not self.tenant_ids:  # Empty list means applies to all tenants
            return True
        return tenant_id in self.tenant_ids

    def get_all_permissions(self, include_inherited=True):
        """Get all permissions including inherited from parent roles."""
        permissions = set(self.permissions)

        if include_inherited and self.parent_role:
            permissions.update(self.parent_role.get_all_permissions())

        return list(permissions)


class RBACPermission(Base):
    """
    Permission model for RBAC system.

    Permissions define specific actions that can be performed on resources.
    Follow the pattern: <resource>:<action> (e.g., "payroll:read", "staff:write")
    """

    __tablename__ = "rbac_permissions"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(
        String(100), unique=True, index=True, nullable=False
    )  # e.g., "payroll:read"
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # Permission categorization
    resource = Column(String(50), nullable=False)  # e.g., "payroll", "staff", "orders"
    action = Column(
        String(50), nullable=False
    )  # e.g., "read", "write", "delete", "approve"

    # Permission metadata
    is_active = Column(Boolean, default=True)
    is_system_permission = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Multi-tenancy support
    tenant_ids = Column(JSONB, default=list)  # Empty list = available to all tenants

    # RBAC relationships
    roles = relationship(
        "RBACRole", secondary=role_permissions, back_populates="permissions"
    )

    def is_applicable_to_tenant(self, tenant_id):
        """Check if permission applies to specific tenant."""
        if not self.tenant_ids:  # Empty list means applies to all tenants
            return True
        return tenant_id in self.tenant_ids


class UserPermission(Base):
    """
    Direct user permissions (not through roles).

    These override role-based permissions and can be used for
    special cases or temporary access grants.
    """

    __tablename__ = "user_permissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("rbac_users.id"), nullable=False)
    permission_key = Column(String(100), nullable=False)

    # Permission scope
    tenant_id = Column(Integer, nullable=True)  # Specific tenant or None for all
    resource_id = Column(String(100), nullable=True)  # Specific resource instance

    # Permission metadata
    is_active = Column(Boolean, default=True)
    is_grant = Column(Boolean, default=True)  # True = grant, False = deny
    granted_at = Column(DateTime, default=datetime.utcnow)
    granted_by = Column(Integer, ForeignKey("rbac_users.id"), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    reason = Column(Text, nullable=True)

    # Relationships
    user = relationship("RBACUser", back_populates="direct_permissions")
    granted_by_user = relationship("RBACUser", foreign_keys=[granted_by])


class RBACSession(Base):
    """
    Enhanced session model with RBAC context.

    Extends the basic session to include RBAC-specific information
    like active role context and permission cache.
    """

    __tablename__ = "rbac_sessions"

    id = Column(String(50), primary_key=True)  # Session ID
    user_id = Column(Integer, ForeignKey("rbac_users.id"), nullable=False)

    # Session context
    active_tenant_id = Column(Integer, nullable=True)  # Currently active tenant
    active_role_ids = Column(JSONB, default=list)  # Currently active roles

    # Permission cache (for performance)
    cached_permissions = Column(JSONB, default=dict)  # {tenant_id: [permissions]}
    cache_expires_at = Column(DateTime, nullable=True)

    # Session metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)

    # Client information
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)

    # Relationships
    user = relationship("RBACUser")


# Predefined system permissions
SYSTEM_PERMISSIONS = [
    # User Management
    ("user:read", "Read User", "View user information"),
    ("user:write", "Write User", "Create and update users"),
    ("user:delete", "Delete User", "Delete users"),
    ("user:manage_roles", "Manage User Roles", "Assign/remove roles from users"),
    # Role Management
    ("role:read", "Read Role", "View role information"),
    ("role:write", "Write Role", "Create and update roles"),
    ("role:delete", "Delete Role", "Delete roles"),
    (
        "role:manage_permissions",
        "Manage Role Permissions",
        "Assign/remove permissions from roles",
    ),
    # Permission Management
    ("permission:read", "Read Permission", "View permission information"),
    ("permission:write", "Write Permission", "Create and update permissions"),
    # Staff Management
    ("staff:read", "Read Staff", "View staff information"),
    ("staff:write", "Write Staff", "Create and update staff records"),
    ("staff:delete", "Delete Staff", "Delete staff records"),
    (
        "staff:manage_schedule",
        "Manage Staff Schedule",
        "Create and modify staff schedules",
    ),
    # Payroll Management
    ("payroll:read", "Read Payroll", "View payroll information"),
    ("payroll:write", "Write Payroll", "Process payroll"),
    ("payroll:approve", "Approve Payroll", "Approve payroll runs"),
    ("payroll:export", "Export Payroll", "Export payroll data"),
    # Order Management
    ("order:read", "Read Order", "View order information"),
    ("order:write", "Write Order", "Create and update orders"),
    ("order:delete", "Delete Order", "Cancel/delete orders"),
    ("order:manage_kitchen", "Manage Kitchen", "Kitchen order operations"),
    # System Administration
    ("system:read", "Read System", "View system information"),
    ("system:write", "Write System", "Configure system settings"),
    ("system:audit", "System Audit", "Access audit logs"),
    ("system:backup", "System Backup", "Perform system backups"),
]

# Predefined system roles
SYSTEM_ROLES = [
    ("super_admin", "Super Administrator", "Full system access"),
    ("admin", "Administrator", "Administrative access"),
    ("manager", "Manager", "Management access"),
    ("payroll_manager", "Payroll Manager", "Payroll management access"),
    ("payroll_clerk", "Payroll Clerk", "Payroll data entry access"),
    ("staff_manager", "Staff Manager", "Staff management access"),
    ("kitchen_manager", "Kitchen Manager", "Kitchen operations access"),
    ("server", "Server", "Front-of-house staff access"),
    ("viewer", "Viewer", "Read-only access"),
]
