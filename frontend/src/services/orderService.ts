import api from './api';
import { Order, OrderFilter, OrderAnalytics } from '@/types/order.types';

export const orderService = {
  // Get all orders with filters
  async getOrders(filters?: OrderFilter): Promise<Order[]> {
    const params = new URLSearchParams();
    
    if (filters) {
      if (filters.status?.length) {
        params.append('status', filters.status.join(','));
      }
      if (filters.payment_status?.length) {
        params.append('payment_status', filters.payment_status.join(','));
      }
      if (filters.order_type?.length) {
        params.append('order_type', filters.order_type.join(','));
      }
      if (filters.date_from) {
        params.append('date_from', filters.date_from);
      }
      if (filters.date_to) {
        params.append('date_to', filters.date_to);
      }
      if (filters.search) {
        params.append('search', filters.search);
      }
      if (filters.restaurant_id) {
        params.append('restaurant_id', filters.restaurant_id);
      }
      if (filters.location_id) {
        params.append('location_id', filters.location_id);
      }
    }
    
    const response = await api.get<Order[]>(`/api/orders?${params.toString()}`);
    return response.data;
  },

  // Get single order by ID
  async getOrder(orderId: string): Promise<Order> {
    const response = await api.get<Order>(`/api/orders/${orderId}`);
    return response.data;
  },

  // Update order status
  async updateOrderStatus(orderId: string, status: string): Promise<Order> {
    const response = await api.patch<Order>(`/api/orders/${orderId}/status`, {
      status
    });
    return response.data;
  },

  // Update order details
  async updateOrder(orderId: string, updates: Partial<Order>): Promise<Order> {
    const response = await api.put<Order>(`/api/orders/${orderId}`, updates);
    return response.data;
  },

  // Cancel order
  async cancelOrder(orderId: string, reason?: string): Promise<Order> {
    const response = await api.post<Order>(`/api/orders/${orderId}/cancel`, {
      reason
    });
    return response.data;
  },

  // Refund order
  async refundOrder(orderId: string, amount: number, reason?: string): Promise<Order> {
    const response = await api.post<Order>(`/api/orders/${orderId}/refund`, {
      amount,
      reason
    });
    return response.data;
  },

  // Get order analytics
  async getAnalytics(filters?: OrderFilter): Promise<OrderAnalytics> {
    const params = new URLSearchParams();
    
    if (filters) {
      if (filters.date_from) {
        params.append('date_from', filters.date_from);
      }
      if (filters.date_to) {
        params.append('date_to', filters.date_to);
      }
      if (filters.restaurant_id) {
        params.append('restaurant_id', filters.restaurant_id);
      }
      if (filters.location_id) {
        params.append('location_id', filters.location_id);
      }
    }
    
    const response = await api.get<OrderAnalytics>(`/api/orders/analytics?${params.toString()}`);
    return response.data;
  },

  // Export orders to CSV
  async exportOrders(filters?: OrderFilter): Promise<Blob> {
    const params = new URLSearchParams();
    
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value) {
          if (Array.isArray(value)) {
            params.append(key, value.join(','));
          } else {
            params.append(key, value.toString());
          }
        }
      });
    }
    
    const response = await api.get(`/api/orders/export?${params.toString()}`, {
      responseType: 'blob'
    });
    return response.data;
  },

  // Search orders
  async searchOrders(query: string): Promise<Order[]> {
    const response = await api.get<Order[]>(`/api/orders/search?q=${encodeURIComponent(query)}`);
    return response.data;
  }
};