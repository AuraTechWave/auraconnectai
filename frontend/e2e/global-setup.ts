import { FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  console.log('Global E2E setup - minimal setup for now');
  // Skip complex setup that requires working app
  return;
}

export default globalSetup;