import { test, expect } from '@playwright/test';

test.describe('Smoke Tests', () => {
  test('frontend application loads', async ({ page }) => {
    // Navigate to the app
    await page.goto('/');
    
    // Wait for the app to load
    await page.waitForLoadState('networkidle');
    
    // Check if the page has loaded by looking for common elements
    // This will need to be adjusted based on actual app structure
    const appRoot = page.locator('#root, .app, [data-testid="app-container"]');
    await expect(appRoot).toBeVisible();
    
    // Check page title
    const title = await page.title();
    expect(title).toBeTruthy();
    expect(title.toLowerCase()).toContain('auraconnect');
  });

  test('navigation menu is accessible', async ({ page }) => {
    await page.goto('/');
    
    // Look for navigation elements
    const nav = page.locator('nav, [role="navigation"], .navbar, .navigation');
    await expect(nav.first()).toBeVisible();
  });

  test('login page is accessible', async ({ page }) => {
    await page.goto('/login');
    
    // Check for login form elements
    const emailInput = page.locator('input[type="email"], input[name="email"], #email');
    const passwordInput = page.locator('input[type="password"], input[name="password"], #password');
    const submitButton = page.locator('button[type="submit"], button:has-text("Login"), button:has-text("Sign In")');
    
    await expect(emailInput.first()).toBeVisible();
    await expect(passwordInput.first()).toBeVisible();
    await expect(submitButton.first()).toBeVisible();
  });

  test('API health check', async ({ request }) => {
    const response = await request.get('http://localhost:8000/health', {
      failOnStatusCode: false
    });
    
    // API should be running
    expect(response.status()).toBeLessThan(500);
  });
});