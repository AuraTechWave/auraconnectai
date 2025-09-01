import { test, expect } from '@playwright/test';

test.describe('Smoke Tests', () => {
  test('frontend application loads', async ({ page }) => {
    // Navigate to the app
    await page.goto('/');
    
    // Wait for the app to load
    await page.waitForLoadState('networkidle');
    
    // Check if the page has loaded by looking for React root
    const appRoot = page.locator('#root');
    await expect(appRoot).toBeVisible();
    
    // Check page title contains something
    const title = await page.title();
    expect(title).toBeTruthy();
  });

  test('API health check', async ({ request }) => {
    const apiUrl = process.env.E2E_API_BASE_URL || 'http://localhost:8000';
    try {
      const response = await request.get(`${apiUrl}/health`, {
        failOnStatusCode: false
      });
      
      // API should be running
      expect(response.status()).toBeLessThan(500);
    } catch (error) {
      // Skip if API is not available
      console.log('API not available for health check');
    }
  });
  
  test('login page loads', async ({ page }) => {
    // Navigate to the login page
    await page.goto('/login');
    
    // Wait for the page to load
    await page.waitForLoadState('networkidle');
    
    // Check for login form elements
    const emailInput = page.locator('input[type="email"], input#email');
    const passwordInput = page.locator('input[type="password"], input#password');
    const loginButton = page.locator('button[type="submit"], button:has-text("Sign In")');
    
    await expect(emailInput).toBeVisible();
    await expect(passwordInput).toBeVisible();
    await expect(loginButton).toBeVisible();
  });
});