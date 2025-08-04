import { renderHook, act, waitFor } from '@testing-library/react';
import { useAuthStore } from '../authStore';
import api from '../../services/api';

// Mock the api module
jest.mock('../../services/api', () => ({
  default: {
    login: jest.fn(),
    register: jest.fn(),
    logout: jest.fn(),
    getProfile: jest.fn(),
  },
}));

const mockCustomer = {
  id: 1,
  email: 'test@example.com',
  first_name: 'Test',
  last_name: 'User',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

describe('authStore', () => {
  beforeEach(() => {
    // Clear localStorage
    localStorage.clear();
    // Reset store
    const { result } = renderHook(() => useAuthStore());
    act(() => {
      result.current.logout();
    });
    // Clear mocks
    jest.clearAllMocks();
  });

  test('should initialize with default state', () => {
    const { result } = renderHook(() => useAuthStore());

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.customer).toBeNull();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  test('should login successfully', async () => {
    const { result } = renderHook(() => useAuthStore());
    
    (api.login as jest.Mock).mockResolvedValueOnce({
      access_token: 'mock-token',
      customer: mockCustomer,
    });

    await act(async () => {
      await result.current.login('test@example.com', 'password123');
    });

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.customer).toEqual(mockCustomer);
    expect(result.current.error).toBeNull();
    expect(localStorage.getItem('customerToken')).toBe('mock-token');
  });

  test('should handle login error', async () => {
    const { result } = renderHook(() => useAuthStore());
    
    (api.login as jest.Mock).mockRejectedValueOnce(new Error('Invalid credentials'));

    await act(async () => {
      try {
        await result.current.login('test@example.com', 'wrong-password');
      } catch (error) {
        // Expected error
      }
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.customer).toBeNull();
    expect(result.current.error).toBe('Invalid credentials');
  });

  test('should register successfully', async () => {
    const { result } = renderHook(() => useAuthStore());
    
    const registerData = {
      email: 'new@example.com',
      password: 'password123',
      first_name: 'New',
      last_name: 'User',
      phone: '1234567890',
    };

    (api.register as jest.Mock).mockResolvedValueOnce({
      access_token: 'mock-token',
      customer: { ...mockCustomer, ...registerData },
    });

    await act(async () => {
      await result.current.register(registerData);
    });

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.customer?.email).toBe('new@example.com');
    expect(localStorage.getItem('customerToken')).toBe('mock-token');
  });

  test('should logout successfully', async () => {
    const { result } = renderHook(() => useAuthStore());
    
    // First login
    (api.login as jest.Mock).mockResolvedValueOnce({
      access_token: 'mock-token',
      customer: mockCustomer,
    });

    await act(async () => {
      await result.current.login('test@example.com', 'password123');
    });

    expect(result.current.isAuthenticated).toBe(true);

    // Then logout
    await act(async () => {
      await result.current.logout();
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.customer).toBeNull();
    expect(localStorage.getItem('customerToken')).toBeNull();
  });

  test('should clear error', () => {
    const { result } = renderHook(() => useAuthStore());
    
    act(() => {
      // Set an error first
      result.current.error = 'Test error';
    });

    expect(result.current.error).toBe('Test error');

    act(() => {
      result.current.clearError();
    });

    expect(result.current.error).toBeNull();
  });

  test('should handle loading state', async () => {
    const { result } = renderHook(() => useAuthStore());
    
    let resolveLogin: (value: any) => void;
    const loginPromise = new Promise((resolve) => {
      resolveLogin = resolve;
    });

    (api.login as jest.Mock).mockReturnValueOnce(loginPromise);

    act(() => {
      result.current.login('test@example.com', 'password123');
    });

    expect(result.current.isLoading).toBe(true);

    await act(async () => {
      resolveLogin!({
        access_token: 'mock-token',
        customer: mockCustomer,
      });
      await loginPromise;
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });
});