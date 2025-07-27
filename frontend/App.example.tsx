/**
 * Example App Component with Authentication
 * 
 * Demonstrates how to integrate the authentication system
 * with automatic token refresh and protected routes.
 */

import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, ProtectedRoute } from './hooks/useAuth';
import { ToastProvider } from './components/ui/Toast';
import { LoginForm, SessionMonitor } from './components/auth/LoginForm';
import { PayrollIntegration } from './components/staff/PayrollIntegration';

// Layout component with session monitor
const AuthenticatedLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <div className="app-layout">
      <header className="app-header">
        <h1>AuraConnect AI</h1>
        <SessionMonitor />
      </header>
      <main className="app-main">
        {children}
      </main>
    </div>
  );
};

// Dashboard component
const Dashboard: React.FC = () => {
  return (
    <div>
      <h2>Dashboard</h2>
      <p>Welcome to AuraConnect AI</p>
    </div>
  );
};

// Staff management component
const StaffManagement: React.FC = () => {
  return (
    <div>
      <h2>Staff Management</h2>
      {/* Example: Show payroll for staff ID 1 */}
      <PayrollIntegration staffId={1} />
    </div>
  );
};

// Admin panel component
const AdminPanel: React.FC = () => {
  return (
    <div>
      <h2>Admin Panel</h2>
      <p>Admin-only features</p>
    </div>
  );
};

// Main App component
export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <Routes>
            {/* Public routes */}
            <Route path="/login" element={<LoginForm />} />
            
            {/* Protected routes */}
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <AuthenticatedLayout>
                    <Dashboard />
                  </AuthenticatedLayout>
                </ProtectedRoute>
              }
            />
            
            {/* Staff management - requires specific roles */}
            <Route
              path="/staff/*"
              element={
                <ProtectedRoute roles={['admin', 'manager', 'payroll_manager']}>
                  <AuthenticatedLayout>
                    <StaffManagement />
                  </AuthenticatedLayout>
                </ProtectedRoute>
              }
            />
            
            {/* Admin panel - admin only */}
            <Route
              path="/admin/*"
              element={
                <ProtectedRoute roles={['admin']} requireAll>
                  <AuthenticatedLayout>
                    <AdminPanel />
                  </AuthenticatedLayout>
                </ProtectedRoute>
              }
            />
            
            {/* Default redirect */}
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  );
};

/**
 * Token Expiration Handling Flow:
 * 
 * 1. User logs in → Gets access token (30min) + refresh token (7 days)
 * 2. Makes API calls with access token
 * 3. Access token expires after 30 minutes
 * 4. Next API call gets 401 Unauthorized
 * 5. Interceptor automatically uses refresh token to get new access token
 * 6. Original request is retried with new access token
 * 7. User continues working without interruption
 * 
 * If refresh token expires:
 * - User is automatically logged out
 * - Redirected to login page with message
 * - Must login again to continue
 * 
 * The SessionMonitor component shows:
 * - Current user
 * - Time until access token expires
 * - Visual indicator when token is expired (but will auto-refresh)
 */

// Example of manual token checking
export const TokenChecker: React.FC = () => {
  const checkTokenExpiration = () => {
    const accessToken = localStorage.getItem('access_token');
    
    if (!accessToken) {
      console.log('No access token found');
      return;
    }
    
    try {
      // Decode JWT payload
      const base64Url = accessToken.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );
      
      const payload = JSON.parse(jsonPayload);
      
      // Check expiration
      const exp = new Date(payload.exp * 1000);
      const now = new Date();
      const isExpired = exp < now;
      const timeLeft = Math.floor((exp.getTime() - now.getTime()) / 1000);
      
      console.log('Token payload:', payload);
      console.log('Expires at:', exp.toLocaleString());
      console.log('Is expired:', isExpired);
      console.log('Time left:', timeLeft > 0 ? `${Math.floor(timeLeft / 60)}m ${timeLeft % 60}s` : 'Expired');
      
      // Check refresh token
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        console.log('Refresh token available - can get new access token');
      } else {
        console.log('No refresh token - must login again');
      }
      
    } catch (error) {
      console.error('Failed to decode token:', error);
    }
  };
  
  return (
    <button onClick={checkTokenExpiration}>
      Check Token Status
    </button>
  );
};