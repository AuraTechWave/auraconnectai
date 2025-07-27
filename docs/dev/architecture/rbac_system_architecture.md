# Role-Based Access Control (RBAC) System Architecture

## Overview

The AuraConnect AI RBAC system provides comprehensive, fine-grained access control for all system operations. It implements a flexible role and permission-based security model that supports multi-tenancy, hierarchical roles, and session-based permission caching.

## System Design

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                      RBAC System                           │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │    Users    │  │    Roles    │  │    Permissions      │  │
│  │             │  │             │  │                     │  │
│  │ - ID        │  │ - ID        │  │ - ID                │  │
│  │ - Username  │  │ - Name      │  │ - Key               │  │
│  │ - Email     │  │ - Display   │  │ - Resource:Action   │  │
│  │ - Tenants   │  │ - Parent    │  │ - Description       │  │
│  │ - Status    │  │ - Tenants   │  │ - Tenants           │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│         │                │                      │           │
│         └────────────────┼──────────────────────┘           │
│                          │                                  │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │              Association Tables                         │  │
│  │  ┌─────────────────┐    ┌─────────────────────────────┐ │  │
│  │  │  User-Roles     │    │    Role-Permissions         │ │  │
│  │  │  - User ID      │    │    - Role ID                │ │  │
│  │  │  - Role ID      │    │    - Permission ID          │ │  │
│  │  │  - Tenant ID    │    │    - Granted At             │ │  │
│  │  │  - Expires At   │    │    - Granted By             │ │  │
│  │  │  - Granted By   │    └─────────────────────────────┘ │  │
│  │  └─────────────────┘                                    │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │              Enhanced Features                          │  │
│  │  ┌─────────────────┐    ┌─────────────────────────────┐ │  │
│  │  │ Direct Perms    │    │    RBAC Sessions            │ │  │
│  │  │ - User ID       │    │    - Session ID             │ │  │
│  │  │ - Permission    │    │    - User ID                │ │  │
│  │  │ - Grant/Deny    │    │    - Active Tenant          │ │  │
│  │  │ - Tenant/Rsrc   │    │    - Cached Permissions     │ │  │
│  │  │ - Expires At    │    │    - Cache Expires          │ │  │
│  │  └─────────────────┘    └─────────────────────────────┘ │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Permission Model

The system uses a **Resource:Action** permission model:

```
Permission Key: <resource>:<action>
Examples:
- staff:read         # View staff information
- staff:write        # Create/update staff records
- payroll:approve    # Approve payroll runs
- order:manage_kitchen # Kitchen operations access
- system:audit       # Access audit logs
```

### Role Hierarchy

Roles support hierarchical inheritance:

```
super_admin
├── admin
│   ├── manager
│   │   ├── staff_manager
│   │   └── kitchen_manager
│   └── payroll_manager
│       └── payroll_clerk
└── viewer
    └── server
```

## Database Schema

### Core Tables

#### rbac_users
```sql
CREATE TABLE rbac_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_email_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    phone VARCHAR(20),
    default_tenant_id INTEGER,
    accessible_tenant_ids JSONB DEFAULT '[]',
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP,
    password_changed_at TIMESTAMP DEFAULT NOW()
);
```

#### rbac_roles
```sql
CREATE TABLE rbac_roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    parent_role_id INTEGER REFERENCES rbac_roles(id),
    is_active BOOLEAN DEFAULT TRUE,
    is_system_role BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    tenant_ids JSONB DEFAULT '[]'
);
```

#### rbac_permissions
```sql
CREATE TABLE rbac_permissions (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    resource VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_system_permission BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    tenant_ids JSONB DEFAULT '[]'
);
```

### Association Tables

#### user_roles
```sql
CREATE TABLE user_roles (
    user_id INTEGER REFERENCES rbac_users(id),
    role_id INTEGER REFERENCES rbac_roles(id),
    tenant_id INTEGER,
    granted_at TIMESTAMP DEFAULT NOW(),
    granted_by INTEGER REFERENCES rbac_users(id),
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (user_id, role_id)
);
```

#### role_permissions
```sql
CREATE TABLE role_permissions (
    role_id INTEGER REFERENCES rbac_roles(id),
    permission_id INTEGER REFERENCES rbac_permissions(id),
    granted_at TIMESTAMP DEFAULT NOW(),
    granted_by INTEGER REFERENCES rbac_users(id),
    PRIMARY KEY (role_id, permission_id)
);
```

## API Endpoints

### Authentication Endpoints

#### Enhanced Login
```http
POST /auth/login/rbac?tenant_id=1
Content-Type: application/x-www-form-urlencoded

username=admin&password=secret
```

