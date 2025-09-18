// Example test configuration file
// Copy this file to test-config.ts and update with your test values
// DO NOT commit test-config.ts with real credentials

export const TEST_CONFIG = {
  // API Configuration
  API_BASE_URL: process.env.E2E_API_BASE_URL || 'http://localhost:8000',
  
  // Test User Credentials - MUST be set via environment variables
  TEST_USERS: {
    CUSTOMER: {
      email: process.env.E2E_CUSTOMER_EMAIL || 'customer@example.com',
      password: process.env.E2E_CUSTOMER_PASSWORD || 'ChangeMe123!',
      role: 'customer'
    },
    STAFF: {
      email: process.env.E2E_STAFF_EMAIL || 'staff@example.com',
      password: process.env.E2E_STAFF_PASSWORD || 'ChangeMe123!',
      role: 'staff'
    },
    ADMIN: {
      email: process.env.E2E_ADMIN_EMAIL || 'admin@example.com',
      password: process.env.E2E_ADMIN_PASSWORD || 'ChangeMe123!',
      role: 'admin'
    },
    MANAGER: {
      email: process.env.E2E_MANAGER_EMAIL || 'manager@example.com',
      password: process.env.E2E_MANAGER_PASSWORD || 'ChangeMe123!',
      role: 'manager'
    }
  },
  
  // Test Restaurant/Tenant Configuration
  TEST_TENANT: {
    id: process.env.E2E_TENANT_ID || 'test-tenant',
    name: process.env.E2E_TENANT_NAME || 'Test Restaurant',
    subdomain: process.env.E2E_TENANT_SUBDOMAIN || 'test',
    domain: process.env.E2E_TENANT_DOMAIN || 'localhost'
  },
  
  // Timeouts
  TIMEOUTS: {
    API: Number(process.env.E2E_API_TIMEOUT) || 30000,
    UI: Number(process.env.E2E_UI_TIMEOUT) || 15000,
    NAVIGATION: Number(process.env.E2E_NAV_TIMEOUT) || 30000
  },
  
  // Test Data
  TEST_DATA: {
    MENU_ITEMS: [
      {
        id: 'item-001',
        name: 'Classic Burger',
        price: 12.99,
        category: 'Main Courses'
      },
      {
        id: 'item-002',
        name: 'Caesar Salad',
        price: 8.99,
        category: 'Salads'
      },
      {
        id: 'item-003',
        name: 'Chocolate Cake',
        price: 6.99,
        category: 'Desserts'
      }
    ],
    // Payment test data should never include real card numbers
    PAYMENT_METHODS: {
      CREDIT_CARD: {
        number: '4242424242424242', // Stripe test card
        expiry: '12/25',
        cvc: '123',
        name: 'Test Customer'
      }
    }
  },
  
  // Feature Flags
  FEATURES: {
    SKIP_CLEANUP: process.env.E2E_SKIP_CLEANUP === 'true',
    VERBOSE_LOGGING: process.env.E2E_VERBOSE === 'true',
    USE_MOCK_API: process.env.E2E_USE_MOCK_API === 'true'
  }
};