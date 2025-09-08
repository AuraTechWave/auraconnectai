import { FullConfig } from '@playwright/test';

async function globalTeardown(config: FullConfig) {
  console.log('Global E2E teardown');
  // Cleanup if needed
  return;
}

export default globalTeardown;