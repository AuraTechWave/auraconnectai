// Load environment variables with validation
const requiredEnvVars = [
  'E2E_CUSTOMER_EMAIL',
  'E2E_CUSTOMER_PASSWORD',
  'E2E_STAFF_EMAIL',
  'E2E_STAFF_PASSWORD',
  'E2E_ADMIN_EMAIL',
  'E2E_ADMIN_PASSWORD',
  'E2E_MANAGER_EMAIL',
  'E2E_MANAGER_PASSWORD'
];

// Validate required environment variables in CI
if (process.env.CI) {
  const missingVars = requiredEnvVars.filter(v => !process.env[v]);
  if (missingVars.length > 0) {
    throw new Error(`Missing required E2E environment variables: ${missingVars.join(', ')}`);
  }
}

export const TEST_CONFIG = {
  // API Configuration - aligned with UI base URL for same-origin
  API_BASE_URL: process.env.E2E_API_BASE_URL || process.env.E2E_BASE_URL || 'http://localhost:8000',
  
  // Test User Credentials - from environment variables
  TEST_USERS: {
    CUSTOMER: {
      email: process.env.E2E_CUSTOMER_EMAIL || 'test.customer@example.com',
      password: process.env.E2E_CUSTOMER_PASSWORD || 'TestPass123!',
      role: 'customer'
    },
    STAFF: {
      email: process.env.E2E_STAFF_EMAIL || 'test.staff@example.com',
      password: process.env.E2E_STAFF_PASSWORD || 'TestPass123!',
      role: 'staff'
    },
    ADMIN: {
      email: process.env.E2E_ADMIN_EMAIL || 'test.admin@example.com',
      password: process.env.E2E_ADMIN_PASSWORD || 'TestPass123!',
      role: 'admin'
    },
    MANAGER: {
      email: process.env.E2E_MANAGER_EMAIL || 'test.manager@example.com',
      password: process.env.E2E_MANAGER_PASSWORD || 'TestPass123!',
      role: 'manager'
    }
  },
  
  // Test Restaurant/Tenant with subdomain support
  TEST_TENANT: {
    id: process.env.E2E_TENANT_ID || 'test-restaurant-001',
    name: process.env.E2E_TENANT_NAME || 'Test Restaurant',
    subdomain: process.env.E2E_TENANT_SUBDOMAIN || 'test',
    domain: process.env.E2E_TENANT_DOMAIN || 'localhost',
    headers: {
      'X-Tenant-ID': process.env.E2E_TENANT_ID || 'test-restaurant-001'
    }
  },
  
  // Timeouts
  TIMEOUTS: {
    API: Number(process.env.E2E_API_TIMEOUT) || 30000,
    UI: Number(process.env.E2E_UI_TIMEOUT) || 15000,
    NAVIGATION: Number(process.env.E2E_NAV_TIMEOUT) || 30000
  },
  
  // Feature Flags
  FEATURES: {
    SKIP_CLEANUP: process.env.E2E_SKIP_CLEANUP === 'true',
    VERBOSE_LOGGING: process.env.E2E_VERBOSE === 'true',
    USE_STORAGE_STATE: process.env.E2E_USE_STORAGE_STATE !== 'false' // default true
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
    PAYMENT_METHODS: {
      CREDIT_CARD: {
        number: '4242424242424242',
        expiry: '12/25',
        cvc: '123',
        name: 'Test Customer'
      }
    }
  },
  
  // Helper method to get tenant-aware base URL
  getTenantBaseUrl(): string {
    const protocol = process.env.E2E_USE_HTTPS === 'true' ? 'https' : 'http';
    const port = process.env.E2E_PORT || '3000';
    const { subdomain, domain } = this.TEST_TENANT;
    
    if (subdomain && subdomain !== 'localhost') {
      return `${protocol}://${subdomain}.${domain}:${port}`;
    }
    return `${protocol}://${domain}:${port}`;
  }
};