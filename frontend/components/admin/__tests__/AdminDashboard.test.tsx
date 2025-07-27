import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { rest } from 'msw';
import { setupServer } from 'msw/node';
import AdminDashboard from '../../../pages/admin/AdminDashboard';
import { RBACProvider } from '../../../hooks/useRBAC';

// Mock data
const mockAdminUser = {
  id: 1,
  username: 'admin',
  email: 'admin@example.com',
  roles: ['admin'],
  permissions: ['user:read', 'user:write', 'role:read', 'role:write', 'system:audit']
};

const mockUsers = [
  {
    id: 1,
    username: 'testuser',
    email: 'test@example.com',
    is_active: true,
    roles: ['manager']
  }
];

const mockRoles = [
  {
    id: 1,
    name: 'admin',
    display_name: 'Administrator',
    permissions: []
  }
];

// MSW server setup
const server = setupServer(
  rest.get('/auth/me/rbac', (req, res, ctx) => {
    return res(ctx.json(mockAdminUser));
  }),
  rest.get('/rbac/users', (req, res, ctx) => {
    return res(ctx.json({ items: mockUsers, total_pages: 1 }));
  }),
  rest.get('/rbac/roles', (req, res, ctx) => {
    return res(ctx.json(mockRoles));
  }),
  rest.get('/rbac/permissions', (req, res, ctx) => {
    return res(ctx.json([]));
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return <RBACProvider>{children}</RBACProvider>;
};

describe('AdminDashboard', () => {
  beforeEach(() => {
    localStorage.setItem('access_token', 'mock-admin-token');
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('renders admin dashboard with tabs', async () => {
    render(
      <TestWrapper>
        <AdminDashboard />
      </TestWrapper>
    );

    // Wait for auth to load
    await waitFor(() => {
      expect(screen.getByText('Admin Dashboard')).toBeInTheDocument();
    });

    // Check tabs are present
    expect(screen.getByText('Users')).toBeInTheDocument();
    expect(screen.getByText('Roles')).toBeInTheDocument();
    expect(screen.getByText('Permissions')).toBeInTheDocument();
    expect(screen.getByText('Audit Log')).toBeInTheDocument();
  });

  it('switches between tabs correctly', async () => {
    render(
      <TestWrapper>
        <AdminDashboard />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Admin Dashboard')).toBeInTheDocument();
    });

    // Default should be Users tab
    expect(screen.getByText('User Management')).toBeInTheDocument();

    // Switch to Roles tab
    fireEvent.click(screen.getByText('Roles'));
    await waitFor(() => {
      expect(screen.getByText('Role Management')).toBeInTheDocument();
    });

    // Switch to Permissions tab
    fireEvent.click(screen.getByText('Permissions'));
    await waitFor(() => {
      expect(screen.getByText('Permission Matrix')).toBeInTheDocument();
    });

    // Switch to Audit Log tab
    fireEvent.click(screen.getByText('Audit Log'));
    await waitFor(() => {
      expect(screen.getByText('Audit Log')).toBeInTheDocument();
    });
  });

  it('shows access denied for non-admin users', async () => {
    server.use(
      rest.get('/auth/me/rbac', (req, res, ctx) => {
        return res(ctx.json({
          ...mockAdminUser,
          roles: ['user'], // Not admin
          permissions: []
        }));
      })
    );

    render(
      <TestWrapper>
        <AdminDashboard />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Access Denied: Admin privileges required')).toBeInTheDocument();
    });
  });

  it('handles loading state', () => {
    // Mock long loading
    server.use(
      rest.get('/auth/me/rbac', (req, res, ctx) => {
        return res(ctx.delay(1000), ctx.json(mockAdminUser));
      })
    );

    render(
      <TestWrapper>
        <AdminDashboard />
      </TestWrapper>
    );

    // Should show admin dashboard structure even during loading
    expect(screen.getByText('Admin Dashboard')).toBeInTheDocument();
  });
});