import '@testing-library/jest-dom';

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};
global.localStorage = localStorageMock;

// Mock sessionStorage
const sessionStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};
global.sessionStorage = sessionStorageMock;

// Mock fetch
global.fetch = jest.fn();

// Mock WebSocket
global.WebSocket = jest.fn(() => ({
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
  send: jest.fn(),
  close: jest.fn(),
}));

// Mock IntersectionObserver
global.IntersectionObserver = jest.fn(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));

// Mock ResizeObserver
global.ResizeObserver = jest.fn(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));

// Suppress console warnings in tests
const originalError = console.error;
beforeAll(() => {
  console.error = (...args) => {
    if (
      typeof args[0] === 'string' &&
      args[0].includes('ReactDOM.render')
    ) {
      return;
    }
    originalError.call(console, ...args);
  };
});

afterAll(() => {
  console.error = originalError;
});

// Mock customerApi
jest.mock('./services/customerApi.ts', () => ({
  __esModule: true,
  default: {
    login: jest.fn((email, password) => {
      if (email === 'john@example.com' && password === 'password123') {
        return Promise.resolve({
          success: true,
          token: 'test-token',
          user: {
            id: 2,
            name: 'Jane Doe',
            email: 'jane@example.com',
            role: 'customer'
          }
        });
      } else if (email === 'bob@example.com' && password === 'validtoken') {
        return Promise.resolve({
          success: true,
          token: 'valid-session-token',
          user: {
            id: 3,
            name: 'Bob Smith',
            email: 'bob@example.com',
            role: 'staff'
          }
        });
      }
      return Promise.reject(new Error('Invalid credentials'));
    }),
    logout: jest.fn().mockResolvedValue({ success: true }),
    getProfile: jest.fn().mockResolvedValue({
      id: 1,
      name: 'John Doe',
      email: 'john@example.com',
      role: 'manager'
    }),
    validateSession: jest.fn((token) => {
      if (token === 'valid-session-token') {
        return Promise.resolve({
          valid: true,
          user: {
            id: 3,
            name: 'Bob Smith',
            email: 'bob@example.com',
            role: 'staff'
          }
        });
      }
      return Promise.reject(new Error('Invalid session'));
    }),
    getTenants: jest.fn().mockResolvedValue([{
      id: 'tenant-123',
      name: 'Restaurant ABC'
    }])
  }
}));

// Mock tenant service
jest.mock('./services/tenantService', () => ({
  __esModule: true,
  tenantService: {
    getCurrentTenant: jest.fn(() => ({
      id: 'tenant-123',
      name: 'Restaurant ABC'
    })),
    setCurrentTenant: jest.fn(),
    validateTenantAccess: jest.fn().mockResolvedValue(true)
  }
}));