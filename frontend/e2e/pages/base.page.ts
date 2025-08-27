import { Page, Locator, expect } from '@playwright/test';
import { TEST_CONFIG } from '../config/test-config';

export abstract class BasePage {
  protected page: Page;
  protected baseURL: string;

  constructor(page: Page) {
    this.page = page;
    this.baseURL = page.context().browser()?.options?.baseURL || TEST_CONFIG.API_BASE_URL;
  }

  /**
   * Navigate to a specific path
   */
  async goto(path: string = '') {
    await this.page.goto(`${this.baseURL}${path}`, {
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
}