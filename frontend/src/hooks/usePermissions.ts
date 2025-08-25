import { useCallback, useMemo } from 'react';
import { useAuth } from './useAuth';

// Permission types
export type SchedulingPermission = 
  | 'scheduling.view'
  | 'scheduling.create'
  | 'scheduling.edit'
  | 'scheduling.delete'
  | 'scheduling.publish'
  | 'scheduling.generate'
  | 'payroll.view'
  | 'payroll.export'
  | 'payroll.process'
  | 'availability.view'
  | 'availability.edit'
  | 'conflicts.view'
  | 'conflicts.resolve';

export type Role = 'admin' | 'manager' | 'supervisor' | 'staff';

// Role-permission mapping
const rolePermissions: Record<Role, SchedulingPermission[]> = {
  admin: [
    'scheduling.view',
    'scheduling.create',
    'scheduling.edit',
    'scheduling.delete',
    'scheduling.publish',
    'scheduling.generate',
    'payroll.view',
    'payroll.export',
    'payroll.process',
    'availability.view',
    'availability.edit',
    'conflicts.view',
    'conflicts.resolve',
  ],
  manager: [
    'scheduling.view',
    'scheduling.create',
    'scheduling.edit',
    'scheduling.delete',
    'scheduling.publish',
    'scheduling.generate',
    'payroll.view',
    'payroll.export',
    'availability.view',
    'availability.edit',
    'conflicts.view',
    'conflicts.resolve',
  ],
  supervisor: [
    'scheduling.view',
    'scheduling.create',
    'scheduling.edit',
    'scheduling.publish',
    'availability.view',
    'availability.edit',
    'conflicts.view',
    'conflicts.resolve',
  ],
  staff: [
    'scheduling.view',
    'availability.view',
    'availability.edit', // Can edit own availability
  ],
};

interface UsePermissionsReturn {
  hasPermission: (permission: SchedulingPermission) => boolean;
  hasAnyPermission: (permissions: SchedulingPermission[]) => boolean;
  hasAllPermissions: (permissions: SchedulingPermission[]) => boolean;
  canViewSchedule: boolean;
  canEditSchedule: boolean;
  canPublishSchedule: boolean;
  canViewPayroll: boolean;
  canExportPayroll: boolean;
  canGenerateSchedule: boolean;
  canResolveConflicts: boolean;
  userRole: Role | null;
  isLoading: boolean;
}

export const usePermissions = (): UsePermissionsReturn => {
  const { user, isLoading } = useAuth();

  const userRole = useMemo(() => {
    if (!user) return null;
    // Map user.role or user.roles to our Role type
    // This depends on your auth implementation
    if (user.role) {
      return user.role.toLowerCase() as Role;
    }
    if (user.roles && user.roles.length > 0) {
      // If multiple roles, pick the highest privilege
      const roleHierarchy: Role[] = ['admin', 'manager', 'supervisor', 'staff'];
      for (const role of roleHierarchy) {
        if (user.roles.includes(role)) {
          return role;
        }
      }
    }
    return 'staff' as Role; // Default to staff
  }, [user]);

  const userPermissions = useMemo(() => {
    if (!userRole) return [];
    return rolePermissions[userRole] || [];
  }, [userRole]);

  const hasPermission = useCallback(
    (permission: SchedulingPermission): boolean => {
      return userPermissions.includes(permission);
    },
    [userPermissions]
  );

  const hasAnyPermission = useCallback(
    (permissions: SchedulingPermission[]): boolean => {
      return permissions.some(permission => hasPermission(permission));
    },
    [hasPermission]
  );

  const hasAllPermissions = useCallback(
    (permissions: SchedulingPermission[]): boolean => {
      return permissions.every(permission => hasPermission(permission));
    },
    [hasPermission]
  );

  // Convenience checks
  const canViewSchedule = hasPermission('scheduling.view');
  const canEditSchedule = hasPermission('scheduling.edit');
  const canPublishSchedule = hasPermission('scheduling.publish');
  const canViewPayroll = hasPermission('payroll.view');
  const canExportPayroll = hasPermission('payroll.export');
  const canGenerateSchedule = hasPermission('scheduling.generate');
  const canResolveConflicts = hasPermission('conflicts.resolve');

  return {
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
    userRole,
    isLoading,
  };
};

// HOC for permission-based rendering
interface PermissionGateProps {
  permission?: SchedulingPermission;
  permissions?: SchedulingPermission[];
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
  const { hasPermission, hasAnyPermission, hasAllPermissions, isLoading } = usePermissions();

  if (isLoading) {
    return <>{fallback}</>;
  }

  let hasAccess = false;

  if (permission) {
    hasAccess = hasPermission(permission);
  } else if (permissions) {
    hasAccess = requireAll ? hasAllPermissions(permissions) : hasAnyPermission(permissions);
  }

  return <>{hasAccess ? children : fallback}</>;
};