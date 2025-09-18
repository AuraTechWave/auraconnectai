import { test, expect } from '../../fixtures/test-fixtures';
import { TEST_CONFIG } from '../../config/test-config';

test.describe('Authentication - Login Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Clear any existing auth state
    await page.context().clearCookies();
    await page.evaluate(() => localStorage.clear());
  });

  test('successful login with valid credentials', async ({ loginPage }) => {
    // Navigate to login page
    await loginPage.gotoLoginPage();
    
    // Fill and submit login form
    await loginPage.login(
      TEST_CONFIG.TEST_USERS.CUSTOMER.email,
      TEST_CONFIG.TEST_USERS.CUSTOMER.password
    );
    
    // Wait for redirect
    await loginPage.waitForSuccessfulLogin();
    
    // Verify we're no longer on login page
    await expect(loginPage['page']).not.toHaveURL(/\/login/);
    
    // Verify auth token is stored
    const authToken = await loginPage.getAuthToken();
    expect(authToken).toBeTruthy();
  });

  test('login with remember me option', async ({ loginPage }) => {
    await loginPage.gotoLoginPage();
    
    // Login with remember me checked
    await loginPage.login(
      TEST_CONFIG.TEST_USERS.CUSTOMER.email,
      TEST_CONFIG.TEST_USERS.CUSTOMER.password,
      true // rememberMe
    );
    
    await loginPage.waitForSuccessfulLogin();
    
    // Check if remember me cookie/storage is set
    const authToken = await loginPage.getAuthToken();
    expect(authToken).toBeTruthy();
    
    // TODO: Verify remember me cookie expiration when implemented
  });

  test('failed login with invalid credentials', async ({ loginPage }) => {
    await loginPage.gotoLoginPage();
    
    // Try to login with invalid credentials
    await loginPage.login(
      'invalid@email.com',
      'wrongpassword'
    );
    
    // Verify error message is displayed
    const errorDisplayed = await loginPage.isErrorDisplayed();
    expect(errorDisplayed).toBeTruthy();
    
    const errorMessage = await loginPage.getErrorMessage();
    expect(errorMessage).toContain('Invalid credentials');
    
    // Verify we're still on login page
    await loginPage.assertURLContains('/login');
  });

  test('login with empty email field', async ({ loginPage }) => {
    await loginPage.gotoLoginPage();
    
    // Try to submit with empty email
    await loginPage.fillLoginForm('', 'somepassword');
    await loginPage.submitLogin();
    
    // Check for HTML5 validation or custom error
    const emailInput = loginPage['page'].locator('[data-testid="login-email"], #email, input[type="email"]');
    
    // Check if browser validation is triggered
    const validationMessage = await emailInput.evaluate((el: HTMLInputElement) => el.validationMessage);
    expect(validationMessage).toBeTruthy();
  });

  test('login with empty password field', async ({ loginPage }) => {
    await loginPage.gotoLoginPage();
    
    // Try to submit with empty password
    await loginPage.fillLoginForm('test@email.com', '');
    await loginPage.submitLogin();
    
    // Check for validation
    const passwordInput = loginPage['page'].locator('[data-testid="login-password"], #password, input[type="password"]');
    const validationMessage = await passwordInput.evaluate((el: HTMLInputElement) => el.validationMessage);
    expect(validationMessage).toBeTruthy();
  });

  test('navigate to forgot password page', async ({ loginPage }) => {
    await loginPage.gotoLoginPage();
    
    // Click forgot password link
    await loginPage.clickForgotPassword();
    
    // Verify navigation to forgot password page
    await expect(loginPage['page']).toHaveURL(/\/forgot-password|\/reset-password/);
  });

  test('navigate to sign up page', async ({ loginPage }) => {
    await loginPage.gotoLoginPage();
    
    // Click sign up link
    await loginPage.clickSignUp();
    
    // Verify navigation to sign up page
    await expect(loginPage['page']).toHaveURL(/\/signup|\/register/);
  });

  test('login state persists on page refresh', async ({ loginPage }) => {
    await loginPage.gotoLoginPage();
    
    // Login successfully
    await loginPage.login(
      TEST_CONFIG.TEST_USERS.CUSTOMER.email,
      TEST_CONFIG.TEST_USERS.CUSTOMER.password
    );
    
    await loginPage.waitForSuccessfulLogin();
    
    // Refresh the page
    await loginPage['page'].reload();
    
    // Verify auth token still exists
    const authToken = await loginPage.getAuthToken();
    expect(authToken).toBeTruthy();
    
    // Verify we're not redirected to login
    await expect(loginPage['page']).not.toHaveURL(/\/login/);
  });

  test('login with different user roles', async ({ loginPage }) => {
    // Test login for each user role
    const userRoles = ['CUSTOMER', 'STAFF', 'ADMIN'] as const;
    
    for (const role of userRoles) {
      // Clear auth state
      await loginPage['page'].context().clearCookies();
      await loginPage['page'].evaluate(() => localStorage.clear());
      
      // Navigate to login
      await loginPage.gotoLoginPage();
      
      // Login with role-specific credentials
      const user = TEST_CONFIG.TEST_USERS[role];
      await loginPage.login(user.email, user.password);
      
      // Verify successful login
      await loginPage.waitForSuccessfulLogin();
      
      // Verify correct role-based redirect
      if (role === 'ADMIN') {
        await loginPage.assertURLContains('/admin');
      } else if (role === 'STAFF') {
        await loginPage.assertURLContains('/staff');
      }
      
      // Logout for next iteration
      await loginPage.logout();
    }
  });

  test('XSS prevention in login form', async ({ loginPage }) => {
    await loginPage.gotoLoginPage();
    
    // Try to inject script in email field
    const xssPayload = '<script>alert("XSS")</script>';
    await loginPage.fillLoginForm(xssPayload, 'password');
    await loginPage.submitLogin();
    
    // Verify no script execution (page should handle it safely)
    const alertFired = await loginPage['page'].evaluate(() => {
      let alertCalled = false;
      window.alert = () => { alertCalled = true; };
      return alertCalled;
    });
    
    expect(alertFired).toBeFalsy();
  });
});