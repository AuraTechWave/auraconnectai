import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import OrderList from './OrderList';
import { orderService } from '../../../services/orderService';
import websocketService from '../../../services/websocketService';
import { OrderStatus, PaymentStatus, OrderType } from '../../../types/order.types';

// Mock services
jest.mock('../../../services/orderService');
jest.mock('../../../services/websocketService');

// Mock child components
jest.mock('./OrderFilters', () => {
  return function OrderFilters({ onFilterChange, onClose }: any) {
    return (
      <div data-testid="order-filters">
        <button onClick={() => onFilterChange({ status: OrderStatus.PENDING })}>
          Apply Pending Filter
        </button>
        <button onClick={onClose}>Close Filters</button>
      </div>
    );
  };
});

jest.mock('./OrderDetails', () => {
  return function OrderDetails({ order, open, onClose, onOrderUpdate }: any) {
    return open ? (
      <div data-testid="order-details">
        <div>Order Details: {order?.order_number}</div>
        <button onClick={() => onOrderUpdate(order)}>Update Order</button>
        <button onClick={onClose}>Close Details</button>
      </div>
    ) : null;
  };
});

jest.mock('./OrderStatusChip', () => {
  return function OrderStatusChip({ status, onChange }: any) {
    return (
      <button 
        data-testid={`status-chip-${status}`}
        onClick={() => onChange && onChange(OrderStatus.CONFIRMED)}
      >
        {status}
      </button>
    );
  };
});

jest.mock('./PaymentStatusChip', () => {
  return function PaymentStatusChip({ status }: any) {
    return <span data-testid={`payment-chip-${status}`}>{status}</span>;
  };
});

const mockOrderService = orderService as jest.Mocked<typeof orderService>;
const mockWebsocketService = websocketService as jest.Mocked<typeof websocketService>;

const theme = createTheme();

const renderWithTheme = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={theme}>
      {component}
    </ThemeProvider>
  );
};

