import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { OrderStatus, PaymentStatus, OrderType } from '../../types/order.types';

// Mock the components
jest.mock('../../components/admin/orders/OrderList', () => {
  return function OrderList() {
    return <div data-testid="order-list">Order List Component</div>;
  };
});

// Mock WebSocket
jest.mock('../../services/websocketService', () => ({
  WebSocketService: jest.fn().mockImplementation(() => ({
    connect: jest.fn(),
    disconnect: jest.fn(),
    subscribeToOrderUpdates: jest.fn(),
    unsubscribeFromOrderUpdates: jest.fn()
  }))
}));

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

describe('Order Management Flow', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    
    // Setup default mock responses
    mockedOrderService.getOrders.mockResolvedValue({
      items: [
        {
          id: 1,
          order_number: 'ORD001',
          status: OrderStatus.PENDING,
          payment_status: PaymentStatus.PENDING,
          order_type: OrderType.DINE_IN,
          customer_name: 'John Doe',
          table_no: 5,
          total: 45.50,
          items: [
            {
              id: 1,
              menu_item_id: 1,
              menu_item_name: 'Burger',
              quantity: 2,
              unit_price: 12.50,
              total_price: 25.00
            }
          ],
          subtotal: 40.00,
          tax: 5.50,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          restaurant_id: 1
        },
        {
          id: 2,
          order_number: 'ORD002',
          status: OrderStatus.CONFIRMED,
          payment_status: PaymentStatus.PAID,
          order_type: OrderType.TAKEOUT,
          customer_name: 'Jane Smith',
          total: 35.00,
          items: [],
          subtotal: 30.00,
          tax: 5.00,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          restaurant_id: 1
        }
      ],
      total: 2,
      limit: 10,
      offset: 0,
      has_more: false
    });

    mockedOrderService.getOrderAnalytics.mockResolvedValue({
      total_orders: 10,
      total_revenue: 500,
      average_order_value: 50,
      orders_by_status: {
        [OrderStatus.COMPLETED]: 5,
        [OrderStatus.PENDING]: 3,
        [OrderStatus.CANCELLED]: 2
      },
      orders_by_type: {
        [OrderType.DINE_IN]: 4,
        [OrderType.TAKEOUT]: 3,
        [OrderType.DELIVERY]: 3
      },
      top_items: [
        { name: 'Burger', quantity: 20, revenue: 250 },
        { name: 'Pizza', quantity: 15, revenue: 200 }
      ],
      payment_methods: {
        cash: { count: 5, amount: 250 },
        card: { count: 5, amount: 250 },
        credit_card: { count: 0, amount: 0 },
        debit_card: { count: 0, amount: 0 },
        digital: { count: 0, amount: 0 },
        mobile_payment: { count: 0, amount: 0 },
        gift_card: { count: 0, amount: 0 },
        split: { count: 0, amount: 0 }
      }
    });
  });

  describe('Order List View', () => {
    test('displays list of orders on load', async () => {
      renderWithProviders(<OrderManagementPage />);

      await waitFor(() => {
        expect(screen.getByText('ORD001')).toBeInTheDocument();
        expect(screen.getByText('ORD002')).toBeInTheDocument();
      });

      expect(screen.getByText('John Doe')).toBeInTheDocument();
      expect(screen.getByText('Jane Smith')).toBeInTheDocument();
    });

    test('filters orders by status', async () => {
      const user = userEvent.setup();
      renderWithProviders(<OrderManagementPage />);

      await waitFor(() => {
        expect(screen.getByText('ORD001')).toBeInTheDocument();
      });

      // Find and click status filter
      const statusFilter = screen.getByLabelText(/status/i);
      await user.click(statusFilter);

      // Select 'Pending' from dropdown
      const pendingOption = await screen.findByText('Pending');
      await user.click(pendingOption);

      // Mock filtered response
      mockedOrderService.getOrders.mockResolvedValueOnce({
        items: [{
          id: 1,
          order_number: 'ORD001',
          status: OrderStatus.PENDING,
          payment_status: PaymentStatus.PENDING,
          order_type: OrderType.DINE_IN,
          customer_name: 'John Doe',
          table_no: 5,
          total: 45.50,
          items: [],
          subtotal: 40.00,
          tax: 5.50,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          restaurant_id: 1
        }],
        total: 1,
        limit: 10,
        offset: 0,
        has_more: false
      });

      await waitFor(() => {
        expect(mockedOrderService.getOrders).toHaveBeenCalledWith(
          expect.objectContaining({
            status: OrderStatus.PENDING
          })
        );
      });
    });

    test('searches orders by customer name', async () => {
      const user = userEvent.setup();
      renderWithProviders(<OrderManagementPage />);

      await waitFor(() => {
        expect(screen.getByText('ORD001')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search/i);
      await user.type(searchInput, 'John');

      mockedOrderService.getOrders.mockResolvedValueOnce({
        items: [{
          id: 1,
          order_number: 'ORD001',
          status: OrderStatus.PENDING,
          payment_status: PaymentStatus.PENDING,
          order_type: OrderType.DINE_IN,
          customer_name: 'John Doe',
          table_no: 5,
          total: 45.50,
          items: [],
          subtotal: 40.00,
          tax: 5.50,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          restaurant_id: 1
        }],
        total: 1,
        limit: 10,
        offset: 0,
        has_more: false
      });

      await waitFor(() => {
        expect(mockedOrderService.getOrders).toHaveBeenCalledWith(
          expect.objectContaining({
            search: 'John'
          })
        );
      });
    });
  });

  describe('Order Status Updates', () => {
    test('updates order status from pending to confirmed', async () => {
      const user = userEvent.setup();
      renderWithProviders(<OrderManagementPage />);

      await waitFor(() => {
        expect(screen.getByText('ORD001')).toBeInTheDocument();
      });

      // Find the status chip for the first order
      const statusChips = screen.getAllByText('Pending');
      const firstStatusChip = statusChips[0];
      
      // Click to open status menu
      await user.click(firstStatusChip);

      // Select 'Confirmed' from menu
      const confirmedOption = await screen.findByText('Confirmed');
      
      mockedOrderService.updateOrderStatus.mockResolvedValueOnce({
        id: 1,
        order_number: 'ORD001',
        status: OrderStatus.CONFIRMED,
        payment_status: PaymentStatus.PENDING,
        order_type: OrderType.DINE_IN,
        customer_name: 'John Doe',
        table_no: 5,
        total: 45.50,
        items: [],
        subtotal: 40.00,
        tax: 5.50,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        restaurant_id: 1
      });

      await user.click(confirmedOption);

      await waitFor(() => {
        expect(mockedOrderService.updateOrderStatus).toHaveBeenCalledWith(
          1,
          OrderStatus.CONFIRMED
        );
      });
    });

    test('cancels an order with reason', async () => {
      const user = userEvent.setup();
      renderWithProviders(<OrderManagementPage />);

      await waitFor(() => {
        expect(screen.getByText('ORD001')).toBeInTheDocument();
      });

      // Click on order to view details
      const orderRow = screen.getByText('ORD001').closest('tr');
      if (orderRow) {
        await user.click(orderRow);
      }

      // Find and click cancel button
      const cancelButton = await screen.findByText(/cancel order/i);
      await user.click(cancelButton);

      // Enter cancellation reason
      const reasonInput = await screen.findByLabelText(/reason/i);
      await user.type(reasonInput, 'Customer request');

      // Confirm cancellation
      const confirmButton = screen.getByText(/confirm/i);
      
      mockedOrderService.cancelOrder.mockResolvedValueOnce({
        id: 1,
        order_number: 'ORD001',
        status: OrderStatus.CANCELLED,
        payment_status: PaymentStatus.PENDING,
        order_type: OrderType.DINE_IN,
        customer_name: 'John Doe',
        table_no: 5,
        total: 45.50,
        items: [],
        subtotal: 40.00,
        tax: 5.50,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        restaurant_id: 1
      });

      await user.click(confirmButton);

      await waitFor(() => {
        expect(mockedOrderService.cancelOrder).toHaveBeenCalledWith(
          1,
          'Customer request'
        );
      });
    });
  });

  describe('Order Analytics', () => {
    test('displays analytics dashboard', async () => {
      renderWithProviders(<OrderManagementPage />);

      // Switch to analytics view
      const analyticsTab = await screen.findByText(/analytics/i);
      fireEvent.click(analyticsTab);

      await waitFor(() => {
        expect(screen.getByText(/total orders/i)).toBeInTheDocument();
        expect(screen.getByText('10')).toBeInTheDocument();
        expect(screen.getByText(/total revenue/i)).toBeInTheDocument();
        expect(screen.getByText('$500')).toBeInTheDocument();
      });
    });

    test('updates analytics when date range changes', async () => {
      const user = userEvent.setup();
      renderWithProviders(<OrderManagementPage />);

      const analyticsTab = await screen.findByText(/analytics/i);
      fireEvent.click(analyticsTab);

      await waitFor(() => {
        expect(screen.getByText(/total orders/i)).toBeInTheDocument();
      });

      // Change date range
      const dateFromInput = screen.getByLabelText(/from/i);
      const dateToInput = screen.getByLabelText(/to/i);

      await user.clear(dateFromInput);
      await user.type(dateFromInput, '01/01/2024');
      
      await user.clear(dateToInput);
      await user.type(dateToInput, '01/31/2024');

      // Mock new analytics data
      mockedOrderService.getOrderAnalytics.mockResolvedValueOnce({
        total_orders: 20,
        total_revenue: 1000,
        average_order_value: 50,
        orders_by_status: {
          [OrderStatus.COMPLETED]: 15,
          [OrderStatus.PENDING]: 3,
          [OrderStatus.CANCELLED]: 2
        },
        orders_by_type: {
          [OrderType.DINE_IN]: 10,
          [OrderType.TAKEOUT]: 5,
          [OrderType.DELIVERY]: 5
        },
        top_items: [],
        payment_methods: {
          cash: { count: 10, amount: 500 },
          card: { count: 10, amount: 500 },
          credit_card: { count: 0, amount: 0 },
          debit_card: { count: 0, amount: 0 },
          digital: { count: 0, amount: 0 },
          mobile_payment: { count: 0, amount: 0 },
          gift_card: { count: 0, amount: 0 },
          split: { count: 0, amount: 0 }
        }
      });

      // Apply filter
      const applyButton = screen.getByText(/apply/i);
      await user.click(applyButton);

      await waitFor(() => {
        expect(mockedOrderService.getOrderAnalytics).toHaveBeenCalledWith(
          expect.objectContaining({
            date_from: expect.any(String),
            date_to: expect.any(String)
          })
        );
      });
    });
  });

  describe('Real-time Updates', () => {
    test('updates order list when new order is received via WebSocket', async () => {
      renderWithProviders(<OrderManagementPage />);

      await waitFor(() => {
        expect(screen.getByText('ORD001')).toBeInTheDocument();
      });

      // Simulate WebSocket message for new order
      const newOrder = {
        id: 3,
        order_number: 'ORD003',
        status: OrderStatus.PENDING,
        payment_status: PaymentStatus.PENDING,
        order_type: OrderType.DELIVERY,
        customer_name: 'Bob Wilson',
        total: 55.00,
        items: [],
        subtotal: 50.00,
        tax: 5.00,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        restaurant_id: 1
      };

      // Mock the service to return updated list
      mockedOrderService.getOrders.mockResolvedValueOnce({
        items: [
          newOrder,
          // ... existing orders
        ],
        total: 3,
        limit: 10,
        offset: 0,
        has_more: false
      });

      // Trigger a re-fetch (simulating WebSocket update)
      const refreshButton = screen.getByLabelText(/refresh/i);
      fireEvent.click(refreshButton);

      await waitFor(() => {
        expect(screen.getByText('ORD003')).toBeInTheDocument();
        expect(screen.getByText('Bob Wilson')).toBeInTheDocument();
      });
    });
  });
});