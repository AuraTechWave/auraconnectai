import React, { useState, useEffect } from 'react';
import { useAuth } from './useAuth';

interface UsePermissionsReturn {
  roles: string[];
  permissions: string[];
  isLoading: boolean;
  hasRole: (role: string) => boolean;
  hasPermission: (permission: string) => boolean;
  hasAnyPermission: (permissions: string[]) => boolean;
  hasAllPermissions: (permissions: string[]) => boolean;
  // Convenience properties for common permissions
  canViewSchedule: boolean;
  canEditSchedule: boolean;
  canPublishSchedule: boolean;
  canViewPayroll: boolean;
  canExportPayroll: boolean;
  canGenerateSchedule: boolean;
  canResolveConflicts: boolean;
  userRole: string | null;
}

// Role-based permissions mapping
const ROLE_PERMISSIONS: Record<string, string[]> = {
  admin: ['*'], // Admin has all permissions
  manager: [
    'view_dashboard',
    'manage_staff',
    'view_reports',
    'manage_menu',
    'manage_orders',
    'view_analytics',
    'manage_inventory'
  ],
  staff: [
    'view_orders',
    'update_orders',
    'view_menu',
    'manage_tables'
  ],
  customer: [
    'view_menu',
    'place_order',
    'view_own_orders'
  ]
};

export const usePermissions = (): UsePermissionsReturn => {
  const { user, isLoading: authLoading } = useAuth();
  const [permissions, setPermissions] = useState<string[]>([]);
  const [roles, setRoles] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!authLoading) {
      if (user) {
        // Set roles
        const userRoles = user.roles || (user.role ? [user.role] : []);
        setRoles(userRoles);

        // Set permissions based on roles
        const allPermissions = new Set<string>();
        userRoles.forEach(role => {
          const rolePerms = ROLE_PERMISSIONS[role] || [];
          rolePerms.forEach(perm => allPermissions.add(perm));
        });
        setPermissions(Array.from(allPermissions));
      } else {
        setRoles([]);
        setPermissions([]);
      }
      setIsLoading(false);
    }
  }, [user, authLoading]);

  const hasRole = (role: string): boolean => {
    return roles.includes(role);
  };

  const hasPermission = (permission: string): boolean => {
    // Admin has all permissions
    if (permissions.includes('*')) return true;
    return permissions.includes(permission);
  };

  const hasAnyPermission = (perms: string[]): boolean => {
    return perms.some(p => hasPermission(p));
  };

  const hasAllPermissions = (perms: string[]): boolean => {
    return perms.every(p => hasPermission(p));
  };

  // Convenience checks
  const canViewSchedule = hasPermission('view_dashboard') || hasPermission('*');
  const canEditSchedule = hasPermission('manage_staff') || hasPermission('*');
  const canPublishSchedule = hasPermission('manage_staff') || hasPermission('*');
  const canViewPayroll = hasPermission('view_reports') || hasPermission('*');
  const canExportPayroll = hasPermission('view_reports') || hasPermission('*');
  const canGenerateSchedule = hasPermission('manage_staff') || hasPermission('*');
  const canResolveConflicts = hasPermission('manage_staff') || hasPermission('*');

  return {
    roles,
    permissions,
    isLoading,
    hasRole,
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
    canViewSchedule,
    canEditSchedule,
    canPublishSchedule,
    canViewPayroll,
    canExportPayroll,
    canGenerateSchedule,
    canResolveConflicts,
    userRole: user?.role || null
  };
};

// Permission Gate component for permission-based rendering
interface PermissionGateProps {
  permission?: string;
  permissions?: string[];
  requireAll?: boolean;
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

export const PermissionGate: React.FC<PermissionGateProps> = ({
  permission,
  permissions,
  requireAll = false,
  fallback = null,
  children,
}) => {
  const { hasPermission, isLoading } = usePermissions();

  if (isLoading) {
    return <>{fallback}</>;
  }

  let hasAccess = false;

  if (permission) {
    hasAccess = hasPermission(permission);
  } else if (permissions) {
    if (requireAll) {
      hasAccess = permissions.every(p => hasPermission(p));
    } else {
      hasAccess = permissions.some(p => hasPermission(p));
    }
  }

  return <>{hasAccess ? children : fallback}</>;
};