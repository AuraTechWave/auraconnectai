import { test as base, expect } from '@playwright/test';
import { LoginPage } from '../pages/login.page';
import { TEST_CONFIG } from '../config/test-config';

// Define custom fixtures
type MyFixtures = {
  loginPage: LoginPage;
  authenticatedPage: LoginPage;
  testUser: typeof TEST_CONFIG.TEST_USERS.CUSTOMER;
};

// Extend base test with custom fixtures
export const test = base.extend<MyFixtures>({
  // Login page fixture
  loginPage: async ({ page }, use) => {
    const loginPage = new LoginPage(page);
    await use(loginPage);
  },

  // Authenticated page fixture (simplified for now)
  authenticatedPage: async ({ page }, use) => {
    const loginPage = new LoginPage(page);
    
    // For now, just set mock auth token
    await page.goto('/');
    await page.evaluate(() => {
      localStorage.setItem('authToken', 'mock-test-token');
    });
    
    await use(loginPage);
  },

  // Test user fixture
  testUser: async ({}, use) => {
    await use(TEST_CONFIG.TEST_USERS.CUSTOMER);
  },
});

export { expect };

// Helper function to create authenticated context
export async function createAuthenticatedContext(browser: any, userType: keyof typeof TEST_CONFIG.TEST_USERS = 'CUSTOMER') {
  const context = await browser.newContext();
  const page = await context.newPage();
  
  const loginPage = new LoginPage(page);
  await loginPage.gotoLoginPage();
  
  const user = TEST_CONFIG.TEST_USERS[userType];
  await loginPage.login(user.email, user.password);
  await loginPage.waitForSuccessfulLogin();
  
  // Get auth token and save to context
  const authToken = await loginPage.getAuthToken();
  
  // Save storage state
  await context.storageState({ path: `./auth-states/${userType.toLowerCase()}.json` });
  
  await page.close();
  await context.close();
  
  return authToken;
}

// Test data generators
export const testDataGenerators = {
  // Generate unique email
  generateEmail: (prefix: string = 'test') => {
    const timestamp = Date.now();
    const random = Math.random().toString(36).substring(7);
    return `${prefix}.${timestamp}.${random}@auraconnect.ai`;
  },

  // Generate unique phone number
  generatePhoneNumber: () => {
    const areaCode = Math.floor(Math.random() * 900) + 100;
    const prefix = Math.floor(Math.random() * 900) + 100;
    const lineNumber = Math.floor(Math.random() * 9000) + 1000;
    return `${areaCode}-${prefix}-${lineNumber}`;
  },

  // Generate order details
  generateOrder: (itemCount: number = 3) => {
    const items = TEST_CONFIG.TEST_DATA.MENU_ITEMS.slice(0, itemCount);
    const subtotal = items.reduce((sum, item) => sum + item.price, 0);
    const tax = subtotal * 0.08; // 8% tax
    const total = subtotal + tax;
    
    return {
      items,
      subtotal: parseFloat(subtotal.toFixed(2)),
      tax: parseFloat(tax.toFixed(2)),
      total: parseFloat(total.toFixed(2))
    };
  },

  // Generate reservation details
  generateReservation: (daysFromNow: number = 1) => {
    const date = new Date();
    date.setDate(date.getDate() + daysFromNow);
    
    return {
      date: date.toISOString().split('T')[0],
      time: '19:00',
      partySize: Math.floor(Math.random() * 6) + 2,
      specialRequests: 'Test reservation - please ignore'
    };
  }
};

// Custom test annotations
export const annotations = {
  smoke: () => test.describe.configure({ tag: '@smoke' }),
  regression: () => test.describe.configure({ tag: '@regression' }),
  critical: () => test.describe.configure({ tag: '@critical' }),
  flaky: () => test.describe.configure({ tag: '@flaky', retries: 2 })
};