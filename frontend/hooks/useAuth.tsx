/**
 * Authentication Hook with Context Provider
 * 
 * Provides authentication state management, automatic token refresh,
 * and auth event handling throughout the application.
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { AuthService, TokenStorage } from '../utils/authInterceptor';
import { useNavigate } from 'react-router-dom';

interface User {
  id: number;
  username: string;
  email: string;
  roles: string[];
  tenant_ids: number[];
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<boolean>;
  logout: (logoutAllSessions?: boolean) => Promise<void>;
  checkAuth: () => Promise<void>;
  hasRole: (role: string) => boolean;
  hasAnyRole: (roles: string[]) => boolean;
  hasAllRoles: (roles: string[]) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: React.ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();
  
  // Check authentication status on mount
  const checkAuth = useCallback(async () => {
    setIsLoading(true);
    try {
      if (TokenStorage.hasTokens()) {
        const userData = await AuthService.getCurrentUser();
        if (userData) {
          setUser(userData);
        } else {
          setUser(null);
        }
      } else {
        setUser(null);
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);
  
  // Login function
  const login = useCallback(async (username: string, password: string): Promise<boolean> => {
    setIsLoading(true);
    try {
      const result = await AuthService.login(username, password);
      
      if (result.success && result.user) {
        setUser(result.user);
        return true;
      } else {
        setUser(null);
        return false;
      }
    } catch (error) {
      console.error('Login error:', error);
      setUser(null);
      return false;
    } finally {
      setIsLoading(false);
    }
  }, []);
  
  // Logout function
  const logout = useCallback(async (logoutAllSessions = false) => {
    setIsLoading(true);
    try {
      await AuthService.logout(logoutAllSessions);
      setUser(null);
      navigate('/login');
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setIsLoading(false);
    }
  }, [navigate]);
  
  // Role checking utilities
  const hasRole = useCallback((role: string): boolean => {
    return user?.roles.includes(role) || false;
  }, [user]);
  
  const hasAnyRole = useCallback((roles: string[]): boolean => {
    return roles.some(role => user?.roles.includes(role)) || false;
  }, [user]);
  
  const hasAllRoles = useCallback((roles: string[]): boolean => {
    return roles.every(role => user?.roles.includes(role)) || false;
  }, [user]);
  
  // Listen for auth events
  useEffect(() => {
    const handleAuthLogout = (event: CustomEvent) => {
      const { reason } = event.detail;
      console.log('Auth logout event:', reason);
      
      setUser(null);
      
      // Navigate to login with reason
      navigate('/login', { 
        state: { 
          message: reason === 'refresh_token_expired' 
            ? 'Your session has expired. Please login again.' 
            : 'You have been logged out.'
        } 
      });
    };
    
    window.addEventListener('auth:logout', handleAuthLogout as EventListener);
    
    return () => {
      window.removeEventListener('auth:logout', handleAuthLogout as EventListener);
    };
  }, [navigate]);
  
  // Check auth on mount
  useEffect(() => {
    checkAuth();
  }, [checkAuth]);
  
  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    logout,
    checkAuth,
    hasRole,
    hasAnyRole,
    hasAllRoles,
  };
  
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

// Protected Route Component
interface ProtectedRouteProps {
  children: React.ReactNode;
  roles?: string[];
  requireAll?: boolean;
  fallback?: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ 
  children, 
  roles = [], 
  requireAll = false,
  fallback = null 
}) => {
  const { isAuthenticated, isLoading, hasAnyRole, hasAllRoles } = useAuth();
  const navigate = useNavigate();
  
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      navigate('/login', { 
        state: { 
          from: window.location.pathname,
          message: 'Please login to access this page.' 
        } 
      });
    }
  }, [isAuthenticated, isLoading, navigate]);
  
  if (isLoading) {
    return <div>Loading...</div>;
  }
  
  if (!isAuthenticated) {
    return null;
  }
  
  // Check role requirements
  if (roles.length > 0) {
    const hasRequiredRoles = requireAll ? hasAllRoles(roles) : hasAnyRole(roles);
    if (!hasRequiredRoles) {
      return fallback || <div>Access Denied: Insufficient permissions</div>;
    }
  }
  
  return <>{children}</>;
};