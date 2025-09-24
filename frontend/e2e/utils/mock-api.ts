import { Page, Route } from '@playwright/test';

type RouteHandler = Parameters<Page['route']>[1];

export class MockAPI {
  private readonly registeredRoutes = new Set<string>();

  constructor(private readonly page: Page) {}

  private async registerRoute(url: string, handler: RouteHandler) {
    this.registeredRoutes.add(url);
    await this.page.route(url, handler);
  }

  async setupAuthMocks() {
    // Mock successful login
    await this.registerRoute('**/api/v1/auth/login', async (route: Route) => {
      const request = route.request();
      const postData = request.postDataJSON();

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
            access_token: 'mock-jwt-token',
            refreshToken: 'mock-refresh-token',
            refresh_token: 'mock-refresh-token',
          }),
        });
      } else {
        await route.fulfill({
          status: 401,
          contentType: 'application/json',
          body: JSON.stringify({
            message: 'Invalid credentials',
          }),
        });
      }
    });

    // Mock token refresh
    await this.registerRoute('**/api/v1/auth/refresh', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          token: 'mock-jwt-token-refreshed',
          access_token: 'mock-jwt-token-refreshed',
          refreshToken: 'mock-refresh-token-updated',
          refresh_token: 'mock-refresh-token-updated',
        }),
      });
    });

    // Mock health check
    await this.registerRoute('**/health', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'healthy',
          timestamp: new Date().toISOString(),
        }),
      });
    });

    // Mock logout
    await this.registerRoute('**/api/v1/auth/logout', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          message: 'Logged out successfully',
        }),
      });
    });
  }

  async setupOrderMocks() {
    await this.registerRoute('**/api/v1/orders', async (route: Route) => {
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
                { name: 'Drink', quantity: 1, price: 2.99 },
              ],
              createdAt: new Date().toISOString(),
            },
          ],
          total: 1,
          page: 1,
          pageSize: 10,
        }),
      });
    });
  }

  async setupAllMocks() {
    await this.setupAuthMocks();
    await this.setupOrderMocks();
  }

  async teardown() {
    await Promise.all(
      Array.from(this.registeredRoutes).map((pattern) => this.page.unroute(pattern))
    );
    this.registeredRoutes.clear();
  }
}
