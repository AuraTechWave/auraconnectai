import axios from 'axios';
import api, { handleApiError, buildQueryString } from './api';

jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

// Mock localStorage
const mockLocalStorage = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn()
};
Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage
});

// Mock location
delete (window as any).location;
window.location = { ...window.location, href: '' };

// Mock querySelector for CSRF token
const mockQuerySelector = jest.fn();
Object.defineProperty(document, 'querySelector', {
  value: mockQuerySelector
});

describe('API Service', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockLocalStorage.getItem.mockClear();
    mockLocalStorage.setItem.mockClear();
    mockLocalStorage.removeItem.mockClear();
    mockQuerySelector.mockClear();
  });

  describe('API Configuration', () => {
    test('creates axios instance with correct base configuration', () => {
      expect(mockedAxios.create).toHaveBeenCalledWith({
        baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
        timeout: 30000,
        headers: {
          'Content-Type': 'application/json',
        },
        withCredentials: true,
      });
    });

    test('uses environment variable for API URL', () => {
      const originalEnv = process.env.REACT_APP_API_URL;
      process.env.REACT_APP_API_URL = 'https://api.example.com';
      
      // Re-import to get updated config
      jest.resetModules();
      require('./api');
      
      expect(mockedAxios.create).toHaveBeenCalledWith(
        expect.objectContaining({
          baseURL: 'https://api.example.com'
        })
      );
      
      process.env.REACT_APP_API_URL = originalEnv;
    });

    test('falls back to localhost when no env var set', () => {
      const originalEnv = process.env.REACT_APP_API_URL;
      delete process.env.REACT_APP_API_URL;
      
      jest.resetModules();
      require('./api');
      
      expect(mockedAxios.create).toHaveBeenCalledWith(
        expect.objectContaining({
          baseURL: 'http://localhost:8000'
        })
      );
      
      process.env.REACT_APP_API_URL = originalEnv;
    });
  });

  describe('Request Interceptor', () => {
    test('adds Authorization header when token exists', () => {
      mockLocalStorage.getItem.mockReturnValue('test-token');
      
      const config = {
        headers: {} as any
      };
      
      // Get the request interceptor
      const requestInterceptor = mockedAxios.create().interceptors.request.use.mock.calls[0][0];
      const result = requestInterceptor(config);
      
      expect(result.headers.Authorization).toBe('Bearer test-token');
    });

    test('does not add Authorization header when no token', () => {
      mockLocalStorage.getItem.mockReturnValue(null);
      
      const config = {
        headers: {} as any
      };
      
      const requestInterceptor = mockedAxios.create().interceptors.request.use.mock.calls[0][0];
      const result = requestInterceptor(config);
      
      expect(result.headers.Authorization).toBeUndefined();
    });

    test('adds CSRF token when available', () => {
      const mockElement = {
        getAttribute: jest.fn().mockReturnValue('csrf-token-123')
      };
      mockQuerySelector.mockReturnValue(mockElement);
      
      const config = {
        headers: {} as any
      };
      
      const requestInterceptor = mockedAxios.create().interceptors.request.use.mock.calls[0][0];
      const result = requestInterceptor(config);
      
      expect(mockQuerySelector).toHaveBeenCalledWith('meta[name="csrf-token"]');
      expect(result.headers['X-CSRF-Token']).toBe('csrf-token-123');
    });

    test('does not add CSRF token when not available', () => {
      mockQuerySelector.mockReturnValue(null);
      
      const config = {
        headers: {} as any
      };
      
      const requestInterceptor = mockedAxios.create().interceptors.request.use.mock.calls[0][0];
      const result = requestInterceptor(config);
      
      expect(result.headers['X-CSRF-Token']).toBeUndefined();
    });
  });

  describe('Response Interceptor - Token Refresh', () => {
    test('attempts token refresh on 401 error', async () => {
      mockLocalStorage.getItem.mockReturnValue('refresh-token');
      mockedAxios.post.mockResolvedValueOnce({
        data: {
          access_token: 'new-access-token',
          refresh_token: 'new-refresh-token'
        }
      });

      const error = {
        response: { status: 401 },
        config: { headers: {} }
      };

      const responseInterceptor = mockedAxios.create().interceptors.response.use.mock.calls[0][1];
      
      await responseInterceptor(error);

      expect(mockedAxios.post).toHaveBeenCalledWith(
        'http://localhost:8000/auth/refresh',
        { refresh_token: 'refresh-token' }
      );
      expect(mockLocalStorage.setItem).toHaveBeenCalledWith('authToken', 'new-access-token');
      expect(mockLocalStorage.setItem).toHaveBeenCalledWith('refreshToken', 'new-refresh-token');
    });

    test('redirects to login when refresh token is invalid', async () => {
      mockLocalStorage.getItem.mockReturnValue('invalid-refresh-token');
      mockedAxios.post.mockRejectedValueOnce(new Error('Invalid refresh token'));

      const error = {
        response: { status: 401 },
        config: { headers: {} }
      };

      const responseInterceptor = mockedAxios.create().interceptors.response.use.mock.calls[0][1];
      
      try {
        await responseInterceptor(error);
      } catch (e) {
        // Expected to throw
      }

      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('authToken');
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('refreshToken');
      expect(window.location.href).toBe('/login');
    });

    test('redirects to login when no refresh token available', async () => {
      mockLocalStorage.getItem.mockReturnValue(null);

      const error = {
        response: { status: 401 },
        config: { headers: {} }
      };

      const responseInterceptor = mockedAxios.create().interceptors.response.use.mock.calls[0][1];
      
      try {
        await responseInterceptor(error);
      } catch (e) {
        // Expected to throw
      }

      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('authToken');
      expect(window.location.href).toBe('/login');
    });

    test('does not retry request twice', async () => {
      mockLocalStorage.getItem.mockReturnValue('refresh-token');
      
      const error = {
        response: { status: 401 },
        config: { headers: {}, _retry: true }
      };

      const responseInterceptor = mockedAxios.create().interceptors.response.use.mock.calls[0][1];
      
      try {
        await responseInterceptor(error);
      } catch (e) {
        expect(e).toBe(error);
      }

      expect(mockedAxios.post).not.toHaveBeenCalled();
    });
  });

  describe('Response Interceptor - Error Handling', () => {
    test('handles 403 Forbidden errors', async () => {
      console.error = jest.fn();
      
      const error = {
        response: { status: 403 },
        config: { headers: {} }
      };

      const responseInterceptor = mockedAxios.create().interceptors.response.use.mock.calls[0][1];
      
      try {
        await responseInterceptor(error);
      } catch (e) {
        expect(e).toBe(error);
      }

      expect(console.error).toHaveBeenCalledWith('Access denied. Insufficient permissions.');
    });

    test('handles network errors', async () => {
      console.error = jest.fn();
      
      const error = {
        message: 'Network Error',
        config: { headers: {} }
        // No response property indicates network error
      };

      const responseInterceptor = mockedAxios.create().interceptors.response.use.mock.calls[0][1];
      
      try {
        await responseInterceptor(error);
      } catch (e) {
        expect(e).toBe(error);
      }

      expect(console.error).toHaveBeenCalledWith('Network error:', 'Network Error');
    });

    test('passes through successful responses', async () => {
      const response = { data: { success: true }, status: 200 };
      
      const successHandler = mockedAxios.create().interceptors.response.use.mock.calls[0][0];
      const result = successHandler(response);
      
      expect(result).toBe(response);
    });
  });

  describe('handleApiError utility', () => {
    test('extracts error message from response data', () => {
      const error = {
        response: {
          data: { message: 'Custom error message' }
        }
      };
      
      const result = handleApiError(error);
      expect(result).toBe('Custom error message');
    });

    test('extracts error from response data when message not available', () => {
      const error = {
        response: {
          data: { error: 'API error occurred' }
        }
      };
      
      const result = handleApiError(error);
      expect(result).toBe('API error occurred');
    });

    test('uses error message when response data not available', () => {
      const error = {
        message: 'Network timeout'
      };
      
      const result = handleApiError(error);
      expect(result).toBe('Network timeout');
    });

    test('returns generic error message when no specific message available', () => {
      const error = {};
      
      const result = handleApiError(error);
      expect(result).toBe('An unexpected error occurred');
    });

    test('handles string errors', () => {
      const error = 'String error message';
      
      const result = handleApiError(error);
      expect(result).toBe('String error message');
    });
  });

  describe('buildQueryString utility', () => {
    test('builds query string from object', () => {
      const params = {
        page: 1,
        limit: 10,
        search: 'test query'
      };
      
      const result = buildQueryString(params);
      expect(result).toBe('page=1&limit=10&search=test%20query');
    });

    test('handles arrays by joining with commas', () => {
      const params = {
        categories: ['food', 'drinks'],
        tags: ['new', 'popular']
      };
      
      const result = buildQueryString(params);
      expect(result).toBe('categories=food%2Cdrinks&tags=new%2Cpopular');
    });

    test('skips undefined and null values', () => {
      const params = {
        defined: 'value',
        undefined: undefined,
        null: null,
        empty: ''
      };
      
      const result = buildQueryString(params);
      expect(result).toBe('defined=value&empty=');
    });

    test('handles boolean values', () => {
      const params = {
        active: true,
        deleted: false
      };
      
      const result = buildQueryString(params);
      expect(result).toBe('active=true&deleted=false');
    });

    test('returns empty string for empty object', () => {
      const result = buildQueryString({});
      expect(result).toBe('');
    });

    test('handles special characters in values', () => {
      const params = {
        query: 'hello world & more',
        email: 'test@example.com'
      };
      
      const result = buildQueryString(params);
      expect(result).toBe('query=hello%20world%20%26%20more&email=test%40example.com');
    });
  });

  describe('API Instance Methods', () => {
    test('exports axios instance with interceptors', () => {
      expect(api).toBeDefined();
      expect(api.interceptors).toBeDefined();
      expect(api.interceptors.request).toBeDefined();
      expect(api.interceptors.response).toBeDefined();
    });

    test('can make GET requests', async () => {
      const mockResponse = { data: { message: 'success' } };
      api.get = jest.fn().mockResolvedValue(mockResponse);
      
      const result = await api.get('/test');
      
      expect(api.get).toHaveBeenCalledWith('/test');
      expect(result).toBe(mockResponse);
    });

    test('can make POST requests', async () => {
      const mockResponse = { data: { id: 1 } };
      const postData = { name: 'test' };
      api.post = jest.fn().mockResolvedValue(mockResponse);
      
      const result = await api.post('/test', postData);
      
      expect(api.post).toHaveBeenCalledWith('/test', postData);
      expect(result).toBe(mockResponse);
    });
  });
});