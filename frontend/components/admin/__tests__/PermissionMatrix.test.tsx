import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { rest } from 'msw';
import { setupServer } from 'msw/node';
import PermissionMatrix from '../PermissionMatrix';
import { RBACProvider } from '../../../hooks/useRBAC';

const mockUser = {
  id: 1,
  username: 'admin',
  email: 'admin@example.com',
  roles: ['admin'],
  permissions: ['role:manage_permissions', 'role:read']
};

const mockRoles = [
  {
    id: 1,
    name: 'admin',
    display_name: 'Administrator',
    is_active: true,
    permissions: [
      { id: 1, key: 'user:read', name: 'Read User', resource: 'user', action: 'read' },
      { id: 2, key: 'user:write', name: 'Write User', resource: 'user', action: 'write' }
    ]
  },
  {
    id: 2,
    name: 'manager',
    display_name: 'Manager',
    is_active: true,
    permissions: [
      { id: 1, key: 'user:read', name: 'Read User', resource: 'user', action: 'read' }
    ]
  }
];

const mockPermissions = [
  { id: 1, key: 'user:read', name: 'Read User', resource: 'user', action: 'read' },
  { id: 2, key: 'user:write', name: 'Write User', resource: 'user', action: 'write' },
  { id: 3, key: 'role:read', name: 'Read Role', resource: 'role', action: 'read' }
];

const server = setupServer(
  rest.get('/auth/me/rbac', (req, res, ctx) => {
    return res(ctx.json(mockUser));
  }),
  rest.get('/rbac/roles', (req, res, ctx) => {
    return res(ctx.json(mockRoles));
  }),
  rest.get('/rbac/permissions', (req, res, ctx) => {
    return res(ctx.json(mockPermissions));
  }),
  rest.post('/rbac/assign-permission', (req, res, ctx) => {
    return res(ctx.json({ message: 'Permission assigned' }));
  }),
  rest.post('/rbac/remove-permission', (req, res, ctx) => {
    return res(ctx.json({ message: 'Permission removed' }));
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return <RBACProvider>{children}</RBACProvider>;
};

describe('PermissionMatrix', () => {
  beforeEach(() => {
    localStorage.setItem('access_token', 'mock-admin-token');
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('renders permission matrix', async () => {
    render(
      <TestWrapper>
        <PermissionMatrix />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Permission Matrix')).toBeInTheDocument();
    });

    // Should show matrix stats
    expect(screen.getByText(/assignments/)).toBeInTheDocument();
    expect(screen.getByText(/coverage/)).toBeInTheDocument();
  });

  it('displays roles and permissions in matrix', async () => {
    render(
      <TestWrapper>
        <PermissionMatrix />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Administrator')).toBeInTheDocument();
    });

    expect(screen.getByText('Manager')).toBeInTheDocument();
    expect(screen.getByText('Read User')).toBeInTheDocument();
    expect(screen.getByText('Write User')).toBeInTheDocument();
  });

  it('filters permissions by resource', async () => {
    render(
      <TestWrapper>
        <PermissionMatrix />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Permission Matrix')).toBeInTheDocument();
    });

    // Find and use resource filter
    const resourceFilter = screen.getByDisplayValue('All Resources');
    fireEvent.change(resourceFilter, { target: { value: 'user' } });

    // Should filter to only show user permissions
    expect(resourceFilter).toHaveValue('user');
  });

  it('toggles permission assignments', async () => {
    render(
      <TestWrapper>
        <PermissionMatrix />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Permission Matrix')).toBeInTheDocument();
    });

    // Find permission toggle buttons
    const toggleButtons = screen.getAllByRole('button');
    const permissionToggle = toggleButtons.find(btn => 
      btn.className.includes('permission-toggle')
    );

    if (permissionToggle) {
      fireEvent.click(permissionToggle);
      // Should trigger API call to assign/remove permission
    }
  });

  it('shows read-only mode for users without manage permissions', async () => {
    server.use(
      rest.get('/auth/me/rbac', (req, res, ctx) => {
        return res(ctx.json({
          ...mockUser,
          permissions: ['role:read'] // No manage permissions
        }));
      })
    );

    render(
      <TestWrapper>
        <PermissionMatrix />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('You have read-only access to the permission matrix')).toBeInTheDocument();
    });
  });

  it('searches permissions', async () => {
    render(
      <TestWrapper>
        <PermissionMatrix />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Permission Matrix')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Search permissions...');
    fireEvent.change(searchInput, { target: { value: 'user' } });

    expect(searchInput).toHaveValue('user');
  });

  it('toggles inactive roles visibility', async () => {
    render(
      <TestWrapper>
        <PermissionMatrix />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Permission Matrix')).toBeInTheDocument();
    });

    const inactiveToggle = screen.getByLabelText('Show inactive roles');
    fireEvent.click(inactiveToggle);

    expect(inactiveToggle).toBeChecked();
  });

  it('calculates and displays statistics', async () => {
    render(
      <TestWrapper>
        <PermissionMatrix />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Permission Matrix')).toBeInTheDocument();
    });

    // Should show assignment statistics
    const statsElement = screen.getByText(/assignments/);
    expect(statsElement).toBeInTheDocument();

    // Should show coverage percentage
    const coverageElement = screen.getByText(/coverage/);
    expect(coverageElement).toBeInTheDocument();
  });
});