import { defineConfig, devices } from '@playwright/test';

/**
 * Read environment variables from file.
 * https://github.com/motdotla/dotenv
 */
// require('dotenv').config();

/**
 * See https://playwright.dev/docs/test-configuration.
 */
export default defineConfig({
  testDir: './e2e',
  /* Global setup and teardown - commented out for now */
  // globalSetup: path.resolve(__dirname, './e2e/global-setup.ts'),
  // globalTeardown: path.resolve(__dirname, './e2e/global-teardown.ts'),
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

  /* Configure projects for major browsers */
  projects: [
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
  webServer: process.env.SKIP_WEBSERVER === 'true' ? undefined : {
    command: process.env.CI 
      ? 'TSC_COMPILE_ON_ERROR=true ESLINT_NO_DEV_ERRORS=true CI=true npm start' 
      : 'TSC_COMPILE_ON_ERROR=true ESLINT_NO_DEV_ERRORS=true npm start',
    url: process.env.E2E_BASE_URL || 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: process.env.CI ? 180 * 1000 : 120 * 1000,
    stdout: 'pipe',
    stderr: 'pipe',
    env: {
      NODE_ENV: 'test',
      REACT_APP_API_URL: process.env.E2E_API_BASE_URL || 'http://localhost:8000',
      REACT_APP_ENVIRONMENT: 'test',
      REACT_APP_API_VERSION: 'v1',
      REACT_APP_WS_URL: 'ws://localhost:8000/ws',
      REACT_APP_ENABLE_ANALYTICS: 'false',
      REACT_APP_ENABLE_NOTIFICATIONS: 'false',
      REACT_APP_ENABLE_AI_RECOMMENDATIONS: 'false',
      REACT_APP_DEFAULT_THEME: 'light',
      REACT_APP_ENABLE_DARK_MODE: 'true',
      REACT_APP_DEFAULT_LANGUAGE: 'en',
      REACT_APP_SUPPORTED_LANGUAGES: 'en',
      TSC_COMPILE_ON_ERROR: 'true',
      ESLINT_NO_DEV_ERRORS: 'true',
      GENERATE_SOURCEMAP: 'false',
      SKIP_PREFLIGHT_CHECK: 'true',
      CI: process.env.CI || 'false'
    }
  },
});