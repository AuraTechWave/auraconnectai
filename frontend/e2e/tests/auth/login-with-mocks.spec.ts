import { test, expect } from '@playwright/test';
import { MockAPI } from '../../utils/mock-api';

test.describe('Login Tests with Mocks', () => {
  let mockAPI: MockAPI;

  test.beforeEach(async ({ page }) => {
    mockAPI = new MockAPI(page);
    await mockAPI.setupAuthMocks();
  });

  test('successful login with mocked API', async ({ page }) => {
    // Navigate to login page
    await page.goto('/login');
    
    // Fill login form
    await page.fill('input[type="email"], input#email', 'test@example.com');
    await page.fill('input[type="password"], input#password', 'testpassword');
    
    // Submit form
    await page.click('button[type="submit"]');
    
    // Wait for localStorage to be updated (mock login sets token)
    await page.waitForFunction(
      () => localStorage.getItem('authToken') !== null,
      { timeout: 5000 }
    ).catch(() => {
      // If auth token not set, check if we at least got a response
      console.log('Auth token not found in localStorage');
    });
    
    // Verify some indication of login attempt
    const authToken = await page.evaluate(() => localStorage.getItem('authToken'));
    const currentUrl = page.url();
    
    // Either auth token should be set OR we should have navigated away from login
    expect(authToken || !currentUrl.includes('/login')).toBeTruthy();
  });

  test('failed login with invalid credentials', async ({ page }) => {
    // Navigate to login page
    await page.goto('/login');
    
    // Fill login form with invalid credentials
    await page.fill('input[type="email"], input#email', 'invalid@example.com');
    await page.fill('input[type="password"], input#password', 'wrongpassword');
    
    // Submit form
    await page.click('button[type="submit"]');
    
    // Wait a bit for error to appear
    await page.waitForTimeout(1000);
    
    // Should still be on login page
    expect(page.url()).toContain('/login');
    
    // Check for error message (if implemented)
    const errorVisible = await page.locator('.error-message, .error, .alert-danger').isVisible().catch(() => false);
    if (errorVisible) {
      const errorText = await page.locator('.error-message, .error, .alert-danger').textContent();
      expect(errorText).toContain('Invalid');
    }
  });
});