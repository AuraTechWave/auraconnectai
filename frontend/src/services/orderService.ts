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
  PaginatedResponse 
} from '../types/order.types';

class OrderService {
  private baseUrl = '/orders';
  
  // Get list of orders with filters
  async getOrders(params?: OrderListParams): Promise<PaginatedResponse<Order>> {
    try {
      // Convert array params to comma-separated strings if needed
      const queryParams: Record<string, any> = { ...params };
      
      if (params?.status && Array.isArray(params.status)) {
        queryParams.status = params.status.join(',');
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
  async getOrder(id: number): Promise<Order> {
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
  async updateOrder(id: number, data: OrderUpdateRequest): Promise<Order> {
    try {
      const response = await api.put(`${this.baseUrl}/${id}`, data);
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }
  
  // Update order status
  async updateOrderStatus(orderId: number, status: string): Promise<Order> {
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
  async cancelOrder(orderId: number, reason?: string): Promise<Order> {
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
  async refundOrder(orderId: number, data: RefundRequest): Promise<RefundResponse> {
    try {
      // Based on backend structure, refunds might be under payment reconciliation
      const response = await api.post(`/api/v1/orders/payment-reconciliation/${orderId}/refund`, data);
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }
  
  // Get order analytics
  async getAnalytics(params?: {
    start_date?: string;
    end_date?: string;
    restaurant_id?: number;
  }): Promise<OrderAnalytics> {
    try {
      const queryString = buildQueryString(params || {});
      // Check if there's a specific analytics endpoint
      const response = await api.get(`${this.baseUrl}/analytics/summary${queryString ? `?${queryString}` : ''}`);
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }
  
  // Search orders (might use main endpoint with search param)
  async searchOrders(query: string): Promise<Order[]> {
    try {
      const params: OrderListParams = { search: query };
      const response = await this.getOrders(params);
      return response.items;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }
  
  // Export orders
  async exportOrders(format: 'csv' | 'excel' | 'pdf', params?: OrderListParams): Promise<Blob> {
    try {
      const queryParams = { ...params, format };
      const queryString = buildQueryString(queryParams);
      
      const response = await api.get(
        `${this.baseUrl}/export${queryString ? `?${queryString}` : ''}`,
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
  async delayOrder(orderId: number, delayMinutes: number, reason?: string): Promise<void> {
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
  async updatePriority(orderId: number, priority: string): Promise<void> {
    try {
      await api.put(`${this.baseUrl}/${orderId}/priority`, { priority });
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }
  
  // Add order tag
  async addTag(orderId: number, tagId: number): Promise<void> {
    try {
      await api.post(`${this.baseUrl}/${orderId}/tags`, { tag_id: tagId });
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }
  
  // Remove order tag
  async removeTag(orderId: number, tagId: number): Promise<void> {
    try {
      await api.delete(`${this.baseUrl}/${orderId}/tags/${tagId}`);
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }
  
  // Archive order
  async archiveOrder(orderId: number): Promise<void> {
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