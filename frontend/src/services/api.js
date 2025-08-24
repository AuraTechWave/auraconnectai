import axios from 'axios';

// Secure API URL configuration
const getApiUrl = () => {
  const apiUrl = process.env.REACT_APP_API_URL;
  
  // In production, require explicit API URL configuration
  if (process.env.NODE_ENV === 'production' && !apiUrl) {
    throw new Error('REACT_APP_API_URL is required in production');
  }
  
  // Development fallback
  if (process.env.NODE_ENV === 'development' && !apiUrl) {
    console.warn('REACT_APP_API_URL not set, using development default');
    return 'http://localhost:8000';
  }
  
  // Enforce HTTPS in production
  if (process.env.NODE_ENV === 'production' && apiUrl && !apiUrl.startsWith('https://')) {
    console.error('API URL must use HTTPS in production');
    throw new Error('API URL must use HTTPS in production');
  }
  
  return apiUrl;
};

const API_BASE_URL = getApiUrl();

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000,
  withCredentials: true, // Enable cookie support
});

// Token refresh promise to prevent multiple simultaneous refresh attempts
let refreshPromise = null;

// Request interceptor for auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('customerToken');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for auth handling and error normalization
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    // Handle 401 Unauthorized
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      // If refresh is already in progress, wait for it
      if (refreshPromise) {
        await refreshPromise;
        return api(originalRequest);
      }
      
      // Attempt to refresh token
      refreshPromise = refreshToken()
        .then((newToken) => {
          if (newToken) {
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
            return api(originalRequest);
          }
          // Refresh failed, redirect to login
          handleAuthFailure();
          return Promise.reject(error);
        })
        .catch(() => {
          handleAuthFailure();
          return Promise.reject(error);
        })
        .finally(() => {
          refreshPromise = null;
        });
      
      return refreshPromise;
    }
    
    // Handle 403 Forbidden
    if (error.response?.status === 403) {
      console.error('Access forbidden:', error.response.data);
    }
    
    // Normalize error response
    const normalizedError = {
      message: error.response?.data?.detail || 
               error.response?.data?.message || 
               error.message || 
               'An unexpected error occurred',
      status: error.response?.status,
      data: error.response?.data,
    };
    
    return Promise.reject(normalizedError);
  }
);

// Refresh token function
async function refreshToken() {
  try {
    const refreshToken = localStorage.getItem('customerRefreshToken');
    if (!refreshToken) {
      return null;
    }
    
    const response = await axios.post(`${API_BASE_URL}/api/auth/refresh`, {
      refresh_token: refreshToken,
    });
    
    const { access_token, refresh_token: newRefreshToken } = response.data;
    
    localStorage.setItem('customerToken', access_token);
    if (newRefreshToken) {
      localStorage.setItem('customerRefreshToken', newRefreshToken);
    }
    
    return access_token;
  } catch (error) {
    console.error('Token refresh failed:', error);
    return null;
  }
}

// Handle authentication failure
function handleAuthFailure() {
  localStorage.removeItem('customerToken');
  localStorage.removeItem('customerRefreshToken');
  localStorage.removeItem('customer-store');
  
  // Dispatch event for global handling
  window.dispatchEvent(new CustomEvent('auth:logout'));
  
  // Redirect to login if not already there
  if (!window.location.pathname.includes('/login')) {
    window.location.href = '/login';
  }
}

// Exponential backoff for retries
const retryWithExponentialBackoff = (fn, retries = 3, delay = 1000) => {
  return fn().catch((error) => {
    if (retries === 0 || error.status < 500) {
      throw error;
    }
    
    const jitter = Math.random() * 200; // Add jitter to prevent thundering herd
    const backoffDelay = delay + jitter;
    
    console.log(`Retrying after ${backoffDelay}ms... (${retries} retries left)`);
    
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(retryWithExponentialBackoff(fn, retries - 1, delay * 2));
      }, backoffDelay);
    });
  });
};

// Enhanced API methods with retry logic for critical endpoints
export const apiWithRetry = {
  post: (url, data, config) => retryWithExponentialBackoff(() => api.post(url, data, config)),
  get: (url, config) => retryWithExponentialBackoff(() => api.get(url, config)),
};

export default api;