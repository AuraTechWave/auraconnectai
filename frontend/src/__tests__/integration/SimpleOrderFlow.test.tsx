import React from 'react';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import OrderManagementPage from '../../pages/admin/OrderManagementPage';

// Mock the OrderList component
jest.mock('../../components/admin/orders/OrderList', () => {
  return function OrderList() {
    return <div data-testid="order-list">Order List Component</div>;
  };
});

const theme = createTheme();

const renderWithProviders = (component: React.ReactElement) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <BrowserRouter>
          {component}
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
};

describe('Order Management Page Integration', () => {
  test('renders order management page with title', () => {
    renderWithProviders(<OrderManagementPage />);
    
    expect(screen.getByText('Order Management')).toBeInTheDocument();
    expect(screen.getByText(/Manage restaurant orders/i)).toBeInTheDocument();
  });

  test('renders order list component', () => {
    renderWithProviders(<OrderManagementPage />);
    
    expect(screen.getByTestId('order-list')).toBeInTheDocument();
    expect(screen.getByText('Order List Component')).toBeInTheDocument();
  });
});