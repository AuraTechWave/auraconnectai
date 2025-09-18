import React from 'react';
import { Navigate } from 'react-router-dom';
import { usePermissions } from '../hooks/usePermissions';
import LoadingSpinner from '../components/customer/LoadingSpinner';
import ErrorMessage from '../components/customer/ErrorMessage';

interface RoleGuardProps {
  children: React.ReactNode;
  allowedRoles?: string[];
  allowedPermissions?: string[];
  requireAll?: boolean;
  fallback?: React.ReactNode;
}

export const RoleGuard: React.FC<RoleGuardProps> = ({
  children,
  allowedRoles = [],
  allowedPermissions = [],
  requireAll = false,
  fallback,
}) => {
  const { roles, permissions, isLoading, hasRole, hasPermission } = usePermissions();

  if (isLoading) {
    return <LoadingSpinner message="Checking permissions..." />;
  }

  const roleCheck = allowedRoles.length === 0 || 
    (requireAll 
      ? allowedRoles.every(role => hasRole(role))
      : allowedRoles.some(role => hasRole(role)));

  const permissionCheck = allowedPermissions.length === 0 ||
    (requireAll
      ? allowedPermissions.every(perm => hasPermission(perm))
      : allowedPermissions.some(perm => hasPermission(perm)));

  const hasAccess = requireAll ? (roleCheck && permissionCheck) : (roleCheck || permissionCheck);

  if (!hasAccess) {
    if (fallback) {
      return <>{fallback}</>;
    }
    return (
      <ErrorMessage 
        type="error"
        message="You don't have permission to access this resource. Please contact your administrator."
        onRetry={() => window.location.reload()}
      />
    );
  }

  return <>{children}</>;
};

export default RoleGuard;