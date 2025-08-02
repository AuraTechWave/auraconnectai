import axios from 'axios';

// Create axios instance with base configuration
const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Token storage utilities
export const TokenStorage = {
  getAccessToken: () => localStorage.getItem('access_token'),
  getRefreshToken: () => localStorage.getItem('refresh_token'),
  getTokenType: () => localStorage.getItem('token_type') || 'Bearer',
  
  setTokens: (accessToken, refreshToken, tokenType = 'Bearer') => {
    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('refresh_token', refreshToken);
    localStorage.setItem('token_type', tokenType);
  },
  
  clearTokens: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('token_type');
  },
  
  hasTokens: () => {
    return !!TokenStorage.getAccessToken() && !!TokenStorage.getRefreshToken();
  }
};

// Request interceptor - add auth header
apiClient.interceptors.request.use(
  (config) => {
    const accessToken = TokenStorage.getAccessToken();
    
    if (accessToken && !config.headers['Authorization']) {
      config.headers['Authorization'] = `${TokenStorage.getTokenType()} ${accessToken}`;
    }
    
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor - handle errors
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    // Handle 401 errors
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      // For now, just clear tokens and redirect to login
      // In a real app, you would try to refresh the token first
      TokenStorage.clearTokens();
      
      // Emit event for app to handle (redirect to login)
      window.dispatchEvent(new CustomEvent('auth:logout', { 
        detail: { reason: 'unauthorized' } 
      }));
      
      return Promise.reject(error);
    }
    
    return Promise.reject(error);
  }
);

// Auth service for login/logout
export const AuthService = {
  login: async (username, password) => {
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
        error: error.response?.data?.detail || 'Login failed'
      };
    }
  },
  
  logout: async () => {
    try {
      await apiClient.post('/auth/logout');
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
  }
};

// Export configured axios instance
export default apiClient;