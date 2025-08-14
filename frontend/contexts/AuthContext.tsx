/**
 * Authentication Context Provider
 * 
 * Manages authentication state, JWT tokens, and user session
 * across the entire application.
 */

import React, { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react';
import { authService } from '../services/authService';
import { tokenManager } from '../services/tokenManager';

interface User {
  id: number;
  email: string;
  name: string;
  role: string;
  restaurant_id?: number;
  location_id?: number;
  permissions?: string[];
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  resetPassword: (email: string) => Promise<void>;
  updatePassword: (token: string, newPassword: string) => Promise<void>;
  refreshToken: () => Promise<void>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Use useRef to maintain timer reference across re-renders
  // This prevents memory leaks by ensuring the timer persists and can be properly cleared
  const refreshTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Initialize auth state from stored tokens
  useEffect(() => {
    initializeAuth();
  }, []);

  const initializeAuth = async () => {
    try {
      setIsLoading(true);
      const token = tokenManager.getAccessToken();
      
      if (token) {
        // Validate token and get user info
        const userData = await authService.getCurrentUser();
        setUser(userData);
      }
    } catch (err) {
      console.error('Failed to initialize auth:', err);
      // Clear invalid tokens
      tokenManager.clearTokens();
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (email: string, password: string) => {
    try {
      setIsLoading(true);
      setError(null);
      
      const response = await authService.login(email, password);
      
      // Store tokens
      tokenManager.setTokens(response.access_token, response.refresh_token);
      
      // Set user data
      setUser(response.user);
      
      // Set up automatic token refresh
      setupTokenRefresh();
      
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Login failed. Please try again.';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const logout = useCallback(async () => {
    try {
      setIsLoading(true);
      
      // Clear any refresh timer first
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
      
      // Call backend logout endpoint if needed
      await authService.logout();
      
      // Clear tokens
      tokenManager.clearTokens();
      
      // Clear user state
      setUser(null);
      
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const register = async (email: string, password: string, name: string) => {
    try {
      setIsLoading(true);
      setError(null);
      
      const response = await authService.register(email, password, name);
      
      // Auto-login after successful registration
      await login(email, password);
      
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Registration failed. Please try again.';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const resetPassword = async (email: string) => {
    try {
      setIsLoading(true);
      setError(null);
      
      await authService.requestPasswordReset(email);
      
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Failed to send reset email.';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const updatePassword = async (token: string, newPassword: string) => {
    try {
      setIsLoading(true);
      setError(null);
      
      await authService.resetPassword(token, newPassword);
      
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Failed to update password.';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const clearError = () => {
    setError(null);
  };

  const clearTokenRefreshTimer = useCallback(() => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
  }, []);

  const refreshToken = useCallback(async () => {
    try {
      const currentRefreshToken = tokenManager.getRefreshToken();
      
      if (!currentRefreshToken) {
        throw new Error('No refresh token available');
      }
      
      const response = await authService.refreshToken(currentRefreshToken);
      
      // Update tokens
      tokenManager.setTokens(response.access_token, response.refresh_token);
      
      // Update user if needed
      if (response.user) {
        setUser(response.user);
      }
      
      // Set up next refresh cycle
      // Clear existing timer
      clearTokenRefreshTimer();
      
      // Set up new timer (refresh 5 minutes before expiry)
      const expiresIn = tokenManager.getTokenExpiry();
      if (expiresIn > 0) {
        const refreshIn = Math.max(0, expiresIn - 5 * 60 * 1000); // 5 minutes before expiry
        refreshTimerRef.current = setTimeout(() => {
          refreshToken().catch(console.error);
        }, refreshIn);
      }
      
    } catch (err) {
      console.error('Token refresh failed:', err);
      // If refresh fails, logout user
      // Clear tokens
      tokenManager.clearTokens();
      
      // Clear user state
      setUser(null);
      
      // Clear any refresh timer
      clearTokenRefreshTimer();
      
      throw err;
    }
  }, [clearTokenRefreshTimer]);

  const setupTokenRefresh = useCallback(() => {
    // Clear existing timer
    clearTokenRefreshTimer();
    
    // Set up new timer (refresh 5 minutes before expiry)
    const expiresIn = tokenManager.getTokenExpiry();
    if (expiresIn > 0) {
      const refreshIn = Math.max(0, expiresIn - 5 * 60 * 1000); // 5 minutes before expiry
      refreshTimerRef.current = setTimeout(() => {
        refreshToken().catch(console.error);
      }, refreshIn);
    }
  }, [clearTokenRefreshTimer, refreshToken]);

  // Set up token refresh on mount if authenticated
  useEffect(() => {
    if (user && tokenManager.getAccessToken()) {
      setupTokenRefresh();
    }
    
    return () => {
      clearTokenRefreshTimer();
    };
  }, [user, setupTokenRefresh, clearTokenRefreshTimer]);

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    error,
    login,
    logout,
    register,
    resetPassword,
    updatePassword,
    refreshToken,
    clearError,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};