describe('OrderList', () => {
  const mockOrders = [
    {
      id: 1,
      order_number: 'ORD001',
      status: OrderStatus.PENDING,
      payment_status: PaymentStatus.PENDING,
      order_type: OrderType.DINE_IN,
      customer_name: 'John Doe',
      customer_phone: '+1234567890',
      table_no: 5,
      total: 45.50,
      items: [],
      subtotal: 40.00,
      tax: 5.50,
      created_at: '2024-01-15T10:30:00Z',
      updated_at: '2024-01-15T10:30:00Z',
      restaurant_id: 1
    },
    {
      id: 2,
      order_number: 'ORD002',
      status: OrderStatus.CONFIRMED,
      payment_status: PaymentStatus.PAID,
      order_type: OrderType.TAKEOUT,
      customer_name: 'Jane Smith',
      customer_phone: '+0987654321',
      total: 35.00,
      items: [],
      subtotal: 30.00,
      tax: 5.00,
      created_at: '2024-01-15T11:15:00Z',
      updated_at: '2024-01-15T11:20:00Z',
      restaurant_id: 1
    }
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Default mock implementations
    mockOrderService.getOrders.mockResolvedValue({
      items: mockOrders,
      total: mockOrders.length,
      limit: 25,
      offset: 0,
      has_more: false
    });

    mockWebsocketService.connect.mockImplementation(() => {});
    mockWebsocketService.subscribeToOrders.mockImplementation(() => {});
    mockWebsocketService.subscribeToOrderUpdates.mockImplementation(() => {});
    mockWebsocketService.subscribeToConnectionStatus.mockImplementation(() => {});
    mockWebsocketService.disconnect.mockImplementation(() => {});

    // Mock localStorage
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: jest.fn().mockReturnValue('1'),
        setItem: jest.fn(),
        removeItem: jest.fn()
      },
      writable: true
    });
  });

  describe('Initial Rendering and Data Loading', () => {
    test('renders order list with loading state initially', () => {
      renderWithTheme(<OrderList />);
      
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    test('displays orders after successful load', async () => {
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getByText('ORD001')).toBeInTheDocument();
        expect(screen.getByText('ORD002')).toBeInTheDocument();
        expect(screen.getByText('John Doe')).toBeInTheDocument();
        expect(screen.getByText('Jane Smith')).toBeInTheDocument();
      });
    });

    test('displays error message on load failure', async () => {
      mockOrderService.getOrders.mockRejectedValue(new Error('API Error'));
      
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getByText(/failed to fetch orders/i)).toBeInTheDocument();
      });
    });

    test('calls orderService.getOrders on mount', async () => {
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(mockOrderService.getOrders).toHaveBeenCalledWith({
          search: ''
        });
      });
    });
  });

  describe('WebSocket Integration', () => {
    test('establishes WebSocket connection on mount', () => {
      renderWithTheme(<OrderList />);
      
      expect(mockWebsocketService.connect).toHaveBeenCalledWith('1');
      expect(mockWebsocketService.subscribeToOrders).toHaveBeenCalledWith('1');
    });

    test('sets up WebSocket event listeners', () => {
      renderWithTheme(<OrderList />);
      
      expect(mockWebsocketService.subscribeToOrderUpdates).toHaveBeenCalled();
      expect(mockWebsocketService.subscribeToConnectionStatus).toHaveBeenCalled();
    });

    test('disconnects WebSocket on unmount', () => {
      const { unmount } = renderWithTheme(<OrderList />);
      
      unmount();
      
      expect(mockWebsocketService.disconnect).toHaveBeenCalled();
    });

    test('handles new order from WebSocket', async () => {
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getByText('ORD001')).toBeInTheDocument();
      });
      
      // Simulate WebSocket subscription callback
      const subscribeCall = mockWebsocketService.subscribeToOrderUpdates.mock.calls[0];
      const newOrderCallback = subscribeCall?.[0];
      
      if (newOrderCallback) {
        const newOrder = {
          ...mockOrders[0],
          id: 3,
          order_number: 'ORD003',
          customer_name: 'New Customer'
        };
        
        // Simulate new order event
        newOrderCallback(newOrder);
        
        await waitFor(() => {
          expect(screen.getByText('ORD003')).toBeInTheDocument();
          expect(screen.getByText('New Customer')).toBeInTheDocument();
        });
      }
    });
  });

  describe('Search Functionality', () => {
    test('renders search input', async () => {
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/search orders/i)).toBeInTheDocument();
      });
    });

    test('updates search query on input', async () => {
      const user = userEvent.setup();
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/search orders/i)).toBeInTheDocument();
      });
      
      const searchInput = screen.getByPlaceholderText(/search orders/i);
      await user.type(searchInput, 'ORD001');
      
      expect(searchInput).toHaveValue('ORD001');
    });

    test('triggers search on input with debounce', async () => {
      const user = userEvent.setup();
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/search orders/i)).toBeInTheDocument();
      });
      
      const searchInput = screen.getByPlaceholderText(/search orders/i);
      await user.type(searchInput, 'John');
      
      // Wait for debounced search
      await waitFor(() => {
        expect(mockOrderService.getOrders).toHaveBeenCalledWith({
          search: 'John'
        });
      }, { timeout: 3000 });
    });
  });

  describe('Filtering', () => {
    test('shows filter button', async () => {
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getByLabelText(/filter/i)).toBeInTheDocument();
      });
    });

    test('opens and closes filter dialog', async () => {
      const user = userEvent.setup();
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getByLabelText(/filter/i)).toBeInTheDocument();
      });
      
      // Open filters
      const filterButton = screen.getByLabelText(/filter/i);
      await user.click(filterButton);
      
      expect(screen.getByTestId('order-filters')).toBeInTheDocument();
      
      // Close filters
      const closeButton = screen.getByText('Close Filters');
      await user.click(closeButton);
      
      expect(screen.queryByTestId('order-filters')).not.toBeInTheDocument();
    });

    test('applies filters and refetches orders', async () => {
      const user = userEvent.setup();
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getByLabelText(/filter/i)).toBeInTheDocument();
      });
      
      // Open filters
      const filterButton = screen.getByLabelText(/filter/i);
      await user.click(filterButton);
      
      // Apply filter
      const applyFilterButton = screen.getByText('Apply Pending Filter');
      await user.click(applyFilterButton);
      
      await waitFor(() => {
        expect(mockOrderService.getOrders).toHaveBeenCalledWith({
          status: OrderStatus.PENDING,
          search: ''
        });
      });
    });
  });

  describe('Order Table Display', () => {
    test('displays order table headers', async () => {
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getByText('Order #')).toBeInTheDocument();
        expect(screen.getByText('Customer')).toBeInTheDocument();
        expect(screen.getByText('Status')).toBeInTheDocument();
        expect(screen.getByText('Payment')).toBeInTheDocument();
        expect(screen.getByText('Total')).toBeInTheDocument();
        expect(screen.getByText('Created')).toBeInTheDocument();
      });
    });

    test('displays order data in table rows', async () => {
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getByText('ORD001')).toBeInTheDocument();
        expect(screen.getByText('John Doe')).toBeInTheDocument();
        expect(screen.getByText('$45.50')).toBeInTheDocument();
      });
    });

    test('displays order status chips', async () => {
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getByTestId(`status-chip-${OrderStatus.PENDING}`)).toBeInTheDocument();
        expect(screen.getByTestId(`status-chip-${OrderStatus.CONFIRMED}`)).toBeInTheDocument();
      });
    });

    test('displays payment status chips', async () => {
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getByTestId(`payment-chip-${PaymentStatus.PENDING}`)).toBeInTheDocument();
        expect(screen.getByTestId(`payment-chip-${PaymentStatus.PAID}`)).toBeInTheDocument();
      });
    });

    test('formats order creation date correctly', async () => {
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getByText('Jan 15, 2024 10:30')).toBeInTheDocument();
      });
    });
  });

  describe('Pagination', () => {
    test('displays pagination controls', async () => {
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getByText(/rows per page/i)).toBeInTheDocument();
        expect(screen.getByText(/1-2 of 2/)).toBeInTheDocument();
      });
    });

    test('changes rows per page', async () => {
      const user = userEvent.setup();
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getByDisplayValue('25')).toBeInTheDocument();
      });
      
      const rowsPerPageSelect = screen.getByDisplayValue('25');
      await user.click(rowsPerPageSelect);
      
      const option50 = screen.getByText('50');
      await user.click(option50);
      
      await waitFor(() => {
        expect(mockOrderService.getOrders).toHaveBeenCalledWith({
          limit: 50,
          offset: 0,
          search: ''
        });
      });
    });

    test('navigates to next page', async () => {
      const user = userEvent.setup();
      
      // Mock orders with pagination
      mockOrderService.getOrders.mockResolvedValue({
        items: mockOrders,
        total: 100,
        limit: 25,
        offset: 0,
        has_more: true
      });
      
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getByLabelText(/go to next page/i)).toBeInTheDocument();
      });
      
      const nextButton = screen.getByLabelText(/go to next page/i);
      await user.click(nextButton);
      
      await waitFor(() => {
        expect(mockOrderService.getOrders).toHaveBeenCalledWith({
          limit: 25,
          offset: 25,
          search: ''
        });
      });
    });
  });

  describe('Order Actions', () => {
    test('opens order details when order clicked', async () => {
      const user = userEvent.setup();
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getByText('ORD001')).toBeInTheDocument();
      });
      
      const orderRow = screen.getByText('ORD001').closest('tr');
      if (orderRow) {
        await user.click(orderRow);
        
        expect(screen.getByTestId('order-details')).toBeInTheDocument();
        expect(screen.getByText('Order Details: ORD001')).toBeInTheDocument();
      }
    });

    test('opens action menu for order', async () => {
      const user = userEvent.setup();
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getAllByLabelText(/more actions/i)[0]).toBeInTheDocument();
      });
      
      const moreButton = screen.getAllByLabelText(/more actions/i)[0];
      await user.click(moreButton);
      
      expect(screen.getByText('View Details')).toBeInTheDocument();
      expect(screen.getByText('Edit Order')).toBeInTheDocument();
      expect(screen.getByText('Cancel Order')).toBeInTheDocument();
    });

    test('updates order status through status chip', async () => {
      const user = userEvent.setup();
      mockOrderService.updateOrderStatus.mockResolvedValue({
        ...mockOrders[0],
        status: OrderStatus.CONFIRMED
      });
      
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getByTestId(`status-chip-${OrderStatus.PENDING}`)).toBeInTheDocument();
      });
      
      const statusChip = screen.getByTestId(`status-chip-${OrderStatus.PENDING}`);
      await user.click(statusChip);
      
      expect(mockOrderService.updateOrderStatus).toHaveBeenCalledWith(1, OrderStatus.CONFIRMED);
    });
  });

  describe('Refresh Functionality', () => {
    test('shows refresh button', async () => {
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getByLabelText(/refresh/i)).toBeInTheDocument();
      });
    });

    test('refreshes orders when refresh button clicked', async () => {
      const user = userEvent.setup();
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getByLabelText(/refresh/i)).toBeInTheDocument();
      });
      
      const refreshButton = screen.getByLabelText(/refresh/i);
      await user.click(refreshButton);
      
      expect(mockOrderService.getOrders).toHaveBeenCalledTimes(2);
    });
  });

  describe('Error Handling', () => {
    test('displays retry button on error', async () => {
      mockOrderService.getOrders.mockRejectedValue(new Error('Network error'));
      
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getByText('Retry')).toBeInTheDocument();
      });
    });

    test('retries loading orders when retry clicked', async () => {
      const user = userEvent.setup();
      mockOrderService.getOrders
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({
          items: mockOrders,
          total: 2,
          limit: 25,
          offset: 0,
          has_more: false
        });
      
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getByText('Retry')).toBeInTheDocument();
      });
      
      const retryButton = screen.getByText('Retry');
      await user.click(retryButton);
      
      await waitFor(() => {
        expect(screen.getByText('ORD001')).toBeInTheDocument();
      });
    });
  });

  describe('Empty State', () => {
    test('displays empty state when no orders', async () => {
      mockOrderService.getOrders.mockResolvedValue({
        items: [],
        total: 0,
        limit: 25,
        offset: 0,
        has_more: false
      });
      
      renderWithTheme(<OrderList />);
      
      await waitFor(() => {
        expect(screen.getByText(/no orders found/i)).toBeInTheDocument();
      });
    });

    test('displays different message for filtered results', async () => {
      mockOrderService.getOrders.mockResolvedValue({
        items: [],
        total: 0,
        limit: 25,
        offset: 0,
        has_more: false
      });
      
      renderWithTheme(<OrderList />);
      
      // Apply a filter first
      await waitFor(() => {
        expect(screen.getByLabelText(/filter/i)).toBeInTheDocument();
      });
      
      const user = userEvent.setup();
      const filterButton = screen.getByLabelText(/filter/i);
      await user.click(filterButton);
      
      const applyFilterButton = screen.getByText('Apply Pending Filter');
      await user.click(applyFilterButton);
      
      await waitFor(() => {
        expect(screen.getByText(/no orders match your search criteria/i)).toBeInTheDocument();
      });
    });
  });
});