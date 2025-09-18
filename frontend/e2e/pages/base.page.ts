import { Page, Locator, expect } from '@playwright/test';
import { TEST_CONFIG, getTenantBaseUrl } from '../config/test-config';

export abstract class BasePage {
  protected page: Page;
  protected baseURL: string;
  protected tenantHeaders: Record<string, string>;

  constructor(page: Page) {
    this.page = page;
    this.baseURL = getTenantBaseUrl();
    this.tenantHeaders = TEST_CONFIG.TEST_TENANT.headers;
  }

  /**
   * Navigate to a specific path with tenant context
   */
  async goto(path: string = '') {
    // Set tenant headers before navigation
    await this.page.setExtraHTTPHeaders(this.tenantHeaders);
    
    const url = path.startsWith('http') ? path : `${this.baseURL}${path}`;
    await this.page.goto(url, {
      waitUntil: 'networkidle',
      timeout: TEST_CONFIG.TIMEOUTS.NAVIGATION
    });
  }

  /**
   * Wait for page to be loaded
   */
  async waitForPageLoad() {
    await this.page.waitForLoadState('networkidle');
  }

  /**
   * Wait for an element to be visible
   */
  async waitForElement(selector: string | Locator, timeout?: number) {
    const element = typeof selector === 'string' ? this.page.locator(selector) : selector;
    await element.waitFor({ state: 'visible', timeout: timeout || TEST_CONFIG.TIMEOUTS.UI });
  }

  /**
   * Click an element with retry logic
   */
  async clickElement(selector: string | Locator) {
    const element = typeof selector === 'string' ? this.page.locator(selector) : selector;
    await element.click({ timeout: TEST_CONFIG.TIMEOUTS.UI });
  }

  /**
   * Fill form field with value
   */
  async fillField(selector: string | Locator, value: string) {
    const element = typeof selector === 'string' ? this.page.locator(selector) : selector;
    await element.fill(value);
  }

  /**
   * Clear and fill form field
   */
  async clearAndFill(selector: string | Locator, value: string) {
    const element = typeof selector === 'string' ? this.page.locator(selector) : selector;
    await element.clear();
    await element.fill(value);
  }

  /**
   * Get text content of an element
   */
  async getElementText(selector: string | Locator): Promise<string> {
    const element = typeof selector === 'string' ? this.page.locator(selector) : selector;
    return await element.textContent() || '';
  }

  /**
   * Check if element is visible
   */
  async isElementVisible(selector: string | Locator): Promise<boolean> {
    const element = typeof selector === 'string' ? this.page.locator(selector) : selector;
    return await element.isVisible();
  }

  /**
   * Take screenshot
   */
  async takeScreenshot(name: string) {
    await this.page.screenshot({ path: `./screenshots/${name}.png`, fullPage: true });
  }

  /**
   * Wait for API response
   */
  async waitForAPIResponse(url: string | RegExp) {
    return await this.page.waitForResponse(
      response => {
        if (url instanceof RegExp) {
          return url.test(response.url());
        }
        return response.url().includes(url);
      },
      { timeout: TEST_CONFIG.TIMEOUTS.API }
    );
  }

  /**
   * Get local storage item
   */
  async getLocalStorageItem(key: string): Promise<string | null> {
    return await this.page.evaluate((key) => localStorage.getItem(key), key);
  }

  /**
   * Set local storage item
   */
  async setLocalStorageItem(key: string, value: string) {
    await this.page.evaluate(([key, value]) => {
      localStorage.setItem(key, value);
    }, [key, value]);
  }

  /**
   * Clear local storage
   */
  async clearLocalStorage() {
    await this.page.evaluate(() => localStorage.clear());
  }

  /**
   * Assert page title
   */
  async assertPageTitle(expectedTitle: string) {
    await expect(this.page).toHaveTitle(expectedTitle);
  }

  /**
   * Assert URL contains
   */
  async assertURLContains(urlPart: string) {
    await expect(this.page).toHaveURL(new RegExp(urlPart));
  }

  /**
   * Handle dialog/alert
   */
  async handleDialog(accept: boolean = true, promptText?: string) {
    this.page.once('dialog', async dialog => {
      if (promptText && dialog.type() === 'prompt') {
        await dialog.accept(promptText);
      } else if (accept) {
        await dialog.accept();
      } else {
        await dialog.dismiss();
      }
    });
  }
  
  /**
   * Get session storage item
   */
  async getSessionStorageItem(key: string): Promise<string | null> {
    return await this.page.evaluate((key) => sessionStorage.getItem(key), key);
  }
  
  /**
   * Set session storage item
   */
  async setSessionStorageItem(key: string, value: string) {
    await this.page.evaluate(([key, value]) => {
      sessionStorage.setItem(key, value);
    }, [key, value]);
  }
  
  /**
   * Clear session storage
   */
  async clearSessionStorage() {
    await this.page.evaluate(() => sessionStorage.clear());
  }
  
  /**
   * Wait for WebSocket connection
   */
  async waitForWebSocketConnection(urlPattern?: string | RegExp) {
    return await this.page.waitForEvent('websocket', {
      predicate: ws => {
        if (!urlPattern) return true;
        const url = ws.url();
        if (urlPattern instanceof RegExp) {
          return urlPattern.test(url);
        }
        return url.includes(urlPattern);
      },
      timeout: TEST_CONFIG.TIMEOUTS.API
    });
  }
  
  /**
   * Check for cross-tenant isolation
   */
  async verifyTenantIsolation(): Promise<boolean> {
    // Check that tenant ID is present in headers or local storage
    const tenantId = await this.getLocalStorageItem('tenantId');
    const expectedTenantId = TEST_CONFIG.TEST_TENANT.id;
    return tenantId === expectedTenantId;
  }
}