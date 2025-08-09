"""Create RBAC tables

Revision ID: 20250727_1600_0012
Revises: 20250726_1200_0011
Create Date: 2025-07-27 16:00:00.000000

This migration creates the complete Role-Based Access Control (RBAC) system
tables including users, roles, permissions, and their relationships.
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import datetime

# revision identifiers
revision = '20250727_1600_0012'
down_revision = '20250726_1200_0011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create RBAC tables and populate with initial data."""
    
    # Create RBAC Users table
    op.create_table('rbac_users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_email_verified', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('first_name', sa.String(length=50), nullable=True),
        sa.Column('last_name', sa.String(length=50), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('default_tenant_id', sa.Integer(), nullable=True),
        sa.Column('accessible_tenant_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('failed_login_attempts', sa.Integer(), nullable=True),
        sa.Column('locked_until', sa.DateTime(), nullable=True),
        sa.Column('password_changed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rbac_users_id'), 'rbac_users', ['id'], unique=False)
    op.create_index(op.f('ix_rbac_users_username'), 'rbac_users', ['username'], unique=True)
    op.create_index(op.f('ix_rbac_users_email'), 'rbac_users', ['email'], unique=True)
    
    # Create RBAC Roles table
    op.create_table('rbac_roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parent_role_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_system_role', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('tenant_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['parent_role_id'], ['rbac_roles.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rbac_roles_id'), 'rbac_roles', ['id'], unique=False)
    op.create_index(op.f('ix_rbac_roles_name'), 'rbac_roles', ['name'], unique=True)
    
    # Create RBAC Permissions table
    op.create_table('rbac_permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('resource', sa.String(length=50), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_system_permission', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('tenant_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rbac_permissions_id'), 'rbac_permissions', ['id'], unique=False)
    op.create_index(op.f('ix_rbac_permissions_key'), 'rbac_permissions', ['key'], unique=True)
    
    # Create User-Roles association table
    op.create_table('user_roles',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('granted_at', sa.DateTime(), nullable=True),
        sa.Column('granted_by', sa.Integer(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['role_id'], ['rbac_roles.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['rbac_users.id'], ),
        sa.ForeignKeyConstraint(['granted_by'], ['rbac_users.id'], ),
        sa.PrimaryKeyConstraint('user_id', 'role_id')
    )
    
    # Create Role-Permissions association table
    op.create_table('role_permissions',
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('permission_id', sa.Integer(), nullable=False),
        sa.Column('granted_at', sa.DateTime(), nullable=True),
        sa.Column('granted_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['permission_id'], ['rbac_permissions.id'], ),
        sa.ForeignKeyConstraint(['role_id'], ['rbac_roles.id'], ),
        sa.ForeignKeyConstraint(['granted_by'], ['rbac_users.id'], ),
        sa.PrimaryKeyConstraint('role_id', 'permission_id')
    )
    
    # Create User Permissions table (direct permissions)
    op.create_table('user_permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('permission_key', sa.String(length=100), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('resource_id', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_grant', sa.Boolean(), nullable=True),
        sa.Column('granted_at', sa.DateTime(), nullable=True),
        sa.Column('granted_by', sa.Integer(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['granted_by'], ['rbac_users.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['rbac_users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_permissions_id'), 'user_permissions', ['id'], unique=False)
    
    # Create RBAC Sessions table
    op.create_table('rbac_sessions',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('active_tenant_id', sa.Integer(), nullable=True),
        sa.Column('active_role_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('cached_permissions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('cache_expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_accessed', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['rbac_users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Insert system permissions
    permissions_table = sa.table('rbac_permissions',
        sa.column('key', sa.String),
        sa.column('name', sa.String),
        sa.column('description', sa.Text),
        sa.column('resource', sa.String),
        sa.column('action', sa.String),
        sa.column('is_active', sa.Boolean),
        sa.column('is_system_permission', sa.Boolean),
        sa.column('created_at', sa.DateTime),
        sa.column('tenant_ids', postgresql.JSONB)
    )
    
    system_permissions = [
        # User Management
        ("user:read", "Read User", "View user information", "user", "read"),
        ("user:write", "Write User", "Create and update users", "user", "write"),
        ("user:delete", "Delete User", "Delete users", "user", "delete"),
        ("user:manage_roles", "Manage User Roles", "Assign/remove roles from users", "user", "manage_roles"),
        
        # Role Management
        ("role:read", "Read Role", "View role information", "role", "read"),
        ("role:write", "Write Role", "Create and update roles", "role", "write"),
        ("role:delete", "Delete Role", "Delete roles", "role", "delete"),
        ("role:manage_permissions", "Manage Role Permissions", "Assign/remove permissions from roles", "role", "manage_permissions"),
        
        # Permission Management
        ("permission:read", "Read Permission", "View permission information", "permission", "read"),
        ("permission:write", "Write Permission", "Create and update permissions", "permission", "write"),
        
        # Staff Management
        ("staff:read", "Read Staff", "View staff information", "staff", "read"),
        ("staff:write", "Write Staff", "Create and update staff records", "staff", "write"),
        ("staff:delete", "Delete Staff", "Delete staff records", "staff", "delete"),
        ("staff:manage_schedule", "Manage Staff Schedule", "Create and modify staff schedules", "staff", "manage_schedule"),
        
        # Payroll Management
        ("payroll:read", "Read Payroll", "View payroll information", "payroll", "read"),
        ("payroll:write", "Write Payroll", "Process payroll", "payroll", "write"),
        ("payroll:approve", "Approve Payroll", "Approve payroll runs", "payroll", "approve"),
        ("payroll:export", "Export Payroll", "Export payroll data", "payroll", "export"),
        
        # Order Management
        ("order:read", "Read Order", "View order information", "order", "read"),
        ("order:write", "Write Order", "Create and update orders", "order", "write"),
        ("order:delete", "Delete Order", "Cancel/delete orders", "order", "delete"),
        ("order:manage_kitchen", "Manage Kitchen", "Kitchen order operations", "order", "manage_kitchen"),
        
        # System Administration
        ("system:read", "Read System", "View system information", "system", "read"),
        ("system:write", "Write System", "Configure system settings", "system", "write"),
        ("system:audit", "System Audit", "Access audit logs", "system", "audit"),
        ("system:backup", "System Backup", "Perform system backups", "system", "backup"),
    ]
    
    op.bulk_insert(permissions_table, [
        {
            'key': key,
            'name': name,
            'description': description,
            'resource': resource,
            'action': action,
            'is_active': True,
            'is_system_permission': True,
            'created_at': datetime.utcnow(),
            'tenant_ids': []
        }
        for key, name, description, resource, action in system_permissions
    ])
    
    # Insert system roles
    roles_table = sa.table('rbac_roles',
        sa.column('name', sa.String),
        sa.column('display_name', sa.String),
        sa.column('description', sa.Text),
        sa.column('is_active', sa.Boolean),
        sa.column('is_system_role', sa.Boolean),
        sa.column('created_at', sa.DateTime),
        sa.column('updated_at', sa.DateTime),
        sa.column('tenant_ids', postgresql.JSONB)
    )
    
    system_roles = [
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
    
    op.bulk_insert(roles_table, [
        {
            'name': name,
            'display_name': display_name,
            'description': description,
            'is_active': True,
            'is_system_role': True,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'tenant_ids': []
        }
        for name, display_name, description in system_roles
    ])
    
    # Migrate existing users from auth.py
    users_table = sa.table('rbac_users',
        sa.column('username', sa.String),
        sa.column('email', sa.String),
        sa.column('hashed_password', sa.String),
        sa.column('is_active', sa.Boolean),
        sa.column('is_email_verified', sa.Boolean),
        sa.column('created_at', sa.DateTime),
        sa.column('updated_at', sa.DateTime),
        sa.column('password_changed_at', sa.DateTime),
        sa.column('accessible_tenant_ids', postgresql.JSONB),
        sa.column('default_tenant_id', sa.Integer),
        sa.column('failed_login_attempts', sa.Integer)
    )
    
    # Insert mock users from auth.py
    op.bulk_insert(users_table, [
        {
            'username': 'admin',
            'email': 'admin@auraconnect.ai',
            'hashed_password': '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW',
            'is_active': True,
            'is_email_verified': True,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'password_changed_at': datetime.utcnow(),
            'accessible_tenant_ids': [1, 2, 3],
            'default_tenant_id': 1,
            'failed_login_attempts': 0
        },
        {
            'username': 'payroll_clerk',
            'email': 'payroll@auraconnect.ai',
            'hashed_password': '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW',
            'is_active': True,
            'is_email_verified': True,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'password_changed_at': datetime.utcnow(),
            'accessible_tenant_ids': [1],
            'default_tenant_id': 1,
            'failed_login_attempts': 0
        },
        {
            'username': 'manager',
            'email': 'manager@auraconnect.ai',
            'hashed_password': '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW',
            'is_active': True,
            'is_email_verified': True,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'password_changed_at': datetime.utcnow(),
            'accessible_tenant_ids': [1],
            'default_tenant_id': 1,
            'failed_login_attempts': 0
        }
    ])


def downgrade() -> None:
    """Drop RBAC tables."""
    op.drop_table('rbac_sessions')
    op.drop_table('user_permissions')
    op.drop_table('role_permissions')
    op.drop_table('user_roles')
    op.drop_table('rbac_permissions')
    op.drop_table('rbac_roles')
    op.drop_table('rbac_users')