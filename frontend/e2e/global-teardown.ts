import { FullConfig } from '@playwright/test';
import { TEST_CONFIG } from './config/test-config';
import { createAPIContext } from './utils/api-helpers';

/**
 * Global teardown that runs once after all tests
 * Performs cleanup of test data if needed
 */
async function globalTeardown(config: FullConfig) {
  console.log('🧹 Running global teardown...');
  
  // Skip cleanup if feature flag is set
  if (TEST_CONFIG.FEATURES.SKIP_CLEANUP) {
    console.log('⚠️  Cleanup skipped via E2E_SKIP_CLEANUP=true');
    return;
  }
  
  try {
    // Create API context for cleanup
    const { apiContext, apiHelpers } = await createAPIContext();
    
    // TODO: Add cleanup logic here once backend provides test data cleanup endpoints
    // Examples:
    // - Delete test users created during tests
    // - Clean up test orders
    // - Remove test reservations
    // - Reset test tenant data
    
    // For now, log what would be cleaned up
    console.log('  📝 Cleanup tasks:');
    console.log('    - Test users cleanup (pending backend support)');
    console.log('    - Test orders cleanup (pending backend support)');
    console.log('    - Test reservations cleanup (pending backend support)');
    
    // Dispose of the API context
    await apiContext.dispose();
    
  } catch (error) {
    console.error('❌ Teardown error:', error);
    // Don't fail the test run due to cleanup errors
  }
  
  console.log('✅ Global teardown completed\n');
}

export default globalTeardown;