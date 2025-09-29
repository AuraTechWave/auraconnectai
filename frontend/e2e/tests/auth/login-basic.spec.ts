import { test, expect } from '@playwright/test';

const authTestsEnabled = process.env.E2E_ENABLE_AUTH_TESTS === 'true';
const describeAuth = authTestsEnabled ? test.describe : test.describe.skip;

describeAuth('Basic Login Tests', () => {
  test('login page renders correctly', async ({ page }) => {
    // Navigate to login page
    await page.goto('/login');
    
    // Wait for page to be ready
    await page.waitForLoadState('domcontentloaded');
    
    // Check if login form elements are present
    const emailInput = await page.locator('input[type="email"], input#email').first();
    const passwordInput = await page.locator('input[type="password"], input#password').first();
    const submitButton = await page.locator('button[type="submit"]').first();
    
    // Verify elements are visible
    await expect(emailInput).toBeVisible({ timeout: 10000 });
    await expect(passwordInput).toBeVisible({ timeout: 10000 });
    await expect(submitButton).toBeVisible({ timeout: 10000 });
  });

  test('login form accepts input', async ({ page }) => {
    // Navigate to login page
    await page.goto('/login');
    
    // Wait for page to be ready
    await page.waitForLoadState('domcontentloaded');
    
    // Find form elements
    const emailInput = await page.locator('input[type="email"], input#email').first();
    const passwordInput = await page.locator('input[type="password"], input#password').first();
    
    // Type into inputs
    await emailInput.fill('test@example.com');
    await passwordInput.fill('testpassword');
    
    // Verify values were entered
    await expect(emailInput).toHaveValue('test@example.com');
    await expect(passwordInput).toHaveValue('testpassword');
  });

  test('app redirects to login when not authenticated', async ({ page }) => {
    // Clear any auth data
    await page.context().clearCookies();
    await page.evaluate(() => localStorage.clear());
    
    // Try to access protected route
    await page.goto('/admin/orders');
    
    // Should redirect to login (or show login form)
    // Note: This might need adjustment based on actual auth implementation
    const currentUrl = page.url();
    const hasLoginForm = await page.locator('input[type="email"], input#email').isVisible().catch(() => false);
    
    expect(currentUrl.includes('/login') || hasLoginForm).toBeTruthy();
  });
});
