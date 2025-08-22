import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import useCustomerStore from '../../stores/useCustomerStore';

function ProtectedRoute() {
  const { isAuthenticated } = useCustomerStore();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <Outlet />;
}

export default ProtectedRoute;