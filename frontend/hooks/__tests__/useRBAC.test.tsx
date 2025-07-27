/**
 * Test suite for RBAC hooks and components
 */

import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import { renderHook } from '@testing-library/react';
import { rest } from 'msw';
import { setupServer } from 'msw/node';
import { RBACProvider, useRBAC, usePermission, useRole } from '../useRBAC';

// Mock API responses
const mockUserData = {
  id: 1,
  username: 'testuser',
  email: 'test@example.com',
  first_name: 'Test',
  last_name: 'User',
  is_active: true,
  is_email_verified: true,
  created_at: '2025-01-01T00:00:00Z',
  last_login: '2025-01-01T12:00:00Z',
  accessible_tenant_ids: [1, 2, 3],
  default_tenant_id: 1,
  roles: ['manager', 'staff_viewer'],
  permissions: ['staff:read', 'staff:write', 'order:read', 'payroll:read']
};

const mockLoginResponse = {
  access_token: 'mock-access-token',
  refresh_token: 'mock-refresh-token',
  token_type: 'bearer',
  access_expires_in: 1800,
  refresh_expires_in: 604800,
  session_id: 'mock-session-id',
  user_info: {
    id: 1,
    username: 'testuser',
    roles: ['manager'],
    active_tenant_id: 1,
    rbac_session_id: 'rbac-session-123'
  }
};

// MSW server setup
const server = setupServer(
  rest.post('/auth/login/rbac', (req, res, ctx) => {
    return res(ctx.json(mockLoginResponse));
  }),
  
  rest.get('/auth/me/rbac', (req, res, ctx) => {
    const authHeader = req.headers.get('Authorization');
    if (!authHeader || !authHeader.includes('mock-access-token')) {
      return res(ctx.status(401), ctx.json({ detail: 'Unauthorized' }));
    }
    return res(ctx.json(mockUserData));
  }),
  
  rest.post('/auth/check-permission', (req, res, ctx) => {
    return res(ctx.json({
      permission_key: 'staff:read',
      has_permission: true,
      tenant_id: 1,
      checked_at: '2025-01-01T12:00:00Z'
    }));
  }),
  
  rest.post('/auth/logout', (req, res, ctx) => {
    return res(ctx.json({ message: 'Logged out successfully' }));
  })
);

beforeAll(() => server.listen());
afterEach(() => {
  server.resetHandlers();
  localStorage.clear();
});
afterAll(() => server.close());

// Test wrapper component
const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return <RBACProvider>{children}</RBACProvider>;
};

describe('useRBAC Hook', () => {
  it('initializes with loading state', () => {
    const { result } = renderHook(() => useRBAC(), {
      wrapper: TestWrapper
    });
    
    expect(result.current.loading).toBe(true);
    expect(result.current.user).toBe(null);
    expect(result.current.error).toBe(null);
  });
  
  it('loads user data when token exists', async () => {
    localStorage.setItem('access_token', 'mock-access-token');
    
    const { result } = renderHook(() => useRBAC(), {
      wrapper: TestWrapper
    });
    
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    
    expect(result.current.user).toEqual(mockUserData);
    expect(result.current.error).toBe(null);
  });
  
  it('handles login successfully', async () => {
    const { result } = renderHook(() => useRBAC(), {
      wrapper: TestWrapper
    });
    
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    
    let loginResult: boolean;
    await act(async () => {
      loginResult = await result.current.login('testuser', 'password123', 1);
    });
    
    expect(loginResult!).toBe(true);
    expect(localStorage.getItem('access_token')).toBe('mock-access-token');
    expect(localStorage.getItem('refresh_token')).toBe('mock-refresh-token');
  });
  
  it('handles login failure', async () => {
    server.use(
      rest.post('/auth/login/rbac', (req, res, ctx) => {
        return res(ctx.status(401), ctx.json({ detail: 'Invalid credentials' }));
      })
    );
    
    const { result } = renderHook(() => useRBAC(), {
      wrapper: TestWrapper
    });
    
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    
    let loginResult: boolean;
    await act(async () => {
      loginResult = await result.current.login('testuser', 'wrongpassword');
    });
    
    expect(loginResult!).toBe(false);
    expect(result.current.error).toBe('Invalid credentials');
  });
  
  it('handles logout', async () => {
    localStorage.setItem('access_token', 'mock-access-token');
    localStorage.setItem('refresh_token', 'mock-refresh-token');
    
    const { result } = renderHook(() => useRBAC(), {
      wrapper: TestWrapper
    });
    
    await waitFor(() => {
      expect(result.current.user).toEqual(mockUserData);
    });
    
    await act(async () => {
      await result.current.logout();
    });
    
    expect(result.current.user).toBe(null);
    expect(localStorage.getItem('access_token')).toBe(null);
    expect(localStorage.getItem('refresh_token')).toBe(null);
  });
});

