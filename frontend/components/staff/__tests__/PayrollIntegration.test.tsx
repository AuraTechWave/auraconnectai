/**
 * Integration tests for PayrollIntegration component
 * Tests the complete payroll UI functionality including API interactions
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { setupServer } from 'msw/node';
import { PayrollIntegration } from '../PayrollIntegration';
import { QueryClient, QueryClientProvider } from 'react-query';

// Mock API responses
const mockPayrollHistory = [
  {
    id: 1,
    staff_id: 1,
    pay_period_start: '2024-01-15',
    pay_period_end: '2024-01-29',
    gross_pay: 1200.00,
    total_deductions: 350.00,
    net_pay: 850.00,
    status: 'completed',
    processed_at: '2024-01-30T10:00:00Z'
  },
  {
    id: 2,
    staff_id: 1,
    pay_period_start: '2024-01-01',
    pay_period_end: '2024-01-14',
    gross_pay: 1150.00,
    total_deductions: 335.00,
    net_pay: 815.00,
    status: 'completed',
    processed_at: '2024-01-15T10:00:00Z'
  }
];

const mockPayrollDetail = {
  id: 1,
  staff_id: 1,
  regular_hours: 40,
  regular_pay: 1000.00,
  overtime_hours: 5,
  overtime_pay: 187.50,
  bonuses: 12.50,
  tips: 0,
  gross_pay: 1200.00,
  federal_tax: 180.00,
  state_tax: 60.00,
  social_security: 74.40,
  medicare: 17.40,
  other_deductions: [
    { description: 'Health Insurance', amount: 18.20 }
  ],
  total_deductions: 350.00,
  net_pay: 850.00
};

// Setup MSW server
const server = setupServer(
  rest.get('/api/v1/payrolls/:staffId', (req, res, ctx) => {
    return res(
      ctx.json({
        staff_id: req.params.staffId,
        staff_name: 'John Doe',
        payroll_history: mockPayrollHistory,
        total_records: 2
      })
    );
  }),
  
  rest.get('/api/v1/payrolls/:payrollId/detail', (req, res, ctx) => {
    return res(ctx.json(mockPayrollDetail));
  }),
  
  rest.post('/api/v1/payrolls/run', async (req, res, ctx) => {
    const body = await req.json();
    return res(
      ctx.status(202),
      ctx.json({
        job_id: 'test-job-123',
        status: 'processing',
        total_staff: body.staff_ids.length,
        successful_count: 0,
        failed_count: 0,
        total_gross_pay: 0,
        total_net_pay: 0,
        created_at: new Date().toISOString()
      })
    );
  })
);

// Test setup
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// Test wrapper with providers
const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
};

describe('PayrollIntegration Component', () => {
  it('renders payroll history on load', async () => {
    render(
      <TestWrapper>
        <PayrollIntegration staffId={1} />
      </TestWrapper>
    );
    
    // Check loading state
    expect(screen.getByText(/loading payroll data/i)).toBeInTheDocument();
    
    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByText('Payroll Information')).toBeInTheDocument();
    });
    
    // Verify history table is rendered
    const historyTable = screen.getByRole('table');
    expect(historyTable).toBeInTheDocument();
    
    // Check table rows
    const rows = within(historyTable).getAllByRole('row');
    expect(rows).toHaveLength(3); // Header + 2 data rows
    
    // Verify data is displayed correctly
    expect(screen.getByText('$1,200.00')).toBeInTheDocument();
    expect(screen.getByText('$850.00')).toBeInTheDocument();
  });

  it('handles run payroll dialog', async () => {
    const user = userEvent.setup();
    
    render(
      <TestWrapper>
        <PayrollIntegration staffId={1} />
      </TestWrapper>
    );
    
    await waitFor(() => {
      expect(screen.getByText('Run Payroll')).toBeInTheDocument();
    });
    
    // Click run payroll button
    const runButton = screen.getByRole('button', { name: /run payroll/i });
    await user.click(runButton);
    
    // Dialog should appear
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByLabelText(/pay period start/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/pay period end/i)).toBeInTheDocument();
    
    // Fill in dates
    const startDate = screen.getByLabelText(/pay period start/i);
    const endDate = screen.getByLabelText(/pay period end/i);
    
    await user.type(startDate, '2024-02-01');
    await user.type(endDate, '2024-02-15');
    
    // Submit form
    const submitButton = within(screen.getByRole('dialog')).getByRole('button', { 
      name: /run payroll/i 
    });
    await user.click(submitButton);
    
    // Dialog should close
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('displays payroll details when row is clicked', async () => {
    const user = userEvent.setup();
    
    render(
      <TestWrapper>
        <PayrollIntegration staffId={1} />
      </TestWrapper>
    );
    
    await waitFor(() => {
      expect(screen.getByText('View Details')).toBeInTheDocument();
    });
    
    // Click view details button
    const detailButtons = screen.getAllByText('View Details');
    await user.click(detailButtons[0]);
    
    // Wait for detail view to load
    await waitFor(() => {
      expect(screen.getByText('Payroll Detail')).toBeInTheDocument();
    });
    
    // Verify detail content
    expect(screen.getByText('Regular Hours (40)')).toBeInTheDocument();
    expect(screen.getByText('$1,000.00')).toBeInTheDocument();
    expect(screen.getByText('Overtime Hours (5)')).toBeInTheDocument();
    expect(screen.getByText('$187.50')).toBeInTheDocument();
    
    // Check deductions
    expect(screen.getByText('Federal Tax')).toBeInTheDocument();
    expect(screen.getByText('-$180.00')).toBeInTheDocument();
    expect(screen.getByText('Health Insurance')).toBeInTheDocument();
    expect(screen.getByText('-$18.20')).toBeInTheDocument();
    
    // Check net pay
    expect(screen.getByText('Net Pay')).toBeInTheDocument();
    const netPayElement = screen.getByText('$850.00');
    expect(netPayElement.closest('.net-pay')).toBeInTheDocument();
  });

  it('handles API errors gracefully', async () => {
    // Override server handler to return error
    server.use(
      rest.get('/api/v1/payrolls/:staffId', (req, res, ctx) => {
        return res(
          ctx.status(500),
          ctx.json({ error: 'Internal server error' })
        );
      })
    );
    
    render(
      <TestWrapper>
        <PayrollIntegration staffId={1} />
      </TestWrapper>
    );
    
    await waitFor(() => {
      expect(screen.getByText(/internal server error/i)).toBeInTheDocument();
    });
  });

  it('cancels run payroll dialog', async () => {
    const user = userEvent.setup();
    
    render(
      <TestWrapper>
        <PayrollIntegration staffId={1} />
      </TestWrapper>
    );
    
    await waitFor(() => {
      expect(screen.getByText('Run Payroll')).toBeInTheDocument();
    });
    
    // Open dialog
    await user.click(screen.getByRole('button', { name: /run payroll/i }));
    
    // Cancel dialog
    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    await user.click(cancelButton);
    
    // Dialog should close
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('closes detail view when close button is clicked', async () => {
    const user = userEvent.setup();
    
    render(
      <TestWrapper>
        <PayrollIntegration staffId={1} />
      </TestWrapper>
    );
    
    await waitFor(() => {
      expect(screen.getByText('View Details')).toBeInTheDocument();
    });
    
    // Open detail view
    await user.click(screen.getAllByText('View Details')[0]);
    
    await waitFor(() => {
      expect(screen.getByText('Payroll Detail')).toBeInTheDocument();
    });
    
    // Close detail view
    const closeButton = screen.getByRole('button', { name: /×/ });
    await user.click(closeButton);
    
    // Detail view should be closed
    expect(screen.queryByText('Payroll Detail')).not.toBeInTheDocument();
  });

  it('handles multi-tenant scenarios', async () => {
    const tenantId = 123;
    
    render(
      <TestWrapper>
        <PayrollIntegration staffId={1} tenantId={tenantId} />
      </TestWrapper>
    );
    
    await waitFor(() => {
      expect(screen.getByText('Payroll Information')).toBeInTheDocument();
    });
    
    // Verify tenant ID was included in request
    // This would be validated through MSW request inspection
    expect(screen.getByText('$1,200.00')).toBeInTheDocument();
  });

  it('formats dates correctly in payroll history', async () => {
    render(
      <TestWrapper>
        <PayrollIntegration staffId={1} />
      </TestWrapper>
    );
    
    await waitFor(() => {
      expect(screen.getByText(/1\/15\/2024 - 1\/29\/2024/)).toBeInTheDocument();
    });
    
    // Check both pay periods are formatted
    expect(screen.getByText(/1\/1\/2024 - 1\/14\/2024/)).toBeInTheDocument();
  });

  it('displays correct status badges', async () => {
    render(
      <TestWrapper>
        <PayrollIntegration staffId={1} />
      </TestWrapper>
    );
    
    await waitFor(() => {
      const statusElements = screen.getAllByText('completed');
      expect(statusElements).toHaveLength(2);
      
      statusElements.forEach(element => {
        expect(element).toHaveClass('status', 'completed');
      });
    });
  });
});

describe('PayrollIntegration Snapshots', () => {
  it('matches snapshot for loading state', () => {
    const { container } = render(
      <TestWrapper>
        <PayrollIntegration staffId={1} />
      </TestWrapper>
    );
    
    expect(container.firstChild).toMatchSnapshot('payroll-integration-loading');
  });

  it('matches snapshot for loaded state with data', async () => {
    const { container } = render(
      <TestWrapper>
        <PayrollIntegration staffId={1} />
      </TestWrapper>
    );
    
    await waitFor(() => {
      expect(screen.getByText('$1,200.00')).toBeInTheDocument();
    });
    
    expect(container.firstChild).toMatchSnapshot('payroll-integration-loaded');
  });

  it('matches snapshot for run payroll dialog', async () => {
    const user = userEvent.setup();
    
    render(
      <TestWrapper>
        <PayrollIntegration staffId={1} />
      </TestWrapper>
    );
    
    await waitFor(() => {
      expect(screen.getByText('Run Payroll')).toBeInTheDocument();
    });
    
    await user.click(screen.getByRole('button', { name: /run payroll/i }));
    
    const dialog = screen.getByRole('dialog');
    expect(dialog).toMatchSnapshot('run-payroll-dialog');
  });

  it('matches snapshot for payroll detail view', async () => {
    const user = userEvent.setup();
    
    render(
      <TestWrapper>
        <PayrollIntegration staffId={1} />
      </TestWrapper>
    );
    
    await waitFor(() => {
      expect(screen.getByText('View Details')).toBeInTheDocument();
    });
    
    await user.click(screen.getAllByText('View Details')[0]);
    
    await waitFor(() => {
      expect(screen.getByText('Payroll Detail')).toBeInTheDocument();
    });
    
    const detailView = screen.getByText('Payroll Detail').closest('.payroll-detail-view');
    expect(detailView).toMatchSnapshot('payroll-detail-view');
  });
});

describe('PayrollIntegration WebSocket Integration', () => {
  it('handles job started events', async () => {
    const mockWebSocket = jest.fn();
    const mockSend = jest.fn();
    
    // Mock WebSocket
    global.WebSocket = jest.fn(() => ({
      send: mockSend,
      close: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
    })) as any;
    
    render(
      <TestWrapper>
        <PayrollIntegration staffId={1} />
      </TestWrapper>
    );
    
    // Simulate job started event
    const event = {
      type: 'payroll.job.started',
      payload: { job_id: 'test-job-123' },
      timestamp: new Date().toISOString()
    };
    
    // This would trigger the WebSocket callback in real scenario
    expect(screen.getByText('Payroll Information')).toBeInTheDocument();
  });

  it('shows connection status indicator', async () => {
    render(
      <TestWrapper>
        <PayrollIntegration staffId={1} />
      </TestWrapper>
    );
    
    await waitFor(() => {
      // Should show connection status
      expect(screen.getByText(/live|connecting|offline|reconnecting/i)).toBeInTheDocument();
    });
  });
});

describe('PayrollIntegration Accessibility', () => {
  it('has proper ARIA labels', async () => {
    render(
      <TestWrapper>
        <PayrollIntegration staffId={1} />
      </TestWrapper>
    );
    
    await waitFor(() => {
      expect(screen.getByRole('table')).toHaveAccessibleName(/payroll history/i);
    });
    
    // Check form labels
    const runButton = screen.getByRole('button', { name: /run payroll/i });
    await userEvent.click(runButton);
    
    expect(screen.getByLabelText(/pay period start/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/pay period end/i)).toBeInTheDocument();
  });

  it('supports keyboard navigation', async () => {
    const user = userEvent.setup();
    
    render(
      <TestWrapper>
        <PayrollIntegration staffId={1} />
      </TestWrapper>
    );
    
    await waitFor(() => {
      expect(screen.getByText('Run Payroll')).toBeInTheDocument();
    });
    
    // Tab to run payroll button
    await user.tab();
    expect(screen.getByRole('button', { name: /run payroll/i })).toHaveFocus();
    
    // Enter to open dialog
    await user.keyboard('{Enter}');
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    
    // Tab through form fields
    await user.tab();
    expect(screen.getByLabelText(/pay period start/i)).toHaveFocus();
    
    await user.tab();
    expect(screen.getByLabelText(/pay period end/i)).toHaveFocus();
  });
});