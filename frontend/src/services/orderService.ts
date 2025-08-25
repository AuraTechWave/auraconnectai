// Order service aligned with backend API

import api, { buildQueryString, handleApiError } from './api';
import { 
  Order, 
  OrderListParams, 
  OrderCreateRequest,
  OrderUpdateRequest,
  RefundRequest,
  RefundResponse,
  OrderAnalytics,
  PaginatedResponse,
  OrderFilter
} from '../types/order.types';

class OrderService {
  private baseUrl = '/api/orders';
  
  // Get list of orders with filters
  async getOrders(params?: OrderListParams): Promise<PaginatedResponse<Order>> {
    try {
      // Convert array params to comma-separated strings if needed
      const queryParams: Record<string, any> = { ...params };
      
      if (params?.status && Array.isArray(params.status)) {
        queryParams.status = params.status.join(',');
      }
      
      if (params?.payment_status && Array.isArray(params.payment_status)) {
        queryParams.payment_status = params.payment_status.join(',');
      }
      
      if (params?.order_type && Array.isArray(params.order_type)) {
        queryParams.order_type = params.order_type.join(',');
      }
      
      // Convert date objects to ISO strings
      if (params?.date_from) {
        queryParams.date_from = new Date(params.date_from).toISOString();
      }
      if (params?.date_to) {
        queryParams.date_to = new Date(params.date_to).toISOString();
      }
      
      const queryString = buildQueryString(queryParams);
      const response = await api.get(`${this.baseUrl}${queryString ? `?${queryString}` : ''}`);
      
      // Backend returns array, wrap in paginated response
      const items = response.data;
      return {
        items,
        total: items.length, // Backend should return total count
        limit: params?.limit || 100,
        offset: params?.offset || 0,
        has_more: items.length === (params?.limit || 100)
      };
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }
  
  // Get single order by ID
  async getOrder(id: string | number): Promise<Order> {
    try {
      const response = await api.get(`${this.baseUrl}/${id}`);
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }
  
  // Create new order
  async createOrder(data: OrderCreateRequest): Promise<Order> {
    try {
      const response = await api.post(this.baseUrl, data);
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }
  
  // Update order
  async updateOrder(id: string | number, data: OrderUpdateRequest | Partial<Order>): Promise<Order> {
    try {
      const response = await api.put(`${this.baseUrl}/${id}`, data);
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }
  
  // Update order status
  async updateOrderStatus(orderId: string | number, status: string): Promise<Order> {
    try {
      const response = await api.patch(`${this.baseUrl}/${orderId}/status`, {
        status
      });
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }
  
  // Cancel order
  async cancelOrder(orderId: string | number, reason?: string): Promise<Order> {
    try {
      const response = await api.post(`${this.baseUrl}/${orderId}/cancel`, {
        reason
      });
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }
  
  // Get kitchen orders (specific endpoint)
  async getKitchenOrders(): Promise<Order[]> {
    try {
      const response = await api.get(`${this.baseUrl}/kitchen`);
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }
  
  // Refund order (payment reconciliation endpoint)
  async refundOrder(orderId: string | number, amount: number, reason?: string): Promise<Order | RefundResponse> {
    try {
      // Check for refund endpoint or payment reconciliation
      const response = await api.post(`${this.baseUrl}/${orderId}/refund`, {
        amount,
        reason
      });
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }
  
  // Get order analytics
  async getAnalytics(filters?: OrderFilter): Promise<OrderAnalytics> {
    try {
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
      
      const response = await api.get<OrderAnalytics>(`${this.baseUrl}/analytics?${params.toString()}`);
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }
  
  // Search orders
  async searchOrders(query: string): Promise<Order[]> {
    try {
      const response = await api.get<Order[]>(`${this.baseUrl}/search?q=${encodeURIComponent(query)}`);
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }
  
  // Export orders
  async exportOrders(filters?: OrderFilter): Promise<Blob> {
    try {
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
      
      const response = await api.get(
        `${this.baseUrl}/export?${params.toString()}`,
        {
          responseType: 'blob',
        }
      );
      
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }
  
  // Additional endpoints from backend
  
  // Delay order
  async delayOrder(orderId: string | number, delayMinutes: number, reason?: string): Promise<void> {
    try {
      await api.post(`${this.baseUrl}/${orderId}/delay`, {
        delay_minutes: delayMinutes,
        reason
      });
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }
  
  // Update order priority
  async updatePriority(orderId: string | number, priority: string): Promise<void> {
    try {
      await api.put(`${this.baseUrl}/${orderId}/priority`, { priority });
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }
  
  // Add order tag
  async addTag(orderId: string | number, tagId: number): Promise<void> {
    try {
      await api.post(`${this.baseUrl}/${orderId}/tags`, { tag_id: tagId });
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }
  
  // Remove order tag
  async removeTag(orderId: string | number, tagId: number): Promise<void> {
    try {
      await api.delete(`${this.baseUrl}/${orderId}/tags/${tagId}`);
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }
  
  // Archive order
  async archiveOrder(orderId: string | number): Promise<void> {
    try {
      await api.post(`${this.baseUrl}/${orderId}/archive`);
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }
  
  // Get archived orders
  async getArchivedOrders(): Promise<Order[]> {
    try {
      const response = await api.get(`${this.baseUrl}/archived`);
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }
}

// Export as singleton instance
export const orderService = new OrderService();

// Also export the class for testing
export { OrderService };

export default orderService;