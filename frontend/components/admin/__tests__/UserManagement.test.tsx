import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { rest } from 'msw';
import { setupServer } from 'msw/node';
import UserManagement from '../UserManagement';
import { RBACProvider } from '../../../hooks/useRBAC';

const mockUser = {
  id: 1,
  username: 'admin',
  email: 'admin@example.com',
  roles: ['admin'],
  permissions: ['user:read', 'user:write', 'user:delete', 'user:manage_roles']
};

const mockUsers = [
  {
    id: 1,
    username: 'testuser',
    email: 'test@example.com',
    first_name: 'Test',
    last_name: 'User',
    is_active: true,
    is_email_verified: true,
    created_at: '2025-01-01T00:00:00Z',
    last_login: '2025-01-01T12:00:00Z',
    accessible_tenant_ids: [1],
    default_tenant_id: 1,
    roles: ['manager']
  },
  {
    id: 2,
    username: 'inactive',
    email: 'inactive@example.com',
    is_active: false,
    is_email_verified: false,
    created_at: '2025-01-01T00:00:00Z',
    accessible_tenant_ids: [1],
    roles: []
  }
];

const server = setupServer(
  rest.get('/auth/me/rbac', (req, res, ctx) => {
    return res(ctx.json(mockUser));
  }),
  rest.get('/rbac/users', (req, res, ctx) => {
    return res(ctx.json({ items: mockUsers, total_pages: 1 }));
  }),
  rest.post('/rbac/users', (req, res, ctx) => {
    return res(ctx.json({ id: 3, username: 'newuser' }));
  }),
  rest.delete('/rbac/users/:id', (req, res, ctx) => {
    return res(ctx.json({ message: 'User deleted' }));
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return <RBACProvider>{children}</RBACProvider>;
};

describe('UserManagement', () => {
  beforeEach(() => {
    localStorage.setItem('access_token', 'mock-admin-token');
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('renders user management interface', async () => {
    render(
      <TestWrapper>
        <UserManagement />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('User Management')).toBeInTheDocument();
    });

    expect(screen.getByText('Add User')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Search by username or email...')).toBeInTheDocument();
  });

  it('displays user list', async () => {
    render(
      <TestWrapper>
        <UserManagement />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('testuser')).toBeInTheDocument();
    });

    expect(screen.getByText('test@example.com')).toBeInTheDocument();
    expect(screen.getByText('Test User')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('filters users by status', async () => {
    render(
      <TestWrapper>
        <UserManagement />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('testuser')).toBeInTheDocument();
    });

    // Filter to inactive users
    fireEvent.click(screen.getByText('Inactive'));

    await waitFor(() => {
      expect(screen.queryByText('testuser')).not.toBeInTheDocument();
    });
  });

  it('opens user form when add user is clicked', async () => {
    render(
      <TestWrapper>
        <UserManagement />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Add User')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Add User'));

    await waitFor(() => {
      expect(screen.getByText('Create New User')).toBeInTheDocument();
    });
  });

  it('handles user deletion', async () => {
    // Mock confirm dialog
    window.confirm = jest.fn(() => true);

    render(
      <TestWrapper>
        <UserManagement />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('testuser')).toBeInTheDocument();
    });

    // Find and click delete button
    const deleteButtons = screen.getAllByTitle('Delete user');
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
      expect(window.confirm).toHaveBeenCalledWith('Are you sure you want to delete this user?');
    });
  });

  it('searches users', async () => {
    render(
      <TestWrapper>
        <UserManagement />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('testuser')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Search by username or email...');
    fireEvent.change(searchInput, { target: { value: 'test' } });

    // Search functionality would filter the list
    expect(searchInput).toHaveValue('test');
  });

  it('shows read-only interface for users without write permissions', async () => {
    server.use(
      rest.get('/auth/me/rbac', (req, res, ctx) => {
        return res(ctx.json({
          ...mockUser,
          permissions: ['user:read'] // Only read permission
        }));
      })
    );

    render(
      <TestWrapper>
        <UserManagement />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('User Management')).toBeInTheDocument();
    });

    // Should not show Add User button
    expect(screen.queryByText('Add User')).not.toBeInTheDocument();
  });
});