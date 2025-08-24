// API client with proper error handling and auth interceptors

import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import { authManager } from '../utils/auth';

// Use environment variable with fallback
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Create axios instance with default config
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Enable cookies for CORS
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = authManager.getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    // Add CSRF token if available
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    if (csrfToken) {
      config.headers['X-CSRF-Token'] = csrfToken;
    }
    
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling and token refresh
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };
    
    // Handle 401 Unauthorized
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      const refreshToken = authManager.getRefreshToken();
      if (refreshToken) {
        try {
          // Attempt to refresh the token
          const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          });
          
          authManager.setTokens(response.data);
          
          // Retry the original request with new token
          const newToken = authManager.getAccessToken();
          if (newToken && originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
          }
          
          return api(originalRequest);
        } catch (refreshError) {
          // Refresh failed, clear tokens and redirect to login
          authManager.clearTokens();
          window.location.href = '/login';
          return Promise.reject(refreshError);
        }
      } else {
        // No refresh token, redirect to login
        authManager.clearTokens();
        window.location.href = '/login';
      }
    }
    
    // Handle 403 Forbidden (RBAC)
    if (error.response?.status === 403) {
      console.error('Access denied. Insufficient permissions.');
      // Could dispatch an action to show permission error
    }
    
    // Handle network errors
    if (!error.response) {
      console.error('Network error:', error.message);
      // Could dispatch an action to show offline message
    }
    
    return Promise.reject(error);
  }
);

// Helper function to handle API errors consistently
export const handleApiError = (error: any): string => {
  if (axios.isAxiosError(error)) {
    if (error.response?.data?.message) {
      return error.response.data.message;
    }
    if (error.response?.data?.error) {
      return error.response.data.error;
    }
    if (error.response?.status === 404) {
      return 'Resource not found';
    }
    if (error.response?.status === 500) {
      return 'Server error. Please try again later.';
    }
    if (error.message === 'Network Error') {
      return 'Network error. Please check your connection.';
    }
  }
  return error.message || 'An unexpected error occurred';
};

// Helper to build query strings with proper encoding
export const buildQueryString = (params: Record<string, any>): string => {
  const searchParams = new URLSearchParams();
  
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null) return;
    
    if (Array.isArray(value)) {
      // For arrays, check backend expectation
      // Option 1: Comma-separated (status=pending,confirmed)
      if (value.length > 0) {
        searchParams.append(key, value.join(','));
      }
      // Option 2: Repeated params (status=pending&status=confirmed)
      // value.forEach(v => searchParams.append(key, v));
    } else if (value instanceof Date) {
      // Convert dates to ISO string
      searchParams.append(key, value.toISOString());
    } else {
      searchParams.append(key, String(value));
    }
  });
  
  return searchParams.toString();
};

export default api;