describe('Permission Checking', () => {
  it('checks permissions correctly', async () => {
    localStorage.setItem('access_token', 'mock-access-token');
    
    const { result } = renderHook(() => useRBAC(), {
      wrapper: TestWrapper
    });
    
    await waitFor(() => {
      expect(result.current.user).toEqual(mockUserData);
    });
    
    // Test permission checking
    expect(result.current.hasPermission('staff:read')).toBe(true);
    expect(result.current.hasPermission('staff:write')).toBe(true);
    expect(result.current.hasPermission('staff:delete')).toBe(false);
    
    // Test admin override (user is not admin in mock data)
    expect(result.current.hasPermission('admin:only')).toBe(false);
  });
  
  it('checks roles correctly', async () => {
    localStorage.setItem('access_token', 'mock-access-token');
    
    const { result } = renderHook(() => useRBAC(), {
      wrapper: TestWrapper
    });
    
    await waitFor(() => {
      expect(result.current.user).toEqual(mockUserData);
    });
    
    // Test role checking
    expect(result.current.hasRole('manager')).toBe(true);
    expect(result.current.hasRole('staff_viewer')).toBe(true);
    expect(result.current.hasRole('admin')).toBe(false);
    
    // Test multiple roles
    expect(result.current.hasAnyRole(['manager', 'admin'])).toBe(true);
    expect(result.current.hasAnyRole(['admin', 'super_admin'])).toBe(false);
    expect(result.current.hasAllRoles(['manager', 'staff_viewer'])).toBe(true);
    expect(result.current.hasAllRoles(['manager', 'admin'])).toBe(false);
  });
  
  it('checks multiple permissions correctly', async () => {
    localStorage.setItem('access_token', 'mock-access-token');
    
    const { result } = renderHook(() => useRBAC(), {
      wrapper: TestWrapper
    });
    
    await waitFor(() => {
      expect(result.current.user).toEqual(mockUserData);
    });
    
    // Test multiple permissions
    expect(result.current.hasAnyPermission(['staff:read', 'admin:write'])).toBe(true);
    expect(result.current.hasAnyPermission(['admin:write', 'system:backup'])).toBe(false);
    expect(result.current.hasAllPermissions(['staff:read', 'order:read'])).toBe(true);
    expect(result.current.hasAllPermissions(['staff:read', 'admin:write'])).toBe(false);
  });
  
  it('performs remote permission check', async () => {
    localStorage.setItem('access_token', 'mock-access-token');
    
    const { result } = renderHook(() => useRBAC(), {
      wrapper: TestWrapper
    });
    
    await waitFor(() => {
      expect(result.current.user).toEqual(mockUserData);
    });
    
    const hasPermission = await result.current.checkPermission('staff:read', 1);
    expect(hasPermission).toBe(true);
  });
});

describe('Convenience Hooks', () => {
  it('usePermission hook works correctly', async () => {
    localStorage.setItem('access_token', 'mock-access-token');
    
    const { result } = renderHook(() => usePermission('staff:read'), {
      wrapper: TestWrapper
    });
    
    await waitFor(() => {
      expect(result.current).toBe(true);
    });
  });
  
  it('useRole hook works correctly', async () => {
    localStorage.setItem('access_token', 'mock-access-token');
    
    const { result } = renderHook(() => useRole('manager'), {
      wrapper: TestWrapper
    });
    
    await waitFor(() => {
      expect(result.current).toBe(true);
    });
  });
});

describe('Tenant Management', () => {
  it('switches tenant correctly', async () => {
    localStorage.setItem('access_token', 'mock-access-token');
    
    const { result } = renderHook(() => useRBAC(), {
      wrapper: TestWrapper
    });
    
    await waitFor(() => {
      expect(result.current.user).toEqual(mockUserData);
    });
    
    await act(async () => {
      await result.current.switchTenant(2);
    });
    
    expect(result.current.activeTenantId).toBe(2);
  });
  
  it('handles unauthorized tenant switch', async () => {
    localStorage.setItem('access_token', 'mock-access-token');
    
    const { result } = renderHook(() => useRBAC(), {
      wrapper: TestWrapper
    });
    
    await waitFor(() => {
      expect(result.current.user).toEqual(mockUserData);
    });
    
    await act(async () => {
      await result.current.switchTenant(999); // Not in accessible_tenant_ids
    });
    
    expect(result.current.error).toBe('Access denied for this tenant');
  });
});

describe('Error Handling', () => {
  it('handles API errors gracefully', async () => {
    server.use(
      rest.get('/auth/me/rbac', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ detail: 'Server error' }));
      })
    );
    
    localStorage.setItem('access_token', 'mock-access-token');
    
    const { result } = renderHook(() => useRBAC(), {
      wrapper: TestWrapper
    });
    
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    
    expect(result.current.error).toBe('Failed to load user data');
    expect(result.current.user).toBe(null);
  });
  
  it('handles token expiration', async () => {
    server.use(
      rest.get('/auth/me/rbac', (req, res, ctx) => {
        return res(ctx.status(401), ctx.json({ detail: 'Token expired' }));
      })
    );
    
    localStorage.setItem('access_token', 'expired-token');
    
    const { result } = renderHook(() => useRBAC(), {
      wrapper: TestWrapper
    });
    
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    
    // Should clear auth state on 401
    expect(result.current.user).toBe(null);
    expect(localStorage.getItem('access_token')).toBe(null);
  });
});

describe('Admin Detection', () => {
  it('detects admin users correctly', async () => {
    const adminUserData = {
      ...mockUserData,
      roles: ['admin', 'manager']
    };
    
    server.use(
      rest.get('/auth/me/rbac', (req, res, ctx) => {
        return res(ctx.json(adminUserData));
      })
    );
    
    localStorage.setItem('access_token', 'mock-access-token');
    
    const { result } = renderHook(() => useRBAC(), {
      wrapper: TestWrapper
    });
    
    await waitFor(() => {
      expect(result.current.user).toEqual(adminUserData);
    });
    
    expect(result.current.isAdmin()).toBe(true);
  });
  
  it('detects non-admin users correctly', async () => {
    localStorage.setItem('access_token', 'mock-access-token');
    
    const { result } = renderHook(() => useRBAC(), {
      wrapper: TestWrapper
    });
    
    await waitFor(() => {
      expect(result.current.user).toEqual(mockUserData);
    });
    
    expect(result.current.isAdmin()).toBe(false);
  });
});