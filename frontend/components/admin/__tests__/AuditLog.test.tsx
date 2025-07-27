import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { rest } from 'msw';
import { setupServer } from 'msw/node';
import AuditLog from '../AuditLog';
import { RBACProvider } from '../../../hooks/useRBAC';

const mockAdminUser = {
  id: 1,
  username: 'admin',
  email: 'admin@example.com',
  roles: ['admin'],
  permissions: ['system:audit']
};

const mockAuditLogs = {
  entries: [
    {
      id: 1,
      action: 'create_user',
      entity_type: 'user',
      entity_id: 123,
      details: JSON.stringify({ username: 'newuser', email: 'newuser@example.com' }),
      performed_by_user_id: 1,
      performed_by_username: 'admin',
      tenant_id: 1,
      created_at: '2025-01-01T12:00:00Z'
    },
    {
      id: 2,
      action: 'assign_role',
      entity_type: 'user_role',
      entity_id: 123,
      details: JSON.stringify({ role: 'manager', user: 'testuser' }),
      performed_by_user_id: 1,
      performed_by_username: 'admin',
      tenant_id: 1,
      created_at: '2025-01-01T11:00:00Z'
    }
  ],
  total_count: 2,
  page: 1,
  page_size: 50
};

const server = setupServer(
  rest.get('/auth/me/rbac', (req, res, ctx) => {
    return res(ctx.json(mockAdminUser));
  }),
  rest.get('/rbac/audit-logs', (req, res, ctx) => {
    return res(ctx.json(mockAuditLogs));
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return <RBACProvider>{children}</RBACProvider>;
};

describe('AuditLog', () => {
  beforeEach(() => {
    localStorage.setItem('access_token', 'mock-admin-token');
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('renders audit log interface', async () => {
    render(
      <TestWrapper>
        <AuditLog />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Audit Log')).toBeInTheDocument();
    });

    expect(screen.getByText('Track all RBAC-related changes and user activities')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Search by username, action, or resource...')).toBeInTheDocument();
  });

  it('displays audit log entries', async () => {
    render(
      <TestWrapper>
        <AuditLog />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('admin')).toBeInTheDocument();
    });

    expect(screen.getByText('create user')).toBeInTheDocument();
    expect(screen.getByText('assign role')).toBeInTheDocument();
    expect(screen.getByText('user')).toBeInTheDocument();
    expect(screen.getByText('user_role')).toBeInTheDocument();
  });

  it('filters by action type', async () => {
    render(
      <TestWrapper>
        <AuditLog />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Audit Log')).toBeInTheDocument();
    });

    const typeFilter = screen.getByDisplayValue('All Actions');
    fireEvent.change(typeFilter, { target: { value: 'user_management' } });

    expect(typeFilter).toHaveValue('user_management');
  });

  it('searches by term', async () => {
    render(
      <TestWrapper>
        <AuditLog />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Audit Log')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Search by username, action, or resource...');
    fireEvent.change(searchInput, { target: { value: 'create' } });

    expect(searchInput).toHaveValue('create');
  });

  it('filters by date range', async () => {
    render(
      <TestWrapper>
        <AuditLog />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Audit Log')).toBeInTheDocument();
    });

    const dateInputs = screen.getAllByDisplayValue('');
    const startDateInput = dateInputs.find(input => 
      input.getAttribute('type') === 'date'
    );

    if (startDateInput) {
      fireEvent.change(startDateInput, { target: { value: '2025-01-01' } });
      expect(startDateInput).toHaveValue('2025-01-01');
    }
  });

  it('shows pagination controls', async () => {
    render(
      <TestWrapper>
        <AuditLog />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Audit Log')).toBeInTheDocument();
    });

    expect(screen.getByText('Previous')).toBeInTheDocument();
    expect(screen.getByText('Next')).toBeInTheDocument();
    expect(screen.getByText('Page 1 of 1')).toBeInTheDocument();
  });

  it('navigates pages', async () => {
    server.use(
      rest.get('/rbac/audit-logs', (req, res, ctx) => {
        return res(ctx.json({
          ...mockAuditLogs,
          total_count: 100,
          page: 1
        }));
      })
    );

    render(
      <TestWrapper>
        <AuditLog />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Page 1 of 2')).toBeInTheDocument();
    });

    const nextButton = screen.getByText('Next');
    expect(nextButton).not.toBeDisabled();
    
    const prevButton = screen.getByText('Previous');
    expect(prevButton).toBeDisabled();
  });

  it('shows access denied for users without audit permission', async () => {
    server.use(
      rest.get('/auth/me/rbac', (req, res, ctx) => {
        return res(ctx.json({
          ...mockAdminUser,
          permissions: [] // No audit permission
        }));
      })
    );

    render(
      <TestWrapper>
        <AuditLog />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('You do not have permission to view audit logs.')).toBeInTheDocument();
    });

    expect(screen.getByText('Required permission: system:audit')).toBeInTheDocument();
  });

  it('handles API errors gracefully', async () => {
    server.use(
      rest.get('/rbac/audit-logs', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ detail: 'Server error' }));
      })
    );

    render(
      <TestWrapper>
        <AuditLog />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Server error')).toBeInTheDocument();
    });
  });

  it('shows loading state', () => {
    server.use(
      rest.get('/rbac/audit-logs', (req, res, ctx) => {
        return res(ctx.delay(1000), ctx.json(mockAuditLogs));
      })
    );

    render(
      <TestWrapper>
        <AuditLog />
      </TestWrapper>
    );

    expect(screen.getByText('Loading audit logs...')).toBeInTheDocument();
  });

  it('shows empty state when no logs found', async () => {
    server.use(
      rest.get('/rbac/audit-logs', (req, res, ctx) => {
        return res(ctx.json({
          entries: [],
          total_count: 0,
          page: 1,
          page_size: 50
        }));
      })
    );

    render(
      <TestWrapper>
        <AuditLog />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('No audit logs found for the selected criteria')).toBeInTheDocument();
    });
  });

  it('formats timestamps correctly', async () => {
    render(
      <TestWrapper>
        <AuditLog />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Audit Log')).toBeInTheDocument();
    });

    // Check that timestamps are formatted as locale strings
    const timestamp = new Date('2025-01-01T12:00:00Z').toLocaleString();
    expect(screen.getByText(timestamp)).toBeInTheDocument();
  });

  it('displays action icons correctly', async () => {
    render(
      <TestWrapper>
        <AuditLog />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Audit Log')).toBeInTheDocument();
    });

    // Check for action badges with appropriate styling
    const createAction = screen.getByText('create user');
    expect(createAction.closest('.action-badge')).toHaveClass('success');

    const assignAction = screen.getByText('assign role');
    expect(assignAction.closest('.action-badge')).toHaveClass('success');
  });

  it('shows detailed information in expandable sections', async () => {
    render(
      <TestWrapper>
        <AuditLog />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Audit Log')).toBeInTheDocument();
    });

    const detailsButtons = screen.getAllByText('View Details');
    expect(detailsButtons).toHaveLength(2);

    // Click to expand details
    fireEvent.click(detailsButtons[0]);
    
    // Should show JSON formatted details
    expect(screen.getByText(/"username": "newuser"/)).toBeInTheDocument();
  });

  it('handles malformed JSON in details gracefully', async () => {
    server.use(
      rest.get('/rbac/audit-logs', (req, res, ctx) => {
        return res(ctx.json({
          entries: [{
            id: 1,
            action: 'test_action',
            entity_type: 'test',
            details: 'invalid json {',
            performed_by_user_id: 1,
            performed_by_username: 'admin',
            created_at: '2025-01-01T12:00:00Z'
          }],
          total_count: 1,
          page: 1,
          page_size: 50
        }));
      })
    );

    render(
      <TestWrapper>
        <AuditLog />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('View Details')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('View Details'));
    
    // Should show raw string when JSON parsing fails
    expect(screen.getByText('invalid json {')).toBeInTheDocument();
  });

  it('handles null details gracefully', async () => {
    server.use(
      rest.get('/rbac/audit-logs', (req, res, ctx) => {
        return res(ctx.json({
          entries: [{
            id: 1,
            action: 'test_action',
            entity_type: 'test',
            details: null,
            performed_by_user_id: 1,
            performed_by_username: 'admin',
            created_at: '2025-01-01T12:00:00Z'
          }],
          total_count: 1,
          page: 1,
          page_size: 50
        }));
      })
    );

    render(
      <TestWrapper>
        <AuditLog />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('View Details')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('View Details'));
    
    // Should show "No details available" for null details
    expect(screen.getByText('No details available')).toBeInTheDocument();
  });

  it('shows tenant information correctly', async () => {
    render(
      <TestWrapper>
        <AuditLog />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Audit Log')).toBeInTheDocument();
    });

    // Should show tenant ID for entries with tenant_id
    expect(screen.getByText('Tenant 1')).toBeInTheDocument();
  });

  it('shows global for entries without tenant', async () => {
    server.use(
      rest.get('/rbac/audit-logs', (req, res, ctx) => {
        return res(ctx.json({
          entries: [{
            id: 1,
            action: 'system_action',
            entity_type: 'system',
            performed_by_user_id: 1,
            performed_by_username: 'admin',
            tenant_id: null,
            created_at: '2025-01-01T12:00:00Z'
          }],
          total_count: 1,
          page: 1,
          page_size: 50
        }));
      })
    );

    render(
      <TestWrapper>
        <AuditLog />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Global')).toBeInTheDocument();
    });
  });
});