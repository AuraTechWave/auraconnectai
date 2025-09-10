import api from './api';
import { 
  OrderStatus, 
  PaymentStatus, 
  OrderType,
  OrderListParams,
  OrderCreateRequest,
  OrderUpdateRequest
} from '../types/order.types';

// Mock the API module
jest.mock('./api');
const mockedApi = api as jest.Mocked<typeof api>;

// Import orderService after mocking
const { orderService } = require('./orderService');

describe('OrderService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('getOrders', () => {
    test('fetches orders without filters', async () => {
      const mockOrders = [
        { id: 1, order_number: 'ORD001', status: OrderStatus.PENDING },
        { id: 2, order_number: 'ORD002', status: OrderStatus.CONFIRMED }
      ];
      
      mockedApi.get.mockResolvedValueOnce({ data: mockOrders });
      
      const result = await orderService.getOrders();
      
      expect(mockedApi.get).toHaveBeenCalledWith('/api/orders');
      expect(result.items).toEqual(mockOrders);
      expect(result.total).toBe(2);
    });

    test('fetches orders with filters', async () => {
      const params: OrderListParams = {
        status: OrderStatus.PENDING,
        payment_status: PaymentStatus.PAID,
        limit: 10,
        offset: 0
      };
      
      mockedApi.get.mockResolvedValueOnce({ data: [] });
      
      await orderService.getOrders(params);
      
      expect(mockedApi.get).toHaveBeenCalledWith(
        '/api/orders?status=pending&payment_status=paid&limit=10&offset=0'
      );
    });

    test('handles array status filters', async () => {
      const params: OrderListParams = {
        status: [OrderStatus.PENDING, OrderStatus.CONFIRMED],
        order_type: [OrderType.DINE_IN, OrderType.TAKEOUT]
      };
      
      mockedApi.get.mockResolvedValueOnce({ data: [] });
      
      await orderService.getOrders(params);
      
      expect(mockedApi.get).toHaveBeenCalledWith(
        '/api/orders?status=pending%2Cconfirmed&order_type=dine_in%2Ctakeout'
      );
    });

    test('converts date filters to ISO strings', async () => {
      const params: OrderListParams = {
        date_from: '2024-01-01',
        date_to: '2024-01-31'
      };
      
      mockedApi.get.mockResolvedValueOnce({ data: [] });
      
      await orderService.getOrders(params);
      
      const call = mockedApi.get.mock.calls[0][0];
      expect(call).toContain('date_from=');
      expect(call).toContain('date_to=');
      expect(call).toContain('2024-01-01T');
      expect(call).toContain('2024-01-31T');
    });

    test('handles API errors', async () => {
      mockedApi.get.mockRejectedValueOnce(new Error('Network error'));
      
      await expect(orderService.getOrders()).rejects.toThrow();
    });
  });

  describe('getOrder', () => {
    test('fetches single order by ID', async () => {
      const mockOrder = { 
        id: 1, 
        order_number: 'ORD001', 
        status: OrderStatus.PENDING 
      };
      
      mockedApi.get.mockResolvedValueOnce({ data: mockOrder });
      
      const result = await orderService.getOrder(1);
      
      expect(mockedApi.get).toHaveBeenCalledWith('/api/orders/1');
      expect(result).toEqual(mockOrder);
    });

    test('fetches order by string ID', async () => {
      mockedApi.get.mockResolvedValueOnce({ data: {} });
      
      await orderService.getOrder('order-123');
      
      expect(mockedApi.get).toHaveBeenCalledWith('/api/orders/order-123');
    });
  });

  describe('createOrder', () => {
    test('creates new order', async () => {
      const orderData: OrderCreateRequest = {
        order_type: OrderType.DINE_IN,
        items: [
          {
            menu_item_id: 1,
            quantity: 2
          }
        ],
        table_no: 5
      };
      
      const mockCreatedOrder = {
        id: 1,
        ...orderData,
        status: OrderStatus.PENDING
      };
      
      mockedApi.post.mockResolvedValueOnce({ data: mockCreatedOrder });
      
      const result = await orderService.createOrder(orderData);
      
      expect(mockedApi.post).toHaveBeenCalledWith('/api/orders', orderData);
      expect(result).toEqual(mockCreatedOrder);
    });
  });

  describe('updateOrder', () => {
    test('updates order', async () => {
      const updateData: OrderUpdateRequest = {
        status: OrderStatus.CONFIRMED,
        notes: 'Updated notes'
      };
      
      const mockUpdatedOrder = {
        id: 1,
        order_number: 'ORD001',
        ...updateData
      };
      
      mockedApi.put.mockResolvedValueOnce({ data: mockUpdatedOrder });
      
      const result = await orderService.updateOrder(1, updateData);
      
      expect(mockedApi.put).toHaveBeenCalledWith('/api/orders/1', updateData);
      expect(result).toEqual(mockUpdatedOrder);
    });
  });

  describe('updateOrderStatus', () => {
    test('updates order status', async () => {
      const mockUpdatedOrder = {
        id: 1,
        order_number: 'ORD001',
        status: OrderStatus.CONFIRMED
      };
      
      mockedApi.patch.mockResolvedValueOnce({ data: mockUpdatedOrder });
      
      const result = await orderService.updateOrderStatus(1, OrderStatus.CONFIRMED);
      
      expect(mockedApi.patch).toHaveBeenCalledWith('/api/orders/1/status', {
        status: OrderStatus.CONFIRMED
      });
      expect(result).toEqual(mockUpdatedOrder);
    });
  });

  describe('cancelOrder', () => {
    test('cancels order', async () => {
      const mockCancelledOrder = {
        id: 1,
        order_number: 'ORD001',
        status: OrderStatus.CANCELLED
      };
      
      mockedApi.post.mockResolvedValueOnce({ data: mockCancelledOrder });
      
      const result = await orderService.cancelOrder(1, 'Customer request');
      
      expect(mockedApi.post).toHaveBeenCalledWith('/api/orders/1/cancel', {
        reason: 'Customer request'
      });
      expect(result).toEqual(mockCancelledOrder);
    });
  });

  describe('refundOrder', () => {
    test('processes full refund', async () => {
      const refundRequest = {
        amount: 50.00,
        reason: 'Quality issue'
      };
      
      const mockRefundResponse = {
        refund_id: 'REF001',
        status: 'completed' as const,
        amount: 50.00
      };
      
      mockedApi.post.mockResolvedValueOnce({ data: mockRefundResponse });
      
      const result = await orderService.refundOrder(1, refundRequest);
      
      expect(mockedApi.post).toHaveBeenCalledWith(
        '/api/orders/1/refund', 
        refundRequest
      );
      expect(result).toEqual(mockRefundResponse);
    });

    test('processes partial refund with items', async () => {
      const refundRequest = {
        amount: 25.00,
        reason: 'Wrong item',
        items: [
          { order_item_id: 1, quantity: 1 }
        ]
      };
      
      mockedApi.post.mockResolvedValueOnce({ 
        data: { 
          refund_id: 'REF002', 
          status: 'completed' as const, 
          amount: 25.00 
        } 
      });
      
      await orderService.refundOrder(1, refundRequest);
      
      expect(mockedApi.post).toHaveBeenCalledWith(
        '/api/orders/1/refund', 
        refundRequest
      );
    });
  });

  describe('getOrderAnalytics', () => {
    test('fetches order analytics', async () => {
      const mockAnalytics = {
        total_orders: 100,
        total_revenue: 5000,
        average_order_value: 50,
        orders_by_status: {
          [OrderStatus.COMPLETED]: 80,
          [OrderStatus.CANCELLED]: 5
        }
      };
      
      mockedApi.get.mockResolvedValueOnce({ data: mockAnalytics });
      
      const result = await orderService.getOrderAnalytics({
        date_from: '2024-01-01',
        date_to: '2024-01-31'
      });
      
      expect(mockedApi.get).toHaveBeenCalled();
      expect(result).toEqual(mockAnalytics);
    });
  });

  describe('bulkUpdateOrders', () => {
    test('updates multiple orders', async () => {
      const orderIds = [1, 2, 3];
      const updateData = { status: OrderStatus.COMPLETED };
      
      mockedApi.post.mockResolvedValueOnce({ 
        data: { updated: 3, failed: 0 } 
      });
      
      const result = await orderService.bulkUpdateOrders(orderIds, updateData);
      
      expect(mockedApi.post).toHaveBeenCalledWith('/api/orders/bulk-update', {
        order_ids: orderIds,
        updates: updateData
      });
      expect(result).toEqual({ updated: 3, failed: 0 });
    });
  });
});