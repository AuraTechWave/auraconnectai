/**
 * RBAC (Role-Based Access Control) React Hooks and Context
 * 
 * This module provides React hooks and context for managing fine-grained
 * role-based access control in the frontend application.
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiClient } from '../utils/apiClient';
import { User, Role, Permission } from './useRbacApi';

// Event emitter for tenant changes
class TenantEventEmitter extends EventTarget {
  emitTenantChange(oldTenantId: number | null, newTenantId: number) {
    this.dispatchEvent(new CustomEvent('tenantChanged', {
      detail: { oldTenantId, newTenantId }
    }));
  }
  
  onTenantChange(callback: (event: CustomEvent) => void) {
    this.addEventListener('tenantChanged', callback as EventListener);
    return () => this.removeEventListener('tenantChanged', callback as EventListener);
  }
}

const tenantEventEmitter = new TenantEventEmitter();

// Types for RBAC system
export interface RBACUser {
  id: number;
  username: string;
  email: string;
  first_name?: string;
  last_name?: string;
  is_active: boolean;
  is_email_verified: boolean;
  created_at: string;
  last_login?: string;
  accessible_tenant_ids: number[];
  default_tenant_id?: number;
  roles: string[];
  permissions: string[];
}

export interface RBACContextType {
  user: RBACUser | null;
  loading: boolean;
  error: string | null;
  activeTenantId: number | null;
  
  // Authentication methods
  login: (username: string, password: string, tenantId?: number) => Promise<boolean>;
  logout: () => Promise<void>;
  refreshUser: (tenantId?: number) => Promise<void>;
  
  // Permission checking methods
  hasPermission: (permission: string, tenantId?: number, resourceId?: string) => boolean;
  hasRole: (role: string) => boolean;
  hasAnyRole: (roles: string[]) => boolean;
  hasAllRoles: (roles: string[]) => boolean;
  hasAnyPermission: (permissions: string[]) => boolean;
  hasAllPermissions: (permissions: string[]) => boolean;
  
  // Tenant management
  switchTenant: (tenantId: number) => Promise<void>;
  onTenantChange: (callback: (event: CustomEvent) => void) => (() => void);
  
  // Utility methods
  checkPermission: (permission: string, tenantId?: number, resourceId?: string) => Promise<boolean>;
  isAdmin: () => boolean;
  
  // Shared RBAC data
  users: User[];
  roles: Role[];
  permissions: Permission[];
  usersLoading: boolean;
  rolesLoading: boolean;
  permissionsLoading: boolean;
  
  // Shared data management
  fetchUsers: () => Promise<void>;
  fetchRoles: () => Promise<void>;
  fetchPermissions: () => Promise<void>;
  invalidateCache: (type?: 'users' | 'roles' | 'permissions' | 'all') => void;
}

const RBACContext = createContext<RBACContextType | null>(null);

interface RBACProviderProps {
  children: React.ReactNode;
}

// Cache keys for localStorage
const CACHE_KEYS = {
  USER_DATA: 'rbac_user_data',
  PERMISSIONS: 'rbac_permissions_cache',
  CACHE_TIMESTAMP: 'rbac_cache_timestamp',
  CACHE_TTL_MS: 15 * 60 * 1000 // 15 minutes in milliseconds
};

export const RBACProvider: React.FC<RBACProviderProps> = ({ children }) => {
  const [user, setUser] = useState<RBACUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTenantId, setActiveTenantId] = useState<number | null>(null);
  
  // Shared RBAC data state
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [rolesLoading, setRolesLoading] = useState(false);
  const [permissionsLoading, setPermissionsLoading] = useState(false);

  // Check if cache is still valid
  const isCacheValid = (): boolean => {
    const timestamp = localStorage.getItem(CACHE_KEYS.CACHE_TIMESTAMP);
    if (!timestamp) return false;
    
    const cacheTime = parseInt(timestamp, 10);
    const now = Date.now();
    return (now - cacheTime) < CACHE_KEYS.CACHE_TTL_MS;
  };

  // Load from cache
  const loadFromCache = (): RBACUser | null => {
    if (!isCacheValid()) {
      clearCache();
      return null;
    }

    const cachedData = localStorage.getItem(CACHE_KEYS.USER_DATA);
    if (cachedData) {
      try {
        return JSON.parse(cachedData) as RBACUser;
      } catch (err) {
        console.error('Failed to parse cached user data:', err);
        clearCache();
      }
    }
    return null;
  };

  // Save to cache
  const saveToCache = (userData: RBACUser) => {
    try {
      localStorage.setItem(CACHE_KEYS.USER_DATA, JSON.stringify(userData));
      localStorage.setItem(CACHE_KEYS.CACHE_TIMESTAMP, Date.now().toString());
    } catch (err) {
      console.error('Failed to save to cache:', err);
    }
  };

  // Clear cache
  const clearCache = () => {
    localStorage.removeItem(CACHE_KEYS.USER_DATA);
    localStorage.removeItem(CACHE_KEYS.PERMISSIONS);
    localStorage.removeItem(CACHE_KEYS.CACHE_TIMESTAMP);
  };

  // Initialize RBAC context on component mount
  useEffect(() => {
    initializeAuth();
  }, []);

  const initializeAuth = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('access_token');
      
      if (token) {
        // Try to load from cache first
        const cachedUser = loadFromCache();
        if (cachedUser) {
          setUser(cachedUser);
          setActiveTenantId(cachedUser.default_tenant_id || null);
          setError(null);
          console.log('Loaded user data from cache');
        } else {
          // Cache miss or expired, fetch from server
          await refreshUser();
        }
      }
    } catch (err) {
      console.error('Failed to initialize auth:', err);
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      clearCache();
    } finally {
      setLoading(false);
    }
  };

  const login = async (username: string, password: string, tenantId?: number): Promise<boolean> => {
    try {
      setLoading(true);
      setError(null);

      const formData = new FormData();
      formData.append('username', username);
      formData.append('password', password);

      const url = tenantId ? `/auth/login/rbac?tenant_id=${tenantId}` : '/auth/login/rbac';
      const response = await apiClient.post(url, formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });

      const { access_token, refresh_token, user_info } = response.data;

      // Store tokens
      localStorage.setItem('access_token', access_token);
      localStorage.setItem('refresh_token', refresh_token);

      // Set active tenant
      if (user_info.active_tenant_id) {
        setActiveTenantId(user_info.active_tenant_id);
      }

      // Refresh user data
      await refreshUser(user_info.active_tenant_id);
      
      return true;
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Login failed';
      setError(errorMessage);
      return false;
    } finally {
      setLoading(false);
    }
  };

  const logout = async (): Promise<void> => {
    try {
      // Call logout endpoint to invalidate tokens
      await apiClient.post('/auth/logout', {
        logout_all_sessions: false
      });
    } catch (err) {
      // Continue with logout even if API call fails
      console.error('Logout API call failed:', err);
    }

    // Clear local storage and state
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    clearCache(); // Clear RBAC cache
    setUser(null);
    setActiveTenantId(null);
    setError(null);
  };

  const refreshUser = async (tenantId?: number): Promise<void> => {
    try {
      const url = tenantId ? `/auth/me/rbac?tenant_id=${tenantId}` : '/auth/me/rbac';
      const response = await apiClient.get(url);
      
      const userData = response.data;
      setUser(userData);
      saveToCache(userData); // Save to cache
      
      // Update active tenant if not set
      if (!activeTenantId && userData.default_tenant_id) {
        setActiveTenantId(userData.default_tenant_id);
      }
      
      setError(null);
    } catch (err: any) {
      if (err.response?.status === 401) {
        // Token expired, clear auth
        await logout();
      } else {
        setError('Failed to load user data');
      }
    }
  };

  const hasPermission = useCallback((
    permission: string, 
    tenantId?: number, 
    resourceId?: string
  ): boolean => {
    if (!user) return false;
    
    // Admin override
    if (user.roles.includes('admin') || user.roles.includes('super_admin')) {
      return true;
    }
    
    // Check if user has the specific permission
    return user.permissions.includes(permission);
  }, [user]);

  const hasRole = useCallback((role: string): boolean => {
    if (!user) return false;
    return user.roles.includes(role);
  }, [user]);

  const hasAnyRole = useCallback((roles: string[]): boolean => {
    if (!user) return false;
    return roles.some(role => user.roles.includes(role));
  }, [user]);

  const hasAllRoles = useCallback((roles: string[]): boolean => {
    if (!user) return false;
    return roles.every(role => user.roles.includes(role));
  }, [user]);

  const hasAnyPermission = useCallback((permissions: string[]): boolean => {
    if (!user) return false;
    
    // Admin override
    if (user.roles.includes('admin') || user.roles.includes('super_admin')) {
      return true;
    }
    
    return permissions.some(permission => user.permissions.includes(permission));
  }, [user]);

  const hasAllPermissions = useCallback((permissions: string[]): boolean => {
    if (!user) return false;
    
    // Admin override
    if (user.roles.includes('admin') || user.roles.includes('super_admin')) {
      return true;
    }
    
    return permissions.every(permission => user.permissions.includes(permission));
  }, [user]);

  const switchTenant = async (tenantId: number): Promise<void> => {
    try {
      setLoading(true);
      
      // Check if user has access to this tenant
      if (!user?.accessible_tenant_ids.includes(tenantId)) {
        throw new Error('Access denied for this tenant');
      }
      
      const oldTenantId = activeTenantId;
      setActiveTenantId(tenantId);
      
      // Emit tenant change event
      tenantEventEmitter.emitTenantChange(oldTenantId, tenantId);
      
      await refreshUser(tenantId);
    } catch (err: any) {
      setError(err.message || 'Failed to switch tenant');
    } finally {
      setLoading(false);
    }
  };

  const checkPermission = async (
    permission: string, 
    tenantId?: number, 
    resourceId?: string
  ): Promise<boolean> => {
    try {
      const response = await apiClient.post('/auth/check-permission', {
        permission_key: permission,
        tenant_id: tenantId || activeTenantId,
        resource_id: resourceId
      });
      
      return response.data.has_permission;
    } catch (err) {
      console.error('Permission check failed:', err);
      return false;
    }
  };

  const isAdmin = useCallback((): boolean => {
    return hasAnyRole(['admin', 'super_admin']);
  }, [hasAnyRole]);

  // Expose tenant change event subscription
  const onTenantChange = useCallback((callback: (event: CustomEvent) => void) => {
    return tenantEventEmitter.onTenantChange(callback);
  }, []);

  // Shared data management functions
  const fetchUsers = useCallback(async () => {
    if (usersLoading) return;
    
    try {
      setUsersLoading(true);
      const response = await apiClient.get('/rbac/users?limit=1000');
      setUsers(response.data.items || response.data);
    } catch (err) {
      console.error('Failed to fetch users:', err);
    } finally {
      setUsersLoading(false);
    }
  }, [usersLoading]);

  const fetchRoles = useCallback(async () => {
    if (rolesLoading) return;
    
    try {
      setRolesLoading(true);
      const response = await apiClient.get('/rbac/roles?limit=1000');
      setRoles(response.data);
    } catch (err) {
      console.error('Failed to fetch roles:', err);
    } finally {
      setRolesLoading(false);
    }
  }, [rolesLoading]);

  const fetchPermissions = useCallback(async () => {
    if (permissionsLoading) return;
    
    try {
      setPermissionsLoading(true);
      const response = await apiClient.get('/rbac/permissions?limit=1000');
      setPermissions(response.data);
    } catch (err) {
      console.error('Failed to fetch permissions:', err);
    } finally {
      setPermissionsLoading(false);
    }
  }, [permissionsLoading]);

  const invalidateCache = useCallback((type?: 'users' | 'roles' | 'permissions' | 'all') => {
    switch (type) {
      case 'users':
        setUsers([]);
        break;
      case 'roles':
        setRoles([]);
        break;
      case 'permissions':
        setPermissions([]);
        break;
      case 'all':
      default:
        setUsers([]);
        setRoles([]);
        setPermissions([]);
        clearCache();
        break;
    }
  }, []);

  const contextValue: RBACContextType = {
    user,
    loading,
    error,
    activeTenantId,
    login,
    logout,
    refreshUser,
    hasPermission,
    hasRole,
    hasAnyRole,
    hasAllRoles,
    hasAnyPermission,
    hasAllPermissions,
    switchTenant,
    onTenantChange,
    checkPermission,
    isAdmin,
    users,
    roles,
    permissions,
    usersLoading,
    rolesLoading,
    permissionsLoading,
    fetchUsers,
    fetchRoles,
    fetchPermissions,
    invalidateCache
  };

  return (
    <RBACContext.Provider value={contextValue}>
      {children}
    </RBACContext.Provider>
  );
};

// Hook to use RBAC context
export const useRBAC = (): RBACContextType => {
  const context = useContext(RBACContext);
  if (!context) {
    throw new Error('useRBAC must be used within an RBACProvider');
  }
  return context;
};

// Convenience hooks for common operations

export const usePermission = (permission: string, tenantId?: number, resourceId?: string) => {
  const { hasPermission } = useRBAC();
  return hasPermission(permission, tenantId, resourceId);
};

export const useRole = (role: string) => {
  const { hasRole } = useRBAC();
  return hasRole(role);
};

export const useRoles = (roles: string[], requireAll = false) => {
  const { hasAnyRole, hasAllRoles } = useRBAC();
  return requireAll ? hasAllRoles(roles) : hasAnyRole(roles);
};

export const usePermissions = (permissions: string[], requireAll = false) => {
  const { hasAnyPermission, hasAllPermissions } = useRBAC();
  return requireAll ? hasAllPermissions(permissions) : hasAnyPermission(permissions);
};

export const useIsAdmin = () => {
  const { isAdmin } = useRBAC();
  return isAdmin();
};

// Higher-order component for permission-based rendering
export const withPermission = <P extends object>(
  WrappedComponent: React.ComponentType<P>,
  requiredPermission: string,
  fallback?: React.ReactNode
) => {
  return React.forwardRef<any, P>((props, ref) => {
    const hasRequiredPermission = usePermission(requiredPermission);
    
    if (!hasRequiredPermission) {
      return <>{fallback || null}</>;
    }
    
    return <WrappedComponent {...props} ref={ref} />;
  });
};

// Higher-order component for role-based rendering
export const withRole = <P extends object>(
  WrappedComponent: React.ComponentType<P>,
  requiredRole: string,
  fallback?: React.ReactNode
) => {
  return React.forwardRef<any, P>((props, ref) => {
    const hasRequiredRole = useRole(requiredRole);
    
    if (!hasRequiredRole) {
      return <>{fallback || null}</>;
    }
    
    return <WrappedComponent {...props} ref={ref} />;
  });
};

export default useRBAC;