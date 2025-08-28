import { Page } from '@playwright/test';
import { BasePage } from './base.page';

export class LoginPage extends BasePage {
  // Selectors - Using only data-testid for reliability
  // Fallback selectors removed to enforce proper data-testid usage
  private readonly emailInput = '[data-testid="login-email"]';
  private readonly passwordInput = '[data-testid="login-password"]';
  private readonly loginButton = '[data-testid="login-submit"]';
  private readonly errorMessage = '[data-testid="login-error"]';
  private readonly forgotPasswordLink = '[data-testid="forgot-password-link"]';
  private readonly signUpLink = '[data-testid="signup-link"]';
  private readonly rememberMeCheckbox = '[data-testid="remember-me"]';
  private readonly logoutButton = '[data-testid="logout-button"]';
  private readonly userMenuTrigger = '[data-testid="user-menu-trigger"]';
  private readonly authStateIndicator = '[data-testid="auth-state"]';

  constructor(page: Page) {
    super(page);
  }

  /**
   * Navigate to login page
   */
  async gotoLoginPage() {
    await this.goto('/login');
    await this.waitForElement(this.emailInput);
  }

  /**
   * Fill login form
   */
  async fillLoginForm(email: string, password: string, rememberMe: boolean = false) {
    await this.clearAndFill(this.emailInput, email);
    await this.clearAndFill(this.passwordInput, password);
    
    if (rememberMe) {
      await this.clickElement(this.rememberMeCheckbox);
    }
  }

  /**
   * Submit login form
   */
  async submitLogin() {
    await this.clickElement(this.loginButton);
  }

  /**
   * Complete login process
   */
  async login(email: string, password: string, rememberMe: boolean = false) {
    await this.fillLoginForm(email, password, rememberMe);
    await this.submitLogin();
  }

  /**
   * Login and wait for redirect
   */
  async loginAndWaitForRedirect(email: string, password: string, expectedUrl?: string) {
    await this.login(email, password);
    
    // Wait for navigation away from login page
    await this.page.waitForURL((url) => !url.toString().includes('/login'), {
      timeout: 10000
    });
    
    if (expectedUrl) {
      await this.assertURLContains(expectedUrl);
    }
  }

  /**
   * Logout
   */
  async logout() {
    // First check if user menu needs to be opened (mobile/desktop difference)
    const userMenuVisible = await this.isElementVisible(this.userMenuTrigger);
    if (userMenuVisible) {
      await this.clickElement(this.userMenuTrigger);
      await this.page.waitForTimeout(500); // Brief wait for menu animation
    }
    
    await this.clickElement(this.logoutButton);
    await this.waitForElement(this.emailInput);
  }

  /**
   * Get error message
   */
  async getErrorMessage(): Promise<string> {
    await this.waitForElement(this.errorMessage, 5000);
    return await this.getElementText(this.errorMessage);
  }

  /**
   * Check if error is displayed
   */
  async isErrorDisplayed(): Promise<boolean> {
    return await this.isElementVisible(this.errorMessage);
  }

  /**
   * Click forgot password link
   */
  async clickForgotPassword() {
    await this.clickElement(this.forgotPasswordLink);
  }

  /**
   * Click sign up link
   */
  async clickSignUp() {
    await this.clickElement(this.signUpLink);
  }

  /**
   * Check if user is logged in by checking for auth token
   */
  async isLoggedIn(): Promise<boolean> {
    const authToken = await this.getLocalStorageItem('authToken');
    return authToken !== null && authToken !== '';
  }

  /**
   * Wait for successful login with multiple verification points
   */
  async waitForSuccessfulLogin() {
    // Wait for auth token to be set
    await this.page.waitForFunction(
      () => localStorage.getItem('authToken') !== null,
      { timeout: 10000 }
    );
    
    // Also wait for navigation away from login page
    await this.page.waitForURL((url) => !url.toString().includes('/login'), {
      timeout: 10000
    }).catch(() => {
      // If URL doesn't change, check for auth indicator
      return this.waitForElement(this.authStateIndicator, 5000);
    });
  }

  /**
   * Get stored auth token
   */
  async getAuthToken(): Promise<string | null> {
    return await this.getLocalStorageItem('authToken');
  }

  /**
   * Set auth token directly (for test setup)
   */
  async setAuthToken(token: string) {
    await this.setLocalStorageItem('authToken', token);
  }
  
  /**
   * Clear all auth data (for test cleanup)
   */
  async clearAuthData() {
    await this.page.evaluate(() => {
      localStorage.removeItem('authToken');
      localStorage.removeItem('refreshToken');
      localStorage.removeItem('userRole');
      sessionStorage.clear();
    });
  }
  
  /**
   * Check for session expiry handling
   */
  async isSessionExpired(): Promise<boolean> {
    const hasExpiredMessage = await this.page.locator('[data-testid="session-expired-message"]').isVisible();
    const isOnLoginPage = this.page.url().includes('/login');
    return hasExpiredMessage || isOnLoginPage;
  }
}