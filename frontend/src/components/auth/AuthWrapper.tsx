import React, { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';

interface AuthWrapperProps {
  children: ReactNode;
  requiredRoles?: string[];
}

// Simple auth wrapper - in production this would connect to your auth system
export const AuthWrapper: React.FC<AuthWrapperProps> = ({ children, requiredRoles }) => {
  // For now, assume user is authenticated
  // In production, check actual auth state and roles
  const isAuthenticated = true;
  const userRoles = ['owner', 'manager']; // Mock roles
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  if (requiredRoles && requiredRoles.length > 0) {
    const hasRequiredRole = requiredRoles.some(role => userRoles.includes(role));
    if (!hasRequiredRole) {
      return <Navigate to="/unauthorized" replace />;
    }
  }
  
  return <>{children}</>;
};