/**
 * RBAC Guard Components
 * 
 * These components provide declarative permission and role-based access control
 * for React applications, allowing easy conditional rendering based on user permissions.
 */

import React from 'react';
import { useRBAC, usePermission, useRole, useRoles, usePermissions } from '../../hooks/useRBAC';

// Permission Guard Component
interface PermissionGuardProps {
  permission: string;
  tenantId?: number;
  resourceId?: string;
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

export const PermissionGuard: React.FC<PermissionGuardProps> = ({
  permission,
  tenantId,
  resourceId,
  fallback = null,
  children
}) => {
  const hasPermission = usePermission(permission, tenantId, resourceId);
  
  return hasPermission ? <>{children}</> : <>{fallback}</>;
};

// Role Guard Component
interface RoleGuardProps {
  role?: string;
  roles?: string[];
  requireAll?: boolean;
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

export const RoleGuard: React.FC<RoleGuardProps> = ({
  role,
  roles,
  requireAll = false,
  fallback = null,
  children
}) => {
  const hasRole = useRole(role || '');
  const hasRoles = useRoles(roles || [], requireAll);
  
  const hasAccess = role ? hasRole : hasRoles;
  
  return hasAccess ? <>{children}</> : <>{fallback}</>;
};

// Multi-Permission Guard Component
interface MultiPermissionGuardProps {
  permissions: string[];
  requireAll?: boolean;
  tenantId?: number;
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

export const MultiPermissionGuard: React.FC<MultiPermissionGuardProps> = ({
  permissions,
  requireAll = false,
  tenantId,
  fallback = null,
  children
}) => {
  const hasPermissions = usePermissions(permissions, requireAll);
  
  return hasPermissions ? <>{children}</> : <>{fallback}</>;
};

// Admin Only Guard
interface AdminGuardProps {
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

export const AdminGuard: React.FC<AdminGuardProps> = ({
  fallback = null,
  children
}) => {
  return (
    <RoleGuard roles={['admin', 'super_admin']} fallback={fallback}>
      {children}
    </RoleGuard>
  );
};

// Combined Permission and Role Guard
interface CombinedGuardProps {
  permission?: string;
  role?: string;
  permissions?: string[];
  roles?: string[];
  requireAllPermissions?: boolean;
  requireAllRoles?: boolean;
  operator?: 'AND' | 'OR'; // How to combine permission and role checks
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

export const CombinedGuard: React.FC<CombinedGuardProps> = ({
  permission,
  role,
  permissions,
  roles,
  requireAllPermissions = false,
  requireAllRoles = false,
  operator = 'AND',
  fallback = null,
  children
}) => {
  const singlePermission = usePermission(permission || '');
  const singleRole = useRole(role || '');
  const multiPermissions = usePermissions(permissions || [], requireAllPermissions);
  const multiRoles = useRoles(roles || [], requireAllRoles);
  
  let hasPermissionAccess = true;
  let hasRoleAccess = true;
  
  // Check permissions
  if (permission) {
    hasPermissionAccess = singlePermission;
  } else if (permissions && permissions.length > 0) {
    hasPermissionAccess = multiPermissions;
  }
  
  // Check roles
  if (role) {
    hasRoleAccess = singleRole;
  } else if (roles && roles.length > 0) {
    hasRoleAccess = multiRoles;
  }
  
  // Combine based on operator
  const hasAccess = operator === 'AND' 
    ? hasPermissionAccess && hasRoleAccess
    : hasPermissionAccess || hasRoleAccess;
  
  return hasAccess ? <>{children}</> : <>{fallback}</>;
};

// Conditional Component (shows/hides based on permission/role)
interface ConditionalProps {
  show: boolean;
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

export const Conditional: React.FC<ConditionalProps> = ({
  show,
  fallback = null,
  children
}) => {
  return show ? <>{children}</> : <>{fallback}</>;
};

// Protected Section Component (with loading state)
interface ProtectedSectionProps {
  permission?: string;
  role?: string;
  permissions?: string[];
  roles?: string[];
  requireAll?: boolean;
  tenantId?: number;
  showLoading?: boolean;
  loadingComponent?: React.ReactNode;
  unauthorizedComponent?: React.ReactNode;
  children: React.ReactNode;
}

export const ProtectedSection: React.FC<ProtectedSectionProps> = ({
  permission,
  role,
  permissions,
  roles,
  requireAll = false,
  tenantId,
  showLoading = true,
  loadingComponent,
  unauthorizedComponent,
  children
}) => {
  const { loading, user } = useRBAC();
  
  // Show loading state
  if (loading && showLoading) {
    return <>{loadingComponent || <div>Loading permissions...</div>}</>;
  }
  
  // Show unauthorized if not logged in
  if (!user) {
    return <>{unauthorizedComponent || <div>Please log in to access this content.</div>}</>;
  }
  
  // Check permissions/roles
  if (permission) {
    return (
      <PermissionGuard 
        permission={permission} 
        tenantId={tenantId}
        fallback={unauthorizedComponent}
      >
        {children}
      </PermissionGuard>
    );
  }
  
  if (role) {
    return (
      <RoleGuard role={role} fallback={unauthorizedComponent}>
        {children}
      </RoleGuard>
    );
  }
  
  if (permissions && permissions.length > 0) {
    return (
      <MultiPermissionGuard 
        permissions={permissions}
        requireAll={requireAll}
        tenantId={tenantId}
        fallback={unauthorizedComponent}
      >
        {children}
      </MultiPermissionGuard>
    );
  }
  
  if (roles && roles.length > 0) {
    return (
      <RoleGuard roles={roles} requireAll={requireAll} fallback={unauthorizedComponent}>
        {children}
      </RoleGuard>
    );
  }
  
  // No restrictions specified, show content if user is authenticated
  return <>{children}</>;
};

// Resource-specific guards for common use cases

export const PayrollGuard: React.FC<{ 
  action: 'read' | 'write' | 'approve' | 'export';
  fallback?: React.ReactNode;
  children: React.ReactNode;
}> = ({ action, fallback, children }) => (
  <PermissionGuard permission={`payroll:${action}`} fallback={fallback}>
    {children}
  </PermissionGuard>
);

export const StaffGuard: React.FC<{ 
  action: 'read' | 'write' | 'delete' | 'manage_schedule';
  fallback?: React.ReactNode;
  children: React.ReactNode;
}> = ({ action, fallback, children }) => (
  <PermissionGuard permission={`staff:${action}`} fallback={fallback}>
    {children}
  </PermissionGuard>
);

export const OrderGuard: React.FC<{ 
  action: 'read' | 'write' | 'delete' | 'manage_kitchen';
  fallback?: React.ReactNode;
  children: React.ReactNode;
}> = ({ action, fallback, children }) => (
  <PermissionGuard permission={`order:${action}`} fallback={fallback}>
    {children}
  </PermissionGuard>
);

export const SystemGuard: React.FC<{ 
  action: 'read' | 'write' | 'audit' | 'backup';
  fallback?: React.ReactNode;
  children: React.ReactNode;
}> = ({ action, fallback, children }) => (
  <PermissionGuard permission={`system:${action}`} fallback={fallback}>
    {children}
  </PermissionGuard>
);

// Tenant-aware guard
interface TenantGuardProps {
  tenantId: number;
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

export const TenantGuard: React.FC<TenantGuardProps> = ({
  tenantId,
  fallback = null,
  children
}) => {
  const { user } = useRBAC();
  
  const hasAccess = user?.accessible_tenant_ids.includes(tenantId) || 
                   user?.roles.includes('admin') || 
                   user?.roles.includes('super_admin');
  
  return hasAccess ? <>{children}</> : <>{fallback}</>;
};

export default {
  PermissionGuard,
  RoleGuard,
  MultiPermissionGuard,
  AdminGuard,
  CombinedGuard,
  Conditional,
  ProtectedSection,
  PayrollGuard,
  StaffGuard,
  OrderGuard,
  SystemGuard,
  TenantGuard
};