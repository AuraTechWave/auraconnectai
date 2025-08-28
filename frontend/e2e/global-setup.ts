import { chromium, FullConfig } from '@playwright/test';
import { TEST_CONFIG } from './config/test-config';
import { LoginPage } from './pages/login.page';
import * as fs from 'fs';
import * as path from 'path';

/**
 * Global setup that runs once before all tests
 * Creates authenticated storage states for different user roles
 */
async function globalSetup(config: FullConfig) {
  console.log('🔧 Running global setup...');
  
  // Ensure auth-states directory exists
  const authStatesDir = path.join(__dirname, 'auth-states');
  if (!fs.existsSync(authStatesDir)) {
    fs.mkdirSync(authStatesDir, { recursive: true });
  }
  
  // Skip storage state creation if feature flag is disabled
  if (TEST_CONFIG.FEATURES.USE_STORAGE_STATE === false) {
    console.log('⚠️  Storage state creation disabled via E2E_USE_STORAGE_STATE=false');
    return;
  }
  
  const browser = await chromium.launch();
  
  // Create storage states for each user role
  const userRoles = ['CUSTOMER', 'STAFF', 'ADMIN', 'MANAGER'] as const;
  
  for (const role of userRoles) {
    console.log(`  📝 Creating storage state for ${role}...`);
    
    try {
      const context = await browser.newContext({
        baseURL: TEST_CONFIG.getTenantBaseUrl(),
        extraHTTPHeaders: {
          ...TEST_CONFIG.TEST_TENANT.headers
        }
      });
      
      const page = await context.newPage();
      const loginPage = new LoginPage(page);
      
      // Navigate to login page
      await loginPage.gotoLoginPage();
      
      // Get user credentials
      const user = TEST_CONFIG.TEST_USERS[role];
      
      // Perform login
      await loginPage.login(user.email, user.password);
      
      // Wait for successful authentication
      await loginPage.waitForSuccessfulLogin();
      
      // Save storage state (includes cookies, localStorage, sessionStorage)
      const storageStatePath = path.join(authStatesDir, `${role.toLowerCase()}.json`);
      await context.storageState({ path: storageStatePath });
      
      console.log(`    ✅ Storage state saved to ${storageStatePath}`);
      
      // Cleanup
      await page.close();
      await context.close();
      
    } catch (error) {
      console.error(`    ❌ Failed to create storage state for ${role}:`, error);
      
      // In CI, fail the setup if authentication fails
      if (process.env.CI) {
        await browser.close();
        throw new Error(`Failed to authenticate ${role} user: ${error}`);
      }
    }
  }
  
  await browser.close();
  console.log('✅ Global setup completed\n');
}

export default globalSetup;