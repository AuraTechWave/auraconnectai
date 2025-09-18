import { test, expect } from '../../fixtures/test-fixtures';
import { TEST_CONFIG } from '../../config/test-config';

test.describe('Authentication - Logout Flow', () => {
  test.beforeEach(async ({ authenticatedPage }) => {
    // authenticatedPage fixture handles login automatically
    // Navigate to a protected page
    await authenticatedPage.goto('/dashboard');
  });

  test('successful logout clears auth state', async ({ authenticatedPage }) => {
    // Verify we're logged in
    const authTokenBefore = await authenticatedPage.getAuthToken();
    expect(authTokenBefore).toBeTruthy();
    
    // Perform logout
    await authenticatedPage.logout();
    
    // Verify auth token is cleared
    const authTokenAfter = await authenticatedPage.getAuthToken();
    expect(authTokenAfter).toBeFalsy();
    
    // Verify redirect to login page
    await authenticatedPage.assertURLContains('/login');
  });

  test('logout from different pages', async ({ authenticatedPage }) => {
    const protectedPages = ['/dashboard', '/profile', '/orders'];
    
    for (const page of protectedPages) {
      // Navigate to protected page
      await authenticatedPage.goto(page);
      
      // Verify we can access it
      await expect(authenticatedPage['page']).not.toHaveURL(/\/login/);
      
      // Logout
      await authenticatedPage.logout();
      
      // Verify redirect to login
      await authenticatedPage.assertURLContains('/login');
      
      // Try to access protected page again
      await authenticatedPage.goto(page);
      
      // Should be redirected to login
      await authenticatedPage.assertURLContains('/login');
      
      // Re-login for next iteration
      await authenticatedPage.login(
        TEST_CONFIG.TEST_USERS.CUSTOMER.email,
        TEST_CONFIG.TEST_USERS.CUSTOMER.password
      );
      await authenticatedPage.waitForSuccessfulLogin();
    }
  });

  test('session timeout redirects to login', async ({ authenticatedPage, page }) => {
    // Simulate session expiry by clearing auth token
    await page.evaluate(() => {
      localStorage.removeItem('authToken');
    });
    
    // Try to navigate to protected page
    await page.goto('/dashboard');
    
    // Should be redirected to login
    await expect(page).toHaveURL(/\/login/);
  });

  test('logout clears all user data', async ({ authenticatedPage, page }) => {
    // Add some user data to local storage
    await page.evaluate(() => {
      localStorage.setItem('userPreferences', JSON.stringify({ theme: 'dark' }));
      localStorage.setItem('cartItems', JSON.stringify([{ id: 1, qty: 2 }]));
      sessionStorage.setItem('tempData', 'some-data');
    });
    
    // Verify data exists
    const userPrefs = await page.evaluate(() => localStorage.getItem('userPreferences'));
    expect(userPrefs).toBeTruthy();
    
    // Logout
    await authenticatedPage.logout();
    
    // Verify all user data is cleared
    const clearedData = await page.evaluate(() => ({
      authToken: localStorage.getItem('authToken'),
      userPreferences: localStorage.getItem('userPreferences'),
      cartItems: localStorage.getItem('cartItems'),
      tempData: sessionStorage.getItem('tempData')
    }));
    
    expect(clearedData.authToken).toBeFalsy();
    expect(clearedData.userPreferences).toBeFalsy();
    expect(clearedData.cartItems).toBeFalsy();
    expect(clearedData.tempData).toBeFalsy();
  });

  test('concurrent logout from multiple tabs', async ({ authenticatedPage, context }) => {
    // Open second tab
    const page2 = await context.newPage();
    await page2.goto('/dashboard');
    
    // Verify both tabs are authenticated
    const authToken1 = await authenticatedPage.getAuthToken();
    const authToken2 = await page2.evaluate(() => localStorage.getItem('authToken'));
    
    expect(authToken1).toBeTruthy();
    expect(authToken2).toBeTruthy();
    
    // Logout from first tab
    await authenticatedPage.logout();
    
    // Wait a bit for storage event to propagate
    await page2.waitForTimeout(1000);
    
    // Refresh second tab
    await page2.reload();
    
    // Second tab should also be logged out
    await expect(page2).toHaveURL(/\/login/);
  });

  test('logout prevents access to protected API endpoints', async ({ authenticatedPage, page }) => {
    // Setup API intercept
    let apiCallAfterLogout = false;
    
    await page.route('**/api/user/profile', (route) => {
      const authHeader = route.request().headers()['authorization'];
      if (!authHeader || authHeader === 'Bearer null') {
        apiCallAfterLogout = true;
        route.fulfill({
          status: 401,
          json: { error: 'Unauthorized' }
        });
      } else {
        route.continue();
      }
    });
    
    // Logout
    await authenticatedPage.logout();
    
    // Try to access protected endpoint
    const response = await page.evaluate(async () => {
      try {
        const res = await fetch('/api/user/profile', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('authToken')}`
          }
        });
        return { status: res.status, ok: res.ok };
      } catch (error) {
        return { error: true };
      }
    });
    
    // Verify unauthorized response
    expect(response.status).toBe(401);
    expect(apiCallAfterLogout).toBeTruthy();
  });

  test('logout button visibility based on auth state', async ({ authenticatedPage, page }) => {
    // Verify logout button is visible when logged in
    const logoutButton = page.locator('[data-testid="logout-button"], button:has-text("Logout")');
    await expect(logoutButton).toBeVisible();
    
    // Logout
    await authenticatedPage.logout();
    
    // Verify logout button is not visible when logged out
    await expect(logoutButton).not.toBeVisible();
  });
});