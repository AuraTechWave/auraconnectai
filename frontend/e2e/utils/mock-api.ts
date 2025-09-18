import { Page, Route } from '@playwright/test';

export class MockAPI {
  constructor(private page: Page) {}

  async setupAuthMocks() {
    // Mock successful login
    await this.page.route('**/api/v1/auth/login', async (route: Route) => {
      const request = route.request();
      const postData = request.postDataJSON();
      
      // Check for test users
      if (postData?.email?.includes('test') && postData?.password) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            customer: {
              id: 'test-user-123',
              email: postData.email,
              firstName: 'Test',
              lastName: 'User',
            },
            token: 'mock-jwt-token',
            refreshToken: 'mock-refresh-token'
          })
        });
      } else {
        await route.fulfill({
          status: 401,
          contentType: 'application/json',
          body: JSON.stringify({
            message: 'Invalid credentials'
          })
        });
      }
    });

    // Mock health check
    await this.page.route('**/health', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'healthy',
          timestamp: new Date().toISOString()
        })
      });
    });

    // Mock logout
    await this.page.route('**/api/v1/auth/logout', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          message: 'Logged out successfully'
        })
      });
    });
  }

  async setupOrderMocks() {
    // Mock get orders
    await this.page.route('**/api/v1/orders', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          orders: [
            {
              id: 'order-123',
              status: 'pending',
              total: 25.99,
              items: [
                { name: 'Burger', quantity: 1, price: 12.99 },
                { name: 'Fries', quantity: 1, price: 4.99 },
                { name: 'Drink', quantity: 1, price: 2.99 }
              ],
              createdAt: new Date().toISOString()
            }
          ],
          total: 1,
          page: 1,
          pageSize: 10
        })
      });
    });
  }

  async setupAllMocks() {
    await this.setupAuthMocks();
    await this.setupOrderMocks();
  }
}