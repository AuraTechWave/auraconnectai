import { APIRequestContext, request } from '@playwright/test';
import { TEST_CONFIG } from '../config/test-config';

export class APIHelpers {
  private apiContext: APIRequestContext;
  private authToken: string | null = null;

  constructor(apiContext: APIRequestContext) {
    this.apiContext = apiContext;
  }

  /**
   * Set authentication token
   */
  setAuthToken(token: string) {
    this.authToken = token;
  }

  /**
   * Get default headers
   */
  private getHeaders() {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    
    if (this.authToken) {
      headers['Authorization'] = `Bearer ${this.authToken}`;
    }
    
    return headers;
  }

  /**
   * Login via API
   */
  async apiLogin(email: string, password: string): Promise<string> {
    const response = await this.apiContext.post(`${TEST_CONFIG.API_BASE_URL}/auth/login`, {
      data: {
        email,
        password
      }
    });

    const responseData = await response.json();
    
    if (!response.ok()) {
      throw new Error(`Login failed: ${responseData.message || response.statusText()}`);
    }

    this.authToken = responseData.access_token;
    return this.authToken;
  }

  /**
   * Create test user via API
   */
  async createTestUser(userData: {
    email: string;
    password: string;
    role: string;
    name?: string;
  }) {
    const response = await this.apiContext.post(`${TEST_CONFIG.API_BASE_URL}/auth/register`, {
      headers: this.getHeaders(),
      data: userData
    });

    if (!response.ok()) {
      const error = await response.text();
      throw new Error(`Failed to create user: ${error}`);
    }

    return await response.json();
  }

  /**
   * Create test menu item
   */
  async createMenuItem(itemData: {
    name: string;
    price: number;
    category: string;
    description?: string;
  }) {
    const response = await this.apiContext.post(`${TEST_CONFIG.API_BASE_URL}/menu/items`, {
      headers: this.getHeaders(),
      data: itemData
    });

    if (!response.ok()) {
      throw new Error(`Failed to create menu item: ${response.statusText()}`);
    }

    return await response.json();
  }

  /**
   * Create test order
   */
  async createOrder(orderData: {
    items: Array<{ id: string; quantity: number }>;
    customerEmail?: string;
    type: 'dine-in' | 'takeout' | 'delivery';
  }) {
    const response = await this.apiContext.post(`${TEST_CONFIG.API_BASE_URL}/orders`, {
      headers: this.getHeaders(),
      data: orderData
    });

    if (!response.ok()) {
      throw new Error(`Failed to create order: ${response.statusText()}`);
    }

    return await response.json();
  }

  /**
   * Update order status
   */
  async updateOrderStatus(orderId: string, status: string) {
    const response = await this.apiContext.patch(`${TEST_CONFIG.API_BASE_URL}/orders/${orderId}/status`, {
      headers: this.getHeaders(),
      data: { status }
    });

    if (!response.ok()) {
      throw new Error(`Failed to update order status: ${response.statusText()}`);
    }

    return await response.json();
  }

  /**
   * Create reservation
   */
  async createReservation(reservationData: {
    date: string;
    time: string;
    partySize: number;
    customerName: string;
    customerEmail: string;
    customerPhone: string;
    specialRequests?: string;
  }) {
    const response = await this.apiContext.post(`${TEST_CONFIG.API_BASE_URL}/reservations`, {
      headers: this.getHeaders(),
      data: reservationData
    });

    if (!response.ok()) {
      throw new Error(`Failed to create reservation: ${response.statusText()}`);
    }

    return await response.json();
  }

  /**
   * Clean up test data
   */
  async cleanupTestData(type: 'orders' | 'reservations' | 'users', ids: string[]) {
    const promises = ids.map(id => 
      this.apiContext.delete(`${TEST_CONFIG.API_BASE_URL}/${type}/${id}`, {
        headers: this.getHeaders()
      })
    );

    await Promise.all(promises);
  }
}

/**
 * Create API context helper
 */
export async function createAPIContext(): Promise<{ apiContext: APIRequestContext; apiHelpers: APIHelpers }> {
  const apiContext = await request.newContext({
    baseURL: TEST_CONFIG.API_BASE_URL,
    extraHTTPHeaders: {
      'Accept': 'application/json',
      'Content-Type': 'application/json'
    }
  });

  const apiHelpers = new APIHelpers(apiContext);
  
  return { apiContext, apiHelpers };
}