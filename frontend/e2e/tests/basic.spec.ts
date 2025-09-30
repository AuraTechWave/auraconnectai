import { test, expect } from '@playwright/test';

test.describe('Basic Tests', () => {
  test('application starts', async ({ page }) => {
    // Try to navigate to the app
    await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 60000 });
    
    // Wait a bit for React to render
    await page.waitForTimeout(5000);
    
    // Take a screenshot for debugging
    await page.screenshot({ path: 'test-results/app-loaded.png' });
    
    // Very basic check - page should have a title
    const title = await page.title();
    expect(title).toBeDefined();
    
    // Page should not be completely empty
    const bodyText = await page.textContent('body');
    expect(bodyText).toBeTruthy();
  });

  test('page responds to navigation', async ({ page }) => {
    // Navigate to root
    const response = await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 60000 });
    
    // Should get a successful response
    expect(response?.status()).toBeLessThan(400);
  });
});