Response:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "access_expires_in": 1800,
  "refresh_expires_in": 604800,
  "session_id": "session_123",
  "user_info": {
    "id": 1,
    "username": "admin",
    "roles": ["admin"],
    "rbac_session_id": "rbac_session_456",
    "active_tenant_id": 1,
    "cached_permissions": {"1": ["staff:read", "payroll:write"]}
  }
}
```

#### User Info with RBAC
```http
GET /auth/me/rbac?tenant_id=1
Authorization: Bearer eyJ...
```

Response:
```json
{
  "id": 1,
  "username": "admin",
  "email": "admin@example.com",
  "first_name": "Admin",
  "last_name": "User",
  "is_active": true,
  "is_email_verified": true,
  "created_at": "2025-01-01T00:00:00Z",
  "last_login": "2025-01-01T12:00:00Z",
  "accessible_tenant_ids": [1, 2, 3],
  "default_tenant_id": 1,
  "roles": ["admin", "manager"],
  "permissions": ["staff:read", "staff:write", "payroll:approve", "order:read"]
}
```

#### Permission Check
```http
POST /auth/check-permission
Authorization: Bearer eyJ...
Content-Type: application/json

{
  "permission_key": "payroll:approve",
  "tenant_id": 1,
  "resource_id": "payroll_123"
}
```

### RBAC Management Endpoints

#### User Management
```http
GET /rbac/users                    # List users
POST /rbac/users                   # Create user
GET /rbac/users/{id}               # Get user
GET /rbac/users/{id}/permissions   # Get user permissions
```

#### Role Management
```http
GET /rbac/roles                    # List roles
POST /rbac/roles                   # Create role
GET /rbac/roles/{id}               # Get role
```

#### Permission Management
```http
GET /rbac/permissions              # List permissions
GET /rbac/permissions/{id}         # Get permission
```

#### Assignment Operations
```http
POST /rbac/assign-role             # Assign role to user
POST /rbac/remove-role             # Remove role from user
POST /rbac/assign-permission       # Assign permission to role
POST /rbac/remove-permission       # Remove permission from role
POST /rbac/grant-direct-permission # Grant direct permission to user
```

## Backend Implementation

### Service Layer

The `RBACService` class provides high-level operations:

```python
from backend.core.rbac_service import RBACService

# Initialize service
rbac_service = RBACService(db_session)

# User operations
user = rbac_service.create_user("username", "email", "password")
authenticated = rbac_service.authenticate_user("username", "password")

# Role operations
role = rbac_service.create_role("role_name", "Display Name")
rbac_service.assign_role_to_user(user_id, role_id, tenant_id)

# Permission operations
permission = rbac_service.create_permission("resource:action", "Name")
rbac_service.assign_permission_to_role(role_id, permission_id)

# Permission checking
has_permission = rbac_service.check_user_permission(
    user_id, "staff:read", tenant_id=1
)
```

### FastAPI Dependencies

Use RBAC dependencies for endpoint protection:

```python
from backend.core.rbac_auth import (
    require_permission, require_role, require_admin,
    RBACDependency
)

# Single permission
@app.get("/api/staff")
async def get_staff(user: RBACUser = Depends(require_permission("staff:read"))):
    pass

# Multiple permissions (any)
@app.post("/api/payroll/run")
async def run_payroll(
    user: RBACUser = Depends(require_permissions(["payroll:write", "payroll:approve"], require_all=False))
):
    pass

# Role-based
@app.get("/api/admin/settings")
async def admin_settings(user: RBACUser = Depends(require_admin())):
    pass

# Custom dependency
advanced_dependency = RBACDependency(
    required_permissions=["order:write"],
    required_roles=["manager"],
    tenant_aware=True,
    allow_admin_override=True
)

@app.post("/api/orders")
async def create_order(user: RBACUser = Depends(advanced_dependency)):
    pass
```

## Frontend Implementation

### React Context and Hooks

```tsx
import { RBACProvider, useRBAC } from './hooks/useRBAC';

// App setup
function App() {
  return (
    <RBACProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<LoginForm />} />
          <Route path="/dashboard" element={<Dashboard />} />
        </Routes>
      </Router>
    </RBACProvider>
  );
}

// Component usage
function Dashboard() {
  const { user, hasPermission, hasRole, login, logout } = useRBAC();
  
  const canViewPayroll = hasPermission('payroll:read');
  const isManager = hasRole('manager');
  
  return (
    <div>
      <h1>Welcome, {user?.username}</h1>
      {canViewPayroll && <PayrollSection />}
      {isManager && <ManagementTools />}
    </div>
  );
}
```

### Guard Components

```tsx
import { PermissionGuard, RoleGuard, PayrollGuard } from './components/rbac/RBACGuard';

function ProtectedContent() {
  return (
    <div>
      <PermissionGuard permission="staff:read">
        <StaffList />
      </PermissionGuard>
      
      <RoleGuard roles={["admin", "manager"]}>
        <AdminPanel />
      </RoleGuard>
      
      <PayrollGuard action="approve">
        <PayrollApprovalButton />
      </PayrollGuard>
    </div>
  );
}
```

### Convenience Hooks

```tsx
import { usePermission, useRole, useIsAdmin } from './hooks/useRBAC';

