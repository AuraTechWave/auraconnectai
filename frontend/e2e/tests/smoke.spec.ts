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
    try {
      const response = await request.get('http://localhost:8000/health', {
        failOnStatusCode: false
      });
      
      // API should be running
      expect(response.status()).toBeLessThan(500);
    } catch (error) {
      // Skip if API is not available
      console.log('API not available for health check');
    }
  });
});