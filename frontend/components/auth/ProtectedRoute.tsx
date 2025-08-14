/**
 * Protected Route HOC
 * 
 * Protects routes that require authentication
 */

import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { tokenManager } from '../../services/tokenManager';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRoles?: string[];
  requiredPermissions?: string[];
  redirectTo?: string;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requiredRoles = [],
  requiredPermissions = [],
  redirectTo = '/auth/login',
}) => {
  const { isAuthenticated, isLoading, user } = useAuth();
  const location = useLocation();

  // Show loading spinner while checking auth
  if (isLoading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return (
      <Navigate
        to={redirectTo}
        state={{ 
          from: location.pathname,
          message: 'Please sign in to continue'
        }}
        replace
      />
    );
  }

  // Check role requirements
  if (requiredRoles.length > 0) {
    const hasRequiredRole = requiredRoles.some(role => 
      user?.role === role || user?.role === 'admin'
    );

    if (!hasRequiredRole) {
      return (
        <div className="access-denied">
          <h1>Access Denied</h1>
          <p>You don't have permission to access this page.</p>
          <p>Required role: {requiredRoles.join(' or ')}</p>
          <a href="/dashboard">Return to Dashboard</a>
        </div>
      );
    }
  }

  // Check permission requirements
  if (requiredPermissions.length > 0) {
    const hasAllPermissions = requiredPermissions.every(permission =>
      tokenManager.hasPermission(permission)
    );

    if (!hasAllPermissions) {
      return (
        <div className="access-denied">
          <h1>Access Denied</h1>
          <p>You don't have the required permissions to access this page.</p>
          <p>Required permissions: {requiredPermissions.join(', ')}</p>
          <a href="/dashboard">Return to Dashboard</a>
        </div>
      );
    }
  }

  // All checks passed, render children
  return <>{children}</>;
};

export default ProtectedRoute;

/**
 * Hook for protecting components
 */
export const useProtectedAccess = (
  requiredRoles: string[] = [],
  requiredPermissions: string[] = []
): { hasAccess: boolean; isLoading: boolean } => {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (!isAuthenticated || isLoading) {
    return { hasAccess: false, isLoading };
  }

  // Check roles
  if (requiredRoles.length > 0) {
    const hasRole = requiredRoles.some(role => 
      user?.role === role || user?.role === 'admin'
    );
    if (!hasRole) {
      return { hasAccess: false, isLoading: false };
    }
  }

  // Check permissions
  if (requiredPermissions.length > 0) {
    const hasPermissions = requiredPermissions.every(permission =>
      tokenManager.hasPermission(permission)
    );
    if (!hasPermissions) {
      return { hasAccess: false, isLoading: false };
    }
  }

  return { hasAccess: true, isLoading: false };
};