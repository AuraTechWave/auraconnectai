# Authentication & Authorization Guide

## Overview

AuraConnect uses JWT (JSON Web Token) based authentication with refresh tokens for secure API access.

## Authentication Flow

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant Auth Service
    participant Database

    Client->>API: POST /auth/login {username, password}
    API->>Auth Service: Validate credentials
    Auth Service->>Database: Check user
    Database-->>Auth Service: User data
    Auth Service-->>API: Generate tokens
    API-->>Client: {access_token, refresh_token, expires_in}
    
    Note over Client: Store tokens securely
    
    Client->>API: GET /orders (Bearer: access_token)
    API->>Auth Service: Validate token
    Auth Service-->>API: Token valid
    API-->>Client: Order data
    
    Note over Client: Token expires
    
    Client->>API: POST /auth/refresh {refresh_token}
    API->>Auth Service: Validate refresh token
    Auth Service-->>API: Generate new access token
    API-->>Client: {access_token, expires_in}
```

## Authentication Endpoints

### Login
```http
POST /auth/login
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "securepassword"
}

Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": 1,
    "username": "user@example.com",
    "roles": ["manager", "staff"]
  }
}
```

### Refresh Token
```http
POST /auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}

Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "expires_in": 1800
}
```

### Logout
```http
POST /auth/logout
Authorization: Bearer {access_token}

Response:
{
  "message": "Successfully logged out"
}
```

## Using Authentication

### Request Headers
Include the access token in the Authorization header:

```http
GET /api/v1/orders
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### Token Expiration
- **Access tokens**: Expire after 30 minutes
- **Refresh tokens**: Expire after 7 days
- **Refresh rotation**: New refresh token issued on each refresh

## Role-Based Access Control (RBAC)

### User Roles

| Role | Description | Permissions |
|------|-------------|-------------|
| `super_admin` | System administrator | Full access |
| `admin` | Restaurant administrator | All restaurant operations |
| `manager` | Restaurant manager | Operations, reports, staff |
| `payroll_manager` | Payroll administrator | Payroll, tax, employee data |
| `staff` | Regular staff | Orders, basic operations |
| `viewer` | Read-only access | View reports only |

### Permission Matrix

| Resource | Viewer | Staff | Manager | Admin | Super Admin |
|----------|--------|-------|---------|-------|-------------|
| Orders | Read | CRUD | CRUD | CRUD | CRUD |
| Menu | Read | Read | CRUD | CRUD | CRUD |
| Staff | - | Read own | CRUD | CRUD | CRUD |
| Payroll | - | Read own | Read | CRUD | CRUD |
| Reports | Read | - | Read | CRUD | CRUD |
| Settings | - | - | Read | CRUD | CRUD |

### Checking Permissions

The API automatically checks permissions. Insufficient permissions return:

```json
{
  "error": {
    "code": "AUTH_INSUFFICIENT_PERMISSIONS",
    "message": "You don't have permission to access this resource",
    "required_permission": "payroll:write"
  }
}
```

## Security Best Practices

### Token Storage
- **Never store tokens in localStorage** - Use httpOnly cookies or secure storage
- **Mobile apps**: Use secure keychain/keystore
- **Web apps**: Store in memory or httpOnly cookies

### Token Refresh Strategy
```javascript
// Example refresh logic
async function makeAuthenticatedRequest(url, options = {}) {
  let response = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'Authorization': `Bearer ${getAccessToken()}`
    }
  });

  if (response.status === 401) {
    // Token expired, try refresh
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      // Retry with new token
      response = await fetch(url, {
        ...options,
        headers: {
          ...options.headers,
          'Authorization': `Bearer ${getAccessToken()}`
        }
      });
    }
  }

  return response;
}
```

### Security Headers
All authenticated requests should include:

```http
Authorization: Bearer {access_token}
X-Request-ID: {unique-request-id}
X-Client-Version: 1.0.0
```

## Multi-Factor Authentication (MFA)

### Enabling MFA
```http
POST /auth/mfa/enable
Authorization: Bearer {access_token}

Response:
{
  "secret": "JBSWY3DPEHPK3PXP",
  "qr_code": "data:image/png;base64,..."
}
```

### Login with MFA
```http
POST /auth/login
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "securepassword",
  "mfa_code": "123456"
}
```

## API Keys (Service Accounts)

For server-to-server communication:

```http
GET /api/v1/orders
X-API-Key: sk_live_abc123...
```

### Creating API Keys
```http
POST /auth/api-keys
Authorization: Bearer {admin_token}
Content-Type: application/json

{
  "name": "POS Integration",
  "permissions": ["orders:read", "orders:write"],
  "expires_at": "2025-12-31T23:59:59Z"
}
```

## OAuth2 Integration (Coming Soon)

Support for third-party authentication:
- Google OAuth
- Apple Sign In
- Restaurant POS OAuth

## Troubleshooting

### Common Issues

1. **"Invalid token"**
   - Token may be expired
   - Token may be malformed
   - Wrong token type (using refresh token as access token)

2. **"Insufficient permissions"**
   - User role doesn't have required permission
   - Permission not granted to API key
   - Tenant isolation preventing access

3. **"Account locked"**
   - Too many failed login attempts
   - Account disabled by admin
   - Email not verified

### Debug Headers

Include these for troubleshooting:
```http
X-Debug-Auth: true
X-Debug-Request-ID: {request-id}
```