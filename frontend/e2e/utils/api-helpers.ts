import { APIRequestContext, request } from '@playwright/test';
import { TEST_CONFIG } from '../config/test-config';

export class APIHelpers {
  private apiContext: APIRequestContext;
  private authToken: string | null = null;
  private tenantId: string;

  constructor(apiContext: APIRequestContext) {
    this.apiContext = apiContext;
    this.tenantId = TEST_CONFIG.TEST_TENANT.id;
  }

  /**
   * Set authentication token
   */
  setAuthToken(token: string) {
    this.authToken = token;
  }

  /**
   * Get default headers with tenant context
   */
  private getHeaders() {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Tenant-ID': this.tenantId,
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
  
  /**
   * Seed test menu items
   */
  async seedMenuItems(items?: typeof TEST_CONFIG.TEST_DATA.MENU_ITEMS) {
    const menuItems = items || TEST_CONFIG.TEST_DATA.MENU_ITEMS;
    const createdItems = [];
    
    for (const item of menuItems) {
      try {
        const created = await this.createMenuItem(item);
        createdItems.push(created);
      } catch (error) {
        console.warn(`Failed to seed menu item ${item.name}:`, error);
      }
    }
    
    return createdItems;
  }
  
  /**
   * Seed test user if not exists
   */
  async seedTestUser(role: keyof typeof TEST_CONFIG.TEST_USERS) {
    const user = TEST_CONFIG.TEST_USERS[role];
    
    try {
      // Try to login first to check if user exists
      await this.apiLogin(user.email, user.password);
      return { exists: true, user };
    } catch (error) {
      // User doesn't exist, create it
      try {
        const created = await this.createTestUser({
          email: user.email,
          password: user.password,
          role: user.role,
          name: `Test ${role.toLowerCase()} User`
        });
        return { exists: false, user: created };
      } catch (createError) {
        console.error(`Failed to create test user for ${role}:`, createError);
        throw createError;
      }
    }
  }
  
  /**
   * Clean up all test orders for a user
   */
  async cleanupUserOrders(userEmail: string) {
    try {
      const response = await this.apiContext.get(
        `${TEST_CONFIG.API_BASE_URL}/orders?email=${userEmail}`,
        { headers: this.getHeaders() }
      );
      
      if (response.ok()) {
        const orders = await response.json();
        const orderIds = orders.map((o: any) => o.id);
        if (orderIds.length > 0) {
          await this.cleanupTestData('orders', orderIds);
        }
      }
    } catch (error) {
      console.warn('Failed to cleanup user orders:', error);
    }
  }
  
  /**
   * Set tenant context for API calls
   */
  setTenantContext(tenantId: string) {
    this.tenantId = tenantId;
  }
}

/**
 * Create API context helper with tenant support
 */
export async function createAPIContext(tenantId?: string): Promise<{ apiContext: APIRequestContext; apiHelpers: APIHelpers }> {
  const apiContext = await request.newContext({
    baseURL: TEST_CONFIG.API_BASE_URL,
    extraHTTPHeaders: {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
      'X-Tenant-ID': tenantId || TEST_CONFIG.TEST_TENANT.id
    }
  });

  const apiHelpers = new APIHelpers(apiContext);
  if (tenantId) {
    apiHelpers.setTenantContext(tenantId);
  }
  
  return { apiContext, apiHelpers };
}