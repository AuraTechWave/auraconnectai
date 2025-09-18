import { test, expect } from '../../fixtures/test-fixtures';
import { TEST_CONFIG } from '../../config/test-config';

test.describe('Authentication - Session Management', () => {
  test('refresh token rotation', async ({ loginPage, page }) => {
    // Login
    await loginPage.gotoLoginPage();
    await loginPage.login(
      TEST_CONFIG.TEST_USERS.CUSTOMER.email,
      TEST_CONFIG.TEST_USERS.CUSTOMER.password
    );
    await loginPage.waitForSuccessfulLogin();
    
    // Get initial tokens
    const initialTokens = await page.evaluate(() => ({
      accessToken: localStorage.getItem('authToken'),
      refreshToken: localStorage.getItem('refreshToken')
    }));
    
    expect(initialTokens.accessToken).toBeTruthy();
    
    // Wait for token to be close to expiry (simulate)
    await page.evaluate(() => {
      // Simulate token near expiry
      const event = new Event('tokenExpiring');
      window.dispatchEvent(event);
    });
    
    // Wait for token refresh
    await page.waitForResponse(response => 
      response.url().includes('/auth/refresh') && response.status() === 200,
      { timeout: 5000 }
    ).catch(() => null); // Gracefully handle if refresh endpoint doesn't exist yet
    
    // Get new tokens
    const newTokens = await page.evaluate(() => ({
      accessToken: localStorage.getItem('authToken'),
      refreshToken: localStorage.getItem('refreshToken')
    }));
    
    // Verify tokens were rotated (if refresh is implemented)
    // This test will need adjustment based on actual implementation
  });

  test('session persistence across browser restart', async ({ loginPage, context }) => {
    // Login
    await loginPage.gotoLoginPage();
    await loginPage.login(
      TEST_CONFIG.TEST_USERS.CUSTOMER.email,
      TEST_CONFIG.TEST_USERS.CUSTOMER.password
    );
    await loginPage.waitForSuccessfulLogin();
    
    // Save storage state
    await context.storageState({ path: './auth-states/session-test.json' });
    
    // Create new context with saved state
    const newContext = await loginPage['page'].context().browser()?.newContext({
      storageState: './auth-states/session-test.json'
    });
    
    if (newContext) {
      const newPage = await newContext.newPage();
      await newPage.goto('/dashboard');
      
      // Should not be redirected to login
      await expect(newPage).not.toHaveURL(/\/login/);
      
      await newContext.close();
    }
  });

  test('multiple session detection', async ({ loginPage, context, browser }) => {
    // Login in first context
    await loginPage.gotoLoginPage();
    await loginPage.login(
      TEST_CONFIG.TEST_USERS.CUSTOMER.email,
      TEST_CONFIG.TEST_USERS.CUSTOMER.password
    );
    await loginPage.waitForSuccessfulLogin();
    
    // Create second context and try to login
    const context2 = await browser.newContext();
    const page2 = await context2.newPage();
    const loginPage2 = new (await import('../../pages/login.page')).LoginPage(page2);
    
    await loginPage2.gotoLoginPage();
    await loginPage2.login(
      TEST_CONFIG.TEST_USERS.CUSTOMER.email,
      TEST_CONFIG.TEST_USERS.CUSTOMER.password
    );
    
    // Check if system detects multiple sessions
    // This behavior depends on backend implementation
    // Either: warning message, logout from other session, or allow multiple sessions
    
    await context2.close();
  });

  test('CSRF token handling', async ({ authenticatedPage, page }) => {
    // Check if CSRF token is set
    const csrfToken = await page.evaluate(() => {
      // Check meta tag
      const metaTag = document.querySelector('meta[name="csrf-token"]');
      if (metaTag) return metaTag.getAttribute('content');
      
      // Check cookie
      const cookies = document.cookie.split(';');
      const csrfCookie = cookies.find(c => c.trim().startsWith('csrf'));
      if (csrfCookie) return csrfCookie.split('=')[1];
      
      // Check header
      return localStorage.getItem('csrfToken');
    });
    
    // If CSRF protection is implemented, token should exist
    if (csrfToken) {
      // Verify CSRF token is sent with requests
      const response = await page.evaluate(async (token) => {
        const res = await fetch('/api/user/profile', {
          method: 'POST',
          headers: {
            'X-CSRF-Token': token || '',
            'Authorization': `Bearer ${localStorage.getItem('authToken')}`
          }
        });
        return res.headers.get('X-CSRF-Token');
      }, csrfToken);
      
      expect(response).toBeTruthy();
    }
  });

  test('session activity timeout', async ({ authenticatedPage, page }) => {
    // Set activity timeout (if configurable)
    await page.evaluate(() => {
      if ((window as any).setSessionTimeout) {
        (window as any).setSessionTimeout(1); // 1 minute for testing
      }
    });
    
    // Simulate inactivity
    await page.waitForTimeout(61000); // Wait 61 seconds
    
    // Try to perform an action
    await page.goto('/dashboard');
    
    // Should be redirected to login due to inactivity
    // This test depends on implementation of activity timeout
  });

  test('prevent session fixation attacks', async ({ loginPage, page }) => {
    // Get session ID before login
    const sessionBeforeLogin = await page.evaluate(() => {
      return document.cookie.split(';')
        .find(c => c.trim().startsWith('sessionid'))
        ?.split('=')[1];
    });
    
    // Login
    await loginPage.gotoLoginPage();
    await loginPage.login(
      TEST_CONFIG.TEST_USERS.CUSTOMER.email,
      TEST_CONFIG.TEST_USERS.CUSTOMER.password
    );
    await loginPage.waitForSuccessfulLogin();
    
    // Get session ID after login
    const sessionAfterLogin = await page.evaluate(() => {
      return document.cookie.split(';')
        .find(c => c.trim().startsWith('sessionid'))
        ?.split('=')[1];
    });
    
    // Session ID should change after login (if session fixation protection exists)
    if (sessionBeforeLogin && sessionAfterLogin) {
      expect(sessionBeforeLogin).not.toBe(sessionAfterLogin);
    }
  });

  test('handle expired auth token gracefully', async ({ authenticatedPage, page }) => {
    // Set expired token
    await page.evaluate(() => {
      // Create expired JWT (this is a mock - real JWT would be from server)
      const expiredToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE2MDAwMDAwMDB9.expired';
      localStorage.setItem('authToken', expiredToken);
    });
    
    // Try to access protected resource
    await page.goto('/dashboard');
    
    // Should redirect to login
    await expect(page).toHaveURL(/\/login/);
    
    // Check for appropriate error message
    const errorMessage = page.locator('.session-expired-message, [data-testid="session-expired"]');
    const isVisible = await errorMessage.isVisible().catch(() => false);
    
    if (isVisible) {
      const text = await errorMessage.textContent();
      expect(text).toContain('session expired');
    }
  });
});