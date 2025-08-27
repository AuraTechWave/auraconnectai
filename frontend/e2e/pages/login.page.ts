import { Page } from '@playwright/test';
import { BasePage } from './base.page';

export class LoginPage extends BasePage {
  // Selectors
  private readonly emailInput = '[data-testid="login-email"], #email, input[type="email"]';
  private readonly passwordInput = '[data-testid="login-password"], #password, input[type="password"]';
  private readonly loginButton = '[data-testid="login-submit"], button[type="submit"]:has-text("Login"), button:has-text("Sign In")';
  private readonly errorMessage = '[data-testid="login-error"], .error-message, .alert-danger';
  private readonly forgotPasswordLink = 'a:has-text("Forgot password"), a:has-text("Forgot Password?")';
  private readonly signUpLink = 'a:has-text("Sign up"), a:has-text("Create account")';
  private readonly rememberMeCheckbox = '[data-testid="remember-me"], input[type="checkbox"][name="remember"]';
  private readonly logoutButton = '[data-testid="logout-button"], button:has-text("Logout"), button:has-text("Sign Out")';

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
   * Wait for successful login
   */
  async waitForSuccessfulLogin() {
    // Wait for auth token to be set
    await this.page.waitForFunction(
      () => localStorage.getItem('authToken') !== null,
      { timeout: 10000 }
    );
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
}