function ComponentWithPermissions() {
  const canEdit = usePermission('staff:write');
  const isAdmin = useIsAdmin();
  const hasManagerRole = useRole('manager');
  
  return (
    <div>
      {canEdit && <EditButton />}
      {isAdmin && <AdminControls />}
      {hasManagerRole && <ManagerDashboard />}
    </div>
  );
}
```

## Multi-Tenancy Support

### Tenant-Scoped Permissions

```python
# Backend: Check permission for specific tenant
has_permission = rbac_service.check_user_permission(
    user_id=1,
    permission_key="staff:read",
    tenant_id=2  # Specific tenant
)

# Grant tenant-specific permission
rbac_service.grant_direct_permission(
    user_id=1,
    permission_key="payroll:approve",
    tenant_id=2,  # Only for tenant 2
    expires_at=datetime.utcnow() + timedelta(days=30)
)
```

```tsx
// Frontend: Tenant context
const { switchTenant, activeTenantId } = useRBAC();

// Switch active tenant
await switchTenant(2);

// Check permission for specific tenant
const canApprove = hasPermission('payroll:approve', 2);
```

## Security Features

### Account Lockout
- Automatic lockout after 5 failed login attempts
- 30-minute lockout duration
- Reset on successful login

### Session Management
- Redis-based session storage
- Permission caching for performance
- Session expiration and cleanup
- Multi-device session tracking

### Token Security
- JWT with unique token IDs (JTI)
- Token blacklisting on logout
- Refresh token rotation
- Session-aware token validation

### Audit Trail
- All role/permission changes logged
- User authentication events tracked
- Administrative actions recorded

## Performance Considerations

### Permission Caching

```python
# Session-based permission caching
session = rbac_service.create_rbac_session(
    session_id="session_123",
    user_id=1,
    active_tenant_id=1,
    # Permissions cached automatically
)

# Cache refresh
rbac_service.refresh_session_cache("session_123")
```

### Database Optimizations
- Indexed permission keys and user IDs
- Efficient join queries for role inheritance
- Bulk permission checking operations
- Connection pooling and query optimization

### Frontend Optimizations
- React context for global state
- Memoized permission checks
- Lazy loading of permission data
- Local storage for session persistence

## Migration and Setup

### Database Migration
```bash
# Run RBAC migration
alembic upgrade 20250727_1600_0012

# Setup default roles and permissions
python -c "
from backend.core.rbac_service import RBACService
from backend.core.database import get_db
rbac_service = RBACService(next(get_db()))
rbac_service.setup_default_roles_and_permissions()
"
```

### Environment Configuration
```env
# JWT Settings
JWT_SECRET_KEY=your-secret-key-here
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Database
DATABASE_URL=postgresql://user:password@localhost/auraconnect

# Redis (for sessions)
REDIS_URL=redis://localhost:6379/0
```

## Best Practices

### Permission Design
1. Use specific, granular permissions
2. Follow `resource:action` naming convention
3. Avoid overly broad permissions
4. Consider permission inheritance

### Role Design
1. Create role hierarchies that reflect business structure
2. Assign minimum necessary permissions
3. Use descriptive role names
4. Document role purposes and responsibilities

### Security
1. Always validate permissions server-side
2. Use tenant-aware permission checking
3. Implement proper session management
4. Regular permission audits and cleanup

### Performance
1. Cache permissions at session level
2. Use bulk operations for role assignments
3. Monitor database query performance
4. Implement pagination for large datasets

## Testing

### Backend Tests
```bash
# Run RBAC tests
pytest backend/tests/test_rbac_system.py -v

# Test specific functionality
pytest backend/tests/test_rbac_system.py::TestRBACPermissionChecking -v
```

### Frontend Tests
```bash
# Run RBAC hook tests
npm test frontend/hooks/__tests__/useRBAC.test.tsx

# Run guard component tests
npm test frontend/components/rbac/
```

## Troubleshooting

### Common Issues

1. **Permission Denied Errors**
   - Verify user has required role/permission
   - Check tenant context
   - Confirm role-permission assignments

2. **Session Issues**
   - Check Redis connectivity
   - Verify session expiration
   - Clear browser storage if needed

3. **Performance Issues**
   - Monitor permission cache hit rates
   - Check database query performance
   - Review role inheritance depth

### Debug Tools

```python
# Check user permissions
user_permissions = rbac_service.get_user_permissions(user_id, tenant_id)
print(f"User permissions: {user_permissions}")

# Check role assignments
user_roles = rbac_service.get_user_roles(user_id, tenant_id)
print(f"User roles: {[role.name for role in user_roles]}")
```

```tsx
// Frontend debugging
const { user, hasPermission } = useRBAC();
console.log('Current user:', user);
console.log('Has staff:read:', hasPermission('staff:read'));
```

## Conclusion

The AuraConnect AI RBAC system provides a comprehensive, secure, and scalable solution for access control. It supports complex organizational structures while maintaining performance and usability. The system is designed to grow with your organization's needs while providing the security and audit capabilities required for enterprise applications.