/**
 * Authentication Interceptor for handling token expiration and refresh
 * 
 * This interceptor automatically handles:
 * - Token expiration detection
 * - Automatic token refresh
 * - Request retry after refresh
 * - Queue management for concurrent requests
 */

import axios, { AxiosError, AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';

// Token storage keys
const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const TOKEN_TYPE_KEY = 'token_type';

// Token storage utilities
export const TokenStorage = {
  getAccessToken: (): string | null => localStorage.getItem(ACCESS_TOKEN_KEY),
  getRefreshToken: (): string | null => localStorage.getItem(REFRESH_TOKEN_KEY),
  getTokenType: (): string => localStorage.getItem(TOKEN_TYPE_KEY) || 'Bearer',
  
  setTokens: (accessToken: string, refreshToken: string, tokenType: string = 'Bearer') => {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
    localStorage.setItem(TOKEN_TYPE_KEY, tokenType);
  },
  
  clearTokens: () => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(TOKEN_TYPE_KEY);
  },
  
  hasTokens: (): boolean => {
    return !!TokenStorage.getAccessToken() && !!TokenStorage.getRefreshToken();
  }
};

// Create axios instance
const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request queue for handling concurrent requests during token refresh
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: any) => void;
}> = [];

// Process the queue after token refresh
const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token!);
    }
  });
  
  failedQueue = [];
};

// Check if token is expired by decoding JWT
export const isTokenExpired = (token: string): boolean => {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    
    const { exp } = JSON.parse(jsonPayload);
    const currentTime = Date.now() / 1000;
    
    // Consider token expired if it expires in less than 1 minute
    return exp < currentTime + 60;
  } catch {
    // If we can't decode the token, consider it expired
    return true;
  }
};

// Request interceptor - add auth header
apiClient.interceptors.request.use(
  (config) => {
    const accessToken = TokenStorage.getAccessToken();
    
    if (accessToken && !config.headers['Authorization']) {
      // Check if token is expired before making request
      if (isTokenExpired(accessToken)) {
        // Token is expired, let the response interceptor handle it
        console.log('Access token expired, will refresh on response');
      }
      
      config.headers['Authorization'] = `${TokenStorage.getTokenType()} ${accessToken}`;
    }
    
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor - handle 401 errors
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };
    
    // Check if error is 401 and we haven't already tried to refresh
    if (error.response?.status === 401 && !originalRequest._retry && TokenStorage.hasTokens()) {
      if (isRefreshing) {
        // If we're already refreshing, queue this request
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then(token => {
          originalRequest.headers!['Authorization'] = `${TokenStorage.getTokenType()} ${token}`;
          return apiClient(originalRequest);
        }).catch(err => {
          return Promise.reject(err);
        });
      }
      
      originalRequest._retry = true;
      isRefreshing = true;
      
      const refreshToken = TokenStorage.getRefreshToken();
      
      try {
        const response = await axios.post('/auth/refresh', {
          refresh_token: refreshToken
        }, {
          baseURL: apiClient.defaults.baseURL,
          headers: {
            'Content-Type': 'application/json'
          }
        });
        
        const { access_token, token_type = 'Bearer' } = response.data;
        
        // Update stored access token
        localStorage.setItem(ACCESS_TOKEN_KEY, access_token);
        localStorage.setItem(TOKEN_TYPE_KEY, token_type);
        
        // Update the Authorization header
        apiClient.defaults.headers.common['Authorization'] = `${token_type} ${access_token}`;
        originalRequest.headers!['Authorization'] = `${token_type} ${access_token}`;
        
        processQueue(null, access_token);
        
        // Retry the original request
        return apiClient(originalRequest);
        
      } catch (refreshError) {
        processQueue(refreshError, null);
        
        // Refresh failed - clear tokens and redirect to login
        TokenStorage.clearTokens();
        
        // Emit event for app to handle (redirect to login)
        window.dispatchEvent(new CustomEvent('auth:logout', { 
          detail: { reason: 'refresh_token_expired' } 
        }));
        
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }
    
    return Promise.reject(error);
  }
);

// Auth service for login/logout
export const AuthService = {
  login: async (username: string, password: string) => {
    try {
      const formData = new FormData();
      formData.append('username', username);
      formData.append('password', password);
      
      const response = await apiClient.post('/auth/login', formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      });
      
      const { 
        access_token, 
        refresh_token, 
        token_type = 'Bearer',
        user_info 
      } = response.data;
      
      // Store tokens
      TokenStorage.setTokens(access_token, refresh_token, token_type);
      
      // Set default auth header
      apiClient.defaults.headers.common['Authorization'] = `${token_type} ${access_token}`;
      
      return {
        success: true,
        user: user_info
      };
      
    } catch (error) {
      console.error('Login failed:', error);
      return {
        success: false,
        error: error instanceof AxiosError ? error.response?.data?.detail : 'Login failed'
      };
    }
  },
  
  logout: async (logoutAllSessions = false) => {
    try {
      // Call logout endpoint
      await apiClient.post('/auth/logout', {
        logout_all_sessions: logoutAllSessions
      });
    } catch (error) {
      console.error('Logout API call failed:', error);
    } finally {
      // Always clear local tokens
      TokenStorage.clearTokens();
      delete apiClient.defaults.headers.common['Authorization'];
      
      // Emit logout event
      window.dispatchEvent(new CustomEvent('auth:logout', { 
        detail: { reason: 'user_logout' } 
      }));
    }
  },
  
  getCurrentUser: async () => {
    try {
      const response = await apiClient.get('/auth/me');
      return response.data;
    } catch (error) {
      return null;
    }
  },
  
  isAuthenticated: (): boolean => {
    const accessToken = TokenStorage.getAccessToken();
    if (!accessToken) return false;
    
    // Check if token is not expired
    return !isTokenExpired(accessToken);
  }
};

// Export configured axios instance
export default apiClient;