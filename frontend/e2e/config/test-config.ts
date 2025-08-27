export const TEST_CONFIG = {
  // API Configuration
  API_BASE_URL: process.env.API_BASE_URL || 'http://localhost:8000',
  
  // Test User Credentials
  TEST_USERS: {
    CUSTOMER: {
      email: 'test.customer@auraconnect.ai',
      password: 'TestCustomer123!',
      role: 'customer'
    },
    STAFF: {
      email: 'test.staff@auraconnect.ai', 
      password: 'TestStaff123!',
      role: 'staff'
    },
    ADMIN: {
      email: 'test.admin@auraconnect.ai',
      password: 'TestAdmin123!',
      role: 'admin'
    },
    MANAGER: {
      email: 'test.manager@auraconnect.ai',
      password: 'TestManager123!',
      role: 'manager'
    }
  },
  
  // Test Restaurant/Tenant
  TEST_TENANT: {
    id: 'test-restaurant-001',
    name: 'Test Restaurant',
    domain: 'test.auraconnect.ai'
  },
  
  // Timeouts
  TIMEOUTS: {
    API: 30000,
    UI: 15000,
    NAVIGATION: 30000
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
  }
};