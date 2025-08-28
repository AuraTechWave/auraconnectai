import { defineConfig, devices } from '@playwright/test';
import * as dotenv from 'dotenv';
import * as path from 'path';

/**
 * Load environment variables from .env.e2e file
 * https://github.com/motdotla/dotenv
 */
const envPath = process.env.DOTENV_PATH || '.env.e2e';
dotenv.config({ path: path.resolve(__dirname, envPath) });

/**
 * See https://playwright.dev/docs/test-configuration.
 */
export default defineConfig({
  testDir: './e2e',
  /* Global setup and teardown */
  globalSetup: path.resolve(__dirname, './e2e/global-setup.ts'),
  globalTeardown: path.resolve(__dirname, './e2e/global-teardown.ts'),
  /* Run tests in files in parallel */
  fullyParallel: true,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Opt out of parallel tests on CI. */
  workers: process.env.CI ? 2 : undefined,
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: [
    ['html', { open: 'never', outputFolder: 'playwright-report' }],
    ['json', { outputFile: 'test-results.json' }],
    ['list'],
    ...(process.env.CI ? [['github']] : [])
  ] as any,
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Base URL to use in actions like `await page.goto('/')`. */
    baseURL: process.env.PLAYWRIGHT_TEST_BASE_URL || 'http://localhost:3000',

    /* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
    trace: 'on-first-retry',

    /* Capture screenshot on failure */
    screenshot: 'only-on-failure',

    /* Capture video on failure */
    video: 'retain-on-failure',

    /* Maximum time for each navigation action */
    navigationTimeout: 30000,

    /* Maximum time for each action */
    actionTimeout: 15000,
  },

  /* Configure projects for major browsers with storage states */
  projects: [
    // Setup project to create storage states
    {
      name: 'setup',
      testMatch: /global-setup\.ts/,
    },
    
    // Customer role tests
    {
      name: 'chromium-customer',
      use: { 
        ...devices['Desktop Chrome'],
        storageState: './e2e/auth-states/customer.json',
      },
      dependencies: process.env.E2E_USE_STORAGE_STATE !== 'false' ? ['setup'] : [],
    },
    
    // Staff role tests
    {
      name: 'chromium-staff',
      use: { 
        ...devices['Desktop Chrome'],
        storageState: './e2e/auth-states/staff.json',
      },
      dependencies: process.env.E2E_USE_STORAGE_STATE !== 'false' ? ['setup'] : [],
    },
    
    // Admin role tests
    {
      name: 'chromium-admin',
      use: { 
        ...devices['Desktop Chrome'],
        storageState: './e2e/auth-states/admin.json',
      },
      dependencies: process.env.E2E_USE_STORAGE_STATE !== 'false' ? ['setup'] : [],
    },
    
    // Default chromium without auth
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },

    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },

    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },

    /* Test against mobile viewports. */
    {
      name: 'mobile-chrome',
      use: { ...devices['Pixel 5'] },
    },
    {
      name: 'mobile-safari',
      use: { ...devices['iPhone 12'] },
    },

    /* Test against branded browsers. */
    // {
    //   name: 'Microsoft Edge',
    //   use: { ...devices['Desktop Edge'], channel: 'msedge' },
    // },
    // {
    //   name: 'Google Chrome',
    //   use: { ...devices['Desktop Chrome'], channel: 'chrome' },
    // },
  ],

  /* Run your local dev server before starting the tests */
  webServer: process.env.CI ? undefined : {
    command: 'npm start',
    url: process.env.E2E_BASE_URL || 'http://localhost:3000',
    reuseExistingServer: true,
    timeout: 120 * 1000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
});