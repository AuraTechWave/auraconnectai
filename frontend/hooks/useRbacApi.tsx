import { useState, useCallback } from 'react';
import { apiClient } from '../utils/apiClient';

interface RetryOptions {
  maxRetries?: number;
  baseDelay?: number;
  maxDelay?: number;
}

interface ApiResponse<T> {
  data: T;
  loading: boolean;
  error: string | null;
  retry: () => void;
}

interface PaginatedResponse<T> {
  items: T[];
  total_pages: number;
  total_count: number;
  page: number;
  page_size: number;
}

interface User {
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
}

interface Role {
  id: number;
  name: string;
  display_name: string;
  description?: string;
  parent_role_id?: number;
  is_active: boolean;
  is_system_role: boolean;
  created_at: string;
  tenant_ids: number[];
  permissions?: Permission[];
}

interface Permission {
  id: number;
  key: string;
  name: string;
  description?: string;
  resource: string;
  action: string;
  is_active: boolean;
  is_system_permission: boolean;
  tenant_ids: number[];
}

interface AuditLogEntry {
  id: number;
  action: string;
  entity_type: string;
  entity_id?: number;
  details?: string;
  performed_by_user_id: number;
  performed_by_username: string;
  tenant_id?: number;
  created_at: string;
}

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

const useRetryableApi = <T,>(
  apiCall: () => Promise<{ data: T }>,
  options: RetryOptions = {}
): ApiResponse<T> => {
  const {
    maxRetries = 3,
    baseDelay = 1000,
    maxDelay = 10000
  } = options;

  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const executeWithRetry = useCallback(async () => {
    setLoading(true);
    setError(null);

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        const response = await apiCall();
        setData(response.data);
        setError(null);
        return;
      } catch (err: any) {
        const isLastAttempt = attempt === maxRetries;
        
        if (isLastAttempt) {
          setError(err.response?.data?.detail || err.message || 'API call failed');
          setData(null);
        } else {
          // Exponential backoff with jitter
          const delay = Math.min(
            baseDelay * Math.pow(2, attempt) + Math.random() * 1000,
            maxDelay
          );
          await sleep(delay);
        }
      }
    }
  }, [apiCall, maxRetries, baseDelay, maxDelay]);

  const retry = useCallback(() => {
    executeWithRetry();
  }, [executeWithRetry]);

  return {
    data: data as T,
    loading,
    error,
    retry
  };
};

export const useRbacApi = () => {
  // Users API
  const fetchUsers = useCallback((params: Record<string, any> = {}) => {
    const queryParams = new URLSearchParams(params).toString();
    return useRetryableApi<PaginatedResponse<User>>(
      () => apiClient.get(`/rbac/users?${queryParams}`)
    );
  }, []);

  const fetchUser = useCallback((userId: number) => {
    return useRetryableApi<User>(
      () => apiClient.get(`/rbac/users/${userId}`)
    );
  }, []);

  const createUser = useCallback(async (userData: Partial<User>) => {
    return apiClient.post('/rbac/users', userData);
  }, []);

  const updateUser = useCallback(async (userId: number, userData: Partial<User>) => {
    return apiClient.put(`/rbac/users/${userId}`, userData);
  }, []);

  const deleteUser = useCallback(async (userId: number) => {
    return apiClient.delete(`/rbac/users/${userId}`);
  }, []);

  const bulkDeleteUsers = useCallback(async (userIds: number[]) => {
    return apiClient.post('/rbac/users/bulk-delete', { user_ids: userIds });
  }, []);

  const bulkActivateUsers = useCallback(async (userIds: number[]) => {
    return apiClient.post('/rbac/users/bulk-activate', { user_ids: userIds });
  }, []);

  const bulkDeactivateUsers = useCallback(async (userIds: number[]) => {
    return apiClient.post('/rbac/users/bulk-deactivate', { user_ids: userIds });
  }, []);

  const bulkAssignRole = useCallback(async (userIds: number[], roleId: number) => {
    return apiClient.post('/rbac/users/bulk-assign-role', { 
      user_ids: userIds, 
      role_id: roleId 
    });
  }, []);

  // Roles API
  const fetchRoles = useCallback((params: Record<string, any> = {}) => {
    const queryParams = new URLSearchParams(params).toString();
    return useRetryableApi<Role[]>(
      () => apiClient.get(`/rbac/roles?${queryParams}`)
    );
  }, []);

  const fetchRole = useCallback((roleId: number) => {
    return useRetryableApi<Role>(
      () => apiClient.get(`/rbac/roles/${roleId}`)
    );
  }, []);

  const createRole = useCallback(async (roleData: Partial<Role>) => {
    return apiClient.post('/rbac/roles', roleData);
  }, []);

  const updateRole = useCallback(async (roleId: number, roleData: Partial<Role>) => {
    return apiClient.put(`/rbac/roles/${roleId}`, roleData);
  }, []);

  const deleteRole = useCallback(async (roleId: number) => {
    return apiClient.delete(`/rbac/roles/${roleId}`);
  }, []);

  // Permissions API
  const fetchPermissions = useCallback((params: Record<string, any> = {}) => {
    const queryParams = new URLSearchParams(params).toString();
    return useRetryableApi<Permission[]>(
      () => apiClient.get(`/rbac/permissions?${queryParams}`)
    );
  }, []);

  const assignPermissionToRole = useCallback(async (roleId: number, permissionId: number) => {
    return apiClient.post('/rbac/assign-permission', {
      role_id: roleId,
      permission_id: permissionId
    });
  }, []);

  const removePermissionFromRole = useCallback(async (roleId: number, permissionId: number) => {
    return apiClient.post('/rbac/remove-permission', {
      role_id: roleId,
      permission_id: permissionId
    });
  }, []);

  // Role assignments
  const assignRoleToUser = useCallback(async (userId: number, roleId: number, tenantId?: number) => {
    return apiClient.post('/rbac/assign-role', {
      user_id: userId,
      role_id: roleId,
      tenant_id: tenantId
    });
  }, []);

  const removeRoleFromUser = useCallback(async (userId: number, roleId: number) => {
    return apiClient.post('/rbac/remove-role', {
      user_id: userId,
      role_id: roleId
    });
  }, []);

  // Audit logs
  const fetchAuditLogs = useCallback((params: Record<string, any> = {}) => {
    const queryParams = new URLSearchParams(params).toString();
    return useRetryableApi<{
      entries: AuditLogEntry[];
      total_count: number;
      page: number;
      page_size: number;
    }>(
      () => apiClient.get(`/rbac/audit-logs?${queryParams}`)
    );
  }, []);

  // System info
  const fetchSystemInfo = useCallback(() => {
    return useRetryableApi<{
      users: number;
      roles: number;
      permissions: number;
      system_version: string;
    }>(
      () => apiClient.get('/rbac/system-info')
    );
  }, []);

  return {
    // Users
    fetchUsers,
    fetchUser,
    createUser,
    updateUser,
    deleteUser,
    bulkDeleteUsers,
    bulkActivateUsers,
    bulkDeactivateUsers,
    bulkAssignRole,
    
    // Roles
    fetchRoles,
    fetchRole,
    createRole,
    updateRole,
    deleteRole,
    
    // Permissions
    fetchPermissions,
    assignPermissionToRole,
    removePermissionFromRole,
    
    // Role assignments
    assignRoleToUser,
    removeRoleFromUser,
    
    // Audit logs
    fetchAuditLogs,
    
    // System
    fetchSystemInfo
  };
};

export type { User, Role, Permission, AuditLogEntry, PaginatedResponse };