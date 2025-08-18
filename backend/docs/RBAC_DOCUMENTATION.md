# AuraConnect RBAC System Documentation

## Overview

The AuraConnect Role-Based Access Control (RBAC) system provides fine-grained access control for all system resources. It supports hierarchical roles, direct permission grants, multi-tenant isolation, and deny permission precedence.

## Table of Contents

1. [Architecture](#architecture)
2. [Role Hierarchy](#role-hierarchy)
3. [System Permissions](#system-permissions)
4. [API Endpoints](#api-endpoints)
5. [Usage Examples](#usage-examples)
6. [Security Considerations](#security-considerations)
7. [Best Practices](#best-practices)

## Architecture

### Core Components

1. **Users** (`RBACUser`)
   - Authenticated entities in the system
   - Can have multiple roles and direct permissions
   - Support multi-tenant access

2. **Roles** (`RBACRole`)
   - Named collections of permissions
   - Support hierarchical inheritance
   - Can be scoped to specific tenants

3. **Permissions** (`RBACPermission`)
   - Define specific actions on resources
   - Follow the pattern: `resource:action`
   - Can be globally or tenant-specific

4. **Sessions** (`RBACSession`)
   - Track active user sessions with RBAC context
   - Cache permissions for performance
   - Include tenant context

### Permission Precedence

1. **Deny Always Wins**: Explicit deny permissions override all grants
2. **Direct Permissions**: Override role-based permissions
3. **Role Inheritance**: Child roles inherit parent role permissions
4. **Tenant Scope**: Tenant-specific permissions override global ones

## Role Hierarchy

### System Roles

```
super_admin
    │
    ├── admin
    │   ├── payroll_manager
    │   │   └── payroll_clerk
    │   ├── staff_manager
    │   └── kitchen_manager
    │
    ├── manager
    │   └── server
    │
    └── viewer (read-only access)
```

### Role Descriptions

| Role | Display Name | Description | Key Permissions |
|------|-------------|-------------|-----------------|
| `super_admin` | Super Administrator | Full system access | All permissions |
| `admin` | Administrator | Administrative access | User, role, and system management |
| `manager` | Manager | Management access | Staff, orders, basic operations |
| `payroll_manager` | Payroll Manager | Payroll management access | Payroll read/write/approve/export |
| `payroll_clerk` | Payroll Clerk | Payroll data entry access | Payroll read/write |
| `staff_manager` | Staff Manager | Staff management access | Staff CRUD, scheduling |
| `kitchen_manager` | Kitchen Manager | Kitchen operations access | Orders, kitchen display |
| `server` | Server | Front-of-house staff access | Order read/write |
| `viewer` | Viewer | Read-only access | Read permissions only |

## System Permissions

### Permission Structure

Permissions follow the pattern: `resource:action`

Example: `staff:read` grants read access to staff resources

### Available Permissions

#### User Management
- `user:read` - View user information
- `user:write` - Create and update users
- `user:delete` - Delete users
- `user:manage_roles` - Assign/remove roles from users

#### Role Management
- `role:read` - View role information
- `role:write` - Create and update roles
- `role:delete` - Delete roles
- `role:manage_permissions` - Assign/remove permissions from roles

#### Permission Management
- `permission:read` - View permission information
- `permission:write` - Create and update permissions

#### Staff Management
- `staff:read` - View staff information
- `staff:write` - Create and update staff records
- `staff:delete` - Delete staff records
- `staff:manage_schedule` - Create and modify staff schedules

#### Payroll Management
- `payroll:read` - View payroll information
- `payroll:write` - Process payroll
- `payroll:approve` - Approve payroll runs
- `payroll:export` - Export payroll data

#### Order Management
- `order:read` - View order information
- `order:write` - Create and update orders
- `order:delete` - Cancel/delete orders
- `order:manage_kitchen` - Kitchen order operations

#### System Administration
- `system:read` - View system information
- `system:write` - Configure system settings
- `system:audit` - Access audit logs
- `system:backup` - Perform system backups

## API Endpoints

### Authentication Required

All RBAC endpoints require authentication with appropriate permissions.

### User Management

#### Create User
```http
POST /rbac/users
Authorization: Bearer {token}
Content-Type: application/json

{
    "username": "newuser",
    "email": "user@example.com",
    "password": "securepassword",
    "first_name": "John",
    "last_name": "Doe",
    "accessible_tenant_ids": [1, 2],
    "default_tenant_id": 1
}
```

#### List Users
```http
GET /rbac/users?page=1&page_size=50&search=john&is_active=true
Authorization: Bearer {token}
```

#### Get User Permissions
```http
GET /rbac/users/{user_id}/permissions?tenant_id=1
Authorization: Bearer {token}
```

### Role Management

#### Create Role
```http
POST /rbac/roles
Authorization: Bearer {token}
Content-Type: application/json

{
    "name": "custom_role",
    "display_name": "Custom Role",
    "description": "A custom role for specific needs",
    "parent_role_id": null,
    "tenant_ids": [1, 2]
}
```

#### Assign Role to User
```http
POST /rbac/assign-role
Authorization: Bearer {token}
Content-Type: application/json

{
    "user_id": 123,
    "role_id": 456,
    "tenant_id": 1,
    "expires_at": "2024-12-31T23:59:59Z"
}
```

### Permission Management

#### List Permissions
```http
GET /rbac/permissions?resource=staff&limit=100
Authorization: Bearer {token}
```

#### Grant Direct Permission
```http
POST /rbac/grant-direct-permission
Authorization: Bearer {token}
Content-Type: application/json

{
    "user_id": 123,
    "permission_key": "special:action",
    "tenant_id": 1,
    "resource_id": "resource123",
    "expires_at": "2024-06-30T23:59:59Z",
    "reason": "Temporary access for project X"
}
```

#### Check Permission
```http
POST /rbac/check-permission
Authorization: Bearer {token}
Content-Type: application/json

{
    "user_id": 123,
    "permission_key": "staff:read",
    "tenant_id": 1,
    "resource_id": null
}
```

### Bulk Operations

#### Bulk Assign Role
```http
POST /rbac/users/bulk-assign-role
Authorization: Bearer {token}
Content-Type: application/json

{
    "user_ids": [123, 456, 789],
    "role_id": 10,
    "tenant_id": 1
}
```

## Usage Examples

### 1. Setting Up a New Employee

```python
# Create user account
user = rbac_service.create_user(
    username="john.doe",
    email="john.doe@restaurant.com",
    password="secure_password",
    first_name="John",
    last_name="Doe",
    accessible_tenant_ids=[1],  # Restaurant location ID
    default_tenant_id=1
)

# Assign server role
server_role = rbac_service.get_role_by_name("server")
rbac_service.assign_role_to_user(
    user_id=user.id,
    role_id=server_role.id,
    tenant_id=1,
    granted_by_user_id=admin_user.id
)
```

### 2. Granting Temporary Access

```python
# Grant temporary payroll access for audit
rbac_service.grant_direct_permission(
    user_id=auditor_user.id,
    permission_key="payroll:read",
    tenant_id=1,
    expires_at=datetime.utcnow() + timedelta(days=7),
    reason="Annual audit - expires in 7 days"
)
```

### 3. Checking Permissions in Code

```python
# In your FastAPI endpoint
from core.auth import get_current_user, require_permission

@router.get("/payroll/reports")
async def get_payroll_reports(
    current_user: User = Depends(get_current_user),
    rbac_service: RBACService = Depends(get_rbac_service)
):
    # Check permission
    if not rbac_service.check_user_permission(
        user_id=current_user.id,
        permission_key="payroll:read",
        tenant_id=current_user.default_tenant_id
    ):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions: payroll:read required"
        )
    
    # Process request...
```

### 4. Implementing Deny Permissions

```python
# User has payroll:read through their role
# But we want to temporarily block access

deny_permission = UserPermission(
    user_id=user.id,
    permission_key="payroll:read",
    tenant_id=1,
    is_grant=False,  # This is a DENY
    is_active=True,
    granted_at=datetime.utcnow(),
    expires_at=datetime.utcnow() + timedelta(hours=24),
    reason="Under investigation - access suspended for 24 hours"
)
db.add(deny_permission)
db.commit()

# Now user.has_permission("payroll:read") returns False
```

## Security Considerations

### 1. Password Security
- Passwords are hashed using Argon2 (via passlib)
- Password history is maintained to prevent reuse
- Account lockout after failed attempts

### 2. Session Management
- JWT tokens with expiration
- Session tracking with IP and user agent
- Permission caching for performance

### 3. Audit Trail
- All permission changes are logged
- Session activity is tracked
- Available through `/rbac/audit-logs` endpoint

### 4. Multi-Tenant Isolation
- Users can only access authorized tenants
- Permissions can be tenant-specific
- Role assignments are tenant-scoped

## Best Practices

### 1. Principle of Least Privilege
- Grant only necessary permissions
- Use roles instead of direct permissions when possible
- Regularly review and revoke unnecessary access

### 2. Role Design
- Create roles that match job functions
- Use hierarchical roles to reduce duplication
- Keep role names consistent and descriptive

### 3. Permission Naming
- Follow the `resource:action` pattern consistently
- Use clear, descriptive resource names
- Standard actions: read, write, delete, manage

### 4. Temporary Access
- Always set expiration for temporary permissions
- Document the reason for direct permission grants
- Regularly clean up expired permissions

### 5. Multi-Tenant Considerations
- Always specify tenant_id for tenant-specific operations
- Use global permissions sparingly
- Validate tenant access before operations

### 6. Performance Optimization
- Use session permission caching
- Batch permission checks when possible
- Index frequently queried fields

### 7. Security Auditing
- Regular review of audit logs
- Monitor for unusual permission patterns
- Alert on privilege escalation attempts

## Troubleshooting

### Common Issues

1. **"Permission Denied" Errors**
   - Check if user has the required permission
   - Verify no deny permissions are active
   - Ensure tenant context is correct

2. **Role Not Taking Effect**
   - Check role assignment tenant_id
   - Verify role is active
   - Ensure permissions are assigned to role

3. **Performance Issues**
   - Enable session caching
   - Check for N+1 permission queries
   - Consider permission prefetching

## Migration Guide

For existing systems migrating to RBAC:

1. **Map Existing Roles**: Convert existing role systems to RBAC roles
2. **Assign Permissions**: Map current access patterns to permissions
3. **Migrate Users**: Assign appropriate roles to existing users
4. **Test Thoroughly**: Verify all access patterns work correctly
5. **Enable Gradually**: Roll out RBAC enforcement incrementally

## API Integration

### Using RBAC in Your Application

```python
# Dependency for protecting endpoints
from core.rbac_auth import require_permissions

@router.post("/sensitive-operation")
@require_permissions(["admin:write", "system:manage"])
async def sensitive_operation(
    current_user: User = Depends(get_current_user)
):
    # Only users with both permissions can access
    pass
```

### Custom Permission Checks

```python
# For complex permission logic
def check_custom_access(user_id: int, resource_id: str) -> bool:
    # Check ownership
    if is_resource_owner(user_id, resource_id):
        return True
    
    # Check permission
    return rbac_service.check_user_permission(
        user_id=user_id,
        permission_key="resource:manage",
        resource_id=resource_id
    )
```

## Conclusion

The AuraConnect RBAC system provides comprehensive access control with flexibility for complex authorization requirements. By following the documented patterns and best practices, you can ensure secure and efficient access management across your application.